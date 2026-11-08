"""For each task that timed out in presubmit-85: how often does the 31B solve it across ALL our 31B runs, and does
it time out repeatedly? Recoverable = solved in other runs (the model CAN do it; the clock is the blocker)."""
import json
from collections import defaultdict

runs = defaultdict(lambda: {"n": 0, "solved": 0, "timeout": 0, "src": defaultdict(lambda: [0, 0])})


def add(task, solved, timeout, src):
    r = runs[task]; r["n"] += 1; r["solved"] += bool(solved); r["timeout"] += bool(timeout)
    r["src"][src][0] += bool(solved); r["src"][src][1] += 1


for r in json.load(open("Outputs/ca5_31b_presubmit_85/presubmit_ab.json"))["rows"]:
    add(r["id"], r["resolved"], "timeout" in (r["err"] or ""), "pre85")
for r in json.load(open("Outputs/ca5_31b_ab/ab31.json"))["rows"]:
    add(r["id"], r["resolved"], "timeout" in (r.get("err") or ""), "ab31")
for r in json.load(open("Outputs/ca5_31b_cap_ab/cap_ab.json"))["rows"]:
    add(r["id"], r["resolved"], "timeout" in (r.get("err") or ""), "cap")
v7 = {r["task"]: r for r in json.load(open("Outputs/v7_31b_full129/_cap_sim_rows.json"))}
for t, r in v7.items():
    add(t, r["resolved"], False, "v7(uncapped)")

T = sorted({r["id"] for r in json.load(open("Outputs/ca5_31b_presubmit_85/presubmit_ab.json"))["rows"]
            if "timeout" in (r["err"] or "")})
print(f"{'task':15s} {'31B runs':>8s} {'solved':>6s} {'timeouts':>8s}  v7-uncapped  commit-call/sec in v7")
rec = 0
for t in sorted(T, key=lambda x: -runs[x]["solved"] / runs[x]["n"]):
    r = runs[t]
    v = v7.get(t, {})
    tag = "RECOVERABLE" if r["solved"] else "never solved"
    rec += bool(r["solved"])
    print(f"{t:15s} {r['n']:8d} {r['solved']:6d} {r['timeout']:8d}  {'Y' if v.get('resolved') else '.'} "
          f"{str(v.get('commit_call','-')):>4}c/{int(v.get('commit_s') or 0):4d}s  {tag}")
print(f"\n{rec}/{len(T)} timeout tasks are solved by the 31B in at least one run")
