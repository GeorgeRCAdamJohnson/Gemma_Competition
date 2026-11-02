"""Is E4B's 27-task 'never read the gold file' a search failure or a prompt-reading failure?

If the problem_statement literally names the file/function and E4B still edits elsewhere,
that is a comprehension/prompt fix. If it names nothing, it is a search-strategy fix.
"""
import json
import re
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
NEWF = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)
DIFF = re.compile(r'^diff --git a/(.+?) b/', re.M)

TASKS = {json.loads(l)['instance_id']: json.loads(l)
         for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()}


def gold_files(t):
    txt = t.get('patch', '') or ''
    return {m.group(1).strip() for m in NEWF.finditer(txt)} | set(DIFF.findall(txt))


RUN = BASE / 'kaggle_pkg' / 'out_e4b'
rows = [json.loads(l) for l in (RUN / 'results' / 'task_results.all.jsonl')
        .read_text(encoding='utf-8').splitlines() if l.strip()]
logs = RUN / 'results' / 'logs'

named_file = unnamed_file = 0
examples = []
named_examples = []
for r in rows:
    if r.get('resolved'):
        continue
    tid = r['instance_id']
    t = TASKS.get(tid, {})
    gf = gold_files(t)
    if not gf:
        continue
    log = ANSI.sub('', (logs / (tid + '.log')).read_text(encoding='utf-8', errors='replace')) \
        if (logs / (tid + '.log')).exists() else ''
    if any(f in log for f in gf):
        continue                                   # it did reach the right file
    ps = (t.get('problem_statement') or '')
    basenames = {Path(f).name for f in gf}
    hits = [b for b in basenames if b in ps]
    # also: does the statement name the full path or module dotted form?
    dotted = {f[:-3].replace('/', '.') for f in gf if f.endswith('.py')}
    hits += [d for d in dotted if d in ps]
    if hits:
        named_file += 1
        if len(named_examples) < 6:
            named_examples.append((tid, sorted(basenames), hits[:2], log.count('read_file'),
                                   log.count('run_command'), log.count('edit_file')))
    else:
        unnamed_file += 1
        if len(examples) < 6:
            examples.append((tid, sorted(basenames), log.count('read_file'),
                             log.count('run_command'), log.count('edit_file')))

print('E4B tasks that NEVER touched the gold file, split by whether the problem')
print('statement literally names that file:')
print('  statement NAMES the gold file      : %d' % named_file)
print('  statement does NOT name it         : %d' % unnamed_file)
print()
print('  names it, still went elsewhere (tid, gold files, matched tokens, reads/cmds/edits):')
for e in named_examples:
    print('    %-22s %-38s %-22s r=%-2d c=%-2d e=%d' % (e[0], e[1], e[2], e[3], e[4], e[5]))
print()
print('  not named (tid, gold files, reads/cmds/edits):')
for e in examples:
    print('    %-22s %-42s r=%-2d c=%-2d e=%d' % (e[0], e[1], e[2], e[3], e[4]))
