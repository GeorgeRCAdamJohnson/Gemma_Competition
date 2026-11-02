"""Of the 17 content failures (right file, hunk on the gold lines), WHAT is wrong?

For each, print the gold's changed lines beside E4B's changed lines at the same region,
and score token overlap so we can separate:
  SAME IDEA, WRONG DETAILS  - shares distinctive identifiers with the gold change
  DIFFERENT IDEA            - no shared identifiers
  DEGENERATE                - empty/no-op/comment-only or syntactically broken edit
"""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
E4B = BASE / 'kaggle_pkg' / 'out_e4b' / 'results'
TASKS = {json.loads(l)['instance_id']: json.loads(l)
         for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()}

# the 17 from the decomposition
NEAR = ['fastapi_11194', 'fastapi_14077', 'fastapi_14301', 'fastapi_14419', 'fastapi_14463',
        'fastapi_14786', 'fastapi_14794', 'fastapi_14873', 'fastapi_5077', 'fastapi_5624',
        'rich_3006', 'rich_3454', 'rich_3521', 'rich_3718', 'rich_3882', 'rich_3905', 'rich_4070']

NEWF = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)
STOP = {'self', 'return', 'def', 'if', 'else', 'not', 'and', 'or', 'in', 'is', 'the', 'a',
        'an', 'None', 'True', 'False', 'value', 'result', 'text', 'str', 'int', 'for'}


def changed(text, want_plus=True):
    out = []
    for line in (text or '').splitlines():
        if line.startswith('+') and not line.startswith('+++') and want_plus:
            out.append(line[1:])
        elif line.startswith('-') and not line.startswith('---') and not want_plus:
            out.append(line[1:])
    return out


def toks(lines):
    s = set()
    for l in lines:
        for t in re.findall(r'[A-Za-z_][A-Za-z0-9_]{2,}', l):
            if t not in STOP:
                s.add(t)
    return s


def unbalanced(lines):
    blob = '\n'.join(lines)
    return blob.count('(') != blob.count(')') or blob.count('[') != blob.count(']')


rows = []
for tid in NEAR:
    gold_txt = TASKS.get(tid, {}).get('patch', '')
    pp = E4B / 'patches' / (tid + '.patch')
    mine_txt = pp.read_text(encoding='utf-8', errors='replace') if pp.exists() else ''
    ga, gd = changed(gold_txt, True), changed(gold_txt, False)
    ma, md = changed(mine_txt, True), changed(mine_txt, False)
    gt, mt = toks(ga), toks(ma)
    shared = gt & mt
    print('=' * 78)
    print('%s   gold(+%d/-%d)  e4b(+%d/-%d)  shared-idents=%d/%d'
          % (tid, len(ga), len(gd), len(ma), len(md), len(shared), len(gt)))
    if shared:
        print('   shared: %s' % sorted(shared)[:8])
    print('   GOLD +: %s' % (' | '.join(x.strip() for x in ga[:3])[:220] or '(none)'))
    print('   E4B  +: %s' % (' | '.join(x.strip() for x in ma[:3])[:220] or '(none)'))
    if gd:
        print('   GOLD -: %s' % (' | '.join(x.strip() for x in gd[:2])[:160]))
    if md:
        print('   E4B  -: %s' % (' | '.join(x.strip() for x in md[:2])[:160]))
    # classify
    if not ma and not md:
        k = 'DEGENERATE (no change)'
    elif len(ma) <= 2 and all(x.strip().startswith('#') or not x.strip() for x in ma):
        k = 'DEGENERATE (comment/blank only)'
    elif unbalanced(ma):
        k = 'MALFORMED (unbalanced)'
    elif len(shared) >= 2 or (gt and len(shared) / max(len(gt), 1) >= 0.25):
        k = 'SAME IDEA, WRONG DETAILS'
    elif shared:
        k = 'PARTIAL OVERLAP'
    else:
        k = 'DIFFERENT IDEA'
    print('   ==> %s' % k)
    rows.append((tid, k, len(shared), len(gt)))

from collections import Counter
print()
print('=' * 78)
print('CLASSIFICATION SUMMARY (%d tasks)' % len(rows))
for k, v in Counter(r[1] for r in rows).most_common():
    print('   %-28s %d' % (k, v))
