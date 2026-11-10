# Runs ON the GPU VM: is the A/B driver alive? pid file, log tail, processes, GPU use.
import os
import subprocess
from pathlib import Path

pidf = Path("/content/ab.pid")
pid = pidf.read_text().strip() if pidf.exists() else None
print("pid file:", pid, "| alive:", bool(pid) and os.path.exists(f"/proc/{pid}"))
log = Path("/content/ab.log")
print("ab.log:", log.stat().st_size if log.exists() else "missing")
if log.exists():
    print("".join(log.read_text(errors="replace").splitlines(keepends=True)[-15:]))
print(subprocess.run("pgrep -fa 'gpu_ab_run|swegemma eval|vllm.entrypoints' | cut -c1-140; "
                     "nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader; ls /content/ab 2>&1 | head",
                     shell=True, capture_output=True, text=True).stdout)
