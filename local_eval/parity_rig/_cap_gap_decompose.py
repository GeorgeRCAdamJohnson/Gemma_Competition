"""Decompose E4B's attempts on the 35 tasks 31B solves.

Classify each E4B attempt:
  no_patch            - produced nothing
  wrong_file          - patch touches no gold file
  right_file_far      - gold file hit, hunk >100 lines away
  right_file_near     - gold file hit, hunk <=100 lines away  => CONTENT failure
Then: of the fixable-by-process classes, how many are there? That is the true ceiling
for any instruction-level lever on E4B.
"""
import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
E4B = BASE / 'kaggle_pkg' / 'out_e4b' / 'results'
V7 = BASE / 'kaggle_pkg' / 'out_v7' / 'results'
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
NEWF = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)
DIFF = re.compile(r'^diff --git a/(.+?) b/', re.M)
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', re.M)

TASKS = {json.loads(l)['instance_id']: json.loads(l)
         for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()}


def parse(text):
    files = {}
    cur = None
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
e4 = {r['instance_id']: r for r in rows}

c = Counter()
dist = []
detail = []
for tid in sorted(s31):
    gold = parse(TASKS.get(tid, {}).get('patch', ''))
    pp = E4B / 'patches' / (tid + '.patch')
    mine = parse(pp.read_text(encoding='utf-8', errors='replace')) if pp.exists() else {}
    lg = E4B / 'logs' / (tid + '.log')
    txt = ANSI.sub('', lg.read_text(encoding='utf-8', errors='replace')) if lg.exists() else ''
    read_gold = any(f in txt for f in gold)

    if not mine:
        k = 'no_patch'
    else:
        shared = set(gold) & set(mine)
        if not shared:
            k = 'wrong_file'
        else:
            d = min(gap(gold[f], mine[f]) for f in shared)
            dist.append(d)
            k = 'right_file_near' if d <= 100 else 'right_file_far'
    c[k] += 1
    detail.append((tid, k, read_gold))

n = len(s31)
print('E4B attempts on the %d tasks that 31B solves:' % n)
for k in ('no_patch', 'wrong_file', 'right_file_far', 'right_file_near'):
    print('   %-16s %3d  (%4.1f%%)' % (k, c[k], 100 * c[k] / n))
print()
print('processed (wrong file + far): %d  <- these are the ONLY process-fixable ones'
      % (c['wrong_file'] + c['right_file_far']))
print('content failures (right file, near): %d  <- capability-bound by construction'
      % c['right_file_near'])
if dist:
    ds = sorted(dist)
    print('near-hunk distance: median %d, min %d, max %d' % (ds[len(ds) // 2], ds[0], ds[-1]))
print()
print('detail:')
for tid, k, rg in detail:
    print('   %-22s %-16s read_gold=%s' % (tid, k, 'YES' if rg else 'no'))
