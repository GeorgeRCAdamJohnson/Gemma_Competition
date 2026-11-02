"""If E4B's patch equals gold and the task still fails, the loss is in verification.

Compare full patches byte-for-byte and read the pytest output for the mismatches.
"""
import difflib
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
E4B = BASE / 'kaggle_pkg' / 'out_e4b' / 'results'
TASKS = {json.loads(l)['instance_id']: json.loads(l)
         for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()}

SUSPECTS = ['fastapi_14463', 'fastapi_14786', 'fastapi_14301', 'fastapi_11194',
            'fastapi_14077', 'rich_3006', 'rich_3454', 'rich_3718', 'rich_3905']


def norm(t):
    return [l.rstrip() for l in (t or '').splitlines() if l.strip()]


for tid in SUSPECTS:
    gold = TASKS.get(tid, {}).get('patch', '')
    pp = E4B / 'patches' / (tid + '.patch')
    mine = pp.read_text(encoding='utf-8', errors='replace') if pp.exists() else ''
    g, m = norm(gold), norm(mine)
    same = g == m
    sm = difflib.SequenceMatcher(None, g, m)
    ratio = sm.ratio()
    print('=' * 78)
    print('%s  gold_lines=%d  e4b_lines=%d  IDENTICAL=%s  similarity=%.3f'
          % (tid, len(g), len(m), same, ratio))
    if not same:
        diff = [l for l in difflib.unified_diff(g, m, 'gold', 'e4b', n=0, lineterm='')][:14]
        for l in diff:
            print('    ', l[:150])
    # what did verification say?
    t = E4B / 'test_outputs' / (tid + '.log')
    if t.exists():
        txt = t.read_text(encoding='utf-8', errors='replace')
        tail = [l for l in txt.splitlines() if l.strip()][-6:]
        print('   VERIFY tail:')
        for l in tail:
            print('       ', l[:150])
    else:
        print('   (no test output - never verified)')
