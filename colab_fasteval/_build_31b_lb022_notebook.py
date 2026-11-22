"""Generate colab_fasteval/run_31b_lb022_ide.ipynb: the template chain (_ab_chain.sh) as notebook cells, for running
through the Colab connector add-on. Follows the conventions of train/colab_repair_decisions_v1_visible.ipynb: a
settings cell with explicit approval, visible rate and balance; a Drive-consent gate; a CU ceiling that includes
setup; one-GPU, fresh-runtime, disk and pinned-version checks; runtime.json at start and outcome.json at the end on
Drive. Inputs are read from MyDrive/gemma_fasteval/launch/<tag>/ with SHA-256 pinned from the local copies.
usage: python colab_fasteval/_build_31b_lb022_notebook.py"""
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
# the Kaggle-matched environment (L18758; same versions as every Kaggle run: wheelhouse globbed=41)
PINNED = {"vllm": "0.19.1", "torch": "2.10.0", "transformers": "5.13.1", "compressed-tensors": "0.15.0.1",
          "adk-submission": "0.2.13", "swegemma": "0.2.11"}
MAX_RATE = 12.0  # CU/h; G4 measured ~10 (L18944)
SETUP_H = 1.0  # prep (env + archive copy/extract + snapshots) counted in the ceiling
APPROVAL_TEXT = "run 31b lb022 ab"


def code(src):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": src.strip("\n").splitlines(keepends=True)}


def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src.strip("\n").splitlines(keepends=True)}


cells = [
    md(f"""
# 31B six-arm A/B: ca5 vs public 0.22 configs (Colab connector)
Pre-registered in `GEMMA_EXPERIMENT_LOG.md` (2026-11-22). Arms: A_ca5, B_denpug, C_flex, D_bliver, E_ayush_noad,
F_ayush_lora; the 85 live tasks; 1 round; 6 tasks at once. Results: `MyDrive/gemma_fasteval/ab_runs/{TAG}`.

To run:
1. Connect to **one G4 (96 GB), High-RAM**. Read the visible rate (at most **{MAX_RATE} CU/hour**) and balance.
2. In the settings cell enter those two values, set `APPROVAL = "{APPROVAL_TEXT}"`, and set
   `DRIVE_CONSENT = "ready"` only when you are ready to approve the Drive prompt yourself.
3. Run the cells in order. The job ceiling is rate x ({LAUNCH['deadline_h']} h driver + {SETUP_H} h setup); the driver
   stops itself at {LAUNCH['deadline_h']} h. Estimate ~8.5 h, ~85 CU at 10 CU/h.

**When the last cell prints `ALL_DONE` (or any cell fails), disconnect and delete the runtime so it stops billing.**
"""),
    code("""
RATE_CU_PER_HOUR = None   # the visible Colab rate for this runtime
AVAILABLE_CU = None       # the visible balance
APPROVAL = ""             # set to the approval text in the cell above
DRIVE_CONSENT = ""        # set to "ready" when you are ready for the Drive prompt
print("SETTINGS_OK: continue with the next cell.", flush=True)
"""),
    code(f"""
# 1. Launch checks, Drive (consent appears here), GPU, fresh runtime, disk
import math, os, shutil, subprocess
from pathlib import Path
MAX_RATE, SETUP_H, DEADLINE_H = {MAX_RATE}, {SETUP_H}, {LAUNCH['deadline_h']}
if type(RATE_CU_PER_HOUR) not in (int, float) or not math.isfinite(RATE_CU_PER_HOUR) or not 0 < RATE_CU_PER_HOUR <= MAX_RATE:
    raise ValueError(f"Enter the visible rate (greater than 0, at most {{MAX_RATE}} CU/h)")
CEILING_CU = RATE_CU_PER_HOUR * (DEADLINE_H + SETUP_H)
if type(AVAILABLE_CU) not in (int, float) or not math.isfinite(AVAILABLE_CU) or AVAILABLE_CU < CEILING_CU:
    raise ValueError(f"Balance must cover the job ceiling of {{CEILING_CU:.1f}} CU")
if APPROVAL != "{APPROVAL_TEXT}":
    raise ValueError('Set APPROVAL = "{APPROVAL_TEXT}" to allow this bounded GPU run')
for stale in ('/content/venv', '/content/prep.done', '/content/ab', '/content/model'):
    if Path(stale).exists():
        raise FileExistsError(f"{{stale}} exists from an earlier run; use a fresh runtime")
out = subprocess.check_output(['nvidia-smi', '--query-gpu=index,name,memory.total', '--format=csv,noheader,nounits'],
                              text=True, timeout=15)
devices = [l.split(',', 2) for l in out.splitlines() if l.strip()]
if len(devices) != 1 or int(devices[0][2]) < 75000:
    raise RuntimeError(f"One GPU with >= 80 GB required (G4 96 GB); saw {{out.strip()}}")
DEVICE = {{'index': int(devices[0][0]), 'name': devices[0][1].strip(), 'memory_mib': int(devices[0][2])}}
free_gb = shutil.disk_usage('/content').free / 2**30
if free_gb < 100:  # env tar 19 + env 19 + archive 19 + model 23 + snapshots ~14, overlapping during prep
    raise OSError(f"Need ~100 GiB free on /content for prep; have {{free_gb:.0f}}")
if not Path('/content/drive/MyDrive').is_dir():
    if DRIVE_CONSENT != "ready":
        raise RuntimeError('When you are ready for the Drive prompt, set DRIVE_CONSENT = "ready" and rerun.')
    from google.colab import drive
    drive.mount('/content/drive')
if not Path('/content/drive/MyDrive').is_dir():
    raise RuntimeError("The Drive mount did not expose MyDrive.")
print('LAUNCH_CHECKS_OK', DEVICE, f'free {{free_gb:.0f}} GiB, ceiling {{CEILING_CU:.1f}} CU')
"""),
    code(f"""
# 2. Copy the pinned inputs from Drive; write launch.json and runtime.json
import hashlib, json, time
STARTED = time.time()
SRC = Path('/content/drive/MyDrive/gemma_fasteval/launch/{TAG}')
HASHES = {json.dumps(HASHES, indent=1)}
DEST = {{'_lb022_inputs.tar': '/content/ab_inputs.tar', '_gpu_prep_ab.py': '/content/gpu_prep_ab.py',
        '_launch_if_ready.py': '/content/launch_if_ready.py', '_verify_model_dir.py': '/content/_verify_model_dir.py'}}
for name, target in DEST.items():
    shutil.copyfile(SRC / name, target)
    got = hashlib.sha256(Path(target).read_bytes()).hexdigest()
    if got != HASHES[name]:
        raise ValueError(f'{{name}}: sha256 {{got[:12]}} != pinned {{HASHES[name][:12]}}')
    print('OK', name, got[:12])
LAUNCH = {json.dumps(LAUNCH, indent=1)}
Path('/content/launch.json').write_text(json.dumps(LAUNCH, indent=2) + '\\n')
RUN = Path('/content/drive/MyDrive/gemma_fasteval/ab_runs') / LAUNCH['tag']
if RUN.exists() and any(RUN.iterdir()):
    raise FileExistsError(f'{{RUN}} is not empty; use a new tag')
RUN.mkdir(parents=True, exist_ok=True)
(RUN / 'runtime.json').write_text(json.dumps({{
    'device': DEVICE, 'reported_cu_per_hour': RATE_CU_PER_HOUR, 'reported_available_cu': AVAILABLE_CU,
    'job_cu_ceiling': CEILING_CU, 'launch': LAUNCH, 'input_sha256': HASHES,
    'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(STARTED))}}, indent=2) + '\\n')
print('runtime.json written to', RUN)
"""),
    code(f"""
# 3. Prep (env 19 GB + model archive 19 GB from Drive, extract, verify); polls until done (~20-40 min)
import runpy
PINNED = {json.dumps(PINNED)}
runpy.run_path('/content/gpu_prep_ab.py')
while not Path('/content/prep.done').exists():
    time.sleep(60)
    log = Path('/content/prep.log').read_text(errors='replace').splitlines() if Path('/content/prep.log').exists() else []
    print(f'{{(time.time() - STARTED) / 60:5.1f}} min |', ' | '.join(log[-2:]), flush=True)
    if any(s in l for l in log for s in ('FAILED', 'MISSING', 'NOT VERIFIED')):
        raise SystemExit('PREP FAILED: read /content/prep.log, then delete the runtime')
    if time.time() - STARTED > SETUP_H * 2 * 3600:
        raise TimeoutError('Prep exceeded twice its budget; read /content/prep.log, then delete the runtime')
# local build tags (torch 2.10.0+cu128) are not version differences; compare the release number only
probe = ('import importlib.metadata as m, json; '
         'print(json.dumps({{n: m.version(n).split("+")[0] for n in %r}}))' % list(PINNED))
installed = json.loads(subprocess.check_output(['/content/venv/bin/python', '-c', probe], text=True))
if installed != PINNED:
    raise ValueError(f'Restored environment differs from the Kaggle-matched set: {{installed}}')
(RUN / 'environment_preflight.json').write_text(json.dumps(installed, indent=2) + '\\n')
print('ENV_OK', installed)
print('\\n'.join(Path('/content/prep.log').read_text().splitlines()[-12:]))
"""),
    code("""
# 4. Launch the driver (detached; survives a dropped connection while the runtime lives)
runpy.run_path('/content/launch_if_ready.py')
"""),
    code("""
# 5. Monitor every 5 min until ALL_DONE (keeping this cell running keeps the session active); outcome.json at the end
log, prog, done = Path('/content/ab.log'), Path('/content/ab/progress.json'), Path('/content/ab/ALL_DONE')
outcome = {'status': 'incomplete'}
try:
    while not done.exists():
        passes = json.loads(prog.read_text())['passes'] if prog.exists() else []
        tail = log.read_text(errors='replace').splitlines()[-1:] if log.exists() else []
        print(time.strftime('%H:%M:%S'), f'passes done {len(passes)}/6 |', *tail, flush=True)
        time.sleep(300)
    passes = json.loads(prog.read_text())['passes']
    outcome.update(status='all_done', all_done=done.read_text(), passes=len(passes))
    for p in passes:
        print({k: v for k, v in p.items() if not isinstance(v, (list, dict))})
finally:
    outcome['elapsed_seconds'] = round(time.time() - STARTED)
    outcome['estimated_cu_at_entered_rate'] = round(outcome['elapsed_seconds'] * RATE_CU_PER_HOUR / 3600, 2)
    (RUN / 'outcome.json').write_text(json.dumps(outcome, indent=2) + '\\n')
    print('OUTCOME', outcome)
print('Results are on Drive. Now disconnect and DELETE this runtime.')
"""),
]
nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python",
                                                  "name": "python3"},
                                   "accelerator": "GPU", "colab": {"machine_shape": "hm"}},
      "nbformat": 4, "nbformat_minor": 5}
target = ROOT / "colab_fasteval" / "run_31b_lb022_ide.ipynb"
target.write_text(json.dumps(nb, indent=1) + "\n", encoding="utf-8", newline="\n")
for f, h in HASHES.items():
    print(f"{f:24s} {h[:12]}")
print("wrote", target)
