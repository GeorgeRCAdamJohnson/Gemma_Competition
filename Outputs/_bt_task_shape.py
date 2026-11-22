"""Calibration for corpus ranking: E4B solve rate by the SHAPE of the gold fix (runtime source files, hunks, changed
lines, test added) over the 129 public tasks, attempt-weighted and task-level. Uses attempts_unique (E4B only)."""
import re
import sqlite3
import statistics as st
from collections import defaultdict

db = sqlite3.connect("kb/attempts.sqlite")
NONRT = re.compile(r"^(docs_src|docs|scripts)/")
shape = {}
for task, patch in db.execute("SELECT task, gold_patch FROM tasks"):
    files, hunks, lines, cur = set(), 0, 0, None
    for l in patch.splitlines():
        if l.startswith("+++ b/"):
            cur = l[6:].strip()
            ok = cur.endswith(".py") and "test" not in cur and not NONRT.match(cur)
            if ok:
                files.add(cur)
        elif l.startswith("@@") and cur in files:
            hunks += 1
        elif l[:1] in "+-" and not l.startswith(("+++", "---")) and cur in files:
            lines += 1
    shape[task] = (len(files), hunks, lines)
rate = {t: (r, n) for t, r, n in db.execute("""SELECT task, AVG(resolved), COUNT(*) FROM attempts_unique
        WHERE model NOT LIKE '%31b%' AND resolved IS NOT NULL GROUP BY task""")}


def table(name, key):
    g = defaultdict(list)
    for t, s in shape.items():
        if t in rate:
            g[key(s)].append(t)
    print(f"\n{name}:  bucket | tasks | ever solved | mean task solve rate | attempts")
    for b in sorted(g):
        ts = g[b]
        rs = [rate[t][0] for t in ts]
        print(f"  {b:>14s} | {len(ts):4d} | {sum(r > 0 for r in rs):4d} | {st.mean(rs):6.1%} | {sum(rate[t][1] for t in ts):6d}")


table("runtime source files", lambda s: f"{min(s[0], 3)}{'+' if s[0] >= 3 else ''} files")
table("runtime hunks", lambda s: "1 hunk" if s[1] == 1 else "2-3 hunks" if s[1] <= 3 else "4+ hunks")
table("changed runtime lines", lambda s: "<=10" if s[2] <= 10 else "11-40" if s[2] <= 40 else "41+")
table("single file, multi-hunk", lambda s: "1 file 1 hunk" if s[0] == 1 and s[1] == 1 else
      "1 file 2+ hunks" if s[0] == 1 else "2+ files")
