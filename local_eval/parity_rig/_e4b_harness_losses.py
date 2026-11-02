"""Quantify E4B's harness-side losses: context overflow and timeouts.

These are tasks where the agent was not out-reasoned -- the run was cut off.
If they are otherwise solvable, fixing them is free inventory toward the pool target.
"""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
RUN = BASE / 'kaggle_pkg' / 'out_e4b' / 'results'
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')

rows = [json.loads(l) for l in (RUN / 'task_results.all.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
logs, patches = RUN / 'logs', RUN / 'patches'

errs = [r for r in rows if r.get('error')]
print('rows: %d | with error: %d | solved: %d' % (
    len(rows), len(errs), sum(1 for r in rows if r.get('resolved'))))

by_kind = {}
for r in errs:
    e = str(r.get('error'))
    kind = ('context_overflow' if 'ContextWindow' in e else
            'session_timeout' if 'session timeout' in e else
            'other')
    by_kind.setdefault(kind, []).append(r)

for kind, rs in by_kind.items():
    print('\n=== %s: %d tasks ===' % (kind, len(rs)))
    for r in rs:
        tid = r['instance_id']
        lg = logs / (tid + '.log')
        txt = ANSI.sub('', lg.read_text(encoding='utf-8', errors='replace')) if lg.exists() else ''
        pp = patches / (tid + '.patch')
        pb = pp.stat().st_size if pp.exists() else 0
        calls = len(re.findall(r'^\s*\[\s*[\d.]+s\]\s+\S+\s+[a-z_]+\b', txt, re.M))
        edits = len(re.findall(r'\bedit_file\b', txt))
        submits = len(re.findall(r'\bsubmit_patch\b', txt))
        dur = r.get('duration_seconds') or 0
        print('  %-22s dur=%5.0fs calls=%2d edits=%2d submits=%d patch=%5dB' %
              (tid, dur, calls, edits, submits, pb))

print('\n--- how far did the overflow runs get? ---')
for r in by_kind.get('context_overflow', []):
    tid = r['instance_id']
    lg = logs / (tid + '.log')
    txt = ANSI.sub('', lg.read_text(encoding='utf-8', errors='replace')) if lg.exists() else ''
    last = [l.strip() for l in txt.splitlines() if l.strip()][-3:]
    print('  %-22s last:' % tid)
    for l in last:
        print('       ', l[:130])
