"""Reproduce swegemma's exact verification command on one task to find the rc=0 cause."""
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TID = sys.argv[1] if len(sys.argv) > 1 else 'requests_7315'
ROOT = Path(__file__).resolve().parent
TASKS = ROOT.parent.parent / 'comp_files' / 'tasks.jsonl'
SNAPS = ROOT.parent / 'snapshots'
PATCHDIR = ROOT / 'm1_full129'

tasks = {}
for line in TASKS.read_text(encoding='utf-8').splitlines():
    if line.strip():
        r = json.loads(line)
        tasks[r['instance_id']] = r

snap = next(SNAPS.glob(f'{TID}.tgz'), None)
patches = sorted(PATCHDIR.glob(f'**/patches/{TID}.patch'))
print('snap:', snap)
print('patch:', patches[:1])

work = Path(tempfile.mkdtemp(prefix=f'rc_{TID}_'))
subprocess.run(['tar', 'xzf', str(snap), '-C', str(work)], check=True)
if patches:
    p = subprocess.run(['git', 'apply', '--whitespace=nowarn', str(patches[0].resolve())],
                       cwd=str(work), capture_output=True, text=True)
    print('agent patch rc:', p.returncode, p.stderr[-200:])
tp_text = tasks[TID].get('test_patch') or ''
tp = work.parent / f'{TID}_t.patch'
tp.write_text(tp_text if tp_text.endswith('\n') else tp_text + '\n', encoding='utf-8')
p = subprocess.run(['git', 'apply', '--whitespace=nowarn', str(tp)], cwd=str(work),
                   capture_output=True, text=True)
print('test patch rc:', p.returncode, p.stderr[-200:])

files = sorted({f.strip() for f in re.findall(r'^\+\+\+ b/(.*?)$', tp_text, re.M)})
targets = ' '.join(files) or '.'
print('targets:', targets)

variants = {
    'plain-file': [sys.executable, '-m', 'pytest', targets, '-q'],
    'harness-flags': [sys.executable, '-m', 'pytest', targets, '-q',
                      '-p', 'no:anyio', '-o', 'timeout=0',
                      '-o', 'python_classes=Test* *Test'],
    'harness-full': [sys.executable, '-s', '-m', 'pytest', targets, '-q',
                     '-p', 'no:anyio', '-o', 'timeout=0',
                     '-o', 'python_classes=Test* *Test',
                     '--junitxml=/tmp/j.xml'],
}
env = dict(__import__('os').environ)
for name, cmd in variants.items():
    e = dict(env)
    if name == 'harness-full':
        e['PYTHONSAFEPATH'] = '1'
        e['PYTHONNOUSERSITE'] = '1'
    p = subprocess.run(cmd, cwd=str(work), capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=e)
    tail = (p.stdout or '').strip().splitlines()[-3:]
    print(f'{name:14s} rc={p.returncode}  {tail}')
shutil.rmtree(work, ignore_errors=True)
