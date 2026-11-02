"""Model-without-the-harness experiment.

No tools, no loop: the model gets the problem statement plus the source excerpts around the gold hunks
(an ORACLE localization) and must answer with SEARCH/REPLACE edit blocks. This separates two abilities:

  * can the model write the fix when it is handed the right code?  (this script)
  * can the tool loop get the model to the right code and to an edit?  (gate_run.py)

Phase 1 (server only, safe to run while gate_run.py is using the repo checkout):
  python raw_solve.py --tag raw_off --tasks-file gate12.txt --thinking off
Phase 2 (touches the repo checkout, so run it when nothing else is using it):
  python raw_solve.py --tag raw_off --verify-only

Results: runs\\<tag>.raw.jsonl (one row per task, generation + parse stats, diff, and after phase 2 `resolved`).
"""
import argparse, difflib, json, re, subprocess, sys, time, urllib.request
from pathlib import Path

import run_local as R

HERE = Path(__file__).resolve().parent
WINDOW = 40  # lines of context either side of each gold hunk

SYSTEM = "You are an expert software engineer fixing a bug in an open-source Python repository."
USER_TMPL = """Repository: {repo}

Problem statement:
{problem}

Source excerpts from the buggy commit (these are the regions that matter):

{excerpts}

Fix the bug with the smallest correct change. Reply with one or more edit blocks in exactly this format and nothing else:

<<<<<<< SEARCH path/to/file.py
exact lines copied from the excerpt
=======
replacement lines
>>>>>>> REPLACE
"""

BLOCK_RE = re.compile(r"<<<<<<< SEARCH(?:[ \t]+(\S+))?[ \t]*\r?\n(.*?)\r?\n=======[ \t]*\r?\n(.*?)\r?\n?>>>>>>>(?:[ \t]*REPLACE)?", re.S)


def git_show(base, path):
    r = subprocess.run(["git", "-C", str(R.REPO), "show", f"{base}:{path}"], capture_output=True)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None


def gold_regions(task):
    """[(path, start_line, end_line)] windows around each gold hunk (1-based, inclusive)."""
    regs, cur = [], None
    for line in task["patch"].splitlines():
        m = re.match(r"--- a/(\S+)", line)
        if m:
            cur = m.group(1)
            continue
        m = re.match(r"@@ -(\d+)(?:,(\d+))? ", line)
        if m and cur:
            a, n = int(m.group(1)), int(m.group(2) or 1)
            regs.append((cur, max(1, a - WINDOW), a + n + WINDOW))
    merged = []
    for p, s, e in sorted(regs):
        if merged and merged[-1][0] == p and s <= merged[-1][2] + 1:
            merged[-1] = (p, merged[-1][1], max(e, merged[-1][2]))
        else:
            merged.append((p, s, e))
    return merged


def build_prompt(task):
    parts = []
    for p, s, e in gold_regions(task):
        txt = git_show(task["base_commit"], p)
        if txt is None:
            continue
        lines = txt.split("\n")
        seg = "\n".join(lines[s - 1:e])
        parts.append(f"### {p} (lines {s}-{min(e, len(lines))})\n```python\n{seg}\n```")
    return USER_TMPL.format(repo=task["repo"], problem=task["problem_statement"][:4000], excerpts="\n\n".join(parts))


def chat_raw(system, user, thinking, temp, top_p, top_k, max_tokens):
    payload = {"model": "local", "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
               "temperature": temp, "max_tokens": max_tokens, "stream": False}
    if top_p is not None:
        payload["top_p"] = top_p
    if top_k is not None:
        payload["top_k"] = top_k
    if not thinking:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    req = urllib.request.Request(R.OLLAMA, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=None) as resp:
        return json.loads(resp.read())


def apply_blocks(task, text):
    """Apply SEARCH/REPLACE blocks to the base files in memory; return (unified diff, info)."""
    blocks = BLOCK_RE.findall(text or "")
    info = {"blocks": len(blocks), "applied": 0, "missing": 0, "ambiguous": 0}
    files = {}
    for path, search, replace in blocks:
        if not path:
            # the model left the path off: use the excerpted file that actually contains the search text
            cands = [p for p, _, _ in gold_regions(task) if (git_show(task["base_commit"], p) or "").count(search)]
            path = cands[0] if cands else (gold_regions(task) or [("", 0, 0)])[0][0]
        if path not in files:
            files[path] = git_show(task["base_commit"], path)
        cur = files[path]
        if cur is None:
            info["missing"] += 1
            continue
        n = cur.count(search)
        if n == 0:
            info["missing"] += 1
            continue
        if n > 1:
            info["ambiguous"] += 1
        files[path] = cur.replace(search, replace, 1)
        info["applied"] += 1
    diff = ""
    for path, new in files.items():
        old = git_show(task["base_commit"], path)
        if old is None or new == old:
            continue
        d = difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), f"a/{path}", f"b/{path}", n=3)
        for line in d:
            diff += line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
    return diff, info


def read_ids(args):
    ids = []
    if args.tasks:
        ids += [t for t in re.split(r"[,\s]+", args.tasks) if t]
    if args.tasks_file:
        ids += [t for t in re.split(r"[,\s]+", Path(args.tasks_file).read_text(encoding="utf-8")) if t]
    return ids


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--tasks", default=None)
    ap.add_argument("--tasks-file", default=None)
    ap.add_argument("--thinking", choices=["on", "off"], default="off")
    ap.add_argument("--temp", type=float, default=0.2)
    ap.add_argument("--top-p", type=float, default=None)
    ap.add_argument("--top-k", type=int, default=None)
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--samples", type=int, default=1, help="independent samples per task")
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--verify-repo", default=None, help="alternate checkout to verify in (lets verification run while gate_run.py uses the main one)")
    args = ap.parse_args()

    runs = HERE / "runs"
    runs.mkdir(exist_ok=True)
    out = runs / f"{args.tag}.raw.jsonl"

    if args.verify_only:
        rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines() if l.strip()]
        for row in rows:
            task = R.load_task(row["task"])
            R.set_repo(task["repo"].split("/")[-1])
            if args.verify_repo:
                R.REPO = Path(args.verify_repo)
            # re-derive the diff from the stored model output so parser fixes apply to old runs
            row["diff"], info = apply_blocks(task, row["content"])
            row.update(info)
            if row["diff"].strip():
                passed, log = R.verify(task, row["diff"])
                row["resolved"], row["verify_tail"] = bool(passed), log[-300:]
            else:
                row["resolved"] = False
            print(f"{row['task']} s{row['sample']} resolved={row['resolved']}", flush=True)
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        n = sum(1 for r in rows if r["resolved"])
        print(f"[raw_solve] verified {n}/{len(rows)} resolved", flush=True)
        return

    ids = read_ids(args)
    for tid in ids:
        task = R.load_task(tid)
        R.set_repo(task["repo"].split("/")[-1])
        user = build_prompt(task)
        for s in range(args.samples):
            t0 = time.time()
            resp = chat_raw(SYSTEM, user, args.thinking == "on", args.temp, args.top_p, args.top_k, args.max_tokens)
            ch = resp["choices"][0]
            m = ch["message"]
            content = m.get("content") or ""
            diff, info = apply_blocks(task, content)
            row = {"task": tid, "sample": s, "tag": args.tag, "thinking": args.thinking, "temp": args.temp,
                   "finish": ch.get("finish_reason"), "prompt_tokens": (resp.get("usage") or {}).get("prompt_tokens"),
                   "completion_tokens": (resp.get("usage") or {}).get("completion_tokens"),
                   "reasoning_chars": len(m.get("reasoning_content") or ""), "content_chars": len(content),
                   "secs": round(time.time() - t0, 1), "diff": diff, "content": content[:6000], **info, "resolved": None}
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"{tid} s{s} finish={row['finish']} ctok={row['completion_tokens']} reas={row['reasoning_chars']} "
                  f"blocks={info['blocks']} applied={info['applied']} missing={info['missing']} diff={len(diff)} "
                  f"secs={row['secs']}", flush=True)


if __name__ == "__main__":
    main()
