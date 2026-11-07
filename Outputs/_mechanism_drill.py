"""Drill-down: gold files for the tasks the gate rejects as 'non_source_only', and trace excerpts for the biggest
win (fastapi_14077) and the biggest loss (rich_3063): what attempt 1 did, what the gate said, what attempt 2 did."""
import glob
import json
import re
from collections import Counter

A = re.compile(r"\x1b\[[0-9;]*m")
TASKS = {json.loads(l)["instance_id"]: json.loads(l) for l in open("kaggle_pkg/taskdefs/tasks.jsonl", encoding="utf-8") if l.strip()}
t0 = TASKS["fastapi_14492"]
print("task keys:", sorted(t0.keys()))
pk = next(k for k in t0 if "patch" in k and "test" not in k)
for t in ("fastapi_14492", "rich_3043", "fastapi_14077"):
    p = TASKS[t][pk]
    files = re.findall(r"^\+\+\+ b/(\S+)", p, re.M) or re.findall(r"^diff --git a/(\S+)", p, re.M)
    print(f"{t}: gold files {files} | statement: {TASKS[t]['problem_statement'][:140]!r}")


def show(task, n=2, pat=r"(edit_file|write_file|stdout\": \"|Agent finished|syntax|old_string)"):
    shown = 0
    for f in sorted(glob.glob(f"Outputs/e4b_pack*_val/results/node*/run_*/logs/{task}.log")):
        if re.search(r"node0[\\/]run_1", f):
            continue
        t = A.sub("", open(f, encoding="utf-8", errors="replace").read())
        if t.count("stdout") < 2:
            continue
        print(f"\n--- {task} {f.split('results')[1]}")
        for line in t.splitlines():
            if re.search(pat, line):
                print("   ", line.strip()[:190])
        shown += 1
        if shown >= n:
            break


show("fastapi_14077", 1)
show("rich_3063", 1)
# control on rich_3063: what did plain ca5 do when it solved?
for f in sorted(glob.glob("Outputs/e4b_cap_ab/results/node*/run_1/logs/rich_3063.log")):
    t = A.sub("", open(f, encoding="utf-8", errors="replace").read())
    rf = f.replace("logs", "").replace("rich_3063.log", "task_results.jsonl").replace("\\\\", "\\")
    print(f"\n--- CONTROL rich_3063 {f.split('results')[1]}")
    for line in t.splitlines():
        if re.search(r"(edit_file|write_file|submit_patch|❌)", line):
            print("   ", line.strip()[:190])
