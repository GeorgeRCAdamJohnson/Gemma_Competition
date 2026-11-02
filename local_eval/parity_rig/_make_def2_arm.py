"""DEF-SUBSTITUTE v2: cover the three shapes that v1 missed.

v1 test (7 tasks): 4/7 reached the definition file, 1/7 solved, controls held.
The three that never reached the gold file were:
  - fastapi_14492 : gold is a DOCS EXAMPLE -> no def/class exists to grep for
  - fastapi_9555  : def greps ran, still never opened models.py
  - rich_3067     : target is a literal/constant construction, not a definition

v2 keeps the definition test and adds a fallback ladder in the SAME sentence:
  1. a def/class named in the statement  -> edit at the definition
  2. a literal/constant/string from the statement -> edit where it is CONSTRUCTED
  3. otherwise -> nearest enclosing def of the usage, never a bare call site
Still a substitution, so one rule about grepping, not two.
"""
import hashlib
import json
import re
import shutil
from pathlib import Path

RIG = Path(__file__).resolve().parent
src, dst = RIG / 'agent_ctrl_e4b', RIG / 'agent_ctrl_e4b_def2'
if dst.exists():
    shutil.rmtree(dst)
shutil.copytree(src, dst)

OLD = ("2. BEFORE the edit: grep your anchor - run `grep -n -A 20 '<the exact symbol you are about "
       "to edit>' <file>` and confirm the problem's symbol/behaviour appears INSIDE that span. If it "
       "does not, you are at the wrong anchor: find the right function first (the shortest correct "
       "anchor beats the nearest plausible one).")
NEW = ("2. BEFORE the edit: grep your anchor by DEFINITION, not by usage. "
       "`grep -rn 'def <symbol>' .` and `grep -rn 'class <symbol>' .` - edit where it is DEFINED. "
       "A call or reference is NOT the definition; if the symbol only appears being USED you are in "
       "the wrong file. If it is defined nowhere (a literal, constant, string or doc example), grep "
       "that exact literal instead and edit where it is CONSTRUCTED, not where it is read. "
       "Then confirm the problem's symbol/behaviour appears INSIDE the span you will edit.")

p = dst / 'prompts' / 'system.md'
txt = p.read_text(encoding='utf-8')
assert OLD in txt
new = txt.replace(OLD, NEW)
p.write_text(new, encoding='utf-8', newline='')

print('baseline chars %d -> v2 %d (delta %+d)' % (len(txt), len(new), len(new) - len(txt)))
print('sha1: b08b32a2438d -> %s' % hashlib.sha1(p.read_bytes()).hexdigest()[:12])
print()

# ---- cohort: every process-fixable task in the 26-task gap, plus controls ----
BASE = RIG.parents[1]
E4B = BASE / 'kaggle_pkg' / 'out_e4b' / 'results'
V7 = BASE / 'kaggle_pkg' / 'out_v7' / 'results'
NEWF = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)
DIFF = re.compile(r'^diff --git a/(.+?) b/', re.M)
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))?', re.M)
TASKS = {json.loads(l)['instance_id']: json.loads(l)
         for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()}


def parse(text):
    files, cur = {}, None
    for line in (text or '').splitlines():
        m = NEWF.match(line) or DIFF.match(line)
        if m:
            cur = m.group(1).strip()
            if cur != '/dev/null':
                files.setdefault(cur, [])
            continue
        m = HUNK.match(line)
        if m and cur:
            files[cur].append(int(m.group(1)))
    return files


s31 = set(json.loads((V7.parent / 'recovered_full129.json').read_text(encoding='utf-8'))['solved'])
rows = [json.loads(l) for l in (E4B / 'task_results.all.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
se4 = {r['instance_id'] for r in rows if r.get('resolved')}

proc = []
for tid in sorted(s31 - se4):
    gold = parse(TASKS.get(tid, {}).get('patch', ''))
    pp = E4B / 'patches' / (tid + '.patch')
    mine = parse(pp.read_text(encoding='utf-8', errors='replace')) if pp.exists() else {}
    if not mine:
        continue
    shared = set(gold) & set(mine)
    if not shared:
        proc.append(tid)
    else:
        d = min(abs(a - b) for f in shared for a in gold[f] for b in mine[f]) if shared else 999
        if d > 100:
            proc.append(tid)

controls = [r['instance_id'] for r in rows if r.get('resolved')]
cohort = dict(defect=sorted(proc), controls=controls, overflow=[], timeout=[], all=sorted(proc) + controls)
out = RIG / 'm1_locate' / 'cohort_proc.json'
out.write_text(json.dumps(cohort, indent=1), encoding='utf-8')
print('process-fixable defect set (%d): %s' % (len(proc), sorted(proc)))
print('controls (%d), total cohort %d -> %s' % (len(controls), len(cohort['all']), out))
