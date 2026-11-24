"""Review any notebook: schema validity, cell ids, per-cell syntax, and cell text (long cells abbreviated).
usage: python colab_fasteval/_nb_review.py <notebook.ipynb> [max_chars_per_cell]"""
import ast
import json
import sys

import nbformat

path = sys.argv[1]
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 4000
d = json.load(open(path, encoding="utf-8"))
print("nbformat", d["nbformat"], d["nbformat_minor"], "| ids", [c.get("id") for c in d["cells"]])
print("metadata keys", sorted(d.get("metadata", {})))
try:
    nbformat.validate(nbformat.from_dict(d))
    print("schema VALID")
except Exception as e:  # noqa: BLE001
    print("schema INVALID:", str(e)[:300])
for i, c in enumerate(d["cells"]):
    s = "".join(c["source"])
    status = ""
    if c["cell_type"] == "code":
        try:
            ast.parse(s)
            status = "parses"
        except SyntaxError as e:
            status = f"SYNTAX ERROR line {e.lineno}: {e.msg}"
    print(f"\n===== cell {i} [{c['cell_type']}] {len(s)} chars {status}")
    print(s if len(s) <= limit else s[: limit - 1500] + f"\n...[{len(s)} chars total]...\n" + s[-1500:])
