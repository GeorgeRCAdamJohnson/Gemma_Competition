"""What test dependencies is the rig missing? Enumerated from collection-error logs."""
import re
from collections import Counter
from pathlib import Path

RIG = Path(__file__).resolve().parent
LOGS = RIG / 'm1_capped' / 'agent_ctrl_e4b_r0' / 'test_outputs'

mods = Counter()
tasks = []
for p in sorted(LOGS.glob('*.log')):
    txt = p.read_text(encoding='utf-8', errors='replace')
    if 'ERROR collecting' not in txt:
        continue
    tasks.append(p.stem)
    for m in re.findall(r"No module named '([^']+)'", txt):
        mods[m] += 1
    for m in re.findall(r'cannot import name [\'"]([A-Za-z0-9_]+)[\'"]', txt):
        mods['cannot-import:' + m] += 1

print('tasks blocked by collection errors:', len(tasks))
print('distinct missing modules:', len(mods))
for m, n in mods.most_common():
    print('  %-34s %d' % (m, n))
print('\ntasks:', ' '.join(tasks))
