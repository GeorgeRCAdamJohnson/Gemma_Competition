import json
import re
from pathlib import Path

RUN = Path('kaggle_pkg/out_v7')
LOGS = RUN / 'results' / 'logs'
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')

tasks = [json.loads(l) for l in open('comp_files/tasks.jsonl', encoding='utf-8')]
vals = {}
maxes = {}
implied = []
for t in tasks:
    p = LOGS / (t['instance_id'] + '.log')
    if not p.exists():
        continue
    txt = ANSI.sub('', p.read_text(encoding='utf-8', errors='replace'))
    for m in re.finditer(r'max_time_minutes"?\s*:\s*([0-9.]+)', txt):
        vals[m.group(1)] = vals.get(m.group(1), 0) + 1
    for m in re.finditer(r'time_seconds_remaining"?\s*:\s*([0-9.]+)', txt):
        rem = float(m.group(1))
        # find the elapsed stamp of the enclosing line
        line_start = txt.rfind('[', 0, m.start())
        ts = re.search(r'\[\s*([0-9.]+)s\]', txt[line_start:m.start()]) if line_start >= 0 else None
        if ts:
            implied.append(float(ts.group(1)) + rem)

print('max_time_minutes values seen:', vals)
if implied:
    implied.sort()
    print('implied total budget (elapsed + remaining): '
          'n=%d min=%s median=%s max=%s'
          % (len(implied), round(implied[0]), round(implied[len(implied) // 2]), round(implied[-1])))
print()
print('tool_calls_used seen:', sorted({int(x) for x in re.findall(
    r'tool_calls_used"?\s*:\s*(\d+)', ' '.join(
        ANSI.sub('', (LOGS / (t['instance_id'] + '.log')).read_text(encoding='utf-8', errors='replace'))
        for t in tasks if (LOGS / (t['instance_id'] + '.log')).exists()))}))
