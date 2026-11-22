"""Breakthrough analysis 5: are E4B's right-file failures INCOMPLETE fixes? Compare the agent's saved patch with the gold
patch at hunk level: a gold source hunk counts as covered if the agent patch changes the same file within +-15 lines of
it (base-file line numbers). Solve rate by coverage, and how often failures cover only some of the gold hunks."""
import re
import sqlite3
import sys
from collections import defaultdict

sys.path.insert(0, "kb/attemptdb")
from vfs import VFS  # noqa: E402

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")


def hunks(patch):
    out, cur = [], None
    for l in patch.splitlines():
        if l.startswith("+++ b/"):
            cur = l[6:].strip()
        elif l.startswith("--- a/"):
            cur = l[6:].strip()
        elif (m := HUNK.match(l)) and cur and "test" not in cur and cur.endswith(".py"):
            s, n = int(m.group(1)), int(m.group(2) or 1)
            out.append((cur, s, s + max(n, 1)))
    return out


db = sqlite3.connect("kb/attempts.sqlite")
vfs = VFS(roots=("Outputs",))
gold = {t: hunks(p) for t, p in db.execute("SELECT task, gold_patch FROM tasks")}
rows = db.execute("""SELECT a.task, a.resolved, a.patch_path FROM attempts_unique a
                     WHERE a.model NOT LIKE '%31b%' AND a.resolved IS NOT NULL AND a.patch_path IS NOT NULL""").fetchall()
by = defaultdict(list)
multi = defaultdict(list)
for task, res, pp in rows:
    g = gold.get(task) or []
    if not g or not vfs.exists(pp):
        continue
    a = hunks(vfs.text(pp))
    if not a:
        continue
    cov = sum(any(f == gf and s <= ge + 15 and e >= gs - 15 for f, s, e in a) for gf, gs, ge in g)
    frac = cov / len(g)
    k = "none" if cov == 0 else "all" if cov == len(g) else "some"
    by[k].append(res)
    if len(g) >= 2:
        multi[(k, len(g) >= 2)].append(res)
print("E4B attempts with a saved patch, by coverage of the gold source hunks (+-15 lines)")
for k in ("none", "some", "all"):
    v = by[k]
    print(f"  covers {k:4s}: n {len(v):5d}  solve {sum(v) / len(v):6.1%}")
print("\nonly tasks whose gold patch has >= 2 source hunks:")
for k in ("none", "some", "all"):
    v = multi[(k, True)]
    if v:
        print(f"  covers {k:4s}: n {len(v):5d}  solve {sum(v) / len(v):6.1%}")
fail_some = len([r for r in multi[("some", True)] if not r])
fail_all = len([r for r in multi[("all", True)] if not r])
print(f"\nfailed multi-hunk attempts that covered SOME but not all gold hunks: {fail_some} "
      f"(vs {fail_all} that covered all and still failed)")
