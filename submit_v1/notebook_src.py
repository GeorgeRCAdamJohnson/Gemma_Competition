# Gemma 4 Developer Agent — submission v1 (sibling-conformance, same-module-first)
# Based on the official getting-started flow (ryanholbrook/getting-started-gemma-4-developer-agent).
# This notebook: (1) installs the wheelhouse, (2) writes OUR agent dir inline,
# (3) runs a TIMING sample (rich + fastapi) printing per-task duration_seconds,
# (4) packages submission.zip with agent.yaml at root.

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

# ===== CELL 2: write OUR agent directory inline =====
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

# sampling.yaml — latency-tuned: thinking_budget and max_output_tokens cut for the slow 31B-INT4
(AGENT_DIR / 'configs' / 'sampling.yaml').write_text('''temperature: 0.2
top_p: 0.95
max_output_tokens: 6144
thinking_config:
  thinking_budget: 1024
  include_thoughts: true
''', encoding='utf-8')

(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 5
  max_tool_calls: 25
  max_turns: 40
  timeout_seconds: 120
''', encoding='utf-8')

(AGENT_DIR / 'prompts' / 'system.md').write_text('''You are an expert autonomous software engineer resolving an issue in a repository efficiently and decisively.

## Core strategy: conform to the pattern, don't invent
Most bugs are a DEVIATION from a pattern the surrounding code already follows. Find the correct pattern - usually in the same file or module - and make the buggy code conform to it. Prefer the minimal change that aligns the broken code with its working siblings. Resolve and submit in the fewest tool calls (under 8-10 turns).

## Workflow
1. LOCATE FAST: extract filenames, functions, classes, error messages, and tracebacks from the problem statement. Read ONLY the target files/lines. If no path is given, use search_similar_code with keywords from the error. Never run repo-wide find/grep.
2. FIND THE SIBLING (SAME MODULE FIRST): look at the function before and after the buggy one, and other functions/classes in the SAME file that do a similar job correctly - the fix usually makes the buggy code resemble these siblings. Use get_code_neighbors / get_code_subgraph for local convention. Only widen beyond the module if no same-module sibling exists; delegate heavy search to the code_analyzer sub-agent. Identify the exact DEVIATION (wrong constant, missing guard/branch, wrong exception, off-by-one, wrong attr/arg, missing return) and fix only that.
3. IMPLEMENT MINIMALLY: smallest change via edit_file (keep edits small to avoid truncation). Match existing conventions, error strings, exception types, status codes, signatures exactly.
4. VERIFY (targeted only) THEN SUBMIT: run ONLY the specific test for this bug (pytest path -k name). NEVER bare pytest or full-repo suites - they time out. Existing tests may be pre-broken; ignore unrelated failures, do not fix them. When your targeted test passes (or testing is impractical), clean up scratch files, then call submit_patch as your FINAL action. Verify patch_size > 0.

## Hard rules (violating these fails the task)
- NEVER modify/create/delete test files (test_*.py, *_test.py, under tests/) or runner config (conftest.py, pytest.ini, pyproject.toml). The harness resets them; editing pollutes the diff or auto-fails.
- Put scratch/repro scripts in /tmp (via run_command), NEVER in /workspace, or they leak into your patch.
- Offline environment: do NOT pip install or fetch packages.
- Do NOT refactor unrelated code. Do NOT conclude without a non-empty patch.
- Be FAST: one good conforming fix beats many iterations. If not converging quickly, submit your best minimal change rather than looping.
''', encoding='utf-8')

(AGENT_DIR / 'prompts' / 'analyzer.md').write_text('''You are a specialized code analysis sub-agent. Locate the buggy symbol and find sibling code - in the SAME module first - whose pattern the fix should conform to.

1. Locate the exact function/class/lines using read_file, get_code_neighbors, get_code_subgraph, search_similar_code.
2. SAME-MODULE SIBLINGS FIRST: find other functions/classes in the SAME file that do a similar job correctly. The fix often makes the buggy code look like its working siblings. Only widen if none exists.
3. Report concisely: exact file paths + line numbers; root cause as how the buggy code DEVIATES from its siblings' pattern; the sibling snippet to conform to (verbatim) if one exists; the recommended minimal change.
''', encoding='utf-8')

(AGENT_DIR / 'sub_agents' / 'code_analyzer.yaml').write_text('''name: code_analyzer_agent
description: Locates the buggy symbol and finds sibling code in the SAME module whose pattern the fix should conform to.
model: gemma-4-31b-it-qat-w4a16-ct
instruction: !include ../prompts/analyzer.md
tools:
  - read_file
  - search_similar_code
  - get_code_neighbors
  - get_code_subgraph
generate_content_config: !include ../configs/sampling.yaml
''', encoding='utf-8')

TASKS_PATH = DATA_DIR / 'tasks.jsonl'
tasks = load_tasks(TASKS_PATH)
print(f'Agent dir written: {AGENT_DIR}')
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

# ===== CELL 4: TIMING RUN — rich + fastapi sample, print per-task duration =====
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
timeout_seconds = int(ev.get('timeout_seconds', 300))
max_tool_calls = int(ev.get('max_tool_calls', 100))
max_time_minutes = float(ev.get('max_time_minutes', 60.0))
turns_raw = ev.get('max_turns', ev.get('max_llm_calls'))
max_turns = int(turns_raw) if turns_raw is not None else None

# TIMING SAMPLE: 4 rich (our target slice) + 2 fastapi (the slow/hard class) to measure both.
rich_tasks    = [t for t in tasks if t.repo.endswith('rich')][:4]
fastapi_tasks = [t for t in tasks if t.repo.endswith('fastapi')][:2]
SAMPLE_TASKS = rich_tasks + fastapi_tasks
print(f'Timing sample: {len(SAMPLE_TASKS)} tasks '
      f'({len(rich_tasks)} rich + {len(fastapi_tasks)} fastapi)')

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
print('\n===== TIMING SUMMARY (the budget measurement) =====')
print(tdf.to_string(index=False))
print('\nMean duration by repo:')
print(tdf.groupby('repo')['duration_s'].agg(['mean','max','count']).to_string())
print(f'\n>>> If fastapi mean >> rich mean, FastAPI is the budget killer. '
      f'129 tasks / 12h = 334s/task avg budget. <<<')

# ===== CELL 5: package submission.zip (agent.yaml at root) =====
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
