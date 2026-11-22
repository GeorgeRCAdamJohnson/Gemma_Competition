"""Generate colab_fasteval/run_31b_lb022_ide.ipynb: the template chain (_ab_chain.sh) as notebook cells, for running
through the Colab connector add-on. Follows train/colab_repair_decisions_v1_visible.ipynb: a settings cell; a CPU
dry-run mode (like its `inspect`) that checks every input the GPU run needs without creating anything on Drive; a
Drive-consent gate; in GPU mode a CU ceiling that includes setup, a pinned-version check and runtime/outcome receipts.
Inputs are read from MyDrive/gemma_fasteval/launch/<tag>/ with SHA-256 pinned from the local copies.
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
# sizes as listed on 2026-11-22 (Drive: colab_env.tar; user upload of the Kaggle /2 archive)
ENV_TAR_BYTES = 19220930560
ARCHIVE_BYTES = 19348664473
MAX_RATE = 12.0  # CU/h; G4 measured ~10 (L18944)
SETUP_H = 1.0  # prep (env + archive copy/extract + snapshots) counted in the ceiling
# arm fingerprints from _build_arms_31b_lb022.py (sha1 over sorted file bytes)
ARM_SHAS = {"A_ca5": "135bacd909cd", "B_denpug": "0a4c009b17ec", "C_flex": "328f689eca0f", "D_bliver": "abc861feada8",
            "E_ayush_noad": "151b922c5d75", "F_ayush_lora": "1185547f0fab"}


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

**1. Dry run on CPU first** (`MODE = "dry_run"`, any runtime). Checks Drive, the pinned inputs, all six arms, the 85
tasks and their snapshots, the environment snapshot, the model archive layout, the runner and the prep script.
Creates nothing on Drive and starts no GPU work. Ends with `DRY_RUN_OK`.

**2. GPU run** (`MODE = "gpu"`) on **one G4 (96 GB), High-RAM**, connected through the add-on's server picker. Enter the
visible rate (at most {MAX_RATE} CU/h) and balance. The job ceiling is rate x ({LAUNCH['deadline_h']} h + {SETUP_H} h setup);
the driver stops itself at {LAUNCH['deadline_h']} h. Estimate ~8.5 h, ~85 CU at 10 CU/h.

Set `DRIVE_CONSENT = "ready"` only when you are ready to approve the Drive prompt yourself.
**When the last cell prints `ALL_DONE` (or any cell fails in GPU mode), disconnect and delete the runtime.**
"""),
    code("""
MODE = "dry_run"          # "dry_run" (CPU, checks only) or "gpu" (the real run)
RATE_CU_PER_HOUR = None   # gpu mode: the visible Colab rate for this runtime
AVAILABLE_CU = None       # gpu mode: the visible balance
DRIVE_CONSENT = ""        # set to "ready" when you are ready for the Drive prompt
print(f"SETTINGS_OK: mode={MODE}. Continue with the next cell.", flush=True)
"""),
    code(f"""
# 1. Mode checks, GPU detection, Drive (consent appears here)
import math, os, shutil, subprocess
from pathlib import Path
MAX_RATE, SETUP_H, DEADLINE_H = {MAX_RATE}, {SETUP_H}, {LAUNCH['deadline_h']}
if MODE not in ("dry_run", "gpu"):
    raise ValueError('MODE must be "dry_run" or "gpu"')
DRY = MODE == "dry_run"


def find_gpu():
    # nvidia-smi is not always on the kernel PATH (Colab images use /opt/bin or /usr/local/nvidia/bin)
    for exe in [shutil.which('nvidia-smi'), '/opt/bin/nvidia-smi', '/usr/local/nvidia/bin/nvidia-smi', '/usr/bin/nvidia-smi']:
        if exe and Path(exe).is_file():
            out = subprocess.check_output([exe, '--query-gpu=index,name,memory.total', '--format=csv,noheader,nounits'],
                                          text=True, timeout=15)
            return [dict(index=int(i), name=n.strip(), memory_mib=int(m))
                    for i, n, m in (l.split(',', 2) for l in out.splitlines() if l.strip())]
    try:
        import torch
        if torch.cuda.is_available():
            return [dict(index=i, name=torch.cuda.get_device_name(i),
                         memory_mib=torch.cuda.get_device_properties(i).total_memory // 2**20)
                    for i in range(torch.cuda.device_count())]
    except ImportError:
        pass
    return []


DEVICES = find_gpu()
print('GPUs:', DEVICES or 'none (CPU runtime)')
free_gb = shutil.disk_usage('/content').free / 2**30
print(f'/content free: {{free_gb:.0f}} GiB')
CEILING_CU = None
if not DRY:
    if len(DEVICES) != 1 or DEVICES[0]['memory_mib'] < 75000:
        raise RuntimeError(f"GPU mode needs one GPU with >= 80 GB (G4 96 GB); found {{DEVICES or 'none'}}. "
                           "In VS Code: Select Kernel > Colab > New Colab Server > G4.")
    if type(RATE_CU_PER_HOUR) not in (int, float) or not math.isfinite(RATE_CU_PER_HOUR) or not 0 < RATE_CU_PER_HOUR <= MAX_RATE:
        raise ValueError(f"Enter the visible rate (greater than 0, at most {{MAX_RATE}} CU/h)")
    CEILING_CU = RATE_CU_PER_HOUR * (DEADLINE_H + SETUP_H)
    if type(AVAILABLE_CU) not in (int, float) or not math.isfinite(AVAILABLE_CU) or AVAILABLE_CU < CEILING_CU:
        raise ValueError(f"Balance must cover the job ceiling of {{CEILING_CU:.1f}} CU")
    if Path('/content/ab/progress.json').exists():
        raise FileExistsError("A driver already ran on this runtime (/content/ab/progress.json); use a fresh runtime")
    if free_gb < 100:  # env tar 19 + env 19 + archive 19 + model 23 + snapshots ~14, overlapping during prep
        print(f"WARNING: prep peaks near ~100 GiB on /content; this runtime has {{free_gb:.0f}} GiB")
DEVICE = DEVICES[0] if DEVICES else None
if not Path('/content/drive/MyDrive').is_dir():
    if DRIVE_CONSENT != "ready":
        raise RuntimeError('When you are ready for the Drive prompt, set DRIVE_CONSENT = "ready" and rerun.')
    from google.colab import drive
    drive.mount('/content/drive')
if not Path('/content/drive/MyDrive').is_dir():
    raise RuntimeError("The Drive mount did not expose MyDrive.")
print('CHECKS_OK', MODE, DEVICE, f'ceiling {{CEILING_CU:.1f}} CU' if CEILING_CU else '')
"""),
    code(f"""
# 2. Copy the pinned inputs from Drive (dry run: into /tmp, nothing created on Drive)
import hashlib, json, time
STARTED = time.time()
D = Path('/content/drive/MyDrive')
SRC = D / 'gemma_fasteval/launch/{TAG}'
HASHES = {json.dumps(HASHES, indent=1)}
BASE = Path('/tmp/lb022_dry') if DRY else Path('/content')
BASE.mkdir(parents=True, exist_ok=True)
DEST = {{'_lb022_inputs.tar': BASE / 'ab_inputs.tar', '_gpu_prep_ab.py': BASE / 'gpu_prep_ab.py',
        '_launch_if_ready.py': BASE / 'launch_if_ready.py', '_verify_model_dir.py': BASE / '_verify_model_dir.py'}}
for name, target in DEST.items():
    shutil.copyfile(SRC / name, target)
    got = hashlib.sha256(target.read_bytes()).hexdigest()
    if got != HASHES[name]:
        raise ValueError(f'{{name}}: sha256 {{got[:12]}} != pinned {{HASHES[name][:12]}}')
    print('OK', name, got[:12])
LAUNCH = {json.dumps(LAUNCH, indent=1)}
(BASE / 'launch.json').write_text(json.dumps(LAUNCH, indent=2) + '\\n')
RUN = D / 'gemma_fasteval/ab_runs' / LAUNCH['tag']
if RUN.exists() and any(RUN.iterdir()):
    raise FileExistsError(f'{{RUN}} is not empty; use a new tag')
if not DRY:
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / 'runtime.json').write_text(json.dumps({{
        'device': DEVICE, 'reported_cu_per_hour': RATE_CU_PER_HOUR, 'reported_available_cu': AVAILABLE_CU,
        'job_cu_ceiling': CEILING_CU, 'launch': LAUNCH, 'input_sha256': HASHES,
        'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(STARTED))}}, indent=2) + '\\n')
    print('runtime.json written to', RUN)
else:
    print('results folder', RUN, 'is free (not created in dry run)')
"""),
    code(f"""
# 3. Dry run: check everything prep and the driver will need. GPU mode: run prep (~20-40 min).
import runpy, tarfile, py_compile
PINNED = {json.dumps(PINNED)}
if DRY:
    C = D / 'gemma-4-developer-agent-cache'
    problems = []
    def need(ok, msg):
        print(('OK   ' if ok else 'FAIL ') + msg)
        if not ok:
            problems.append(msg)
    work = BASE / 'work'
    shutil.rmtree(work, ignore_errors=True)
    with tarfile.open(BASE / 'ab_inputs.tar') as t:
        t.extractall(work, filter='data')
    ARM_SHAS = {json.dumps(ARM_SHAS)}
    for arm, want in ARM_SHAS.items():
        a = work / 'arms' / arm
        fs = {{p.relative_to(a).as_posix(): p.read_bytes() for p in a.rglob('*') if p.is_file()}}
        got = hashlib.sha1(b''.join(fs[n] for n in sorted(fs))).hexdigest()[:12] if fs else None
        model = next((l.split(':', 1)[1].strip() for l in (a / 'agent.yaml').read_text().splitlines()
                      if l.startswith('model:')), None) if fs else None
        need(got == want and model == LAUNCH['model_name'], f'arm {{arm}} sha {{got}} model {{model}}')
    need(sorted(p.name for p in (work / 'arms').iterdir()) == sorted(ARM_SHAS), 'exactly the six registered arms')
    tasks = json.loads((work / 'ab_tasks.json').read_text())
    need(len(tasks) == 85 == len(set(tasks)), f'{{len(tasks)}} unique tasks')
    ids = {{json.loads(l).get('instance_id') or json.loads(l).get('id') for l in (work / 'tasks.jsonl').read_text().splitlines() if l}}
    need(set(tasks) <= ids, 'every task defined in tasks.jsonl')
    snaps = C / 'competitions/gemma-4-developer-agent/snapshots'
    missing = [t for t in tasks if not (snaps / f'{{t}}.tgz').is_file()]
    need(not missing, f'snapshots on Drive for all tasks (missing {{missing[:5]}})')
    try:
        py_compile.compile(str(work / 'gpu_ab_run.py'), doraise=True)
        src = (work / 'gpu_ab_run.py').read_text()
        need(all(s in src for s in ('ALL_DONE', 'AB_CONC', '--timeout-seconds', 'merged = {{}}')), 'runner compiles, current version')
    except py_compile.PyCompileError as e:
        need(False, f'runner compiles: {{e}}')
    prep = (BASE / 'gpu_prep_ab.py').read_text().split("SCRIPT = r'''", 1)[1].split("'''", 1)[0]
    (BASE / 'prep.sh').write_text(prep, newline='\\n')
    need(subprocess.run(['bash', '-n', str(BASE / 'prep.sh')]).returncode == 0, 'prep script syntax')
    env_tar = D / 'gemma_fasteval/colab_env/colab_env.tar'
    need(env_tar.is_file() and env_tar.stat().st_size == {ENV_TAR_BYTES}, f'environment snapshot {{env_tar.stat().st_size if env_tar.is_file() else "missing"}} B')
    cache = C / 'models/google/gemma-4/Other' / LAUNCH['model_name'] / '2'
    archive = D / LAUNCH['model_archive']
    if (cache / 'config.json').is_file():
        r = subprocess.run(['python3', str(BASE / '_verify_model_dir.py'), str(cache), LAUNCH['model_name']], capture_output=True, text=True)
        print(r.stdout)
        need(r.returncode == 0, 'model cache folder verified')
    else:
        need(archive.is_file() and archive.stat().st_size == {ARCHIVE_BYTES},
             f'model archive {{archive.stat().st_size if archive.is_file() else "missing"}} B')
        # read only the start of the gzip stream: member names and sizes (stops early, no full extract)
        names = []
        with tarfile.open(archive, 'r|gz') as t:
            for m in t:
                names.append((m.name, m.size))
                if len(names) >= 8 or m.name.endswith('model.safetensors'):
                    break
        print('archive starts with:', names)
        need(any(n.endswith('config.json') for n, _ in names) or any(n.endswith('.safetensors') for n, _ in names),
             'archive holds the checkpoint files')
    usable = shutil.disk_usage('/content').free / 2**30
    print(f'(info) this CPU runtime has {{usable:.0f}} GiB free; the G4 needs ~100 GiB for prep')
    if problems:
        raise SystemExit(f'DRY_RUN_FAILED: {{len(problems)}} problem(s): {{problems}}')
    print('DRY_RUN_OK: inputs, arms, tasks, snapshots, runner, prep script, environment and model are ready for GPU mode')
else:
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
# 4. Launch the driver (GPU mode only; detached, survives a dropped connection while the runtime lives)
if DRY:
    print('dry run: driver not launched')
else:
    runpy.run_path('/content/launch_if_ready.py')
"""),
    code("""
# 5. Monitor every 5 min until ALL_DONE (GPU mode); outcome.json at the end
if DRY:
    print('dry run complete. For the real run: connect a G4 server, set MODE = "gpu", rate and balance, run all cells.')
else:
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
