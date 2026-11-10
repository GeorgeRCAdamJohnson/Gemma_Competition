# Runs ON the GPU VM (Drive mounted). Background job: restore the Kaggle-matched env, stage model + the smoke
# tasks' snapshots locally, lay out /content/work like Kaggle's /kaggle/working. Log /content/prep.log.
import subprocess
from pathlib import Path

TASKS = ["fastapi_14786", "fastapi_14301", "rich_3905", "rich_3006", "rich_3067", "fastapi_9555"]
SCRIPT = r'''
set -u
T0=$(date +%s)
D=/content/drive/MyDrive
C=$D/gemma-4-developer-agent-cache
# 1) env + model in parallel (both large, both from Drive)
( cp $D/gemma_fasteval/colab_env/colab_env.tar /content/ && tar -xf /content/colab_env.tar -C / && rm -f /content/colab_env.tar \
  && echo "ENV restored $(( $(date +%s) - T0 ))s" ) &
( mkdir -p /content/model && cp -r $C/models/google/gemma-4/Other/gemma-4-e4b-it-qat-w4a16-ct/2/. /content/model/ \
  && echo "MODEL staged $(( $(date +%s) - T0 ))s" ) &
# 2) only the smoke tasks' snapshots (Kaggle's snapshots dir holds just .tgz files)
mkdir -p /content/snaps
for t in __TASKS__; do cp $C/competitions/gemma-4-developer-agent/snapshots/$t.tgz /content/snaps/; done
echo "SNAPS $(ls /content/snaps | wc -l) $(( $(date +%s) - T0 ))s"
wait
# 3) Kaggle-like working dir: tasks.jsonl + agent; NO graphs/embeddings/wheels/secret anywhere near it
mkdir -p /content/work && cd /content/work
rm -rf /wheels /tmp/wheels /tmp/wheelhouse /content/work/wheels /content/work/data 2>/dev/null
ls -l /content/model | awk '{print $5, $9}'
/content/venv/bin/python -c "import swegemma, adk_submission, vllm, pydantic, starlette, pytest; print('IMPORTS', swegemma.__version__ if hasattr(swegemma,'__version__') else '?', vllm.__version__, pydantic.VERSION, starlette.__version__, pytest.__version__)"
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader
echo "PREP DONE $(( $(date +%s) - T0 ))s"
echo 0 > /content/prep.done
'''.replace("__TASKS__", " ".join(TASKS))
Path("/content/prep.sh").write_text(SCRIPT)
Path("/content/prep.done").unlink(missing_ok=True)
subprocess.Popen("nohup bash /content/prep.sh > /content/prep.log 2>&1 &", shell=True)
print("started prep job")
