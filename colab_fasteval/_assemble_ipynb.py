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
    "# Get kaggle.json, then clone the repo so the ca5 + deffind bundles are present.\n",
    "# Colab Secret (key icon, left sidebar) named 'Kaggle_token', notebook access ON. The secret may hold\n",
    "# EITHER the full kaggle.json ({\"username\":...,\"key\":...}) OR just the API key string; both handled.\n",
    "import os, subprocess, json\n",
    "SECRET_NAMES = ['kagKaggle_token', 'Kaggle_token', 'KAGGLE_JSON', 'kaggle_json', 'KAGGLE_TOKEN']\n",
    "if not os.path.exists('/content/kaggle.json'):\n",
    "    wrote = False\n",
    "    try:\n",
    "        from google.colab import userdata\n",
    "        val = None\n",
    "        for nm in SECRET_NAMES:\n",
    "            try:\n",
    "                val = userdata.get(nm)\n",
    "            except Exception:\n",
    "                val = None\n",
    "            if val: print('using secret:', nm); break\n",
    "        if val:\n",
    "            val = val.strip()\n",
    "            if val.startswith('{'):\n",
    "                open('/content/kaggle.json','w').write(val)            # already full json\n",
    "            else:\n",
    "                user = os.environ.get('KAGGLE_USERNAME') or ''\n",
    "                for nm in ['Kaggle_username','KAGGLE_USERNAME','kaggle_username']:\n",
    "                    try:\n",
    "                        u = userdata.get(nm)\n",
    "                    except Exception:\n",
    "                        u = None\n",
    "                    if u: user = u.strip(); break\n",
    "                if not user: user = input('Kaggle username (secret had only the key): ').strip()\n",
    "                json.dump({'username': user, 'key': val}, open('/content/kaggle.json','w'))\n",
    "            wrote = True; print('wrote /content/kaggle.json')\n",
    "    except Exception as e:\n",
    "        print('secret read failed:', e)\n",
    "    if not wrote:\n",
    "        from google.colab import files\n",
    "        print('No secret found. Upload kaggle.json (or add the KAGGLE_JSON secret and rerun):')\n",
    "        up = files.upload()\n",
    "        if up:\n",
    "            name = list(up)[0]\n",
    "            if name != 'kaggle.json': os.rename('/content/'+name, '/content/kaggle.json')\n",
    "assert os.path.exists('/content/kaggle.json'), 'kaggle.json missing - add the KAGGLE_JSON secret or upload it'\n",
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
