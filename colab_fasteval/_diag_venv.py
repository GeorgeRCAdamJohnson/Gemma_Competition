# Runs ON the GPU VM: why does venv.create(with_pip=True) from the launcher interpreter fail? (ensurepip)
import subprocess
from pathlib import Path

PY = "/content/venv/bin/python"
for cmd in (f"{PY} -c 'import ensurepip, sys; print(\"ensurepip ok\", sys.version)'",
            f"{PY} -m ensurepip --version",
            "ls /usr/lib/python3.12/ensurepip/_bundled/ 2>&1 | head",
            "dpkg -l | grep -E 'python3.12-venv|python3-venv' | awk '{print $2, $3}'",
            f"rm -rf /tmp/_vt && {PY} -m venv --system-site-packages /tmp/_vt 2>&1 | tail -3; echo rc=$?",
            "nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader"):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print("$", cmd[:90], "\n ", (r.stdout + r.stderr).strip()[:600])
log = Path("/content/smoke.log").read_text(errors="replace").splitlines()
print("== smoke.log head")
print("\n".join(log[:12]))
