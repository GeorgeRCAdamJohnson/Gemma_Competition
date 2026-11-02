"""Replay fixed patches through verification, with NO model involved.

For each task: extract the base snapshot, apply the agent's patch, apply the official
test_patch, then run the test files that the test_patch touches.

Same script runs locally (docker rig) and on Kaggle, so any difference is ENVIRONMENT,
not model. Answers: are our local-only solves environmental artefacts?
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TASKS = Path(sys.argv[1])
SNAPS = Path(sys.argv[2])
PATCHDIR = Path(sys.argv[3])
IDS = sys.argv[4:]
OUT = Path(os.environ.get('REPLAY_OUT', '/out/replay_result.json'))

tasks = {json.loads(l)['instance_id']: json.loads(l)
         for l in TASKS.read_text(encoding='utf-8').splitlines() if l.strip()}

TESTFILE = re.compile(r'^\+\+\+ b/(.*?)$', re.M)


def sh(cmd, cwd):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=900)


results = []
for tid in IDS:
    rec = dict(task=tid)
    snap = SNAPS / f'{tid}.tgz'
    patch = PATCHDIR / f'{tid}.patch'
    t = tasks.get(tid, {})
    test_patch = t.get('test_patch') or ''
    if not snap.exists():
        rec['error'] = 'no snapshot'
        results.append(rec)
        continue
    work = Path(tempfile.mkdtemp(prefix=f'r_{tid}_'))
    try:
        p = sh(['tar', 'xzf', str(snap), '-C', str(work)], work)
        rec['extract_rc'] = p.returncode
        if p.returncode != 0:
            rec['error'] = 'extract failed: ' + (p.stderr or '')[-200:]
            results.append(rec)
            continue

        # agent patch
        if patch.exists():
            p = sh(['git', 'apply', '--whitespace=nowarn', str(patch.resolve())], work)
            rec['agent_patch_rc'] = p.returncode
            if p.returncode != 0:
                p = sh(['git', 'apply', '--3way', '--whitespace=nowarn', str(patch.resolve())], work)
                rec['agent_patch_3way_rc'] = p.returncode
            rec['agent_patch_tail'] = ((p.stderr or '') + (p.stdout or ''))[-300:]
        else:
            rec['agent_patch_rc'] = None

        # official test patch
        tp = work.parent / f'{tid}_test.patch'
        tp.write_text(test_patch if test_patch.endswith(chr(10)) else test_patch + chr(10), encoding='utf-8')
        p = sh(['git', 'apply', '--whitespace=nowarn', str(tp)], work)
        rec['test_patch_rc'] = p.returncode
        if p.returncode != 0:
            p = sh(['git', 'apply', '--3way', '--whitespace=nowarn', str(tp)], work)
            rec['test_patch_3way_rc'] = p.returncode
            rec['test_patch_tail'] = ((p.stderr or '') + (p.stdout or ''))[-300:]

        files = sorted({f.strip() for f in TESTFILE.findall(test_patch)})
        rec['test_files'] = files
        if not files:
            rec['error'] = 'no test files in test_patch'
            results.append(rec)
            continue

        p = sh([sys.executable, '-m', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider'] + files, work)
        tail = ((p.stdout or '') + (p.stderr or ''))
        rec['pytest_rc'] = p.returncode
        m = re.findall(r'(\d+)\s+(passed|failed|error|errors|skipped)', tail)
        rec['counts'] = {k: int(v) for v, k in m}
        rec['pytest_tail'] = tail[-400:]
        passed = rec['counts'].get('passed', 0)
        bad = sum(rec['counts'].get(k, 0) for k in ('failed', 'error', 'errors', 'skipped'))
        rec['resolved_here'] = bool(passed > 0 and bad == 0)
    except Exception as e:
        rec['error'] = f'{type(e).__name__}: {e}'
    finally:
        shutil.rmtree(work, ignore_errors=True)
    results.append(rec)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(results, indent=1), encoding='utf-8')
print('%-22s %-8s %-8s %-10s %s' % ('task', 'a_patch', 't_patch', 'passed_here', 'counts'))
for r in results:
    print('%-22s %-8s %-8s %-10s %s' % (r.get('task'), r.get('agent_patch_rc'), r.get('test_patch_rc'),
                                         r.get('resolved_here'), r.get('counts') or r.get('error', '')[:50]))
print('\nresolved in this environment: %d / %d' % (sum(1 for r in results if r.get('resolved_here')), len(results)))
print('wrote', OUT)

