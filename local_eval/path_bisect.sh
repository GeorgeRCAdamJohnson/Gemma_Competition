#!/bin/bash
~/vllmenv/bin/python - <<'PYEOF'
import os, subprocess
clean = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
for d in os.environ["PATH"].split(os.pathsep):
    if not d:
        continue
    env = dict(os.environ, PATH=d)
    r = subprocess.run(["nvcc", "--version"], env=env, capture_output=True)
    if r.returncode not in (127,):
        print("SUSPECT", repr(d), "rc=", r.returncode, (r.stderr[:120].decode(errors="replace") if r.stderr else b""))
print("BISECT_DONE")
PYEOF
echo "=== /Docker/host/bin ==="
ls -la /Docker/host/bin 2>&1 | head -8