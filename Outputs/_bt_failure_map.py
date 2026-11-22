"""Breakthrough analysis 2: where do E4B's failures sit? Every traced, failed E4B attempt on a task E4B has solved at least
once is assigned ONE bucket (first match):
  overflow        context overflow error
  timeout         timeout / time budget error
  no_edit         no edit ever applied
  wrong_file      applied edits, none on a gold source file
  right_file      edited a gold source file but the hidden tests failed; split by the hidden-test output:
                    near   some of the task's NEW tests (added by test_patch) passed, no collection error
                    far    none of the new tests passed / collection error / regressions only
                    no_out no test output on disk
Also per bucket: share of attempts whose gate ACCEPTED (the agent thought it was done) and mean calls."""
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(".").resolve()
db = sqlite3.connect("kb/attempts.sqlite")
NEW = {t: set(re.findall(r"^\+\s*(?:async\s+)?def (test_\w+)", tp, re.M)) for t, tp in db.execute("SELECT task, test_patch FROM tasks")}
solved_tasks = {t for (t,) in db.execute("""SELECT DISTINCT task FROM attempts_unique WHERE resolved = 1
                                            AND model NOT LIKE '%31b%'""")}
sys_path = __import__("sys").path
sys_path.insert(0, "kb/attemptdb")
from vfs import VFS  # noqa: E402
vfs = VFS(roots=("Outputs",))


def test_detail(path, task):
    if not path or not vfs.exists(path):
        return "no_out", None
    txt = vfs.text(path)
    if re.search(r"ERROR collecting|errors? during collection|ImportError|ModuleNotFoundError", txt):
        return "far", "collection error"
    fails = set(re.findall(r"^(?:FAILED|ERROR) \S+::(\w+)", txt, re.M))
    new = NEW.get(task, set())
    nf = len(fails & new)
    if new and nf < len(new) and fails & new:
        return "near", f"{nf}/{len(new)} new tests failing"
    if new and not (fails & new) and fails:
        return "near", "only regressions fail"
    return "far", f"{nf}/{len(new)} new tests failing"


rows = db.execute("""
SELECT a.id, a.task, a.error_class, f.n_edit_ok, f.edited_any_gold, f.gate_accepted, f.n_calls, a.test_output_path, a.exp
FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id JOIN attempt_features f ON f.trace_id = t.trace_id
WHERE a.model NOT LIKE '%31b%' AND a.resolved = 0""").fetchall()
b = Counter()
acc = defaultdict(list)
calls = defaultdict(list)
near_detail = Counter()
per_task = defaultdict(Counter)
for aid, task, ec, nok, gold, gacc, nc, tout, exp in rows:
    if task not in solved_tasks:
        continue
    if ec == "overflow":
        k = "overflow"
    elif ec == "timeout":
        k = "timeout"
    elif not nok:
        k = "no_edit"
    elif not gold:
        k = "wrong_file"
    else:
        sub, det = test_detail(tout, task)
        k = f"right_file:{sub}"
        if sub == "near":
            near_detail[det.split(" new")[0] if "new" in det else det] += 1
    b[k] += 1
    acc[k].append(1 if gacc else 0)
    calls[k].append(nc or 0)
    per_task[task][k] += 1
tot = sum(b.values())
print(f"{tot} failed traced E4B attempts on {len(solved_tasks)} tasks E4B has solved at least once\n")
print("bucket                 n      share   gate ACCEPTED   mean calls")
for k, n in b.most_common():
    print(f"  {k:20s} {n:5d}  {n / tot:6.1%}   {sum(acc[k]) / n:8.1%}      {sum(calls[k]) / n:5.1f}")
print("\nright_file:near detail (new tests failing / total new):", near_detail.most_common(8))
print("\ntasks with the most right_file:near failures (fixable-by-contract candidates):")
for t, c in sorted(per_task.items(), key=lambda kv: -kv[1]["right_file:near"])[:12]:
    n = sum(c.values())
    sr = db.execute("SELECT ROUND(AVG(resolved),2), COUNT(*) FROM attempts_unique WHERE task = ? AND model NOT LIKE '%31b%'", (t,)).fetchone()
    print(f"  {t:15s} near {c['right_file:near']:4d} of {n:4d} failures | E4B solve rate {sr[0]} (n {sr[1]}) | {dict(c.most_common(3))}")
