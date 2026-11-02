"""Compare reasoning volume vs action rate across 4077 arms:
does more prompt text -> more thinking -> fewer edits -> timeout death?"""
import json
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
TASK = "rich_4077"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
ARMS = ["off12", "off4077t", "ddv4077", "ddv2_4077", "ddv3_4077"]


def stats(arm):
    reps = sorted((RIG / "m1_batch_multi" / arm).glob("r*"), key=lambda p: int(p.name[1:]))
    rows = []
    for d in reps:
        tr = d / "traces" / f"trace_{TASK}.json"
        if not tr.exists():
            continue
        j = json.loads(ANSI.sub("", tr.read_text(encoding="utf-8")))
        fm = j.get("final_metrics") or {}
        steps = [s for s in j["steps"] if s.get("source") == "agent"]
        think_chars = sum(len((s.get("message") or "")) for s in steps)
        calls = sum(len(s.get("tool_calls") or []) for s in steps)
        edits = sum(1 for s in steps for tc in (s.get("tool_calls") or [])
                    if tc.get("function_name") == "edit_file")
        res = None
        rf = d / "task_results.jsonl"
        if rf.exists():
            for line in open(rf, encoding="utf-8"):
                if line.strip():
                    r = json.loads(line)
                    if r.get("instance_id") == TASK:
                        res = bool(r.get("resolved"))
        rows.append({
            "rep": d.name,
            "comp_tokens": fm.get("total_completion_tokens") or 0,
            "steps": len(steps),
            "calls": calls,
            "edits": edits,
            "think_chars": think_chars,
            "resolved": res,
        })
    return rows


def main():
    print(f"{'arm':<12} {'n':>3} {'solved':>7} {'comp_tok':>9} {'think_chars':>12} {'steps':>6} {'calls':>6} {'edits':>6} {'ed/rep':>7}")
    print("-" * 90)
    for arm in ARMS:
        rows = stats(arm)
        if not rows:
            print(f"{arm:<12} (no data)")
            continue
        n = len(rows)
        solved = sum(1 for r in rows if r["resolved"])
        f = lambda k: sum(r[k] for r in rows) / n
        print(f"{arm:<12} {n:>3} {solved:>3}/{n:<3} {f('comp_tokens'):>9.0f} {f('think_chars'):>12.0f} "
              f"{f('steps'):>6.1f} {f('calls'):>6.1f} {f('edits'):>6.1f} {f('edits'):>7.2f}")

    # per-rep detail for ddv2: did thinking crowd out acting?
    print("\nDDV2 per-rep (thinking chars vs edits vs outcome):")
    for r in stats("ddv2_4077"):
        print(f"  {r['rep']:>4} think={r['think_chars']:>6} calls={r['calls']:>3} edits={r['edits']:>2} "
              f"comp_tok={r['comp_tokens']:>6} resolved={r['resolved']}")


if __name__ == "__main__":
    main()
