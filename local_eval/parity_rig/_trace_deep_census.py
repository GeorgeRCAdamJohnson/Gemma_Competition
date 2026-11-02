"""Deep trace mining: the things the first pass never measured.

 1. write pathology   - edit_file / submit_patch failure rate (Sahil: "especially with writes")
 2. retry loops       - identical repeated tool calls (4077 r4 retried the same anchor 6x)
 3. compaction        - context compaction / truncation events (MrMadsheep's lever)
 4. find-to-commit gap- time of first edit, replicating Nir Aberman (106s solved vs 183s failed)
"""
import json
import re
import statistics
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
RUN = BASE / 'kaggle_pkg' / 'out_v7'
LOGS = RUN / 'results' / 'logs'

tasks = [json.loads(l) for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()]
solved = set(json.loads((RUN / 'recovered_full129.json').read_text(encoding='utf-8'))['solved'])

EV = re.compile(r'^\s*\[\s*([\d.]+)s\]\s*(.*)$')
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
TOOL = re.compile(r'[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]\s*([a-z_]+)|(?:^|\s)(?:🔧|🤖)\s*([a-z_]+)')
TOOL2 = re.compile(r'^\s*\[\s*([\d.]+)s\]\s+\S+\s+([a-z_]+)\b')
RES_ERR = re.compile(r'→\s*(?:error|✗)|"status":\s*"error"|\berror\b\s*\(exit', re.I)
COMPACT = re.compile(r'compact|truncat|summariz|summaris|context (?:window|limit)|history', re.I)
SAMPLE_PRINTED = [False]

rows = []
for t in tasks:
    tid = t['instance_id']
    p = LOGS / (tid + '.log')
    txt = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
    txt = ANSI.sub('', txt)
    if not txt:
        continue

    if not SAMPLE_PRINTED[0] and 'edit_file' in txt:
        SAMPLE_PRINTED[0] = True
        ls = txt.splitlines()
        i = next(j for j, l in enumerate(ls) if 'edit_file' in l)
        print('--- sample block around first edit_file (%s) ---' % tid)
        for l in ls[i:i + 4]:
            print('   ', repr(l)[:170])
        print()

    calls = []          # (time, tool)
    for line in txt.splitlines():
        m = TOOL2.match(line)
        if m:
            calls.append((float(m.group(1)), m.group(2)))

    # block-level result attribution: a tool call owns lines until the next call
    blocks = []
    cur = None
    for line in txt.splitlines():
        m = TOOL2.match(line)
        if m:
            cur = {'t': float(m.group(1)), 'tool': m.group(2), 'body': []}
            blocks.append(cur)
        elif cur is not None:
            cur['body'].append(line)

    def fails(tool):
        return sum(1 for b in blocks if b['tool'] == tool and any(RES_ERR.search(x) for x in b['body']))

    n = {k: sum(1 for b in blocks if b['tool'] == k) for k in
         ('edit_file', 'read_file', 'run_command', 'submit_patch')}
    f = {k: fails(k) for k in n}

    edit_times = [c[0] for c in calls if c[1] == 'edit_file']
    first_edit = min(edit_times) if edit_times else None

    # identical repeated calls = the same tool+args string recurring
    sig = []
    for b in blocks:
        s = ' '.join(x.strip() for x in b['body'][:1])
        sig.append((b['tool'], s[:160]))
    dup = max(Counter(sig).values()) if sig else 0

    rows.append(dict(
        tid=tid, solved=tid in solved,
        **{f'n_{k}': v for k, v in n.items()},
        **{f'f_{k}': v for k, v in f.items()},
        first_edit=first_edit,
        last_t=(calls[-1][0] if calls else None),
        ncalls=len(calls),
        max_dup=dup,
        compact=len(COMPACT.findall(txt)),
    ))

S = [r for r in rows if r['solved']]
U = [r for r in rows if not r['solved']]


def med(xs):
    xs = [x for x in xs if x is not None]
    return round(statistics.median(xs), 1) if xs else None


def rate(rs, key):
    vals = [r[key] for r in rs if r[key] is not None]
    return (sum(vals) / len(vals)) if vals else None


print('n=%d  solved=%d unsolved=%d' % (len(rows), len(S), len(U)))
print()
print('=== 1. WRITE PATHOLOGY (per task) ===')
for k in ('edit_file', 'submit_patch', 'read_file', 'run_command'):
    a, b = rate(S, 'f_' + k), rate(U, 'f_' + k)
    na, nb = med([r['n_' + k] for r in S]), med([r['n_' + k] for r in U])
    print('  %-13s calls solved/unsolved %-6s %-6s | FAILED calls mean %-6s %-6s'
          % (k, na, nb, None if a is None else round(a, 2), None if b is None else round(b, 2)))

def anyfail(rs, k):
    return sum(1 for r in rs if r['f_' + k] > 0)
print('  tasks with >=1 failed edit_file : solved %d/%d | unsolved %d/%d'
      % (anyfail(S, 'edit_file'), len(S), anyfail(U, 'edit_file'), len(U)))
print('  tasks with >=1 failed submit    : solved %d/%d | unsolved %d/%d'
      % (anyfail(S, 'submit_patch'), len(S), anyfail(U, 'submit_patch'), len(U)))

print()
print('=== 2. RETRY LOOPS (max identical call repeats) ===')
print('  median max_dup: solved %s | unsolved %s' % (med([r['max_dup'] for r in S]), med([r['max_dup'] for r in U])))
print('  tasks with >=3 identical calls: solved %d/%d | unsolved %d/%d'
      % (sum(1 for r in S if r['max_dup'] >= 3), len(S), sum(1 for r in U if r['max_dup'] >= 3), len(U)))

print()
print('=== 3. COMPACTION / TRUNCATION MENTIONS ===')
print('  median: solved %s | unsolved %s' % (med([r['compact'] for r in S]), med([r['compact'] for r in U])))
print('  tasks with >0: solved %d/%d | unsolved %d/%d'
      % (sum(1 for r in S if r['compact'] > 0), len(S), sum(1 for r in U if r['compact'] > 0), len(U)))

print()
print('=== 4. FIND-TO-COMMIT GAP (first edit_file time) ===')
fe_s = [r['first_edit'] for r in S if r['first_edit'] is not None]
fe_u = [r['first_edit'] for r in U if r['first_edit'] is not None]
print('  median first edit: solved %ss (n=%d) | unsolved %ss (n=%d)'
      % (med(fe_s), len(fe_s), med(fe_u), len(fe_u)))
print('  median TOTAL time: solved %ss | unsolved %ss' % (med([r['last_t'] for r in S]), med([r['last_t'] for r in U])))
print('  median calls     : solved %s | unsolved %s' % (med([r['ncalls'] for r in S]), med([r['ncalls'] for r in U])))

(RUN / 'trace_metrics.json').write_text(json.dumps(rows, indent=1), encoding='utf-8')
print()
print('wrote', RUN / 'trace_metrics.json')
