"""Is the no-patch bucket purchasable? A submit rule can only bank an existing diff."""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
RUN = BASE / 'kaggle_pkg' / 'out_v7'
LOGS = RUN / 'results' / 'logs'
PATCHES = RUN / 'results' / 'patches'

tasks = [json.loads(l) for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()]
solved = set(json.loads((RUN / 'recovered_full129.json').read_text(encoding='utf-8'))['solved'])

# an edit_file call that actually changed something
EDIT_OK = re.compile(r'edit_file', re.I)
SUBMIT = re.compile(r'submit_patch')

rows = []
for t in tasks:
    tid = t['instance_id']
    p = LOGS / (tid + '.log')
    txt = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
    rows.append(dict(
        tid=tid, solved=tid in solved,
        edits=len(EDIT_OK.findall(txt)),
        submits=len(SUBMIT.findall(txt)),
        patch=(PATCHES / (tid + '.patch')).exists(),
        patch_bytes=(PATCHES / (tid + '.patch')).stat().st_size if (PATCHES / (tid + '.patch')).exists() else 0,
    ))

nopatch = [r for r in rows if not r['patch']]
print('no-patch tasks: %d' % len(nopatch))
print()
print('%-22s %6s %8s %7s' % ('task', 'edits', 'submits', 'solved'))
for r in nopatch:
    print('%-22s %6d %8d %7s' % (r['tid'], r['edits'], r['submits'], r['solved']))

# THE question: how many tasks made edits but never submitted a patch?
purchasable = [r for r in rows if r['edits'] > 0 and not r['patch']]
print()
print('=== PURCHASABLE (edited but produced no patch): %d ===' % len(purchasable))
for r in purchasable:
    print('   %-22s edits=%d submits=%d' % (r['tid'], r['edits'], r['submits']))

# Inverse risk: tasks that submitted a patch but were still unsolved (content failures)
content_fail = [r for r in rows if r['patch'] and not r['solved']]
print()
print('content-level failures (patch submitted, tests failed): %d' % len(content_fail))
print('median patch bytes: %d' % (sorted(r['patch_bytes'] for r in content_fail)[len(content_fail) // 2] if content_fail else 0))
print('empty-ish patches (<50B) among them: %d' % sum(1 for r in content_fail if r['patch_bytes'] < 50))
