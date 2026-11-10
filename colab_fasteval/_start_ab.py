# Runs ON the GPU VM: launch the A/B driver in the background, then KEEP THIS KERNEL BUSY while it runs
# (Colab keeps a runtime alive while its kernel is active). Status checks go through other kernels/sessions.
import os
import subprocess
import time
from pathlib import Path

N_ROUNDS = int(os.environ.get("AB_ROUNDS", "10"))
DEADLINE_H = float(os.environ.get("AB_DEADLINE_H", "20"))
if not Path("/content/ab.pid").exists():
    p = subprocess.Popen(f"cd /content/work && AB_TAG=e4b_ab_20261110 nohup /content/venv/bin/python /content/work/gpu_ab_run.py "
                         f"{N_ROUNDS} {DEADLINE_H} > /content/ab.log 2>&1 & echo $! > /content/ab.pid", shell=True)
    p.wait()
pid = int(Path("/content/ab.pid").read_text().strip())
print("driver pid", pid, flush=True)
while os.path.exists(f"/proc/{pid}"):
    time.sleep(300)
    tail = Path("/content/ab.log").read_text(errors="replace").splitlines()[-1:] if Path("/content/ab.log").exists() else []
    print(time.strftime("%H:%M"), tail, flush=True)
print("driver exited", flush=True)
