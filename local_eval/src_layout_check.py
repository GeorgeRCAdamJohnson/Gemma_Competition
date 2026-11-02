"""Did the agent edit the right paths on the 14 src/-layout tasks?

These 14 tasks (13 requests + 1 httpx) are the only ones whose gold patch lives
entirely under src/.  We solve 1/14 there versus 35/115 elsewhere, and both E4B
and 31B are stuck at requests 1/13 -- so this is structural, not capability.
"""
import io
import json
import os
import re

RUN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "kaggle_pkg", "out_e4b")

ids = []
for line in io.open(os.path.join(RUN, "tasks.jsonl"), encoding="utf-8"):
    r = json.loads(line)
    if r["instance_id"].startswith(("requests_", "httpx_")):
        ids.append(r["instance_id"])

print("%d src-layout tasks" % len(ids))
ok = bad = empty = 0
for t in sorted(ids):
    p = os.path.join(RUN, "results", "patches", t + ".patch")
    if not os.path.exists(p) or os.path.getsize(p) == 0:
        print("  %-16s NO PATCH" % t)
        empty += 1
        continue
    files = re.findall(r"^\+\+\+ b/(.+)$",
                       io.open(p, encoding="utf-8", errors="replace").read(), re.M)
    good = bool(files) and all(f.startswith("src/") for f in files)
    if good:
        ok += 1
    else:
        bad += 1
    print("  %-16s %-10s %s" % (t, "SRC-OK" if good else "WRONG-PATH", files[:3]))

print()
print("src-path correct: %d   wrong path: %d   no patch: %d" % (ok, bad, empty))
