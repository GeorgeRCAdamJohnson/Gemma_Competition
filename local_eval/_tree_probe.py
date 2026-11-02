"""CPU-only: replicate the Kaggle harness 'Workspace Layout' tree from git at a task's base commit and diff it
against the real sample captured in runs/kaggle_first_user_4079.txt."""
import json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE / "repos" / "rich_v"
TASKS = HERE.parent / "comp_files" / "tasks.jsonl"

PRUNE = {"docs", "docs_src", "tests", "examples", "benchmarks"}


def load(tid):
    for l in open(TASKS, encoding="utf-8"):
        t = json.loads(l)
        if t["instance_id"] == tid:
            return t


def ls_tree(commit):
    r = subprocess.run(["git", "ls-tree", "-r", "--name-only", commit], cwd=REPO, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return [l for l in r.stdout.splitlines() if l]


def sample_entries():
    t = (HERE / "runs" / "kaggle_first_user_4079.txt").read_text(encoding="utf-8").splitlines()
    fences = [i for i, l in enumerate(t) if l == "```"]
    return t[fences[0] + 1: fences[1]]


def key(p):
    # glibc-like first-level collation: case-insensitive, punctuation ignored; ties by raw string
    parts = p.split("/")
    return [(re.sub(r"[^0-9a-z]", "", x.lower()), x) for x in parts]


def build(files, maxdepth=3, cap=200, excl_ext=()):
    entries = set()
    for f in files:
        parts = f.split("/")
        if any(x.startswith(".") for x in parts):
            continue
        if any(x == "__pycache__" or x.endswith(".pyc") or x.endswith(".egg-info") for x in parts):
            continue
        if f.endswith(tuple(excl_ext)):
            continue
        # a path below a pruned dir at depth>=2 is dropped
        if len(parts) >= 2 and parts[0] in PRUNE:
            entries.add("./" + parts[0])
            continue
        for d in range(1, min(len(parts), maxdepth) + 1):
            entries.add("./" + "/".join(parts[:d]))
    ordered = sorted(entries, key=lambda e: (e.count("/"), key(e)))  # BFS order
    picked = ordered[:cap]
    return sorted(picked, key=key)


if __name__ == "__main__":
    tid = sys.argv[1] if len(sys.argv) > 1 else "rich_4079"
    t = load(tid)
    files = ls_tree(t["base_commit"])
    print("tracked files:", len(files))
    for top in ("imgs", "assets", "questions", "tools"):
        sub = [f for f in files if f.split("/")[0] == top]
        print(f"  {top}: {len(sub)} files, e.g. {sub[:4]}")
    mine = build(files)
    theirs = sample_entries()
    print("mine:", len(mine), "theirs:", len(theirs))
    sm, st = set(mine), set(theirs)
    print("only in mine  :", sorted(sm - st)[:40])
    print("only in theirs:", sorted(st - sm)[:40])
    print("order identical:", [e for e in mine if e in st] == [e for e in theirs if e in sm])
    if "--show" in sys.argv:
        print("\n".join(mine))
