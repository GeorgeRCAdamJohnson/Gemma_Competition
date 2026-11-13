# Runs ON the VM: finish a prep whose shell was killed after its copies completed. Verifies the env restore, then runs
# prep's tail (cutlass .pth removal, arm hashes, imports, GPU) and writes prep.done ONLY if everything checks out.
import subprocess
from pathlib import Path

TAIL = r'''
set -e
test -x /content/venv/bin/python
for pth in /content/venv/lib/python*/site-packages/*cutlass*.pth; do [ -e "$pth" ] && rm -f "$pth" && echo "removed $pth"; done
/content/venv/bin/python - <<'EOF'
import hashlib, json, pathlib
for a in sorted(pathlib.Path("/content/work/arms6").iterdir()):
    fs = {p.relative_to(a).as_posix(): p.read_bytes() for p in a.rglob("*") if p.is_file()}
    print("arm", a.name, hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12])
import swegemma, vllm, pydantic, starlette, pytest
print("IMPORTS", vllm.__version__, pydantic.VERSION, starlette.__version__, pytest.__version__)
EOF
ls /content/model | head -3; du -sb /content/model | cut -f1
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo "PREP DONE (finished by _prep_finish)"
echo 0 > /content/prep.done
'''
r = subprocess.run(["bash", "-c", TAIL], capture_output=True, text=True, timeout=600)
out = r.stdout + r.stderr
print(out[-3000:], "rc", r.returncode)
with open("/content/prep.log", "a") as f:
    f.write(out)
