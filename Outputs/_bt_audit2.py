"""Audit 2: corrected overflow loss (only UNGRADED overflow attempts can have been lost to the overflow itself), and
expected per-round effects + A/B power for leads 1 and 2 on the 39-task Seed39 cohort."""
import math
import sqlite3
import statistics as st

db = sqlite3.connect("kb/attempts.sqlite")
q = lambda s, *a: db.execute(s, a).fetchall()
lost = 0.0
lost_hi = 0.0
n_ung_gold = 0
for task, k in q("""SELECT a.task, COUNT(*) FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id
        JOIN attempt_features f ON f.trace_id = t.trace_id WHERE a.model NOT LIKE '%31b%' AND a.error_class = 'overflow'
        AND f.edited_any_gold = 1 AND a.test_output_path IS NULL GROUP BY a.task"""):
    n_ung_gold += k
    r = q("""SELECT AVG(a.resolved), COUNT(*) FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id
             JOIN attempt_features f ON f.trace_id = t.trace_id WHERE a.task = ? AND a.model NOT LIKE '%31b%'
             AND COALESCE(a.error_class, '') <> 'overflow' AND f.edited_any_gold = 1""", task)[0]
    if r[1] >= 5:
        lost += k * (r[0] or 0)
    lost_hi += k * (r[0] or 0) if r[1] else 0
tot, solved = q("""SELECT COUNT(*), SUM(resolved) FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id
                   WHERE a.model NOT LIKE '%31b%' AND a.resolved IS NOT NULL""")[0]
print(f"ungraded overflow attempts with a gold-file edit: {n_ung_gold}")
print(f"corrected lost-solve estimate: {lost:.0f} solves = {lost / tot:.2%} of {tot} attempts = +{lost / solved:.1%} relative "
      f"(previous estimate 120). Per 39-task round: +{39 * lost / tot:.2f} tasks (upper bound: assumes the overflow "
      f"attempt would have done as well as non-overflow gold-edit attempts).")

# lead 1 effect sketch: share of attempts in the 'some' bucket on multi-hunk tasks x within-task gap x assumed uptake
some_share = 798 / tot   # runtime-only, tol 15 (audit A2)
for gap in (0.23, 0.31):
    for uptake in (0.25, 0.5):
        print(f"lead 1: some-share {some_share:.1%} x gap {gap} x uptake {uptake} = +{39 * some_share * gap * uptake:.2f} tasks/round")

# power: Seed39 historical per-round sd
rounds = [r[0] for r in q("""SELECT SUM(verified) FROM attempts_unique WHERE exp IN ('kaggle_e4b_evidence_seed39_r2_r10',
          'kaggle_e4b_repair_decisions_seed39_r1_r5_v2','kaggle_e4b_repair_decisions_seed39_r6_r10',
          'kaggle_e4b_seed39_evidence_first') GROUP BY exp, round""")]
sd = st.pstdev(rounds)
print(f"\nSeed39 per-round verified: n {len(rounds)} rounds, mean {st.mean(rounds):.2f}, sd {sd:.2f}")
for delta in (0.3, 0.5, 1.0, 1.5):
    n = math.ceil((2 * 2 * sd * sd) / delta ** 2) if delta else None  # paired diff sd ~ sqrt(2)*sd, t>=2
    print(f"  rounds per arm to reach t >= 2 for +{delta} tasks/round (unpaired-correlation assumption): {n}")
