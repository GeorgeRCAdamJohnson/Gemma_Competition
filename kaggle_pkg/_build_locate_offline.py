"""Build a CPU-only Kaggle kernel that pressure-tests skills/locate offline on ALL 129 tasks (no model, no GPU):
for each task, extract the snapshot, run locate.py with two queries, and check whether the GOLD patch's source file is the
#1 / in the top 3 candidates.
  query A "full"  = the whole problem statement (upper bound: everything the model could copy)
  query B "ids"   = only code-like tokens from the problem (backticks, CamelCase, snake_case, name(), dotted)
Writes /kaggle/working/locate_offline.json and prints a summary + per-task table.
"""
import base64
import json
from pathlib import Path

K = Path(__file__).resolve().parent
ROOT = K.parent
LOC = (ROOT / "colab_fasteval" / "skill_locate" / "scripts" / "locate.py").read_bytes()
SLUG = "locate-offline"
DST = K / "push_locate_offline"
LANDABLE = json.loads((ROOT / "colab_fasteval" / "ab_tasks.json").read_text())
code = r'''
import base64, glob, json, os, re, shutil, subprocess, sys, tarfile, tempfile
from pathlib import Path
LOC = base64.b64decode("__LOC__")
Path("/kaggle/working/locate.py").write_bytes(LOC)
LANDABLE = set(json.loads("""__LANDABLE__"""))
tasks, tasks_f = [], None
for f in glob.glob("/kaggle/input/**/tasks.jsonl", recursive=True):   # take the copy that carries gold patches
    rows = [json.loads(l) for l in open(f) if l.strip()]
    if sum(bool(r.get("patch")) for r in rows) > len(tasks and [1] or []) and sum(bool(r.get("patch")) for r in rows) > sum(bool(r.get("patch")) for r in tasks):
        tasks, tasks_f = rows, f
snaps = {Path(p).stem.replace(".tar", ""): p for p in glob.glob("/kaggle/input/**/*.tgz", recursive=True)}
print("tasks", len(tasks), "snapshots", len(snaps), "from", tasks_f)

def gold_files(patch):
    fs = []
    for ln in patch.splitlines():
        if ln.startswith("+++ "):
            f = ln[4:].strip()
            f = f[2:] if f.startswith(("a/", "b/")) else f
            b = f.rsplit("/", 1)[-1]
            if f != "/dev/null" and f.endswith(".py") and not (b.startswith("test_") or "/tests/" in "/" + f):
                fs.append(f)
    return fs

def ids_only(q):
    t = set(re.findall(r"`([^`]{2,80})`", q))
    t |= set(re.findall(r"\b[A-Z][a-z0-9]+(?:[A-Z][A-Za-z0-9]+)+\b", q))
    t |= set(re.findall(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", q))
    t |= set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*(?=\()", q))
    t |= set(re.findall(r"\b[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+\b", q))
    return " ".join(sorted(t))

res = []
for t in tasks:
    iid = t["instance_id"]
    gold = gold_files(t.get("patch") or "")
    if iid not in snaps or not gold:
        res.append(dict(id=iid, skip="no snapshot" if iid not in snaps else "no source gold"))
        continue
    d = tempfile.mkdtemp()
    try:
        with tarfile.open(snaps[iid]) as tf:
            tf.extractall(d, filter="data")
        # snapshot may unpack into a single top dir
        subs = [p for p in Path(d).iterdir()]
        root = str(subs[0]) if len(subs) == 1 and subs[0].is_dir() and not (Path(d) / ".git").exists() else d
        row = dict(id=iid, gold=gold, landable=iid in LANDABLE)
        for name, q in (("full", t["problem_statement"]), ("ids", ids_only(t["problem_statement"]))):
            p = subprocess.run([sys.executable, "/kaggle/working/locate.py", "--q", q], cwd=root, capture_output=True,
                               text=True, timeout=120, env=dict(os.environ, PYTHONPATH=root))
            cand = re.findall(r"^\s+\d+\. (\S+)", p.stdout, re.M)
            row[name] = cand
            row[name + "_rank"] = next((i + 1 for i, c in enumerate(cand) if c in gold), None)
        res.append(row)
    except Exception as e:
        res.append(dict(id=iid, skip=f"{type(e).__name__}: {e}"[:120]))
    finally:
        shutil.rmtree(d, ignore_errors=True)

json.dump(res, open("/kaggle/working/locate_offline.json", "w"), indent=1)
ok = [r for r in res if "skip" not in r]
print("evaluated", len(ok), "| skipped", len(res) - len(ok), [r["skip"] for r in res if "skip" in r][:5])
for sub, rs in (("ALL", ok), ("LANDABLE26", [r for r in ok if r["landable"]])):
    for name in ("full", "ids"):
        k1 = sum(r[name + "_rank"] == 1 for r in rs)
        k3 = sum((r[name + "_rank"] or 99) <= 3 for r in rs)
        k5 = sum(r[name + "_rank"] is not None for r in rs)
        print(f"{sub:11s} query={name:4s} n={len(rs):3d}  top1 {k1:3d} ({100*k1/max(1,len(rs)):.0f}%)  top3 {k3:3d} "
              f"({100*k3/max(1,len(rs)):.0f}%)  top5 {k5:3d} ({100*k5/max(1,len(rs)):.0f}%)")
print("\nper task (landable first): id | gold | full rank | ids rank | full top3")
for r in sorted(ok, key=lambda r: (not r["landable"], r["id"])):
    print(f"{'*' if r['landable'] else ' '} {r['id']:16s} {','.join(r['gold'])[:60]:60s} {str(r['full_rank']):>4s} "
          f"{str(r['ids_rank']):>4s}  {r['full'][:3]}")
'''.replace("__LOC__", base64.b64encode(LOC).decode()).replace("__LANDABLE__", json.dumps(LANDABLE))
compile(code, "cell", "exec")
nb = {"cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": code.splitlines(True)}],
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
      "nbformat": 4, "nbformat_minor": 5}
DST.mkdir(exist_ok=True)
(DST / f"{SLUG}.ipynb").write_text(json.dumps(nb), encoding="utf-8")
meta = {"id": f"comfyops/{SLUG}", "title": SLUG.replace("-", " "), "code_file": f"{SLUG}.ipynb", "language": "python",
        "kernel_type": "notebook", "is_private": True, "enable_gpu": False, "enable_tpu": False, "enable_internet": False,
        "keywords": [], "dataset_sources": ["comfyops/gemma129-taskdefs", "comfyops/gemma129-snapshots"],
        "kernel_sources": [], "competition_sources": ["gemma-4-developer-agent"], "model_sources": []}
(DST / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("wrote", DST)
