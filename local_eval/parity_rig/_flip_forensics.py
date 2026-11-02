"""Flip forensics across the three full-129 E4B runs.

For every task: did it flip between runs, and if it never solved, WHY?
Classes:
  no_patch      - agent produced no/empty patch
  wrong_file    - patch does not touch any file in the gold patch
  near_miss     - touches gold file, tests ran, some passed but some failed
  all_fail      - touches gold file, every required test failed
  no_test       - touches gold file but no test result recorded
  unresolved_env- tests errored (collection/dep) so the task is unjudgeable
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

RIG = Path(__file__).resolve().parent
TASKS = RIG.parents[1] / 'comp_files' / 'tasks.jsonl'
RUNS = {
    'r0': RIG / 'm1_capped' / 'agent_ctrl_e4b_r0',
    'r1': RIG / 'm1_capped' / 'agent_ctrl_e4b_r1',
    'fa': RIG / 'm1_faithful' / 'agent_ctrl_e4b_r0',
}
PHANTOM = {'requests_7309', 'requests_7315', 'requests_7427'}

gold = {}
for line in TASKS.read_text(encoding='utf-8').splitlines():
    if line.strip():
        r = json.loads(line)
        gold[r['instance_id']] = set(re.findall(r'^\+\+\+ b/(.*?)$', r.get('patch') or '', re.M))

runs = {}
for k, d in RUNS.items():
    f = d / 'task_results.jsonl'
    runs[k] = {r['instance_id']: r for r in
               (json.loads(l) for l in f.read_text(encoding='utf-8').splitlines() if l.strip())}

ids = sorted(set.intersection(*[set(v) for v in runs.values()]))
print('tasks in all 3 runs:', len(ids))

SUMMARY = re.compile(r'(\d+)\s+(passed|failed|error|errors|skipped)')


def test_counts(tid):
    p = RUNS['r0'] / 'test_outputs' / f'{tid}.log'
    if not p.exists():
        p = RUNS['r1'] / 'test_outputs' / f'{tid}.log'
    if not p.exists():
        return None, ''
    txt = p.read_text(encoding='utf-8', errors='replace')
    c = {k: int(v) for v, k in SUMMARY.findall(txt)}
    return c, txt


def classify(tid, rec):
    patch = RUNS['r0'] / 'patches' / f'{tid}.patch'
    files = set()
    if patch.exists():
        files = set(re.findall(r'^\+\+\+ b/(.*?)$', patch.read_text(encoding='utf-8', errors='replace'), re.M))
    size = rec.get('agent_patch_size') or 0
    if not files or size == 0:
        return 'no_patch', files
    if gold.get(tid) and not (files & gold[tid]):
        return 'wrong_file', files
    c, txt = test_counts(tid)
    if c is None:
        return 'no_test', files
    if c.get('error') or c.get('errors'):
        return 'unresolved_env', files
    if c.get('passed', 0) > 0 and (c.get('failed', 0) or 0) > 0:
        return 'near_miss', files
    if (c.get('failed', 0) or 0) > 0:
        return 'all_fail', files
    if c.get('passed', 0) > 0:
        return 'passes_but_not_credited', files
    return 'no_test', files


solved = {k: {t for t in ids if runs[k][t].get('resolved')} for k in runs}
n_solved = {t: sum(1 for k in runs if t in solved[k]) for t in ids}
print('solves per task:', dict(sorted(Counter(n_solved.values()).items())))

flip = [t for t in ids if 0 < n_solved[t] < 3]
stable = [t for t in ids if n_solved[t] == 3]
never = [t for t in ids if n_solved[t] == 0]
print('\n=== FLIPPING (%d) ===' % len(flip))
print('%-18s %-4s %s' % ('task', 'n', 'per-run: solved/tools/dur/patchsz'))
for t in sorted(flip):
    cells = []
    for k in runs:
        r = runs[k][t]
        cells.append('%s%s/%s/%s/%s' % (k, 'S' if r.get('resolved') else '.',
                                        r.get('tool_calls'), round(r.get('duration_seconds') or 0),
                                        r.get('agent_patch_size')))
    print('%-18s %-4d %s' % (t, n_solved[t], '  '.join(cells)))

print('\n=== NEVER SOLVED (%d) - classification on the r0 attempt ===' % len(never))
cls = Counter()
for t in never:
    c, files = classify(t, runs['r0'][t])
    cls[c] += 1
for c, n in cls.most_common():
    print('  %-22s %3d' % (c, n))

print('\n  detail:')
for t in sorted(never):
    c, files = classify(t, runs['r0'][t])
    r = runs['r0'][t]
    g = ','.join(sorted(gold.get(t) or []))[:34]
    print('  %-18s %-15s tools=%-3s dur=%-4s patch=%-5s gold=%s' % (
        t, c, r.get('tool_calls'), round(r.get('duration_seconds') or 0),
        r.get('agent_patch_size'), g))

print('\n=== CAP PRESSURE (all 3 runs, all tasks) ===')
for k in runs:
    d = runs[k]
    tc = [x.get('tool_calls') or 0 for x in d.values()]
    du = [x.get('duration_seconds') or 0 for x in d.values()]
    print('  %s: max tools %d (>=28: %d) | max dur %ds (>=480: %d) | turns capped: n/a' % (
        k, max(tc), sum(1 for v in tc if v >= 28), max(du), sum(1 for v in du if v >= 480)))

print('\n=== CAP PRESSURE on tasks that never solved ===')
for k in runs:
    d = runs[k]
    tc = [d[t].get('tool_calls') or 0 for t in never]
    du = [d[t].get('duration_seconds') or 0 for t in never]
    print('  %s: max tools %d (>=28: %d) | max dur %ds (>=480: %d)' % (
        k, max(tc), sum(1 for v in tc if v >= 28), max(du), sum(1 for v in du if v >= 480)))
