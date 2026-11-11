# Runs ON a GPU VM: print a batch's progress.json compactly (one JSON line) so it can be saved locally.
import json
import sys
from pathlib import Path

name = "ab"
p = Path(f"/content/{name}/progress.json")
print("PROGRESS_JSON " + json.dumps(json.loads(p.read_text())))
