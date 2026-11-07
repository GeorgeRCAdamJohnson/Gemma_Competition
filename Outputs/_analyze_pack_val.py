"""Final read of e4b-pack1-val / e4b-pack2-val: score39 passes vs control and vs each other; runtime90 sums ->
full-129 task-seconds estimate vs the 31B references (28/8 ~12.3 h fits, 50/20 ~14.5 h timed out); overflow rates."""
import json
import statistics as st
from math import sqrt
from pathlib import Path

O = Path("Outputs")
ids39 = set(json.load(open(O / "_solvable85.json"))["ever"])
ctrl = [sum(1 for r in p["rows"] if r["resolved"] and r["id"] in ids39)
        for p in json.load(open(O / "e4b_cap_ab" / "variance_ab.json"))["passes"] if p["complete"]]
prior_f = [sum(1 for r in p["rows"] if r["resolved"] and r["id"] in ids39)
           for p in json.load(open(O / "e4b_repro_ab" / "variance_ab.json"))["passes"]
           if p["complete"] and p["arm"] == "ARM_F_retry_fresh"]


def welch(a, b):
    se = sqrt(st.variance(a) / len(a) + st.variance(b) / len(b))
    return (st.mean(a) - st.mean(b)) / se


data = {}
for name, d in (("pack1", "e4b_pack1_val"), ("pack2", "e4b_pack2_val")):
    P = json.load(open(O / d / "variance_ab.json"))["passes"]
    score = [p for p in P if p["complete"] and p.get("kind") == "score39"]
    rt = [p for p in P if p.get("kind") == "runtime90"]
    ks = [p["k"] for p in score]
    rows39 = [r for p in score for r in p["rows"]]
    d39 = [r["dur"] for r in rows39 if r.get("dur")]
    ov39 = sum("ContextWindow" in (r.get("err") or "") for r in rows39)
    data[name] = ks
    print(f"== {name}: {len(score)} score39 passes {ks}")
    print(f"   mean {st.mean(ks):.2f} sd {st.pstdev(ks):.2f} | vs control 9.82: t = {welch(ks, ctrl):.2f}")
    print(f"   39-task rows: mean dur {st.mean(d39):.0f}s, overflow {ov39}/{len(rows39)} ({100*ov39/len(rows39):.1f}%)")
    for p in rt:
        d = [r["dur"] for r in p["rows"] if r.get("dur")]
        ov = sum("ContextWindow" in (r.get("err") or "") for r in p["rows"])
        est = sum(d) + 39 * st.mean(d39)
        print(f"   runtime90: complete={p['complete']} n={p['n']} solved {p['k']} wall {p['seconds']/60:.1f} min | "
              f"sum {sum(d)/3600:.2f} h, mean {st.mean(d):.0f}s, max {max(d):.0f}s, overflow {ov}/{p['n']}")
        print(f"   FULL-129 task-seconds estimate = runtime90 sum + 39 x mean39 = {est/3600:.2f} h "
              f"(31B 28/8 ~12.3 h fits | 31B 50/20 ~14.5 h timed out)")
print(f"\npack2 - pack1: {st.mean(data['pack2']) - st.mean(data['pack1']):+.2f}, t = {welch(data['pack2'], data['pack1']):.2f}")
pooled1 = data["pack1"] + prior_f
print(f"pack1 pooled with prior 16 F passes: n={len(pooled1)} mean {st.mean(pooled1):.2f}; "
      f"pack2 vs pooled pack1 t = {welch(data['pack2'], pooled1):.2f}")
