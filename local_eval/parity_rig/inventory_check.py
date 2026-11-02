"""Corrected benchmark inventory after the outside review's M1/M2/M11/M12."""
import json
from pathlib import Path

RIG = Path(r'C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval\parity_rig')
PH = {'requests_7309', 'requests_7315', 'requests_7427'}
RUNS = {'r0': RIG / 'm1_capped' / 'agent_ctrl_e4b_r0',
        'r1': RIG / 'm1_capped' / 'agent_ctrl_e4b_r1',
        'fa': RIG / 'm1_faithful' / 'agent_ctrl_e4b_r0',
        'np': RIG / 'm1_noprompt129' / 'agent_ctrl_e4b_noprompt_r0'}


def rs(p):
    p = Path(p)
    if not p.exists():
        return set()
    return {r['task'] for r in json.loads(p.read_text(encoding='utf-8')) if r.get('resolved_here')}


old_gold = rs(RIG / 'replay_gold129_files.json') | rs(RIG.parents[1] / 'kaggle_pkg' / 'out_gold_fa' / 'replay_result.json')
new_gold = rs(RIG / 'replay_gold129_files_skiptol.json') | rs(RIG.parents[1] / 'kaggle_pkg' / 'out_gold_fa' / 'replay_result.json')
empty = rs(RIG / 'replay_empty129_files.json')

print('gold-valid:  old (skips=fail) %d   ->  corrected (skips tolerated) %d' % (len(old_gold), len(new_gold)))
print('newly gold-valid: %d' % len(new_gold - old_gold))
print('degenerate (empty patch passes): %d %s' % (len(empty), sorted(empty)))
solv_old = old_gold - empty
solv_new = new_gold - empty
print('truly solvable: old %d  ->  corrected %d' % (len(solv_old), len(solv_new)))
print('repos (corrected):', {r: sum(1 for t in solv_new if t.startswith(r))
                             for r in ('fastapi', 'rich', 'requests', 'httpx')})

# official grader ground truth: any task it resolved IS solvable
import re
off = {r['instance_id']: r for r in
       (json.loads(l) for l in (RIG.parents[1] / 'kaggle_pkg' / 'out_e4b' / 'results' / 'task_results.all.jsonl').read_text(encoding='utf-8').splitlines() if l.strip())}
off_solved = {t for t, r in off.items() if r.get('resolved')}
print('\nofficial grader resolved %d tasks; of those, %d were NOT in the old solvable set: %s' % (
    len(off_solved), len(off_solved - solv_old), sorted(off_solved - solv_old)))
print('  of those, now in the corrected set: %d' % len((off_solved - solv_old) & solv_new))


def load(d):
    return {r['instance_id']: r for r in
            (json.loads(l) for l in (Path(d) / 'task_results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip())}


recs = {k: load(d) for k, d in RUNS.items()}
ids = sorted(set.intersection(*[set(v) for v in recs.values()]))
gen = {k: {t for t in ids if recs[k][t].get('resolved')} - PH for k in RUNS}

for label, S in [('OLD inventory', solv_old), ('CORRECTED inventory', solv_new)]:
    print('\n%s (%d tasks)' % (label, len(S)))
    for k in ('r0', 'r1', 'fa', 'np'):
        v = {t for t in gen[k] if t in S}
        print('  %-4s gold-valid genuine %2d/%d = %.1f%%' % (k, len(v), len(S), 100 * len(v) / len(S)))
    stable = {t for t in S if all(t in gen[k] for k in ('r0', 'r1', 'fa'))}
    print('  ca5 stable gold-valid core: %d -> %s' % (len(stable), sorted(stable)))
