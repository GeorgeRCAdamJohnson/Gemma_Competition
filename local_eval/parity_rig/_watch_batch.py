"""Live watchdog for a router_v3 batch: polls disk every 15s and prints mechanism metrics
as rows/traces land, with preregistered on-the-fly flags.

DECISION RULES (fixed before the run, 2026-10-27):
- STOP flags are MECHANISM-based (near-deterministic), never score-based:
    after >=7 rows:  multi-dispatch tasks >= 3   -> STOP
                     empty specialist returns > 0 -> STOP
                     avg locator calls/task > 1.5 -> FLAG (warn only; stop at rep1 if still >1.5)
- SCORE is display-only until all 21 rows exist (7-task reps swing +-2 on binomial noise).
Usage: python _watch_batch.py [batch_dir]   (default m1_batch_v3/router_v3)
"""
import json
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
D = Path(sys.argv[1]) if len(sys.argv) > 1 else RIG / "m1_batch_v3" / "router_v3"
REPS = 3
TICK = 15


def read_rows(rep):
    f = D / f"r{rep}" / "task_results.jsonl"
    if not f.exists():
        return []
    out = []
    for l in open(f, encoding="utf-8"):
        if l.strip():
            out.append(json.loads(l))
    return out


def trace_stats(rep):
    td = D / f"r{rep}" / "traces"
    disp_tasks = multi = loc = 0
    if td.exists():
        for tr in td.glob("trace_*.json"):
            txt = tr.read_text(encoding="utf-8", errors="replace")
            c = len(re.findall(r'"function_name":\s*"code_locator"', txt))
            c += len(re.findall(r'"function_name":\s*"logic_analyst"', txt))
            if c:
                disp_tasks += 1
                loc += c
                if c > 1:
                    multi += 1
    return disp_tasks, multi, loc


def empty_returns(rep):
    ld = D / f"r{rep}" / "logs"
    e = 0
    if ld.exists():
        for lg in ld.glob("*.log"):
            t = lg.read_text(encoding="utf-8", errors="replace")
            e += t.count('"raw": ""') + t.count("'raw': ''")
    return e


def main():
    print(f"[watch] dir={D}  rules: STOP if multi>=3 tasks | empties>0 | warn avg_disp>1.5", flush=True)
    seen_rows = 0
    while True:
        total_rows = 0; k = 0; caps = 0
        disp_t = multi_t = loc = empties = 0
        blocks = []
        for r in range(REPS):
            rows = read_rows(r)
            total_rows += len(rows)
            rk = sum(int(bool(x.get("resolved"))) for x in rows)
            rcap = sum(1 for x in rows if (x.get("tool_calls") or 0) >= 28)
            k += rk; caps += rcap
            d, m, lc = trace_stats(r)
            disp_t += d; multi_t += m; loc += lc
            empties += empty_returns(r)
            if rows:
                blocks.append(f"r{r}: {len(rows)}/7 res={rk} cap28={rcap} disp={d} multi={m}")
        avg_disp = (loc / disp_t) if disp_t else 0.0
        flag = ""
        if total_rows >= 7:
            if multi_t >= 3:
                flag = "  *** STOP FLAG: multi-dispatch >= 3 tasks ***"
            elif empties > 0:
                flag = "  *** STOP FLAG: empty specialist return reappeared ***"
            elif avg_disp > 1.5:
                flag = f"  ** warn: avg dispatch {avg_disp:.2f}/task > 1.5 (stop at rep1 if persists) **"
        stamp = time.strftime("%H:%M:%S")
        if total_rows != seen_rows or flag:
            print(f"\n[{stamp}] rows {total_rows}/21  resolved {k}  cap28 {caps}  "
                  f"dispatch_tasks {disp_t}  multi {multi_t}  empties {empties}  "
                  f"avg_disp {avg_disp:.2f}{flag}", flush=True)
            for b in blocks:
                print("   ", b, flush=True)
            seen_rows = total_rows
        if total_rows >= REPS * 7:
            print(f"\n[{stamp}] COMPLETE: resolved {k}/21", flush=True)
            break
        time.sleep(TICK)


if __name__ == "__main__":
    main()
