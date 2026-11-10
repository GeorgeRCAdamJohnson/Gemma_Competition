# Runs ON the Colab VM: did python3.12-venv land? Can a task-style venv be created now?
import subprocess

for cmd in ("tail -3 /tmp/apt_venv.log; pgrep -fa 'apt-get|dpkg' | cut -c1-100",
            "/content/venv/bin/python -c 'import ensurepip; print(\"ensurepip\", ensurepip.version())'",
            "rm -rf /tmp/_vt && timeout 120 /content/venv/bin/python -c \"import venv; venv.create('/tmp/_vt', system_site_packages=True, with_pip=True, symlinks=True, clear=True); print('venv+pip OK')\" 2>&1 | tail -2",
            "/tmp/_vt/bin/python -c 'import pytest, pydantic, starlette; print(\"task venv sees\", pytest.__version__, pydantic.VERSION, starlette.__version__)' 2>&1 | tail -1"):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print((r.stdout + r.stderr).strip()[:500])
