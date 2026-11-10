"""Per-task pack-1 E4B results from the Kaggle validation (variance_ab.json): solve rate + mean duration, to pick a
6-task smoke set (mix of reliable solves and fast tasks)."""
import json
import statistics as st
from collections import defaultdict

d = json.load(open("Outputs/e4b_pack1_val/variance_ab.json", encoding="utf-8"))
passes = d["passes"] if isinstance(d, dict) and "passes" in d else d
agg = defaultdict(lambda: {"n": 0, "k": 0, "dur": []})
for p in passes:
    if p.get("kind") != "score39" or not p.get("complete", True):
        continue
    for r in p["rows"]:
        a = agg[r["id"]]
        a["n"] += 1
        a["k"] += bool(r["resolved"])
        if r.get("dur"):
            a["dur"].append(r["dur"])
rows = sorted(agg.items(), key=lambda kv: (-kv[1]["k"] / kv[1]["n"], st.mean(kv[1]["dur"] or [0])))
print(f"{'task':16s} {'k/n':>6s} {'rate':>5s} {'mean s':>7s}")
for t, a in rows:
    print(f"{t:16s} {a['k']:>2d}/{a['n']:<3d} {a['k']/a['n']:5.2f} {st.mean(a['dur'] or [0]):7.0f}")
