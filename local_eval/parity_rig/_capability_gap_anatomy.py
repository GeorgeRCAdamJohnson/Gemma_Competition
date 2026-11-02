"""Deep forensics on the capability gap: tasks 31B solves and E4B does not.

For each of the '31B-only' tasks, compare the two traces on:
  - first tool action (grep vs read-whole-file vs edit)
  - reads before first edit; whether the GOLD file was read
  - line-level hunk proximity of the agent's edit to the gold hunk
  - patch shape (added vs removed lines, hunks, files)
and characterise what 31B does that E4B does not.
"""
import json
import re
import statistics
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
E4B = BASE / 'kaggle_pkg' / 'out_e4b' / 'results'
V7 = BASE / 'kaggle_pkg' / 'out_v7' / 'results'

ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
NEWF = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)
DIFF = re.compile(r'^diff --git a/(.+?) b/', re.M)
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', re.M)
ACTION = re.compile(r'^\s*\[\s*[\d.]+s\]\s+\S+\s+(read_file|run_command|edit_file|write_file|get_status|submit_patch)\b', re.M)

TASKS = {json.loads(l)['instance_id']: json.loads(l)
         for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()}


def gold_files(t):
    txt = t.get('patch', '') or ''
    return {m.group(1).strip() for m in NEWF.finditer(txt)} | set(DIFF.findall(txt))


def parse(text):
    files = {}
    cur = None
    for line in (text or '').splitlines():
        m = NEWF.match(line) or DIFF.match(line)
        if m:
            cur = m.group(1).strip()
            if cur != '/dev/null':
                files.setdefault(cur, [])
            continue
        m = HUNK.match(line)
        if m and cur:
            files[cur].append((int(m.group(1)), int(m.group(2) or 1)))
    adds = sum(1 for l in (text or '').splitlines() if l.startswith('+') and not l.startswith('+++'))
    dels = sum(1 for l in (text or '').splitlines() if l.startswith('-') and not l.startswith('---'))
    return files, adds, dels


def trace(run: Path, tid: str):
    lg = run / 'logs' / (tid + '.log')
    txt = ANSI.sub('', lg.read_text(encoding='utf-8', errors='replace')) if lg.exists() else ''
    acts = ACTION.findall(txt)
    m = re.search(r'edit_file', txt)
    pre = txt[:m.start()] if m else txt
    pre_reads = re.findall(r'read_file\s*\(([^)]+)\)', pre)
    return dict(actions=acts, n_calls=len(acts), first=(acts[0] if acts else None),
                pre_reads=[x.strip() for x in pre_reads])


def solved_set(run: Path, rec=None):
    """run is the RESULTS dir; tolerate either nesting."""
    for p in (run / 'task_results.all.jsonl', run / 'results' / 'task_results.all.jsonl'):
        if p.exists():
            rows = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
            if len(rows) > 20:
                return {r['instance_id'] for r in rows if r.get('resolved')}
    if rec and rec.exists():
        return set(json.loads(rec.read_text(encoding='utf-8'))['solved'])
    return set()


s31 = solved_set(V7, V7.parent / 'recovered_full129.json')
se4 = solved_set(E4B)
only31 = sorted(s31 - se4)
onlye4 = sorted(se4 - s31)
both = sorted(s31 & se4)

print('31B solved %d | E4B solved %d | both %d | 31B-only %d | E4B-only %d'
      % (len(s31), len(se4), len(both), len(only31), len(onlye4)))
print('E4B-only:', onlye4)
print()
print('%-22s %-11s %-11s %5s %5s %5s %5s %s' % ('31B-only task', 'first31', 'firstE4B', 'r31', 'rE4', 'a31', 'aE4', 'E4B read gold?'))
n_gold_read = 0
for tid in only31:
    t = TASKS.get(tid, {})
    gf = gold_files(t)
    t31 = trace(V7, tid)
    te4 = trace(E4B, tid)
    e4_read_gold = any(f in ' '.join(te4['pre_reads']) for f in gf)
    n_gold_read += int(e4_read_gold)
    p31 = V7 / 'patches' / (tid + '.patch')
    pe4 = E4B / 'patches' / (tid + '.patch')
    _, a31, _ = parse(p31.read_text(encoding='utf-8', errors='replace') if p31.exists() else '')
    _, aE4, _ = parse(pe4.read_text(encoding='utf-8', errors='replace') if pe4.exists() else '')
    print('%-22s %-11s %-11s %5d %5d %5d %5d %s'
          % (tid, str(t31['first'])[:10], str(te4['first'])[:10],
             len(t31['pre_reads']), len(te4['pre_reads']), a31, aE4, 'YES' if e4_read_gold else 'no'))

print()
print('E4B read the gold file on %d / %d of the 31B-only tasks' % (n_gold_read, len(only31)))


def med(xs):
    return int(statistics.median(xs)) if xs else 0


for label, ids, run in (('31B', only31, V7), ('E4B', only31, E4B)):
    rr = [len(trace(run, t)['pre_reads']) for t in ids]
    nn = [trace(run, t)['n_calls'] for t in ids]
    firsts = {}
    for t in ids:
        f = trace(run, t)['first']
        firsts[f] = firsts.get(f, 0) + 1
    print('%-4s on the 31B-only set: median pre-edit reads %-3d median calls %-3d first-action mix %s'
          % (label, med(rr), med(nn), dict(sorted(firsts.items(), key=lambda kv: -kv[1]))))
