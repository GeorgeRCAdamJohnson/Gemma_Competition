"""Inside the rig: is the workspace imported under the harness's pytest command?

Baseline run, then sabotage the workspace's rich, then re-run. If the verdict changes,
pytest is importing the workspace. If it does not, pytest is importing site-packages.
"""
import subprocess
import tarfile
from pathlib import Path

W = Path('/tmp/w')
W.mkdir(exist_ok=True)
with tarfile.open('/snaps/rich_3006.tgz') as tf:
    tf.extractall(W)

ENV = {'PYTHONSAFEPATH': '1', 'PYTHONNOUSERSITE': '1', 'PATH': '/usr/local/bin:/usr/bin:/bin'}
CMD = ['python', '-s', '-m', 'pytest', 'tests/test_console.py', '-q', '--no-header']


def run():
    p = subprocess.run(CMD, cwd=str(W), capture_output=True, text=True, env=ENV)
    tail = [l for l in (p.stdout + p.stderr).splitlines() if l.strip()][-2:]
    return p.returncode, ' | '.join(tail)[:170]


rc0, t0 = run()
print('BASELINE       rc=%s  %s' % (rc0, t0))

init = W / 'rich' / '__init__.py'
init.write_text(init.read_text() + '\nraise RuntimeError("WORKSPACE_RICH_IMPORTED")\n')
rc1, t1 = run()
print('AFTER SABOTAGE rc=%s  %s' % (rc1, t1))
print()
print('VERDICT:', 'workspace IS imported' if (rc0, t0) != (rc1, t1)
      else 'workspace NOT imported (site-packages used)')
