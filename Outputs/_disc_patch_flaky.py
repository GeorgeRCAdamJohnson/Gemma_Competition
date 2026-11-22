"""Free flakiness check from recorded data: group graded attempts by the exact patch text (normalised: no index lines,
no trailing whitespace) per task. A patch graded both resolved and unresolved = direct evidence the grading flips for
an identical fix. Also: how many distinct patches each swing task has, and the solve rate of its most common patch."""
import hashlib
import re
import sqlite3
import sys
from collections import defaultdict

sys.path.insert(0, "kb/attemptdb")
from vfs import VFS  # noqa: E402

db = sqlite3.connect("kb/attempts.sqlite")
vfs = VFS(roots=("Outputs",))


def norm(p):
    lines = [l.rstrip() for l in p.splitlines() if not l.startswith(("index ", "diff --git"))]
    return "\n".join(lines).strip()


rows = db.execute("""SELECT task, resolved, verified, patch_path, error_class, test_output_chars FROM attempts_unique
                     WHERE patch_path IS NOT NULL AND resolved IS NOT NULL AND model NOT LIKE '%31b%'""").fetchall()
groups = defaultdict(lambda: defaultdict(list))
for task, res, ver, pp, ec, toc in rows:
    if not vfs.exists(pp):
        continue
    p = norm(vfs.text(pp))
    if not p:
        continue
    # only attempts whose grade is real: no harness error and test output present
    if ec is not None or not toc:
        continue
    groups[task][hashlib.sha1(p.encode()).hexdigest()[:12]].append(res)
swing = [t for (t,) in db.execute("SELECT task FROM task_rates WHERE model NOT LIKE '%31b%' AND n >= 40 AND rate BETWEEN 0.1 AND 0.9")]
print(f"tasks with graded, error-free patches: {len(groups)}")
mixed_total = 0
print("\ntask            distinct patches  repeated patches  MIXED (same patch both pass and fail)  top patch: n, pass rate")
for t in sorted(groups, key=lambda t: -sum(len(v) for v in groups[t].values())):
    g = groups[t]
    rep = {h: v for h, v in g.items() if len(v) >= 2}
    mixed = {h: v for h, v in rep.items() if 0 < sum(v) < len(v)}
    mixed_total += len(mixed)
    top = max(g.values(), key=len)
    if t in swing or mixed:
        mx = ", ".join(f"{sum(v)}/{len(v)}" for v in sorted(mixed.values(), key=len, reverse=True)[:4])
        print(f"  {t:15s} {len(g):6d}          {len(rep):6d}            {len(mixed):3d}  [{mx}]"
              f"{'':6s} n {len(top):3d} pass {sum(top) / len(top):.2f}{'   (swing)' if t in swing else ''}")
print(f"\nidentical patches graded both pass and fail: {mixed_total}")
