# Read-only peek at a running Colab A/B driver (run via `colab exec -s <session> -f`): driver alive, current pass
# progress (finished traces per arm), log tail, GPU load. Changes nothing.
import subprocess
import time
from pathlib import Path

print("vm time", time.strftime("%H:%M:%S"))
pid = Path("/content/ab.pid")
alive = pid.exists() and Path(f"/proc/{pid.read_text().strip()}").exists()
print("driver alive:", alive, "| ALL_DONE:", Path("/content/ab/ALL_DONE").exists())
for arm in sorted(p for p in Path("/content/ab").iterdir() if p.is_dir()) if Path("/content/ab").is_dir() else []:
    traces = list(arm.rglob("trace_*.json"))
    newest = max((t.stat().st_mtime for t in traces), default=0)
    print(f"  {arm.name:14s} traces {len(traces):3d}/85  newest {time.strftime('%H:%M:%S', time.localtime(newest)) if newest else '-'}")
log = Path("/content/ab.log")
print("\n".join(log.read_text(errors="replace").splitlines()[-4:]) if log.exists() else "no ab.log")
print(subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used", "--format=csv,noheader"],
                     capture_output=True, text=True).stdout.strip())
