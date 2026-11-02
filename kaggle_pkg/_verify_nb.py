import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
nb = json.loads(Path("push_129_off31/ca5-31b-full129.ipynb").read_text(encoding="utf-8"))
print("valid JSON, cells:", len(nb["cells"]))
src = "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
probes = ["PREFLIGHT OK", "b08b32a2438d", 'filter="data"', "snapshots.tar",
          "--task-id", "summary.json", "tensor_parallel_size", "gemma4"]
for p in probes:
    print(f"  contains {p!r}: {p in src}")
print("chars of code:", len(src))
