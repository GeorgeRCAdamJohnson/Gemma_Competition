import json
import re
from pathlib import Path

RUN = Path('kaggle_pkg/out_v7')
LOGS = RUN / 'results' / 'logs'
PAT = RUN / 'results' / 'patches'
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')

tasks = [json.loads(l) for l in open('comp_files/tasks.jsonl', encoding='utf-8')]
tot = {'edit_file': 0, 'write_file': 0}
nopatch = []
mm = set()
for t in tasks:
    tid = t['instance_id']
    p = LOGS / (tid + '.log')
    txt = ANSI.sub('', p.read_text(encoding='utf-8', errors='replace')) if p.exists() else ''
    e = len(re.findall(r'\bedit_file\b', txt))
    w = len(re.findall(r'\bwrite_file\b', txt))
    tot['edit_file'] += e
    tot['write_file'] += w
    mm.update(re.findall(r'"max_time_minutes": ([0-9.]+)', txt))
    if not (PAT / (tid + '.patch')).exists():
        nopatch.append((tid, e, w))

print('total mentions across 129 logs:', tot)
print('no-patch tasks: %d' % len(nopatch))
print('%-24s %9s %10s' % ('task', 'edit_file', 'write_file'))
for tid, e, w in nopatch:
    print('%-24s %9d %10d' % (tid, e, w))
print()
print('max_time_minutes values seen:', sorted(mm, key=float)[:10])
print('tool_calls_used values seen:', sorted({int(x) for x in re.findall(r'"tool_calls_used": (\d+)', ' '.join(
    ANSI.sub('', (LOGS / (t['instance_id'] + '.log')).read_text(encoding='utf-8', errors='replace'))
    for t in tasks if (LOGS / (t['instance_id'] + '.log')).exists()))})[:20])
