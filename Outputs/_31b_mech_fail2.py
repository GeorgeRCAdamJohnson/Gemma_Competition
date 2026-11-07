"""Split the 31B mechanical failures into what a pre-submit check could catch vs not."""
import json
import re
from collections import Counter
from pathlib import Path

A = re.compile(r"\x1b\[[0-9;]*m")
dead = set(json.load(open("kaggle_pkg/live_dead_129.json"))["dead"]) | {"fastapi_14266"}
live = set(json.load(open("kaggle_pkg/live_ids_31b_ab.json"))["order"])
root = Path("Outputs/v7_31b_full129/results")
rows = {r["task"]: r for r in json.load(open("Outputs/v7_31b_full129/_cap_sim_rows.json"))}
imp = Counter(); emp = Counter(); syn = []
for t, r in rows.items():
    if r["resolved"]:
        continue
    log = A.sub("", (root / "logs" / f"{t}.log").read_text(encoding="utf-8", errors="replace"))
    to = root / "test_outputs" / f"{t}.log"
    out = A.sub("", to.read_text(errors="replace")) if to.exists() else ""
    m = re.search(r'submit_patch: \{"status": "ok", "patch_size": (\d+)', log)
    size = int(m.group(1)) if m else None
    grp = "dead" if t in dead else ("live" if t in live else "other(requests/httpx)")
    if size == 0 or (m is None and not r.get("commit_call")):
        how = "submitted EMPTY" if size == 0 else "never submitted (budget/time end)"
        emp[(grp, how)] += 1
    elif re.search(r"(SyntaxError|IndentationError)", out):
        syn.append((t, grp))
    elif re.search(r"(ImportError while|ModuleNotFoundError|NameError: name)", out):
        imp[grp] += 1
print("v7 EMPTY (unsolved):", dict(emp))
print("v7 SYNTAX (unsolved):", syn)
print("v7 IMPORT/collection (unsolved):", dict(imp))
ab = json.load(open("Outputs/ca5_31b_ab/ab31.json"))["rows"]
e = [r for r in ab if not r["resolved"] and not (r.get("patch") or 0)]
print("\nab31 empty unsolved by error field:", Counter((r.get("err") or "none")[:50] for r in e).most_common(6))
print("ab31 empty unsolved by calls:", sorted((r.get("calls") or 0) for r in e))
