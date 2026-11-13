# Runs ON the VM: prep log tail (arm hashes, imports) + batch-6 driver log tail + progress.
import json
import subprocess
from pathlib import Path

print("== prep.log");
print("\n".join(Path("/content/prep.log").read_text(errors="replace").splitlines()[-10:]))
print("== ab6.log")
lg = Path("/content/ab6.log")
print("\n".join(lg.read_text(errors="replace").splitlines()[-12:]) if lg.exists() else "no log")
pg = Path("/content/ab6/progress.json")
if pg.exists():
    print("== progress", json.dumps(json.loads(pg.read_text()))[:1500])
print(subprocess.run("nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader", shell=True,
                     capture_output=True, text=True).stdout)
