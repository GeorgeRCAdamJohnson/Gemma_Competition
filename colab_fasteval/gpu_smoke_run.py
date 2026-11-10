"""E4B Colab smoke run. Executed ON the GPU VM with /content/venv/bin/python (the Kaggle-matched env).

Replicates comfyops/e4b-pack1-val cells 3-4 for ONE server: same VllmConfig, same swegemma eval command, caps
from the agent's eval_config.yaml, --sandbox subprocess, cwd = a clean Kaggle-like working dir.
Inputs: /content/model (E4B /2), /content/snaps (smoke .tgz), /content/work/tasks.jsonl, /content/work/agent_pack1.
Outputs: /content/work/results/{task_results.jsonl, logs/...}, /content/work/smoke_summary.json.
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import torch
import yaml
from adk_submission import VllmConfig, VllmServer, discover_adapters

try:
    from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
except Exception:
    ALLOWED_ADAPTER_EXTENSIONS = frozenset({'.safetensors', '.bin', '.pt', '.pth', '.gguf', '.ggml'})

TASK_IDS = ["fastapi_14786", "fastapi_14301", "rich_3905", "rich_3006", "rich_3067", "fastapi_9555"]
WORK = Path("/content/work")
AGENT = WORK / "agent_pack1"
TASKS = WORK / "tasks.jsonl"
SNAPS = Path("/content/snaps")
OUT = WORK / "results"
TARGET_MODEL_NAME = "gemma-4-e4b-it-qat-w4a16-ct"
MODEL_PATH = Path("/content/model")
T0 = time.time()


def log(*a):
    print(f"[{time.time() - T0:7.1f}s]", *a, flush=True)


log("python", sys.version.split()[0], "| torch", torch.__version__, "| cuda", torch.cuda.is_available(),
    torch.cuda.get_device_name(0) if torch.cuda.is_available() else "-")
assert MODEL_PATH.exists() and (MODEL_PATH / "config.json").exists()
assert len(list(SNAPS.glob("*.tgz"))) == len(TASK_IDS), list(SNAPS.glob("*.tgz"))
adapters = discover_adapters(str(AGENT), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)

# ---- cell 3: VllmConfig exactly as the Kaggle kernel (INSTANCES_PER_GPU = 1 -> util 0.85) ----
cfg = VllmConfig(model=str(MODEL_PATH), port=8000, host='127.0.0.1',
                 tool_call_parser='gemma4', reasoning_parser='gemma4',
                 dtype='bfloat16' if torch.cuda.is_bf16_supported() else 'auto',
                 enable_auto_tool_choice=True, enable_lora=False, tensor_parallel_size=1,
                 startup_timeout=60 * 25, max_model_len=32768, gpu_memory_utilization=0.85,
                 extra_args=['--served-model-name', TARGET_MODEL_NAME, '2'])
srv = VllmServer(cfg, adapter_manifest=adapters)
_orig = srv.build_env


def _pin():
    e = _orig()
    e['CUDA_VISIBLE_DEVICES'] = '0'
    return e


srv.build_env = _pin
log("booting vLLM ...")
srv.start()
boot_s = time.time() - T0
ids = [m['id'] for m in json.load(urllib.request.urlopen(srv.base_url.rstrip('/') + '/models'))['data']]
log("vLLM up", srv.base_url, "models", ids)
assert TARGET_MODEL_NAME in ids

# ---- cell 4: identical eval command, caps from eval_config.yaml ----
raw = yaml.safe_load((AGENT / "eval_config.yaml").read_text()) or {}
c = raw.get("evaluation", raw) or {}
caps = []
for k_, flag in (("max_tool_calls", "--max-tool-calls"), ("max_time_minutes", "--max-time-minutes"),
                 ("max_turns", "--max-turns")):
    if c.get(k_) is not None:
        caps += [flag, str(c[k_])]
OUT.mkdir(parents=True, exist_ok=True)
env = dict(os.environ)
env["OPENAI_BASE_URL"] = srv.base_url
env["OPENAI_API_KEY"] = "EMPTY"
cmd = [sys.executable, "-m", "swegemma", "eval", "--tasks", str(TASKS), "--snapshots-dir", str(SNAPS),
       "--results-dir", str(OUT), "--submission-dir", str(AGENT), "--sandbox", "subprocess",
       "--concurrency", str(len(TASK_IDS)), "--display", "quiet"] + caps
for t in TASK_IDS:
    cmd += ["--task-id", t]
log("eval cmd:", " ".join(cmd[1:]))
t_eval = time.time()
p = subprocess.run(cmd, env=env, cwd=str(WORK), capture_output=True, text=True, timeout=3 * 3600)
eval_s = time.time() - t_eval
(WORK / "eval_stdout.txt").write_text(p.stdout or "")
(WORK / "eval_stderr.txt").write_text(p.stderr or "")
rows = []
rf = OUT / "task_results.jsonl"
if rf.exists():
    rows = [json.loads(l) for l in rf.read_text().splitlines() if l.strip()]
summ = {"rc": p.returncode, "boot_s": round(boot_s), "eval_wall_s": round(eval_s), "n": len(rows),
        "solved": sum(bool(r.get("resolved")) for r in rows), "caps": caps,
        "rows": [{k: r.get(k) for k in ("instance_id", "resolved", "tool_calls", "total_llm_calls",
                                         "agent_patch_size", "duration_seconds", "test_exit_code", "error")}
                 for r in rows]}
(WORK / "smoke_summary.json").write_text(json.dumps(summ, indent=1))
log("SMOKE DONE", json.dumps({k: summ[k] for k in ("rc", "boot_s", "eval_wall_s", "n", "solved")}))
for r in summ["rows"]:
    log(f"  {r['instance_id']:15s} resolved={r['resolved']} calls={r['tool_calls']} dur={r['duration_seconds']} "
        f"err={str(r['error'])[:80]}")
if not rows:
    log("STDERR tail:", (p.stderr or "")[-3000:])
srv.stop() if hasattr(srv, "stop") else None
