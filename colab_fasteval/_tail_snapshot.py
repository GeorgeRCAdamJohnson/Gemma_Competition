# Runs ON the Colab VM: progress of the env snapshot job.
from pathlib import Path

LOG, DONE = Path("/content/snapshot.log"), Path("/content/snapshot.done")
print("done:", DONE.read_text().strip() if DONE.exists() else "no")
if LOG.exists():
    print(LOG.read_text(errors="replace")[-1500:])
