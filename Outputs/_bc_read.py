"""B+C check read: the 6 recoverable vs history, regressions on the 27 always-solved, timing."""
import json
from collections import defaultdict

ab = json.load(open("Outputs/ca5_31b_bc_check/presubmit_ab.json"))
rows = [r for r in ab["rows"] if r["chunk_complete"]]
alw = json.load(open("Outputs/_31b_always.json"))["always"]
rec6 = ["rich_3480", "fastapi_14616", "fastapi_14851", "rich_3506", "fastapi_14419", "rich_3521"]
by = {r["id"]: r for r in rows}
print(f"complete rows {len(rows)}/33 | solved {sum(r['resolved'] for r in rows)}")
r6 = [by[t] for t in rec6 if t in by]
print(f"recoverable 6: {sum(r['resolved'] for r in r6)}/{len(r6)} | " +
      ", ".join(f"{r['id']} {'Y' if r['resolved'] else '.'} {round(r['dur'] or 0)}s {(r['err'] or '')[:25]}" for r in r6))
lost = [by[t] for t in alw if t in by and t not in rec6 and not by[t]["resolved"]]
n_alw = sum(1 for t in alw if t in by and t not in rec6)
print(f"always-solved: {n_alw - len(lost)}/{n_alw} kept | LOST: " +
      (", ".join(f"{r['id']} ({round(r['dur'] or 0)}s, calls {r['calls']}, err={(r['err'] or 'none')[:40]})" for r in lost) or "none"))
d = sorted((r["dur"] or 0) for r in rows)
late = [r for r in rows if r["resolved"] and (r["dur"] or 0) > 480]
print(f"duration median {d[len(d)//2]:.0f}s, max {d[-1]:.0f}s | solves after 8 min: {len(late)} -> {[(r['id'], round(r['dur'])) for r in late]}")
print(f"session timeouts: {sum('timeout' in (r['err'] or '') for r in rows)} | overflow: {sum('ContextWindow' in (r['err'] or '') for r in rows)}")
# historical durations of the same 33 tasks at 28/8, 4 in flight (presubmit-85 arm A) -> runtime delta
pre = {r["id"]: r for r in json.load(open("Outputs/ca5_31b_presubmit_85/presubmit_ab.json"))["rows"] if r["arm"] == "A_ca5"}
common = [t for t in by if t in pre]
dbc = sum(by[t]["dur"] or 0 for t in common); d28 = sum(pre[t]["dur"] or 0 for t in common)
print(f"task-seconds on the same {len(common)} tasks: B+C {dbc/3600:.2f} h vs 28/8 (presubmit-85 A) {d28/3600:.2f} h "
      f"-> {100*(dbc-d28)/d28:+.0f}%")
