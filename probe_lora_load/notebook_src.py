# Gemma 4 Developer Agent — STAGE-2 ADAPTER-LOAD PROBE (the LoRA gate; NOT a leaderboard submission)
# PURPOSE (GEMMA_EXPERIMENT_LOG "TRACK A STAGE-2"): we trained localizer_v1 (r=16, 84MB) on the UNQUANTIZED
# QAT twin via bnb-nf4. The SCORED model is gemma-4-31b-it-qat-w4a16-ct — a DIFFERENT quantizer. This probe
# answers the ONE open question that gates the whole LoRA track:
#   (A) does vLLM LOAD the adapter over the w4a16 model (enable_lora, --lora-modules) WITHOUT a shape/rank error?
#   (B) with the adapter ACTIVE, does the agent still emit a NON-EMPTY patch (no regression to 0)?
# If (A)+(B) pass -> the LoRA path is LIVE and we can build a real LoRA submission + measure resolve lift.
# If (A) fails -> DEBUG the encoding/target-module naming (rule 11: a load failure on a novel idea with real
#   signal is a debugging task, NOT idea-death). Do NOT retreat from the LoRA.
# This is a MINIMAL probe: v6-style agent (no sub-agent) + adapter: localizer_v1, run on 2 anchor tasks,
# read the vLLM startup logs for the LoRA-load line + confirm non-empty patches. Resolve-rate is secondary.
#
# ADAPTER DELIVERY: localizer_v1 (84MB) is attached as a Kaggle input (dataset/model) and COPIED into the
# submission's adapters/ dir at runtime. ATTACH the adapter dataset to this session before running; the
# resolver globs for adapter_model.safetensors under /kaggle/input so it finds it wherever it mounts.

# ===== CELL 1: environment + wheelhouse (robust path resolve) =====
import glob, importlib, os, shutil, subprocess, sys
from pathlib import Path
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['TRANSFORMERS_NO_TF'] = '1'
os.environ['VLLM_WORKER_MULTIPROC_METHOD'] = 'spawn'
os.environ['VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS'] = '1'
os.environ['VLLM_ENGINE_READY_TIMEOUT_S'] = '1200'
os.environ['VLLM_NO_USAGE_STATS'] = '1'
os.environ['OTEL_SDK_DISABLED'] = 'true'
os.environ['PYTORCH_CUDA_ALLOC_CONF'] = 'expandable_segments:True'
_WHEEL_HINTS = [
    '/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse',
    '/kaggle/input/gemma-4-developer-agent-wheelhouse',
]
_wheel_src = next((p for p in _WHEEL_HINTS if Path(p).is_dir()), None)
if _wheel_src is None:
    _found = glob.glob('/kaggle/input/**/*.whl', recursive=True)
    _wheel_src = str(Path(_found[0]).parent) if _found else None
print(f'[wheelhouse] source dir: {_wheel_src}')
for pth_pattern in ('/usr/local/lib/python*/dist-packages/*cutlass*.pth',
                    '/usr/local/lib/python*/site-packages/*cutlass*.pth'):
    for pth in glob.glob(pth_pattern):
        try: os.unlink(pth)
        except OSError: pass
tmp_whl = Path('/tmp/wheelhouse'); tmp_whl.mkdir(parents=True, exist_ok=True)
if _wheel_src:
    for w in Path(_wheel_src).glob('*.whl'):
        if 'cutlass' in w.name.lower(): continue
        target_name = (w.name.replace('cu128', '+cu128') if ('cu128' in w.name and '+' not in w.name) else w.name)
        target = tmp_whl / target_name
        if not target.exists():
            try: os.symlink(w, target)
            except FileExistsError: pass
wheels = sorted(str(w) for w in tmp_whl.glob('*.whl'))
print(f'Installing {len(wheels)} wheels...')
if wheels:
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *wheels], check=True)
    importlib.invalidate_caches()
    print('Wheelhouse installation complete.')
else:
    print('[wheelhouse] WARNING: 0 wheels found. /kaggle/input contents:')
    for p in sorted(glob.glob('/kaggle/input/*')) + sorted(glob.glob('/kaggle/input/*/*')):
        print('   ', p)

# ===== CELL 2: write agent dir (v6-style, NO sub-agent) + COPY adapter into adapters/localizer_v1 =====
from swegemma.models import load_tasks
def _resolve_input(candidates, sentinel):
    for c in candidates:
        if sentinel and (Path(c) / sentinel).exists(): return Path(c)
        if not sentinel and Path(c).is_dir(): return Path(c)
    hits = glob.glob(f'/kaggle/input/**/{sentinel}', recursive=True) if sentinel else []
    if hits: return Path(hits[0]).parent
    raise FileNotFoundError(f'resolve failed: {candidates} + glob {sentinel!r}; /kaggle/input={sorted(glob.glob("/kaggle/input/*"))}')
DATA_DIR = _resolve_input([
    '/kaggle/input/competitions/gemma-4-developer-agent',
    '/kaggle/input/gemma-4-developer-agent',
], 'tasks.jsonl')
print(f'[data] DATA_DIR = {DATA_DIR}')

# locate the trained adapter among mounted inputs (attach the adapter dataset to this session first).
# the dataset was uploaded in zip mode, so Kaggle may mount it as localizer_v1.zip OR as an unzipped dir —
# handle both: prefer an unzipped adapter_config.json; else unzip any localizer_v1*.zip into /tmp.
import zipfile
_adapter_cfg = glob.glob('/kaggle/input/**/adapter_config.json', recursive=True)
if not _adapter_cfg:
    _zips = glob.glob('/kaggle/input/**/localizer_v1*.zip', recursive=True) or glob.glob('/kaggle/input/**/*.zip', recursive=True)
    for z in _zips:
        ex = Path('/tmp/_adapter_unzip') / Path(z).stem
        ex.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(z) as zf: zf.extractall(ex)
        hit = glob.glob(str(ex / '**' / 'adapter_config.json'), recursive=True)
        if hit:
            _adapter_cfg = hit; break
assert _adapter_cfg, ('localizer_v1 adapter NOT mounted. ATTACH comfyops/gemma-localizer-v1-adapter to this '
                      f'session. /kaggle/input={sorted(glob.glob("/kaggle/input/*"))}')
ADAPTER_SRC = Path(_adapter_cfg[0]).parent
print(f'[adapter] source = {ADAPTER_SRC}')

WORKING_DIR = Path('/kaggle/working'); WORKING_DIR.mkdir(parents=True, exist_ok=True)
AGENT_DIR = WORKING_DIR / 'submission'
if AGENT_DIR.exists(): shutil.rmtree(AGENT_DIR)
(AGENT_DIR / 'prompts').mkdir(parents=True, exist_ok=True)
(AGENT_DIR / 'configs').mkdir(parents=True, exist_ok=True)
# copy adapter into the submission (ONLY the 2 allowed files: adapter_config.json + adapter_model.safetensors)
dst = AGENT_DIR / 'adapters' / 'localizer_v1'; dst.mkdir(parents=True, exist_ok=True)
for fn in ('adapter_config.json', 'adapter_model.safetensors'):
    shutil.copy2(ADAPTER_SRC / fn, dst / fn)
sz = sum(f.stat().st_size for f in dst.glob('*'))
print(f'[adapter] copied -> {dst} ({sz/1e6:.1f} MB); files: {[f.name for f in dst.glob("*")]}')
assert sz < 3 * 1024**3, 'adapter over 3GiB cap'

# agent.yaml WITH adapter: localizer_v1 on the root coder (the thing under test). v6-style prompt, no sub-agent.
(AGENT_DIR / 'agent.yaml').write_text('''name: localizer_lora_probe_agent
model: gemma-4-31b-it-qat-w4a16-ct
adapter: localizer_v1
instruction: !include prompts/system.md
tools:
  - run_command
  - read_file
  - edit_file
  - write_file
  - get_status
  - submit_patch
  - get_code_neighbors
  - search_similar_code
  - get_code_subgraph
generate_content_config: !include configs/sampling.yaml
''', encoding='utf-8')

# sampling: per HARNESS_README, with LoRA over vLLM /v1 OMIT thinking_level; use include_thoughts + thinking_budget.
(AGENT_DIR / 'configs' / 'sampling.yaml').write_text('''temperature: 0.2
top_p: 0.95
max_output_tokens: 6144
thinking_config:
  thinking_budget: 4096
  include_thoughts: true
''', encoding='utf-8')

(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 5
  max_tool_calls: 22
  max_turns: 40
  timeout_seconds: 120
''', encoding='utf-8')

# Minimal v6-style coder prompt (the adapter is what we are testing, not prompt changes). Localization-leaning
# since the adapter was trained on localization trajectories.
(AGENT_DIR / 'prompts' / 'system.md').write_text('''You are an expert autonomous software engineer. You have a HARD budget of ~22 tool calls and 5 minutes. BE DECISIVE AND FAST.

## Workflow
1. Read the problem. Extract the concrete file/function/error tokens. If a path is named, read_file it; else grep the repo for those exact tokens to locate the bug (MAX 3-4 locate calls).
2. Make the minimal fix with edit_file. Match the file's existing conventions, message style, and the shape of any sibling check already there.
3. Call submit_patch ONCE; the moment it returns "ok", STOP.

## Hard rules
- NEVER modify test files (test_*.py, tests/) or runner config (conftest.py, pytest.ini, pyproject.toml).
- Scratch goes in /tmp via run_command heredoc, NOT write_file (which is jailed to /workspace).
- Offline: no pip install. Do NOT run bare pytest. Do NOT conclude without a non-empty patch.
''', encoding='utf-8')

TASKS_PATH = DATA_DIR / 'tasks.jsonl'
tasks = load_tasks(TASKS_PATH)
print(f'[agent] dir written WITH adapter: localizer_v1 -> {AGENT_DIR}')
print(f'Loaded {len(tasks)} tasks')

# ===== CELL 3: start vLLM server WITH the adapter — THE LOAD GATE (watch this cell's logs) =====
import litellm, torch
from adk_submission import VllmConfig, VllmServer, discover_adapters
from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
from swegemma.models.discovery import validate_single_declared_model
litellm.drop_params = True
TARGET_MODEL_NAME = 'gemma-4-31b-it-qat-w4a16-ct'
def _resolve_model():
    cands = [
        '/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2',
        '/kaggle/input/models/google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2',
    ]
    for c in cands:
        if Path(c, 'config.json').exists(): return Path(c)
    hits = glob.glob('/kaggle/input/**/gemma-4-31b-it-qat-w4a16-ct/**/config.json', recursive=True)
    if hits: return Path(hits[0]).parent
    raise FileNotFoundError(f'w4a16 model not found; /kaggle/input={sorted(glob.glob("/kaggle/input/*"))}')
MODEL_PATH = _resolve_model()
print(f'[model] MODEL_PATH = {MODEL_PATH}')
declared_model = validate_single_declared_model(AGENT_DIR)
# THE KEY STEP: discover_adapters must find localizer_v1 under AGENT_DIR/adapters and register it with vLLM.
adapters = discover_adapters(str(AGENT_DIR), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)
print(f'[adapter] discover_adapters found: {adapters}')
assert adapters, 'discover_adapters found NO adapters — wiring is wrong before we even start vLLM'
gpu_count = torch.cuda.device_count() if torch.cuda.is_available() else 1
tp_size = 4 if gpu_count >= 4 else (2 if gpu_count >= 2 else 1)
vllm_cfg = VllmConfig(
    model=str(MODEL_PATH), port=8000, host='127.0.0.1',
    tool_call_parser='gemma4', reasoning_parser='gemma4', max_model_len=32768,
    dtype='bfloat16' if (torch.cuda.is_available() and torch.cuda.is_bf16_supported()) else 'auto',
    gpu_memory_utilization=0.90, enable_auto_tool_choice=True,
    enable_lora=True, max_loras=8, max_lora_rank=128,
    tensor_parallel_size=tp_size, startup_timeout=60 * 20,
)
server_instance = VllmServer(vllm_cfg, adapter_manifest=adapters)
print('[gate A] starting vLLM WITH enable_lora + localizer_v1 — watch for a LoRA-load error here...', flush=True)
server_instance.start()   # <-- GATE A: if the adapter is incompatible with w4a16, this is where it throws.
print(f'[gate A PASS] vLLM server started on {server_instance.base_url} (tp={tp_size}) WITH adapter loaded', flush=True)
models = server_instance.create_model_registry(
    aliases=[declared_model, TARGET_MODEL_NAME], model_prefix='openai/', api_key='EMPTY')

# ===== CELL 4: run 2 anchor tasks WITH the adapter — GATE B (non-empty patch, no regression to 0) =====
import asyncio, concurrent.futures, yaml
import pandas as pd
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps._configs import EventsCompactionConfig
from swegemma.config import EvalConfig, build_submission_limits
from swegemma.evaluate import Evaluator
def run_sync(fn, *a, **k):
    try: loop = asyncio.get_running_loop()
    except RuntimeError: loop = None
    if loop is not None and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(fn(*a, **k))).result()
    return asyncio.run(fn(*a, **k))
raw = yaml.safe_load((AGENT_DIR / 'eval_config.yaml').read_text(encoding='utf-8'))
ev = raw.get('evaluation', raw)
PROBE_IDS = ['rich_4077', 'fastapi_14485']   # 2 small-single-file anchors; cheap, representative
by_iid = {t.instance_id: t for t in tasks}
PROBE_TASKS = [by_iid[i] for i in PROBE_IDS if i in by_iid]
limits, gen_constraints = build_submission_limits()
eval_config = EvalConfig(
    tasks_path=TASKS_PATH, snapshots_dir=DATA_DIR / 'snapshots', results_dir=WORKING_DIR / 'results',
    submission_dir=AGENT_DIR, models=models, sandbox='subprocess',
    timeout_seconds=int(ev.get('timeout_seconds', 120)), max_time_minutes=float(ev.get('max_time_minutes', 5)),
    max_tool_calls=int(ev.get('max_tool_calls', 22)), max_turns=int(ev.get('max_turns', 40)),
    limits=limits, generation_constraints=gen_constraints, adapter_manifest=adapters,
    context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
    events_compaction_config=EventsCompactionConfig(compaction_interval=15, overlap_size=2,
        token_threshold=14336, event_retention_size=5),
    graph_dir=str(DATA_DIR / 'graphs'), embeddings_dir=str(DATA_DIR / 'embeddings'),
    wheels_dir=DATA_DIR / 'wheels', verbose=False,
)
evaluator = Evaluator(eval_config)
rows = []
for i, t in enumerate(PROBE_TASKS, 1):
    print(f'[gate B {i}/{len(PROBE_TASKS)}] {t.instance_id} (adapter ACTIVE) ...', flush=True)
    r = run_sync(evaluator.evaluate_task, task=t, task_index=i, total_tasks=len(PROBE_TASKS))
    rows.append({'id': t.instance_id, 'resolved': bool(r.resolved),
                 'patch_chars': len(r.agent_patch or ''), 'tool_calls': r.tool_calls,
                 'duration_s': round(r.duration_seconds, 1)})
    print(f'  -> resolved={r.resolved} patch_chars={len(r.agent_patch or "")} calls={r.tool_calls}', flush=True)
tdf = pd.DataFrame(rows)
print('\n===== STAGE-2 PROBE RESULT =====')
print(tdf.to_string(index=False))
nonempty = int((tdf.patch_chars > 0).sum())
print(f'\n[gate A] vLLM started WITH adapter: PASS (reached here)')
print(f'[gate B] non-empty patches with adapter active: {nonempty}/{len(tdf)} '
      f'-> {"PASS (adapter does not break generation)" if nonempty == len(tdf) else "CHECK (some empty — inspect)"}')
print(f'resolved (secondary, not the gate): {tdf.resolved.sum()}/{len(tdf)}')
print('VERDICT: if gate A+B PASS, the LoRA path is LIVE -> build a real LoRA submission + measure resolve lift.')
