# Runs ON the VM via CLI exec: start the prep job ONLY if Drive is mounted (a prep without Drive fails and used to
# leave a misleading /content/prep.done). Then the chained keep-alive takes over.
import runpy
from pathlib import Path

if not Path("/content/drive/MyDrive/gemma-4-developer-agent-cache").is_dir():
    print("PREP REFUSED: Drive not mounted")
    raise SystemExit(3)
runpy.run_path("/content/gpu_prep_ab.py")
