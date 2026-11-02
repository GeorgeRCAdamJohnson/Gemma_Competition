"""Gate-noise estimate from the coin-flip tasks. CPU only, no GPU.

Tasks whose resolve rate is strictly between 0 and 1 across traced runs are the
only source of run-to-run variance we have. This script:
  1. fits p_hat per coin-flip task and reports binomial noise,
  2. simulates gates drawn from the observed p_hat mix to get the FULL spread of
     gate outcomes, i.e. what tells us whether 4/6 vs 6/6 means anything,
  3. reports P(a null arm scores >= baseline), our real risk of promoting a no-op,
  4. reports whether a gate can distinguish a real lift, PAIRED (same task set).

Resolves are simulated as Bernoulli(p_hat): a run resolves when u < p_hat.
Nothing here compares to the 0.15 board number; it quantifies gate noise only.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import random
import statistics

GEMMA = pathlib.Path(__file__).resolve().parent.parent
RUNS = GEMMA / "kb" / "runs.jsonl"
N = 20000


def load():
    per = collections.defaultdict(list)
    for line in RUNS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        out = r.get("outcome") or {}
        if isinstance(out, dict) and "resolved" in out:
            per[r["task"]].append(bool(out["resolved"]))
    return per


def gate_draws(rng, ps, G, n):
    return [sum(rng.random() < rng.choice(ps) for _ in range(G)) for _ in range(n)]


def paired(rng, ps, G, n, lift=1.0):
    """Both arms score ONE shared task set. Returns P(arm>base), P(arm>=base)."""
    strict = tie = 0
    for _ in range(n):
        tasks = [rng.choice(ps) for _ in range(G)]
        b = sum(rng.random() < p for p in tasks)
        a = sum(rng.random() < min(0.99, p * lift) for p in tasks)
        strict += a > b
        tie += a >= b
    return strict / n, tie / n


def main():
    per = load()
    coin = {}
    for t, vals in sorted(per.items()):
        rate = sum(vals) / len(vals)
        if 0.0 < rate < 1.0:
            coin[t] = (rate, len(vals))
    ps = [p for p, _ in coin.values()]
    rng = random.Random(20261016)

    print("=" * 74)
    print("1. COIN-FLIP TASKS (rate strictly between 0 and 1)")
    print("=" * 74)
    print(f"{'task':14}{'p_hat':>8}{'n':>5}{'sd_single':>11}{'95%CI':>18}")
    for t, (p, n) in coin.items():
        sd = math.sqrt(p * (1 - p) / n)
        print(f"{t:14}{p:>8.2f}{n:>5}{sd:>11.3f}"
              f"   [{max(0, p - 1.96 * sd):.2f}, {min(1, p + 1.96 * sd):.2f}]")
    print(f"\ncoin-flip tasks: {len(coin)} of {len(per)} traced"
          f"   mean p_hat={statistics.mean(ps):.3f}")
    print("p_hat sorted:", ", ".join(f"{p:.2f}" for p in sorted(ps)))
    print(f"=> between-task sd of p_hat = {statistics.stdev(ps):.3f}")

    print()
    print("=" * 74)
    print("2. SIMULATED GATE SPREAD (draw G tasks from the observed p_hat mix)")
    print("=" * 74)
    for G in (6, 12, 24, 48):
        draws = gate_draws(rng, ps, G, N)
        srt = sorted(draws)
        lo, hi = srt[int(0.05 * N)], srt[int(0.95 * N)]
        print(f"gate G={G:>3}: expected resolves {statistics.mean(draws):>5.1f}"
              f"  sd={statistics.stdev(draws):>4.1f}"
              f"  90% range [{lo}, {hi}]  spread={hi - lo}")

    print()
    print("=" * 74)
    print("3. PROMOTE-A-NO-OP RISK, PAIRED (both arms run the SAME tasks)")
    print("=" * 74)
    print("A real gate scores baseline and arm on one fixed task set, so task-set")
    print("variance is shared. Null arm = true no-op, identical p_hat.")
    for G in (6, 12, 24, 48, 129):
        st, ti = paired(rng, ps, G, N)
        print(f"G={G:>3}: P(arm > base)={st:.3f}  P(arm >= base)={ti:.3f}"
              f"  -> a 'win' sits {(st - 0.5) * 100:+.1f}pp above a coin flip")

    print()
    print("=" * 74)
    print("4. CAN A GATE DISTINGUISH A REAL LIFT? (paired, P(arm>base))")
    print("=" * 74)
    print("Pool is only 6 distinct tasks, so G > 6 re-draws the same tasks: that is")
    print("a REPLICATE (more runs per task), not a bigger gate.")
    for lift in (1.25, 1.5, 2.0, 3.0):
        row = []
        for G in (6, 12, 24, 48, 129):
            st, _ = paired(rng, ps, G, N, lift=lift)
            row.append(f"G={G}:{st:.3f}")
        best = max(float(x.split(":")[1]) for x in row)
        print(f"  lift x{lift:<5} " + "  ".join(row) + f"   best={best:.3f}")

    print()
    print("=" * 74)
    print("5. THE BINDING CONSTRAINT")
    print("=" * 74)
    print(f"Distinct coin-flip tasks: {len(coin)} of {len(per)} traced.")
    print(f"Pool mean p_hat={statistics.mean(ps):.3f} sd={statistics.stdev(ps):.3f}")
    print("Discrimination is bounded by the POOL, not by run count: extra runs")
    print("shrink within-task noise but cannot add tasks. Only 3 of the 6")
    print("coin-flip tasks sit above 0.5 p_hat, so a uniform multiplicative lift")
    print("moves the pool mean only slightly and the residual task ceiling caps it.")

    out = GEMMA / "kb" / "audits" / "_gate_noise.json"
    out.write_text(json.dumps(
        {"coin_flip": {t: {"p_hat": p, "n": n} for t, (p, n) in coin.items()}},
        indent=1), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
