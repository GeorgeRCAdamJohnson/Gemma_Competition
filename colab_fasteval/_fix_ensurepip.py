# Runs ON the Colab VM: install ensurepip for the image's python3.12 (Kaggle's image has it; Colab's does not), then
# prove a task-style venv (system_site_packages + pip) can be created from the launcher interpreter.
import subprocess

for cmd in ("DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3.12-venv >/tmp/apt_venv.log 2>&1; echo apt rc=$?; tail -2 /tmp/apt_venv.log",
            "/content/venv/bin/python -c 'import ensurepip; print(\"ensurepip\", ensurepip.version())'",
            "rm -rf /tmp/_vt && /content/venv/bin/python -c \"import venv; venv.create('/tmp/_vt', system_site_packages=True, with_pip=True, symlinks=True, clear=True); print('venv+pip OK')\" 2>&1 | tail -2",
            "/tmp/_vt/bin/python -c 'import pytest, pydantic, starlette; print(\"task venv sees\", pytest.__version__, pydantic.VERSION, starlette.__version__)' 2>&1 | tail -1"):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print((r.stdout + r.stderr).strip()[:500])
