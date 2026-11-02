"""CPU-only probe: max / p95 tool-result length per tool across all Kaggle ATIF traces (calibrates the local result cap)."""
import json, glob, statistics
from collections import defaultdict

lens = defaultdict(list)
for p in glob.glob(r"..\**\trace_rich_*.json", recursive=True):
    try:
        t = json.loads(open(p, encoding="utf-8").read())
    except Exception:
        continue
    for s in t.get("steps", []):
        obs = s.get("observation")
        if not obs:
            continue
        tn = (obs.get("extra") or {}).get("tool_name")
        c = obs.get("content")
        if tn and isinstance(c, str):
            lens[tn].append(len(c))
for tn, v in sorted(lens.items()):
    v.sort()
    over = sum(1 for n in v if n > 3000)
    print(f"{tn:22s} n={len(v):5d} max={v[-1]:6d} p95={v[int(len(v)*0.95)]:6d} median={int(statistics.median(v)):6d} share>3000={100*over/len(v):4.1f}%")
