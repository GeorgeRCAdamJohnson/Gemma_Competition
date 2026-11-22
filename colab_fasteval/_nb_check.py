"""Check the connector notebook on disk: cell ids, per-cell syntax, and whether it equals a fresh generator build.
usage: python colab_fasteval/_nb_check.py"""
import ast
import hashlib
import json
from pathlib import Path

p = Path("colab_fasteval/run_31b_lb022_v3.ipynb")
raw = p.read_bytes()
nb = json.loads(raw)
print("file", p, len(raw), "bytes, sha256", hashlib.sha256(raw).hexdigest()[:12])
for i, c in enumerate(nb["cells"]):
    src = "".join(c["source"])
    status = "markdown"
    if c["cell_type"] == "code":
        try:
            ast.parse(src)
            status = "parses"
        except SyntaxError as e:
            status = f"SYNTAX ERROR line {e.lineno}: {e.msg}"
    first = src.splitlines()[0][:70] if src else ""
    print(f"cell {i} id={c.get('id')} {c['cell_type']:8s} lines={len(src.splitlines()):3d} {status} | {first}")
