#!/bin/bash
~/vllmenv/bin/python - <<'PYEOF'
import os, subprocess, errno
bad = 0
for d in os.environ["PATH"].split(os.pathsep):
    if not d:
        continue
    env = dict(os.environ, PATH=d)
    try:
        r = subprocess.run(["nvcc", "--version"], env=env, capture_output=True)
        print("RAN", repr(d), "rc=", r.returncode)
        bad += 1
    except OSError as e:
        if e.errno != errno.ENOENT:
            print("SUSPECT", repr(d), errno.errorcode.get(e.errno), e.strerror)
            bad += 1
print("BISECT_DONE bad=", bad)
PYEOF