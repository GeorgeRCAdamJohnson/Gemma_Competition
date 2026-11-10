# Runs ON the GPU VM (Drive mounted, /content/ab_inputs.tar uploaded). Background job: unpack inputs, restore the
# Kaggle-matched env, stage the model + the A/B tasks' snapshots, install python3.12-venv. Log /content/prep.log.
import subprocess
from pathlib import Path

SCRIPT = r'''
set -u
T0=$(date +%s)
D=/content/drive/MyDrive
C=$D/gemma-4-developer-agent-cache
mkdir -p /content/work && tar -xf /content/ab_inputs.tar -C /content/work && echo "inputs: $(ls /content/work | tr '\n' ' ')"
( cp $D/gemma_fasteval/colab_env/colab_env.tar /content/ && tar -xf /content/colab_env.tar -C / && rm -f /content/colab_env.tar \
  && echo "ENV restored $(( $(date +%s) - T0 ))s" ) &
( mkdir -p /content/model && cp -r $C/models/google/gemma-4/Other/gemma-4-e4b-it-qat-w4a16-ct/2/. /content/model/ \
  && echo "MODEL staged $(( $(date +%s) - T0 ))s" ) &
mkdir -p /content/snaps
for t in $(python3 -c "import json; print(' '.join(json.load(open('/content/work/ab_tasks.json'))))"); do
  cp $C/competitions/gemma-4-developer-agent/snapshots/$t.tgz /content/snaps/
done
echo "SNAPS $(ls /content/snaps | wc -l) $(( $(date +%s) - T0 ))s"
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3.12-venv >/tmp/apt_venv.log 2>&1 && echo "python3.12-venv OK"
wait
for pth in /content/venv/lib/python*/site-packages/*cutlass*.pth; do [ -e "$pth" ] && rm -f "$pth" && echo "removed $pth"; done
rm -rf /wheels /tmp/wheels /tmp/wheelhouse /content/work/wheels /content/work/data 2>/dev/null
/content/venv/bin/python - <<'EOF'
import hashlib, json, pathlib
for a in sorted(pathlib.Path("/content/work/arms").iterdir()):
    fs = {p.relative_to(a).as_posix(): p.read_bytes() for p in a.rglob("*") if p.is_file()}
    print("arm", a.name, hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12])
print("tasks.jsonl", hashlib.sha1(pathlib.Path("/content/work/tasks.jsonl").read_bytes()).hexdigest()[:12])
import swegemma, vllm, pydantic, starlette, pytest
print("IMPORTS", vllm.__version__, pydantic.VERSION, starlette.__version__, pytest.__version__)
EOF
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
echo "PREP DONE $(( $(date +%s) - T0 ))s"
echo 0 > /content/prep.done
'''
Path("/content/prep.sh").write_text(SCRIPT)
Path("/content/prep.done").unlink(missing_ok=True)
subprocess.Popen("nohup bash /content/prep.sh > /content/prep.log 2>&1 &", shell=True)
print("started prep job")
