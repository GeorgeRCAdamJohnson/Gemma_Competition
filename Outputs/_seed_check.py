"""Are passes that share a vLLM seed correlated? Batch 5a and 5b ran the SAME arms on two separate Kaggle kernels, both
starting vLLM with the default seed. If sampling is seed-reproducible, run k of an arm in 5a ~ run k in 5b.
Per task we compare (a) outcome agreement and (b) an exact-trajectory signature (tool calls, llm calls, patch size):
SAME run index across kernels vs DIFFERENT run index (baseline). Plus: within one kernel, are run pairs more alike
than chance (shared server state)?"""
import itertools
import json
import statistics as st
from pathlib import Path

P = {}
for b in ("kaggle_batch5a", "kaggle_batch5b"):
    for p in json.loads(Path(f"Outputs/{b}/variance_ab.json").read_text(encoding="utf-8-sig"))["passes"]:
        if p.get("complete", True) and p["n"] >= 24:
            P[(b, p["arm"], p["run"])] = {r["id"]: r for r in p["rows"]}
arms = sorted({a for _, a, _ in P})
print("passes:", {b: sorted({(a, r) for bb, a, r in P if bb == b}) for b in ("kaggle_batch5a", "kaggle_batch5b")})


def compare(x, y):
    ids = sorted(set(x) & set(y))
    agree = st.mean(x[t]["resolved"] == y[t]["resolved"] for t in ids)
    sig = st.mean((x[t]["calls"], x[t]["llm"], x[t]["patch"]) == (y[t]["calls"], y[t]["llm"], y[t]["patch"]) for t in ids)
    patch = st.mean(x[t]["patch"] == y[t]["patch"] and x[t]["patch"] > 0 for t in ids)
    return agree, sig, patch


def summarize(label, pairs):
    if not pairs:
        print(f"  {label:44s} n 0")
        return
    a, s, pt = zip(*pairs)
    print(f"  {label:44s} n {len(pairs):3d} | outcome agree {st.mean(a):.1%} | identical trajectory {st.mean(s):.1%}"
          f" | identical patch size {st.mean(pt):.1%}")


print("\n1. ACROSS kernels (5a vs 5b), same arm")
same, diff = [], []
for a in arms:
    ra = [r for b, aa, r in P if b == "kaggle_batch5a" and aa == a]
    rb = [r for b, aa, r in P if b == "kaggle_batch5b" and aa == a]
    for i in ra:
        for j in rb:
            (same if i == j else diff).append(compare(P[("kaggle_batch5a", a, i)], P[("kaggle_batch5b", a, j)]))
summarize("same run index (shared seed position)", same)
summarize("different run index (baseline)", diff)

print("\n2. WITHIN a kernel, same arm, different runs (does a server repeat itself?)")
within = []
for b in ("kaggle_batch5a", "kaggle_batch5b"):
    for a in arms:
        rs = sorted(r for bb, aa, r in P if bb == b and aa == a)
        within += [compare(P[(b, a, i)], P[(b, a, j)]) for i, j in itertools.combinations(rs, 2)]
summarize("within-kernel run pairs", within)

print("\n3. per arm, same-index across kernels")
for a in arms:
    ra = {r for b, aa, r in P if b == "kaggle_batch5a" and aa == a}
    rb = {r for b, aa, r in P if b == "kaggle_batch5b" and aa == a}
    summarize(f"{a} runs {sorted(ra & rb)}", [compare(P[("kaggle_batch5a", a, k)], P[("kaggle_batch5b", a, k)]) for k in ra & rb])

print("\n4. expected outcome agreement if passes were independent (from per-task solve rates)")
for a in arms:
    ps = [v for (b, aa, r), v in P.items() if aa == a]
    ids = sorted(set.intersection(*(set(v) for v in ps)))
    rate = {t: st.mean(v[t]["resolved"] for v in ps) for t in ids}
    print(f"  {a:8s} independent-expected agreement {st.mean(q * q + (1 - q) * (1 - q) for q in rate.values()):.1%}")
