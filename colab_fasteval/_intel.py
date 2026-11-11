# Runs ON the vote VM (Drive mounted): paired results for the local V_vote batch and batch 2 (from Drive).
import json
import math
import statistics as st
from pathlib import Path


def paired(P, label):
    arms = sorted({p["arm"] for p in P})
    by = {(p["round"], p["arm"]): p for p in P}
    rounds = sorted({p["round"] for p in P if all((p["round"], a) in by for a in arms)})
    print(f"== {label}: arms {arms} | complete rounds {len(rounds)}")
    for a in arms:
        s = [by[(r, a)]["solved"] for r in rounds]
        m = [by[(r, a)]["seconds"] / 60 for r in rounds]
        ov = [sum("ContextWindow" in x["err"] for x in by[(r, a)]["rows"]) for r in rounds]
        if s:
            print(f"  {a:10s} mean {st.mean(s):5.2f} sd {st.pstdev(s):4.2f} min/pass {st.mean(m):5.1f} overflow/pass {st.mean(ov):4.2f} {s}")
    for a in arms:
        if a == "C_pack1" or len(rounds) < 2:
            continue
        d = [by[(r, a)]["solved"] - by[(r, "C_pack1")]["solved"] for r in rounds]
        sd = st.stdev(d)
        t = st.mean(d) / (sd / math.sqrt(len(d))) if sd else float("nan")
        print(f"  {a:10s} - C: {st.mean(d):+.2f} t {t:+.2f}")
    # per-task: control vs each arm, solves out of len(rounds)
    k = {}
    for r in rounds:
        for a in arms:
            for x in by[(r, a)]["rows"]:
                k.setdefault(x["id"], {}).setdefault(a, 0)
                k[x["id"]][a] += x["resolved"]
    print("  task            " + " ".join(f"{a[:6]:>6s}" for a in arms))
    for t in sorted(k, key=lambda t: -k[t].get("C_pack1", 0)):
        v = [k[t].get(a, 0) for a in arms]
        if len(set(v)) > 1:
            print(f"  {t:15s} " + " ".join(f"{x:6d}" for x in v))


for label, p in (("V_vote (local)", Path("/content/ab4/progress.json")),
                 ("batch 2 (Drive)", Path("/content/drive/MyDrive/gemma_fasteval/ab_runs/e4b_ab2_20261111/progress.json"))):
    if p.exists():
        paired(json.loads(p.read_text())["passes"], label)
    else:
        print("missing", p)
