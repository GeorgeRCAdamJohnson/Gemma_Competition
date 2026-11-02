import json
import re
from pathlib import Path

run = Path('kaggle_pkg/out_v7')
out = run / 'results' / 'test_outputs'
cov = {}
for line in (run / 'results' / 'task_results.jsonl').read_text(encoding='utf-8').splitlines():
    r = json.loads(line)
    cov[r['instance_id']] = r

print('task                         resolved  exit  parse')
for tid, r in cov.items():
    p = out / (tid + '.log')
    txt = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
    c = {k: int(v) for v, k in re.findall(r'(\d+)\s+(passed|failed|error|errors|skipped)', txt)}
    print('%-28s %-9s %-4s %s' % (tid, r['resolved'], r['test_exit_code'], c))

agree = tot = 0
for tid, r in cov.items():
    if r['test_exit_code'] is None:
        continue
    tot += 1
    agree += int((r['test_exit_code'] == 0) == bool(r['resolved']))
print()
print('exit_code==0 <-> resolved agreement: %d/%d' % (agree, tot))

for tid in ('rich_4077', 'fastapi_5077', 'requests_7427'):
    p = out / (tid + '.log')
    if p.exists():
        tail = [x for x in p.read_text(encoding='utf-8', errors='replace').splitlines() if x.strip()][-4:]
        print()
        print('---', tid, '---')
        for x in tail:
            print('   ', x[:150])
