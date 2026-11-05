"""Assemble fast_eval_deffind.ipynb from fast_eval_deffind.py by splitting on '# ===== CELL' markers.
Run: python _assemble_ipynb.py  (writes the .ipynb next to the .py)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
src = (HERE / "fast_eval_deffind.py").read_text(encoding="utf-8")

# the file starts with a header comment block before the first CELL marker; keep it on cell 1
parts = src.split("# ===== CELL ")
header = parts[0].rstrip("\n")
cells = []
for idx, p in enumerate(parts[1:]):
    code = (header + "\n\n# ===== CELL " + p) if idx == 0 else ("# ===== CELL " + p)
    code = code.rstrip("\n")
    cells.append({
        "cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
        "source": [l + "\n" for l in code.split("\n")],
    })

# prepend a markdown cell + a repo-clone + kaggle.json upload helper cell (cell 0)
setup = [
    "# Upload kaggle.json, then clone the repo so the ca5 + deffind bundles are present.\n",
    "from google.colab import files\n",
    "import os\n",
    "if not os.path.exists('/content/kaggle.json'):\n",
    "    print('Upload kaggle.json:'); files.upload()\n",
    "import subprocess\n",
    "if not os.path.exists('/content/Gemma_Competition'):\n",
    "    subprocess.run(['git','clone','--depth','1',\n",
    "                    'https://github.com/GeorgeRCAdamJohnson/Gemma_Competition','/content/Gemma_Competition'])\n",
    "print('repo present:', os.path.exists('/content/Gemma_Competition/local_eval/parity_rig/agent_ctrl_e4b_deffind'))\n",
]
md = {"cell_type": "markdown", "metadata": {},
      "source": ["# Fast-Eval DEFFIND gate (E4B, ca5 vs find-def) \u2014 Colab warm-server A/B\n",
                 "Run cells top to bottom. Needs kaggle.json (data/model pull) + the cloned repo (bundles).\n"]}
clone = {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": setup}
cells = [md, clone] + cells

nb = {"cells": cells,
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python", "version": "3.11"},
                   "accelerator": "GPU", "colab": {"gpuType": "T4", "provenance": []}},
      "nbformat": 4, "nbformat_minor": 5}
out = HERE / "fast_eval_deffind.ipynb"
out.write_text(json.dumps(nb, indent=1), encoding="utf-8")
print("wrote", out, "with", len(cells), "cells")
