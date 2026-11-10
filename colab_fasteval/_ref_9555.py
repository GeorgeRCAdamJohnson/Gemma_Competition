"""How did fastapi_9555 fail in the 20 Kaggle pack-1 score passes? (overflow vs other, durations)"""
import json
from collections import Counter

d = json.load(open("Outputs/e4b_pack1_val/variance_ab.json", encoding="utf-8"))
rows = [r for p in d["passes"] if p.get("kind") == "score39" for r in p["rows"] if r["id"] == "fastapi_9555"]
kind = lambda r: "solved" if r["resolved"] else ("overflow" if "ContextWindow" in r.get("err", "") else
                                                  ("timeout" if "timeout" in r.get("err", "") else "failed"))
print(Counter(kind(r) for r in rows))
for k in ("solved", "overflow", "failed", "timeout"):
    ds = sorted(r["dur"] for r in rows if kind(r) == k and r.get("dur"))
    if ds:
        print(f"  {k:8s} n={len(ds):2d} dur min/median/max = {ds[0]:.0f}/{ds[len(ds)//2]:.0f}/{ds[-1]:.0f} s"
              f" | calls {sorted(r['calls'] for r in rows if kind(r) == k)}")
