# Runs ON the Colab VM after _setup_env.py finished. Overlays Kaggle's exact task-environment pins
# (/content/kaggle_pins.txt, from the CPU env-freeze kernel) onto /content/venv with --no-deps, so the
# swegemma subprocess sandbox (which runs task code + pytest over the launching interpreter's site-packages)
# sees the same package versions as on Kaggle. Background job; log /content/overlay.log, done /content/overlay.done.
import subprocess
from pathlib import Path

SCRIPT = r'''
set -u
export PATH=$HOME/.local/bin:$PATH
PY=/content/venv/bin/python
$PY - <<'EOF'
import importlib.metadata as md, re
from pathlib import Path
SKIP = re.compile(r"^(tensorflow|tf-|tensorboard|keras|jax|jaxlib|flax|optax|orbax|torch|torchvision|torchaudio|"
                  r"nvidia-|triton|vllm|flashinfer|xformers|cupy|cuda|cudf|cuml|rapids|dask-cuda|pycuda|tensorrt|"
                  r"onnxruntime|jupyter|notebook|ipython|ipykernel|ipywidgets|nbconvert|nbformat|google-colab|"
                  r"kaggle|bigframes|opencv|pyarrow|transformers|tokenizers|safetensors|huggingface-hub|"
                  r"accelerate|bitsandbytes|deepspeed|peft|sentencepiece|xgboost|lightgbm|catboost)", re.I)
have = {}
for d in md.distributions():
    have[d.metadata["Name"].lower().replace("_", "-")] = d.version
want, skipped, same = [], 0, 0
for l in Path("/content/kaggle_pins.txt").read_text().splitlines():
    n, v = l.split("==", 1)
    if SKIP.match(n):
        skipped += 1
        continue
    if have.get(n) == v:
        same += 1
        continue
    want.append(l)
Path("/content/overlay_req.txt").write_text("\n".join(want) + "\n")
print(f"pins: same {same} | to install {len(want)} | skipped {skipped}")
EOF
# bulk install; when uv rejects a pin (not on PyPI, system package, bad sdist), drop THAT pin and retry.
: > /content/overlay_dropped.txt
for attempt in $(seq 1 60); do
  if uv pip install -q --python $PY --no-deps --no-build -r /content/overlay_req.txt > /content/overlay_bulk.log 2>&1; then
    echo "bulk OK on attempt $attempt"
    break
  fi
  BAD=$($PY - <<'EOF'
import re
from pathlib import Path
norm = lambda s: re.sub(r"[-_.]+", "-", s).lower()  # PEP 503: lazr.restfulclient == lazr-restfulclient
t = Path("/content/overlay_bulk.log").read_text(errors="replace")
rf = Path("/content/overlay_req.txt")
lines = [l for l in rf.read_text().splitlines() if l]
req = {norm(l.split("==")[0]) for l in lines}
# uv's fixed phrasings: "Because X==v has no usable wheels", "Because X==v has a non-PEP 625...",
# "Because there is no version of X==v", "X==v ... was not found in the package registry"
pats = [r"Because (?:there is no version of |only )?([A-Za-z0-9][A-Za-z0-9._-]*)==",
        r"([A-Za-z0-9][A-Za-z0-9._-]*)==\S+ (?:was not found|has no usable wheels|has a non-PEP)",
        r"Failed to (?:download|build|fetch) `([A-Za-z0-9][A-Za-z0-9._-]*)[=`]"]
for p in pats:
    for m in re.finditer(p, t):
        n = norm(m.group(1))
        if n in req:
            keep = [l for l in lines if norm(l.split("==")[0]) != n]
            with open("/content/overlay_dropped.txt", "a") as f:
                f.write("\n".join(l for l in lines if norm(l.split("==")[0]) == n) + "\n")
            rf.write_text("\n".join(keep) + "\n")
            print(n); raise SystemExit
EOF
)
  if [ -z "$BAD" ]; then echo "cannot parse failure:"; tail -5 /content/overlay_bulk.log; break; fi
done
echo "dropped pins ($(wc -l < /content/overlay_dropped.txt)): $(tr '\n' ' ' < /content/overlay_dropped.txt)"
$PY - <<'EOF'
import importlib.metadata as md
from pathlib import Path
pins = dict(l.split("==", 1) for l in Path("/content/kaggle_pins.txt").read_text().splitlines())
KEY = ["pytest", "anyio", "pydantic", "pydantic-core", "starlette", "fastapi", "httpx", "httpcore", "sqlalchemy",
       "orjson", "ujson", "email-validator", "python-multipart", "jinja2", "pyyaml", "typer", "flask", "rich",
       "pygments", "markdown-it-py", "attrs", "requests", "urllib3", "idna", "charset-normalizer", "pysocks",
       "werkzeug", "typing-extensions", "coverage", "pyjwt", "aiosqlite", "peewee", "torch", "numpy", "certifi"]
bad = []
for k in KEY:
    try:
        got = md.version(k)
    except md.PackageNotFoundError:
        got = None
    if pins.get(k) and got != pins[k]:
        bad.append((k, pins[k], got))
print(f"KEY task packages: {len(KEY) - len(bad)}/{len(KEY)} match Kaggle")
for b in bad:
    print("  MISMATCH", b)
EOF
for m in swegemma adk_submission vllm; do $PY -c "import $m; print('still imports', '$m')" 2>&1 | tail -1; done
echo 0 > /content/overlay.done
'''
Path("/content/overlay.sh").write_text(SCRIPT)
Path("/content/overlay.done").unlink(missing_ok=True)
subprocess.Popen("nohup bash /content/overlay.sh > /content/overlay.log 2>&1 &", shell=True)
print("started overlay job")
