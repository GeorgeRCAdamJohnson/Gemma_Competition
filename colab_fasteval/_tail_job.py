# Runs ON the Colab VM: tail the prep and smoke logs.
from pathlib import Path

for name in ("prep", "smoke"):
    log = Path(f"/content/{name}.log")
    if log.exists():
        print(f"== {name}.log")
        print("".join(log.read_text(errors="replace").splitlines(keepends=True)[-25:]))
