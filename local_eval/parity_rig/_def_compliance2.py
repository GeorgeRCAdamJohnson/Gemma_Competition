"""Correct compliance measurement: the model runs the def-grep, but SCOPED TO THE ALREADY-CHOSEN FILE.

That form cannot falsify the file choice, so the rule is executed in a degenerate shape.
Classify each def-grep as repo-wide (-r/-R) or single-file.
"""
import json
import re
from pathlib import Path

D = Path(r'C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval\parity_rig\m1_refdef\agent_ctrl_e4b_def_r0')
TASKS = Path(r'C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\comp_files\tasks.jsonl')
COHORT = ['fastapi_14372', 'fastapi_14458', 'fastapi_14492', 'fastapi_9555',
          'rich_3067', 'rich_3480', 'rich_4077']
FILES = re.compile(r'^\+\+\+ b/(.*?)$', re.M)

gold = {}
for line in TASKS.read_text(encoding='utf-8').splitlines():
    if line.strip():
        r = json.loads(line)
        gold[r['instance_id']] = set(FILES.findall(r.get('patch') or ''))
recs = {r['instance_id']: r for r in
        (json.loads(l) for l in (D / 'task_results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip())}


def calls(tid):
    p = D / 'traces' / f'trace_{tid}.json'
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding='utf-8', errors='replace'))
    out = []
    for st in d.get('steps') or []:
        for tc in (st.get('tool_calls') or []):
            out.append((tc.get('function_name') or '',
                        tc.get('arguments') or {}))
    return out


DEFPAT = re.compile(r'\bdef\s+\w+|\bclass\s+\w+')
print('%-16s %-5s %-11s %-11s %-10s %s' % ('task', 'calls', 'def-grep', 'repo-wide?', 'localised', 'resolved'))
repo_wide = single = none = 0
for t in COHORT:
    cs = calls(t)
    kind = 'none'
    for name, a in cs:
        if name != 'run_command':
            continue
        cmd = str((a or {}).get('command') or '')
        if 'grep' in cmd and DEFPAT.search(cmd):
            # repo-wide if -r/-R present, or the target is '.' / a directory
            if re.search(r'\s-[A-Za-z]*[rR]', cmd) or re.search(r'\s\.\s*$', cmd):
                kind = 'REPO-WIDE'
            else:
                kind = 'single-file'
            break
    if kind == 'REPO-WIDE':
        repo_wide += 1
    elif kind == 'single-file':
        single += 1
    else:
        none += 1
    p = D / 'patches' / f'{t}.patch'
    f = set(FILES.findall(p.read_text(encoding='utf-8', errors='replace'))) if p.exists() else set()
    loc = 'gold_file' if (f and gold.get(t) and (f & gold[t])) else ('wrong_file' if f else 'no_edit')
    print('%-16s %-5d %-11s %-11s %-10s %s' % (t, len(cs), kind,
                                               'yes' if kind == 'REPO-WIDE' else 'NO', loc,
                                               (recs.get(t) or {}).get('resolved')))
print('\ndef-grep executed : %d/7  (repo-wide %d, single-file %d, none %d)' % (
    repo_wide + single, repo_wide, single, none))
print('the rule asks for `grep -rn "def <symbol>" .` -> repo-wide. Compliance: %d/7 = %.0f%%' % (
    repo_wide, 100 * repo_wide / 7))
