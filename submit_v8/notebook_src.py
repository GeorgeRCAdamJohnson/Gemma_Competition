# Gemma 4 Developer Agent — v8 (CONTRACT SELF-AUDIT; branched from v6=0.12 LB anchor)
# WHY v8 (evidence, not vibes): v7 (text-search-first) scored 2/6 on the 6-task A/B, same as v6, and its
#   Type-A target fastapi_15588 STILL failed. But the per-task TRACE (GEMMA_EXPERIMENT_LOG "v7 PER-TASK
#   TRACE CORRECTION") showed the miss is NOT localization: the agent grepped ServerSentEvent, found
#   fastapi/sse.py in 2 calls, read the sibling validator _check_id_no_null (an AfterValidator), then chose
#   a DIFFERENT shape (one model_validator), wrote a repro asserting ITS OWN invented message, saw it pass,
#   and submitted at 7/22 calls. Perfect localization + plausible fix + FALSE CONFIDENCE from a self-graded
#   test = the real resolution blocker is CONTRACT-EXACTNESS, not finding the bug.
# v6 ALREADY HAS a "match the exact contract" paragraph — and the agent still paraphrased. So the fix is
#   NOT another instruction; it is a PROCEDURAL pre-submit GATE that forces an ACTION the paraphrase cannot
#   survive. v8 = v6 EXACTLY (tool_calls 22, temp 0.2, thinking 512, contract-anchoring text kept) + ONE
#   change: a MANDATORY CONTRACT SELF-AUDIT run as the step right before submit_patch.
# FREE NOTEBOOK RUN (6-task A/B). Pre-registered bar: >=2/6 AND fastapi_15588 resolves (the exemplar the
#   audit is designed to convert). If 15588 still fails, read the trace — do NOT assume the idea is dead.

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

# ===== CELL 2: write OUR agent directory inline (v8 = v6 + contract self-audit) =====
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

# v6 sampling EXACTLY (temp 0.2, thinking 512).
(AGENT_DIR / 'configs' / 'sampling.yaml').write_text('''temperature: 0.2
top_p: 0.95
max_output_tokens: 6144
thinking_config:
  thinking_budget: 512
  include_thoughts: true
''', encoding='utf-8')

# v6 eval_config EXACTLY (tool_calls 22).
(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 5
  max_tool_calls: 22
  max_turns: 40
  timeout_seconds: 120
''', encoding='utf-8')

# v8 system.md = v6's prompt EXACTLY + ONE new change: a MANDATORY CONTRACT SELF-AUDIT step wired into the
# workflow right before submit_patch. v6 told the agent to "match the exact contract" but the agent still
# paraphrased (fastapi_15588: picked model_validator over the AfterValidator sibling, asserted its own
# message, self-graded test passed, submitted at 7/22). v8 turns that passive instruction into an ACTION
# the paraphrase cannot survive: before submitting, the agent must (a) write down the problem's literal
# contract tokens, (b) prefer the SIBLING validator's exact shape, and (c) grep its OWN diff for each
# literal token/variant and only submit once they are all present.
(AGENT_DIR / 'prompts' / 'system.md').write_text('''You are an expert autonomous software engineer. You have a HARD budget of ~22 tool calls and 5 minutes. BE DECISIVE AND FAST.

## The one rule that matters: EDIT EARLY, DON'T EXPLORE.
You will run out of time if you keep searching. Spend AT MOST 3-4 tool calls locating the bug, then MAKE YOUR EDIT. One good minimal fix beats endless exploration. If unsure, make your best minimal change and submit - a plausible patch scores, endless searching scores nothing.

## Strategy: conform to the pattern
Most bugs are a DEVIATION from a pattern the surrounding code already follows. Make the buggy code look like its correct siblings (the function before/after it, or similar functions in the same file). Fix the exact deviation (wrong constant, missing guard/branch, wrong exception, off-by-one, wrong attr/arg, missing return) - nothing else. When the file already has a validator/check/handler for a RELATED field, COPY ITS EXACT SHAPE (same decorator, same function form, same message style) rather than inventing a new mechanism - the hidden test expects the established shape.

## Match the EXACT contract the problem describes (this is what the hidden tests check)
The hidden test asserts a PRECISE observable contract, not just "the behavior is roughly right". When your fix introduces or changes a user-facing string, error message, exception type, status code, or validation, you MUST match the exact wording and cover every obvious input variant:
- ERROR / VALIDATION messages: use the exact phrasing the problem statement implies, and mirror the style of the SIBLING check already in the file (same message shape, same field-name interpolation). Do NOT invent your own wording - a test often does `pytest.raises(..., match="exact phrase")`, so a paraphrase FAILS even when the logic is right.
- INPUT VARIANTS: if you reject newlines, reject "\\n" AND "\\r" AND "\\r\\n". If you guard one special char, guard the whole obvious class. Tests parametrize across all of them.
- Apply the change to EVERY field/argument/branch the problem mentions, not just the first - if the problem says "id or event", fix BOTH, mirroring how an existing validated field is wired.
- A self-written test only counts as verification if it asserts the SAME exact string and the SAME variants the problem implies. If your test passes but only checks your own paraphrase, it proves nothing. Prefer asserting the behavior described in the problem's own words.

## Workflow (tight)
1. Read the problem statement. Extract the file/function/error AND the exact contract (messages, variants, every field named). Open the code with read_file (or `grep -n` via run_command if no path given). MAX 3-4 locate calls.
2. Make the minimal fix with edit_file (small edits only). Match existing conventions/strings/types EXACTLY, including the sibling's message style and SHAPE (if a sibling field uses an AfterValidator/a specific decorator, use the SAME one).
3. CONTRACT SELF-AUDIT - do this ONCE, right before submit_patch, it is NOT optional. In your thinking, list the LITERAL contract tokens the problem implies: (i) every field/argument it names, (ii) every exact quoted or clearly-implied message string, (iii) every input variant in the obvious class (e.g. \\n, \\r, \\r\\n for "newlines"; empty/None if relevant). Then run ONE command to inspect your own diff and check the tokens are actually there:
   `git diff` (or `git diff -U1`) - read your diff and confirm, token by token, that EVERY listed field is handled and EVERY literal message/variant appears. If a sibling validator exists for a related field, confirm your new code MIRRORS its shape (same decorator/function form), not a different mechanism.
   If any token is MISSING or your shape differs from the sibling's, FIX it with edit_file, then re-check. Only when every contract token is present in the diff do you submit. (This one audit is worth more than any extra exploration - it is the difference between a plausible patch and a passing one.)
4. Call submit_patch ONCE. The moment it returns status "ok", you are DONE: write a one-sentence summary and make NO more tool calls. NEVER call submit_patch twice.

## Hard rules
- NEVER modify/create/delete test files (test_*.py, *_test.py, tests/) or runner config (conftest.py, pytest.ini, pyproject.toml) - the harness resets them; it pollutes your diff or auto-fails.
- write_file is JAILED to /workspace and rejects /tmp. For scratch, use run_command heredoc: `cat > /tmp/x.py <<'EOF'`. For a NEW repo file, use run_command heredoc to the real path. Use edit_file ONLY for existing files.
- Offline: no pip install. Do NOT refactor unrelated code. Do NOT run bare pytest (it times out) - if you test, run ONLY the one target test.
- Do NOT conclude without a non-empty patch.
''', encoding='utf-8')

# v6's analyzer.md VERBATIM.
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
print(f'Agent dir written (v8 = v6 + contract self-audit): {AGENT_DIR}')
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

# ===== CELL 4: A/B RUN — SAME 6 tasks; bar = fastapi_15588 resolves AND >=2/6 (v8 contract self-audit) =====
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
print(f'A/B sample (same as v1/v3/v4/v5/v6/v7): {len(SAMPLE_TASKS)} tasks')
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
print('\n===== v8 A/B SUMMARY (v6=2/6; THE CHANGE: contract self-audit; bar: fastapi_15588 resolves AND >=2/6) =====')
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
