"""What is E4B's FIRST tool action, and does it split winners from losers?

31B opens with run_command (grep) in 28/35 tasks. If E4B opens with get_status
(a free-but-turn-consuming no-op), that is a real, prompt-caused behavioural tell
that is NOT an exhortation to try harder.
"""
import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
ACTION = re.compile(r'^\s*\[\s*[\d.]+s\]\s+\S+\s+(read_file|run_command|edit_file|write_file|get_status|submit_patch)\b', re.M)

RUNS = [('E4B', BASE / 'kaggle_pkg' / 'out_e4b' / 'results'),
        ('31B', BASE / 'kaggle_pkg' / 'out_v7' / 'results')]

for label, run in RUNS:
    rows = [json.loads(l) for l in (run / 'task_results.all.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()] \
        if (run / 'task_results.all.jsonl').exists() else None
    if rows is None:
        rec = json.loads((run.parent / 'recovered_full129.json').read_text(encoding='utf-8'))
        solved = set(rec['solved'])
        ids = [(r['instance_id'], r['instance_id'] in solved) for r in rec['rows']]
    else:
        ids = [(r['instance_id'], bool(r.get('resolved'))) for r in rows]
    logs = run / 'logs'
    S, U = Counter(), Counter()
    first_solved, first_unsolved = Counter(), Counter()
    for tid, ok in ids:
        lg = logs / (tid + '.log')
        if not lg.exists():
            continue
        acts = ACTION.findall(ANSI.sub('', lg.read_text(encoding='utf-8', errors='replace')))
        if not acts:
            continue
        (S if ok else U)[acts[0]] += 1
        # second action too
        if len(acts) > 1:
            (first_solved if ok else first_unsolved)[acts[1]] += 1
    ns, nu = sum(S.values()), sum(U.values())
    print('=' * 70)
    print('%s  first action  (solved n=%d | unsolved n=%d)' % (label, ns, nu))
    for tool in ('run_command', 'read_file', 'get_status', 'edit_file', 'submit_patch', 'write_file'):
        a, b = S[tool], U[tool]
        if a or b:
            print('   %-14s solved %3d (%3.0f%%)   unsolved %3d (%3.0f%%)'
                  % (tool, a, 100 * a / max(ns, 1), b, 100 * b / max(nu, 1)))
    print('   SECOND action, solved  : %s' % dict(first_solved.most_common(4)))
