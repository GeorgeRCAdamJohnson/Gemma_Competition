"""What makes a 14-15/26 pass different from a 10-12 pass? All E4B A/B passes so far (Colab b1, b2, vote; Kaggle b3).
1. Is pass-to-pass spread explained by independent per-task coin flips? (observed sd vs binomial sd from per-task rates)
2. Which tasks are solved in HIGH passes (>= 14) but not in typical ones: luck spread over many flaky tasks, or a few tasks?
3. Run-level features of high vs other passes: overflows, mean task duration, tool calls, pass minutes, arm, batch, position.
"""
import json
import math
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

passes = []   # dict(batch, arm, round, solved, rows={id: row})
for tag, f in (("colab_b1", "Outputs/colab_e4b_ab1/progress.json"), ("colab_b2", "Outputs/colab_e4b_ab2/progress.json"),
               ("colab_vote", "Outputs/colab_e4b_ab4/progress.json")):
    for p in json.loads(Path(f).read_text(encoding="utf-8-sig"))["passes"]:
        passes.append(dict(batch=tag, arm=p["arm"], round=p["round"], minutes=p["seconds"] / 60,
                           rows={r["id"]: dict(res=bool(r["resolved"]), dur=r.get("dur") or 0, calls=r.get("calls") or 0,
                                               ov="ContextWindow" in r["err"], patch=r.get("patch") or 0) for r in p["rows"]}))
NODE = {"node0": "C_pack1", "node1": "H_hygiene", "node2": "HT5", "node3": "HG4"}
for tr in Path("Outputs/kaggle_batch3/results").glob("node*/run_*/task_results.jsonl"):
    rows = [json.loads(l) for l in tr.read_text(encoding="utf-8").splitlines() if l.strip()]
    if len(rows) < 24:
        continue
    passes.append(dict(batch="kaggle_b3", arm=NODE[tr.parent.parent.name], round=int(tr.parent.name.split("_")[1]),
                       minutes=None,
                       rows={r["instance_id"]: dict(res=bool(r["resolved"]), dur=r.get("duration_seconds") or 0,
                                                    calls=r.get("tool_calls") or 0, ov="ContextWindow" in str(r.get("error")),
                                                    patch=r.get("agent_patch_size") or 0) for r in rows}))
for p in passes:
    p["solved"] = sum(r["res"] for r in p["rows"].values())
ids = sorted({t for p in passes for t in p["rows"]})
print(f"{len(passes)} passes | solved distribution {sorted(Counter(p['solved'] for p in passes).items())}")

# 1. independence check, per arm (rates from that arm's own passes)
print("\n1. spread vs independent coin flips (per arm, per batch)")
for (b, a) in sorted({(p["batch"], p["arm"]) for p in passes}):
    ps = [p for p in passes if p["batch"] == b and p["arm"] == a]
    if len(ps) < 6:
        continue
    rate = {t: st.mean(p["rows"][t]["res"] for p in ps if t in p["rows"]) for t in ids}
    bsd = math.sqrt(sum(r * (1 - r) for r in rate.values()))
    print(f"  {b:10s} {a:10s} n {len(ps):2d} mean {st.mean(p['solved'] for p in ps):5.2f} observed sd "
          f"{st.pstdev([p['solved'] for p in ps]):4.2f} | coin-flip sd {bsd:4.2f}")

# 2. which tasks drive high passes
hi = [p for p in passes if p["solved"] >= 14]
lo = [p for p in passes if p["solved"] <= 12]
print(f"\n2. HIGH passes (>=14): {len(hi)} -> {[(p['batch'], p['arm'], p['round'], p['solved']) for p in hi]}")
print(f"   typical/low passes (<=12): {len(lo)}")
rh = {t: st.mean(p["rows"][t]["res"] for p in hi if t in p["rows"]) for t in ids}
rl = {t: st.mean(p["rows"][t]["res"] for p in lo if t in p["rows"]) for t in ids}
print("   task            high   low   diff   (solve rate in high vs low passes)")
for t in sorted(ids, key=lambda t: rl[t] - rh[t]):
    if abs(rh[t] - rl[t]) >= 0.15:
        print(f"   {t:15s} {rh[t]:5.0%} {rl[t]:5.0%} {rh[t] - rl[t]:+5.0%}")
spread = sum(1 for t in ids if rh[t] - rl[t] >= 0.15)
print(f"   tasks >= +15 pts higher in high passes: {spread}; total excess solves per high pass "
      f"{sum(rh[t] - rl[t] for t in ids):+.2f}")

# 3. run-level features
def feat(ps):
    rows = [r for p in ps for r in p["rows"].values()]
    return dict(overflow_per_pass=st.mean(sum(r["ov"] for r in p["rows"].values()) for p in ps),
                mean_task_s=st.mean(r["dur"] for r in rows), median_calls=st.median(r["calls"] for r in rows),
                empty_patch_per_pass=st.mean(sum(r["patch"] == 0 for r in p["rows"].values()) for p in ps))
print("\n3. run-level features")
for name, ps in (("high (>=14)", hi), ("low (<=12)", lo)):
    print(f"   {name:12s} " + " | ".join(f"{k} {v:.2f}" for k, v in feat(ps).items()))
print("   high passes by arm:", dict(Counter(p["arm"] for p in hi)), "| by batch:", dict(Counter(p["batch"] for p in hi)))
print("   all passes by arm: ", dict(Counter(p["arm"] for p in passes)))
# overflow-adjusted: do high passes simply have fewer overflows on the flaky tasks?
fl = [t for t in ids if 0.15 < st.mean(p["rows"][t]["res"] for p in passes if t in p["rows"]) < 0.85]
print(f"   flaky tasks ({len(fl)}): overflow rate high {st.mean(p['rows'][t]['ov'] for p in hi for t in fl if t in p['rows']):.2%}"
      f" vs low {st.mean(p['rows'][t]['ov'] for p in lo for t in fl if t in p['rows']):.2%}")
