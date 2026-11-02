"""Is the local E4B rig a faithful model of the Kaggle E4B run?

Same config, same 129 tasks, identical caps. Compare solve sets per task, error profile,
durations and call counts.
"""
import json
import statistics
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
KAG = BASE / 'kaggle_pkg' / 'out_e4b' / 'results' / 'task_results.all.jsonl'
LOCAL = BASE / 'local_eval' / 'parity_rig' / 'm1_locate' / 'agent_ctrl_e4b_r0' / 'task_results.jsonl'


def load(p):
    rows = [json.loads(l) for l in Path(p).read_text(encoding='utf-8').splitlines() if l.strip()]
    return {r['instance_id']: r for r in rows}


k = load(KAG)
m = load(LOCAL)
both = set(k) & set(m)
print('rows: kaggle %d | local %d | common %d' % (len(k), len(m), len(both)))

ks = {t for t in both if k[t].get('resolved')}
ls = {t for t in both if m[t].get('resolved')}
print()
print('solved    kaggle %d/%d | local %d/%d' % (len(ks), len(both), len(ls), len(both)))
print('  both solved      : %d  %s' % (len(ks & ls), sorted(ks & ls)))
print('  kaggle only      : %d  %s' % (len(ks - ls), sorted(ks - ls)))
print('  local only       : %d  %s' % (len(ls - ks), sorted(ls - ks)))
print('  neither          : %d' % len(both - ks - ls))
try:
    from math import comb

    def fisher(a, b, c, d):
        n = a + b + c + d
        def p(a_, b_, c_, d_):
            return comb(a_ + c_, a_) * comb(b_ + d_, b_) / comb(n, a_ + b_)
        obs = p(a, b, c, d)
        tot = 0.0
        for i in range(0, min(a + b, a + c) + 1):
            j = a + b - i
            ii = a + c - i
            jj = n - i - j - ii
            if ii < 0 or jj < 0:
                continue
            pi = p(i, j, ii, jj)
            if pi <= obs + 1e-12:
                tot += pi
        return tot
    a = len(ks & ls); b = len(ks - ls); c = len(ls - ks); d = len(both - ks - ls)
    print('  agreement (both/neither): %.3f' % ((a + d) / max(len(both), 1)))
    print('  McNemar-ish fisher on discordant pairs: p = %.3f' % fisher(a, b, c, d))
except Exception as e:
    print('  (fisher skipped: %s)' % e)


def med(rows, field):
    vals = [rows[t].get(field) or 0 for t in both]
    return statistics.median(vals) if vals else 0


print()
print('%-22s %10s %10s' % ('metric', 'kaggle', 'local'))
print('%-22s %10.0f %10.0f' % ('median duration (s)', med(k, 'duration_seconds'), med(m, 'duration_seconds')))
print('%-22s %10.1f %10.1f' % ('mean tool calls', sum((k[t].get('tool_calls') or 0) for t in both) / len(both),
                                                sum((m[t].get('tool_calls') or 0) for t in both) / len(both)))


def errclass(r):
    e = str(r.get('error') or '')
    if 'ContextWindow' in e:
        return 'overflow'
    if 'session timeout' in e:
        return 'timeout'
    if e:
        return 'other_error'
    return 'none'


from collections import Counter
ce = Counter(errclass(k[t]) for t in both)
le = Counter(errclass(m[t]) for t in both)
print()
print('%-22s %10s %10s' % ('error class', 'kaggle', 'local'))
for c in ('none', 'overflow', 'timeout', 'other_error'):
    print('%-22s %10d %10d' % (c, ce[c], le[c]))
