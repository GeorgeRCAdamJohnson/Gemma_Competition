"""Faithful replay: mirrors swegemma's own verification rule.

swegemma derives the required test nodes from the test_patch
(`_extract_test_functions_from_patch`) and runs only those, failing on
failed/error/skipped. This script does exactly the same, with no model involved,
so the same patches can be replayed in any environment.
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


def extract_tests(test_patch: str):
    """Byte-identical logic to swegemma.harness.verification._extract_test_functions_from_patch."""
    if not test_patch:
        return []
    added = re.findall(r'^\+\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)\s*\(', test_patch, re.MULTILINE)
    if added:
        return list(dict.fromkeys(added))
    removed = set(re.findall(r'^-\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)\s*\(', test_patch, re.MULTILINE))
    hunk_headers = re.findall(r'^@@[^@]+@@\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)\b', test_patch, re.MULTILINE)
    context_defs = re.findall(r'^ \s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)\s*\(', test_patch, re.MULTILINE)
    context_set = set(context_defs)
    combined = list(dict.fromkeys(hunk_headers + context_defs))
    return [fn for fn in combined if fn not in removed and not (
        fn not in context_set and (any(r.startswith(fn) for r in removed)
                                   or any(c != fn and c.startswith(fn) for c in context_set)))]


def sh(cmd, cwd):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          encoding='utf-8', errors='replace', timeout=1800)


results = []
for tid in IDS:
    rec = dict(task=tid)
    snap, patch = SNAPS / f'{tid}.tgz', PATCHDIR / f'{tid}.patch'
    t = tasks.get(tid, {})
    tp_text = t.get('test_patch') or ''
    if not snap.exists():
        rec['error'] = 'no snapshot'
        results.append(rec)
        continue
    work = Path(tempfile.mkdtemp(prefix=f'r_{tid}_'))
    try:
        if sh(['tar', 'xzf', str(snap), '-C', str(work)], work).returncode != 0:
            rec['error'] = 'extract failed'
            results.append(rec)
            continue
        if patch.exists():
            p = sh(['git', 'apply', '--whitespace=nowarn', str(patch.resolve())], work)
            rec['agent_patch_rc'] = p.returncode
            if p.returncode != 0:
                p = sh(['git', 'apply', '--3way', '--whitespace=nowarn', str(patch.resolve())], work)
                rec['agent_patch_3way_rc'] = p.returncode
            rec['agent_patch_tail'] = ((p.stderr or '') + (p.stdout or ''))[-200:]
        tp = work.parent / f'{tid}_test.patch'
        tp.write_bytes((tp_text if tp_text.endswith('\n') else tp_text + '\n')
                       .replace('\r\n', '\n').encode('utf-8'))
        p = sh(['git', 'apply', '--whitespace=nowarn', str(tp)], work)
        rec['test_patch_rc'] = p.returncode
        if p.returncode != 0:
            p = sh(['git', 'apply', '--3way', '--whitespace=nowarn', str(tp)], work)
            rec['test_patch_3way_rc'] = p.returncode
            rec['test_patch_tail'] = ((p.stderr or '') + (p.stdout or ''))[-200:]

        files = sorted({f.strip() for f in TESTFILE.findall(tp_text)})
        fns = extract_tests(tp_text)
        rec['test_files'] = files
        rec['test_fns'] = fns
        if os.environ.get('REPLAY_MODE') == 'files':
            # Match swegemma: run the WHOLE test files, not extracted nodes.
            nodes = files
        else:
            nodes = [f'{f}::{fn}' for f in files for fn in fns] or files
        if not nodes:
            rec['error'] = 'no nodes'
            results.append(rec)
            continue
        p = sh([sys.executable, '-m', 'pytest', '-q', '--no-header', '-p', 'no:cacheprovider'] + nodes, work)
        tail = (p.stdout or '') + (p.stderr or '')
        m = re.findall(r'(\d+)\s+(passed|failed|error|errors|skipped)', tail)
        rec['counts'] = {k: int(v) for v, k in m}
        rec['nodes'] = nodes
        rec['pytest_tail'] = tail[-300:]
        passed = rec['counts'].get('passed', 0)
        bad = sum(rec['counts'].get(k, 0) for k in ('failed', 'error', 'errors'))
        if os.environ.get('REPLAY_TOLERATE_SKIPS') != '1':
            bad += rec['counts'].get('skipped', 0)
        rec['resolved_here'] = bool(passed > 0 and bad == 0)
    except Exception as e:
        rec['error'] = f'{type(e).__name__}: {e}'
    finally:
        shutil.rmtree(work, ignore_errors=True)
    results.append(rec)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(results, indent=1), encoding='utf-8')
print('%-22s %-7s %-7s %-9s %s' % ('task', 'a_rc', 't_rc', 'resolved', 'counts / err'))
for r in results:
    print('%-22s %-7s %-7s %-9s %s' % (r.get('task'), r.get('agent_patch_rc'), r.get('test_patch_rc'),
                                       r.get('resolved_here'), r.get('counts') or (r.get('error') or '')[:45]))
ok = sum(1 for r in results if r.get('resolved_here'))
print('\nresolved here: %d / %d' % (ok, len(results)))
print('wrote', OUT)
