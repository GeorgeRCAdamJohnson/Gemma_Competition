"""Offline validation of GPU rule 4 (stop an experiment attempt at its first context overflow). Safe only if
(a) no overflow attempt was ever resolved, and (b) after the first overflow the agent made no tool call that could change
the on-disk patch (any edit/write/command), so the graded patch would be identical. Uses lanes with vLLM logs."""
import sqlite3
from collections import Counter

db = sqlite3.connect("kb/attempts.sqlite")
q = lambda s, *a: db.execute(s, a).fetchall()
res = q("SELECT COUNT(*), SUM(resolved) FROM attempts_unique WHERE error_class = 'overflow'")[0]
print(f"(a) overflow attempts {res[0]}, resolved {res[1]}")
after = Counter()
n = 0
for aid, tid, f, l, sid in q("""SELECT a.id, t.trace_id, t.first_ts, t.last_ts, l.server_id FROM attempts_unique a
        JOIN traces t ON t.attempt_id = a.id JOIN attempt_server_load l ON l.attempt_id = a.id
        WHERE a.error_class = 'overflow'"""):
    e = q("""SELECT MIN(ts) FROM vllm_errors WHERE server_id = ? AND kind = 'context_overflow' AND ts BETWEEN ? AND ?""",
          sid, f - 5, l + 15)[0][0]
    if not e:
        continue
    n += 1
    # vLLM timestamps are whole seconds and untimestamped lines inherit the previous one (<= ~10 s early),
    # so allow a 15 s margin before counting a call as "after" the first overflow
    calls = q("""SELECT tool, is_edit, author FROM tool_calls WHERE trace_id = ? AND ts > ?""", tid, e + 15)
    kinds = Counter(("EDIT" if c[1] else c[0]) for c in calls)
    if not calls:
        after["no tool call after first overflow"] += 1
    elif kinds.get("EDIT"):
        after["EDIT after first overflow"] += 1
    else:
        after["non-edit calls only after first overflow"] += 1
print(f"(b) overflow attempts on logged lanes: {n}")
for k, v in after.most_common():
    print(f"    {k:42s} {v:4d} ({v / n:.0%})")
