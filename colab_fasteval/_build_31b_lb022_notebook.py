"""Generate colab_fasteval/run_31b_lb022_ide.ipynb: the template chain (_ab_chain.sh) as notebook cells, for running
through the Colab connector add-on. Inputs are read from Drive (MyDrive/gemma_fasteval/launch/<tag>/), with the
SHA-256 of each file pinned here from the local copies. usage: python colab_fasteval/_build_31b_lb022_notebook.py"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG = "31b_lb022_20261122"
FILES = ["_lb022_inputs.tar", "_gpu_prep_ab.py", "_launch_if_ready.py", "_verify_model_dir.py"]
HASHES = {f: hashlib.sha256((ROOT / "colab_fasteval" / f).read_bytes()).hexdigest() for f in FILES}
LAUNCH = {"arms": "arms", "out": "/content/ab", "tag": TAG, "rounds": 1, "round_from": 1, "deadline_h": 12,
          "gpu_utilization": 0.85, "model_name": "gemma-4-31b-it-qat-w4a16-ct",
          "model_archive": "gemma_fasteval/model/gemma-4-other-gemma-4-31b-it-qat-w4a16-ct-v2.tar.gz", "conc": 6}


def code(src):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": src.strip("\n").splitlines(keepends=True)}


def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src.strip("\n").splitlines(keepends=True)}


cells = [
    md(f"""
# 31B six-arm A/B: ca5 vs public 0.22 configs (Colab connector)
Pre-registered in `GEMMA_EXPERIMENT_LOG.md` (2026-11-22). Runtime: **G4, High-RAM**. Run the cells in order.
Arms: A_ca5, B_denpug, C_flex, D_bliver, E_ayush_noad, F_ayush_lora; 85 live tasks; 1 round; 6 tasks at once.
Estimate ~8.5 h, ~85 CU at ~10 CU/h; the driver stops itself at 12 h. Results: `MyDrive/gemma_fasteval/ab_runs/{TAG}`.
**When cell 5 prints ALL_DONE (or if anything fails), disconnect and delete the runtime so it stops billing.**
"""),
    code("""
# 1. Drive (consent appears here) and GPU check
from google.colab import drive
drive.mount('/content/drive')
import subprocess
gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader'],
                     capture_output=True, text=True).stdout.strip()
print('GPU:', gpu)
mem_mib = int(gpu.split(',')[-1].split()[0])
assert mem_mib >= 75000, f'31B needs >= 80 GB (G4 96 GB); this runtime has {mem_mib} MiB'
"""),
    code(f"""
# 2. Copy the pinned inputs from Drive and write launch.json
import hashlib, json, shutil
from pathlib import Path
SRC = Path('/content/drive/MyDrive/gemma_fasteval/launch/{TAG}')
HASHES = {json.dumps(HASHES, indent=1)}
DEST = {{'_lb022_inputs.tar': '/content/ab_inputs.tar', '_gpu_prep_ab.py': '/content/gpu_prep_ab.py',
        '_launch_if_ready.py': '/content/launch_if_ready.py', '_verify_model_dir.py': '/content/_verify_model_dir.py'}}
for name, target in DEST.items():
    shutil.copyfile(SRC / name, target)
    got = hashlib.sha256(Path(target).read_bytes()).hexdigest()
    assert got == HASHES[name], f'{{name}}: sha256 {{got[:12]}} != pinned {{HASHES[name][:12]}}'
    print('OK', name, got[:12])
LAUNCH = {json.dumps(LAUNCH, indent=1)}
Path('/content/launch.json').write_text(json.dumps(LAUNCH, indent=2) + '\\n')
out = Path('/content/drive/MyDrive/gemma_fasteval/ab_runs') / LAUNCH['tag']
assert not (out / 'progress.json').exists(), f'{{out}} already has results; use a new tag'
print('launch.json written; Drive output', out)
"""),
    code("""
# 3. Prep (env 19 GB + model archive 19 GB from Drive, extract, verify); polls until done (~20-40 min)
import runpy, time
from pathlib import Path
runpy.run_path('/content/gpu_prep_ab.py')
t0 = time.time()
while not Path('/content/prep.done').exists():
    time.sleep(60)
    log = Path('/content/prep.log').read_text(errors='replace').splitlines() if Path('/content/prep.log').exists() else []
    print(f'{(time.time() - t0) / 60:5.1f} min |', ' | '.join(log[-2:]), flush=True)
    if any(s in l for l in log for s in ('FAILED', 'MISSING', 'NOT VERIFIED')):
        raise SystemExit('PREP FAILED: read /content/prep.log, then delete the runtime')
print('\\n'.join(Path('/content/prep.log').read_text().splitlines()[-15:]))
"""),
    code("""
# 4. Launch the driver (detached; survives a dropped connection while the runtime lives)
import runpy
runpy.run_path('/content/launch_if_ready.py')
"""),
    code("""
# 5. Monitor every 5 min until ALL_DONE (keeping this cell running keeps the session active)
import json, time
from pathlib import Path
log, prog, done = Path('/content/ab.log'), Path('/content/ab/progress.json'), Path('/content/ab/ALL_DONE')
while not done.exists():
    passes = json.loads(prog.read_text())['passes'] if prog.exists() else []
    tail = log.read_text(errors='replace').splitlines()[-1:] if log.exists() else []
    print(time.strftime('%H:%M:%S'), f'passes done {len(passes)}/6 |', *tail, flush=True)
    time.sleep(300)
print('ALL_DONE:', done.read_text())
for p in json.loads(prog.read_text())['passes']:
    print({k: v for k, v in p.items() if not isinstance(v, (list, dict))})
print('Results are on Drive. Now disconnect and DELETE this runtime.')
"""),
]
nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "name": "python3"},
                                   "accelerator": "GPU", "colab": {"machine_shape": "hm"}},
      "nbformat": 4, "nbformat_minor": 5}
target = ROOT / "colab_fasteval" / "run_31b_lb022_ide.ipynb"
target.write_text(json.dumps(nb, indent=1) + "\n", encoding="utf-8", newline="\n")
for f, h in HASHES.items():
    print(f"{f:24s} {h[:12]}")
print("wrote", target)
