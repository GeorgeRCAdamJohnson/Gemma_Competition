"""Does E4B obey/call the budget mechanism at all? If not, numeric prompt edits are inert."""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')


def scan(run: Path, label: str):
    p = run / 'results' / 'task_results.all.jsonl'
    if p.exists():
        rows = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
    else:
        rec = json.loads((run / 'recovered_full129.json').read_text(encoding='utf-8'))
        rows = [dict(instance_id=r['instance_id']) for r in rec['rows']]
    logs = run / 'results' / 'logs'
    gs_tasks = gs_total = reads = cmds = edits = calls = 0
    n = 0
    for r in rows:
        p = logs / (r['instance_id'] + '.log')
        if not p.exists():
            continue
        n += 1
        t = ANSI.sub('', p.read_text(encoding='utf-8', errors='replace'))
        g = len(re.findall(r'\bget_status\b', t))
        gs_total += g
        gs_tasks += int(g > 0)
        reads += len(re.findall(r'\bread_file\b', t))
        cmds += len(re.findall(r'\brun_command\b', t))
        edits += len(re.findall(r'\bedit_file\b', t))
        calls += len(re.findall(r'^\s*\[\s*[\d.]+s\]\s+\S+\s+[a-z_]+\b', t, re.M))
    print('%-14s tasks=%d | get_status called in %d (%.0f%%) total %d | reads %d cmds %d edits %d'
          % (label, n, gs_tasks, 100 * gs_tasks / max(n, 1), gs_total, reads, cmds, edits))
    print('%-14s per-task means: reads %.1f cmds %.1f edits %.1f | get_status %.2f'
          % ('', reads / max(n, 1), cmds / max(n, 1), edits / max(n, 1), gs_total / max(n, 1)))
    return dict(tasks=n, gs_tasks=gs_tasks, gs=gs_total, reads=reads, cmds=cmds, edits=edits)


print('=== budget-mechanism usage ===')
e = scan(BASE / 'kaggle_pkg' / 'out_e4b', 'E4B')
v = scan(BASE / 'kaggle_pkg' / 'out_v7', '31B')
