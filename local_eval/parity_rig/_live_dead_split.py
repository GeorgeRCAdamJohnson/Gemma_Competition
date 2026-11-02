"""Definitive live/dead split of the 129 tasks, and what our solves mean inside it.

A task is DEAD if the official Kaggle eval image could not even collect its tests
(missing wheelhouse packages). Dead tasks are unresolvable for every submission.
"""
import json
import re
from collections import Counter
from pathlib import Path

RIG = Path(__file__).resolve().parent
KAGGLE_LOGS = RIG.parents[1] / 'kaggle_pkg' / 'out_e4b' / 'results' / 'test_outputs'
LOCAL_LOGS = RIG / 'm1_capped' / 'agent_ctrl_e4b_r0' / 'test_outputs'
RUNS = {
    'r0': RIG / 'm1_capped' / 'agent_ctrl_e4b_r0',
    'r1': RIG / 'm1_capped' / 'agent_ctrl_e4b_r1',
    'fa': RIG / 'm1_faithful' / 'agent_ctrl_e4b_r0',
}
PHANTOM = {'requests_7309', 'requests_7315', 'requests_7427'}


DEAD_MODULES = ('inline_snapshot', 'dirty_equals', 'scripts.prepare_release')


def blocked(d):
    """DEAD = collection failed on a third-party module absent from the wheelhouse.

    A collection error caused by the agent's own patch (e.g. cannot import name
    'may_v1') is an agent failure, NOT a dead task, so it is excluded here.
    """
    out = set()
    for p in d.glob('*.log'):
        t = p.read_text(encoding='utf-8', errors='replace')
        for m in re.findall(r"No module named '([^']+)'", t):
            if any(m == dm or m.startswith(dm) for dm in DEAD_MODULES):
                out.add(p.stem)
                break
    return out


kb, lb = blocked(KAGGLE_LOGS), blocked(LOCAL_LOGS)
dead = kb | lb
print('dead on Kaggle image :', len(kb))
print('dead on local rig    :', len(lb))
print('DEAD (union)         :', len(dead))

recs = {k: {r['instance_id']: r for r in
            (json.loads(l) for l in (Path(d) / 'task_results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip())}
        for k, d in RUNS.items()}
ids = sorted(set.intersection(*[set(v) for v in recs.values()]))
live = [t for t in ids if t not in dead]
print('live tasks           :', len(live), '(%.0f%% of 129)' % (100 * len(live) / 129))

solved = {k: {t for t in ids if recs[k][t].get('resolved')} for k in RUNS}
union = set().union(*solved.values()) - PHANTOM
union_live = union & set(live)
mean_gen = sum(len(v - PHANTOM) for v in solved.values()) / 3
print('\nrecorded mean %.2f  genuine mean %.2f  genuine union %d' % (
    sum(len(v) for v in solved.values()) / 3, mean_gen, len(union)))
print('genuine solves that are DEAD tasks:', sorted(union & dead) or 'none')
print('genuine union inside LIVE: %d / %d = %.1f%%' % (
    len(union_live), len(live), 100 * len(union_live) / len(live)))
print('genuine mean inside LIVE: %.2f / %d = %.1f%%' % (
    mean_gen, len(live), 100 * mean_gen / len(live)))

print('\n--- LB projection (58 public, ~%.0f%% dead) ---' % (100 * len(dead) / 129))
live58 = 58 * len(live) / 129
for label, rate in [('average draw', mean_gen / len(live)), ('reachable', len(union_live) / len(live))]:
    n = live58 * rate
    print('  %-13s rate=%.3f -> %.1f solves on 58 -> %.2f displayed' % (
        label, rate, n, int(n / 58 * 100) / 100))
print('  0.10 board top = 6/58 -> needs %.1f%% of live tasks' % (100 * 6 / live58))

print('\n--- dead-task repo mix ---')
print(' ', dict(Counter(t.split('_')[0] for t in dead)))
