# LoRA prerequisite census: how many solved E4B trajectories with full ATIF traces do we hold locally?
import collections
import glob
import json
import os

tot = collections.Counter()
tasks = collections.defaultdict(int)
trace_ok = 0
steps = []
for f in glob.glob("Outputs/e4b_variance3/results/run_*/shard*/task_results.jsonl"):
    d = os.path.dirname(f)
    for line in open(f):
        r = json.loads(line)
        ok = r["resolved"]
        tot[ok] += 1
        tasks[r["instance_id"]] += ok
        tp = f"{d}/traces/trace_{r['instance_id']}.json"
        if ok and os.path.exists(tp):
            trace_ok += 1
            steps.append(len(json.load(open(tp))["steps"]))
print("resolved counter", dict(tot), "| solved with trace", trace_ok)
print("distinct solved", sum(1 for v in tasks.values() if v), "of", len(tasks))
print("solved-count histogram (times solved in 5 runs -> n tasks)", sorted(collections.Counter(tasks.values()).items()))
print("solved tasks by repo", collections.Counter(t.split("_")[0] for t, v in tasks.items() if v))
if steps:
    print("steps per solved trace: min", min(steps), "median", sorted(steps)[len(steps) // 2], "max", max(steps))
