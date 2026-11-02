"""Build the thinking-budget arm and the overflow cohort.

Arm: agent_ctrl_e4b with sampling.yaml thinking_budget 4096 -> 1024 (single variable).
Cohort: 6 context-overflow + 2 session-timeout tasks (the harness-side losses) plus the
10 tasks E4B already solved as regression controls.
"""
import json
import shutil
import hashlib
from pathlib import Path

RIG = Path(__file__).resolve().parent
BASE = RIG.parents[1]
RUN = BASE / 'kaggle_pkg' / 'out_e4b' / 'results'

# ---------- arm ----------
src, dst = RIG / 'agent_ctrl_e4b', RIG / 'agent_ctrl_e4b_t1024'
if dst.exists():
    shutil.rmtree(dst)
shutil.copytree(src, dst)
p = dst / 'configs' / 'sampling.yaml'
before = p.read_text(encoding='utf-8')
after = before.replace('thinking_budget: 4096', 'thinking_budget: 1024')
assert after != before, 'thinking_budget 4096 not found'
p.write_text(after, encoding='utf-8', newline='')

print('--- arm sampling.yaml ---')
print(after.strip())
prompt = dst / 'prompts' / 'system.md'
print('prompt sha1:', hashlib.sha1(prompt.read_bytes()).hexdigest()[:12], '(must stay b08b32a2438d)')

# ---------- cohort ----------
rows = [json.loads(l) for l in (RUN / 'task_results.all.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
overflow, timeout, solved = [], [], []
for r in rows:
    e = str(r.get('error') or '')
    if r.get('resolved'):
        solved.append(r['instance_id'])
    elif 'ContextWindow' in e:
        overflow.append(r['instance_id'])
    elif 'session timeout' in e:
        timeout.append(r['instance_id'])

cohort = dict(overflow=overflow, timeout=timeout, controls=solved,
              defect=overflow + timeout, all=overflow + timeout + solved)
out = RIG / 'm1_locate' / 'cohort_overflow.json'
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(cohort, indent=1), encoding='utf-8')
print('\noverflow (%d): %s' % (len(overflow), overflow))
print('timeout  (%d): %s' % (len(timeout), timeout))
print('controls (%d): %s' % (len(solved), solved))
print('TOTAL cohort: %d -> %s' % (len(cohort['all']), out))
