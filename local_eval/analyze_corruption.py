"""Corruption-rate analyzer for the edit_file argument-corruption arm.

Primary metric (pre-registered): corrupted edit_file calls / total edit_file calls,
a RATE rather than a count, so exposure (how many edits a task attempted) cannot
inflate it. Corruption is identified by status=None, which the harness sets exactly
when a mandatory argument is missing; verified against args_full on trace L315.

Usage:
    python analyze_corruption.py --arms A2=pilot_A2_rep1,pilot_A2_rep2 A3=pilot_A3_rep1,pilot_A3_rep2
    python analyze_corruption.py --arms A2=e4b_A2_par6_rep1,...,e4b_A2_rich44
"""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"


def load(tag):
    """Return (per-task stats, task order) for one run tag."""
    trace = RUNS / f"{tag}.trace.jsonl"
    results = RUNS / f"{tag}.results.jsonl"
    if not trace.exists():
        return None
    per = defaultdict(lambda: {"edit": 0, "corrupt": 0})
    for line in trace.read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("kind") != "tool" or r.get("tool") != "edit_file":
            continue
        per[r["task"]]["edit"] += 1
        if r.get("status") is None:
            per[r["task"]]["corrupt"] += 1
    rows = {}
    if results.exists():
        for line in results.read_text(encoding="utf-8").split("\n"):
            if line.strip():
                r = json.loads(line)
                rows[r["task"]] = r
    return per, rows


def rate(per):
    edit = sum(v["edit"] for v in per.values())
    corrupt = sum(v["corrupt"] for v in per.values())
    return corrupt, edit, (corrupt / edit if edit else 0.0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", required=True, help="NAME=tag1,tag2,...")
    ap.add_argument("--per-task", action="store_true")
    args = ap.parse_args()

    summary = {}
    for spec in args.arms:
        name, tags = spec.split("=", 1)
        agg = defaultdict(lambda: {"edit": 0, "corrupt": 0})
        landed = resolved = reps = 0
        task_hits = defaultdict(list)
        for tag in tags.split(","):
            got = load(tag)
            if not got:
                print(f"  (skip missing {tag})")
                continue
            per, rows = got
            reps += 1
            for t, v in per.items():
                agg[t]["edit"] += v["edit"]
                agg[t]["corrupt"] += v["corrupt"]
            landed += sum(r.get("edit_ok", 0) for r in rows.values())
            resolved += sum(1 for r in rows.values() if r.get("resolved"))
            for t in agg:
                task_hits[t].append(1 if any(
                    rr.get("task") == t and rr.get("resolved") for rr in rows.values()) else 0)
        c, e, rt = rate(agg)
        summary[name] = (c, e, rt, landed, resolved, reps)
        print(f"{name:<6} reps={reps}  corrupted={c}/{e} = {rt:.3f}  landed={landed}  resolved={resolved}")
        if args.per_task:
            for t in sorted(agg):
                tc, te = agg[t]["corrupt"], agg[t]["edit"]
                hits = task_hits.get(t, [])
                print(f"    {t:<12} {tc:>3}/{te:<4} = {tc/te if te else 0:.2f}  solved {sum(hits)}/{len(hits)}")

    if len(summary) == 2:
        (n1, (c1, e1, r1, l1, s1, p1)), (n2, (c2, e2, r2, l2, s2, p2)) = summary.items()
        print(f"\n{n1} -> {n2}: corruption {r1:.3f} -> {r2:.3f} "
              f"({(r2-r1)/r1*100:+.0f}% relative)" if r1 else "")
        if r1 > 0 and e2 > 0:
            # Two-proportion z-test on edit_file calls, pooled.
            p = (c1 + c2) / (e1 + e2)
            se = math.sqrt(p * (1 - p) * (1 / e1 + 1 / e2))
            z = (r2 - r1) / se if se else 0.0
            print(f"  two-proportion z = {z:.2f}  "
                  f"({'SIGNIFICANT' if abs(z) > 1.96 else 'not significant'} at 95%)")
        print(f"  landed {l1} -> {l2}   resolved {s1} -> {s2}   (must not decline)")


if __name__ == "__main__":
    main()