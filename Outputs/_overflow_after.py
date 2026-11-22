"""Who works after the first overflow, and does the attempt's recorded error come from that first overflow?"""
import sqlite3
from collections import Counter

db = sqlite3.connect("kb/attempts.sqlite")
q = lambda s, *a: db.execute(s, a).fetchall()
auth, n_err, iters = Counter(), Counter(), Counter()
for aid, tid, f, l, sid in q("""SELECT a.id, t.trace_id, t.first_ts, t.last_ts, l.server_id FROM attempts_unique a
        JOIN traces t ON t.attempt_id = a.id JOIN attempt_server_load l ON l.attempt_id = a.id
        WHERE a.error_class = 'overflow'"""):
    errs = [x for (x,) in q("""SELECT ts FROM vllm_errors WHERE server_id = ? AND kind = 'context_overflow'
                               AND ts BETWEEN ? AND ? ORDER BY ts""", sid, f - 5, l + 15)]
    if not errs:
        continue
    e = errs[0]
    before = {a for (a,) in q("SELECT DISTINCT author FROM tool_calls WHERE trace_id = ? AND ts <= ?", aid and tid, e + 15)}
    after = Counter(a for (a,) in q("SELECT author FROM tool_calls WHERE trace_id = ? AND ts > ?", tid, e + 15))
    for a, c in after.items():
        auth[a] += c
    # distinct overflow bursts (gaps > 60 s) ~ separate agents/iterations hitting the limit
    bursts = 1 + sum(1 for x, y in zip(errs, errs[1:]) if y - x > 60)
    n_err["1 burst" if bursts == 1 else "2 bursts" if bursts == 2 else "3+ bursts"] += 1
    last_overflow_to_end = l - errs[-1]
    iters["trace ends within 30 s of the LAST overflow" if last_overflow_to_end <= 30 else "work continues > 30 s after last overflow"] += 1
print("tool calls after the first overflow, by author:", auth.most_common())
print("overflow bursts per attempt:", n_err.most_common())
print("end of trace vs last overflow:", iters.most_common())
