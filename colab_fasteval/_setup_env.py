# Runs ON the Colab VM. Starts a background job that builds a py3.12 env with the competition wheelhouse.
# Log: /content/setup_env.log ; done marker: /content/setup_env.done (contains rc).
import subprocess
from pathlib import Path

SCRIPT = r'''
set -u
WH=/content/drive/MyDrive/gemma_fasteval/wheelhouse
export PATH=$HOME/.local/bin:$PATH
T0=$(date +%s)
command -v uv >/dev/null || (curl -LsSf https://astral.sh/uv/install.sh | sh) >/dev/null 2>&1
export PATH=$HOME/.local/bin:$PATH
echo "uv $(uv --version)"
mkdir -p /content/wh && cp -n $WH/*.whl /content/wh/ && echo "copied $(ls /content/wh/*.whl | wc -l) wheels from Drive"
rm -f /content/wh/*cutlass*.whl
uv venv -q -p 3.12 /content/venv && echo "venv: $(/content/venv/bin/python --version)"
PY=/content/venv/bin/python
# 1) the runtime stack the Kaggle image provides: vLLM (pins its torch) resolved from PyPI + local wheels
echo "== step 1: vllm + deps"
uv pip install -q --python $PY --find-links /content/wh /content/wh/vllm-*.whl 2>&1 | tail -15
RC=${PIPESTATUS[0]}
# 2) the wheelhouse exactly as Kaggle installs it: --no-deps, force-reinstall, competition versions win
echo "== step 2: wheelhouse --no-deps (rc1=$RC)"
uv pip install -q --python $PY --no-deps --reinstall /content/wh/*.whl 2>&1 | tail -15
RC2=${PIPESTATUS[0]}; [ $RC2 -ne 0 ] && RC=$RC2
# 3) deps of the harness packages not covered by vLLM (installed without upgrading anything already present)
echo "== step 3: missing harness deps"
$PY - <<'EOF' > /content/missing.txt
import importlib.metadata as md, re
have = {d.metadata["Name"].lower().replace("_", "-") for d in md.distributions()}
need = set()
for pkg in ("swegemma", "adk-submission", "adk-eval-core", "google-adk"):
    for r in (md.requires(pkg) or []):
        if "extra ==" in r:
            continue
        name = re.split(r"[ ;<>=!~\[(]", r, 1)[0].lower().replace("_", "-")
        if name not in have:
            need.add(r.split(";")[0].strip())
print("\n".join(sorted(need)))
EOF
echo "missing: $(tr '\n' ' ' < /content/missing.txt)"
[ -s /content/missing.txt ] && uv pip install -q --python $PY -r /content/missing.txt 2>&1 | tail -10
/content/venv/bin/python - <<'EOF'
import importlib
for m in ("swegemma", "adk_submission", "adk_eval_core", "vllm", "torch", "transformers"):
    try:
        mod = importlib.import_module(m)
        print("IMPORT OK", m, getattr(mod, "__version__", "?"))
    except Exception as e:
        print("IMPORT FAIL", m, type(e).__name__, str(e)[:200])
EOF
echo "elapsed $(( $(date +%s) - T0 ))s"
echo $RC > /content/setup_env.done
'''
Path("/content/setup_env.sh").write_text(SCRIPT)
Path("/content/setup_env.done").unlink(missing_ok=True)
subprocess.Popen("nohup bash /content/setup_env.sh > /content/setup_env.log 2>&1 &", shell=True)
print("started setup job")
