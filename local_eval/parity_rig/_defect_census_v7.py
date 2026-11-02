"""Quantify failure signatures across a full-pool run from per-task agent logs."""
import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
RUN = BASE / 'kaggle_pkg' / 'out_v7'
LOGS = RUN / 'results' / 'logs'
PATCHES = RUN / 'results' / 'patches'
TESTS = RUN / 'results' / 'test_outputs'

tasks = [json.loads(l) for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()]
solved = set(json.loads((RUN / 'recovered_full129.json').read_text(encoding='utf-8'))['solved'])

SIGS = {
    'ctx_overflow': r'maximum context length|context length is|Reduce the length|longer than the maximum',
    'api_notfound': r'NotFoundError',
    'api_retry': r'Retried: \d+ times',
    'api_conn': r'APIConnectionError|Connection error|ReadTimeout|Read timed out',
    'no_submit': r'(?!x)x',  # placeholder, handled structurally
    'heredoc_fallback': r"<<'PY'|<< 'PY'|<<EOF|<<\"PY\"",
    'edit_err': r'edit_file.*(?:error|failed|not found)',
    'timeout_arm': r'time budget|out of time|remaining time',
}

rows = []
for t in tasks:
    tid = t['instance_id']
    p = LOGS / (tid + '.log')
    txt = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
    c = Counter()
    for k, rx in SIGS.items():
        if k == 'no_submit':
            continue
        c[k] = len(re.findall(rx, txt, re.I))
    submits = len(re.findall(r'submit_patch', txt))
    calls = len(re.findall(r'^\s*\[\s*[\d.]+s\]\s+\S+\s+\S+', txt, re.M))
    rows.append(dict(tid=tid, repo=t['repo'], solved=tid in solved,
                     submits=submits, has_patch=(PATCHES / (tid + '.patch')).exists(),
                     has_test=(TESTS / (tid + '.log')).exists(),
                     log_chars=len(txt), **c))

S, U = [r for r in rows if r['solved']], [r for r in rows if not r['solved']]
print('solved %d | unsolved %d' % (len(S), len(U)))
print()

sub0 = [r for r in rows if r['submits'] == 0]
print('never called submit_patch: %d  (solved among them: %d)' % (len(sub0), sum(r['solved'] for r in sub0)))
no_patch = [r for r in rows if not r['has_patch']]
print('no patch artifact:         %d  (solved among them: %d)' % (len(no_patch), sum(r['solved'] for r in no_patch)))
print()

print('%-18s %8s %8s' % ('signature', 'solved%', 'unsolv%'))
for k in SIGS:
    if k == 'no_submit':
        continue
    a = sum(1 for r in S if r[k]) / max(len(S), 1) * 100
    b = sum(1 for r in U if r[k]) / max(len(U), 1) * 100
    ha = sum(1 for r in S if r[k])
    hb = sum(1 for r in U if r[k])
    print('%-18s %4d/%2d  %4d/%2d' % (k, ha, len(S), hb, len(U)))

print()
err = [r for r in rows if r['api_notfound'] or r['ctx_overflow']]
print('tasks with API/context errors: %d  -> %s' % (len(err), [r['tid'] for r in err][:15]))
print()
print('unsolved with a patch but tests failed: %d' % sum(1 for r in U if r['has_patch']))
print('log size: solved median %d | unsolved median %d' % (
    sorted(r['log_chars'] for r in S)[len(S) // 2],
    sorted(r['log_chars'] for r in U)[len(U) // 2]))
