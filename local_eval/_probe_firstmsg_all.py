"""CPU-only: byte-compare my generated Kaggle first user message against the REAL one in every ATIF trace
(different tasks => different base commits and trees). Only traces that used the 28-call/8-minute template count."""
import glob, json, re, sys
from pathlib import Path

import run_local as R

HERE = Path(__file__).resolve().parent
R.set_tools_mode("kaggle")
R.set_repo("rich")
R.REPO = (HERE / "repos" / "rich_v").resolve()

seen = {}
rows = []
for p in sorted(glob.glob(str(HERE.parent / "**" / "trace_rich_*.json"), recursive=True)):
    m = re.search(r"trace_(rich_\d+)\.json$", p)
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        u = d["steps"][1]["message"]
    except Exception:
        continue
    if "Tool calls allowance: 28 calls" not in u:
        continue
    tid = m.group(1)
    key = (tid, u)
    if key in seen:
        continue
    seen[key] = p
    rows.append((tid, p, u))

print("distinct (task, message) pairs with the 28-call template:", len(rows))
ok = bad = 0
last_commit = None
for tid, p, u in rows:
    try:
        task = R.load_task(tid)
    except Exception as e:
        print("skip", tid, e); continue
    R.reset_repo(task["base_commit"])
    mine = R.kaggle_first_message(task)
    if mine == u:
        ok += 1
    else:
        bad += 1
        n = min(len(mine), len(u))
        i = next((k for k in range(n) if mine[k] != u[k]), n)
        print("MISMATCH", tid, Path(p).parts[-5:-3], "len real/mine", len(u), len(mine), "first diff", i)
        print("   REAL:", repr(u[max(0, i - 100): i + 160]))
        print("   MINE:", repr(mine[max(0, i - 100): i + 160]))
print("identical:", ok, "mismatched:", bad)
R.reset_repo(R.load_task("rich_4079")["base_commit"])
