"""Mine the 77 content-level failures for a defect with real inventory.

Dimensions (ranked by inventory):
  A. edit-location: where in the right file did the edit land vs the gold hunk?
  B. read/verify coverage: did the agent ever touch the gold file, mention the
     enclosing symbol, or run the repo's own tests?
  C. (residual) same-region wrong fix = genuine reasoning failure.
"""
import json
import re
import statistics
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
RUN = BASE / 'kaggle_pkg' / 'out_v7'
PATCHES = RUN / 'results' / 'patches'
LOGS = RUN / 'results' / 'logs'

tasks = [json.loads(l) for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()]
solved = set(json.loads((RUN / 'recovered_full129.json').read_text(encoding='utf-8'))['solved'])

HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', re.M)
NEWF = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)
DIFF = re.compile(r'^diff --git a/(.+?) b/', re.M)
DEF = re.compile(r'^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)')


def parse_patch(text: str):
    """-> {file: [(old_start, old_len), ...]} plus per-hunk enclosing def names."""
    files = {}
    hunks = {}
    cur = None
    for line in (text or '').splitlines():
        m = NEWF.match(line)
        if m:
            cur = m.group(1).strip()
            if cur != '/dev/null':
                files.setdefault(cur, [])
                hunks.setdefault(cur, [])
            continue
        m = DIFF.match(line)
        if m:
            cur = m.group(1)
            files.setdefault(cur, [])
            hunks.setdefault(cur, [])
            continue
        m = HUNK.match(line)
        if m and cur:
            files[cur].append((int(m.group(1)), int(m.group(2) or 1)))
            continue
        if cur and line[:1] in (' ', '+', '-'):
            m = DEF.match(line[1:])
            if m:
                hunks[cur].append(m.group(1))
    return files, hunks


def center(rngs):
    return statistics.mean(s + l / 2 for s, l in rngs) if rngs else None


def gap(a_rngs, b_rngs):
    """min distance between any two line ranges (0 = touching/overlapping)."""
    best = None
    for s1, l1 in a_rngs:
        for s2, l2 in b_rngs:
            d = max(0, max(s1, s2) - min(s1 + l1, s2 + l2))
            best = d if best is None else min(best, d)
    return best


rows = []
for t in tasks:
    tid = t['instance_id']
    if tid in solved:
        continue
    pp = PATCHES / (tid + '.patch')
    if not pp.exists():
        continue
    gold_f, gold_h = parse_patch(t.get('patch', ''))
    mine_f, mine_h = parse_patch(pp.read_text(encoding='utf-8', errors='replace'))
    log = (LOGS / (tid + '.log')).read_text(encoding='utf-8', errors='replace') if (LOGS / (tid + '.log')).exists() else ''

    shared = set(gold_f) & set(mine_f)
    if not shared:
        loc = 'wrong_file'
        d = None
    else:
        d = min(gap(gold_f[f], mine_f[f]) for f in shared)
        loc = 'same_region' if d <= 20 else ('adjacent' if d <= 100 else 'far_in_file')

    gold_defs = {x for f in gold_f for x in gold_h.get(f, [])}
    mentioned = [x for x in gold_defs if re.search(r'\b' + re.escape(x) + r'\b', log)]

    rows.append(dict(
        tid=tid, loc=loc, dist=d,
        gold_files=len(gold_f), mine_files=len(mine_f),
        read_gold_file=any(f in log for f in gold_f),
        gold_defs=len(gold_defs), mentioned=len(mentioned),
        def_hit=bool(gold_defs) and len(mentioned) == len(gold_defs),
        any_def_hit=bool(mentioned),
        pytest=bool(re.search(r'\bpytest\b|-m\s+pytest|python -m pytest', log)),
        ran_tests=bool(re.search(r'pytest|unittest|\btests/\S+\.py\b', log)),
        chars=len(log),
    ))

print('content-level failures analysed: %d' % len(rows))
print()

print('=== A. edit location (right file, where did it land?) ===')
c = Counter(r['loc'] for r in rows)
for k in ('same_region', 'adjacent', 'far_in_file', 'wrong_file'):
    print('  %-12s %3d' % (k, c[k]))
far = [r for r in rows if r['loc'] == 'far_in_file']
if far:
    ds = sorted(r['dist'] for r in far)
    print('  far distances: median %d, min %d, max %d' % (ds[len(ds) // 2], ds[0], ds[-1]))

print()
print('=== B. read / verify coverage ===')
print('  never mentioned the enclosing symbol : %d/%d' % (sum(1 for r in rows if not r['any_def_hit']), len(rows)))
print('  never ran pytest / tests at all      : %d/%d' % (sum(1 for r in rows if not r['pytest']), len(rows)))
print('  never referenced any test file       : %d/%d' % (sum(1 for r in rows if not r['ran_tests']), len(rows)))

# same stats for the solved set, as a contrast
srows = []
for t in tasks:
    tid = t['instance_id']
    if tid not in solved:
        continue
    gold_f, gold_h = parse_patch(t.get('patch', ''))
    log = (LOGS / (tid + '.log')).read_text(encoding='utf-8', errors='replace') if (LOGS / (tid + '.log')).exists() else ''
    gold_defs = {x for f in gold_f for x in gold_h.get(f, [])}
    srows.append(dict(any_def_hit=bool([x for x in gold_defs if re.search(r'\b' + re.escape(x) + r'\b', log)]),
                      pytest=bool(re.search(r'\bpytest\b|-m\s+pytest|python -m pytest', log))))
print()
print('  CONTRAST solved (n=%d): symbol mentioned %d/%d | pytest run %d/%d'
      % (len(srows), sum(r['any_def_hit'] for r in srows), len(srows),
         sum(r['pytest'] for r in srows), len(srows)))

print()
print('=== ranked by inventory ===')
cands = [
    ('edit landed far from gold hunk in right file', len(far)),
    ('never named the symbol the gold patch changes',
     sum(1 for r in rows if not r['any_def_hit'])),
    ('never ran pytest on any test', sum(1 for r in rows if not r['pytest'])),
    ('wrong file entirely', c['wrong_file']),
]
for name, n in sorted(cands, key=lambda kv: -kv[1]):
    print('  %-48s %3d  (%s)' % (name, n, 'ABOVE 10-TASK BAR' if n > 10 else 'below bar'))

(RUN / 'content_failures.json').write_text(json.dumps(rows, indent=1), encoding='utf-8')
print()
print('wrote', RUN / 'content_failures.json')
