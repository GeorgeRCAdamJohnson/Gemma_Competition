# Runs ON the GPU VM: is a smoke run alive, which log is current, how far along is it?
import subprocess
from pathlib import Path

ps = subprocess.run("pgrep -fa 'gpu_smoke_run|swegemma eval|vllm' | cut -c1-150", shell=True, capture_output=True, text=True).stdout
print("procs:\n" + (ps or "  none"))
for f in ("/content/smoke.log", "/content/smoke_attempt_prev.log"):
    p = Path(f)
    if p.exists():
        lines = p.read_text(errors="replace").splitlines()
        print(f"== {f} ({len(lines)} lines, mtime {int(p.stat().st_mtime)})")
        print("\n".join([l for l in lines if l.startswith("[")][-8:]))
print("results dirs:", sorted(str(p) for p in Path("/content/work").glob("results*")))
r = Path("/content/work/results/task_results.jsonl")
print("task_results rows:", len(r.read_text().splitlines()) if r.exists() else 0)
print(subprocess.run("nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader", shell=True,
                     capture_output=True, text=True).stdout.strip())
