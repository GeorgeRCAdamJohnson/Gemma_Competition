"""Extract the candidate submission files embedded in the denpugovkin notebook (a Python dict literal in cell 1)."""
import ast
import json
from pathlib import Path

root = Path("competitor_probe/lb022/denpugovkin__gemma-4-repair-lab-compare-before-you-submit")
nb = json.loads(next(root.glob("*.ipynb")).read_text(encoding="utf-8"))
src = "".join(nb["cells"][1]["source"])
tree = ast.parse(src)
found = {}
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
        try:
            value = ast.literal_eval(node.value)
        except Exception:
            continue
        if isinstance(value, dict) and "agent.yaml" in value:
            name = node.targets[0].id if isinstance(node.targets[0], ast.Name) else "?"
            found[name] = value
for name, files in found.items():
    out = root / f"files_{name}"
    out.mkdir(exist_ok=True)
    for rel, text in files.items():
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text if isinstance(text, str) else text.decode(), encoding="utf-8", newline="\n")
    print(name, sorted(files), "->", out)
