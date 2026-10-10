"""Characterize all 129 tasks from tasks.jsonl: repo, gold-patch shape, winnability class.
Tests the hypothesis that rich is a high-ceiling repo being hidden by an unrepresentative 6-task sample.
Uses the gold `patch` (what the fix touches) and `test_patch` (what's asserted) — both in tasks.jsonl."""
import json, re
from collections import defaultdict

TASKS = "Gemma/comp_files/tasks.jsonl"
rows = [json.loads(l) for l in open(TASKS, encoding="utf-8") if l.strip()]

def patch_files(patch):
    """Return (files_touched, adds, dels, creates_new_file)."""
    files = re.findall(r'^\+\+\+ b/(.+)$', patch, re.M)
    adds = len(re.findall(r'^\+(?!\+\+)', patch, re.M))
    dels = len(re.findall(r'^-(?!--)', patch, re.M))
    creates = bool(re.search(r'^--- a/.*\n\+\+\+ b/.*\n@@ -0,0', patch, re.M)) or '\n@@ -0,0 +1,' in patch
    return files, adds, dels, creates

def classify(rec):
    """Winnability class from the GOLD patch shape (not the problem text)."""
    files, adds, dels, creates = patch_files(rec["patch"])
    nonfiles = [f for f in files if not f.startswith("tests/") and "test_" not in f]
    nfiles = len(set(nonfiles))
    if creates and dels <= 1:
        return "NEW_FILE_FEATURE", nfiles, adds   # creates a file from scratch (feature add)
    if nfiles == 0:
        return "DOCS_OR_TEST_ONLY", nfiles, adds
    if nfiles == 1 and adds <= 25:
        return "SMALL_SINGLE_FILE", nfiles, adds   # the "winnable bug" class
    if nfiles == 1:
        return "LARGE_SINGLE_FILE", nfiles, adds
    return "MULTI_FILE", nfiles, adds

by_repo = defaultdict(lambda: defaultdict(int))
by_repo_total = defaultdict(int)
cls_examples = defaultdict(list)
for r in rows:
    repo = r["repo"].split("/")[-1]
    cls, nf, adds = classify(r)
    by_repo[repo][cls] += 1
    by_repo_total[repo] += 1
    cls_examples[(repo, cls)].append((r["instance_id"], nf, adds))

CLASSES = ["SMALL_SINGLE_FILE", "LARGE_SINGLE_FILE", "MULTI_FILE", "NEW_FILE_FEATURE", "DOCS_OR_TEST_ONLY"]
print(f"TOTAL TASKS: {len(rows)}\n")
print(f"{'repo':10s} {'total':>5s} " + " ".join(f"{c[:12]:>13s}" for c in CLASSES))
for repo in sorted(by_repo_total, key=lambda r: -by_repo_total[r]):
    line = f"{repo:10s} {by_repo_total[repo]:>5d} "
    line += " ".join(f"{by_repo[repo][c]:>13d}" for c in CLASSES)
    print(line)

print("\n=== RICH breakdown (the hypothesis: mostly SMALL_SINGLE_FILE = winnable) ===")
rich_small = cls_examples[("rich", "SMALL_SINGLE_FILE")]
print(f"rich SMALL_SINGLE_FILE: {len(rich_small)} tasks")
for iid, nf, adds in rich_small[:20]:
    print(f"   {iid:14s} files={nf} adds={adds}")

print("\n=== our cursed 6-sample classification ===")
sample = ["rich_4070","rich_4077","rich_4079","rich_4076","fastapi_15661","fastapi_15588"]
by_id = {r["instance_id"]: r for r in rows}
for iid in sample:
    if iid in by_id:
        cls, nf, adds = classify(by_id[iid])
        print(f"   {iid:14s} {cls:18s} files={nf} adds={adds}")
    else:
        print(f"   {iid:14s} NOT FOUND")
