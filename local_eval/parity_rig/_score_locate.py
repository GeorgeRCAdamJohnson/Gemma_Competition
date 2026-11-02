"""Score the locate-numeral arm against its pre-registered gates.

Compares the arm run against the baseline cohort it was drawn from:
  - defect tasks: did they now reference a gold file?   (baseline 0/N by construction)
  - mediator: run_command per task                      (baseline ~2.0)
  - controls: solved count (regressions)
  - solve rate overall (reported, not gated)
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
NEWF = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)
DIFF = re.compile(r'^diff --git a/(.+?) b/', re.M)
CALL = re.compile(r'^\s*\[\s*[\d.]+s\]\s+\S+\s+([a-z_]+)\b', re.M)

TASKS = {json.loads(l)['instance_id']: json.loads(l)
         for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()}


def gold(t):
    txt = t.get('patch', '') or ''
    return {m.group(1).strip() for m in NEWF.finditer(txt)} | set(DIFF.findall(txt))


def main(run_dir: Path, cohort_path: Path, label: str):
    cohort = json.loads(cohort_path.read_text(encoding='utf-8'))
    rows = [json.loads(l) for l in (run_dir / 'task_results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    got = {r['instance_id']: r for r in rows}
    logs = run_dir / 'logs'

    defect, controls = cohort['defect'], cohort['controls']
    print('=' * 74)
    print('%s  |  cohort: %d defect + %d controls' % (label, len(defect), len(controls)))
    print('rows returned: %d / %d' % (len(rows), len(cohort['all'])))

    read_gold, cmd_tot, nodes = [], Counter(), 0
    for tid in cohort['all']:
        lg = logs / (tid + '.log')
        txt = ANSI.sub('', lg.read_text(encoding='utf-8', errors='replace')) if lg.exists() else ''
        g = gold(TASKS.get(tid, {}))
        n = len(CALL.findall(txt))
        nodes += n
        c = len(re.findall(r'\brun_command\b', txt))
        cmd_tot[tid] = c
        if tid in defect:
            read_gold.append(any(f in txt for f in g))

    solved = {r['instance_id'] for r in rows if r.get('resolved')}
    d_solved = len(solved & set(defect))
    c_solved = len(solved & set(controls))
    nonread = sum(1 for x in read_gold if not x)

    print('\n--- PRIMARY: did the 31 defect tasks find the gold file? ---')
    print('  read gold file: %d / %d   (baseline 0/%d by construction)' % (sum(read_gold), len(defect), len(defect)))
    print('\n--- MEDIATOR: search rate ---')
    vals = [cmd_tot[t] for t in cohort['all']]
    print('  run_command per task: mean %.2f  median %d  (baseline ~2.0)' % (sum(vals) / len(vals), sorted(vals)[len(vals) // 2]))
    print('  tool calls per task : mean %.2f' % (nodes / len(cohort['all'])))
    print('\n--- SECONDARY: solves ---')
    print('  controls solved : %d / %d  (baseline %d/%d)' % (c_solved, len(controls), len(controls), len(controls)))
    print('  defect solved   : %d / %d  (baseline 0/%d)' % (d_solved, len(defect), len(defect)))
    print('  total solved    : %d / %d' % (len(solved), len(cohort['all'])))

    print('\n--- GATE VERDICT ---')
    rg = sum(read_gold)
    med_cmd = sum(vals) / len(vals)
    if rg >= 12 and med_cmd >= 5 and c_solved >= 13:
        print('  PASS: mechanism moved (>=12 read gold, run_command >=5, controls intact)')
    elif med_cmd < 3:
        print('  INERT: run_command %.2f < 3 -> the numeral did not change behaviour' % med_cmd)
    elif c_solved < 13:
        print('  HARMFUL: controls regressed to %d/%d' % (c_solved, len(controls)))
    else:
        print('  PARTIAL: read %d/%d, run_command %.2f, controls %d/%d' % (rg, len(defect), med_cmd, c_solved, len(controls)))


if __name__ == '__main__':
    R = Path(__file__).resolve().parent
    if len(sys.argv) >= 3:
        main(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3] if len(sys.argv) > 3 else 'arm')
    else:
        main(R / 'm1_locate' / 'agent_ctrl_12b_locate_r0', R / 'm1_locate' / 'cohort.json',
             '12B locate arm (3-4 -> 10-12)')
