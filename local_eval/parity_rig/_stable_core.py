"""Which run best explains 2/58? Break each run's solves into stable / flaky / invalid."""
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


def rs(p):
    if not Path(p).exists():
        return None
    return {r['task'] for r in json.loads(Path(p).read_text(encoding='utf-8')) if r.get('resolved_here')}


gold = rs(RIG / 'replay_gold129_files.json')
empty = rs(RIG / 'replay_empty129_files.json')

recs = {k: {r['instance_id']: r for r in
            (json.loads(l) for l in (Path(d) / 'task_results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip())}
        for k, d in RUNS.items()}
ids = sorted(set.intersection(*[set(v) for v in recs.values()]))
solved = {k: {t for t in ids if recs[k][t].get('resolved')} for k in RUNS}
n_of = {t: sum(1 for k in RUNS if t in solved[k]) for t in ids}

stable = {t for t in ids if n_of[t] == 3}
flaky = {t for t in ids if 0 < n_of[t] < 3}
always_fail = {t for t in ids if n_of[t] == 0}

print('=== the stable core: solved in ALL 3 runs (%d) ===' % len(stable))
for t in sorted(stable):
    tag = []
    if t in PHANTOM:
        tag.append('PHANTOM (rig imports site-packages requests)')
    if gold is not None:
        tag.append('gold-valid' if t in gold else 'gold-FAILS')
    if empty is not None:
        tag.append('empty-passes(DEGENERATE)' if t in empty else 'empty-fails')
    print('  %-18s %s' % (t, ' | '.join(tag)))

if gold is not None:
    core_valid = stable & gold
    if empty is not None:
        core_valid = core_valid - empty
    print('\nSTABLE AND LB-VALID: %d -> %s' % (len(core_valid), sorted(core_valid)))
    print('   >>> 2/58 = 0.03. This is the number that matches the leaderboard.')

print('\n=== per-run breakdown ===')
print('%-6s %-7s %-7s %-8s %-8s %-9s %s' % (
    'run', 'solved', 'stable', 'flaky', 'phantom', 'valid-stb', 'valid-flaky'))
for k, S in solved.items():
    st, fl = S & stable, S & flaky
    ph = S & PHANTOM
    if gold is not None:
        v = gold - empty if empty is not None else gold
        vs, vf = len((st - PHANTOM) & v), len((fl - PHANTOM) & v)
    else:
        vs = vf = -1
    print('%-6s %-7d %-7d %-8d %-8d %-9d %d' % (k, len(S), len(st), len(fl), len(ph), vs, vf))

print('\n=== flaky tasks and their validity (%d) ===' % len(flaky))
for t in sorted(flaky, key=lambda x: -n_of[x]):
    v = ''
    if gold is not None:
        v = 'gold-valid' if t in gold else 'gold-FAILS'
    print('  %-18s %d/3  %s' % (t, n_of[t], v))
