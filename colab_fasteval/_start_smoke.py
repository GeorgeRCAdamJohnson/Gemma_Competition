# Runs ON the GPU VM: Kaggle-parity cleanup, then launch gpu_smoke_run.py in the Kaggle-matched venv (background).
import glob
import os
import shutil
import subprocess
from pathlib import Path

# the Kaggle kernels unlink cutlass .pth files before running (cell 1); do the same in the launcher venv
for pth in glob.glob("/content/venv/lib/python*/site-packages/*cutlass*.pth"):
    os.unlink(pth)
    print("removed", pth)
# fresh results dir for this attempt (keep the failed attempt's log for the record)
r = Path("/content/work/results")
if r.exists():
    shutil.move(str(r), f"/content/work/results_failed_{len(glob.glob('/content/work/results_failed_*'))}")
if Path("/content/smoke.log").exists():
    shutil.copy("/content/smoke.log", "/content/smoke_attempt_prev.log")
Path("/content/smoke.log").unlink(missing_ok=True)
subprocess.Popen("cd /content/work && nohup /content/venv/bin/python /content/work/gpu_smoke_run.py "
                 "> /content/smoke.log 2>&1 &", shell=True)
print("started smoke run")
