"""Generate a CPU-only Kaggle probe: do the 3 code-intelligence tools work at all?

No model, no GPU, no task evaluation. Installs the wheelhouse, then calls
get_code_neighbors / search_similar_code / get_code_subgraph with a real repo and
prints exactly what the harness would return. Decides whether the biggest unused
localization lever is real or dead.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "kaggle_pkg" / "push_ci_probe"
OUT.mkdir(parents=True, exist_ok=True)

WHEELS = r'''
import glob, os, shutil, subprocess, sys
from pathlib import Path
print("listing /kaggle/input:", sorted(os.listdir("/kaggle/input")))
CANDIDATES = [
    Path("/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse"),
    Path("/kaggle/input/gemma-4-developer-agent-wheelhouse"),
]
WH = next((p for p in CANDIDATES if p.is_dir()), None) or Path(
    (glob.glob("/kaggle/input/**/gemma-4-developer-agent-wheelhouse", recursive=True) or [""])[0])
assert WH and WH.is_dir(), "wheelhouse not mounted"
print("WHEELHOUSE:", WH)
for pat in ("/usr/local/lib/python*/dist-packages/*cutlass*.pth",
            "/usr/local/lib/python*/site-packages/*cutlass*.pth"):
    for p in glob.glob(pat):
        try: os.unlink(p)
        except OSError: pass
tmp = Path("/tmp/wh"); shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True)
for w in WH.glob("*.whl"):
    if "cutlass" in w.name.lower(): continue
    shutil.copy2(w, tmp / w.name.replace("cu128", "+cu128"))
r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps",
                    "--force-reinstall"] + [str(p) for p in sorted(tmp.glob("*.whl"))],
                   capture_output=True, text=True)
print("pip rc:", r.returncode, (r.stderr or "")[-400:])
import swegemma, adk_submission
print("IMPORTS OK: adk_submission", getattr(adk_submission, "__version__", "?"),
      "| swegemma", getattr(swegemma, "__version__", "?"))
'''

PROBE = r'''
import inspect, json, os, traceback
from pathlib import Path

print("\n" + "=" * 70)
print("1. WHERE WOULD THE GRAPH COME FROM?")
print("=" * 70)
try:
    from swegemma.graph import embedding_utils as EU
    for name in [n for n in dir(EU) if "SSTABLE" in n or "DEFAULT" in n]:
        v = getattr(EU, name)
        if isinstance(v, str):
            exists = Path(v).exists()
            print("  %-34s %s  (exists=%s)" % (name, v[:70], exists))
except Exception as e:
    print("  cannot read embedding_utils:", type(e).__name__, e)

print("\n  graph-like files under /kaggle/input:")
hits = 0
seen_top = set()
for root, dirs, files in os.walk("/kaggle/input"):
    depth = root.count("/")
    parts = root.split("/")
    if len(parts) > 6:
        seen_top.add("/".join(parts[:6]))
    if depth > 8:
        dirs[:] = []
        continue
    for f in files:
        if any(k in f.lower() for k in ("graph", ".sst", "embedding", "topolog", "callgraph")):
            print("   ", os.path.join(root, f)[:130])
            hits += 1
            if hits > 15: break
    if hits > 15: break
print("  total graph-ish files found:", hits)
print("  /kaggle/input top-level:", sorted(os.listdir("/kaggle/input")))
for d in ("competitions", "datasets", "models"):
    p = "/kaggle/input/" + d
    if os.path.isdir(p):
        for sub in sorted(os.listdir(p))[:6]:
            print("    %s/%s -> %s" % (d, sub, sorted(os.listdir(os.path.join(p, sub)))[:8]))

print("\n" + "=" * 70)
print("2. DO THE TOOLS RETURN DATA OR ERRORS?")
print("=" * 70)


class Ctx:
    """Minimal stand-in for the harness context the tools expect."""
    graph_dir = None
    repo = "Textualize/rich"
    task = {"repo": "Textualize/rich", "instance_id": "rich_4077"}

    def __getattr__(self, k):
        return None


CASES = [
    ("get_code_neighbors", {"node": "FileProxy"}),
    ("get_code_neighbors", {"node": "FileProxy.isatty"}),
    ("search_similar_code", {"query": "proxy isatty"}),
    ("get_code_subgraph", {"nodes": ["FileProxy"]}),
]
try:
    from swegemma.tools import graph as G
    for fn, kw in CASES:
        f = getattr(G, fn, None)
        if f is None:
            print("  %s: NOT PRESENT" % fn)
            continue
        try:
            out = f(Ctx(), **kw)
            s = out if isinstance(out, str) else json.dumps(out, default=str)
            print("  %-22s %-34s -> %s" % (fn, kw, s[:220]))
        except Exception as e:
            print("  %-22s %-34s -> RAISED %s: %s" % (fn, kw, type(e).__name__, str(e)[:160]))
except Exception:
    print("  cannot import swegemma.tools.graph:")
    traceback.print_exc(limit=4)

print("\n" + "=" * 70)
print("3. ARE THEY REGISTERED IN THE TOOL REGISTRY (i.e. callable at all)?")
print("=" * 70)
try:
    from adk_submission import ToolRegistry
    names = [n for n in dir(ToolRegistry) if not n.startswith("_")]
    print("  ToolRegistry members:", names[:12])
except Exception as e:
    print("  ToolRegistry introspect failed:", type(e).__name__, e)

try:
    from swegemma.tools import __all__ as tools_all
    print("  swegemma.tools exports:", [t for t in tools_all if "code" in t.lower() or "search" in t.lower()])
except Exception as e:
    print("  no __all__:", type(e).__name__)

print("\nPROBE DONE")
'''


def cell(src):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": src.splitlines(keepends=True)}


nb = {
    "cells": [
        {"cell_type": "markdown", "metadata": {}, "source": [
            "# Do the 3 code-intelligence tools work?\n\n"
            "The ca5 pack declares 9 tools. Across **258 task-runs (129 E4B + 129 31B)** the three\n"
            "graph tools were called **zero times**, and `system.md` never mentions them.\n\n"
            "This probe decides whether that is because they are ignored, or because they are **dead**\n"
            "(their default backing store is a Google-internal CNS path).\n\n"
            "CPU only. No model, no GPU, no task evaluation.\n"]},
        cell(WHEELS), cell(PROBE),
    ],
    "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                 "language_info": {"name": "python"}},
    "nbformat": 4, "nbformat_minor": 5,
}

path = OUT / "ci-tools-probe.ipynb"
path.write_text(json.dumps(nb, indent=1), encoding="utf-8")

meta = {
    "id": "comfyops/ci-tools-probe",
    "title": "ci tools probe",
    "code_file": "ci-tools-probe.ipynb",
    "language": "python",
    "kernel_type": "notebook",
    "is_private": True,
    "enable_gpu": False,
    "enable_tpu": False,
    "enable_internet": False,
    "keywords": [],
    "dataset_sources": ["metric/gemma-4-developer-agent-wheelhouse"],
    "kernel_sources": [],
    "competition_sources": ["gemma-4-developer-agent"],
    "model_sources": [],
    "docker_image": "gcr.io/kaggle-private-byod/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461",
}
(OUT / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("wrote", path, "(%d B)" % path.stat().st_size)
print("wrote", OUT / "kernel-metadata.json")
print("gpu:", meta["enable_gpu"], "| datasets:", meta["dataset_sources"])
