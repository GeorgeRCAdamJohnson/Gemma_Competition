# Runs ON the GPU VM: paired-by-round arm minus control for any batch dir (default /content/ab2).
import json
import math
import statistics as st
from pathlib import Path

D = Path("/content/ab2")
P = json.loads((D / "progress.json").read_text())["passes"]
arms = sorted({p["arm"] for p in P})
by = {(p["round"], p["arm"]): p for p in P}
rounds = sorted({p["round"] for p in P if all((p["round"], a) in by for a in arms)})
print("arms", arms, "| complete rounds", rounds)
for a in arms:
    print(f"  {a:10s} solved per round {[by[(r, a)]['solved'] for r in rounds]}")
for a in arms:
    if a == "C_pack1":
        continue
    d = [by[(r, a)]["solved"] - by[(r, "C_pack1")]["solved"] for r in rounds]
    if len(d) > 1:
        sd = st.stdev(d)
        t = st.mean(d) / (sd / math.sqrt(len(d))) if sd else float("nan")
        print(f"  {a:10s} minus C: mean {st.mean(d):+.2f} t {t:+.2f}  {d}")
