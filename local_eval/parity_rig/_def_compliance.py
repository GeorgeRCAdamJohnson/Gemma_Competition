"""Proper compliance measurement: read `steps` tool calls and their arguments.

The earlier attempt matched the prompt text embedded in the trace (which literally contains
"grep -rn 'def <symbol>'") and therefore reported a false 100% compliance.
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


def tool_calls(tid):
    p = D / 'traces' / f'trace_{tid}.json'
    if not p.exists():
        return []
    d = json.loads(p.read_text(encoding='utf-8', errors='replace'))
    out = []
    for st in d.get('steps') or []:
        for tc in (st.get('tool_calls') or []):
            fn = (tc.get('function') or tc.get('function_call') or {})
            name = fn.get('name') or tc.get('name') or ''
            args = fn.get('arguments') or tc.get('arguments') or ''
            if isinstance(args, (dict, list)):
                args = json.dumps(args)
            out.append((str(name), str(args)))
    return out


DEFGREP = re.compile(r'grep[^\n]{0,100}?(?:-rn|-R\b|-n\s+-r)[^\n]{0,100}?\b(?:def|class)\b', re.I)

print('%-16s %-6s %-6s %-9s %-10s %s' % ('task', 'calls', 'def?', 'before?', 'localised', 'resolved'))
comp = 0
for t in COHORT:
    calls = tool_calls(t)
    names = [n for n, _ in calls]
    first_edit = names.index('edit_file') if 'edit_file' in names else None
    defidx = None
    for i, (n, a) in enumerate(calls):
        if n == 'run_command' and DEFGREP.search(a):
            defidx = i
            break
    before = defidx is not None and (first_edit is None or defidx < first_edit)
    if defidx is not None:
        comp += 1
    p = D / 'patches' / f'{t}.patch'
    f = set(FILES.findall(p.read_text(encoding='utf-8', errors='replace'))) if p.exists() else set()
    loc = 'gold_file' if (f and gold.get(t) and (f & gold[t])) else ('wrong_file' if f else 'no_edit')
    print('%-16s %-6d %-6s %-9s %-10s %s' % (t, len(calls), 'YES' if defidx is not None else 'no',
                                             'yes' if before else 'no', loc,
                                             (recs.get(t) or {}).get('resolved')))
print('\ncompliance (executed a def/class grep): %d/%d = %.0f%%' % (
    comp, len(COHORT), 100 * comp / len(COHORT)))
