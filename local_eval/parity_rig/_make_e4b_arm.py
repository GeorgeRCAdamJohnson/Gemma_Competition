"""Build the E4B locate arm and its cohort.

Arm: agent_ctrl_e4b + ONE numeral (3-4 -> 10-12) on prompt line 26.
Cohort: the gate's design -- E4B baseline tasks that edited the wrong file AND never
referenced a gold file (defect), plus E4B's solved set (controls).
"""
import json
import re
import shutil
from pathlib import Path

RIG = Path(__file__).resolve().parent
BASE = RIG.parents[1]
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
NEWF = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)
DIFF = re.compile(r'^diff --git a/(.+?) b/', re.M)

# ---------- 1. arm ----------
src = RIG / 'agent_ctrl_e4b'
dst = RIG / 'agent_ctrl_e4b_locate'
if dst.exists():
    shutil.rmtree(dst)
shutil.copytree(src, dst)
p = dst / 'prompts' / 'system.md'
text = p.read_text(encoding='utf-8')
before = text
text = text.replace('AT MOST 3-4 tool calls locating', 'AT MOST 10-12 tool calls locating')
assert text != before, 'numeral not found'
p.write_text(text, encoding='utf-8', newline='')
import hashlib
print('arm prompt sha1:', hashlib.sha1(p.read_bytes()).hexdigest()[:12], '(baseline b08b32a2438d)')
print('numeral occurrences of "10-12":', text.count('10-12 tool calls'))

# ---------- 2. cohort from the E4B Kaggle baseline ----------
RUN = BASE / 'kaggle_pkg' / 'out_e4b' / 'results'
TASKS = {json.loads(l)['instance_id']: json.loads(l)
         for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()}


def gold(t):
    txt = t.get('patch', '') or ''
    return {m.group(1).strip() for m in NEWF.finditer(txt)} | set(DIFF.findall(txt))


rows = [json.loads(l) for l in (RUN / 'task_results.all.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
logs, patches = RUN / 'logs', RUN / 'patches'
solved, defect = [], []
for r in rows:
    tid = r['instance_id']
    if r.get('resolved'):
        solved.append(tid)
        continue
    lg = logs / (tid + '.log')
    txt = ANSI.sub('', lg.read_text(encoding='utf-8', errors='replace')) if lg.exists() else ''
    g = gold(TASKS.get(tid, {}))
    if not g:
        continue
    pp = patches / (tid + '.patch')
    mine = {m.group(1).strip() for m in NEWF.finditer(pp.read_text(encoding='utf-8', errors='replace'))} \
        if pp.exists() else set()
    if mine and not (mine & g) and not any(f in txt for f in g):
        defect.append(tid)

print('\nE4B baseline: solved %d | defect (wrong file AND never read gold) %d' % (len(solved), len(defect)))
out = RIG / 'm1_locate' / 'cohort_e4b.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(dict(defect=defect, controls=solved, all=defect + solved), indent=1),
               encoding='utf-8')
print('TOTAL E4B COHORT: %d  -> %s' % (len(defect) + len(solved), out))
