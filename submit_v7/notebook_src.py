# Gemma 4 Developer Agent — v7 (TEXT-SEARCH-FIRST LOCALIZATION; branched from v6=0.12 LB anchor)
# v6 = v5 + contract-anchoring -> 0.12 public LB (up from v1 0.10). v6's remaining gap is TYPE A
#   underspecified-LOCALIZATION: the agent cannot find the bug site when no path is named (71% of tasks).
# INTEL + our verification (GEMMA_EXPERIMENT_LOG): the harness code-graph tools are near-useless for
#   localization — search_similar_code needs an EXACT dotted symbol id, free-text returns []. Plain
#   TEXT/TF-IDF matching of the problem statement's tokens vs the code finds the gold def in the top-10
#   ~33% of tasks (per-repo: requests 75%, rich 31%, fastapi 25%) — far better than the graph tools (~0%).
# v7 = v6 EXACTLY (tool_calls 22, temp 0.2, thinking 512, CONTRACT-ANCHORING kept) + ONE change:
#   LOCALIZATION workflow -> TEXT-SEARCH-FIRST. Extract concrete identifiers/error-strings from the
#   problem statement, GREP the repo for them as the PRIMARY locator; use the graph tools only to inspect
#   neighbors of a symbol already located. This attacks the Type-A localization gap that v6 left open.
# FREE NOTEBOOK RUN (6-task A/B) vs v6 baseline. Bar: v7 >= v6 (do not regress the 0.12 anchor's wins).

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

# ===== CELL 2: write OUR agent directory inline (v6 = v5 + contract-anchoring) =====
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

# v5 sampling EXACTLY (temp 0.2, thinking 512).
(AGENT_DIR / 'configs' / 'sampling.yaml').write_text('''temperature: 0.2
top_p: 0.95
max_output_tokens: 6144
thinking_config:
  thinking_budget: 512
  include_thoughts: true
''', encoding='utf-8')

# v5 eval_config EXACTLY (tool_calls 22 — the budget bump that recovered rich_4077).
(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 5
  max_tool_calls: 22
  max_turns: 40
  timeout_seconds: 120
''', encoding='utf-8')

# v7 system.md = v6 EXACTLY + ONE change: LOCALIZATION = text-search-first (the Type-A localization lever).
# Verified on our data: TF-IDF/text match of problem-statement tokens vs code finds the gold def in the
# top-10 ~33% of tasks; the graph tools (search_similar_code/get_code_neighbors) are near-useless for
# localization because search_similar_code needs an EXACT dotted symbol id (free-text returns nothing).
# So v7 steers the agent to GREP the codebase for the concrete identifiers/error-strings in the problem
# statement FIRST, and only use the graph tools once it already has an exact dotted symbol name.
(AGENT_DIR / 'prompts' / 'system.md').write_text('''You are an expert autonomous software engineer. You have a HARD budget of ~22 tool calls and 5 minutes. BE DECISIVE AND FAST.

## The one rule that matters: EDIT EARLY, DON'T EXPLORE.
You will run out of time if you keep searching. Spend AT MOST 3-4 tool calls locating the bug, then MAKE YOUR EDIT. One good minimal fix beats endless exploration. If unsure, make your best minimal change and submit - a plausible patch scores, endless searching scores nothing.

## Strategy: conform to the pattern
Most bugs are a DEVIATION from a pattern the surrounding code already follows. Make the buggy code look like its correct siblings (the function before/after it, or similar functions in the same file). Fix the exact deviation (wrong constant, missing guard/branch, wrong exception, off-by-one, wrong attr/arg, missing return) - nothing else.

## Match the EXACT contract the problem describes (this is what the hidden tests check)
The hidden test asserts a PRECISE observable contract, not just "the behavior is roughly right". When your fix introduces or changes a user-facing string, error message, exception type, status code, or validation, you MUST match the exact wording and cover every obvious input variant:
- ERROR / VALIDATION messages: use the exact phrasing the problem statement implies, and mirror the style of the SIBLING check already in the file (same message shape, same field-name interpolation). Do NOT invent your own wording - a test often does `pytest.raises(..., match="exact phrase")`, so a paraphrase FAILS even when the logic is right.
- INPUT VARIANTS: if you reject newlines, reject "\\n" AND "\\r" AND "\\r\\n". If you guard one special char, guard the whole obvious class. Tests parametrize across all of them.
- Apply the change to EVERY field/argument/branch the problem mentions, not just the first - if the problem says "id or event", fix BOTH, mirroring how an existing validated field is wired.
- A self-written test only counts as verification if it asserts the SAME exact string and the SAME variants the problem implies. If your test passes but only checks your own paraphrase, it proves nothing. Prefer asserting the behavior described in the problem's own words.

## Workflow (tight)
1. LOCATE BY TEXT SEARCH FIRST. Read the problem statement and extract its CONCRETE tokens: file/function/class names, the exact error or validation strings, unusual identifiers, config keys, decorator names. Then FIND them in the code:
   - If a file/path is named, read_file it directly.
   - Otherwise GREP the repo with run_command for those exact tokens, e.g. `grep -rn "exact error string" --include=*.py .` or `grep -rn "def the_function\\|class TheClass" --include=*.py .`. The problem statement's own words almost always appear in or next to the buggy code. This is your PRIMARY locator.
   - search_similar_code / get_code_neighbors only work when you ALREADY have an EXACT dotted symbol id (e.g. "fastapi.sse.ServerSentEvent"); they return nothing for free-text or short names, so do NOT rely on them to find an unknown bug - use them only to inspect neighbors of a symbol you have already located by grep/read.
   Also extract the exact contract (messages, variants, every field named). MAX 3-4 locate calls.
2. Make the minimal fix with edit_file (small edits only). Match existing conventions/strings/types EXACTLY, including the sibling's message style.
3. Call submit_patch ONCE. The moment it returns status "ok", you are DONE: write a one-sentence summary and make NO more tool calls. NEVER call submit_patch twice.

## Hard rules
- NEVER modify/create/delete test files (test_*.py, *_test.py, tests/) or runner config (conftest.py, pytest.ini, pyproject.toml) - the harness resets them; it pollutes your diff or auto-fails.
- write_file is JAILED to /workspace and rejects /tmp. For scratch, use run_command heredoc: `cat > /tmp/x.py <<'EOF'`. For a NEW repo file, use run_command heredoc to the real path. Use edit_file ONLY for existing files.
- Offline: no pip install. Do NOT refactor unrelated code. Do NOT run bare pytest (it times out) - if you test, run ONLY the one target test.
- Do NOT conclude without a non-empty patch.
''', encoding='utf-8')

# v5's analyzer.md VERBATIM.
(AGENT_DIR / 'prompts' / 'analyzer.md').write_text('''You are a fast code-analysis sub-agent. In a FEW targeted lookups (read_file, grep via run_command, get_code_neighbors), locate the buggy function and the SAME-MODULE sibling whose pattern the fix should match. Report: file path + line numbers; how the buggy code deviates from its siblings; the minimal change, INCLUDING the exact message/string style the sibling uses. Be fast - do not exhaustively explore.
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
print(f'Agent dir written (v6 = v5 + contract-anchoring): {AGENT_DIR}')
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

# ===== CELL 4: A/B RUN — SAME 6 tasks; bar = fastapi_15588 resolves (Type-B) AND >=2/6 with rich_4077 =====
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
print(f'A/B sample (same as v1/v3/v4/v5): {len(SAMPLE_TASKS)} tasks')
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
print('\n===== v6 A/B SUMMARY (v5=1/6; THE CHANGE: contract-anchoring; bar: fastapi_15588 resolves AND >=2/6) =====')
print(tdf.to_string(index=False))
print(f'\nRESOLVED: {tdf.resolved.sum()}/{len(tdf)}')
for key in ['4077','15588']:
    row = tdf[tdf.id.str.contains(key)]
    if len(row): print(f'  {row.id.iloc[0]}: resolved={bool(row.resolved.iloc[0])} (calls={int(row.tool_calls.iloc[0])}, chars={int(row.patch_chars.iloc[0])})')
print('Max tool_calls used:', int(tdf.tool_calls.max()), '| max dur:', round(tdf.duration_s.max()), 's (cap 300)')

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
