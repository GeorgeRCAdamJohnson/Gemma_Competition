# Gemma 4 Developer Agent — v4 (TEMP 0 + LOCALIZATION push + L1 prose rewrite; keep v3 speed config)
# v1 (tool_calls 25) resolved 1/6 -> scored 0.10. v3 (tool_calls 15, thinking 512) resolved 1/6, zero timeouts, rich mean 124s.
# v4 changes (one coherent change-set aimed at the proven LOCALIZATION gap + a measured plumbing win):
#   (a) temperature 0.2 -> 0 (greedy; deterministic; competitor signal "tune temp down"; exact-string fixes).
#   (b) L1: system.md has NO literal shell/tool-call examples -> described in prose. g4kit measured
#       literal shell examples -> 31% malformed tool-name emissions vs 5% as prose bound to run_command.
#   (c) LOCALIZATION push: the failing test names a class/symbol; trace it to the file that DEFINES that
#       class and edit the method THERE (not where it is merely referenced). This is the exact gap that
#       made rich_4077 miss locally (edited console.py annotation instead of adding FileProxy.isatty).
# This is a FREE NOTEBOOK RUN (6-task A/B) + packages submission.zip. NOT scored. Bar: resolve >=2/6.

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

# ===== CELL 2: write OUR agent directory inline (v4) =====
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

# v4: temperature 0 (greedy, deterministic, exact-form precision for hidden-string checks).
#     thinking_budget 512 kept from v3 (fast; more turns fit under the 5min wall).
(AGENT_DIR / 'configs' / 'sampling.yaml').write_text('''temperature: 0.0
top_p: 0.95
max_output_tokens: 6144
thinking_config:
  thinking_budget: 512
  include_thoughts: true
''', encoding='utf-8')

# v4: eval_config unchanged from v3 (tool_calls 15, 5min cap -> zero timeouts, rich mean 124s).
(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 5
  max_tool_calls: 15
  max_turns: 30
  timeout_seconds: 120
''', encoding='utf-8')

# v4 system.md:
#  - L1: NO literal shell/tool-call examples (prose only) -> fewer malformed tool-name emissions.
#  - LOCALIZATION push: trace the failing symbol/class to the file that DEFINES it; edit THAT class.
#  - keep v3 speed discipline (edit early, submit once, stop).
(AGENT_DIR / 'prompts' / 'system.md').write_text('''You are an expert autonomous software engineer. You have a HARD budget of about 15 tool calls and 5 minutes. Be decisive and fast.

## The one rule that matters: EDIT EARLY, DON'T EXPLORE.
You will run out of time if you keep searching. Spend at most three or four tool calls locating the bug, then make your edit. One good minimal fix beats endless exploration. If unsure, make your best minimal change and submit: a plausible patch scores, endless searching scores nothing.

## Localize to the DEFINITION, not the reference.
The problem statement and the failing test name a class, function, or attribute. Your fix almost always belongs in the file that DEFINES that class or function, not in a file that merely uses or references it. Before editing, confirm you are in the defining module. If the test constructs an object of some class and calls a method on it, the fix is a change to THAT class in its defining file. Trace the named symbol to its definition first, then edit there.

Use the code-intelligence tools to jump from a symbol to its definition and its relationships rather than reading files blindly: ask for a symbol's neighbors to find where it is defined, who calls it, and its siblings. Search for a symbol by name to find semantically similar functions and classes.

## Strategy: conform to the pattern.
Most bugs are a deviation from a pattern the surrounding code already follows. Make the buggy code look like its correct siblings: a similar method on the same class, or a neighboring function in the same file that already does the right thing. If one field or method is validated or forwarded correctly and a parallel one is not, make the broken one match the working one. Fix the exact deviation only: a wrong constant, a missing guard or branch, a wrong exception, an off-by-one, a wrong attribute or argument, a missing return or a missing forwarding method.

## Workflow (tight)
1. Read the problem statement and the failing test. Identify the named class, function, or attribute. Find the file that defines it and open it, using the code-intelligence tools to go symbol-to-definition rather than guessing. Keep this to three or four locate calls.
2. Make the minimal fix with edit_file. The old_string must be an exact snippet copied verbatim from the file, appearing once; the new_string must change program behavior, not merely reformat. Match the file's existing conventions, strings, and types exactly.
3. Call submit_patch once. The moment it returns a success status, you are done: write a one-sentence summary and make no more tool calls. Never call submit_patch twice.

## Hard rules
- Never modify, create, or delete test files or runner configuration such as conftest or the pytest or project config: the harness resets them, and touching them pollutes your diff or fails the task.
- Do not write reproduction scripts and do not try to reproduce the bug before fixing it: that burns the entire budget. Go straight from reading the defining code to editing it.
- The environment is offline, so do not attempt to install or download anything. Do not refactor unrelated code. Do not run the full test suite, as it will time out; if you must check something, exercise only the single most relevant piece of code.
- Do not conclude without a non-empty patch.
''', encoding='utf-8')

(AGENT_DIR / 'prompts' / 'analyzer.md').write_text('''You are a fast code-analysis sub-agent. In a few targeted lookups, locate the file that DEFINES the buggy class or function named in the problem, and the same-module sibling whose pattern the fix should match. Prefer the code-intelligence tools to jump from a symbol to its definition and neighbors rather than reading files blindly. Report: the defining file path and line numbers; how the buggy code deviates from its correct sibling; and the single minimal change. Be fast and do not exhaustively explore.
''', encoding='utf-8')

(AGENT_DIR / 'sub_agents' / 'code_analyzer.yaml').write_text('''name: code_analyzer_agent
description: Quickly locates the file that defines the buggy symbol and its same-module sibling pattern.
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
print(f'Agent dir written (v4 temp0 + localization): {AGENT_DIR}')
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

# ===== CELL 4: A/B RUN — SAME 6 tasks (v1=1/6, v3=1/6); bar = resolve >=2 =====
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
print(f'A/B sample (same as v1/v3): {len(SAMPLE_TASKS)} tasks')
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
print('\n===== v4 A/B SUMMARY (v1=1/6, v3=1/6; bar >=2/6) =====')
print(tdf.to_string(index=False))
print(f'\nRESOLVED: {tdf.resolved.sum()}/{len(tdf)}  (bar: >=2/6 to beat v1/v3; >=1 to match)')
print('Mean duration by repo:')
print(tdf.groupby('repo')['duration_s'].agg(['mean','max','count']).to_string())

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
