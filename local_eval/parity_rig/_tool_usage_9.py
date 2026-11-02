"""Which of the 9 harness tools do E4B and 31B actually use?

If the graph/code-intelligence tools are unused by E4B, the lever is tool discovery,
not more prose about searching -- a mechanically different axis from the anchor rule.
"""
import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
CALL = re.compile(r'^\s*\[\s*[\d.]+s\]\s+\S+\s+([a-z_]+)\b', re.M)

TOOLS = ['run_command', 'read_file', 'edit_file', 'write_file', 'get_status', 'submit_patch',
         'get_code_neighbors', 'search_similar_code', 'get_code_subgraph']


def scan(run: Path, label: str):
    p = run / 'results' / 'task_results.all.jsonl'
    if p.exists():
        ids = [json.loads(l)['instance_id'] for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
    else:
        ids = [r['instance_id'] for r in json.loads(
            (run / 'recovered_full129.json').read_text(encoding='utf-8'))['rows']]
    logs = run / 'results' / 'logs'
    tot = Counter()
    users = Counter()
    n = 0
    for tid in ids:
        f = logs / (tid + '.log')
        if not f.exists():
            continue
        n += 1
        txt = ANSI.sub('', f.read_text(encoding='utf-8', errors='replace'))
        seen = set()
        for m in CALL.finditer(txt):
            t = m.group(1)
            if t in TOOLS:
                tot[t] += 1
                seen.add(t)
        for t in seen:
            users[t] += 1
    print('\n%-8s n=%d' % (label, n))
    print('  %-20s %8s %10s' % ('tool', 'calls', 'tasks used'))
    for t in TOOLS:
        print('  %-20s %8d %8d (%3.0f%%)' % (t, tot[t], users[t], 100 * users[t] / max(n, 1)))
    return tot, users, n


e = scan(BASE / 'kaggle_pkg' / 'out_e4b', 'E4B')
v = scan(BASE / 'kaggle_pkg' / 'out_v7', '31B')

print('\n=== code-intelligence tools (the ones the anchor rule cannot replace) ===')
CI = ['get_code_neighbors', 'search_similar_code', 'get_code_subgraph']
for label, (tot, users, n) in (('E4B', e), ('31B', v)):
    c = sum(tot[t] for t in CI)
    u = sum(1 for _ in range(0))  # placeholder
    print('  %-4s total CI calls %4d (%.1f/task) | tasks using any CI tool: %s'
          % (label, c, c / max(n, 1),
             sum(1 for t in CI if users[t] > 0)))
    for t in CI:
        print('        %-20s calls %4d | tasks %3d' % (t, tot[t], users[t]))
