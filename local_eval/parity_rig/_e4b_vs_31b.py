"""Explain an E4B-vs-31B pool delta on the axes that can actually move the board.

Usage: python _e4b_vs_31b.py <runA_dir> <runB_dir>    (each contains results/)
Reports, per run: solved, and the mechanisms that could explain a shortfall:
  - cap binding      (tool_calls >= cap, duration >= time cap)
  - patch production (zero-patch, zero-edit)
  - localization     (wrong file, far hunk)
  - pace             (first edit, total duration, calls)
  - set overlap      (what B solves that A does not)
"""
import json
import re
import statistics
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
ANSI = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
NEWF = re.compile(r'^\+\+\+ b/([^\t\n]+)', re.M)
DIFF = re.compile(r'^diff --git a/(.+?) b/', re.M)
HUNK = re.compile(r'^@@ -(\d+)(?:,(\d+))?', re.M)

tasks = {json.loads(l)['instance_id']: json.loads(l)
         for l in (BASE / 'comp_files' / 'tasks.jsonl').read_text(encoding='utf-8').splitlines()}


def load_rows(run: Path):
    for name in ('task_results.all.jsonl', 'task_results.jsonl'):
        p = run / 'results' / name
        if p.exists() and p.stat().st_size > 2:
            rows = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
            if len(rows) >= 100 or not (run / 'recovered_full129.json').exists():
                return rows
    rec = run / 'recovered_full129.json'
    if rec.exists():
        d = json.loads(rec.read_text(encoding='utf-8'))
        solved = set(d['solved'])
        tm = {}
        tp = run / 'trace_metrics.json'
        if tp.exists():
            tm = {r['tid']: r for r in json.loads(tp.read_text(encoding='utf-8'))}
        out = []
        for r in d['rows']:
            tid = r['instance_id']
            t = tm.get(tid, {})
            out.append(dict(instance_id=tid, repo=r.get('repo'), resolved=tid in solved,
                            tool_calls=t.get('ncalls'), duration_seconds=t.get('last_t'),
                            agent_patch_size=None))
        return out
    return []


def files_of(text: str):
    return set(DIFF.findall(text or '')) | {f.strip() for f in NEWF.findall(text or '')
                                             if f.strip() != '/dev/null'}


def profile(run: Path, label: str, cap_calls: int = 40, cap_secs: float = 360):
    rows = load_rows(run)
    logs = run / 'results' / 'logs'
    patches = run / 'results' / 'patches'
    if not rows:
        print('%s: NO RESULTS' % label)
        return None
    solved = {r['instance_id'] for r in rows if r.get('resolved')}
    n = len(rows)
    calls = [r.get('tool_calls') or 0 for r in rows]
    durs = [r.get('duration_seconds') or 0 for r in rows]

    zero_patch = sum(1 for r in rows if r.get('agent_patch_size') is not None
                     and not (r.get('agent_patch_size') or 0)) if any(
        r.get('agent_patch_size') is not None for r in rows) else sum(
        1 for r in rows if not (patches / (r['instance_id'] + '.patch')).exists())
    noedit = 0
    first_edit = []
    wrong_file = 0
    for r in rows:
        tid = r['instance_id']
        txt = ANSI.sub('', (logs / (tid + '.log')).read_text(encoding='utf-8', errors='replace')) \
            if (logs / (tid + '.log')).exists() else ''
        if 'edit_file' not in txt:
            noedit += 1
        m = re.findall(r'\[\s*([0-9.]+)s\][^\n]*edit_file', txt)
        if m:
            first_edit.append(min(float(x) for x in m))
        gold = files_of(tasks.get(tid, {}).get('patch', ''))
        mine = files_of((patches / (tid + '.patch')).read_text(encoding='utf-8', errors='replace')) \
            if (patches / (tid + '.patch')).exists() else set()
        if mine and gold and not (mine & gold):
            wrong_file += 1

    def med(xs):
        return round(statistics.median(xs), 1) if xs else None

    out = dict(label=label, n=n, solved=len(solved), solved_set=solved,
               call_med=med(calls), dur_med=med(durs),
               hit_calls=sum(1 for c in calls if c >= cap_calls),
               hit_time=sum(1 for d in durs if d >= cap_secs),
               zero_patch=zero_patch, noedit=noedit, wrong_file=wrong_file,
               first_edit=med(first_edit))
    print('\n=== %s ===' % label)
    print('  solved           %d/%d = %.3f' % (out['solved'], n, out['solved'] / n))
    print('  median calls     %s   (>=%d calls: %d, %.0f%%)'
          % (out['call_med'], cap_calls, out['hit_calls'], 100 * out['hit_calls'] / n))
    print('  median duration  %ss  (>=%ss: %d, %.0f%%)'
          % (out['dur_med'], cap_secs, out['hit_time'], 100 * out['hit_time'] / n))
    print('  zero-patch       %d (%.0f%%)' % (out['zero_patch'], 100 * out['zero_patch'] / n))
    print('  never edited     %d (%.0f%%)' % (out['noedit'], 100 * out['noedit'] / n))
    print('  wrong file       %d' % out['wrong_file'])
    print('  median first edit %ss' % out['first_edit'])
    return out


if __name__ == '__main__':
    A = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE / 'kaggle_pkg' / 'out_v7'
    B = Path(sys.argv[2]) if len(sys.argv) > 2 else BASE / 'kaggle_pkg' / 'out_e4b'
    a = profile(A, 'A: ' + A.name)
    b = profile(B, 'B: ' + B.name)
    if a and b:
        print('\n=== set differences ===')
        print('  only %s solves: %d -> %s' % (a['label'], len(a['solved_set'] - b['solved_set']),
                                              sorted(a['solved_set'] - b['solved_set'])[:12]))
        print('  only %s solves: %d -> %s' % (b['label'], len(b['solved_set'] - a['solved_set']),
                                              sorted(b['solved_set'] - a['solved_set'])[:12]))
        print('  both: %d' % len(a['solved_set'] & b['solved_set']))
        print('\n=== board projection ===')
        for x in (a, b):
            print('  %-12s pool %.3f -> expected 58-task board %.3f'
                  % (x['label'], x['solved'] / x['n'], x['solved'] / x['n']))
