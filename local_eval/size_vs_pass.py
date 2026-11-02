"""Gold-patch size vs raw-oracle outcome for the gate12 tasks.  CPU only.   python size_vs_pass.py"""
import json, re, collections, pathlib

HERE = pathlib.Path(__file__).resolve().parent
T = {}
for line in open(HERE.parent / "comp_files" / "tasks.jsonl", encoding="utf-8"):
    t = json.loads(line)
    T[t["instance_id"]] = t

t02 = {}
for line in open(HERE / "runs" / "raw_off_t02.raw.jsonl", encoding="utf-8"):
    r = json.loads(line)
    t02[r["task"]] = r
t10 = collections.defaultdict(list)
for line in open(HERE / "runs" / "raw_off_t10.raw.jsonl", encoding="utf-8"):
    r = json.loads(line)
    t10[r["task"]].append(bool(r.get("resolved")))

print(f"{'task':10}{'files':>6}{'hunks':>6}{'+/-':>8}  {'t0.2':>5}  {'t1.0':>5}  statement_head")
for tid in open(HERE / "gate12.txt", encoding="utf-8").read().split():
    t = T[tid]
    p = t["patch"]
    files = len(re.findall(r"^diff --git", p, re.M))
    hunks = len(re.findall(r"^@@", p, re.M))
    add = len(re.findall(r"^\+(?!\+\+)", p, re.M))
    dele = len(re.findall(r"^-(?!--)", p, re.M))
    ps = (t.get("problem_statement") or "").replace("\n", " ")[:70]
    r02 = str(t02.get(tid, {}).get("resolved"))[:1]
    print(f"{tid:10}{files:>6}{hunks:>6}{str(add) + '/' + str(dele):>8}  {r02:>5}  {sum(t10[tid])}/3    {ps}")
