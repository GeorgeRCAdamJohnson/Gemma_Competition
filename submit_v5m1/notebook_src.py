# v5m1 (A: SURGICAL EDITS) = v5 + smallest-unique old_string anchoring. Kills the edit-retry
# thrash (fastapi_15588 burned 4+ calls on 'old_string not found'). Helps ALL repos. One lever vs v5.
# CORRECTED DIAGNOSIS from v4's full trace: the bottleneck is the TOOL-CALL budget, not the method.
# v4 on rich_4077 LOCALIZED PERFECTLY and derived the exact gold fix (add FileProxy.isatty forwarding),
# then hit BudgetExceeded on the edit at call 15 — it ran out of CALLS one step before applying the fix.
# Every v4 rich task hit exactly 15 calls; max duration 214s vs the 300s cap => ~90s/task UNUSED clock.
# TIME is not the constraint; the 15-call ceiling is. v5 = v3's EXACT known-good config with ONE change:
#   max_tool_calls 15 -> 22 (spend the time headroom on calls so the model can APPLY the fix it finds).
# v3's prompt restored VERBATIM (the "commit-fast localization" wording in the earlier v5 draft targeted
# a wandering problem the data does NOT show; it is dropped). temp 0.2, thinking 512 unchanged from v3.
# FREE NOTEBOOK RUN (6-task A/B). Bar: rich_4077 resolves AND >=2/6 before any scored submission.

# ===== CELL 1: environment + wheelhouse =====
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

# ===== CELL 2: write OUR agent directory inline (v5m1 (A: surgical edits)) =====
from swegemma.models import load_tasks
DATA_DIR = Path('/kaggle/input/competitions/gemma-4-developer-agent')
WORKING_DIR = Path('/kaggle/working'); WORKING_DIR.mkdir(parents=True, exist_ok=True)
AGENT_DIR = WORKING_DIR / 'submission'
if AGENT_DIR.exists(): shutil.rmtree(AGENT_DIR)
(AGENT_DIR / 'prompts').mkdir(parents=True, exist_ok=True)
(AGENT_DIR / 'configs').mkdir(parents=True, exist_ok=True)
(AGENT_DIR / 'sub_agents').mkdir(parents=True, exist_ok=True)

(AGENT_DIR / 'agent.yaml').write_text('''name: sibling_conform_agent
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
  - agent_tool:
      config_path: sub_agents/code_analyzer.yaml
      skip_summarization: true
generate_content_config: !include configs/sampling.yaml
''', encoding='utf-8')

# v3 sampling EXACTLY (temp 0.2, thinking 512).
(AGENT_DIR / 'configs' / 'sampling.yaml').write_text('''temperature: 0.2
top_p: 0.95
max_output_tokens: 6144
thinking_config:
  thinking_budget: 512
  include_thoughts: true
''', encoding='utf-8')

# THE ONE CHANGE: max_tool_calls 15 -> 22. max_time_minutes 5 kept as the real failsafe (v4 max dur 214s
# << 300s, so 22 calls at the observed ~10-14s/call stays well under the 5min wall). max_turns bumped
# proportionally 30 -> 40 so turns don't become the new artificial ceiling.
(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 5
  max_tool_calls: 22
  max_turns: 40
  timeout_seconds: 120
''', encoding='utf-8')

# v3's system.md VERBATIM (budget number updated 15 -> 22 to match eval_config; otherwise unchanged).
(AGENT_DIR / 'prompts' / 'system.md').write_text('''You are an expert autonomous software engineer. You have a HARD budget of ~22 tool calls and 5 minutes. BE DECISIVE AND FAST.

## The one rule that matters: EDIT EARLY, DON'T EXPLORE.
You will run out of time if you keep searching. Spend AT MOST 3-4 tool calls locating the bug, then MAKE YOUR EDIT. One good minimal fix beats endless exploration. If unsure, make your best minimal change and submit - a plausible patch scores, endless searching scores nothing.

## Strategy: conform to the pattern
Most bugs are a DEVIATION from a pattern the surrounding code already follows. Make the buggy code look like its correct siblings (the function before/after it, or similar functions in the same file). Fix the exact deviation (wrong constant, missing guard/branch, wrong exception, off-by-one, wrong attr/arg, missing return) - nothing else.

## Make SURGICAL edits (smallest unique anchor)
When you call edit_file, do NOT paste a big multi-line block as old_string - large blocks frequently fail to match (whitespace, quotes, escaped chars like \n or \0) and waste your budget on retries. Instead: pick the SMALLEST UNIQUE snippet that identifies the spot (often a single line, or a signature/field-name anchor), and make the change around it. If a change spans several lines, do it as SEVERAL small edit_file calls, each with a tiny unique old_string, rather than one large replacement. Copy old_string VERBATIM from what read_file showed, exactly as-is.

## Workflow (tight)
1. Read the problem statement. Extract the file/function/error. Open it with read_file (or `grep -n` via run_command if no path given). MAX 3-4 locate calls.
2. Make the minimal fix with edit_file (small edits only). Match existing conventions/strings/types exactly.
3. Call submit_patch ONCE. The moment it returns status "ok", you are DONE: write a one-sentence summary and make NO more tool calls. NEVER call submit_patch twice.

## Hard rules
- NEVER modify/create/delete test files (test_*.py, *_test.py, tests/) or runner config (conftest.py, pytest.ini, pyproject.toml) - the harness resets them; it pollutes your diff or auto-fails.
- write_file is JAILED to /workspace and rejects /tmp. For scratch, use run_command heredoc: `cat > /tmp/x.py <<'EOF'`. For a NEW repo file, use run_command heredoc to the real path. Use edit_file ONLY for existing files.
- Offline: no pip install. Do NOT refactor unrelated code. Do NOT run bare pytest (it times out) - if you test, run ONLY the one target test.
- Do NOT conclude without a non-empty patch.
''', encoding='utf-8')

# v3's analyzer.md VERBATIM.
(AGENT_DIR / 'prompts' / 'analyzer.md').write_text('''You are a fast code-analysis sub-agent. In a FEW targeted lookups (read_file, grep via run_command, get_code_neighbors), locate the buggy function and the SAME-MODULE sibling whose pattern the fix should match. Report: file path + line numbers; how the buggy code deviates from its siblings; the minimal change. Be fast - do not exhaustively explore.
''', encoding='utf-8')

(AGENT_DIR / 'sub_agents' / 'code_analyzer.yaml').write_text('''name: code_analyzer_agent
description: Quickly locates the buggy symbol and its same-module sibling pattern.
model: gemma-4-31b-it-qat-w4a16-ct
instruction: !include ../prompts/analyzer.md
tools:
  - read_file
  - run_command
  - search_similar_code
  - get_code_neighbors
  - get_code_subgraph
generate_content_config: !include ../configs/sampling.yaml
''', encoding='utf-8')

TASKS_PATH = DATA_DIR / 'tasks.jsonl'
tasks = load_tasks(TASKS_PATH)
print(f'Agent dir written (v5m1 (A: surgical edits)): {AGENT_DIR}')
print(f'Loaded {len(tasks)} tasks')

# ===== CELL 3: start vLLM server =====
import litellm, torch
from adk_submission import VllmConfig, VllmServer, discover_adapters
from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
from swegemma.models.discovery import validate_single_declared_model
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

# ===== CELL 4: A/B RUN — SAME 6 tasks; bar = rich_4077 resolves AND >=2/6 =====
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
rich_tasks    = [t for t in tasks if t.repo.endswith('rich')][:4]
fastapi_tasks = [t for t in tasks if t.repo.endswith('fastapi')][:2]
SAMPLE_TASKS = rich_tasks + fastapi_tasks
print(f'A/B sample (same as v1/v3/v4): {len(SAMPLE_TASKS)} tasks')
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
print('\n===== v5m1 (A) A/B SUMMARY (v3=1/6, v4=0/6; THE CHANGE: tool_calls 15->22; bar: rich_4077 back AND >=2/6) =====')
print(tdf.to_string(index=False))
print(f'\nRESOLVED: {tdf.resolved.sum()}/{len(tdf)}')
r4077 = tdf[tdf.id.str.contains('4077')]
if len(r4077): print(f'rich_4077 recovered: {bool(r4077.resolved.iloc[0])}  (calls={int(r4077.tool_calls.iloc[0])})')
print('Mean/max duration by repo (watch max vs 300s cap - 22 calls must still finish under 5min):')
print(tdf.groupby('repo')['duration_s'].agg(['mean','max','count']).to_string())
print('Max tool_calls used:', int(tdf.tool_calls.max()), '(if <22, budget is no longer the binding limit)')

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
