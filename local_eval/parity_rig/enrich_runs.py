"""enrich_runs.py - extract max intelligence from run dirs (bank-agnostic).

Per (bank, rep, task) row, joins: task_results + traces + logs + patches + test_outputs
+ tasks.jsonl gold, and emits enriched.jsonl with:

  outcome           SOLVED / NO_PATCH / WRONG_FILE / RIGHT_FILE_WRONG / NEAR_MISS (>=80% of
                    gold added-lines present in landed patch) / SAME_FILE_PARTIAL (>=40%)
  distance_frac     fraction of gold added-lines present in the landed patch (0..1)
  gold_file_touched bool (did the patch touch any gold file)
  anchor_compliance bool (a run_command grep happened BEFORE the first edit_file)
  first_edit_call   tool-call index of first edit_file (None if none)
  n_edits, n_submits, n_status, n_dispatch
  thinking_chars    sum of "(N chars)" thought sizes from the agent log (overthinking proxy)
  patch_sha12       hash of the landed patch (mode clustering: same-wrong-patch across reps?)
  test_passed       parse "N passed" from test log; test_failed likewise

Aggregates printed: outcome class distribution, compliance x outcome 2x2,
per-flippy-task patch-mode clustering (unique failing patch shas / fails).

Usage: python enrich_runs.py <bank_dir> [<bank_dir> ...]     (dir contains r0..rN subdirs)
"""
import hashlib
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = Path(__file__).resolve().parent
G = HERE.parent.parent  # Gemma/
TASKS = {}
for l in open(G / "comp_files" / "tasks.jsonl", encoding="utf-8"):
    if l.strip():
        d = json.loads(l)
        TASKS[d["instance_id"]] = d

GOLD_ADD = re.compile(r"^\+(?!\+\+)(.*)$", re.M)
GOLD_FILE = re.compile(r"^--- a/(\S+)", re.M)
TOOLS = ("get_status", "read_file", "run_command", "edit_file", "submit_patch",
         "code_locator", "logic_analyst", "search_similar_code")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
THINK = re.compile(r"\((\d+) chars\)")
TESTN = re.compile(r"(\d+) failed(?:, (\d+) passed)?|(\d+) passed")


def norm_lines(patch_text):
    return {l.strip() for l in patch_text.splitlines() if l.strip()}


def analyze_run(bank, rep, tid):
    rdir = bank / f"r{rep}"
    row_path = rdir / "task_results.jsonl"
    if not row_path.exists():
        return None
    row = None
    for l in open(row_path, encoding="utf-8"):
        if l.strip():
            d = json.loads(l)
            if d["instance_id"] == tid:
                row = d
    if row is None:
        return None
    task = TASKS.get(tid, {})
    gold = task.get("patch", "") or ""
    gold_adds = [m.group(1).strip() for m in GOLD_ADD.finditer(gold) if m.group(1).strip()]
    gold_files = GOLD_FILE.findall(gold)
    patch_path = rdir / "patches" / f"{tid}.patch"
    patch = patch_path.read_text(encoding="utf-8", errors="replace") if patch_path.exists() else ""
    pnorm = norm_lines(patch)
    hits = sum(1 for a in gold_adds if a in pnorm or any(a in pl for pl in pnorm))
    frac = hits / len(gold_adds) if gold_adds else 0.0
    touched = any(f in patch for f in gold_files)

    resolved = bool(row.get("resolved"))
    if resolved:
        outcome = "SOLVED"
    elif not patch.strip():
        outcome = "NO_PATCH"
    elif frac >= 0.8:
        outcome = "NEAR_MISS"
    elif frac >= 0.4:
        outcome = "SAME_FILE_PARTIAL"
    elif touched:
        outcome = "RIGHT_FILE_WRONG"
    else:
        outcome = "WRONG_FILE"

    # trace: tool sequence
    first_edit = None; n_edits = n_sub = n_stat = n_disp = 0
    grep_before_edit = False; seen_tools = 0
    tr = rdir / "traces" / f"trace_{tid}.json"
    if tr.exists():
        try:
            tj = json.loads(tr.read_text(encoding="utf-8", errors="replace"))
            for s in tj.get("steps", []):
                for tc in (s.get("tool_calls") or []):
                    fn = tc.get("function_name")
                    if fn not in TOOLS:
                        continue
                    seen_tools += 1
                    args = tc.get("arguments") or ""
                    if isinstance(args, dict):
                        args = json.dumps(args)
                    if fn == "run_command" and "grep" in args and ("-A" in args or "-n" in args):
                        grep_before_edit = True
                    if fn == "edit_file":
                        n_edits += 1
                        if first_edit is None:
                            first_edit = seen_tools
                    elif fn == "submit_patch":
                        n_sub += 1
                    elif fn == "get_status":
                        n_stat += 1
                    elif fn in ("code_locator", "logic_analyst"):
                        n_disp += 1
        except Exception as e:
            print("  trace parse fail", tid, e)

    # log: thinking chars
    think = 0
    lg = rdir / "logs" / f"{tid}.log"
    if lg.exists():
        t = lg.read_text(encoding="utf-8", errors="replace")
        think = sum(int(m.group(1)) for m in THINK.finditer(t))

    # test log
    tp = r = None
    tl = rdir / "test_outputs" / f"{tid}.log"
    if tl.exists():
        tt = tl.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"(\d+) failed, (\d+) passed", tt)
        if m:
            tp, r = int(m.group(2)), int(m.group(1))
        else:
            m2 = re.search(r"(\d+) passed", tt)
            if m2:
                tp, r = int(m2.group(1)), 0

    return dict(bank=str(bank.name), rep=rep, task=tid, resolved=resolved, outcome=outcome,
                distance_frac=round(frac, 3), gold_touched=touched,
                anchor_compliance=bool(grep_before_edit) if first_edit else None,
                first_edit_call=first_edit, n_edits=n_edits, n_submits=n_sub,
                n_status=n_stat, n_dispatch=n_disp, thinking_chars=think,
                patch_sha12=(hashlib.sha1(patch.encode()).hexdigest()[:12] if patch else None),
                patch_chars=len(patch), test_passed=tp, test_failed=r,
                tool_calls=row.get("tool_calls"), duration=row.get("duration_seconds"))


def main():
    banks = [Path(a) for a in sys.argv[1:]] or [HERE / "m1_batch_multi" / "ca5"]
    for bank in banks:
        rows = []
        reps = sorted(int(p.name[1:]) for p in bank.glob("r*") if p.is_dir() and p.name[1:].isdigit())
        tasks = []
        for rep in reps:
            f = bank / f"r{rep}" / "task_results.jsonl"
            if f.exists():
                for l in open(f, encoding="utf-8"):
                    if l.strip():
                        tasks.append((rep, json.loads(l)["instance_id"]))
        for rep, tid in tasks:
            r = analyze_run(bank, rep, tid)
            if r:
                rows.append(r)
        if not rows:
            print("no rows:", bank)
            continue
        out = bank / "enriched.jsonl"
        out.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")

        print("\n===== %s (%d runs) =====" % (bank.name, len(rows)))
        oc = {}
        for r in rows:
            oc[r["outcome"]] = oc.get(r["outcome"], 0) + 1
        print("outcomes:", oc)
        # compliance 2x2 (runs that edited)
        comp = {}
        for r in rows:
            if r["anchor_compliance"] is not None:
                k = ("compliant" if r["anchor_compliance"] else "no-grep") + "/" + ("SOLVED" if r["resolved"] else "fail")
                comp[k] = comp.get(k, 0) + 1
        print("anchor-grep before edit x outcome:", comp)
        # near-miss depth among fails
        fails = [r for r in rows if not r["resolved"] and r["outcome"] in ("NEAR_MISS", "SAME_FILE_PARTIAL")]
        print("sub-80%%-but->=40%% gold-line misses (near-misses): %d" % len(fails))
        # mode clustering per task among failures with patches
        byt = {}
        for r in rows:
            if not r["resolved"] and r["patch_sha12"]:
                byt.setdefault(r["task"], []).append(r["patch_sha12"])
        clustered = {t: (len(s), len(set(s))) for t, s in byt.items() if len(s) >= 3}
        print("failing-patch mode clustering (total_shas vs unique) for tasks with >=3 failed patches:")
        for t, (tot, uniq) in sorted(clustered.items(), key=lambda x: x[1][1]):
            kind = "DETERMINISTIC-WRONG (1 mode)" if uniq == 1 else ("tight mode" if uniq <= tot // 2 else "chaos")
            print("   %-14s %d fails / %d unique patches -> %s" % (t, tot, uniq, kind))
        # thinking proxy
        import statistics as st
        tp = [r["thinking_chars"] for r in rows if r["resolved"]]
        tf = [r["thinking_chars"] for r in rows if not r["resolved"]]
        if tp and tf:
            print("thinking_chars: solved median=%d  failed median=%d" % (st.median(tp), st.median(tf)))


if __name__ == "__main__":
    main()
