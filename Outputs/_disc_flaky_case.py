# Inspect the one identical patch graded both pass and fail (fastapi_14873): where and how did the failing grade happen?
import hashlib
import re
import sqlite3
import sys

sys.path.insert(0, "kb/attemptdb")
from vfs import VFS  # noqa: E402

db = sqlite3.connect("kb/attempts.sqlite")
vfs = VFS(roots=("Outputs",))
norm = lambda p: "\n".join(l.rstrip() for l in p.splitlines() if not l.startswith(("index ", "diff --git"))).strip()
rows = db.execute("""SELECT exp, arm, round, resolved, patch_path, test_output_path, test_exit_code, duration_s FROM attempts_unique
                     WHERE task = 'fastapi_14873' AND patch_path IS NOT NULL AND error_class IS NULL AND test_output_chars > 0""").fetchall()
groups = {}
for r in rows:
    if vfs.exists(r[4]):
        groups.setdefault(hashlib.sha1(norm(vfs.text(r[4])).encode()).hexdigest()[:12], []).append(r)
for h, rs in groups.items():
    if 0 < sum(x[3] for x in rs) < len(rs):
        print(f"patch {h}: {sum(x[3] for x in rs)}/{len(rs)} pass")
        for x in rs:
            if not x[3]:
                print("  FAILING grade:", x[:3], "exit", x[6], "dur", x[7])
                txt = vfs.text(x[5])
                fails = re.findall(r"^(?:FAILED|ERROR) .*$", txt, re.M)
                print("  failing tests:", fails[:6])
                print("  tail:", txt[-700:].replace("\n", " | "))
        print("  passing examples:", [x[:3] for x in rs if x[3]][:4])
