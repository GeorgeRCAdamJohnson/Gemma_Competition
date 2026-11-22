"""Print an arm's full file-change list vs pack 1 and its task-adjusted mechanism row.
usage: python Outputs/_show_changes.py <exp> <arm>"""
import json
import sqlite3
import sys

exp, arm = sys.argv[1], sys.argv[2]
db = sqlite3.connect("kb/attempts.sqlite")
row = db.execute("SELECT changed_vs_pack1, bundle_sha12 FROM arm_catalog WHERE exp = ? AND arm = ?", (exp, arm)).fetchone()
print("bundle", row[1] if row else None)
for item in json.loads(row[0]) if row and row[0] else []:
    print("  ", item)
for r in json.load(open("Outputs/arm_mechanisms.json")):
    if r["exp"] == exp and r["arm"] == arm:
        print({k: (round(v[0] * (1 if k == "calls" else 100), 1), round(v[1], 1)) if isinstance(v, list) else v
               for k, v in r.items() if k not in ("changed",)})
