"""How often does the 31B submit a MECHANICALLY broken patch (empty, or a file that no longer parses / imports)?
Sources: v7 uncapped (129 tasks, test_outputs + logs) and ab31 enforced 28/8 (85 live, rows carry patch size, both
arms, all rounds). A pre-submit syntax/empty check can only convert these classes."""
import glob
import json
import re
from collections import Counter
from pathlib import Path

A = re.compile(r"\x1b\[[0-9;]*m")
SYN = re.compile(r"(SyntaxError|IndentationError|TabError)")
IMP = re.compile(r"(ImportError while (loading conftest|importing test module)|ModuleNotFoundError|NameError: name)")

# ---- v7: test_outputs + logs ----
root = Path("Outputs/v7_31b_full129/results")
rows = {r["task"]: r for r in json.load(open("Outputs/v7_31b_full129/_cap_sim_rows.json"))}
c = Counter(); ex = {}
for t, r in rows.items():
    to = root / "test_outputs" / f"{t}.log"
    log = A.sub("", (root / "logs" / f"{t}.log").read_text(encoding="utf-8", errors="replace"))
    out = A.sub("", to.read_text(errors="replace")) if to.exists() else ""
    submitted = "submit_patch: {\"status\": \"ok\"" in log
    m = re.search(r'submit_patch: \{"status": "ok", "patch_size": (\d+)', log)
    size = int(m.group(1)) if m else None
    if r["resolved"]:
        c["resolved"] += 1; continue
    if size == 0 or (not submitted and not r.get("commit_call")):
        c["unsolved: EMPTY / no edit"] += 1; ex.setdefault("empty", t)
    elif SYN.search(out):
        c["unsolved: SYNTAX error at test time"] += 1; ex.setdefault("syntax", t)
    elif IMP.search(out):
        c["unsolved: IMPORT/collection error at test time"] += 1; ex.setdefault("import", t)
    elif not out:
        c["unsolved: no test output"] += 1
    else:
        c["unsolved: tests ran, failed (logic)"] += 1
print("== v7 31B uncapped, 129 tasks:")
for k, v in c.most_common():
    print(f"   {v:3d}  {k}")
print("   examples:", ex)

# ---- ab31: enforced 28/8, 85 live, both arms, all rounds ----
ab = json.load(open("Outputs/ca5_31b_ab/ab31.json"))["rows"]
n = len(ab); unsolved = [r for r in ab if not r["resolved"]]
empty = [r for r in unsolved if not (r.get("patch") or 0)]
print(f"\n== ab31 31B enforced 28/8: {n} task-runs, {n-len(unsolved)} solved")
print(f"   unsolved with EMPTY patch: {len(empty)} ({100*len(empty)/n:.1f}% of runs) | by task: {Counter(r['id'] for r in empty).most_common(6)}")
print(f"   unsolved with a non-empty patch: {len(unsolved)-len(empty)}")
