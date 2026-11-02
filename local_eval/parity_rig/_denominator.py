"""What is the real denominator? gold-winnable vs empty-winnable vs our solves."""
import json
from collections import Counter
from pathlib import Path

RIG = Path(__file__).resolve().parent
PHANTOM = {'requests_7309', 'requests_7315', 'requests_7427'}
RUNS = {
    'r0': RIG / 'm1_capped' / 'agent_ctrl_e4b_r0',
    'r1': RIG / 'm1_capped' / 'agent_ctrl_e4b_r1',
    'fa': RIG / 'm1_faithful' / 'agent_ctrl_e4b_r0',
}


def resolved_set(p):
    if not Path(p).exists():
        return None
    rs = json.loads(Path(p).read_text(encoding='utf-8'))
    return {r['task'] for r in rs if r.get('resolved_here')}


gold = resolved_set(RIG / 'replay_gold129_files.json')
empty = resolved_set(RIG / 'replay_empty129_files.json')

recs = {k: {r['instance_id']: r for r in
            (json.loads(l) for l in (Path(d) / 'task_results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip())}
        for k, d in RUNS.items()}
ids = sorted(set.intersection(*[set(v) for v in recs.values()]))
solved = {k: {t for t in ids if recs[k][t].get('resolved')} for k in RUNS}
union = set().union(*solved.values()) - PHANTOM
mean_gen = sum(len(v - PHANTOM) for v in solved.values()) / 3

print('gold validates      :', len(gold), '/', len(ids))
if empty is not None:
    print('empty patch passes  :', len(empty), '/', len(ids))
    solvable = gold - empty
    print('TRULY SOLVABLE      :', len(solvable), '(gold passes AND empty fails)')
else:
    solvable = gold
    print('(empty-patch run still in progress)')

print('\nrepo mix  gold:', dict(Counter(t.split("_")[0] for t in gold)))
print('repo mix  our solves:', dict(Counter(t.split("_")[0] for t in union)))

print('\nour genuine union: %d  (mean per run %.2f)' % (len(union), mean_gen))
print('  inside gold-winnable:', len(union & gold))
print('  OUTSIDE gold-winnable (our patch passes where gold does not):', sorted(union - gold))
print()
if solvable:
    print('rate on TRULY SOLVABLE : %d/%d = %.1f%%  (mean per run %.1f/%d = %.1f%%)' % (
        len(union & solvable), len(solvable), 100 * len(union & solvable) / len(solvable),
        mean_gen, len(solvable), 100 * mean_gen / len(solvable)))
print('rate on all 129        : %.1f%%' % (100 * mean_gen / 129))
