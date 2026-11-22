"""Discovery 3: would an EARLY RESTART beat continuing? For swing tasks (strata as in discovery 2), compare
  P(solve | the attempt is still running at call k with no successful edit yet)          -> value of continuing
  P(solve | the attempt has made its first successful edit by call k, on a gold file / elsewhere)
against the stratum's base solve rate (what a fresh restart would give, if time allows). Also the time cost: median
seconds spent by attempts that reach call k without an edit."""
import sqlite3
from collections import defaultdict

db = sqlite3.connect("kb/attempts.sqlite")
q = lambda s, *a: db.execute(s, a).fetchall()
rows = q("""SELECT a.exp, a.arm, a.task, a.resolved, f.first_edit_idx, f.first_edit_gold, f.n_calls, f.wall_s, t.trace_id
            FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id JOIN attempt_features f ON f.trace_id = t.trace_id
            WHERE f.basis = 'trace' AND a.model NOT LIKE '%31b%' AND a.resolved IS NOT NULL AND a.arm IS NOT NULL""")
by = defaultdict(list)
for r in rows:
    by[(r[0], r[1], r[2])].append(r)
usable = {k: v for k, v in by.items() if sum(x[3] for x in v) >= 3 and sum(1 - x[3] for x in v) >= 3}
att = [x for v in usable.values() for x in v]
base = {k: sum(x[3] for x in v) / len(v) for k, v in usable.items()}
print(f"{len(att)} attempts in {len(usable)} swing strata; mean base solve rate {sum(base.values()) / len(base):.3f}\n")
ts = defaultdict(list)
for tid, idx, t in q("SELECT trace_id, idx, ts FROM tool_calls ORDER BY trace_id, idx"):
    ts[tid].append(t)
print("  k  | still no edit at call k: n   solve   base(same strata)  ratio  median s spent | edited by k on gold: solve | elsewhere: solve")
for k in (3, 5, 8, 10, 12, 15, 20, 25):
    alive = [x for x in att if x[6] >= k and (x[4] is None or x[4] >= k)]
    gold = [x for x in att if x[4] is not None and x[4] < k and x[5] == 1]
    other = [x for x in att if x[4] is not None and x[4] < k and x[5] == 0]
    if not alive:
        continue
    s = sum(x[3] for x in alive) / len(alive)
    b = sum(base[(x[0], x[1], x[2])] for x in alive) / len(alive)
    spent = sorted((ts[x[8]][k - 1] - ts[x[8]][0]) for x in alive if len(ts[x[8]]) >= k and ts[x[8]][0])
    med = spent[len(spent) // 2] if spent else float("nan")
    sg = sum(x[3] for x in gold) / len(gold) if gold else float("nan")
    so = sum(x[3] for x in other) / len(other) if other else float("nan")
    print(f" {k:3d} | {len(alive):6d} {s:7.3f}   {b:7.3f}          {s / b if b else 0:5.2f}  {med:8.0f}      | "
          f"{sg:6.3f} (n {len(gold):4d}) | {so:6.3f} (n {len(other):4d})")
