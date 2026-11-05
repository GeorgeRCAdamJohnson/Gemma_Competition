"""Build kaggle_pkg/push_e4b_variance: 3-HOUR VARIANCE HARNESS for ca5 E4B on the full 129.

Goal: measure run-to-run variance by repeating the full 129-task eval as many times as fits in ~3h,
maximizing GPU use with MULTIPLE instances per L4 (E4B QAT ~6-7GB; 23.7GB L4 fits 2 comfortably).

DESIGN:
- INSTANCES_PER_GPU=2 -> 8 tp=1 E4B servers (ports 8000..8007), 2 pinned to each of the 4 L4s via a
  per-server CUDA_VISIBLE_DEVICES build_env override. gpu_memory_utilization 0.40 each (2x6.5GB weights +
  KV fits in 23.7GB). Concurrent boot (threads) so the ~300s health waits overlap.
- TIME-BOXED loop: repeatedly run the full 129 (sharded 8-way across the servers) until the 3h wall minus
  a 12-min save-reserve. Each pass tagged run_1, run_2, ... Results appended to a durable per-pass file.
- Config = ca5 (agent_ctrl_e4b, our banked E4B baseline). Caps from eval_config (28/8). No compaction
  (matches our E4B Kaggle baseline, for comparability with prior ca5 numbers).
- Output: variance.json with per-pass resolved sets + the cross-pass stability analysis (stable core,
  flaky set, per-task resolve rate, mean/sd of total resolves).

Kaggle kernel wall is 12h max; we self-limit to ~3h via BUDGET_SECONDS.
"""
import base64
import json
import re
import shutil
from pathlib import Path

K = Path(__file__).resolve().parent
SRC = K / "push_e4b_verify_par"      # concurrent-boot serve machinery + embed
DST = K / "push_e4b_variance"
BUNDLE = K.parent / "local_eval" / "parity_rig" / "agent_ctrl_e4b"   # ca5 control = best banked E4B
INSTANCES_PER_GPU = 1              # PROVEN: 1/GPU (4 servers, util 0.85) boots clean every prior run.
                                   # 2/GPU OOM'd twice (vLLM memory profiler assumes sole card ownership
                                   # even staggered). Not worth more 3h-window risk; 4 servers gives
                                   # plenty of passes. Revisit density with explicit --kv-cache caps later.
BUDGET_SECONDS = 3 * 3600          # 3 hours total
SAVE_RESERVE_SECONDS = 12 * 60     # stop launching new passes with 12 min left

assert SRC.is_dir() and BUNDLE.is_dir()
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir()

emb = {}
for p in sorted(BUNDLE.rglob("*")):
    if p.is_file() and "__pycache__" not in p.parts:
        emb[p.relative_to(BUNDLE).as_posix()] = base64.b64encode(p.read_bytes()).decode()

nb = json.loads((SRC / "e4b-verify-par.ipynb").read_text(encoding="utf-8"))

# ---- CELL 2: embed ca5, materialize AGENT, keep tasks + snapshot resolver (reuse stock single-bundle path) ----
# Rebuild push_e4b_verify_batch-style cell2 is complex; instead take the ORIGINAL push_129_e4b cell2 (single
# flat bundle, 4 files) which already materializes AGENT + tasks + snapshots cleanly, and swap its EMBED.
orig = json.loads((K / "push_129_e4b" / "ca5-e4b-full129.ipynb").read_text(encoding="utf-8"))
cell2 = "".join(orig["cells"][2]["source"])
m = re.search(r'EMBED = json\.loads\("""(.*?)"""\)', cell2, re.S)
stock = json.loads(m.group(1))
emb_flat = {
    "system.md": emb["prompts/system.md"],
    "agent.yaml": emb["agent.yaml"],
    "sampling.yaml": emb["configs/sampling.yaml"],
    "eval_config.yaml": emb["eval_config.yaml"],
    "tasks.jsonl_gz": stock["tasks.jsonl_gz"],
}
cell2 = cell2.replace(m.group(0), 'EMBED = json.loads("""%s""")' % json.dumps(emb_flat), 1)
# drop the ca5 sha assert (control content is ca5 but line-endings differ)
cell2 = re.sub(r'assert sha == "b08b32a2438d".*?\n',
               'print("prompt sha (ca5 control):", sha)\n', cell2, count=1, flags=re.S)
nb["cells"][1]["source"] = orig["cells"][1]["source"]   # use the stock wheelhouse cell too
nb["cells"][2]["source"] = cell2.splitlines(keepends=True)

# ---- CELL 3: 8 servers (2 per GPU), concurrent boot, per-server CUDA pin ----
SERVE = r'''# ---------- Serve N_SERVERS tp=1 E4B instances: INSTANCES_PER_GPU per L4 (max GPU use) ----------
import litellm, json as _json, urllib.request as _req, time as _time, threading as _thr
from adk_submission import VllmConfig, VllmServer, discover_adapters
try:
    from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
except Exception:
    ALLOWED_ADAPTER_EXTENSIONS = frozenset({'.safetensors','.bin','.pt','.pth','.gguf','.ggml'})
litellm.drop_params = True
TARGET_MODEL_NAME = 'gemma-4-e4b-it-qat-w4a16-ct'
MODEL_PATH = Path('/kaggle/input/models/google/gemma-4/other/gemma-4-e4b-it-qat-w4a16-ct/2')
assert MODEL_PATH.exists(), "E4B model not mounted"
import re as _re2
DECLARED = (_re2.search(r'(?m)^\s*model:\s*(\S+)', (AGENT/'agent.yaml').read_text(encoding='utf-8')) or [None, TARGET_MODEL_NAME])[1] \
           if True else TARGET_MODEL_NAME
_m2 = _re2.search(r'(?m)^\s*model:\s*(\S+)', (AGENT/'agent.yaml').read_text(encoding='utf-8'))
DECLARED = _m2.group(1) if _m2 else TARGET_MODEL_NAME
adapters = discover_adapters(str(AGENT), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)

INSTANCES_PER_GPU = __IPG__
NG = torch.cuda.device_count() or 1
N_SERVERS = NG * INSTANCES_PER_GPU
# vLLM profiles peak memory assuming it owns the card. Two instances booting SIMULTANEOUSLY on the same
# GPU each grab util*23.7 AND profile as if alone -> collective over-commit -> OOM exit code 1 (observed).
# FIX: (1) lower util so 2 genuinely fit with profiling headroom: 6.5GB weights + KV + profile margin;
#      (2) boot ROUND-BY-ROUND: all GPU-0..3 first instances concurrently, wait healthy, THEN the seconds.
UTIL = round(min(0.42, (20.0/INSTANCES_PER_GPU)/23.7), 3) if INSTANCES_PER_GPU > 1 else 0.85
print(f"booting {N_SERVERS} servers ({INSTANCES_PER_GPU}/GPU x {NG} GPUs), util={UTIL}, staggered by round", flush=True)

def _make(gpu, port):
    cfg = VllmConfig(model=str(MODEL_PATH), port=port, host='127.0.0.1',
        tool_call_parser='gemma4', reasoning_parser='gemma4',
        dtype='bfloat16' if torch.cuda.is_bf16_supported() else 'auto',
        enable_auto_tool_choice=True, enable_lora=False, tensor_parallel_size=1,
        startup_timeout=60*25, max_model_len=32768, gpu_memory_utilization=UTIL,
        extra_args=['--served-model-name', TARGET_MODEL_NAME, '2'])
    s = VllmServer(cfg, adapter_manifest=adapters)
    _orig = s.build_env
    def _pin():
        e = _orig(); e['CUDA_VISIBLE_DEVICES'] = str(gpu); return e
    s.build_env = _pin
    return s

SERVERS = {}; _errs = {}
def _boot(idx):
    gpu = idx % NG; port = 8000+idx
    for att in range(1,4):
        try:
            print(f"[srv{idx} gpu{gpu} :{port}] attempt {att}", flush=True)
            s=_make(gpu,port); s.start(); SERVERS[idx]=s
            print(f"  srv{idx} up {s.base_url}", flush=True); return
        except Exception as e:
            _errs[idx]=e; print(f"  srv{idx} att{att} FAIL {type(e).__name__}: {str(e)[:200]}", flush=True)

# ROUND r = server indices [r*NG, r*NG+NG): one per GPU, booted concurrently; rounds run SEQUENTIALLY so
# the second instance on a GPU never races the first's memory profiling.
_bt=_time.time()
for r in range(INSTANCES_PER_GPU):
    idxs = [r*NG + g for g in range(NG)]
    print(f"--- boot round {r+1}/{INSTANCES_PER_GPU}: servers {idxs} ---", flush=True)
    ths=[_thr.Thread(target=_boot,args=(i,)) for i in idxs]
    for t in ths: t.start()
    for t in ths: t.join()
    print(f"  round {r+1} done, {len(SERVERS)} servers up so far ({_time.time()-_bt:.0f}s)", flush=True)
print(f"all boot rounds joined in {_time.time()-_bt:.0f}s", flush=True)
SERVERS=[SERVERS[i] for i in sorted(SERVERS)]
assert len(SERVERS)>=NG, f"too few servers up: {len(SERVERS)}/{N_SERVERS}; errs={[str(e)[:80] for e in _errs.values() if e]}"
BASE_URLS=[s.base_url for s in SERVERS]
print("live servers:", len(BASE_URLS), BASE_URLS, flush=True)
# smoke one
_ids=[m['id'] for m in _json.load(_req.urlopen(SERVERS[0].base_url.rstrip('/')+'/models'))['data']]
assert TARGET_MODEL_NAME in _ids
print("SMOKE OK", flush=True)
'''
SERVE = SERVE.replace("__IPG__", str(INSTANCES_PER_GPU))
# AGENT is defined in cell2 (materialize); serve uses it. Prepend nothing needed.
nb["cells"][3]["source"] = SERVE.splitlines(keepends=True)

# ---- CELL 4: 3-hour time-boxed repeat loop ----
EVAL = r'''# ---------- 3-HOUR VARIANCE LOOP: repeat full-129 (8-way sharded) until the budget ----------
import threading, subprocess as _sp, yaml as _yaml, time as _t, statistics as _stats
BUDGET_SECONDS = __BUDGET__
SAVE_RESERVE = __RESERVE__
PER_GPU_CONC = 3
START = _t.time()
OUT = Path("/kaggle/working/results"); OUT.mkdir(parents=True, exist_ok=True)
VAR = Path("/kaggle/working/variance.json")

_raw = _yaml.safe_load((AGENT/'eval_config.yaml').read_text()) or {}
_c = _raw.get("evaluation", _raw) or {}
CAPS=[]
for k,flag in (("max_tool_calls","--max-tool-calls"),("max_time_minutes","--max-time-minutes"),("max_turns","--max-turns")):
    if _c.get(k) is not None: CAPS += [flag, str(_c[k])]
ALL_IDS = [json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()]
print(f"variance run: {len(ALL_IDS)} tasks x as many passes as fit in {BUDGET_SECONDS//3600}h on {len(BASE_URLS)} servers | caps {CAPS}", flush=True)

PASSES = []   # each = {"run": n, "resolved": [...], "k": int, "seconds": float}

def _one_pass(run_no):
    pass_out = OUT / f"run_{run_no}"; 
    if pass_out.exists(): shutil.rmtree(pass_out)
    pass_out.mkdir(parents=True, exist_ok=True)
    shards = [ALL_IDS[i::len(BASE_URLS)] for i in range(len(BASE_URLS))]
    lock = threading.Lock(); rows=[]
    def _run(i, base_url, ids):
        if not ids: return
        so = pass_out / f"shard{i}"; so.mkdir(parents=True, exist_ok=True)
        env=dict(os.environ); env["OPENAI_BASE_URL"]=base_url; env["OPENAI_API_KEY"]="EMPTY"
        cmd=[sys.executable,"-m","swegemma","eval","--tasks",str(TASKS),"--snapshots-dir",str(SNAPS),
             "--results-dir",str(so),"--submission-dir",str(AGENT),"--sandbox","subprocess",
             "--concurrency",str(PER_GPU_CONC),"--display","quiet"]+CAPS
        for t in ids: cmd += ["--task-id", t]
        _sp.run(cmd, env=env, capture_output=True, text=True)
        rf = so/"task_results.jsonl"
        if rf.exists():
            with lock:
                for l in open(rf):
                    if l.strip(): rows.append(json.loads(l))
    ths=[threading.Thread(target=_run,args=(i,BASE_URLS[i],shards[i])) for i in range(len(BASE_URLS))]
    t0=_t.time()
    for t in ths: t.start()
    for t in ths: t.join()
    resolved=sorted(r["instance_id"] for r in rows if r.get("resolved"))
    return {"run":run_no,"resolved":resolved,"k":len(resolved),"n":len(rows),"seconds":round(_t.time()-t0,1)}

run_no=0
while True:
    elapsed=_t.time()-START
    if elapsed > BUDGET_SECONDS - SAVE_RESERVE:
        print(f"stopping: {elapsed:.0f}s elapsed, within save-reserve", flush=True); break
    run_no+=1
    print(f"\n--- PASS {run_no} (elapsed {elapsed/60:.1f}m) ---", flush=True)
    p = _one_pass(run_no)
    PASSES.append(p)
    print(f"  PASS {run_no}: {p['k']}/{p['n']} in {p['seconds']:.0f}s", flush=True)
    # persist after every pass so a kill is not fatal
    json.dump({"passes":PASSES}, open(VAR,"w"), indent=2)

# ---- variance analysis ----
ks=[p["k"] for p in PASSES]
from collections import Counter
hit=Counter()
for p in PASSES:
    for t in p["resolved"]: hit[t]+=1
npass=len(PASSES)
stable=sorted(t for t,c in hit.items() if c==npass)
flaky=sorted((t,c) for t,c in hit.items() if 0<c<npass)
never=len(ALL_IDS)-len(hit)
summary={
  "passes":npass,"k_per_pass":ks,
  "k_mean":round(_stats.mean(ks),2) if ks else 0,
  "k_sd":round(_stats.pstdev(ks),2) if len(ks)>1 else 0,
  "k_min":min(ks) if ks else 0,"k_max":max(ks) if ks else 0,
  "stable_core":stable,"stable_n":len(stable),
  "flaky":[{"task":t,"hits":c,"of":npass} for t,c in flaky],"flaky_n":len(flaky),
  "ever_solved":len(hit),"never_solved":never,
}
json.dump({"passes":PASSES,"summary":summary}, open(VAR,"w"), indent=2)
print("\n"+"="*60+"\nVARIANCE SUMMARY ("+str(npass)+" passes of 129)\n"+"="*60, flush=True)
print(f"  k per pass: {ks}", flush=True)
print(f"  mean {summary['k_mean']} sd {summary['k_sd']} min {summary['k_min']} max {summary['k_max']}", flush=True)
print(f"  STABLE core (every pass): {len(stable)} | FLAKY: {len(flaky)} | ever: {len(hit)} | never: {never}", flush=True)
print(f"  flaky detail: {summary['flaky']}", flush=True)
print("wrote variance.json", flush=True)
'''
EVAL = EVAL.replace("__BUDGET__", str(BUDGET_SECONDS)).replace("__RESERVE__", str(SAVE_RESERVE_SECONDS))
nb["cells"][4]["source"] = EVAL.splitlines(keepends=True)

nb["cells"][0]["source"] = [
    "# E4B ca5 VARIANCE HARNESS - repeat full-129 for ~3h on 8 servers (2 per L4)\n",
    "Measures run-to-run variance: k per pass, stable core, flaky set. Config = ca5 (best banked E4B).\n",
]
(DST / "e4b-variance.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
meta = json.loads((SRC / "kernel-metadata.json").read_text(encoding="utf-8"))
meta.update(id="comfyops/e4b-variance-129", title="e4b variance 129", code_file="e4b-variance.ipynb")
(DST / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("wrote", DST, "| instances/gpu", INSTANCES_PER_GPU, "| budget", BUDGET_SECONDS, "s")
