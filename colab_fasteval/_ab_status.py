# Runs ON the GPU VM (any kernel): A/B progress table + last driver log lines.
import json
from collections import defaultdict
from pathlib import Path

p = Path("/content/ab/progress.json")
if p.exists():
    passes = json.loads(p.read_text())["passes"]
    by = defaultdict(list)
    for x in passes:
        by[x["arm"]].append(x)
    for arm, xs in sorted(by.items()):
        s = [x["solved"] for x in xs]
        print(f"{arm:10s} passes {len(xs):2d} | solved {s} | mean {sum(s)/len(s):5.2f} | min/pass "
              f"{sum(x['seconds'] for x in xs)/len(xs)/60:5.1f}")
else:
    print("no progress yet")
log = Path("/content/ab.log")
if log.exists():
    print("".join([l for l in log.read_text(errors="replace").splitlines(keepends=True) if l.startswith("[")][-6:]))
