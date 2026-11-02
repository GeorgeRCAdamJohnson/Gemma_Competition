"""Push a CPU-only Kaggle kernel that replays the same patches through verification.

No model, no GPU. If the local-only solves also resolve here, the sandbox is not the
difference and the gap is model/backend. If they fail here, our local rates are inflated
by environment.
"""
import base64
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RIG = ROOT / 'local_eval' / 'parity_rig'
OUT = ROOT / 'kaggle_pkg' / os.environ.get('RP_DIR', 'push_replay')
OUT.mkdir(parents=True, exist_ok=True)

PATCHDIR = Path(os.environ.get('RP_PATCHDIR', str(RIG / 'm1_full129' / 'ca5' / 'patches')))
DEFAULT_IDS = ['fastapi_9753', 'requests_7309', 'requests_7315', 'requests_7427',
               'fastapi_14616', 'fastapi_9425', 'rich_3067', 'rich_3882']
IDS = [s for s in (os.environ.get('RP_IDS') or '').split(',') if s] or DEFAULT_IDS
KID = os.environ.get('RP_KID', 'comfyops/replay-verify')
KTITLE = os.environ.get('RP_TITLE', 'replay verify')
PATCHES = {}
for tid in IDS:
    p = PATCHDIR / f'{tid}.patch'
    if p.exists():
        PATCHES[tid] = base64.b64encode(p.read_bytes()).decode()
print('missing patches:', [t for t in IDS if t not in PATCHES])

runner = (RIG / 'replay_verify2.py').read_text(encoding='utf-8')

CELL = r'''
import base64, json, os, subprocess, sys
from pathlib import Path

print('input:', sorted(os.listdir('/kaggle/input')))
TASKS = None
for root, dirs, files in os.walk('/kaggle/input'):
    if 'tasks.jsonl' in files:
        TASKS = Path(root) / 'tasks.jsonl'
        break
SNAPS = None
for root, dirs, files in os.walk('/kaggle/input'):
    if any(f.endswith('.tgz') for f in files):
        SNAPS = Path(root)
        break
print('tasks:', TASKS)
print('snaps:', SNAPS)
assert TASKS and SNAPS

PATCHES = json.loads("""__PATCHES__""")
PD = Path('/kaggle/working/patches'); PD.mkdir(parents=True, exist_ok=True)
for tid, b64 in PATCHES.items():
    (PD / f'{tid}.patch').write_bytes(base64.b64decode(b64))
print('patches written:', len(PATCHES))

RUNNER = Path('/kaggle/working/replay_verify2.py')
RUNNER.write_bytes(base64.b64decode("""__RUNNER_B64__"""))

env = dict(os.environ, REPLAY_OUT='/kaggle/working/replay_result.json')
p = subprocess.run([sys.executable, str(RUNNER), str(TASKS), str(SNAPS), str(PD)] + sorted(PATCHES),
                   capture_output=True, text=True, env=env)
print(p.stdout)
print('STDERR', p.stderr[-1500:])
res = json.loads(Path('/kaggle/working/replay_result.json').read_text())
print('=== KAGGLE-SIDE REPLAY ===')
for r in res:
    print('%-22s resolved=%-6s counts=%s err=%s' % (r['task'], r.get('resolved_here'),
          r.get('counts'), (r.get('error') or '')[:40]))
print('resolved on Kaggle: %d / %d' % (sum(1 for r in res if r.get('resolved_here')), len(res)))
'''

cell_src = (CELL.replace('__PATCHES__', json.dumps(PATCHES))
            .replace('__RUNNER_B64__', base64.b64encode(runner.encode()).decode()))

nb = {
    "cells": [
        {"cell_type": "markdown", "metadata": {}, "source": [
            "# Replay verification, no model\n\n"
            "Applies 8 patches (that resolved LOCALLY) to the base snapshots, applies the official\n"
            "test_patch, and runs exactly the test nodes swegemma would run. CPU only.\n\n"
            "Purpose: is the local sandbox the reason these tasks resolve locally but not on Kaggle?\n"]},
        {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
         "source": cell_src.splitlines(keepends=True)},
    ],
    "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                 "language_info": {"name": "python"}},
    "nbformat": 4, "nbformat_minor": 5,
}
path = OUT / 'replay-verify.ipynb'
path.write_text(json.dumps(nb, indent=1), encoding='utf-8')

meta = {
    "id": KID,
    "title": KTITLE,
    "code_file": "replay-verify.ipynb",
    "language": "python",
    "kernel_type": "notebook",
    "is_private": True,
    "enable_gpu": False,
    "enable_tpu": False,
    "enable_internet": False,
    "keywords": [],
    "dataset_sources": ["comfyops/gemma129-taskdefs", "comfyops/gemma129-snapshots"],
    "kernel_sources": [],
    "competition_sources": [],
    "model_sources": [],
    "docker_image": "gcr.io/kaggle-private-byod/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461",
}
(OUT / 'kernel-metadata.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
print('patches embedded:', len(PATCHES), '| notebook', path.stat().st_size, 'B | gpu', meta['enable_gpu'])
