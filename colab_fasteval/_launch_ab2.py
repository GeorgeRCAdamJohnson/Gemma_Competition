# Runs ON the GPU VM: start the batch-2 driver detached (own session) and return. Fixed driver: exits after the last pass.
import os
import subprocess
from pathlib import Path

ARMS, OUT, TAG, N_ROUNDS, DEADLINE_H = "arms2", "/content/ab2", "e4b_ab2_20261111", 8, 11
assert "ALL_DONE" in Path("/content/work/gpu_ab_run.py").read_text(), "driver is not the fixed version"
pidf = Path("/content/ab2.pid")
if pidf.exists() and os.path.exists(f"/proc/{pidf.read_text().strip()}"):
    print("batch-2 driver already running, pid", pidf.read_text().strip())
else:
    p = subprocess.Popen(["/content/venv/bin/python", "/content/work/gpu_ab_run.py", str(N_ROUNDS), str(DEADLINE_H)],
                         cwd="/content/work", stdout=open("/content/ab2.log", "a"), stderr=subprocess.STDOUT,
                         env=dict(os.environ, AB_ARMS=ARMS, AB_OUT=OUT, AB_TAG=TAG), start_new_session=True)
    pidf.write_text(str(p.pid))
    print("batch-2 driver started, pid", p.pid)
