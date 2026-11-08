"""Why are 31B timeout runs slow per call? Split each run's wall time into MODEL time (previous tool result -> next
model step) and TOOL time (tool call -> its result), from the per-step timestamps in the presubmit-85 logs."""
import json
import re
import tarfile
from collections import Counter
from pathlib import Path

A = re.compile(r"\x1b\[[0-9;]*m")
TS = re.compile(r"^\s*\[\s*([\d.]+)s\]\s+(.*)$")
D = Path("Outputs/ca5_31b_presubmit_85")
rows = {(r["arm"], r["id"]): r for r in json.load(open(D / "presubmit_ab.json"))["rows"]}


def split(log):
    ev = []
    for line in log.splitlines():
        m = TS.match(line)
        if m:
            ev.append((float(m.group(1)), m.group(2)))
    model = tool = 0.0
    big_tool = []
    last_result = 0.0
    pending_call = None
    for t, s in ev:
        is_result = s.lstrip().startswith(("→", "✓", "❌")) or "→ " in s[:6]
        is_call = bool(re.match(r"\S+\s+(run_command|read_file|edit_file|write_file|get_status|submit_patch|run_skill_script)", s))
        if is_call:
            model += max(0.0, t - last_result)
            pending_call = (t, s)
        elif is_result and pending_call:
            dt = t - pending_call[0]
            tool += dt
            if dt > 20:
                big_tool.append((round(dt), pending_call[1][:70]))
            last_result = t
            pending_call = None
    end = ev[-1][0] if ev else 0
    return model, tool, end, big_tool


stats = {"timeout": [], "solved": []}
slow = Counter()
with tarfile.open(D / "results.tar.gz") as tf:
    for m in tf.getmembers():
        if not (m.name.endswith(".log") and "/logs/" in m.name):
            continue
        arm = "A_ca5" if "/A_ca5/" in m.name else "B_presubmit"
        task = m.name.rsplit("/", 1)[1][:-4]
        r = rows.get((arm, task))
        if not r:
            continue
        kind = "timeout" if "timeout" in (r["err"] or "") else ("solved" if r["resolved"] else None)
        if not kind:
            continue
        log = A.sub("", tf.extractfile(m).read().decode("utf-8", "replace"))
        mo, to, end, big = split(log)
        stats[kind].append((task, r["calls"], mo, to, end, big))
        if kind == "timeout":
            for dt, s in big:
                slow[re.sub(r"\s+", " ", s)[:55]] += 1
for k, v in stats.items():
    n = len(v)
    mo = sorted(x[2] for x in v); to = sorted(x[3] for x in v)
    print(f"== {k}: n={n} | median MODEL time {mo[n//2]:.0f}s | median TOOL time {to[n//2]:.0f}s | "
          f"median calls {sorted(x[1] or 0 for x in v)[n//2]} | model s/call {sum(mo)/max(1,sum((x[1] or 1) for x in v)):.1f}")
print("\nper timeout run: task, calls, model s, tool s, tool calls > 20 s")
for task, calls, mo, to, end, big in sorted(stats["timeout"], key=lambda x: -x[3]):
    print(f"   {task:15s} calls {calls:>3} model {mo:5.0f}s tool {to:5.0f}s | {big[:3]}")
print("\nslowest tool-call kinds in timeout runs:", slow.most_common(6))
