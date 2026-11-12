"""Gold-patch analysis: WHY are E4B pack-1 fixes wrong? Kaggle batch 3 node0 (C_pack1), 12 passes x 26 landable tasks.
For each run with a non-empty patch, compare its NON-TEST source hunks to the gold patch:
  solved            resolved
  wrong_file        touches none of the gold's source files
  right_file_far    shares a file but no hunk within +-15 lines of a gold hunk
  right_region      at least one hunk overlaps / sits within 15 lines of a gold hunk (correct place, wrong logic)
  extra_files       (flag) touches source files the gold does not
Also per task: how many DISTINCT failing patches (normalized) the model produced: low = a systematic misreading.
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

TASKS = {json.loads(l)["instance_id"]: json.loads(l)
         for l in Path("colab_fasteval/_smoke_inputs/tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
IDS = json.loads(Path("colab_fasteval/ab_tasks.json").read_text())
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.M)


def is_test(p):
    b = p.rsplit("/", 1)[-1]
    return b.startswith("test_") or b.endswith("_test.py") or b == "conftest.py" or "/tests/" in "/" + p or "/test/" in "/" + p


def hunks(diff):
    """{file: [(start, end)]} over the OLD file, non-test source files only."""
    out, cur = defaultdict(list), None
    for ln in diff.splitlines():
        # the gold patches have no "diff --git" lines; key files on "+++ b/<path>" (present in both)
        if ln.startswith("+++ "):
            f = ln[4:].strip()
            f = f[2:] if f.startswith(("a/", "b/")) else f
            cur = f if f != "/dev/null" and not is_test(f) else None
        elif cur and ln.startswith("@@"):
            m = HUNK.match(ln)
            if m:
                s, n = int(m.group(1)), int(m.group(2) or 1)
                out[cur].append((s, s + max(n, 1)))
    return out


def norm(diff):
    keep = [re.sub(r"\s+", "", l[1:]) for l in diff.splitlines()
            if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    return "|".join(k for k in keep if k)


rows = []
R = Path("Outputs/kaggle_batch3/results/node0")
for tr in sorted(R.glob("run_*/task_results.jsonl")):
    for l in tr.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        if r["instance_id"] not in IDS:
            continue
        pp = tr.parent / "patches" / f"{r['instance_id']}.patch"
        patch = pp.read_text(encoding="utf-8", errors="replace") if pp.exists() else ""
        rows.append((r, patch))

cls = Counter()
per = defaultdict(lambda: Counter())
distinct = defaultdict(set)
extra = 0
for r, patch in rows:
    t = r["instance_id"]
    if r["resolved"]:
        c = "solved"
    elif not patch.strip():
        c = "no_patch"
    else:
        g, a = hunks(TASKS[t]["patch"]), hunks(patch)
        shared = set(g) & set(a)
        if not a:
            c = "test_or_doc_only"
        elif not shared:
            c = "wrong_file"
        else:
            near = any(gs - 15 <= ae and as_ <= ge + 15 for f in shared for gs, ge in g[f] for as_, ae in a[f])
            c = "right_region" if near else "right_file_far"
        if set(a) - set(g):
            extra += 1
        distinct[t].add(norm(patch))
    cls[c] += 1
    per[t][c] += 1

n = len(rows)
print(f"runs {n} (12 passes x {len(IDS)} tasks, C_pack1 on Kaggle node0)")
for c, k in cls.most_common():
    print(f"  {c:18s} {k:4d}  {100 * k / n:5.1f}%")
fails = n - cls["solved"]
print(f"  of {fails} failures: right_region {100 * cls['right_region'] / fails:.0f}% | right_file_far "
      f"{100 * cls['right_file_far'] / fails:.0f}% | wrong_file {100 * cls['wrong_file'] / fails:.0f}% | extra source files "
      f"touched in {extra} failing runs")
print("\nper task (solved / right_region / right_file_far / wrong_file / no_patch | distinct failing patches)")
for t in sorted(per, key=lambda t: -per[t]["solved"]):
    p = per[t]
    print(f"  {t:15s} {p['solved']:2d} / {p['right_region']:2d} / {p['right_file_far']:2d} / {p['wrong_file']:2d} / "
          f"{p['no_patch'] + p['test_or_doc_only']:2d} | {len(distinct[t]):2d}")
