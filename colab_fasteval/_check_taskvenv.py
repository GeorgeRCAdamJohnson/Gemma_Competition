# Runs ON the Colab VM: build a task venv EXACTLY like SubprocessManager.start() (venv + _host_env.pth from the
# launcher's sys.path) and confirm the task interpreter sees Kaggle's test-package versions.
import subprocess

code = r'''
import sys, venv
from pathlib import Path
d = Path("/tmp/_vt2")
venv.create(d, system_site_packages=True, with_pip=True, symlinks=True, clear=True)
sp = [p for p in sys.path if "site-packages" in p and Path(p).is_dir()]
for s in d.glob("lib/python*/site-packages"):
    (s / "_host_env.pth").write_text("\n".join(sp) + "\n")
print("host site-packages:", sp)
'''
print(subprocess.run(["/content/venv/bin/python", "-c", code], capture_output=True, text=True).stdout.strip())
r = subprocess.run("/tmp/_vt2/bin/python3 -s -c 'import pytest, pydantic, starlette, fastapi, rich, httpx; "
                   "print(\"task venv sees\", pytest.__version__, pydantic.VERSION, starlette.__version__, "
                   "fastapi.__version__, httpx.__version__)'", shell=True, capture_output=True, text=True)
print((r.stdout + r.stderr).strip()[-400:])
