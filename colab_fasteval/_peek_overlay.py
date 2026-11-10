# Runs ON the Colab VM: what is the overlay job doing / why did it stop?
import subprocess
from pathlib import Path

log = Path("/content/overlay.log")
print("== overlay.log head")
print("".join(log.read_text(errors="replace").splitlines(keepends=True)[:12]) if log.exists() else "missing")
print("== bulk log")
b = Path("/content/overlay_bulk.log")
print(b.read_text(errors="replace")[-900:] if b.exists() else "missing")
print("done:", Path("/content/overlay.done").read_text().strip() if Path("/content/overlay.done").exists() else "no")
print("req lines:", len(Path("/content/overlay_req.txt").read_text().splitlines()))
print(subprocess.run("pgrep -fa 'uv pip|overlay' | cut -c1-140", shell=True, capture_output=True, text=True).stdout)
