"""Build gemma-sibling-conform-v11.ipynb from notebook_src.py (the ipynb is the real artifact kaggle runs)."""
import json, os
HERE = os.path.dirname(__file__)
src = open(os.path.join(HERE, "notebook_src.py"), encoding="utf-8").read()
parts = src.split("# ===== CELL ")
header = parts[0]
cells = []
for idx, p in enumerate(parts[1:]):
    code = (header + "# ===== CELL " + p) if idx == 0 else ("# ===== CELL " + p)
    code = code.rstrip("\n")
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None,
                  "outputs": [], "source": [l + "\n" for l in code.split("\n")]})
nb = {"cells": cells,
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python", "version": "3.11"}},
      "nbformat": 4, "nbformat_minor": 5}
out = os.path.join(HERE, "gemma-sibling-conform-v11.ipynb")
json.dump(nb, open(out, "w", encoding="utf-8"), indent=1)
print("wrote", out, "with", len(cells), "cells")
