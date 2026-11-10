"""Landable task set for the E4B A/B: every task with >= 1 solve in pack 1's 20 Kaggle score passes, minus
fastapi_14851 (passes with an EMPTY patch: a free solve that measures nothing). Writes colab_fasteval/ab_tasks.json."""
import json
from collections import defaultdict
from pathlib import Path

d = json.load(open("Outputs/e4b_pack1_val/variance_ab.json", encoding="utf-8"))
k, n = defaultdict(int), defaultdict(int)
for p in d["passes"]:
    if p.get("kind") != "score39":
        continue
    for r in p["rows"]:
        n[r["id"]] += 1
        k[r["id"]] += bool(r["resolved"])
ids = sorted((t for t in n if k[t] > 0 and t != "fastapi_14851"), key=lambda t: (-k[t] / n[t], t))
exp = sum(k[t] / n[t] for t in ids)
print(len(ids), "tasks | expected pack-1 solves per pass on this set: %.2f" % exp)
for t in ids:
    print(f"  {t:15s} {k[t]:2d}/{n[t]}")
Path("colab_fasteval/ab_tasks.json").write_text(json.dumps(ids))
