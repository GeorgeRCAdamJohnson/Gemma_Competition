"""Why did 17 tasks produce no patch at all? Read the tail of each agent log."""
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
RUN = BASE / 'kaggle_pkg' / 'out_v7'
LOGS = RUN / 'results' / 'logs'
PATCHES = RUN / 'results' / 'patches'

tasks = [json.loads(l) for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()]
missing = [t['instance_id'] for t in tasks if not (PATCHES / (t['instance_id'] + '.patch')).exists()]

END_RX = re.compile(r'^\s*\[\s*([\d.]+)s\]\s+(.*)$', re.M)

for tid in missing:
    p = LOGS / (tid + '.log')
    txt = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
    lines = [l.rstrip() for l in txt.splitlines() if l.strip()]
    stamps = END_RX.findall(txt)
    dur = max((float(s) for s, _ in stamps), default=0.0)
    tools = len(re.findall(r'^\s*\[\s*[\d.]+s\]\s+[^\s].*\b(?:edit_file|read_file|search|grep|shell|list_dir|submit_patch)\b', txt, re.M))
    has_submit = 'submit_patch' in txt
    print('=' * 90)
    print('%-22s dur=%6.0fs  chars=%6d  toolish=%3d  submit=%s' % (tid, dur, len(txt), tools, has_submit))
    for l in lines[-6:]:
        print('    ', l[:150])
