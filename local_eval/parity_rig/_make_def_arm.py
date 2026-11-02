"""Build the DEF-SUBSTITUTE arm.

Distinction from ddv3 (already tested, 2/24): ddv3 ADDED a 'define it where it is defined'
rule while leaving ca5's anchor grep intact -> two overlapping grep rules -> edits/rep
2.15 -> 0.54 (rule collision). This arm SUBSTITUTES ca5's anchor-grep sentence with a
definition-targeted grep of similar length, so the prompt grows by ~0 chars and there is
exactly ONE rule about grepping.
"""
import hashlib
import json
import shutil
from pathlib import Path

RIG = Path(__file__).resolve().parent
src, dst = RIG / 'agent_ctrl_e4b', RIG / 'agent_ctrl_e4b_def'
if dst.exists():
    shutil.rmtree(dst)
shutil.copytree(src, dst)

OLD = ("2. BEFORE the edit: grep your anchor - run `grep -n -A 20 '<the exact symbol you are about "
       "to edit>' <file>` and confirm the problem's symbol/behaviour appears INSIDE that span. If it "
       "does not, you are at the wrong anchor: find the right function first (the shortest correct "
       "anchor beats the nearest plausible one).")
NEW = ("2. BEFORE the edit: grep your anchor by DEFINITION, not by usage - run `grep -rn 'def <symbol>' .` "
       "and `grep -rn 'class <symbol>' .` to find where it is DEFINED, then `grep -n -A 20 '<symbol>' "
       "<that file>` and confirm the problem's symbol/behaviour appears INSIDE that span. A call or "
       "reference is NOT the definition: if the symbol only appears being USED, you are in the wrong "
       "file - locate the class/function that DEFINES it.")

p = dst / 'prompts' / 'system.md'
txt = p.read_text(encoding='utf-8')
assert OLD in txt, 'anchor sentence not found verbatim'
new = txt.replace(OLD, NEW)
p.write_text(new, encoding='utf-8', newline='')

print('baseline prompt chars: %d' % len(txt))
print('arm      prompt chars: %d  (delta %+d)' % (len(new), len(new) - len(txt)))
print('sha1 baseline b08b32a2438d -> arm %s' % hashlib.sha1(p.read_bytes()).hexdigest()[:12])
print()
print('--- substituted text ---')
print(NEW)

# cohort: the 7 reference-vs-definition tasks + E4B's solved controls
REFDEF = ['fastapi_14372', 'fastapi_14458', 'fastapi_14492', 'fastapi_9555',
          'rich_3067', 'rich_3480', 'rich_4077']
RUN = Path('C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE/Gemma/kaggle_pkg/out_e4b/results')
rows = [json.loads(l) for l in (RUN / 'task_results.all.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
controls = [r['instance_id'] for r in rows if r.get('resolved')]
cohort = dict(defect=REFDEF, controls=controls, overflow=[], timeout=[],
              all=REFDEF + controls)
out = RIG / 'm1_locate' / 'cohort_refdef.json'
out.write_text(json.dumps(cohort, indent=1), encoding='utf-8')
print()
print('cohort: %d refdef + %d controls = %d -> %s'
      % (len(REFDEF), len(controls), len(cohort['all']), out))
print('controls:', controls)
