"""Per-turn view of model time in 31B timeout vs solved runs: seconds per model turn and the text size the log
records for that turn (the 💭 chars field = visible text + thought summary), plus what tool the turn emitted."""
import json
import re
import tarfile
import statistics as st
from collections import Counter
from pathlib import Path

A = re.compile(r"\x1b\[[0-9;]*m")
TS = re.compile(r"^\s*\[\s*([\d.]+)s\]\s+(.*)$")
D = Path("Outputs/ca5_31b_presubmit_85")
rows = {(r["arm"], r["id"]): r for r in json.load(open(D / "presubmit_ab.json"))["rows"]}
turns = {"timeout": [], "solved": []}
tool_after_slow = Counter()
with tarfile.open(D / "results.tar.gz") as tf:
    for m in tf.getmembers():
        if not (m.name.endswith(".log") and "/logs/" in m.name):
            continue
        arm = "A_ca5" if "/A_ca5/" in m.name else "B_presubmit"
        r = rows.get((arm, m.name.rsplit("/", 1)[1][:-4]))
        if not r:
            continue
        kind = "timeout" if "timeout" in (r["err"] or "") else ("solved" if r["resolved"] else None)
        if not kind:
            continue
        ev = [(float(x.group(1)), x.group(2)) for x in (TS.match(l) for l in A.sub("", tf.extractfile(m).read().decode("utf-8", "replace")).splitlines()) if x]
        last = 0.0
        for i, (t, s) in enumerate(ev):
            mt = re.search(r"💭 \((\d+) chars\)", s)
            if mt:
                dt = t - last
                nxt = next((ev[j][1] for j in range(i + 1, min(i + 3, len(ev))) if not ev[j][1].lstrip().startswith(("→", "✓", "❌"))), "")
                tool = re.search(r"(run_command|read_file|edit_file|write_file|get_status|submit_patch|run_skill_script)", nxt)
                turns[kind].append((dt, int(mt.group(1)), tool.group(1) if tool else "none"))
                if kind == "timeout" and dt > 60:
                    tool_after_slow[tool.group(1) if tool else "none"] += 1
            if s.lstrip().startswith(("→", "✓", "❌")):
                last = t
for k, v in turns.items():
    d = sorted(x[0] for x in v); c = sorted(x[1] for x in v)
    print(f"== {k}: {len(v)} model turns | sec/turn median {d[len(d)//2]:.1f} p90 {d[int(.9*len(d))]:.1f} max {d[-1]:.0f} | "
          f"turns > 60 s: {sum(x > 60 for x in d)} ({100*sum(x > 60 for x in d)/len(d):.0f}%) | text chars median {c[len(c)//2]} p90 {c[int(.9*len(c))]}")
    slow = [x for x in v if x[0] > 60]
    if slow:
        print(f"   slow turns: median chars {st.median(x[1] for x in slow):.0f} | emitted tool: {Counter(x[2] for x in slow).most_common(5)}")
    fast = [x for x in v if x[0] <= 60]
    print(f"   chars vs sec correlation proxy: mean chars slow {st.mean(x[1] for x in slow) if slow else 0:.0f} vs fast {st.mean(x[1] for x in fast):.0f}")
