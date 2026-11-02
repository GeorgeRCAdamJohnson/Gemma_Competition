"""Tool-mix vs outcome across the full 129-task pool.

Hypothesis from the 17 no-patch tasks: agents drift from edit_file into
run_command heredoc loops, explore forever, and never submit.
"""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
RUN = BASE / 'kaggle_pkg' / 'out_v7'
LOGS = RUN / 'results' / 'logs'

tasks = [json.loads(l) for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()]
solved = set(json.loads((RUN / 'recovered_full129.json').read_text(encoding='utf-8'))['solved'])

TOOL_RX = re.compile(r'^\s*\[\s*[\d.]+s\]\s+[\U0001F300-\U0001FAFF\u2600-\u27BF]\s*(\w+)', re.M)
HEREDOC_RX = re.compile(r'<<-?\s*[\'"]?([A-Z]{2,8})[\'"]?')
EDIT_RX = re.compile(r'\bedit_file\b')
SUB_RX = re.compile(r'\bsubmit_patch\b')


def count(txt, name):
    return len(re.findall(r'^\s*\[\s*[\d.]+s\]\s+\S+\s+' + name + r'\b', txt, re.M)) or len(re.findall(name, txt))


rows = []
for t in tasks:
    tid = t['instance_id']
    txt = (LOGS / (tid + '.log')).read_text(encoding='utf-8', errors='replace') if (LOGS / (tid + '.log')).exists() else ''
    rows.append(dict(
        tid=tid, repo=t['repo'], solved=tid in solved,
        edit=len(EDIT_RX.findall(txt)),
        cmd=len(re.findall(r'\brun_command\b', txt)),
        heredoc=len(HEREDOC_RX.findall(txt)),
        submit=len(SUB_RX.findall(txt)),
    ))

S = [r for r in rows if r['solved']]
U = [r for r in rows if not r['solved']]


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else 0


print('%-22s %8s %8s' % ('metric (median)', 'solved', 'unsolved'))
for k in ('edit', 'cmd', 'heredoc', 'submit'):
    print('%-22s %8d %8d' % (k, med([r[k] for r in S]), med([r[k] for r in U])))

print()
print('zero edit_file calls: solved %d/%d | unsolved %d/%d'
      % (sum(1 for r in S if r['edit'] == 0), len(S), sum(1 for r in U if r['edit'] == 0), len(U)))
print('zero submit_patch  : solved %d/%d | unsolved %d/%d'
      % (sum(1 for r in S if r['submit'] == 0), len(S), sum(1 for r in U if r['submit'] == 0), len(U)))
print('>=3 heredocs       : solved %d/%d | unsolved %d/%d'
      % (sum(1 for r in S if r['heredoc'] >= 3), len(S), sum(1 for r in U if r['heredoc'] >= 3), len(U)))
print('cmd > edit         : solved %d/%d | unsolved %d/%d'
      % (sum(1 for r in S if r['cmd'] > r['edit']), len(S), sum(1 for r in U if r['cmd'] > r['edit']), len(U)))

# The clean question: among tasks where shell dominated, what is the solve rate?
shell_dom = [r for r in rows if r['cmd'] > r['edit']]
edit_dom = [r for r in rows if r['edit'] >= r['cmd']]
print()
print('solve rate | shell-dominant (cmd>edit): %d/%d = %.3f'
      % (sum(r['solved'] for r in shell_dom), len(shell_dom),
         sum(r['solved'] for r in shell_dom) / max(len(shell_dom), 1)))
print('solve rate | edit-dominant            : %d/%d = %.3f'
      % (sum(r['solved'] for r in edit_dom), len(edit_dom),
         sum(r['solved'] for r in edit_dom) / max(len(edit_dom), 1)))

print()
print('unsolved with cmd>edit (the target population):')
tgt = [r for r in shell_dom if not r['solved']]
print('   n=%d -> %s' % (len(tgt), [r['tid'] for r in tgt]))
