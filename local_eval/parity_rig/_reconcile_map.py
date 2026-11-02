"""Reconcile the two-week-old winnability map with the measured verifiability filter.

The map (kb/tasks_gold.json kb_mech_class, RICH_48_DIFFICULTY_MAP, log L4059 SMALL_SINGLE_FILE)
says which tasks are winnable ON PAPER from gold-patch shape. The measurement adds a second,
independent axis: can the task be VERIFIED at all in the scoring environment
(gold patch resolves AND empty patch fails). Their intersection is the real target.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RIG = Path(__file__).resolve().parent


def rs(p):
    p = Path(p)
    if not p.exists():
        return set()
    return {r['task'] for r in json.loads(p.read_text(encoding='utf-8')) if r.get('resolved_here')}


gold = rs(RIG / 'replay_gold129_files.json') | rs(ROOT / 'kaggle_pkg' / 'out_gold_fa' / 'replay_result.json')
empty = rs(RIG / 'replay_empty129_files.json')
verifiable = gold - empty

kb = json.loads((ROOT / 'kb' / 'tasks_gold.json').read_text(encoding='utf-8'))['tasks']

# SMALL_SINGLE_FILE proxy from the log: <=1 non-test file AND <=25 added lines
small = {t for t, v in kb.items()
         if (v.get('n_files') or 99) <= 1 and (v.get('added') or 999) <= 25}

PHANTOM = {'requests_7309', 'requests_7315', 'requests_7427'}
RUNS = {'r0': 'm1_capped/agent_ctrl_e4b_r0',
        'r1': 'm1_capped/agent_ctrl_e4b_r1',
        'fa': 'm1_faithful/agent_ctrl_e4b_r0'}
recs = {k: {r['instance_id']: r for r in
            (json.loads(l) for l in (RIG / d / 'task_results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip())}
        for k, d in RUNS.items()}
ids = sorted(set.intersection(*[set(v) for v in recs.values()]))
solved = {k: {t for t in ids if recs[k][t].get('resolved')} for k in RUNS}
n_of = {t: sum(1 for k in RUNS if t in solved[k]) for t in ids}
stable = {t for t in ids if n_of[t] == 3}
flaky = {t for t in ids if 0 < n_of[t] < 3}

print('=== the map you already had ===')
print('kb_mech_class:', dict(Counter((kb[t].get('difficulty') or {}).get('kb_mech_class') for t in kb)))
print('SMALL_SINGLE_FILE (<=1 file, <=25 adds):', len(small), '/129  (log L4059 said 82)')

print('\n=== cross-tab: MAP class x MEASURED verifiability ===')
print('%-8s %-6s %-8s %-9s %-10s %s' % ('class', 'n', 'verif', 'dead', 'verif%', 'stable solves'))
tab = defaultdict(Counter)
for t in ids:
    c = (kb[t].get('difficulty') or {}).get('kb_mech_class') or '?'
    tab[c]['n'] += 1
    if t in verifiable:
        tab[c]['verif'] += 1
    if t in stable:
        tab[c]['stable'] += 1
for c in ['EASY', 'MEDIUM', 'HARD']:
    r = tab[c]
    print('%-8s %-6d %-8d %-9d %-10.0f%% %d' % (
        c, r['n'], r['verif'], r['n'] - r['verif'],
        100 * r['verif'] / r['n'] if r['n'] else 0, r['stable']))

print('\n=== the same for the SMALL_SINGLE_FILE "winnable" set ===')
sv = small & verifiable
print('small-single-file          : %d' % len(small))
print('  AND verifiable           : %d   <-- the real target, not %d' % (len(sv), len(small)))
print('  AND stable solve         : %d -> %s' % (len(small & stable), sorted(small & stable)))
print('  lost to verifiability    : %d -> %s' % (len(small - verifiable), sorted(small - verifiable)[:12]))

print('\n=== our 5 stable + 8 flaky, by map class ===')
for t in sorted(stable & verifiable):
    print('  STABLE %-18s %-7s files=%s adds=%s' % (
        t, (kb[t].get('difficulty') or {}).get('kb_mech_class'),
        kb[t].get('n_files'), kb[t].get('added')))
for t in sorted(flaky & verifiable):
    print('  flaky  %-18s %-7s files=%s adds=%s' % (
        t, (kb[t].get('difficulty') or {}).get('kb_mech_class'),
        kb[t].get('n_files'), kb[t].get('added')))

print('\n=== target arithmetic on the MEASURED set ===')
N = len(verifiable)
for need in (6,):
    print('  need %d/58  ->  S = %.1f stable solves of %d verifiable (%.0f%% conversion)' % (
        need, need * N / 58, N, 100 * need * N / 58 / N))
print('  have 5 stable. shortfall: %.1f' % (6 * N / 58 - 5))
easy_verif = sum(1 for t in verifiable if (kb[t].get('difficulty') or {}).get('kb_mech_class') == 'EASY')
print('  EASY AND verifiable tasks available: %d  (we stably solve %d of them)' % (
    easy_verif, len(stable & verifiable & {t for t in ids if (kb[t].get('difficulty') or {}).get('kb_mech_class') == 'EASY'})))
