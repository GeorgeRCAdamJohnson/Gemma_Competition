"""Interim swing-repeats table from TASK_END lines in a kernel log (before the run's files can be collected).
Rate here is the raw `resolved` flag from the log, not the verified definition (which also needs exit 0 and the
routing audit); the final RESULTS_TABLE.md uses the verified definition."""
import sys
from collections import defaultdict
from pathlib import Path

from kaggle_pkg.results_table import pooled_rates
from kaggle_pkg.tool_lora_runner import wilson

path = Path(sys.argv[1])
rows = [line.split() for line in path.read_text().splitlines() if line and not line.startswith("#")]
by = defaultdict(list)
for rnd, task, res, graded, err in rows:
    by[task].append((res == "T", graded == "T", err == "O"))
pooled = pooled_rates(sorted(by), "e4b-swing-task-repeats-r100") or {}
pct = lambda v: f"{100 * v:.0f}%"
out = ["| task | ended | resolved | rate | 95% CI | DB pooled | outside CI | overflow | not graded |",
       "|---|---|---|---|---|---|---|---|---|"]
order = sorted(by, key=lambda t: sum(r for r, _, _ in by[t]) / len(by[t]))
for task in order + ["**total**"]:
    group = [x for t in by for x in by[t]] if task == "**total**" else by[task]
    n, s = len(group), sum(r for r, _, _ in group)
    lo, hi = wilson(s, n)
    ref = pooled.get(task)
    out.append(f"| {task} | {n} | {s} | {pct(s / n)} | {pct(lo)}-{pct(hi)} | "
               + (f"{pct(ref[1])} (n {ref[0]})" if ref else "-") + " | "
               + ("yes" if ref and not lo <= ref[1] <= hi else "") + " | "
               + f"{sum(o for _, _, o in group)} | {sum(not g for _, g, _ in group)} |")
print("\n".join(out))
