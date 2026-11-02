"""At n=129, measure whether submitted patches touch the files the gold patch touches.

This scales the rich_4077 finding (7/13 reps edited the call site instead of the
definition) to the whole pool, using the gold `patch` and the agent's `patches/*.patch`.
"""
import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
RUN = BASE / 'kaggle_pkg' / 'out_v7'
PATCHES = RUN / 'results' / 'patches'

tasks = [json.loads(l) for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()]
solved = set(json.loads((RUN / 'recovered_full129.json').read_text(encoding='utf-8'))['solved'])

FILE_RX = re.compile(r'^diff --git a/(.+?) b/', re.M)
NEW_RX = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)


def files_of(text: str) -> set[str]:
    got = set(FILE_RX.findall(text or ''))
    got |= {f.strip() for f in NEW_RX.findall(text or '') if f.strip() != '/dev/null'}
    return got


rows = []
for t in tasks:
    tid = t['instance_id']
    gold = files_of(t.get('patch', ''))
    p = PATCHES / (tid + '.patch')
    mine = files_of(p.read_text(encoding='utf-8', errors='replace')) if p.exists() else set()
    if not mine:
        kind = 'no_patch'
    elif not gold:
        kind = 'gold_unknown'
    elif mine & gold:
        kind = 'overlap'
    else:
        kind = 'DISJOINT'
    rows.append(dict(tid=tid, repo=t['repo'], solved=tid in solved, kind=kind,
                     gold=len(gold), mine=len(mine),
                     extra=len(mine - gold) if gold else 0))

print('n=%d  solved=%d' % (len(rows), len(solved)))
print()
print('%-12s %10s %10s' % ('patch/gold', 'solved', 'unsolved'))
for k in ('overlap', 'DISJOINT', 'no_patch', 'gold_unknown'):
    s = sum(1 for r in rows if r['kind'] == k and r['solved'])
    u = sum(1 for r in rows if r['kind'] == k and not r['solved'])
    print('%-12s %10d %10d' % (k, s, u))

ov = [r for r in rows if r['kind'] == 'overlap']
dj = [r for r in rows if r['kind'] == 'DISJOINT']
print()
print('solved rate | overlap : %d/%d = %.3f' % (sum(r['solved'] for r in ov), len(ov), sum(r['solved'] for r in ov) / max(len(ov), 1)))
print('solved rate | DISJOINT: %d/%d = %.3f' % (sum(r['solved'] for r in dj), len(dj), sum(r['solved'] for r in dj) / max(len(dj), 1)))

print()
print('DISJOINT unsolved tasks (wrong file entirely):')
for r in dj:
    if not r['solved']:
        print('   %-24s gold=%d mine=%d extra=%d' % (r['tid'], r['gold'], r['mine'], r['extra']))

print()
print('multi-file spread, unsolved overlap tasks (edited gold file + others):')
noisy = [r for r in ov if not r['solved'] and r['extra'] > 0]
print('   %d of %d unsolved-overlap tasks touched >=1 extra file the gold patch did not' % (len(noisy), sum(1 for r in ov if not r['solved'])))

print()
by = Counter((r['repo'], r['kind']) for r in rows)
for repo in sorted({r['repo'] for r in rows}):
    tot = sum(v for (rp, k), v in by.items() if rp == repo)
    dj_n = by[(repo, 'DISJOINT')]
    print('%-22s n=%-3d DISJOINT=%d (%.0f%%)' % (repo, tot, dj_n, 100 * dj_n / max(tot, 1)))
