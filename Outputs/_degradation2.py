"""Two follow-ups to _degradation.py (task-adjusted outcomes, percentage points):
D. Same task repeated on the same vLLM server: residual by how many earlier attempts of that task the server served
   (a cached-prefix carry-over between repeats would show up here).
E. Drift across runs: the unchanged pack-1 control arm (C_pack1) and other unchanged-policy arms by experiment date."""
import math
import sqlite3
from collections import defaultdict

db = sqlite3.connect("kb/attempts.sqlite")
q = lambda s, *a: db.execute(s, a).fetchall()
task_mean = dict(q("""SELECT task, AVG(resolved) FROM attempts_unique
                      WHERE model NOT LIKE '%31b%' AND resolved IS NOT NULL GROUP BY task"""))


def summary(values):
    n = len(values)
    if n < 2:
        return n, None, None
    mean = sum(values) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))
    return n, mean, mean / (sd / math.sqrt(n)) if sd else 0.0


rows = q("""SELECT l.server_id, a.task, a.resolved, t.first_ts FROM attempt_server_load l
            JOIN attempts_unique a ON a.id = l.attempt_id JOIN traces t ON t.attempt_id = a.id
            WHERE a.resolved IS NOT NULL AND t.first_ts IS NOT NULL AND a.model NOT LIKE '%31b%'
            ORDER BY l.server_id, t.first_ts""")
seen = defaultdict(int)
bins = defaultdict(list)
for sid, task, res, start in rows:
    k = seen[(sid, task)]
    seen[(sid, task)] += 1
    bins[min(k, 6)].append(res - task_mean[task])
print("D. same task, same server: earlier attempts of this task on this server")
print(f"{'earlier':>8s} {'attempts':>8s} {'residual':>9s} {'z':>6s}")
for k in sorted(bins):
    n, m, z = summary(bins[k])
    if m is not None:
        print(f"{(str(k) + '+') if k == 6 else k:>8} {n:8d} {100 * m:+9.1f} {z:+6.1f}")

print("\nE. control arms by experiment start (C_pack1)")
ctl = q("""SELECT c.exp, c.first_utc, a.task, a.resolved FROM attempts_unique a JOIN experiment_catalog c ON c.exp = a.exp
           WHERE a.arm = 'C_pack1' AND a.resolved IS NOT NULL AND a.model NOT LIKE '%31b%'""")
per = defaultdict(list)
start = {}
for exp, first, task, res in ctl:
    per[exp].append(res - task_mean[task])
    start[exp] = first
for exp in sorted(per, key=lambda e: start[e] or ""):
    n, m, z = summary(per[exp])
    print(f"  {str(start[exp])[:16]:16s} {exp:42s} n {n:4d}  residual {100 * m:+5.1f}  z {z:+5.1f}")
