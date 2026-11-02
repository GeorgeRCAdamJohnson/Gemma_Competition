"""Measure both open questions on the corrected 26-task gap.

A. The wrong-file cases that NEVER read the gold file: what were they doing instead?
   - sequence of files read
   - what they grepped for (and whether it appears in the problem statement)
   - did they edit immediately or after searching
B. The content failures (right file, hunk on gold): does E4B's patch share identifiers
   with gold -> SAME IDEA / WRONG DETAILS vs DIFFERENT IDEA?
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
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))?', re.M)
READ = re.compile(r'read_file\s*\(([^)]+)\)')
GREP = re.compile(r'run_command\s+(.{0,150})')
EDIT = re.compile(r'edit_file\s*\(([^)]+)\)')

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
            files[cur].append((int(m.group(1)), 1))
    return files


def gap(a, b):
    best = None
    for s1, _ in a:
        for s2, _ in b:
            d = abs(s1 - s2)
            best = d if best is None else min(best, d)
    return best


s31 = set(json.loads((V7.parent / 'recovered_full129.json').read_text(encoding='utf-8'))['solved'])
rows = [json.loads(l) for l in (E4B / 'task_results.all.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
se4 = {r['instance_id'] for r in rows if r.get('resolved')}
target = sorted(s31 - se4)

wrong_noread, near = [], []
for tid in target:
    gold = parse(TASKS.get(tid, {}).get('patch', ''))
    pp = E4B / 'patches' / (tid + '.patch')
    mine = parse(pp.read_text(encoding='utf-8', errors='replace')) if pp.exists() else {}
    lg = E4B / 'logs' / (tid + '.log')
    txt = ANSI.sub('', lg.read_text(encoding='utf-8', errors='replace')) if lg.exists() else ''
    read_gold = any(f in txt for f in gold)
    if not mine:
        continue
    shared = set(gold) & set(mine)
    if not shared:
        if not read_gold:
            wrong_noread.append((tid, gold, txt))
    else:
        if min(gap(gold[f], mine[f]) for f in shared) <= 100:
            near.append((tid, gold, mine, txt))

print('=' * 78)
print('A. WRONG FILE + NEVER READ GOLD: %d tasks' % len(wrong_noread))
print('=' * 78)
for tid, gold, txt in wrong_noread:
    ps = TASKS.get(tid, {}).get('problem_statement') or ''
    reads = [x.strip() for x in READ.findall(txt)]
    greps = [g.strip() for g in GREP.findall(txt)]
    m = EDIT.search(txt)
    n_before = len(READ.findall(txt[:m.start()])) if m else len(reads)
    goldf = sorted(gold)
    print('\n%s   gold file=%s' % (tid, goldf))
    print('   reads before first edit: %d -> %s' % (n_before, reads[:5]))
    print('   greps: %d %s' % (len(greps), [g[:60] for g in greps[:3]]))
    print('   statement(120): %s' % ps.replace('\n', ' ')[:120])
    # did any grep string appear in the problem statement?
    hit = sum(1 for g in greps if any(w for w in re.findall(r'[A-Za-z_]{5,}', g) if w in ps))
    print('   greps using a statement term: %d / %d' % (hit, len(greps)))

print()
print('=' * 78)
print('B. CONTENT FAILURES: %d tasks' % len(near))
print('=' * 78)
STOP = {'self', 'return', 'def', 'if', 'else', 'not', 'and', 'or', 'in', 'is', 'the', 'a',
        'an', 'None', 'True', 'False', 'value', 'result', 'text', 'str', 'int', 'for', 'import'}


def adds(text):
    return [l[1:] for l in (text or '').splitlines()
            if l.startswith('+') and not l.startswith('+++')]


def toks(lines):
    return {t for l in lines for t in re.findall(r'[A-Za-z_][A-Za-z0-9_]{2,}', l)} - STOP


classes = Counter()
for tid, gold, mine, txt in near:
    gt = toks(adds(TASKS.get(tid, {}).get('patch', '')))
    pp = E4B / 'patches' / (tid + '.patch')
    mt = toks(adds(pp.read_text(encoding='utf-8', errors='replace')))
    shared = gt & mt
    frac = len(shared) / max(len(gt), 1)
    if frac >= 0.4:
        k = 'SAME IDEA, WRONG DETAILS'
    elif shared:
        k = 'PARTIAL OVERLAP'
    else:
        k = 'DIFFERENT IDEA'
    classes[k] += 1
    print('   %-22s shared %2d/%-2d (%.0f%%)  %s' % (tid, len(shared), len(gt), 100 * frac, k))
    print('        gold: %s' % (' | '.join(x.strip() for x in adds(TASKS.get(tid, {}).get("patch", ""))[:2])[:130]))
    print('        e4b : %s' % (' | '.join(x.strip() for x in adds(pp.read_text(encoding="utf-8", errors="replace"))[:2])[:130]))

print()
print('CLASS SUMMARY:')
for k, v in classes.most_common():
    print('   %-28s %d' % (k, v))
