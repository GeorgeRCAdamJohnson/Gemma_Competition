# Runs ON the Colab VM: show progress of a background job. Edit LOG/DONE for other jobs.
from pathlib import Path

LOG, DONE = Path("/content/setup_env.log"), Path("/content/setup_env.done")
print("done:", DONE.read_text().strip() if DONE.exists() else "no")
if LOG.exists():
    print("".join(LOG.read_text(errors="replace").splitlines(keepends=True)[-40:]))
