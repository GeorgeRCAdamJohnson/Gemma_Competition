# Runs ON the GPU VM: live view of the CURRENT pass (rows finished so far) + driver elapsed time.
import json
import os
import time
from pathlib import Path

pid = Path("/content/ab.pid").read_text().strip()
start = os.stat(f"/proc/{pid}").st_mtime if os.path.exists(f"/proc/{pid}") else None
print("driver alive:", start is not None, "| running for %.1f min" % ((time.time() - start) / 60) if start else "")
for rf in sorted(Path("/content/ab").glob("*/round_*/task_results.jsonl"), key=lambda p: p.stat().st_mtime):
    rows = [json.loads(l) for l in rf.read_text().splitlines() if l.strip()]
    print(f"{rf.parent.parent.name:10s} {rf.parent.name}: {len(rows)}/26 done, solved {sum(bool(r['resolved']) for r in rows)}")
