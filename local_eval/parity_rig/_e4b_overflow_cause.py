"""Did thinking volume cause the 6 E4B context overflows?

thinking_budget 4096 permits ~4k tokens of thinking PER TURN; over 17-26 turns that can
exceed the 32768 window on its own. Measure accumulated thinking chars per task and
compare overflow tasks against solved / other-failed tasks.
"""
import json
import re
import statistics
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
RUN = BASE / 'kaggle_pkg' / 'out_e4b' / 'results'
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
THINK = re.compile(r'💭\s*\((\d+)\s*chars\)')
TOOLOUT = re.compile(r"'\s*content':\s*'(.*?)'", re.S)

rows = [json.loads(l) for l in (RUN / 'task_results.all.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
logs = RUN / 'logs'


def kind(r):
    e = str(r.get('error') or '')
    if r.get('resolved'):
        return 'solved'
    if 'ContextWindow' in e:
        return 'overflow'
    if 'session timeout' in e:
        return 'timeout'
    return 'other_fail'


buckets = {}
for r in rows:
    tid = r['instance_id']
    lg = logs / (tid + '.log')
    txt = ANSI.sub('', lg.read_text(encoding='utf-8', errors='replace')) if lg.exists() else ''
    think_chars = sum(int(x) for x in THINK.findall(txt))
    n_think = len(THINK.findall(txt))
    tool_chars = sum(len(m) for m in TOOLOUT.findall(txt))
    # rough token estimate: ~4 chars/token
    buckets.setdefault(kind(r), []).append(dict(
        tid=tid, think_chars=think_chars, n_think=n_think, tool_chars=tool_chars,
        est_tokens=(think_chars + tool_chars) // 4))

print('%-12s %4s | %10s %10s %10s %10s' % ('bucket', 'n', 'thinkChars', 'nThink', 'toolChars', 'estTokens'))
for k in ('solved', 'overflow', 'timeout', 'other_fail'):
    rs = buckets.get(k, [])
    if not rs:
        continue
    def med(f):
        return int(statistics.median([x[f] for x in rs]))
    print('%-12s %4d | %10d %10d %10d %10d' % (k, len(rs), med('think_chars'), med('n_think'),
                                                med('tool_chars'), med('est_tokens')))

print('\noverflow tasks in detail:')
for x in sorted(buckets.get('overflow', []), key=lambda z: -z['est_tokens']):
    print('  %-22s think=%7d chars (%2d blocks)  tools=%7d chars  est=%6d tok'
          % (x['tid'], x['think_chars'], x['n_think'], x['tool_chars'], x['est_tokens']))

print('\ntop-10 est_tokens across ALL tasks (is overflow simply the heavy end?):')
allr = [x for v in buckets.values() for x in v]
for x in sorted(allr, key=lambda z: -z['est_tokens'])[:10]:
    print('  %-22s est=%6d tok  think=%7d  tools=%7d' % (x['tid'], x['est_tokens'], x['think_chars'], x['tool_chars']))
