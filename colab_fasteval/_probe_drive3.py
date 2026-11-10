# Runs ON the Colab VM: is an E4B model anywhere on Drive (hf_cache, Colab Notebooks, kaggle cache)?
import os
from pathlib import Path

D = Path("/content/drive/MyDrive")
for root in ("hf_cache", "Colab Notebooks", "gemma-4-developer-agent-cache/models"):
    base = D / root
    if not base.exists():
        print(root, "missing")
        continue
    print(f"== {root}")
    for dirpath, dirnames, filenames in os.walk(base):
        depth = dirpath[len(str(base)):].count(os.sep)
        if depth > 5:
            dirnames[:] = []
            continue
        big = [(f, os.path.getsize(os.path.join(dirpath, f))) for f in filenames]
        sz = sum(s for _, s in big)
        if depth <= 3 or sz > 1e8:
            rel = dirpath[len(str(base)):] or "/"
            names = sorted(f for f, _ in big)[:6]
            print(f"  {rel:80s} files={len(big):4d} GB={sz / 1e9:6.2f} {names}")
