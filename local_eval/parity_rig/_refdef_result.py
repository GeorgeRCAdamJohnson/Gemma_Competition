"""Def-substitute arm vs baseline on the 7 reference-vs-definition tasks (log L14680 cohort)."""
import json
from pathlib import Path

RIG = Path(__file__).resolve().parent
COHORT = ['fastapi_14372', 'fastapi_14458', 'fastapi_14492', 'fastapi_9555',
          'rich_3067', 'rich_3480', 'rich_4077']
RUNS = {'base r0': RIG / 'm1_capped' / 'agent_ctrl_e4b_r0',
        'base r1': RIG / 'm1_capped' / 'agent_ctrl_e4b_r1',
        'base fa': RIG / 'm1_faithful' / 'agent_ctrl_e4b_r0',
        'DEF arm': RIG / 'm1_refdef' / 'agent_ctrl_e4b_def_r0'}


def load(d):
    f = Path(d) / 'task_results.jsonl'
    if not f.exists():
        return {}
    return {r['instance_id']: r for r in
            (json.loads(l) for l in f.read_text(encoding='utf-8').splitlines() if l.strip())}


recs = {k: load(d) for k, d in RUNS.items()}
print('%-16s %s' % ('task', ' '.join('%-8s' % k for k in RUNS)))
for t in COHORT:
    cells = []
    for k in RUNS:
        r = recs[k].get(t) or {}
        cells.append('%-8s' % ('SOLVED' if r.get('resolved') else '.'))
    print('%-16s %s' % (t, ' '.join(cells)))

print()
base_best = sum(1 for t in COHORT if any((recs[k].get(t) or {}).get('resolved')
                                         for k in ('base r0', 'base r1', 'base fa')))
base_mean = sum(sum(1 for k in ('base r0', 'base r1', 'base fa')
                    if (recs[k].get(t) or {}).get('resolved')) for t in COHORT) / 3
arm = sum(1 for t in COHORT if (recs['DEF arm'].get(t) or {}).get('resolved'))
print('baseline: mean %.2f/7   best-of-3 %.0f/7' % (base_mean, base_best))
print('DEF arm : %d/7' % arm)
base_union = {t for t in COHORT if any((recs[k].get(t) or {}).get('resolved')
                                       for k in ('base r0', 'base r1', 'base fa'))}
arm_set = {t for t in COHORT if (recs['DEF arm'].get(t) or {}).get('resolved')}
print('\nDEF-only solves :', sorted(arm_set - base_union) or 'none')
print('baseline-only   :', sorted(base_union - arm_set) or 'none')
print('both            :', sorted(arm_set & base_union) or 'none')
print('\nDEF arm wrong-file / no-edit:')
import re
FILES = re.compile(r'^\+\+\+ b/(.*?)$', re.M)
gold = {}
for line in (RIG.parents[1] / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines():
    if line.strip():
        r = json.loads(line)
        gold[r['instance_id']] = set(FILES.findall(r.get('patch') or ''))
for t in COHORT:
    p = RUNS['DEF arm'] / 'patches' / f'{t}.patch'
    f = set(FILES.findall(p.read_text(encoding='utf-8', errors='replace'))) if p.exists() else set()
    tag = 'no_edit' if not f else ('wrong_file' if gold.get(t) and not (f & gold[t]) else 'gold_file')
    print('  %-16s %-11s %s' % (t, tag, sorted(f)[:2]))
