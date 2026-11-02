"""YOUR HYPOTHESIS: winners read a sibling implementation as a template.

The log says "the prompt never TOLD it to read a sibling reference file -> winners do this
spontaneously". Measure it inside E4B: do SOLVED runs read more distinct files, and more
files in the SAME DIRECTORY as the gold file, than UNSOLVED runs?

If a positive contrast exists, template-as-oracle is the arm to build.
"""
import json
import re
import statistics
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
RUN = BASE / 'kaggle_pkg' / 'out_e4b' / 'results'
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
NEWF = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)
DIFF = re.compile(r'^diff --git a/(.+?) b/', re.M)
READ = re.compile(r'read_file\s*\(([^)]+)\)')
CMD = re.compile(r'run_command\s+(.{0,120})')
EDIT = re.compile(r'edit_file\s*\(([^)]+)\)')

TASKS = {json.loads(l)['instance_id']: json.loads(l)
         for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()}


def gold(t):
    txt = t.get('patch', '') or ''
    return {m.group(1).strip() for m in NEWF.finditer(txt)} | set(DIFF.findall(txt))


rows = [json.loads(l) for l in (RUN / 'task_results.all.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
logs = RUN / 'logs'

recs = []
for r in rows:
    tid = r['instance_id']
    gf = gold(TASKS.get(tid, {}))
    if not gf:
        continue
    gp = next(iter(gf))
    gdir = str(Path(gp).parent)
    lg = logs / (tid + '.log')
    txt = ANSI.sub('', lg.read_text(encoding='utf-8', errors='replace')) if lg.exists() else ''

    reads = [x.strip() for x in READ.findall(txt)]
    # cut everything after the first edit: we care about PRE-EDIT behaviour
    m = EDIT.search(txt)
    pre = txt[:m.start()] if m else txt
    pre_reads = [x.strip() for x in READ.findall(pre)]
    pre_cmds = CMD.findall(pre)

    # sibling = a file in the same directory as the gold file, but not the gold file itself
    siblings = {x for x in pre_reads if str(Path(x).parent) == gdir and x != gp}
    same_pkg = {x for x in pre_reads if str(Path(x).parent).split('/')[0] == gdir.split('/')[0]}
    # did it grep for the gold symbol rather than the file?
    grepped_gold = any(Path(gp).stem in c for c in pre_cmds)

    recs.append(dict(tid=tid, solved=bool(r.get('resolved')),
                     n_read_pre=len(pre_reads), n_read=len(reads),
                     siblings=len(siblings), same_pkg=len(same_pkg),
                     grepped_gold=grepped_gold, read_gold=gp in reads))

S = [x for x in recs if x['solved']]
U = [x for x in recs if not x['solved']]


def med(rs, k):
    return statistics.median([x[k] for x in rs]) if rs else 0


def pct(rs, k):
    return 100 * sum(1 for x in rs if x[k]) / len(rs) if rs else 0


print('E4B, tasks with a gold patch: solved %d | unsolved %d' % (len(S), len(U)))
print()
print('%-34s %10s %10s' % ('metric', 'SOLVED', 'UNSOLVED'))
print('%-34s %10s %10s' % ('median read_file BEFORE first edit', med(S, 'n_read_pre'), med(U, 'n_read_pre')))
print('%-34s %10s %10s' % ('median total read_file calls', med(S, 'n_read'), med(U, 'n_read')))
print('%-34s %10s %10s' % ('median SIBLING files read pre-edit', med(S, 'siblings'), med(U, 'siblings')))
print('%-34s %10s %10s' % ('median same-package files pre-edit', med(S, 'same_pkg'), med(U, 'same_pkg')))
print()
print('%-34s %9.0f%% %9.0f%%' % ('% reading >=1 SIBLING pre-edit', pct(S, 'siblings'), pct(U, 'siblings')))
print('%-34s %9.0f%% %9.0f%%' % ('% grepping the gold FILE stem', pct(S, 'grepped_gold'), pct(U, 'grepped_gold')))
print('%-34s %9.0f%% %9.0f%%' % ('% ever reading the gold file', pct(S, 'read_gold'), pct(U, 'read_gold')))
print()
print('solved-task pre-edit reads in detail:')
for x in sorted(S, key=lambda z: -z['siblings'])[:12]:
    print('  %-22s siblings=%d same_pkg=%d pre_reads=%d total_reads=%d grep_gold=%s'
          % (x['tid'], x['siblings'], x['same_pkg'], x['n_read_pre'], x['n_read'], x['grepped_gold']))
