# Runs ON a GPU VM: print progress.json files compactly (one line each) so they can be saved locally.
import json
from pathlib import Path

for tag, p in (("ab4", Path("/content/ab4/progress.json")),
               ("ab2", Path("/content/drive/MyDrive/gemma_fasteval/ab_runs/e4b_ab2_20261111/progress.json"))):
    if p.exists():
        print(f"PROGRESS_JSON {tag} " + json.dumps(json.loads(p.read_text())))
print("ALL_DONE ab4:", Path("/content/ab4/ALL_DONE").exists())
