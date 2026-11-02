"""Anatomy of E4B localization failures vs 31B, on the axis that determines the fix.

For every unsolved task classify:
  no_edit        - never called edit_file
  no_patch       - edited but produced no patch
  wrong_file     - patched, zero overlap with the gold patch's files
      + did the agent READ the gold file?  (search failure vs decision failure)
      + did the agent NAME any symbol the gold patch touches?
  far_span       - right file, hunk >100 lines from gold
  near_span      - right file, within 100 lines, still failed (wrong fix)
"""
import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
NEWF = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)
DIFF = re.compile(r'^diff --git a/(.+?) b/', re.M)
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))?', re.M)
DEF = re.compile(r'^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)')

TASKS = {json.loads(l)['instance_id']: json.loads(l)
         for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()}


def parse_patch(text):
    files, hunks, syms = {}, {}, set()
    cur = None
    for line in (text or '').splitlines():
        m = NEWF.match(line) or DIFF.match(line)
        if m:
            cur = (m.group(1) if m.re is NEWF else m.group(1)).strip()
            if cur != '/dev/null':
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
                syms.add(m.group(1))
    return files, hunks, syms


def gap(a, b):
    best = None
    for s1, l1 in a:
        for s2, l2 in b:
            d = max(0, max(s1, s2) - min(s1 + l1, s2 + l2))
            best = d if best is None else min(best, d)
    return best


def load_rows(run: Path):
    p = run / 'results' / 'task_results.all.jsonl'
    if p.exists():
        return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
    rec = run / 'recovered_full129.json'          # out_v7 was hit by the chunk-overwrite bug
    if rec.exists():
        d = json.loads(rec.read_text(encoding='utf-8'))
        solved = set(d['solved'])
        return [dict(instance_id=r['instance_id'], resolved=r['instance_id'] in solved,
                     tool_calls=None, duration_seconds=None) for r in d['rows']]
    return []


def analyse(run: Path, label: str):
    rows = load_rows(run)
    patches = run / 'results' / 'patches'
    logs = run / 'results' / 'logs'
    out = Counter()
    detail = []
    for r in rows:
        tid = r['instance_id']
        if r.get('resolved'):
            continue
        gold_f, gold_h, gold_syms = parse_patch(TASKS.get(tid, {}).get('patch', ''))
        pp = patches / (tid + '.patch')
        log = ANSI.sub('', (logs / (tid + '.log')).read_text(encoding='utf-8', errors='replace')) \
            if (logs / (tid + '.log')).exists() else ''
        read_gold = any(f in log for f in gold_f)
        named = any(re.search(r'\b' + re.escape(s) + r'\b', log) for s in gold_syms)

        if 'edit_file' not in log:
            kind = 'no_edit'
        elif not pp.exists():
            kind = 'no_patch'
        else:
            mine_f, mine_h, _ = parse_patch(pp.read_text(encoding='utf-8', errors='replace'))
            shared = set(gold_f) & set(mine_f)
            if not shared:
                kind = 'wrong_file'
            else:
                d = min(gap(gold_f[f], mine_f[f]) for f in shared)
                kind = 'near_span' if d <= 100 else 'far_span'
        out[kind] += 1
        detail.append(dict(tid=tid, kind=kind, read_gold=read_gold, named_gold_sym=named,
                           gold_files=len(gold_f)))
    print('\n' + '=' * 74)
    print('%s  (unsolved n=%d)' % (label, sum(out.values())))
    for k in ('no_edit', 'no_patch', 'wrong_file', 'far_span', 'near_span'):
        n = out[k]
        print('  %-12s %3d  (%4.1f%%)' % (k, n, 100 * n / max(sum(out.values()), 1)))

    wf = [d for d in detail if d['kind'] == 'wrong_file']
    if wf:
        read = sum(1 for d in wf if d['read_gold'])
        named = sum(1 for d in wf if d['named_gold_sym'])
        print('  wrong_file breakdown (n=%d):' % len(wf))
        print('     READ the gold file first      : %3d  -> decision failure' % read)
        print('     NEVER read the gold file      : %3d  -> search failure' % (len(wf) - read))
        print('     named a gold-patch symbol     : %3d' % named)
    ns = [d for d in detail if d['kind'] == 'near_span']
    if ns:
        print('  near_span: right file, <=100 lines from gold, wrong fix: %d  -> reasoning' % len(ns))
    return out, detail


if __name__ == '__main__':
    for label, run in (('E4B (10/129)', BASE / 'kaggle_pkg' / 'out_e4b'),
                       ('31B (35/129)', BASE / 'kaggle_pkg' / 'out_v7')):
        analyse(run, label)
