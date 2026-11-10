# Runs ON the GPU VM: start the A/B driver detached (own session, survives kernel/connection loss) and return.
import os
import subprocess
from pathlib import Path

N_ROUNDS = 10
DEADLINE_H = 20
pidf = Path("/content/ab.pid")
if pidf.exists() and os.path.exists(f"/proc/{pidf.read_text().strip()}"):
    print("driver already running, pid", pidf.read_text().strip())
else:
    p = subprocess.Popen(["/content/venv/bin/python", "/content/work/gpu_ab_run.py", str(N_ROUNDS), str(DEADLINE_H)],
                         cwd="/content/work", stdout=open("/content/ab.log", "a"), stderr=subprocess.STDOUT,
                         env=dict(os.environ, AB_TAG="e4b_ab_20261110"), start_new_session=True)
    pidf.write_text(str(p.pid))
    print("driver started, pid", p.pid)
