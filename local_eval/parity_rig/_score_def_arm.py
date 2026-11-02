"""Measure the DEF-substitute arm on the 7 reference-vs-definition tasks."""
import json
import re
from pathlib import Path

BASE = Path('.').resolve()
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
NEWF = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)
DIFF = re.compile(r'^diff --git a/(.+?) b/', re.M)

TASKS = {json.loads(l)['instance_id']: json.loads(l)
         for l in open('comp_files/tasks.jsonl', encoding='utf-8')}
cohort = json.loads(Path('local_eval/parity_rig/m1_locate/cohort_refdef.json').read_text())
run = Path('local_eval/parity_rig/m1_locate/agent_ctrl_e4b_def_r0')

rows = [json.loads(l) for l in (run / 'task_results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
got = {r['instance_id']: r for r in rows}
logs = run / 'logs'


def gold(t):
    p = TASKS[t].get('patch', '') or ''
    return {m.group(1).strip() for m in NEWF.finditer(p)} | set(DIFF.findall(p))


print('%-22s %-7s %-10s %-9s %-6s %s' % ('task', 'solved', 'read_gold', 'def_greps', 'dur', 'note'))
n_read = 0
for t in cohort['defect']:
    gf = gold(t)
    lg = logs / (t + '.log')
    txt = ANSI.sub('', lg.read_text(encoding='utf-8', errors='replace')) if lg.exists() else ''
    rg = any(f in txt for f in gf)
    n_read += int(rg)
    ndef = len(re.findall(r'grep[^\n]*\bdef\b', txt)) + len(re.findall(r'grep[^\n]*\bclass\b', txt))
    r = got.get(t, {})
    print('%-22s %-7s %-10s %-9d %-6.0f %s'
          % (t, r.get('resolved'), 'YES' if rg else 'no', ndef,
             r.get('duration_seconds') or 0, str(r.get('error') or '')[:26]))

ct = set(cohort['controls'])
csolved = [t for t in ct if got.get(t, {}).get('resolved')]
print()
print('MECHANISM  : defect tasks now reading the gold (definition) file: %d / 7   (baseline 0/7)' % n_read)
print('CONTROLS   : %d / %d solved   (local rig baseline on these = 6/10)' % (len(csolved), len(ct)))
print('DEFECT     : %d / 7 solved    (baseline 0/7)' % sum(1 for t in cohort['defect'] if got.get(t, {}).get('resolved')))
