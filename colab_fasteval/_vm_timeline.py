# Runs ON a GPU VM: wall-clock timeline of the A/B work here (driver start, last log line, passes done, now).
import json
import os
import time
from pathlib import Path

now = time.time()
print("now", time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(now)))
for name in ("ab", "ab2", "ab3"):
    log, pidf, prog = Path(f"/content/{name}.log"), Path(f"/content/{name}.pid"), Path(f"/content/{name}/progress.json")
    if not log.exists():
        continue
    pid = pidf.read_text().strip() if pidf.exists() else None
    alive = bool(pid) and os.path.exists(f"/proc/{pid}")
    started = os.stat(f"/proc/{pid}").st_mtime if alive else None
    n = len(json.loads(prog.read_text())["passes"]) if prog.exists() else 0
    lines = [l for l in log.read_text(errors="replace").splitlines() if l.startswith("[")]
    print(f"{name}: alive={alive} started={time.strftime('%H:%M', time.gmtime(started)) if started else '-'} "
          f"passes={n} | log last write {(now - log.stat().st_mtime) / 60:.0f} min ago | last: {lines[-1][:110] if lines else ''}")
