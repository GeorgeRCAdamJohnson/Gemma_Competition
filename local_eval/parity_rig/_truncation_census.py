"""Does the harness's silent read truncation (150 lines / 10000 chars) cause misdiagnosis?

If read_file returns exactly the cap, the agent may believe it saw the whole file
while the answer sits beyond the cut.
"""
import json
import re
from pathlib import Path

RUN = Path('kaggle_pkg/out_v7')
LOGS = RUN / 'results' / 'logs'
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')

tasks = [json.loads(l) for l in open('comp_files/tasks.jsonl', encoding='utf-8')]
solved = set(json.loads((RUN / 'recovered_full129.json').read_text(encoding='utf-8'))['solved'])

rows = []
for t in tasks:
    tid = t['instance_id']
    p = LOGS / (tid + '.log')
    if not p.exists():
        continue
    txt = ANSI.sub('', p.read_text(encoding='utf-8', errors='replace'))

    # read_file results embed the content between 'content': ' and the closing quote
    trunc = 0
    reads = 0
    for m in re.finditer(r"'filepath': '([^']+)', 'content': (.*?)\n", txt):
        reads += 1
        body = m.group(2)
        lines = body.count('\\n')
        if lines >= 145 or len(body) >= 9900:
            trunc += 1
    # harness wording for truncation, if any
    word = len(re.findall(r'truncat|\.\.\.\s*\(truncated|more lines|showing first', txt, re.I))

    rows.append(dict(tid=tid, solved=tid in solved, reads=reads, trunc=trunc, truncword=word))

S = [r for r in rows if r['solved']]
U = [r for r in rows if not r['solved']]


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0


print('n=%d solved=%d unsolved=%d' % (len(rows), len(S), len(U)))
print()
print('%-28s %8s %8s' % ('median', 'solved', 'unsolved'))
print('%-28s %8d %8d' % ('read_file calls', med([r['reads'] for r in S]), med([r['reads'] for r in U])))
print('%-28s %8d %8d' % ('CAP-HITTING reads (>=145 ln)', med([r['trunc'] for r in S]), med([r['trunc'] for r in U])))
print('%-28s %8d %8d' % ('explicit truncation wording', med([r['truncword'] for r in S]), med([r['truncword'] for r in U])))

print()
print('tasks with >=1 cap-hitting read : solved %d/%d | unsolved %d/%d'
      % (sum(1 for r in S if r['trunc'] > 0), len(S), sum(1 for r in U if r['trunc'] > 0), len(U)))
print('tasks with >=1 truncation wording: solved %d/%d | unsolved %d/%d'
      % (sum(1 for r in S if r['truncword'] > 0), len(S), sum(1 for r in U if r['truncword'] > 0), len(U)))

tot_trunc = sum(r['trunc'] for r in rows)
tot_reads = sum(r['reads'] for r in rows)
print()
print('pool-wide: %d cap-hitting reads out of %d parsed reads (%.1f%%)'
      % (tot_trunc, tot_reads, 100 * tot_trunc / max(tot_reads, 1)))
