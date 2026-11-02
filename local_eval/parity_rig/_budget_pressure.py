"""Is the tool-call / time budget actually terminating unsolved runs?"""
import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
RUN = BASE / 'kaggle_pkg' / 'out_v7'
LOGS = RUN / 'results' / 'logs'
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')

m = json.loads((RUN / 'trace_metrics.json').read_text(encoding='utf-8'))
S = [r for r in m if r['solved']]
U = [r for r in m if not r['solved']]

print('=== call-count distribution ===')
for thr in (20, 24, 26, 28, 30, 35):
    a = sum(1 for r in S if r['ncalls'] >= thr)
    b = sum(1 for r in U if r['ncalls'] >= thr)
    print('  ncalls >= %-3d solved %2d/%d | unsolved %2d/%d' % (thr, a, len(S), b, len(U)))

print()
print('max ncalls: solved %d | unsolved %d' % (max(r['ncalls'] for r in S), max(r['ncalls'] for r in U)))

# termination wording in the tail of each log
PATS = {
    'budget_warning': r'tool call|budget|remaining|out of calls|no calls left',
    'time_warning': r'time|minutes|seconds left|deadline',
    'hard_stop': r'terminat|abort|exceeded|limit reached|forced',
    'submit_seen': r'submit_patch',
}
print()
print('=== last 3 meaningful lines: what ends an unsolved run? ===')
c = Counter()
examples = {}
for r in U:
    p = LOGS / (r['tid'] + '.log')
    if not p.exists():
        continue
    txt = ANSI.sub('', p.read_text(encoding='utf-8', errors='replace'))
    tail = [l.strip() for l in txt.splitlines() if l.strip()][-3:]
    joined = ' '.join(tail)
    tag = ('budget' if re.search(PATS['budget_warning'], joined, re.I) else
           'submit' if re.search(PATS['submit_seen'], joined) else 'other')
    c[tag] += 1
    examples.setdefault(tag, (r['tid'], tail))
for k, v in c.most_common():
    print('  %-8s %d' % (k, v))
    tid, tail = examples[k]
    print('      e.g. %s:' % tid)
    for l in tail:
        print('         ', l[:140])

print()
print('=== compaction tasks (all unsolved) ===')
for r in m:
    if r['compact'] > 0:
        print('   %-24s compact=%d calls=%d first_edit=%s solved=%s'
              % (r['tid'], r['compact'], r['ncalls'], r['first_edit'], r['solved']))
