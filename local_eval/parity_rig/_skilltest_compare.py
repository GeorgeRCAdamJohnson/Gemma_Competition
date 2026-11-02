"""Compare gated replicates vs the 7 existing ungated E4B ca5 runs (5 local + 2 Kaggle) per task.
Also reports, per gated run, the gate verdict sequence and whether the final submission came after an ACCEPTED."""
import json
import sys
from pathlib import Path

RIG = Path(__file__).resolve().parent
G = RIG.parents[1]
BASE_RUNS = [RIG / "m1_full129" / "ca5", RIG / "m1_full129" / "ca5_v2", RIG / "m1_capped" / "agent_ctrl_e4b_r0",
             RIG / "m1_capped" / "agent_ctrl_e4b_r1", RIG / "m1_faithful" / "agent_ctrl_e4b_r0",
             G / "kaggle_pkg" / "out_e4b" / "results", G / "kaggle_pkg" / "out_e4b_r2" / "results"]
GATED = [RIG / "m1_skilltest" / n for n in sys.argv[1:]]


def res(d):
    f = d / "task_results.all.jsonl"
    if not f.exists():
        f = d / "task_results.jsonl"
    return {json.loads(l)["instance_id"]: json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()}


base = [res(d) for d in BASE_RUNS]
gated = [(d.name, res(d)) for d in GATED]
tasks = list(gated[0][1].keys())
tb = tg = 0
nb = ng = 0
print(f"{'task':<14} {'ungated':>9} {'gated':>7}   gate verdicts per gated run")
for t in tasks:
    b = sum(1 for r in base if r.get(t, {}).get("resolved"))
    g = sum(1 for _, r in gated if r.get(t, {}).get("resolved"))
    tb += b; nb += len(base); tg += g; ng += len(gated)
    verdicts = []
    for name, r in gated:
        tr = RIG / "m1_skilltest" / name / "traces" / f"trace_{t}.json"
        v = []
        if tr.exists():
            for s in json.loads(tr.read_text(encoding="utf-8")).get("steps", []):
                for c in s.get("tool_calls") or []:
                    if c.get("function_name") == "run_skill_script":
                        try:
                            out = json.loads(s["observation"]["content"]).get("stdout", "")
                        except Exception:
                            out = "?"
                        v.append("A" if out.startswith("ACCEPTED") else "R" if out.startswith("REJECTED") else "?")
                    elif c.get("function_name") == "submit_patch":
                        v.append("S")
        rr = r.get(t, {})
        v.append("=" + ("WIN" if rr.get("resolved") else "miss"))
        v.append(f"({rr.get('duration_seconds')}s,{rr.get('tool_calls')}c{', ERR' if rr.get('error') else ''})")
        verdicts.append("".join(v[:-2]) + v[-2] + v[-1])
    print(f"{t:<14} {b:>4}/{len(base):<4} {g:>3}/{len(gated):<3}   " + "  ".join(verdicts))
print(f"{'TOTAL':<14} {tb:>4}/{nb:<4} {tg:>3}/{ng:<3}   rate ungated {tb / nb:.2f} vs gated {tg / ng:.2f}")
print("legend: A=gate ACCEPTED, R=gate REJECTED, S=submit_patch")
