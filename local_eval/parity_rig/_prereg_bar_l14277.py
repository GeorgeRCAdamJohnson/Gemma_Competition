"""Locate arm vs baseline on the SHARED cohort, using the pre-registered metric from log L14277."""
import json
import re
from pathlib import Path

RIG = Path(__file__).resolve().parent
TASKS = RIG.parents[1] / 'comp_files' / 'tasks.jsonl'
FILES = re.compile(r'^\+\+\+ b/(.*?)$', re.M)

gold = {}
for line in TASKS.read_text(encoding='utf-8').splitlines():
    if line.strip():
        r = json.loads(line)
        gold[r['instance_id']] = set(FILES.findall(r.get('patch') or ''))


def load(d):
    f = Path(d) / 'task_results.jsonl'
    return {r['instance_id']: r for r in
            (json.loads(x) for x in f.read_text(encoding='utf-8').splitlines() if x.strip())}


def classify(d, ids):
    wrong = noedit = ok = 0
    for t in ids:
        p = Path(d) / 'patches' / f'{t}.patch'
        files = set(FILES.findall(p.read_text(encoding='utf-8', errors='replace'))) if p.exists() else set()
        if not files:
            noedit += 1
        elif gold.get(t) and not (files & gold[t]):
            wrong += 1
        else:
            ok += 1
    return wrong, noedit, ok


ARMS = [('baseline r0', RIG / 'm1_capped' / 'agent_ctrl_e4b_r0'),
        ('baseline r1', RIG / 'm1_capped' / 'agent_ctrl_e4b_r1'),
        ('locate arm', RIG / 'm1_locate' / 'agent_ctrl_e4b_locate_r0')]

recs = {n: load(d) for n, d in ARMS if (Path(d) / 'task_results.jsonl').exists()}
shared = sorted(set.intersection(*[set(r) for r in recs.values()]))
print('shared tasks across arms:', len(shared))
print()
print('%-14s %-9s %-13s %-11s %-11s' % ('arm', 'solved', 'wrong_file', 'no_edit', 'gold_file'))
for n, d in ARMS:
    if n not in recs:
        continue
    R = recs[n]
    w, ne, ok = classify(d, shared)
    s = sum(1 for t in shared if R[t].get('resolved'))
    print('%-14s %-9s %-13s %-11s %-11s' % (
        n, f'{s}/{len(shared)}', f'{w} ({100*w/len(shared):.1f}%)',
        f'{ne} ({100*ne/len(shared):.0f}%)', f'{ok} ({100*ok/len(shared):.0f}%)'))
print()
print('PRE-REGISTERED BAR (log L14277): wrong_file < 20% AND solved >= 13/129')
