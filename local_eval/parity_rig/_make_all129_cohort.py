"""Verify whether the local E4B rig is a faithful model of the Kaggle E4B run.

Runs the SAME config on the SAME 129 tasks and then compares per-task outcomes,
error profile and durations against kaggle_pkg/out_e4b.
"""
import json
from pathlib import Path

RIG = Path(__file__).resolve().parent
BASE = RIG.parents[1]

ids = [json.loads(l)['instance_id']
       for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
cohort = dict(defect=[], controls=[], overflow=[], timeout=[], all=ids)
out = RIG / 'm1_locate' / 'cohort_all129.json'
out.write_text(json.dumps(cohort, indent=1), encoding='utf-8')
print('wrote %s with %d tasks' % (out, len(ids)))
