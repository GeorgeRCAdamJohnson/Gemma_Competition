"""Which of the 111 never-solved tasks are actually within reach?

Splits them by whether localization succeeded (patch touches a gold file) and, if so,
how close the fix was (tests that ran: passed vs failed vs errored).
"""
import json
import re
from collections import Counter
from pathlib import Path

RIG = Path(__file__).resolve().parent
TASKS = RIG.parents[1] / 'comp_files' / 'tasks.jsonl'
RUNS = {
    'r0': RIG / 'm1_capped' / 'agent_ctrl_e4b_r0',
    'r1': RIG / 'm1_capped' / 'agent_ctrl_e4b_r1',
    'fa': RIG / 'm1_faithful' / 'agent_ctrl_e4b_r0',
}
FILES_RE = re.compile(r'^\+\+\+ b/(.*?)$', re.M)
SUM = re.compile(r'(\d+)\s+(passed|failed|error|errors|skipped)')

gold = {}
for line in TASKS.read_text(encoding='utf-8').splitlines():
    if line.strip():
        r = json.loads(line)
        gold[r['instance_id']] = set(FILES_RE.findall(r.get('patch') or ''))

recs = {k: {r['instance_id']: r for r in
            (json.loads(l) for l in (Path(d) / 'task_results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip())}
        for k, d in RUNS.items()}
ids = sorted(set.intersection(*[set(v) for v in recs.values()]))
never = [t for t in ids if not any(recs[k][t].get('resolved') for k in RUNS)]
print('never solved:', len(never))


def patch_files(tid):
    p = RUNS['r0'] / 'patches' / f'{tid}.patch'
    if not p.exists():
        return set()
    return set(FILES_RE.findall(p.read_text(encoding='utf-8', errors='replace')))


def test_counts(tid):
    for d in RUNS.values():
        p = d / 'test_outputs' / f'{tid}.log'
        if p.exists():
            txt = p.read_text(encoding='utf-8', errors='replace')
            c = {}
            for v, k in SUM.findall(txt):
                c[k] = int(v)
            return c, txt
    return None, ''


buckets = Counter()
near, env, wrong, nopatch, other = [], [], [], [], []
for t in never:
    files = patch_files(t)
    if not files:
        buckets['no_patch'] += 1
        nopatch.append(t)
        continue
    if gold.get(t) and not (files & gold[t]):
        buckets['wrong_file'] += 1
        wrong.append((t, files, gold[t]))
        continue
    c, txt = test_counts(t)
    if c is None:
        buckets['no_test_log'] += 1
        other.append(t)
        continue
    if c.get('error') or c.get('errors'):
        buckets['tests_errored'] += 1
        env.append((t, c, txt))
    elif c.get('failed', 0):
        buckets['near_miss'] += 1
        near.append((t, c))
    elif c.get('passed', 0):
        buckets['passes_but_not_credited'] += 1
        other.append(t)
    else:
        buckets['no_counts'] += 1
        other.append(t)

print('\n=== never-solved buckets ===')
for k, v in buckets.most_common():
    print('  %-26s %3d  (%.0f%%)' % (k, v, 100 * v / len(never)))

print('\n=== NEAR MISS: localized correctly, some tests pass, some fail (%d) ===' % len(near))
for t, c in sorted(near, key=lambda x: (x[1].get('failed', 0), -x[1].get('passed', 0))):
    print('  %-18s passed=%-3d failed=%-3d skipped=%-2d gold=%s' % (
        t, c.get('passed', 0), c.get('failed', 0), c.get('skipped', 0),
        ','.join(sorted(gold.get(t) or []))[:38]))

print('\n=== TESTS ERRORED: patch landed on a gold file but the suite blew up (%d) ===' % len(env))
sig = Counter()
for t, c, txt in env:
    m = re.findall(r'(ModuleNotFoundError|ImportError|AttributeError|TypeError|SyntaxError|'
                   r'ERROR collecting|no tests ran|error: |Failed: )', txt)
    sig[m[0] if m else 'other'] += 1
print('  signatures:', dict(sig))
for t, c, txt in env:
    line = [l.strip() for l in txt.splitlines() if re.search(r'(Error|ERROR|error:)', l)][:1]
    print('  %-18s %-3s %s' % (t, c, (line[0] if line else '')[:104]))

print('\n=== WRONG FILE (%d): which gold file did we miss? ===' % len(wrong))
hot = Counter(f for _, _, g in wrong for f in g)
for f, n in hot.most_common(8):
    print('  %-46s %d' % (f, n))
