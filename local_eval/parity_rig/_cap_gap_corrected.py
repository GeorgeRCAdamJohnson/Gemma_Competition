"""CORRECTED decomposition: only tasks 31B solves AND E4B does NOT.

My earlier version classified E4B's patches on all 35 tasks 31B solves, without excluding
the 9 that E4B also solves -- so 'content failures' included solved tasks whose tests
passed. This version filters to genuine E4B failures and re-checks each patch against the
verification output.
"""
import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
E4B = BASE / 'kaggle_pkg' / 'out_e4b' / 'results'
V7 = BASE / 'kaggle_pkg' / 'out_v7' / 'results'
NEWF = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)
DIFF = re.compile(r'^diff --git a/(.+?) b/', re.M)
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', re.M)

TASKS = {json.loads(l)['instance_id']: json.loads(l)
         for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()}


def parse(text):
    files, cur = {}, None
    for line in (text or '').splitlines():
        m = NEWF.match(line) or DIFF.match(line)
        if m:
            cur = m.group(1).strip()
            if cur != '/dev/null':
                files.setdefault(cur, [])
            continue
        m = HUNK.match(line)
        if m and cur:
            files[cur].append((int(m.group(1)), int(m.group(2) or 1)))
    return files


def gap(a, b):
    best = None
    for s1, l1 in a:
        for s2, l2 in b:
            d = max(0, max(s1, s2) - min(s1 + l1, s2 + l2))
            best = d if best is None else min(best, d)
    return best


s31 = set(json.loads((V7.parent / 'recovered_full129.json').read_text(encoding='utf-8'))['solved'])
rows = [json.loads(l) for l in (E4B / 'task_results.all.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
se4 = {r['instance_id'] for r in rows if r.get('resolved')}

target = sorted(s31 - se4)
print('31B solved %d | E4B solved %d | shared %d' % (len(s31), len(se4), len(s31 & se4)))
print('GENUINE gap (31B solves, E4B does not): %d' % len(target))
print('  ', target)
print()

c = Counter()
near = []
for tid in target:
    gold = parse(TASKS.get(tid, {}).get('patch', ''))
    pp = E4B / 'patches' / (tid + '.patch')
    mine = parse(pp.read_text(encoding='utf-8', errors='replace')) if pp.exists() else {}
    if not mine:
        k = 'no_patch'
    else:
        shared = set(gold) & set(mine)
        if not shared:
            k = 'wrong_file'
        else:
            d = min(gap(gold[f], mine[f]) for f in shared)
            k = 'right_file_near' if d <= 100 else 'right_file_far'
            if k == 'right_file_near':
                near.append(tid)
    c[k] += 1

n = len(target)
print('CORRECTED decomposition of the genuine gap (n=%d):' % n)
for k in ('no_patch', 'wrong_file', 'right_file_far', 'right_file_near'):
    print('   %-16s %3d  (%4.1f%%)' % (k, c[k], 100 * c[k] / max(n, 1)))
print()
print('process-fixable (wrong file + far): %d' % (c['wrong_file'] + c['right_file_far']))
print('content-bound (right file, near)  : %d' % c['right_file_near'])
print()
print('near-hunk tasks:', near)
