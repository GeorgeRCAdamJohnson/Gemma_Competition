"""Build the locate-arm cohort from the LOCAL 12B baseline.

Defect population = unsolved tasks whose patch touched no gold file AND whose log
never referenced a gold file (search failures). Controls = the baseline's solved set,
so a regression is visible.
"""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
RUN = BASE / 'local_eval' / 'parity_rig' / 'm1_full129' / 'ca5'
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
NEWF = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)
DIFF = re.compile(r'^diff --git a/(.+?) b/', re.M)

TASKS = {json.loads(l)['instance_id']: json.loads(l)
         for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()}


def gold(t):
    txt = t.get('patch', '') or ''
    return {m.group(1).strip() for m in NEWF.finditer(txt)} | set(DIFF.findall(txt))


rows = [json.loads(l) for l in (RUN / 'task_results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
logs = RUN / 'logs'
patches = RUN / 'patches'

solved, defect = [], []
for r in rows:
    tid = r['instance_id']
    if r.get('resolved'):
        solved.append(tid)
        continue
    txt = ANSI.sub('', (logs / (tid + '.log')).read_text(encoding='utf-8', errors='replace')) \
        if (logs / (tid + '.log')).exists() else ''
    g = gold(TASKS.get(tid, {}))
    if not g:
        continue
    pp = patches / (tid + '.patch')
    mine = {m.group(1).strip() for m in NEWF.finditer(pp.read_text(encoding='utf-8', errors='replace'))} \
        if pp.exists() else set()
    wrong_file = bool(mine) and not (mine & g)
    never_read = not any(f in txt for f in g)
    if wrong_file and never_read:
        defect.append(tid)

print('12B baseline ca5: solved %d | defect (wrong-file AND never-read-gold) %d' % (len(solved), len(defect)))
print('\ncontrols (solved):')
print('  ', solved)
print('\ndefect cohort:')
for t in defect:
    print('  ', t)

cohort = defect + solved
print('\nTOTAL COHORT: %d tasks' % len(cohort))
out = BASE / 'local_eval' / 'parity_rig' / 'm1_locate' / 'cohort.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(dict(defect=defect, controls=solved, all=cohort), indent=1), encoding='utf-8')
print('wrote', out)
