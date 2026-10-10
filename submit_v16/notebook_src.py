# Gemma 4 Developer Agent — v16: v15 base + EDIT-RESERVE + ANTI-LOOP (budget 15). RICH-FOCUSED.
#
# WHY (v15-at-12 run, rich sample, measured):
#   - rich_4077 WON (resolved, 11/12 calls) — but at the ceiling, after wasting calls 3-9 poking io.TextIOBase
#     internals though it KNEW the fix at call 2.
#   - rich_4079 LOCALIZED CORRECTLY to markdown.py by call 8 (anti-word-trap rule WORKS on the 31b), then got
#     GUILLOTINED at call 12 before it could edit. 0-char patch.
#   - rich_4076/3469 ran out of calls mid-localization. rich_4070 (9-file refactor) guillotined mid-edit.
#   => TWO diseases, both must be fixed TOGETHER: (A) 12 calls is too few to LAND the edit the agent derives;
#      (B) the agent OVER-INVESTIGATES before editing (wastes the budget it does have). Raising budget alone
#      (A) risks tipping into the ~15-call instruction-decay/LOOP zone the log repeatedly documents (re-reads
#      same file, repeats searches). So v16 raises budget to 15 AND adds hard EDIT-EARLY + RESERVE-TAIL +
#      ANTI-LOOP rules so the extra calls are spent LANDING the fix, not wandering into the decay zone.
#
# CHANGE-SET vs v15 (budget + 3 prompt rules; localization-by-behavior / thinking 256 / no sub-agent KEPT):
#   1. max_tool_calls 12 -> 15 (reach + land the edit; 15 is the log's edge-of-decay sweet spot, not past it).
#      max_turns 20 -> 24 (turns > calls, non-binding). max_time 5 -> 8 (rich is NOT time-constrained;
#      v15 max dur ~2.3min, so time is removed as a guillotine confound, NOT a behavior change).
#   2. EDIT-EARLY: "make your first edit_file by call 6 — the moment you know file+function, EDIT your best
#      hypothesis; do NOT keep investigating to be sure." (kills the 4077 calls-3-9-poking waste.)
#   3. RESERVE-TAIL: "NEVER spend your last 3 calls on read/grep — they are for edit -> verify -> submit."
#      (guarantees the derived fix LANDS; kills the 4079 guillotine.)
#   4. ANTI-LOOP: "NEVER re-read a file already in your context, NEVER repeat a search that returned the same
#      thing — re-reading is the #1 way runs die." (the log's ~15-call decay/loop guard.)
#
# PRE-REGISTERED BAR (rule 2; judge = rich resolves then LB; v6/0.12 sacred):
#   - rich_4077 stays True; rich_4079 FLIPS to True (it localized right, just needed to land the edit).
#   - >= 2/6 rich resolved on the sample = the budget+reserve fix works -> candidate to submit.
#   - WATCH (user's warning): if a task that would resolve now LOOPS in calls 10-15 instead of editing, 15
#     tipped into the decay zone -> the anti-loop rule failed and we revert to 13.

# ===== CELL 1: environment + wheelhouse (robust resolver) =====
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
    '/kaggle/input/metric/gemma-4-developer-agent-wheelhouse',
]
_wheel_src = next((p for p in _WHEEL_HINTS if Path(p).is_dir() and list(Path(p).glob('*.whl'))), None)
if _wheel_src is None:
    _found = glob.glob('/kaggle/input/**/*.whl', recursive=True)
    _wheel_src = str(Path(_found[0]).parent) if _found else None
print(f'[wheelhouse] source dir: {_wheel_src}')
assert _wheel_src is not None, (
    'WHEELHOUSE NOT FOUND under /kaggle/input. Attach the metric/gemma-4-developer-agent-wheelhouse '
    f'dataset. /kaggle/input has: {sorted(glob.glob("/kaggle/input/*"))}')
WHEELHOUSE_DIR = Path(_wheel_src)
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
    if not target.exists():
        try: os.symlink(w, target)
        except FileExistsError: pass
wheels = sorted(str(w) for w in tmp_whl.glob('*.whl'))
print(f'Installing {len(wheels)} wheels...')
assert wheels, f'0 wheels resolved from {WHEELHOUSE_DIR} - aborting before empty pip install'
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *wheels], check=True)
importlib.invalidate_caches()
print('Wheelhouse installation complete.')

# ===== CELL 2: write OUR agent directory inline (v16 = v15 + edit-reserve + anti-loop) =====
from swegemma.models import load_tasks
def _resolve_data_dir():
    cands = ['/kaggle/input/competitions/gemma-4-developer-agent', '/kaggle/input/gemma-4-developer-agent']
    for c in cands:
        if (Path(c) / 'tasks.jsonl').exists():
            return Path(c)
    hits = glob.glob('/kaggle/input/**/tasks.jsonl', recursive=True)
    if hits:
        return Path(hits[0]).parent
    raise FileNotFoundError(
        f'tasks.jsonl not found under /kaggle/input. /kaggle/input has: {sorted(glob.glob("/kaggle/input/*"))}')
DATA_DIR = _resolve_data_dir()
print(f'[data] DATA_DIR = {DATA_DIR}')
WORKING_DIR = Path('/kaggle/working'); WORKING_DIR.mkdir(parents=True, exist_ok=True)
AGENT_DIR = WORKING_DIR / 'submission'
if AGENT_DIR.exists(): shutil.rmtree(AGENT_DIR)
(AGENT_DIR / 'prompts').mkdir(parents=True, exist_ok=True)
(AGENT_DIR / 'configs').mkdir(parents=True, exist_ok=True)

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
generate_content_config: !include configs/sampling.yaml
''', encoding='utf-8')

(AGENT_DIR / 'configs' / 'sampling.yaml').write_text('''temperature: 0.2
top_p: 0.95
max_output_tokens: 4096
thinking_config:
  thinking_budget: 256
  include_thoughts: true
''', encoding='utf-8')

# v16 eval_config: budget 15 (reach+land the edit), 24 turns (non-binding), 8 min (time not a confound for rich).
(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 8
  max_tool_calls: 15
  max_turns: 24
  timeout_seconds: 120
''', encoding='utf-8')

# v16 system.md = v15 anti-word-trap localization + EDIT-EARLY + RESERVE-TAIL + ANTI-LOOP.
(AGENT_DIR / 'prompts' / 'system.md').write_text('''You are an expert autonomous software engineer. You have a HARD budget of ~15 tool calls and 8 minutes. BE DECISIVE. Your reasoning is NOT retained across many turns, so a SHORT, FORWARD-MOVING run is a COHERENT run. Every call must make NEW progress - never repeat yourself.

## THE RULE THAT DECIDES EVERYTHING: EDIT EARLY, THEN RESERVE THE TAIL.
- Make your FIRST edit_file by call 6 at the latest. The moment you know the FILE and the FUNCTION, EDIT your best hypothesis - do NOT keep investigating to be 100% sure. A landed edit you can refine beats a perfect plan you never get to type.
- RESERVE your last 3 calls for edit -> verify -> submit. NEVER spend calls 13-15 on read/grep. If you are at call 12 and have not edited, edit NOW with your best guess.
- A derived fix that never gets typed scores ZERO. Landing the edit is the whole game.

## ANTI-LOOP (the #1 way runs die): NEVER repeat yourself.
- NEVER re-read a file (or region) you have already read - it is in your context. Scroll your memory, do not re-fetch.
- NEVER repeat a search/grep that returned the same result (or nothing). If a search was empty, try a DIFFERENT query, do not re-run it.
- If you catch yourself about to do something you already did, STOP and edit instead.

## LOCALIZE BY BEHAVIOR, NOT BY THE SYMPTOM WORD (the #1 cause of WRONG fixes)
The problem is usually a 2-5 word SYMPTOM. The fix file is OFTEN NOT the file whose NAME matches that word; it is the code that PRODUCES the behavior.
- Do NOT assume "table"->table.py, "panel"->panel.py, "space"/"newline"->the obvious renderable. The word names the SYMPTOM; the fix is in whatever RENDERS or DECODES that output.
- Patterns: a spacing/alignment/"superfluous" symptom in rendered output is usually in the code that EMITS segments/lines (the markdown/console render path or cell-width math), not the high-level container. A "newline"/ANSI/escape symptom is usually in the DECODER that parses the text. A "proxy"/wrapper symptom is in the wrapper class that forwards calls. "inline" markdown/table issues live in markdown.py, not table.py.
- PROCEDURE: (1) name the exact OBSERVABLE behavior. (2) grep ONCE for the MECHANISM that emits it (the function building the line/segment/string, the decoder, the forwarding method), not the symptom noun. (3) open the one most-likely file. (4) EDIT. If a test is named, trace the symbol/class it constructs to its DEFINING module and fix THERE.
- Cap localization at ~4 calls. Then EDIT.

## Strategy: conform to the pattern
Most bugs are a DEVIATION from a pattern the surrounding code already follows. Make the buggy code look like its correct siblings (the function before/after it, or a similar function in the same file). Fix the exact deviation (wrong constant, missing guard/branch, wrong exception, off-by-one, wrong attr/arg, missing return) - nothing else.

## Workflow (edit by call 6, submit by call ~12)
1. Read the problem. Name the observable behavior. Localize by BEHAVIOR (above). MAX ~4 locate calls - no repeats.
2. edit_file the minimal fix by call 6. Keep old_string SMALL and unique (one line / tight anchor) so it matches first try.
3. Verify with ONE targeted test (the test the problem names, or an obvious one). NEVER run bare pytest. Scratch in /tmp via run_command heredoc, NOT the repo.
4. submit_patch ONCE. The moment it returns "ok", STOP - one-line summary, no more tool calls.

## Hard rules
- NEVER modify/create/delete test files (test_*.py, *_test.py, tests/) or runner config (conftest.py, pytest.ini, pyproject.toml) - the harness resets them AND they poison your diff.
- write_file is JAILED to /workspace and rejects /tmp. Scratch -> run_command heredoc `cat > /tmp/x.py <<'EOF'`. edit_file ONLY for existing source files.
- Offline: no pip install. Do NOT refactor unrelated code. Do NOT run bare pytest. Do NOT conclude with an empty patch.
''', encoding='utf-8')

TASKS_PATH = DATA_DIR / 'tasks.jsonl'
tasks = load_tasks(TASKS_PATH)
print(f'Agent dir written (v16 = v15 + edit-reserve + anti-loop, budget 15): {AGENT_DIR}')
print(f'Loaded {len(tasks)} tasks')

# ===== CELL 3: start vLLM server (robust model resolver + defensive validator import) =====
import litellm, torch
from adk_submission import VllmConfig, VllmServer, discover_adapters
from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
# DEFENSIVE import: server-side swegemma version drifts (discovery module moved). Try known locations, else no-op.
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
    print('[import] validate_single_declared_model NOT FOUND; using no-op (single-model rule satisfied by agent.yaml)')
    def validate_single_declared_model(agent_dir):
        return 'gemma-4-31b-it-qat-w4a16-ct'
litellm.drop_params = True
TARGET_MODEL_NAME = 'gemma-4-31b-it-qat-w4a16-ct'
def _resolve_model():
    cands = [
        '/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2',
        '/kaggle/input/models/google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2',
        '/kaggle/input/gemma-4-31b-it-qat-w4a16-ct',
    ]
    for c in cands:
        if Path(c, 'config.json').exists():
            return Path(c)
    hits = glob.glob('/kaggle/input/**/gemma-4-31b-it-qat-w4a16-ct/**/config.json', recursive=True)
    if not hits:
        hits = glob.glob('/kaggle/input/**/config.json', recursive=True)
    if hits:
        return Path(sorted(hits, key=len)[0]).parent
    raise FileNotFoundError(
        f'w4a16 model config.json not found under /kaggle/input. /kaggle/input has: {sorted(glob.glob("/kaggle/input/*"))}')
MODEL_PATH = _resolve_model()
print(f'[model] MODEL_PATH = {MODEL_PATH}')
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

# ===== CELL 4: RICH-FOCUSED RUN — rich sample; watch EDIT-BY-CALL-6 + no loops =====
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
PRIORITY = ["rich_4077", "rich_4079", "rich_4076", "rich_3469"]
by_iid = {t.instance_id: t for t in tasks}
rich_all = [t for t in tasks if t.repo.endswith('rich')]
priority_tasks = [by_iid[i] for i in PRIORITY if i in by_iid]
rest_rich = [t for t in rich_all if t.instance_id not in set(PRIORITY)][:6]
SAMPLE_TASKS = priority_tasks + rest_rich
print(f'RICH sample: {len(SAMPLE_TASKS)} tasks ({len(priority_tasks)} word-trap exemplars + {len(rest_rich)} more rich)')
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
timing = []
for idx, task in enumerate(SAMPLE_TASKS, start=1):
    print(f'[{idx}/{len(SAMPLE_TASKS)}] {task.instance_id} ({task.repo})...', flush=True)
    result = run_sync(evaluator.evaluate_task, task=task, task_index=idx, total_tasks=len(SAMPLE_TASKS))
    timing.append({'id': task.instance_id, 'repo': task.repo.split('/')[-1],
                   'resolved': bool(result.resolved), 'duration_s': round(result.duration_seconds, 1),
                   'tool_calls': result.tool_calls, 'patch_chars': len(result.agent_patch or '')})
    print(f'  -> resolved={result.resolved} duration={result.duration_seconds:.1f}s '
          f'tool_calls={result.tool_calls} patch_chars={len(result.agent_patch or "")}', flush=True)
tdf = pd.DataFrame(timing)
print('\n===== v16 SUMMARY (v15 + edit-reserve + anti-loop, budget 15; bar: rich_4077 stays, rich_4079 flips, >=2/6) =====')
print(tdf.to_string(index=False))
print(f'\nRICH RESOLVED: {int(tdf.resolved.sum())}/{len(tdf)}')
for iid in PRIORITY:
    row = tdf[tdf.id == iid]
    if len(row): print(f'  {iid}: resolved={bool(row.resolved.iloc[0])} calls={int(row.tool_calls.iloc[0])} chars={int(row.patch_chars.iloc[0])} dur={row.duration_s.iloc[0]}s')
print('Max tool_calls used:', int(tdf.tool_calls.max()), '(want edits landing by ~12, not 15) | max dur:', round(tdf.duration_s.max()), 's')

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
