# Gemma 4 Developer Agent — v15: SHORT-TRAJECTORY design (compaction-aware). RICH-FOCUSED.
#
# WHY (unifying finding, logged 2026-10-05 — measured from HARNESS_README 7.2 + wheel bytes + our runs):
#   TRAJECTORY LENGTH is the hidden lever. The scoring harness runs ADK EventsCompaction
#   (compaction_interval=5, token_threshold=14,336, event_retention_size=5): it compacts history every few
#   turns and keeps only ~5 recent events. PLUS the reasoning_content->reasoning fix is in the wheel but our
#   POST-fix runs still re-derive -> on LONG trajectories the model's own prior reasoning is DROPPED
#   (compaction, and/or the vLLM mirror not biting), so it re-reads/re-greps/re-derives and thrashes.
#   v14 (40 calls) data proves it: RESOLVED = rich_4077 (14 calls), rich_3718 (9 calls) = SHORT, inside the
#   retention window. FAILED = rich_4079 (22c), rich_4076 (38c), rich_4070 (33c) = LONG, crossed compaction.
#   => raising the budget was BACKWARDS. The win shape is a SHORT run that finishes before compaction.
#
# CHANGE-SET vs v14 (coherent, all aimed at ONE goal = keep the trajectory SHORT so reasoning stays coherent):
#   1. DROP the code_analyzer sub-agent entirely (single LlmAgent). The sub-agent is a separate context that
#      never compacts cleanly, burns the SHARED turn budget, and pushes the run LONG into the compaction
#      failure zone (v14 rich_4076: sub-agent ate all 40 turns, main agent had 0 left to edit).
#   2. LOW thinking_budget 512 -> 256 (just enough to plan the ONE edit; long reasoning gets compacted away =
#      wasted context). include_thoughts stays true (false would DISABLE generation entirely in 0.2.12).
#   3. TIGHT budget: max_tool_calls 40 -> 12, max_turns 60 -> 20 (turns > calls so turns don't guillotine
#      first). 5-min failsafe kept. 12 calls keeps the whole run near/inside the ~5-event retention window.
#   4. Prompt rewritten HARD around FINISH-SHORT: locate in <=3, edit by call ~4-5, verify once, submit —
#      target the whole task in UNDER ~6-8 calls. Anti-word-trap localization KEPT (validated on 31b).
#
# PRE-REGISTERED BAR (rule 2; judge = scored LB, our only trustworthy external judge):
#   - On the LB: beat v2's 0.10 anchor. v14's 40-call long-trajectory config is confirmed BACKWARDS; v15 is
#     the short-trajectory counter. The two clean resolves we DO get (4077/3718) were short — v15 makes ALL
#     tasks short, so the long-failers (4079/4076/3469) get the same short-trajectory conditions that worked.
#   - UNCERTAINTY (rule 9): short budget may cut off a genuinely hard multi-file task (rich_4070-class, out of
#     scope anyway). rich is 37% of public; owning it targets ~0.12 (top of pack), not a breakout.
#   - This is submitted directly (user call) — GPU quota is spent, so no pre-run; it is reasoned from the
#     compaction mechanism + the v14 short-vs-long split, not a fresh dev run. Logged as such.

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
# ROBUST wheelhouse resolver: the hardcoded /kaggle/input/datasets/... path can be WRONG depending on how
# the dataset mounts, which silently finds 0 wheels -> `pip install` with no args -> crash in Cell 1 (this
# is exactly what killed v15 version 1). Search known paths THEN glob /kaggle/input/** for the wheels, and
# HARD-ASSERT we found them so a 0-wheel mount fails LOUD instead of cryptically.
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
    f'dataset to this kernel. /kaggle/input has: {sorted(glob.glob("/kaggle/input/*"))}')
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

# ===== CELL 2: write OUR agent directory inline (v15 = SHORT-trajectory, NO sub-agent) =====
from swegemma.models import load_tasks
# ROBUST data-dir resolver (same lesson as the wheelhouse: hardcoded mount path was wrong -> FileNotFound
# on tasks.jsonl). Search known mount points THEN glob /kaggle/input/** for tasks.jsonl. HARD-ASSERT.
def _resolve_data_dir():
    cands = [
        '/kaggle/input/competitions/gemma-4-developer-agent',
        '/kaggle/input/gemma-4-developer-agent',
    ]
    for c in cands:
        if (Path(c) / 'tasks.jsonl').exists():
            return Path(c)
    hits = glob.glob('/kaggle/input/**/tasks.jsonl', recursive=True)
    if hits:
        return Path(hits[0]).parent
    raise FileNotFoundError(
        f'tasks.jsonl not found under /kaggle/input. Attach the gemma-4-developer-agent competition. '
        f'/kaggle/input has: {sorted(glob.glob("/kaggle/input/*"))}')
DATA_DIR = _resolve_data_dir()
print(f'[data] DATA_DIR = {DATA_DIR}')
WORKING_DIR = Path('/kaggle/working'); WORKING_DIR.mkdir(parents=True, exist_ok=True)
AGENT_DIR = WORKING_DIR / 'submission'
if AGENT_DIR.exists(): shutil.rmtree(AGENT_DIR)
(AGENT_DIR / 'prompts').mkdir(parents=True, exist_ok=True)
(AGENT_DIR / 'configs').mkdir(parents=True, exist_ok=True)

# v15 agent.yaml = SINGLE LlmAgent, NO sub-agent (the sub-agent pushed runs long -> compaction). NO adapter.
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

# v15 sampling: LOW thinking_budget 256 (in-window planning only; long reasoning gets compacted = wasted).
# include_thoughts TRUE (false would DISABLE generation entirely in adk_submission 0.2.12). temp 0.2 kept.
(AGENT_DIR / 'configs' / 'sampling.yaml').write_text('''temperature: 0.2
top_p: 0.95
max_output_tokens: 4096
thinking_config:
  thinking_budget: 256
  include_thoughts: true
''', encoding='utf-8')

# v15 eval_config: TIGHT. 12 tool calls / 20 turns (turns>calls so turns don't guillotine first) / 5-min
# failsafe. 12 calls keeps the whole run near the ~5-event compaction retention window -> reasoning coherent.
# v15 TUNE: ONE knob, max_tool_calls 12 -> 15. v15-at-12 data: rich_4077 WON at 11 (ceiling), rich_4079
# LOCALIZED to markdown.py by call 8 then guillotined at 12 before editing. 15 gives ~3 more calls to LAND
# the edit the agent already derived. 15 is the log's sweet spot (edge of the ~15-call decay zone, not past
# it). max_turns bumped to 24 so turns stay > calls (non-binding, not a second variable). max_time 5 -> 8:
# rich is NOT time-constrained and v15 max dur was ~2.3min, so this only removes time as a guillotine confound.
(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 8
  max_tool_calls: 15
  max_turns: 24
  timeout_seconds: 120
''', encoding='utf-8')

# v15 system.md = anti-word-trap localization (KEPT, validated) + HARD finish-short framing. No sub-agent refs.
(AGENT_DIR / 'prompts' / 'system.md').write_text('''You are an expert autonomous software engineer. You have a HARD budget of ~15 tool calls and 8 minutes. BE DECISIVE AND FAST. Your reasoning is NOT retained across many turns, so a SHORT run is a COHERENT run: FINISH THE WHOLE TASK IN UNDER ~8 TOOL CALLS. Long runs lose their own context and fail.

## The one rule that matters: LOCATE in <=3 calls, EDIT by call ~4, VERIFY once, SUBMIT.
Do NOT keep exploring. The moment you know the FILE and FUNCTION, edit. Re-reading a file already in your context is a BANNED, wasted call. A plausible edit submitted beats endless searching that loses coherence.

## LOCALIZE BY BEHAVIOR, NOT BY THE SYMPTOM WORD (the #1 cause of wrong fixes)
The problem is usually a 2-5 word SYMPTOM. The fix file is OFTEN NOT the file whose NAME matches that word; it is the code that PRODUCES the behavior.
- Do NOT assume "table"->table.py, "panel"->panel.py, "space"/"newline"->the obvious renderable. The word names the SYMPTOM; the fix is in whatever RENDERS or DECODES that output.
- Patterns: a spacing/alignment/"superfluous" symptom in rendered output is usually in the code that EMITS segments/lines (the markdown/console render path or cell-width math), not the high-level container. A "newline"/ANSI/escape symptom is usually in the DECODER that parses the text. A "proxy"/wrapper symptom is in the wrapper class that forwards calls.
- PROCEDURE: (1) name the exact OBSERVABLE behavior. (2) grep for the MECHANISM that emits it (the function building the line/segment/string, the decoder, the forwarding method), not the symptom noun. (3) confirm the behavior flows through the file before editing. (4) if the obvious file lacks the emitting code, follow the import/call to the module that does — the fix is frequently in a SMALLER, more specific module than the word suggests. If a test is named, trace the exact symbol/class it constructs to its DEFINING module and fix THERE.
- Cap localization at ~3 calls, then EDIT.

## Strategy: conform to the pattern
Most bugs are a DEVIATION from a pattern the surrounding code already follows. Make the buggy code look like its correct siblings (the function before/after it, or a similar function in the same file). Fix the exact deviation (wrong constant, missing guard/branch, wrong exception, off-by-one, wrong attr/arg, missing return) - nothing else.

## Workflow (tight — target: whole task done in under ~6-8 calls)
1. Read the problem. Name the observable behavior. Localize by BEHAVIOR (above). MAX ~3 locate calls.
2. edit_file the minimal fix. Match existing conventions/strings/types exactly. Keep old_string SMALL and unique (one line or a tight anchor) so it matches on the first try.
3. Verify with ONE targeted test (the test the problem names, or an obvious one). NEVER run bare pytest. Put any scratch in /tmp via run_command heredoc, NOT the repo.
4. submit_patch ONCE. The moment it returns "ok", STOP - one-line summary, no more tool calls.

## Hard rules
- NEVER modify/create/delete test files (test_*.py, *_test.py, tests/) or runner config (conftest.py, pytest.ini, pyproject.toml) - the harness resets them AND they poison your diff.
- write_file is JAILED to /workspace and rejects /tmp. Scratch -> run_command heredoc `cat > /tmp/x.py <<'EOF'`. edit_file ONLY for existing source files.
- Offline: no pip install. Do NOT refactor unrelated code. Do NOT run bare pytest. Do NOT conclude with an empty patch.
''', encoding='utf-8')

TASKS_PATH = DATA_DIR / 'tasks.jsonl'
tasks = load_tasks(TASKS_PATH)
print(f'Agent dir written (v15 = short-trajectory, NO sub-agent, thinking 256, budget 12): {AGENT_DIR}')
print(f'Loaded {len(tasks)} tasks')

# ===== CELL 3: start vLLM server (NO adapter) =====
import litellm, torch
from adk_submission import VllmConfig, VllmServer, discover_adapters
from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
# DEFENSIVE import: the server-side swegemma version drifts (v14 ran with
# swegemma.models.discovery; a later version moved it -> ModuleNotFoundError killed v15 v3). Try the
# known locations, else fall back to a no-op validator (it only enforces the single-model rule, which
# our agent.yaml satisfies by construction, so skipping it is safe).
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
    print('[import] validate_single_declared_model NOT FOUND in any known module; using no-op (single-model rule satisfied by agent.yaml)')
    def validate_single_declared_model(agent_dir):
        return 'gemma-4-31b-it-qat-w4a16-ct'
litellm.drop_params = True
TARGET_MODEL_NAME = 'gemma-4-31b-it-qat-w4a16-ct'
# ROBUST model-path resolver (same lesson): the hardcoded model mount path varies by case/version.
# Try known candidates THEN glob /kaggle/input/** for the w4a16 config.json. HARD-ASSERT.
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
        f'w4a16 model config.json not found under /kaggle/input. Attach the model. '
        f'/kaggle/input has: {sorted(glob.glob("/kaggle/input/*"))}')
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

# ===== CELL 4: RICH-FOCUSED RUN — rich sample; watch TRAJECTORY LENGTH (calls) vs resolve =====
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
print('\n===== v15 SUMMARY (SHORT-trajectory: no sub-agent, thinking 256, budget 12; watch calls stay LOW) =====')
print(tdf.to_string(index=False))
print(f'\nRICH RESOLVED: {int(tdf.resolved.sum())}/{len(tdf)}')
for iid in PRIORITY:
    row = tdf[tdf.id == iid]
    if len(row): print(f'  {iid}: resolved={bool(row.resolved.iloc[0])} calls={int(row.tool_calls.iloc[0])} chars={int(row.patch_chars.iloc[0])} dur={row.duration_s.iloc[0]}s')
print('Max tool_calls used:', int(tdf.tool_calls.max()), '(want LOW - short run = coherent run) | max dur:', round(tdf.duration_s.max()), 's')

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
