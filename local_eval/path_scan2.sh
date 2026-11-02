#!/bin/bash
echo "=== PATH seen by this shell ==="
echo "$PATH" | tr ":" "\n"
echo "=== python execvp test ==="
~/vllmenv/bin/python - <<'PYEOF'
import os, shutil, errno
print("which nvcc:", shutil.which("nvcc"))
for d in os.environ["PATH"].split(os.pathsep):
    p = os.path.join(d, "nvcc")
    if os.path.exists(p):
        st = os.stat(p)
        print("EXISTS", p, oct(st.st_mode))
try:
    os.execvp("nvcc", ["nvcc", "--version"])
except OSError as e:
    print("execvp errno:", e.errno, errno.errorcode.get(e.errno), e.strerror, "filename:", e.filename)
PYEOF
echo "=== g++/ninja ==="
command -v g++ || echo no-g++
command -v ninja || echo no-ninja
ls /usr/bin/g++* 2>/dev/null || true