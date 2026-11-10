# Runs ON the GPU VM: is the current pass progressing? Minutes since the last log line, since the newest task log
# was written, live eval processes, GPU activity, vLLM request counters.
import subprocess
import time
from pathlib import Path

now = time.time()
log = Path("/content/ab.log")
print(f"ab.log last write {(now - log.stat().st_mtime) / 60:.1f} min ago")
logs = sorted(Path("/content/ab").glob("*/round_*/logs/*.log"), key=lambda p: p.stat().st_mtime)
if logs:
    print(f"newest task log {logs[-1].parent.parent.parent.name}/{logs[-1].parent.parent.name}/{logs[-1].name} written "
          f"{(now - logs[-1].stat().st_mtime) / 60:.1f} min ago")
cur = sorted(Path("/content/ab/L_lean/round_8/logs").glob("*.log"), key=lambda p: p.stat().st_mtime) if Path("/content/ab/L_lean/round_8/logs").exists() else []
print("L_lean round_8 task logs:", len(cur), [f"{p.stem}:{(now - p.stat().st_mtime) / 60:.0f}m" for p in cur][-8:])
print(subprocess.run("pgrep -fa 'swegemma eval' | wc -l; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader; "
                     "curl -s localhost:8000/metrics | grep -E '^vllm:num_requests_(running|waiting)' ",
                     shell=True, capture_output=True, text=True).stdout)
