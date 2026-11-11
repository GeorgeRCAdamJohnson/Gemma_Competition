# Runs ON the vote VM: is the V_vote driver alive and what has it done?
import json
import os
from pathlib import Path

pidf = Path("/content/ab4.pid")
pid = pidf.read_text().strip() if pidf.exists() else None
print("pid", pid, "alive", bool(pid) and os.path.exists(f"/proc/{pid}"))
log = Path("/content/ab4.log")
print("log:", "".join(log.read_text(errors="replace").splitlines(keepends=True)[-12:]) if log.exists() else "missing")
p = Path("/content/ab4/progress.json")
if p.exists():
    for x in json.loads(p.read_text())["passes"]:
        print(x["round"], x["arm"], x["solved"], round(x["seconds"] / 60, 1), "min")
for rf in Path("/content/ab4").glob("*/round_*/task_results.jsonl"):
    rows = [json.loads(l) for l in rf.read_text().splitlines() if l.strip()]
    print(rf.parent.parent.name, rf.parent.name, f"{len(rows)}/26 done, solved {sum(r['resolved'] for r in rows)}")
