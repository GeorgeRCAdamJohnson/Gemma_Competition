"""Breakthrough analysis 3: E4B context overflows -- who overflows, when, and what was lost?
For every E4B attempt that ended in a context overflow: which agent was running at the end (fixer / verifier / tester),
how many LoopAgent iterations had happened, whether a gold-file edit had already been applied, whether the gate had
ACCEPTED before the overflow, whether the patch was graded at all, and the prompt-token trajectory.
Then: on the same tasks, how often does an attempt that reached the same state (gold edit applied + gate accepted)
WITHOUT overflowing get solved -> an estimate of solves lost to overflow."""
import sqlite3
from collections import Counter

db = sqlite3.connect("kb/attempts.sqlite")
q = lambda s, *a: db.execute(s, a).fetchall()
rows = q("""
SELECT a.id, a.task, a.exp, a.patch_chars, a.test_exit_code, a.test_output_path IS NOT NULL, f.last_author,
       f.n_iterations, f.edited_any_gold, f.gate_accepted, f.n_edit_ok, f.max_prompt_tokens, f.n_calls,
       f.n_verifier_calls, f.n_fixer_calls, t.trace_id
FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id JOIN attempt_features f ON f.trace_id = t.trace_id
WHERE a.model NOT LIKE '%31b%' AND a.error_class = 'overflow'""")
n = len(rows)
print(f"{n} traced E4B overflow attempts")
print("  agent running at the end:", Counter(r[6] for r in rows).most_common())
print("  loop iterations completed:", sorted(Counter(r[7] for r in rows).items()))
print(f"  had applied an edit: {sum(1 for r in rows if r[10]) / n:.0%} | on a gold file: {sum(1 for r in rows if r[8]) / n:.0%}"
      f" | gate had ACCEPTED: {sum(1 for r in rows if r[9]) / n:.0%}")
print(f"  patch non-empty: {sum(1 for r in rows if r[3]) / n:.0%} | hidden tests run (output on disk): "
      f"{sum(1 for r in rows if r[5]) / n:.0%} | resolved: {q('''SELECT SUM(resolved) FROM attempts_unique
       WHERE model NOT LIKE '%31b%' AND error_class = 'overflow' ''')[0][0]}")
# prompt growth: which author's turn crossed 20k tokens first
cross = Counter()
for r in rows:
    s = q("SELECT author, prompt_tokens FROM steps WHERE trace_id = ? AND prompt_tokens IS NOT NULL ORDER BY step_id", r[15])
    first = next((a for a, p in s if p >= 20000), None)
    cross[first] += 1
print("  author whose turn first exceeded 20k prompt tokens:", cross.most_common())
# lost-solve estimate: same task, non-overflow attempts with a gold edit applied AND gate accepted
est = 0.0
detail = []
for task, k in q("""SELECT a.task, COUNT(*) FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id
    JOIN attempt_features f ON f.trace_id = t.trace_id WHERE a.model NOT LIKE '%31b%' AND a.error_class = 'overflow'
    AND f.edited_any_gold = 1 GROUP BY a.task"""):
    r = q("""SELECT AVG(a.resolved), COUNT(*) FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id
             JOIN attempt_features f ON f.trace_id = t.trace_id WHERE a.task = ? AND a.model NOT LIKE '%31b%'
             AND COALESCE(a.error_class, '') <> 'overflow' AND f.edited_any_gold = 1""", task)[0]
    if r[1] >= 5:
        est += k * (r[0] or 0)
        detail.append((task, k, round(r[0] or 0, 2), r[1]))
tot_attempts = q("SELECT COUNT(*) FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id WHERE a.model NOT LIKE '%31b%'")[0][0]
solved = q("SELECT SUM(resolved) FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id WHERE a.model NOT LIKE '%31b%'")[0][0]
print(f"\nlost-solve estimate: overflow attempts with a gold-file edit x the solve rate of non-overflow gold-edit attempts"
      f" on the same task = {est:.0f} solves ({est / tot_attempts:.1%} of {tot_attempts} traced attempts; "
      f"current solves {solved}, i.e. +{est / solved:.0%} relative)")
for d in sorted(detail, key=lambda x: -x[1] * x[2])[:10]:
    print(f"   {d[0]:15s} overflow-with-gold-edit {d[1]:4d} x solve rate {d[2]} (n {d[3]})")
# which experiments / arms overflow most
print("\noverflow rate by experiment (traced E4B, >= 100 attempts):")
for r in q("""SELECT a.exp, COUNT(*), ROUND(AVG(a.error_class = 'overflow'), 3) FROM attempts_unique a
              JOIN traces t ON t.attempt_id = a.id WHERE a.model NOT LIKE '%31b%' GROUP BY a.exp HAVING COUNT(*) >= 100
              ORDER BY 3 DESC"""):
    print(f"   {r[0]:45s} n {r[1]:5d} overflow {r[2]:.1%}")
