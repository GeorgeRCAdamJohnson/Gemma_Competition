# Runs ON a Colab VM: what has been set up here? (prep artifacts, Drive mount, uptime)
import os
import subprocess
from pathlib import Path

print("host", os.uname().nodename, "| uptime", subprocess.run("cut -d' ' -f1 /proc/uptime", shell=True, capture_output=True, text=True).stdout.strip(), "s")
for p in ("/content/work/arms", "/content/work/ab_tasks.json", "/content/venv/bin/python", "/content/model/model.safetensors",
          "/content/snaps", "/content/prep.done", "/content/ab_inputs.tar"):
    q = Path(p)
    print(f"  {p:40s} {'yes' if q.exists() else 'NO'}" + (f" ({len(list(q.iterdir()))} entries)" if q.is_dir() else ""))
print("  drive mounted:", os.path.ismount("/content/drive"))
