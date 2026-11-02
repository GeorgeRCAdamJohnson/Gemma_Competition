"""Wrong-file / failure profile for any local pool run (e.g. the 12B ca5 run).

Answers: is the E4B defect (29% wrong file) also present in 12B? If yes, the mechanism
test can be run locally on 12B and E4B is not needed.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
NEWF = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)
DIFF = re.compile(r'^diff --git a/(.+?) b/', re.M)

TASKS = {json.loads(l)['instance_id']: json.loads(l)
         for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()}


def gold(t):
    txt = t.get('patch', '') or ''
    return {m.group(1).strip() for m in NEWF.finditer(txt)} | set(DIFF.findall(txt))


def run(path: Path, label: str):
    p = path / 'results' / 'task_results.jsonl'
    alt = path / 'task_results.jsonl'
    f = p if p.exists() else alt
    if not f.exists():
        print('%s: no results at %s' % (label, f))
        return
    rows = [json.loads(l) for l in f.read_text(encoding='utf-8').splitlines() if l.strip()]
    logs = path / 'results' / 'logs'
    if not logs.exists():
        logs = path / 'logs'
    patches = path / 'results' / 'patches'
    if not patches.exists():
        patches = path / 'patches'

    c = Counter()
    for r in rows:
        tid = r['instance_id']
        if r.get('resolved'):
            c['solved'] += 1
            continue
        lg = logs / (tid + '.log')
        txt = ANSI.sub('', lg.read_text(encoding='utf-8', errors='replace')) if lg.exists() else ''
        if 'edit_file' not in txt:
            c['no_edit'] += 1
            continue
        pp = patches / (tid + '.patch')
        if not pp.exists():
            c['no_patch'] += 1
            continue
        mine = {m.group(1).strip() for m in NEWF.finditer(pp.read_text(encoding='utf-8', errors='replace'))}
        g = gold(TASKS.get(tid, {}))
        c['wrong_file' if (mine and g and not (mine & g)) else 'overlap'] += 1

    n = len(rows)
    print('\n%-28s n=%d' % (label, n))
    for k in ('solved', 'overlap', 'wrong_file', 'no_patch', 'no_edit'):
        print('   %-12s %3d (%4.1f%%)' % (k, c[k], 100 * c[k] / n))


for arg in sys.argv[1:]:
    run(Path(arg), arg)
