# Runs ON the Colab VM: progress of the overlay job.
from pathlib import Path

LOG, DONE = Path("/content/overlay.log"), Path("/content/overlay.done")
print("done:", DONE.read_text().strip() if DONE.exists() else "no")
if LOG.exists():
    print("".join(LOG.read_text(errors="replace").splitlines(keepends=True)[-45:]))
