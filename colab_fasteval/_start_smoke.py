# Runs ON the GPU VM: launch gpu_smoke_run.py in the Kaggle-matched venv as a background job.
import subprocess
from pathlib import Path

Path("/content/smoke.log").unlink(missing_ok=True)
subprocess.Popen("cd /content/work && nohup /content/venv/bin/python /content/work/gpu_smoke_run.py "
                 "> /content/smoke.log 2>&1 &", shell=True)
print("started smoke run")
