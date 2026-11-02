"""Honest read of the decode sweep: are the 'WIN' verdicts distinguishable from noise?"""
import json
from collections import defaultdict
from math import comb
from pathlib import Path

J = Path(r'C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\audits\2026-10-15-decode-commitment-sweep.jsonl')
rows = [json.loads(l) for l in J.read_text(encoding='utf-8').splitlines() if l.strip()]
cells = [r for r in rows if r.get('kind') == 'cell' or 'resolved' in r]
print('jsonl rows:', len(rows))

# normalise
by = defaultdict(dict)
for r in cells:
    arm, task = r.get('config_name'), r.get('task')
    if arm and task:
        by[arm][task] = r

CONFIRM = ['rich_4076', 'rich_3469', 'rich_3278', 'rich_3470', 'rich_3518']
DISCOVER = ['rich_4077', 'rich_4079', 'rich_3471', 'rich_2943', 'rich_3882', 'rich_3935']

print('\n%-12s %-16s %-16s %s' % ('arm', 'CONFIRM resolved', 'DISCOVER resolved', 'per-CONFIRM detail'))
for arm in ['baseline', 'temp_00', 'temp_01', 'freq_02', 'freq_04', 'pres_02', 'pres_04', 'reserve_tail']:
    d = by.get(arm)
    if not d:
        continue
    c = [t for t in CONFIRM if (d.get(t) or {}).get('resolved') is True]
    s = [t for t in DISCOVER if (d.get(t) or {}).get('resolved') is True]
    detail = ' '.join('%s:%s' % (t.split('_')[1], 'Y' if t in c else '.') for t in CONFIRM)
    print('%-12s %-16s %-16s %s' % (arm, f'{len(c)}/5', f'{len(s)}/6', detail))

print('\n=== McNemar vs baseline on CONFIRM (exact, two-sided) ===')
base = {t for t in CONFIRM if (by.get('baseline', {}).get(t) or {}).get('resolved') is True}
for arm in ['temp_00', 'freq_02', 'freq_04', 'pres_02']:
    a = {t for t in CONFIRM if (by.get(arm, {}).get(t) or {}).get('resolved') is True}
    only_a, only_b = len(a - base), len(base - a)
    n = only_a + only_b
    p = 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(0, min(only_a, only_b) + 1)) / 2 ** n)
    print('  %-10s arm-only=%d baseline-only=%d  McNemar p=%.2f  %s' % (
        arm, only_a, only_b, p, 'indistinguishable from noise' if p > 0.3 else 'signal'))

print('\n=== first_edit_at medians on CONFIRM (n=5) ===')
for arm in ['baseline', 'temp_00', 'pres_02']:
    vals = [(by.get(arm, {}).get(t) or {}).get('first_edit_at') for t in CONFIRM]
    vals = sorted(v for v in vals if isinstance(v, int))
    print('  %-10s %s  median=%s' % (arm, vals, vals[len(vals) // 2] if vals else None))
