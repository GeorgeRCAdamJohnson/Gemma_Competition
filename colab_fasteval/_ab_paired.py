# Runs ON the GPU VM: paired (by round) arm-minus-control on solves/pass, minutes/pass, overflow; per-task deltas.
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

P = json.loads(Path("/content/ab/progress.json").read_text())["passes"]
by = {(p["round"], p["arm"]): p for p in P}
rounds = sorted({p["round"] for p in P if all((p["round"], a) in by for a in ("C_pack1", "H_hygiene", "L_lean", "R_reads"))})
print("complete rounds:", rounds)
ov = lambda p: sum("ContextWindow" in r["err"] for r in p["rows"])
for arm in ("H_hygiene", "L_lean", "R_reads"):
    d = [by[(r, arm)]["solved"] - by[(r, "C_pack1")]["solved"] for r in rounds]
    m, sd = st.mean(d), (st.stdev(d) if len(d) > 1 else 0)
    t = m / (sd / math.sqrt(len(d))) if sd else float("nan")
    dm = st.mean(by[(r, arm)]["seconds"] - by[(r, "C_pack1")]["seconds"] for r in rounds) / 60
    do = st.mean(ov(by[(r, arm)]) - ov(by[(r, "C_pack1")]) for r in rounds)
    print(f"{arm:10s} diff/round {d} | mean {m:+.2f} sd {sd:.2f} t {t:+.2f} | min/pass {dm:+.1f} | overflow/pass {do:+.2f}")
c = [by[(r, "C_pack1")]["solved"] for r in rounds]
print(f"control mean {st.mean(c):.2f} (Kaggle-expected 11.80) | overflow/pass {st.mean(ov(by[(r, 'C_pack1')]) for r in rounds):.2f}")
# per-task solve counts by arm over the complete rounds
k = defaultdict(lambda: defaultdict(int))
for r in rounds:
    for a in ("C_pack1", "H_hygiene", "L_lean", "R_reads"):
        for row in by[(r, a)]["rows"]:
            k[row["id"]][a] += row["resolved"]
print("\ntask            C  H  L  R   (solves out of %d)" % len(rounds))
for t in sorted(k, key=lambda t: -k[t]["C_pack1"]):
    v = k[t]
    if len({v["C_pack1"], v["H_hygiene"], v["L_lean"], v["R_reads"]}) > 1:
        print(f"{t:15s} {v['C_pack1']:2d} {v['H_hygiene']:2d} {v['L_lean']:2d} {v['R_reads']:2d}")
