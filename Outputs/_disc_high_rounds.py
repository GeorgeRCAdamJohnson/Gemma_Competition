"""Discovery 1: where do high-scoring rounds come from? For every experiment-arm with >= 4 complete rounds on a fixed
cohort, decompose round totals: which tasks are 'swing' (solved in some rounds, not others), and how much of the
round-to-round variance would independent per-task coin flips explain (binomial expectation vs observed)."""
import math
import sqlite3
import statistics as st
from collections import defaultdict

db = sqlite3.connect("kb/attempts.sqlite")
q = lambda s, *a: db.execute(s, a).fetchall()
rows = q("""SELECT exp, arm, round, task, verified, resolved FROM attempts_unique
            WHERE round IS NOT NULL AND arm IS NOT NULL AND resolved IS NOT NULL AND model NOT LIKE '%31b%'""")
groups = defaultdict(lambda: defaultdict(dict))
for exp, arm, rnd, task, ver, res in rows:
    groups[(exp, arm)][rnd][task] = ver if ver is not None else res
print("exp / arm                                      rounds tasks  totals                     sd_obs  sd_coin  swing")
swing_all = defaultdict(lambda: [0, 0])
for (exp, arm), rounds in sorted(groups.items()):
    tasks = set.intersection(*(set(r) for r in rounds.values())) if rounds else set()
    full = {k: r for k, r in rounds.items() if tasks and tasks <= set(r)}
    if len(full) < 4 or len(tasks) < 12:
        continue
    totals = [sum(full[k][t] or 0 for t in tasks) for k in sorted(full)]
    rate = {t: st.mean(full[k][t] or 0 for k in full) for t in tasks}
    coin = math.sqrt(sum(p * (1 - p) for p in rate.values()))
    swing = [t for t, p in rate.items() if 0 < p < 1]
    for t in tasks:
        swing_all[t][0] += 1
        swing_all[t][1] += 0 < rate[t] < 1
    print(f"  {exp[:38]:38s} {arm[:8]:8s} {len(full):4d} {len(tasks):5d}  {str(totals)[:26]:26s} "
          f"{st.pstdev(totals):6.2f} {coin:7.2f} {len(swing):5d}")
print("\ntasks that swing in the most experiment-arms (solved in some rounds, not others):")
for t, (n, s) in sorted(swing_all.items(), key=lambda kv: -kv[1][1])[:15]:
    print(f"  {t:15s} swing in {s:2d} of {n:2d} experiment-arms")
