"""Task 1 (spec gemma-lora-colab-training): build EDIT-DISCIPLINE trajectories.

Teaches the two MEASURED weights-level gaps (v18-v19v3):
  R2 byte-faithful edit anchors: the edit's old_string is a SHORT EXACT span copied verbatim from the
     file as it exists at base_commit (NOT paraphrased) -> applying new_string reproduces the gold post-image.
  R3 stop-after-submit, no repeated-call tails: trajectory ends at submit_patch, terse (<= ~6 actions).

Each trajectory (messages format, consumed by train_lora.py encode_example which masks loss to assistant turns):
  system = v19 frozen prompt   (train the adapter to act UNDER the exact shipped prompt)
  user   = harness-style task prompt (repo + problem_statement)   [build_agent_prompt shape]
  assistant: read_file(file, start,end)  -> tool: the REAL slice  -> edit_file(file, old=VERBATIM, new=GOLD)
             -> submit_patch -> END

Anti-leak / honesty (rule 8, R10): we ONLY emit trajectories whose old_string is a verbatim substring of the
real file at base_commit AND whose (old->new) application equals the gold post-image. Any task whose patch we
cannot ground to real bytes is DROPPED and counted, never fabricated.

Source: comp_files/tasks.jsonl (gold patch + problem_statement) + local_eval/repos/<repo> checked out at base_commit.
Output: train/data/edit_discipline_rich.jsonl  (+ a build report to stdout).

NOTE: this script reads the system prompt from the v19 submission so the training prompt == the ship prompt.
"""
import json, os, re, subprocess, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                      # Gemma/
TASKS = os.path.join(ROOT, "comp_files", "tasks.jsonl")
REPOS = os.path.join(ROOT, "local_eval", "repos") # <repo-name> clones
V19_SRC = os.path.join(ROOT, "submit_v19", "notebook_src.py")
OUT = os.path.join(HERE, "data", "edit_discipline_rich.jsonl")

# -- extract the v19 system prompt verbatim (so training prompt == ship prompt) --
def load_v19_system():
    src = open(V19_SRC, encoding="utf-8").read()
    m = re.search(r"'system\.md'\)\.write_text\(\"\"\"(.*?)\"\"\",\s*encoding", src, re.S)
    if not m:
        m = re.search(r"'system\.md'\)\.write_text\('''(.*?)''',\s*encoding", src, re.S)
    assert m, "could not extract v19 system.md prompt"
    return m.group(1)

# -- git helpers: read a file as it exists at base_commit (no mutation of the clone's HEAD) --
def repo_dir(repo):  # "Textualize/rich" -> local_eval/repos/rich
    return os.path.join(REPOS, repo.split("/")[-1])

def file_at_commit(repo, commit, path):
    d = repo_dir(repo)
    try:
        # decode bytes as UTF-8 explicitly (Windows subprocess defaults to cp1252 and corrupts source files)
        res = subprocess.run(["git", "-C", d, "show", f"{commit}:{path}"],
                             capture_output=True, check=True)
        return res.stdout.decode("utf-8", errors="replace")
    except subprocess.CalledProcessError:
        return None

# -- unified-diff parsing: return list of (path, pre_block, post_block) per hunk --
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.M)

def parse_patch(patch):
    """Yield (path, old_lines:list[str], new_lines:list[str]) per file (concatenated across its hunks)."""
    files = {}
    cur = None
    for line in patch.splitlines():
        if line.startswith("--- a/"):
            cur = None
        elif line.startswith("+++ b/"):
            cur = line[6:].strip()
            files.setdefault(cur, {"old": [], "new": []})
        elif cur is not None and line.startswith("@@"):
            continue
        elif cur is not None and line and line[0] in " -+":
            tag, text = line[0], line[1:]
            if tag == " ":
                files[cur]["old"].append(text); files[cur]["new"].append(text)
            elif tag == "-":
                files[cur]["old"].append(text)
            elif tag == "+":
                files[cur]["new"].append(text)
    for p, d in files.items():
        yield p, d["old"], d["new"]

def shortest_unique_anchor(file_text, old_block_lines):
    """Return the SHORTEST contiguous slice of old_block that is a UNIQUE verbatim substring of file_text.
    Prefer a single changed line; grow until unique. Returns (old_str, None) or (None, reason)."""
    block = "\n".join(old_block_lines)
    if block and block in file_text and file_text.count(block) == 1:
        # try to shrink to a minimal unique window around the change
        lines = old_block_lines
        n = len(lines)
        best = block
        for size in range(1, n + 1):
            for start in range(0, n - size + 1):
                cand = "\n".join(lines[start:start + size])
                if cand.strip() and cand in file_text and file_text.count(cand) == 1:
                    return cand, None
        return best, None
    if block and block in file_text:
        return None, "anchor_not_unique"
    return None, "anchor_not_in_file"

def build_user_prompt(repo, problem):
    # mirrors build_agent_prompt header shape (HARNESS_README 5.2)
    return (f"You are evaluating a software engineering task for repository {repo}.\n\n"
            f"Problem Statement:\n{problem}")

def gemma4_call(name, args):
    inner = ",".join(f"{k}:{json.dumps(v)}" for k, v in args.items())
    return f"call:{name}{{{inner}}}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repos", default="rich", help="comma list of repo-name filters (default rich-only, D2)")
    ap.add_argument("--max-files", type=int, default=1, help="only single-file-fix tasks by default (terse, R4)")
    args = ap.parse_args()
    repo_filter = set(args.repos.split(","))

    system = load_v19_system()
    rows = [json.loads(l) for l in open(TASKS, encoding="utf-8") if l.strip()]
    sel = [r for r in rows if any(f in r.get("repo", "").split("/")[-1] for f in repo_filter)]
    print(f"[data] {len(sel)} tasks match repos={sorted(repo_filter)} (of {len(rows)} total)")

    out, drops = [], {"multi_file": 0, "no_repo": 0, "anchor_not_in_file": 0, "anchor_not_unique": 0,
                      "apply_mismatch": 0, "empty_patch": 0}
    for r in sel:
        iid, repo, commit, patch = r["instance_id"], r["repo"], r["base_commit"], r.get("patch", "")
        if not patch.strip():
            drops["empty_patch"] += 1; continue
        perfile = list(parse_patch(patch))
        # keep only source edits (skip test files — the harness resets them)
        perfile = [(p, o, n) for (p, o, n) in perfile
                   if not re.search(r"(^|/)(test_|tests/|conftest\.py|.*_test\.py)", p)]
        if len(perfile) != args.max_files:
            drops["multi_file"] += 1; continue
        path, old_lines, new_lines = perfile[0]
        ftext = file_at_commit(repo, commit, path)
        if ftext is None:
            drops["no_repo"] += 1; continue
        old_str, reason = shortest_unique_anchor(ftext, old_lines)
        if old_str is None:
            drops[reason] += 1; continue
        # new_string = old_str with the gold change applied: reconstruct by replacing the old block region.
        old_block = "\n".join(old_lines); new_block = "\n".join(new_lines)
        # map the minimal old_str back: new_str is old_str with the old_block->new_block delta.
        # Simplest faithful approach: if old_str == old_block use new_block; else apply block delta to the file
        # and re-derive the minimal replacement. For the common single-hunk case old_block is small -> use it.
        if old_str == old_block:
            new_str = new_block
        else:
            # old_str is a sub-slice; apply full block replacement to the file, then the edit is old_block->new_block
            old_str, new_str = old_block, new_block
        # VERIFY (R2): old_str must be a unique verbatim substring, and applying it must yield the gold post-image.
        if old_str not in ftext or ftext.count(old_str) != 1:
            drops["anchor_not_unique"] += 1; continue
        post = ftext.replace(old_str, new_str, 1)
        gold_post = ftext.replace(old_block, new_block, 1) if old_block in ftext else None
        if gold_post is None or post != gold_post:
            drops["apply_mismatch"] += 1; continue

        # locate line range of old_str for the read_file call (1-indexed inclusive)
        pre = ftext[:ftext.index(old_str)]
        start_line = pre.count("\n") + 1
        end_line = start_line + old_str.count("\n")
        rd_start = max(1, start_line - 3); rd_end = end_line + 3
        slice_lines = ftext.splitlines()[rd_start - 1: rd_end]
        slice_text = "\n".join(slice_lines)

        assistant_read = gemma4_call("read_file", {"filepath": path, "start_line": rd_start, "end_line": rd_end})
        tool_obs = json.dumps({"status": "ok", "filepath": path, "content": slice_text,
                               "start_line": rd_start, "end_line": rd_end})
        assistant_edit = gemma4_call("edit_file", {"filepath": path, "old_string": old_str, "new_string": new_str})
        assistant_submit = gemma4_call("submit_patch", {})

        msgs = [
            {"role": "system", "content": system},
            {"role": "user", "content": build_user_prompt(repo, r["problem_statement"][:2000])},
            {"role": "assistant", "content": f"TARGET: {path} — apply the fix.\n{assistant_read}"},
            {"role": "tool", "content": tool_obs},
            {"role": "assistant", "content": f"The anchor is confirmed verbatim. Apply the edit.\n{assistant_edit}"},
            {"role": "tool", "content": json.dumps({"status": "ok", "occurrences": 1, "strategy": "exact"})},
            {"role": "assistant", "content": f"Edit applied. Submit.\n{assistant_submit}"},
        ]
        out.append({"messages": msgs, "instance_id": iid, "repo": repo,
                    "anchor_lines": old_str.count("\n") + 1})

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r) + "\n")
    print(f"[write] {OUT}: {len(out)} edit-discipline trajectories")
    print(f"[drops] {drops}")
    if out:
        import statistics
        al = [r["anchor_lines"] for r in out]
        print(f"[anchor] lines: median={statistics.median(al)} min={min(al)} max={max(al)}")
        ex = out[0]
        print("--- sample", ex["instance_id"], "---")
        for m in ex["messages"]:
            print(f"  [{m['role']}] {m['content'][:120].replace(chr(10),' ')}")

if __name__ == "__main__":
    main()
