"""For hard tasks where E4B edits the right file but always fails: show the statement, the gold fix, E4B's most
common losing fix and a 31B winning fix side by side. usage: python Outputs/_hard_fix_compare.py task [task ...]"""
import json
import sqlite3
import sys

sys.path.insert(0, "kb/attemptdb")
from vfs import VFS  # noqa: E402

v = VFS(roots=("Outputs",))
db = sqlite3.connect("kb/attempts.sqlite")
d = json.load(open("Outputs/hard_dossier.json"))


def changed(patch, limit=16):
    return [l for l in patch.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---"))][:limit]


for t in sys.argv[1:]:
    print("=" * 20, t, "| losing families", d[t]["losing_families"], "| top share", d[t]["top_losing_family_share"])
    statement, gold = db.execute("SELECT problem_statement, gold_patch FROM tasks WHERE task = ?", (t,)).fetchone()
    print("STATEMENT:", statement[:600].replace("\n", " "))
    print("-- GOLD (non-test)")
    gold_src = "\n".join(chunk for chunk in gold.split("diff --git") if "test" not in chunk.split("\n", 1)[0])
    print("\n".join(changed(gold_src)))
    print("-- E4B most common losing fix (added lines)")
    print("\n".join(d[t]["top_losing_family"]["added_lines"][:8]))
    row = db.execute("""SELECT patch_path FROM attempts_unique WHERE task = ? AND model LIKE '%31b%' AND resolved = 1
                        AND patch_path IS NOT NULL LIMIT 1""", (t,)).fetchone()
    if row and v.exists(row[0]):
        print("-- 31B winning fix")
        print("\n".join(l for l in changed(v.text(row[0]), 24) if "tmp/" not in l))
    print()
