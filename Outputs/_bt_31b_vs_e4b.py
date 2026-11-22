"""Breakthrough analysis 4: 31B vs E4B on the SAME tasks -- behaviour, not just score. Traced attempts only."""
import sqlite3

db = sqlite3.connect("kb/attempts.sqlite")
q = lambda s, *a: db.execute(s, a).fetchall()
shared = [t for (t,) in q("""SELECT a.task FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id WHERE a.resolved IS NOT NULL
    GROUP BY a.task HAVING SUM(a.model LIKE '%31b%') >= 3 AND SUM(a.model NOT LIKE '%31b%') >= 10""")]
print(f"{len(shared)} tasks with >= 3 traced 31B and >= 10 traced E4B attempts")
ph = ",".join("?" * len(shared))
cols = """COUNT(*) n, ROUND(AVG(a.resolved),3) solve, ROUND(AVG(f.n_calls),1) calls, ROUND(AVG(f.calls_before_first_edit),1) to_edit,
 ROUND(AVG(f.first_edit_gold),2) edit_gold, ROUND(AVG(f.n_edit_fail),2) edit_fail, ROUND(AVG(f.n_read_file),1) reads,
 ROUND(AVG(f.n_grep),1) greps, ROUND(AVG(f.n_repeat_calls),2) repeats, ROUND(AVG(f.n_edited_files),2) files,
 ROUND(AVG(f.max_prompt_tokens)) max_prompt, ROUND(AVG(COALESCE(a.error_class,'')='overflow'),3) overflow,
 ROUND(AVG(f.thinking_chars)) think_chars"""
for label, cond in (("31B", "a.model LIKE '%31b%'"), ("E4B", "a.model NOT LIKE '%31b%'")):
    r = q(f"""SELECT {cols} FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id JOIN attempt_features f ON f.trace_id = t.trace_id
              WHERE {cond} AND a.resolved IS NOT NULL AND a.task IN ({ph})""", *shared)[0]
    names = [c.split()[-1] for c in cols.split(",")]
    print(f"\n{label}: " + " | ".join(f"{k} {v}" for k, v in zip(names, r)))
print("\nper task (31B solve vs E4B solve; E4B first edit on gold file):")
for t in shared:
    r = q("""SELECT ROUND(AVG(CASE WHEN a.model LIKE '%31b%' THEN a.resolved END),2), ROUND(AVG(CASE WHEN a.model NOT LIKE '%31b%' THEN a.resolved END),2),
             ROUND(AVG(CASE WHEN a.model NOT LIKE '%31b%' THEN f.first_edit_gold END),2),
             ROUND(AVG(CASE WHEN a.model LIKE '%31b%' THEN f.first_edit_gold END),2)
             FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id JOIN attempt_features f ON f.trace_id = t.trace_id
             WHERE a.task = ? AND a.resolved IS NOT NULL""", t)[0]
    print(f"  {t:15s} 31B {r[0]}  E4B {r[1]}  | first edit gold: 31B {r[3]} E4B {r[2]}")
