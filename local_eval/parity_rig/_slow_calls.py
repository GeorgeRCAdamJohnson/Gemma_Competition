"""Find what consumes the session wall-clock in a 4077 arm: tool calls ranked by elapsed_s."""
import json
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
ARM = os.environ.get("M1_ARM", "ddv2_4077")
TASK = "rich_4077"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def main():
    reps = sorted((RIG / "m1_batch_multi" / ARM).glob("r*"), key=lambda p: int(p.name[1:]))
    slow = []
    totals = []
    for d in reps:
        tr = d / "traces" / f"trace_{TASK}.json"
        if not tr.exists():
            continue
        j = json.loads(ANSI.sub("", tr.read_text(encoding="utf-8")))
        calls = []
        for s in j["steps"]:
            for tc in (s.get("tool_calls") or []):
                el = float((tc.get("extra") or {}).get("elapsed_s") or 0)
                a = tc.get("arguments") or {}
                if isinstance(a, str):
                    try:
                        a = json.loads(a)
                    except Exception:
                        a = {}
                detail = a.get("command") or a.get("filepath") or a.get("path") or ""
                calls.append((el, tc.get("function_name"), str(detail)[:170]))
        calls.sort(key=lambda x: x[0])
        prev = 0.0
        rep_max = 0.0
        for el, fn, detail in calls:
            delta = el - prev
            prev = el
            rep_max = max(rep_max, el)
            if delta >= 25:
                slow.append((delta, d.name, fn, f"[t={el:.0f}s] {detail}"))
        totals.append((d.name, rep_max, len(calls)))

    print("=== tool-call wall time per rep ===")
    for name, last, ncalls in totals:
        print(f"  {name}: session ended at {last:.0f}s, {ncalls} calls")

    print(f"\n=== calls >= 25s ({len(slow)} total) ===")
    for el, rep, fn, detail in sorted(slow, reverse=True)[:20]:
        print(f"  {el:7.1f}s  [{rep}] {fn}: {detail}")


if __name__ == "__main__":
    main()

