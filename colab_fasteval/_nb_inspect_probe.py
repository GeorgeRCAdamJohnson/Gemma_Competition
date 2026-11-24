"""Run the length-probe notebook's cells in inspect mode locally (no GPU, no Drive) and extract its embedded
sources to Outputs/_probe_v2_sources/ for review. usage: python colab_fasteval/_nb_inspect_probe.py"""
import json
from pathlib import Path

nb = json.loads(Path("train/colab_repair_length_probe_v2.ipynb").read_text(encoding="utf-8"))
code = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
env = {}
for i, src in enumerate(code):
    print(f"--- running code cell {i}")
    exec(compile(src, f"cell{i}", "exec"), env)
out = Path("Outputs/_probe_v2_sources")
out.mkdir(parents=True, exist_ok=True)
for name, src in env["SOURCES"].items():
    (out / name).write_text(src, encoding="utf-8", newline="\n")
    print(f"extracted {name} ({len(src):,} chars)")
