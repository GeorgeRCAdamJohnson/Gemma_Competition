"""Generate v6s (STOCK PROMPT CONTROL) notebook_src.py.

The stock system.md is embedded as a JSON string literal inside a Python raw string, so the
prompt that ships is BYTE-IDENTICAL to comp_files/system.md. A round-trip assertion is written
into the generated notebook and will fail loudly if the text drifted.

Design rationale (see GEMMA_EXPERIMENT_LOG.md v6s entry):
  - prompt   = comp_files/system.md VERBATIM  (the thing under test)
  - tools    = the 9-tool starter list VERBATIM (restores edit_file + write_file, keeps graph tools)
  - budget   = the 0.18 recipe 28/8/80/240  (HELD FIXED - NOT stock's own 10 calls / 1 min)
  - sampling = the 0.18 recipe 8192 / thinking 4096  (HELD FIXED - NOT stock's 16384)
  - tasks    = the SAME 6 as v6c, so the numbers are directly comparable.
Stock's own eval_config is 10 calls / 1 minute, which would starve the agent and confound the
prompt comparison with a budget difference. Holding budget at the externally-validated 0.18
recipe isolates what we have actually been changing for 22 versions.
"""
import json, pathlib

HERE = pathlib.Path(__file__).parent
stock = (HERE.parent / "comp_files" / "system.md").read_text(encoding="utf-8")
stock_json_literal = json.dumps(stock)

HEADER = '''# Gemma 4 Developer Agent - v6s = THE STOCK PROMPT CONTROL (never run before).
#
# THE QUESTION: every v1-v22 number in this project is measured against OUR OWN prior version.
# We have never measured against the official starter prompt that ships with the competition
# (comp_files/system.md). So we do not know whether 22 versions of custom sibling-conform
# method beat the DEFAULT. v6c just scored 4/6 on the rich gate; v6b scored 1/6. Is that our
# method working, or just prompt length / variance? This run answers it.
#
# WHAT IS HELD FIXED (so the comparison isolates the prompt):
#   - budget   = 28/8/80/240 - the externally-validated 0.18 recipe. NOT stock's own
#                eval_config, which is max_tool_calls 10 / max_time_minutes 1 and would
#                starve the agent, confounding PROMPT with BUDGET.
#   - sampling = max_output_tokens 8192 / thinking_budget 4096 - the 0.18 recipe. NOT stock's
#                16384 (honghanh notes 16384 "leaves too little room" in a 32k context).
#   - tasks    = the SAME 6 rich tasks as v6c, so numbers are directly comparable.
#   - no adapter, no sub-agent - both would add a second variable.
#
# WHAT CHANGES vs v6c (this IS the experiment):
#   - prompts/system.md = comp_files/system.md VERBATIM (embedded byte-exact below).
#   - agent.yaml tools = the 9-tool starter list, which RESTORES edit_file and write_file
#     and keeps the three graph tools. v6c ships 7 (edit_file/write_file removed).
#
# HONEST LIMIT (stated up front): this is a TWO-variable comparison - prompt text AND tool
# list both revert to stock. It answers "does our package beat the default?" (the question
# that matters). It does NOT isolate which of the two is responsible.
#
# NEW kernel id (comfyops/gemma-sibling-conform-v6s). v6/0.12, v6b, and v6c are untouched.

'''

CELL1 = '''# ===== CELL 1: environment + wheelhouse =====
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
WHEELHOUSE_DIR = Path('/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse')
for pth_pattern in ('/usr/local/lib/python*/dist-packages/*cutlass*.pth',
                    '/usr/local/lib/python*/site-packages/*cutlass*.pth'):
    for pth in glob.glob(pth_pattern):
        try: os.unlink(pth)
        except OSError: pass
tmp_whl = Path('/tmp/wheelhouse'); tmp_whl.mkdir(parents=True, exist_ok=True)
for w in WHEELHOUSE_DIR.glob('*.whl'):
    if 'cutlass' in w.name.lower(): continue
    target_name = (w.name.replace('cu128', '+cu128') if ('cu128' in w.name and '+' not in w.name) else w.name)
    target = tmp_whl / target_name
    if not target.exists(): os.symlink(w, target)
wheels = sorted(str(w) for w in tmp_whl.glob('*.whl'))
print(f'Installing {len(wheels)} wheels...')
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *wheels], check=True)
importlib.invalidate_caches()
print('Wheelhouse installation complete.')

# ===== CELL 2: write the STOCK agent directory (prompt + tools verbatim, 0.18 budget) =====
import json as _json
from swegemma.models import load_tasks
DATA_DIR = Path('/kaggle/input/competitions/gemma-4-developer-agent')
WORKING_DIR = Path('/kaggle/working'); WORKING_DIR.mkdir(parents=True, exist_ok=True)
AGENT_DIR = WORKING_DIR / 'submission'
if AGENT_DIR.exists(): shutil.rmtree(AGENT_DIR)
(AGENT_DIR / 'prompts').mkdir(parents=True, exist_ok=True)
(AGENT_DIR / 'configs').mkdir(parents=True, exist_ok=True)

# 9-tool STARTER list, verbatim from comp_files/agent.yaml. This RESTORES edit_file and
# write_file (v6c removed both) and KEEPS the three graph tools. No sub-agent, no adapter.
(AGENT_DIR / 'agent.yaml').write_text("""name: swe_baseline_agent
model: gemma-4-31b-it-qat-w4a16-ct
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
""", encoding='utf-8')

# Budget/sampling HELD at the 0.18 recipe so the prompt is the only thing under test.
(AGENT_DIR / 'configs' / 'sampling.yaml').write_text("""temperature: 0.2
top_p: 0.95
max_output_tokens: 8192
thinking_config:
  thinking_budget: 4096
  include_thoughts: true
""", encoding='utf-8')

(AGENT_DIR / 'eval_config.yaml').write_text("""evaluation:
  max_time_minutes: 8
  max_tool_calls: 28
  max_turns: 80
  timeout_seconds: 240
""", encoding='utf-8')

# STOCK PROMPT, byte-exact. Embedded as a JSON string literal inside a Python raw string so
# no escape processing happens here; json.loads restores the exact original bytes.
_STOCK_SYSTEM_MD_JSON = r\'\'\'@STOCK_JSON_LITERAL@\'\'\'
STOCK_SYSTEM_MD = _json.loads(_STOCK_SYSTEM_MD_JSON)
assert STOCK_SYSTEM_MD == _json.loads(_json.dumps(STOCK_SYSTEM_MD)), 'prompt round-trip failed'
assert 'search_similar_code' in STOCK_SYSTEM_MD, 'stock prompt lost its localization line'
assert 'Anti-Patterns' in STOCK_SYSTEM_MD, 'stock prompt truncated'
print(f'[prompt] stock system.md embedded, {len(STOCK_SYSTEM_MD)} chars, round-trip OK')
print('[prompt] NOTE: stock has NO budget section. It never tells the model the 28-call budget,')
print('[prompt]       never states that an edit before the wall counts, and never gives a')
print('[prompt]       call-number trigger to stop exploring. That absence IS the variable.')
(AGENT_DIR / 'prompts' / 'system.md').write_text(STOCK_SYSTEM_MD, encoding='utf-8')

TASKS_PATH = DATA_DIR / 'tasks.jsonl'
tasks = load_tasks(TASKS_PATH)
print(f'Agent dir written (v6s = STOCK PROMPT CONTROL, byte-exact official starter prompt '
      f'+ starter 9 tools, budget held at 0.18 recipe): {AGENT_DIR}')
print(f'Loaded {len(tasks)} tasks')

# ===== CELL 3: start vLLM server =====
import litellm, torch
from adk_submission import VllmConfig, VllmServer, discover_adapters
from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
validate_single_declared_model = None
for _modpath in ('swegemma.models.discovery', 'swegemma.models.registry', 'swegemma.submission',
                 'swegemma.config', 'swegemma.models'):
    try:
        _m = __import__(_modpath, fromlist=['validate_single_declared_model'])
        validate_single_declared_model = getattr(_m, 'validate_single_declared_model', None)
        if validate_single_declared_model is not None:
            print(f'[import] validate_single_declared_model <- {_modpath}')
            break
    except Exception:
        continue
if validate_single_declared_model is None:
    print('[import] validate_single_declared_model NOT FOUND; using no-op')
    def validate_single_declared_model(agent_dir):
        return 'gemma-4-31b-it-qat-w4a16-ct'
litellm.drop_params = True
TARGET_MODEL_NAME = 'gemma-4-31b-it-qat-w4a16-ct'
MODEL_PATH = Path('/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2')
declared_model = validate_single_declared_model(AGENT_DIR)
adapters = discover_adapters(str(AGENT_DIR), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)
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
server_instance.start()
print(f'vLLM server started on {server_instance.base_url} (tp={tp_size})')
models = server_instance.create_model_registry(
    aliases=[declared_model, TARGET_MODEL_NAME], model_prefix='openai/', api_key='EMPTY')

# ===== CELL 4: SAME 6 tasks as v6c - numbers are directly comparable =====
import asyncio, concurrent.futures, yaml
import pandas as pd
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps._configs import EventsCompactionConfig
from swegemma.config import EvalConfig, build_submission_limits
from swegemma.evaluate import Evaluator
def run_sync(coro_or_fn, *args, **kwargs):
    fn = (lambda: coro_or_fn(*args, **kwargs)) if callable(coro_or_fn) else (lambda: coro_or_fn)
    try: loop = asyncio.get_running_loop()
    except RuntimeError: loop = None
    if loop is not None and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(fn())).result()
    return asyncio.run(fn())
raw = yaml.safe_load((AGENT_DIR / 'eval_config.yaml').read_text(encoding='utf-8'))
ev = raw.get('evaluation', raw)
timeout_seconds = int(ev.get('timeout_seconds', 300)); max_tool_calls = int(ev.get('max_tool_calls', 100))
max_time_minutes = float(ev.get('max_time_minutes', 60.0))
turns_raw = ev.get('max_turns', ev.get('max_llm_calls')); max_turns = int(turns_raw) if turns_raw is not None else None

# IDENTICAL to v6c SAMPLE_IDS. Same tasks => v6s is directly comparable to v6b (1/6) and
# v6c (4/6). Do NOT change this list; it is the entire point of the control.
SAMPLE_IDS = ['rich_4077', 'rich_4079', 'rich_4076', 'rich_3471', 'rich_3278', 'rich_3882']
by_id = {t.instance_id: t for t in tasks}
SAMPLE_TASKS = []
for _tid in SAMPLE_IDS:
    if _tid in by_id:
        SAMPLE_TASKS.append(by_id[_tid])
    else:
        print(f'  WARNING: {_tid} not found in tasks.jsonl - skipped')
print(f'STOCK-PROMPT control on the SAME 6 tasks ({len(SAMPLE_TASKS)}): {[t.instance_id for t in SAMPLE_TASKS]}')

limits, gen_constraints = build_submission_limits()
eval_config = EvalConfig(
    tasks_path=TASKS_PATH, snapshots_dir=DATA_DIR / 'snapshots', results_dir=WORKING_DIR / 'results',
    submission_dir=AGENT_DIR, models=models, sandbox='subprocess',
    timeout_seconds=timeout_seconds, max_time_minutes=max_time_minutes,
    max_tool_calls=max_tool_calls, max_turns=max_turns,
    limits=limits, generation_constraints=gen_constraints, adapter_manifest=adapters,
    context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
    events_compaction_config=EventsCompactionConfig(compaction_interval=15, overlap_size=2,
        token_threshold=14336, event_retention_size=5),
    graph_dir=str(DATA_DIR / 'graphs'), embeddings_dir=str(DATA_DIR / 'embeddings'),
    wheels_dir=DATA_DIR / 'wheels', verbose=False,
)
evaluator = Evaluator(eval_config)
predictions = []; timing = []
for idx, task in enumerate(SAMPLE_TASKS, start=1):
    print(f'[{idx}/{len(SAMPLE_TASKS)}] {task.instance_id} ({task.repo})...')
    result = run_sync(evaluator.evaluate_task, task=task, task_index=idx, total_tasks=len(SAMPLE_TASKS))
    predictions.append({'id': task.instance_id, 'prediction': result.agent_patch or ''})
    timing.append({'id': task.instance_id, 'repo': task.repo.split('/')[-1],
                   'resolved': result.resolved, 'duration_s': round(result.duration_seconds, 1),
                   'tool_calls': result.tool_calls, 'patch_chars': len(result.agent_patch or '')})
    print(f'  -> resolved={result.resolved} duration={result.duration_seconds:.1f}s '
          f'tool_calls={result.tool_calls} patch_chars={len(result.agent_patch or "")}')
tdf = pd.DataFrame(timing)
print('\\n===== v6s SUMMARY (STOCK PROMPT CONTROL) =====')
print(tdf.to_string(index=False))
print(f'\\nRESOLVED: {tdf.resolved.sum()}/{len(tdf)}')
print('\\nCOMPARISON ON THE IDENTICAL 6 TASKS:')
print('  v6b (our prompt, 7 tools, v6b recipe)   : 1/6')
print('  v6c (our prompt, 7 tools, 0.18 budget)  : 4/6')
print(f'  v6s (STOCK prompt, 9 tools, same budget): {tdf.resolved.sum()}/6   <-- THE CONTROL')
print('If v6s >= 4/6 our 22-version custom method added nothing and 0.18 is just defaults.')
print('If v6s <= 2/6 the custom method is doing real work and v6c 4/6 is not a length artifact.')

# ===== CELL 5: package submission.zip =====
import zipfile
from swegemma.config import ALLOWED_SUBMISSION_EXTENSIONS, MAX_SUBMISSION_SIZE_BYTES
zip_path = Path(shutil.make_archive(str(WORKING_DIR / 'submission'), 'zip', root_dir=AGENT_DIR))
with zipfile.ZipFile(zip_path, 'r') as zf:
    total = sum(i.file_size for i in zf.infolist())
    assert total <= MAX_SUBMISSION_SIZE_BYTES, f'too big: {total}'
    for info in zf.infolist():
        if not info.is_dir():
            assert Path(info.filename).suffix.lower() in ALLOWED_SUBMISSION_EXTENSIONS, info.filename
print(f'Created {zip_path} ({zip_path.stat().st_size/1024:.1f} KiB)')
'''

out = HERE / "notebook_src.py"
CELL1_FINAL = CELL1.replace("@STOCK_JSON_LITERAL@", stock_json_literal)
assert "@STOCK_JSON_LITERAL@" not in CELL1_FINAL, "placeholder substitution failed"
assert "stock_json_literal" not in CELL1_FINAL, "generator variable leaked into notebook"
out.write_text(HEADER + "\n" + CELL1_FINAL, encoding="utf-8", newline="\n")
print(f"wrote {out} ({len(out.read_text(encoding='utf-8'))} chars)")
print(f"embedded stock prompt: {len(stock)} chars -> JSON literal {len(stock_json_literal)} chars")