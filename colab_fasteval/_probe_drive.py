# Runs ON the Colab VM: map what Kaggle resources are on Drive. Names and sizes only.
import os
from pathlib import Path

ROOT = Path("/content/drive/MyDrive")
print("MyDrive exists:", ROOT.exists())
if ROOT.exists():
    print("top level:", sorted(p.name for p in ROOT.iterdir())[:60])
KEYS = ("gemma", "kaggle", "e4b", "wheel", "snapshot", "taskdef", "swegemma", "qat", "w4a16")
hits = []
for dirpath, dirnames, filenames in os.walk(ROOT):
    depth = dirpath[len(str(ROOT)):].count(os.sep)
    if depth > 4:
        dirnames[:] = []
        continue
    low = dirpath.lower()
    if any(k in low for k in KEYS):
        n = len(filenames)
        sz = 0
        for f in filenames:
            try:
                sz += os.path.getsize(os.path.join(dirpath, f))
            except OSError:
                pass
        exts = sorted({Path(f).suffix for f in filenames})[:8]
        hits.append((dirpath[len(str(ROOT)):] or "/", n, round(sz / 1e9, 2), exts))
for h in hits[:80]:
    print(f"{h[0]:70s} files={h[1]:5d} GB={h[2]:7.2f} ext={h[3]}")
print("matched dirs:", len(hits))
