"""Pool every E4B A/B run so far (26 landable tasks) and report, per arm vs the SAME-batch control:
mean diff per pass, consistency (sd, floor), erosion (tasks the control solves >= 60% that the arm solves >= 25 pts less)
and gains. Sources: Colab b1 (Outputs/colab_e4b_ab1), Colab b2 (colab_e4b_ab2), Colab vote (colab_e4b_ab4),
Kaggle b3 (Outputs/kaggle_batch3/results/node*/run_*/task_results.jsonl; node0 C, 1 H, 2 HT5, 3 HG4)."""
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

batches = {}
for tag, f in (("colab_b1", "Outputs/colab_e4b_ab1/progress.json"), ("colab_b2", "Outputs/colab_e4b_ab2/progress.json"),
               ("colab_vote", "Outputs/colab_e4b_ab4/progress.json")):
    P = json.loads(Path(f).read_text(encoding="utf-8-sig"))["passes"]
    batches[tag] = [(p["round"], p["arm"], {r["id"]: r["resolved"] for r in p["rows"]},
                     sum("ContextWindow" in r["err"] for r in p["rows"]), p["seconds"] / 60) for p in P]
NODE = {"node0": "C_pack1", "node1": "H_hygiene", "node2": "HT5", "node3": "HG4"}
kg = []
for tr in Path("Outputs/kaggle_batch3/results").glob("node*/run_*/task_results.jsonl"):
    rows = [json.loads(l) for l in tr.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(rows) < 24:   # incomplete pass
        continue
    k = int(tr.parent.name.split("_")[1])
    kg.append((k, NODE[tr.parent.parent.name], {r["instance_id"]: bool(r["resolved"]) for r in rows},
               sum("ContextWindow" in str(r.get("error")) for r in rows), sum(r.get("duration_seconds") or 0 for r in rows) / 60))
batches["kaggle_b3"] = kg

pool = defaultdict(list)          # arm -> list of per-pass diffs vs same-batch control
for tag, P in batches.items():
    by = {(r, a): (s, o, m) for r, a, s, o, m in P}
    arms = sorted({a for _, a, *_ in P})
    rounds = sorted({r for r, *_ in P if all((r, a) in by for a in arms)})
    print(f"\n=== {tag}: {len(rounds)} paired rounds, arms {arms}")
    ctl = {t: st.mean(by[(r, 'C_pack1')][0].get(t, False) for r in rounds) for t in by[(rounds[0], 'C_pack1')][0]}
    for a in arms:
        s = [sum(by[(r, a)][0].values()) for r in rounds]
        ov = st.mean(by[(r, a)][1] for r in rounds)
        line = f"  {a:10s} mean {st.mean(s):5.2f} sd {st.pstdev(s):4.2f} floor {min(s):2d} overflow/pass {ov:4.2f}"
        if a != "C_pack1":
            d = [s[i] - sum(by[(r, 'C_pack1')][0].values()) for i, r in enumerate(rounds)]
            pool[a] += d
            sd = st.stdev(d) if len(d) > 1 else 0
            t = st.mean(d) / (sd / math.sqrt(len(d))) if sd else float("nan")
            rate = {t_: st.mean(by[(r, a)][0].get(t_, False) for r in rounds) for t_ in ctl}
            ero = sorted((t_ for t_ in ctl if ctl[t_] >= 0.6 and rate[t_] <= ctl[t_] - 0.25), key=lambda t_: rate[t_] - ctl[t_])
            gain = sorted((t_ for t_ in ctl if rate[t_] >= ctl[t_] + 0.25), key=lambda t_: ctl[t_] - rate[t_])
            line += f" | vs C {st.mean(d):+.2f} t {t:+.2f}"
            line += "\n      erosions: " + (", ".join(f"{t_} {ctl[t_]:.0%}->{rate[t_]:.0%}" for t_ in ero) or "none")
            line += "\n      gains:    " + (", ".join(f"{t_} {ctl[t_]:.0%}->{rate[t_]:.0%}" for t_ in gain) or "none")
        print(line)

print("\n=== POOLED across batches (per-pass diff vs same-batch control)")
for a, d in sorted(pool.items(), key=lambda kv: -st.mean(kv[1])):
    sd = st.stdev(d) if len(d) > 1 else 0
    t = st.mean(d) / (sd / math.sqrt(len(d))) if sd else float("nan")
    print(f"  {a:10s} n={len(d):3d}  mean {st.mean(d):+.2f}  t {t:+.2f}")
