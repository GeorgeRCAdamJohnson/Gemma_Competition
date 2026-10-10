"""Assemble notebook_src.py (head + cell2 data + body) then convert to .ipynb.
The .ipynb is the real artifact kaggle runs; notebook_src.py is the editable source."""
import json, os

HERE = os.path.dirname(__file__)
head = open(os.path.join(HERE, "notebook_head.py"), encoding="utf-8").read().rstrip() + "\n"
body = open(os.path.join(HERE, "notebook_body.py"), encoding="utf-8").read().strip("\n") + "\n"
blob = open(os.path.join(HERE, "..", "_data_blob.txt"), encoding="utf-8").read().strip("\n")

cell2 = (
    "\n# ===== CELL 2: decode the embedded 48 localization trajectories (gzip+base64, self-contained) =====\n"
    "import gzip, base64, json as _json\n"
    + blob + "\n"
    "_raw = gzip.decompress(base64.b64decode(_DATA_B64GZ))\n"
    "DATA = [_json.loads(l) for l in _raw.decode('utf-8').splitlines() if l.strip()]\n"
    "print('loaded', len(DATA), 'localization trajectories')\n"
    "assert all('messages' in r for r in DATA), 'bad data shape'\n"
    "print('sample assistant turn:\\n', DATA[0]['messages'][1]['content'][:200])\n"
)

src = head + cell2 + "\n" + body
with open(os.path.join(HERE, "notebook_src.py"), "w", encoding="utf-8") as f:
    f.write(src)

# split on the cell markers into ipynb code cells
parts = src.split("# ===== CELL ")
cells = []
# first part is the top header comment -> prepend to cell 1
header = parts[0]
for idx, p in enumerate(parts[1:]):
    code = ("# ===== CELL " + p) if idx > 0 else (header + "# ===== CELL " + p)
    code = code.rstrip("\n")
    cells.append({
        "cell_type": "code", "metadata": {}, "execution_count": None,
        "outputs": [], "source": [l + "\n" for l in code.split("\n")]
    })

nb = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    },
    "nbformat": 4, "nbformat_minor": 5,
}
out_ipynb = os.path.join(HERE, "gemma-localizer-lora-train.ipynb")
with open(out_ipynb, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1)
print("wrote", out_ipynb, "with", len(cells), "cells")
