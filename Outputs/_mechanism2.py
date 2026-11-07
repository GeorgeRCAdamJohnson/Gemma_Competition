"""(a) The 31 conversions: what did the rejected first attempt fail on? (b) Loss tasks: does the pack edit DIFFERENT
files than plain ca5 (localization) or the same files (edit mechanics)? (c) attempt-1 size: multi-file sprawl."""
import glob
import json
import re
from collections import Counter, defaultdict

A = re.compile(r"\x1b\[[0-9;]*m")
rows = json.load(open("Outputs/_mechanism_rows.json"))
conv = [x for x in rows if x["res"] and len(x["v"]) > 1]
print(f"(a) {len(conv)} conversions - first-attempt verdict: {dict(Counter(x['v'][0] for x in conv))}")
print(f"    by task: {dict(Counter(x['task'] for x in conv).most_common(8))}")


def files_edited(log):
    return [f for f in re.findall(r"(?:edit_file|write_file) \(([^),]+)", log)]


def per_task_files(pattern, task):
    c = Counter(); n = 0; fails = 0
    for f in glob.glob(pattern.format(task=task)):
        if re.search(r"pack\d_val[\\/]results[\\/]node0[\\/]run_1", f):
            continue
        t = A.sub("", open(f, encoding="utf-8", errors="replace").read())
        n += 1
        fails += t.count("old_string not") + t.count("No changes to apply")
        for x in set(files_edited(t)):
            c[x] += 1
    return n, c, fails


print("\n(b) loss tasks: files edited (share of runs) - pack vs control; edit_file 'not found' errors per run")
for task in ("rich_3063", "fastapi_14463", "fastapi_9425", "rich_3067"):
    n1, c1, f1 = per_task_files("Outputs/e4b_pack*_val/results/node*/run_*/logs/{task}.log", task)
    n0, c0, f0 = per_task_files("Outputs/e4b_cap_ab/results/node*/run_1/logs/{task}.log", task)
    fmt = lambda c, n: ", ".join(f"{k} {v/n:.0%}" for k, v in c.most_common(3))
    print(f"   {task}: PACK n={n1} [{fmt(c1, n1)}] edit-misses/run {f1/n1:.1f}")
    print(f"   {' '*len(task)}  CTRL n={n0} [{fmt(c0, n0)}] edit-misses/run {f0/n0:.1f}")

print("\n(c) attempt-1 sprawl: distinct files edited before the first gate verdict, by first verdict")
spread = defaultdict(list)
for f in glob.glob("Outputs/e4b_pack*_val/results/node*/run_*/logs/*.log"):
    if re.search(r"node0[\\/]run_1", f):
        continue
    t = A.sub("", open(f, encoding="utf-8", errors="replace").read())
    first = t.split('"stdout": "', 1)
    if len(first) < 2:
        continue
    head = first[1][:60]
    cls = "ACC" if head.startswith("ACCEPTED") else ("REJ:syntax" if "syntax" in head else
                                                     ("REJ:breaks_tests" if "existing test" in head else
                                                      ("REJ:no_change" if "no change" in head else
                                                       ("REJ:non_source" if "non-source" in head else "REJ:other"))))
    spread[cls].append(len(set(files_edited(first[0]))))
for k, v in sorted(spread.items()):
    v.sort()
    print(f"   first verdict {k:16s} n={len(v):4d}  median files {v[len(v)//2]}  share >=3 files {sum(x>=3 for x in v)/len(v):.0%}")
