"""Build a 4x-PARALLEL E4B eval kernel: 4 independent tp=1 vLLM servers (one per L4), tasks sharded
across them. This is the standard dev-batch harness going forward (the stock kernel serves ONE tp=1
instance and leaves 3 of the 4 L4s idle -- the waste the user flagged).

Forks push_e4b_verify_batch (so it inherits the verify-fix bundle embedding + the relaxed sha assert),
and rewrites ONLY the serve cell (3) and the eval cell (4):
  CELL 3: start 4 tp=1 servers, each pinned to GPU i via CUDA_VISIBLE_DEVICES (build_env does
          os.environ.copy(), so the device set before .start() sticks to that server). ports 8000..8003.
  CELL 4: split the task list into 4 shards, launch 4 concurrent `swegemma eval` subprocesses, each with
          its own OPENAI_BASE_URL + results dir, then merge the rows. Per-GPU concurrency kept modest.

Usage knobs at top: BATCH_IDS (empty list => all 129), N_GPU, PER_GPU_CONC.
No GPU here; writes the kernel only.
"""
import json
import re
from pathlib import Path

K = Path(__file__).resolve().parent
SRC = K / "push_e4b_verify_batch"      # inherits the verify bundle embedding
DST = K / "push_e4b_verify_par"
assert SRC.is_dir(), "run _build_verify_kernel.py first (need push_e4b_verify_batch)"

# ---- KNOBS ----
# BATCH_IDS empty => all 129. N_GPU: use 1 for small batches (one ~300s boot beats 4), 4 for the full
# 129 (concurrent boot ~300s once, then 4x eval throughput). PER_GPU_CONC: concurrent agent loops/server.
# Guidance (measured 2026-11-02): E4B tp=1 boot ~150-295s/server; with concurrent boot 4 servers ~300s
# total, so 4-GPU only wins when there are enough tasks to amortize (full 129). For <=8 tasks use N_GPU=1.
BATCH_IDS = ["rich_4077", "rich_3894", "rich_3006", "rich_3905", "fastapi_14301", "fastapi_14463"]
N_GPU = 4
PER_GPU_CONC = 3

import shutil
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir()
nb = json.loads((SRC / "e4b-verify-batch.ipynb").read_text(encoding="utf-8"))

# ================= CELL 3: four tp=1 servers, one per GPU =================
SERVE = r'''# ---------- 2. Serve N independent tp=1 E4B instances, one per L4 (4x parallel dev harness) ----------
import litellm, json as _json, urllib.request as _req, time as _time
from adk_submission import VllmConfig, VllmServer, discover_adapters
try:
    from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
except Exception:
    ALLOWED_ADAPTER_EXTENSIONS = frozenset({'.safetensors', '.bin', '.pt', '.pth', '.gguf', '.ggml'})
litellm.drop_params = True
TARGET_MODEL_NAME = 'gemma-4-e4b-it-qat-w4a16-ct'
MODEL_PATH = Path('/kaggle/input/models/google/gemma-4/other/gemma-4-e4b-it-qat-w4a16-ct/2')
print("model path exists:", MODEL_PATH.exists())
if not MODEL_PATH.exists():
    raise SystemExit("E4B model source not mounted")

import re as _re2
_m2 = _re2.search(r'(?m)^\s*model:\s*(\S+)', (AGENT / 'agent.yaml').read_text(encoding='utf-8'))
DECLARED = _m2.group(1) if _m2 else TARGET_MODEL_NAME
adapters = discover_adapters(str(AGENT), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)

import threading as _thr
N_GPU = min(__NGPU__, torch.cuda.device_count() or 1)
print(f"starting {N_GPU} tp=1 servers (one per GPU) CONCURRENTLY", flush=True)

def _make_server(gpu, port):
    # Pin this server to GPU `gpu` WITHOUT touching the shared os.environ (threads race):
    # override the instance's build_env() to inject CUDA_VISIBLE_DEVICES for ITS subprocess only.
    cfg = VllmConfig(
        model=str(MODEL_PATH), port=port, host='127.0.0.1',
        tool_call_parser='gemma4', reasoning_parser='gemma4',
        dtype='bfloat16' if torch.cuda.is_bf16_supported() else 'auto',
        enable_auto_tool_choice=True, enable_lora=False,
        tensor_parallel_size=1, startup_timeout=60 * 25,
        max_model_len=32768, gpu_memory_utilization=0.85,
        extra_args=['--served-model-name', TARGET_MODEL_NAME, '2'],
    )
    s = VllmServer(cfg, adapter_manifest=adapters)
    _orig_build_env = s.build_env
    def _pinned_env():
        e = _orig_build_env()
        e['CUDA_VISIBLE_DEVICES'] = str(gpu)
        return e
    s.build_env = _pinned_env
    return s

SERVERS = [None] * N_GPU
_errs = [None] * N_GPU
def _boot(i):
    port = 8000 + i
    for attempt in range(1, 4):
        try:
            print(f"[serve gpu{i} :{port}] attempt {attempt}", flush=True)
            s = _make_server(i, port)
            s.start()                    # spawns subprocess + blocks on health, but in THIS thread
            SERVERS[i] = s
            print(f"  gpu{i} up: {s.base_url}", flush=True)
            return
        except Exception as e:
            print(f"  gpu{i} attempt {attempt} FAILED: {type(e).__name__}: {str(e)[:300]}", flush=True)
            _errs[i] = e
    # all attempts failed
# launch all boots at once so the ~5-min health waits OVERLAP instead of serializing
_boot_threads = [_thr.Thread(target=_boot, args=(i,)) for i in range(N_GPU)]
_bt0 = _time.time()
for th in _boot_threads: th.start()
for th in _boot_threads: th.join()
print(f"all server boots joined in {_time.time()-_bt0:.0f}s (concurrent)", flush=True)
SERVERS = [s for s in SERVERS if s is not None]
assert len(SERVERS) == N_GPU, f"only {len(SERVERS)}/{N_GPU} servers came up; errs={_errs}"

BASE_URLS = [s.base_url for s in SERVERS]
print("BASE_URLS:", BASE_URLS, flush=True)

# smoke each server on the id the agent will actually request
for i, s in enumerate(SERVERS):
    ids = [m['id'] for m in _json.load(_req.urlopen(s.base_url.rstrip('/') + '/models'))['data']]
    assert TARGET_MODEL_NAME in ids, f"gpu{i} served ids {ids} missing {TARGET_MODEL_NAME}"
    body = _json.dumps({'model': DECLARED, 'max_tokens': 8,
                        'messages': [{'role': 'user', 'content': 'Reply with OK'}]}).encode()
    r = _req.Request(s.base_url.rstrip('/') + '/chat/completions', data=body,
                     headers={'Content-Type': 'application/json', 'Authorization': 'EMPTY'})
    resp = _json.load(_req.urlopen(r))
    print(f"  SMOKE gpu{i} ->", repr(resp['choices'][0]['message'].get('content'))[:40], flush=True)
print("ALL SERVERS READY", flush=True)
'''
SERVE = SERVE.replace("__NGPU__", str(N_GPU))
nb["cells"][3]["source"] = SERVE.splitlines(keepends=True)

# ================= CELL 4: shard tasks across the N servers, run in parallel =================
EVAL = r'''# ---------- 3. Sharded parallel eval: split tasks across the N servers ----------
import threading, subprocess as _sp, yaml as _yaml, time as _t
OUT = Path("/kaggle/working/results"); OUT.mkdir(parents=True, exist_ok=True)

BATCH_IDS = __BATCH__
PER_GPU_CONC = __CONC__

# caps from eval_config (mirror the grader)
_cfg = {}
_ec = Path(AGENT) / "eval_config.yaml"
if _ec.exists():
    _raw = _yaml.safe_load(_ec.read_text()) or {}
    _cfg = _raw.get("evaluation", _raw) or {}
CAPS = []
for _k, _flag in (("max_tool_calls", "--max-tool-calls"), ("max_time_minutes", "--max-time-minutes"),
                  ("max_turns", "--max-turns")):
    if _cfg.get(_k) is not None:
        CAPS += [_flag, str(_cfg[_k])]
print("board caps:", CAPS or "(none)", flush=True)

all_ids = [json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()]
if BATCH_IDS:
    want = set(BATCH_IDS)
    all_ids = [i for i in all_ids if i in want]
print(f"tasks to run: {len(all_ids)}", flush=True)

# round-robin shard so repos/hard-tasks spread evenly across GPUs
shards = [all_ids[i::len(BASE_URLS)] for i in range(len(BASE_URLS))]
for i, sh in enumerate(shards):
    print(f"  shard {i} (gpu{i}, :{8000+i}): {len(sh)} tasks", flush=True)

results_lock = threading.Lock()
rows_all = []

def _run_shard(i, base_url, task_ids):
    if not task_ids:
        return
    shard_out = OUT / f"shard{i}"; shard_out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["OPENAI_BASE_URL"] = base_url
    env["OPENAI_API_KEY"] = "EMPTY"
    cmd = [sys.executable, "-m", "swegemma", "eval",
           "--tasks", str(TASKS), "--snapshots-dir", str(SNAPS),
           "--results-dir", str(shard_out), "--submission-dir", str(AGENT),
           "--sandbox", "subprocess", "--concurrency", str(PER_GPU_CONC),
           "--display", "quiet"] + CAPS
    for t in task_ids:
        cmd += ["--task-id", t]
    t0 = _t.time()
    p = _sp.run(cmd, env=env, capture_output=True, text=True)
    print(f"[shard {i}] rc={p.returncode} wall={_t.time()-t0:.0f}s", flush=True)
    if p.returncode != 0:
        print(f"[shard {i}] STDERR tail:", (p.stderr or "")[-600:], flush=True)
    rf = shard_out / "task_results.jsonl"
    got = []
    if rf.exists():
        for l in open(rf):
            if l.strip():
                r = json.loads(l)
                got.append(r)
                print(f"  [gpu{i}] {r['instance_id']:<16} resolved={bool(r.get('resolved'))} "
                      f"calls={r.get('tool_calls')} patch={r.get('agent_patch_size')} "
                      f"err={str(r.get('error') or '')[:60]}", flush=True)
    with results_lock:
        rows_all.extend(got)

threads = [threading.Thread(target=_run_shard, args=(i, BASE_URLS[i], shards[i]))
           for i in range(len(BASE_URLS))]
t0 = _t.time()
for th in threads: th.start()
for th in threads: th.join()
print(f"\nALL SHARDS DONE in {_t.time()-t0:.0f}s (vs ~{len(all_ids)} serial-task-times)", flush=True)

k = sum(int(bool(r.get("resolved"))) for r in rows_all)
print(f"\n=== VERIFY BATCH (4x parallel): {k}/{len(rows_all)} ===", flush=True)
by = {}
for r in rows_all:
    repo = r.get("repo") or r["instance_id"].split("_")[0]
    d = by.setdefault(repo, [0, 0]); d[0] += int(bool(r.get("resolved"))); d[1] += 1
for repo, (kk, nn) in sorted(by.items()):
    print(f"  {repo:<22} {kk:>3}/{nn:<3}", flush=True)
# merge all shard rows into one durable file + a summary
with open(OUT / "task_results.all.jsonl", "w") as f:
    for r in rows_all:
        f.write(json.dumps(r) + "\n")
with open("/kaggle/working/summary.json", "w") as f:
    json.dump({"resolved": k, "total": len(rows_all), "by_repo": by, "prompt_sha": sha}, f, indent=2)
print("wrote summary.json", flush=True)
'''
EVAL = EVAL.replace("__BATCH__", json.dumps(BATCH_IDS)).replace("__CONC__", str(PER_GPU_CONC))
nb["cells"][4]["source"] = EVAL.splitlines(keepends=True)

# retitle
nb["cells"][0]["source"] = [
    "# E4B VERIFY-FIX gate -- 4x PARALLEL (one tp=1 server per L4, tasks sharded)\n",
    "Standard dev harness: 4 GPUs busy instead of 1. Same verify-fix bundle + caps.\n",
    f"Batch = {BATCH_IDS or 'ALL 129'}. Read per-task resolved + VERIFY: lines in results/shard*/logs.\n",
]

(DST / "e4b-verify-par.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
meta = json.loads((SRC / "kernel-metadata.json").read_text(encoding="utf-8"))
meta.update(id="comfyops/e4b-verify-par", title="e4b verify par", code_file="e4b-verify-par.ipynb")
(DST / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("wrote", DST)
print("N_GPU", N_GPU, "PER_GPU_CONC", PER_GPU_CONC, "batch", BATCH_IDS or "ALL 129")
