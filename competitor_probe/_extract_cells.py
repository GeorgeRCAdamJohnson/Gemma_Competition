"""Dump every notebook under a folder to <notebook>_cells.txt (code and markdown, numbered) for reading/diffing.
usage: python competitor_probe/_extract_cells.py competitor_probe/lb022"""
import json
import sys
from pathlib import Path

for nb in Path(sys.argv[1]).rglob("*.ipynb"):
    cells = json.loads(nb.read_text(encoding="utf-8"))["cells"]
    out = []
    for i, c in enumerate(cells):
        src = "".join(c.get("source", []))
        out.append(f"# ===== cell {i} [{c['cell_type']}] =====\n{src}\n")
    target = nb.with_name(nb.stem + "_cells.txt")
    target.write_text("\n".join(out), encoding="utf-8")
    print(f"{target}  cells={len(cells)}  chars={sum(len(x) for x in out)}")
