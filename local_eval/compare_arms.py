"""Paired A/B analysis for A3 vs A5 across reps.

Answers the question the resolve count alone cannot: for EACH task, how many reps did each arm solve?
That per-task resolve count is the stable signal (the Kaggle replicates showed patch SIZE is a near-deterministic
fingerprint while the binary resolved bit flips on multi-solution tasks).

Usage:
    python compare_arms.py --arms A3=e4b_A3_rich44,e4b_A3_rich44_rep2 A5=e4b_A5_rich44,e4b_A5_rich44_rep2
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"


def load(tag):
    p = RUNS / f"{tag}.pinned.jsonl"
    if not p.exists():
        return None
    out = {}
    for line in p.read_text(encoding="utf-8").split("\n"):
        if line.strip():
            r = json.loads(line)
            out[r["task"]] = r
    return out


def load_raw(tag):
    p = RUNS / f"{tag}.results.jsonl"
    if not p.exists():
        return None
    out = {}
    for line in p.read_text(encoding="utf-8").split("\n"):
        if line.strip():
            r = json.loads(line)
            out[r["task"]] = r
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", required=True, help="NAME=tag1,tag2,...")
    args = ap.parse_args()

    arms = {}
    for spec in args.arms:
        name, tags = spec.split("=", 1)
        tl = [t for t in tags.split(",") if t]
        arms[name] = {"tags": tl, "pin": [load(t) for t in tl], "raw": [load_raw(t) for t in tl]}

    n = len(next(iter(arms.values()))["tags"])
    print(f"reps per arm: {n}\n")

    # per-task resolve count per arm
    counts = {}
    for name, a in arms.items():
        c = defaultdict(int)
        for p in a["pin"]:
            if not p:
                continue
            for t, r in p.items():
                if r["pinned_resolved"]:
                    c[t] += 1
        counts[name] = c

    names = list(arms)
    # Denominator must be EVERY scored task, not just those with >=1 resolve, or the
    # "x/8" per-rep figures silently inflate.
    tasks = sorted(set().union(*[set(p) for a in arms.values() for p in a["pin"] if p]))
    print(f"{'task':<12}" + "".join(f"{nm+'/rep':>12}" for nm in names) + "   verdict")
    decisive = []
    for t in tasks:
        row = [counts[nm].get(t, 0) for nm in names]
        if len(names) == 2:
            a, b = row
            v = f"{names[1]} +{b-a}" if b > a else (f"{names[0]} +{a-b}" if a > b else "tie")
            if a != b:
                decisive.append((t, a, b))
        else:
            v = ""
        print(f"{t:<12}" + "".join(f"{x:>12}" for x in row) + f"   {v}")

    print()
    for nm in names:
        tot = sum(counts[nm].values())
        print(f"  {nm}: {tot} resolves over {n} reps x {len(tasks)} tasks "
              f"(mean {tot/(n*len(tasks)):.3f} per rep = {tot/n:.1f}/{len(tasks)})")

    if len(names) == 2 and decisive:
        n0, n1 = names
        wins = sum(1 for _, a, b in decisive if b > a)
        loss = sum(1 for _, a, b in decisive if a > b)
        print(f"\n  tasks where the two arms DISAGREE: {len(decisive)}")
        print(f"    {n1} wins {wins}, {n0} wins {loss}")
        print(f"    detail: {[(t, a, b) for t, a, b in decisive]}")
        # McNemar exact-ish: two-sided binomial on the discordant pairs
        d = wins + loss
        if d:
            k = min(wins, loss)
            p = 2 * sum(math.comb(d, i) for i in range(k + 1)) / (2 ** d)
            print(f"    McNemar (discordant pairs only, n={d}): two-sided p = {min(p,1.0):.3f} "
                  f"-> {'SIGNIFICANT' if p < 0.05 else 'NOT significant'}")
        print("\n  VERDICT: " + ("decisive" if p < 0.05 else
              "directionally better but NOT statistically separated -- keep the simpler prompt"))

    # process metrics, averaged over reps
    print("\n  process metrics (mean over reps):")
    for label, f in [("mean tool calls", lambda r: r["calls"]),
                     ("empty patches", lambda r: 1 if r.get("patch_chars", 0) == 0 else 0),
                     ("call-cap exits", lambda r: 1 if r.get("end_reason") == "call_cap" else 0),
                     ("landed edits", lambda r: r.get("edit_ok", 0))]:
        out = []
        for nm, a in arms.items():
            vals = [f(r) for raw in a["raw"] if raw for r in raw.values()]
            out.append(f"{nm}={sum(vals)/len(vals):.2f}" if vals else f"{nm}=n/a")
        print(f"    {label:<18} " + "  ".join(out))


if __name__ == "__main__":
    main()