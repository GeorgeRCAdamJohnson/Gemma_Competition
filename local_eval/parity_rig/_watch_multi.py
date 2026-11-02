"""Multi-dir watchdog for the tuning panel: polls m1_batch_multi/{v4,v5,v6} every 15s.
Same preregistered mechanism flags as _watch_batch (per arm): multi-dispatch, empties,
cap28, live resolved."""
import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
ROOT = RIG / "m1_batch_multi"
ARMS = ["v4", "v5", "v6"]
REPS = 2
TICK = 15


def arm_stats(arm):
    k = n = cap = disp = multi = empt = 0
    per_trace_multi = 0
    for rep in range(REPS):
        base = ROOT / arm / f"r{rep}"
        f = base / "task_results.jsonl"
        if f.exists():
            for l in open(f, encoding="utf-8"):
                if l.strip():
                    r = json.loads(l)
                    n += 1
                    k += int(bool(r.get("resolved")))
                    if (r.get("tool_calls") or 0) >= 28:
                        cap += 1
        td = base / "traces"
        if td.exists():
            for tr in td.glob("trace_*.json"):
                txt = tr.read_text(encoding="utf-8", errors="replace")
                c = len(re.findall(r'"function_name":\s*"(code_locator|logic_analyst)"', txt))
                if c:
                    disp += 1
                    if c > 1:
                        multi += 1
        ld = base / "logs"
        if ld.exists():
            for lg in ld.glob("*.log"):
                empt += lg.read_text(encoding="utf-8", errors="replace").count('"raw": ""')
    return k, n, cap, disp, multi, empt


def main():
    print("[watch-multi] arms:", ARMS, "rules: stop if multi>=3/14 tasks or empties>0", flush=True)
    last = None
    while True:
        lines = []
        stop = []
        total_n = 0
        for a in ARMS:
            k, n, cap, disp, multi, empt = arm_stats(a)
            total_n += n
            flag = ""
            if n >= 7:
                if multi >= 3:
                    flag = "  *** STOP multi>=3 ***"
                    stop.append(a)
                elif empt > 0:
                    flag = "  *** STOP empties>0 ***"
                    stop.append(a)
            lines.append(f"{a}: {k}/{n} res cap28={cap} disp_tasks={disp} multi={multi} empties={empt}{flag}")
        cur = "\n".join(lines)
        if cur != last:
            print(f"\n[{time.strftime('%H:%M:%S')}] " + cur, flush=True)
            last = cur
        if total_n >= len(ARMS) * REPS * 7:
            print("\n[watch-multi] COMPLETE", flush=True)
            break
        if stop:
            print(f"[watch-multi] STOP FLAGS on: {stop} - decide whether to kill remaining blocks", flush=True)
        time.sleep(TICK)


if __name__ == "__main__":
    main()
