"""What makes a 14-15/26 E4B pass? Test RUN CONDITIONS, not luck: GPU speed, warm-up / cache build-up over rounds, cold start
after vLLM boot, position in round, platform. Every E4B pass on the 26-task landable set (Colab b1/b2/vote, Kaggle b3/b5a/b5b).

Outcome = pass solves minus that arm's mean in that batch (removes arm + batch effects).
Speed = pass median duration of ANCHOR tasks (solved in >= 90% of all passes): their duration measures generation speed
without being driven by whether hard tasks were solved (a solved hard task ends early and would fake "fast = good").
"""
import json
import math
import statistics as st
from collections import defaultdict
from pathlib import Path

passes = []
for tag, f in (("colab_b1", "Outputs/colab_e4b_ab1/progress.json"), ("colab_b2", "Outputs/colab_e4b_ab2/progress.json"),
               ("colab_vote", "Outputs/colab_e4b_ab4/progress.json")):
    P = json.loads(Path(f).read_text(encoding="utf-8-sig"))["passes"]
    for i, p in enumerate(P):  # list order = execution order on that one server
        passes.append(dict(batch=tag, plat="colab", arm=p["arm"], round=p["round"], seq=i, minutes=p["seconds"] / 60,
                           rows={r["id"]: (bool(r["resolved"]), r.get("dur") or 0, "ContextWindow" in r["err"])
                                 for r in p["rows"]}))
for tag in ("kaggle_batch3", "kaggle_batch5a", "kaggle_batch5b"):
    f = Path(f"Outputs/{tag}/variance_ab.json")
    if not f.exists():
        continue
    for p in json.loads(f.read_text(encoding="utf-8-sig"))["passes"]:
        if not p.get("complete", True) or p["n"] < 24:
            continue
        passes.append(dict(batch=f"{tag}:n{p['node']}", plat="kaggle", arm=p["arm"], round=p["run"], seq=p["run"] - 1,
                           minutes=p["seconds"] / 60,
                           rows={r["id"]: (bool(r["resolved"]), r.get("dur") or 0, "ContextWindow" in r["err"])
                                 for r in p["rows"]}))
passes = [p for p in passes if len(p["rows"]) >= 24]
for p in passes:
    p["solved"] = sum(v[0] for v in p["rows"].values())
ids = sorted({t for p in passes for t in p["rows"]})
rate = {t: st.mean(p["rows"][t][0] for p in passes if t in p["rows"]) for t in ids}
anchors = [t for t in ids if rate[t] >= 0.9]
for p in passes:
    d = [p["rows"][t][1] for t in anchors if t in p["rows"]]
    p["speed_s"] = st.median(d) if d else float("nan")
    p["overflow"] = sum(v[2] for v in p["rows"].values())
grp = defaultdict(list)
for p in passes:
    grp[(p["batch"].split(":")[0], p["arm"])].append(p)
for g in grp.values():
    m = st.mean(p["solved"] for p in g)
    ms = st.mean(p["speed_s"] for p in g)
    for p in g:
        p["dev"] = p["solved"] - m
        p["speed_dev"] = p["speed_s"] - ms
first_seq = {}
for p in passes:
    first_seq.setdefault(p["batch"], min(q["seq"] for q in passes if q["batch"] == p["batch"]))
for p in passes:
    p["cold"] = p["seq"] == first_seq[p["batch"]]
    p["late"] = p["round"]

print(f"{len(passes)} passes | {len(anchors)} anchor tasks (speed proxy): {anchors}")
print(f"solved: mean {st.mean(p['solved'] for p in passes):.2f}, range {min(p['solved'] for p in passes)}-"
      f"{max(p['solved'] for p in passes)}; high (>=14): {sum(p['solved'] >= 14 for p in passes)}")


def corr(xs, ys, label):
    pts = [(x, y) for x, y in zip(xs, ys) if not math.isnan(x)]
    n = len(pts)
    mx, my = st.mean(x for x, _ in pts), st.mean(y for _, y in pts)
    sxy = sum((x - mx) * (y - my) for x, y in pts)
    sxx = sum((x - mx) ** 2 for x, _ in pts)
    syy = sum((y - my) ** 2 for _, y in pts)
    r = sxy / math.sqrt(sxx * syy) if sxx and syy else 0.0
    t = r * math.sqrt((n - 2) / (1 - r * r)) if abs(r) < 1 else float("inf")
    print(f"  {label:52s} n {n:3d}  r {r:+.2f}  t {t:+.2f}  slope {sxy / sxx if sxx else 0:+.3f} solves/unit")


print("\nA. correlations with outcome (solves vs arm/batch mean); |t| >= 2 would be a real effect")
dev = [p["dev"] for p in passes]
corr([p["speed_dev"] for p in passes], dev, "speed: anchor-task median sec (+ = slower GPU)")
corr([p["minutes"] for p in passes], dev, "pass wall minutes (confounded: solves end early)")
corr([p["late"] for p in passes], dev, "round index (warm-up / cache build-up)")
corr([p["seq"] for p in passes], dev, "passes since server boot")
corr([float(p["cold"]) for p in passes], dev, "cold: first pass after vLLM boot")
corr([p["overflow"] for p in passes], dev, "context overflows in the pass")
col = [p for p in passes if p["plat"] == "colab"]
pos = defaultdict(list)
for p in col:
    pos[(p["batch"], p["round"])].append(p)
for g in pos.values():
    for i, p in enumerate(sorted(g, key=lambda q: q["seq"])):
        p["pos"] = i
corr([p["pos"] for p in col], [p["dev"] for p in col], "Colab: position within round (0 = first)")

print("\nB. high (>=14) vs rest")
hi = [p for p in passes if p["solved"] >= 14]
lo = [p for p in passes if p["solved"] < 14]
for k in ("speed_s", "round", "seq", "overflow", "minutes"):
    print(f"  {k:9s} high {st.mean(p[k] for p in hi):7.2f} | rest {st.mean(p[k] for p in lo):7.2f}")
print(f"  cold    high {st.mean(p['cold'] for p in hi):.0%} | rest {st.mean(p['cold'] for p in lo):.0%}")
print("  high passes:", [(p["batch"], p["arm"], f"r{p['round']}", p["solved"], f"{p['speed_s']:.0f}s") for p in hi])
print("\nC. platform: mean solves | anchor speed")
for pl in ("colab", "kaggle"):
    q = [p for p in passes if p["plat"] == pl]
    if q:
        print(f"  {pl:7s} n {len(q):3d} solves {st.mean(p['solved'] for p in q):5.2f} sd {st.pstdev([p['solved'] for p in q]):4.2f}"
              f" | anchor median {st.mean(p['speed_s'] for p in q):6.1f}s")
print("\nD. by round index (all batches): mean deviation")
for r in sorted({p["round"] for p in passes}):
    q = [p["dev"] for p in passes if p["round"] == r]
    print(f"  round {r:2d} n {len(q):3d} dev {st.mean(q):+.2f}")
