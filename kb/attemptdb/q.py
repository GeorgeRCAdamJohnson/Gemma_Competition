"""Query kb/attempts.sqlite.
usage:
  python kb/attemptdb/q.py "SELECT ..."              ad-hoc SQL (tables: attempts, attempts_unique, pass_summary,
                                                      task_rates, experiments, arms, tasks, submissions)
  python kb/attemptdb/q.py --task rich_3782          every unique attempt of a task, newest experiments first
  python kb/attemptdb/q.py --exp <exp> [--by round]  per-arm (or per-arm-round) totals for one experiment
  python kb/attemptdb/q.py --schema                  table/column list
"""
import argparse
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[2] / "kb" / "attempts.sqlite"


def show(cur, limit=200):
    cols = [d[0] for d in cur.description]
    rows = cur.fetchmany(limit)
    w = [max(len(str(c)), *(len(str(r[i])[:60]) for r in rows)) if rows else len(c) for i, c in enumerate(cols)]
    print("  ".join(str(c).ljust(w[i]) for i, c in enumerate(cols)))
    for r in rows:
        print("  ".join(str(v)[:60].ljust(w[i]) for i, v in enumerate(r)))
    print(f"({len(rows)} rows{' shown, more exist' if len(rows) == limit else ''})")


ap = argparse.ArgumentParser()
ap.add_argument("sql", nargs="?")
ap.add_argument("--task")
ap.add_argument("--exp")
ap.add_argument("--by", choices=["arm", "round"], default="arm")
ap.add_argument("--schema", action="store_true")
ap.add_argument("--limit", type=int, default=200)
a = ap.parse_args()
db = sqlite3.connect(DB)
if a.schema:
    for (name, sql) in db.execute("SELECT name, sql FROM sqlite_master WHERE type IN ('table','view') ORDER BY type, name"):
        print(f"-- {name}\n{sql}\n")
elif a.task:
    show(db.execute("""SELECT exp, arm, round, model, source, resolved, verified, error_class, patch_chars,
        ROUND(duration_s) AS s, tool_calls, trace_path FROM attempts_unique WHERE task = ? ORDER BY exp DESC, arm, round""",
                    (a.task,)), a.limit)
elif a.exp:
    grp = "arm" if a.by == "arm" else "arm, round"
    show(db.execute(f"""SELECT {grp}, COUNT(*) AS n, SUM(resolved) AS resolved, SUM(verified) AS verified,
        SUM(verified IS NULL) AS unverifiable, SUM(error_class='overflow') AS overflow, ROUND(AVG(duration_s)) AS mean_s
        FROM attempts_unique WHERE exp = ? GROUP BY {grp} ORDER BY {grp}""", (a.exp,)), a.limit)
else:
    show(db.execute(a.sql), a.limit)
