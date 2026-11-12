# Runs ON the logpull VM: is the log bundle being built / done?
import os
import subprocess
from pathlib import Path

p = Path("/content/ab_logs.tar.gz")
print("tar exists:", p.exists(), "| MB", round(p.stat().st_size / 1e6, 1) if p.exists() else 0)
print(subprocess.run("pgrep -fa '_tar_ab_logs|python' | cut -c1-120 | head; ls /content/drive/MyDrive/gemma_fasteval/ab_runs",
                     shell=True, capture_output=True, text=True).stdout)
