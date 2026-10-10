# Gemma 4 Developer Agent — v13 (v3): v12 base + BUDGET CUT to the INSTRUCTION-FOLLOWING WINDOW (18 calls / 5 min).
# RICH-FOCUSED. The structural embodiment of the "ADHD / ~15-call decay" insight.
#
# WHY (session findings, logged):
# - fastapi_14485 (v12 v2) LOCALIZED CORRECTLY at ~call 5 / 35s, then WANDERED 185s re-reading the same file 5x
#   and hunting symbols that don't exist, finally editing at call 30 / 275s = too late to verify -> wrong.
#   rich_4076 same shape (localized, wandered, hasty wrong edit). ONE DISEASE: post-localization WANDERING.
# - This = the ~15-call INSTRUCTION-DECAY cliff (research) + the "given a 40-call budget it dawdles to the
#   deadline" (user's ADHD model) — SAME phenomenon. The useful work happens in the first ~15 calls; the
#   budget PAST that is the decay zone where the agent ignores its own "don't re-read" rules and wanders.
# - v6 (our best scored, 0.12) ran a TIGHTER budget (22) and was forced to edit early. 40 gave room to wander.
# THE FIX (structural, not a prompt plea — prompts decay in exactly this zone): cap the budget so the WHOLE run
#   stays inside the instruction-following window. max_tool_calls 40 -> 18, max_time 6 -> 5 min. Forcing the
#   edit early also moves verification early (into the sharp zone), and cuts per-task time (helps the 129-run).
#
# CHANGE vs v12: ONLY the budget (eval_config 40->18 calls, 6->5 min; prompt budget line + a sharper
#   "stop locating once you have FILE+FUNCTION; first edit by ~call 8" rule). Retrieval-first + fix-loop +
#   contract rules all retained from v12 (localization works; don't touch it). No LoRA.
#
# PRE-REGISTERED BAR (judge = hidden-set LB from a blind submission; dev-10 sample is behavior-debug only):
#   - HYPOTHESIS: tighter budget prevents decay-zone wandering -> earlier edit -> earlier verification ->
#     higher resolve AND lower per-task time. On the dev-10, watch: do tasks now EDIT by ~call 8-10 (vs
#     call 20-30 in v12), and does rich_4076/rich_3469 convert?
#   - NULL to beat on LB: v6/0.12.
#   - TUNE: 18 is one point; the cap should be SWEPT (15/18/22) on the free Colab harness before concluding
#     which value peaks (rule 13 tune-before-concluding). 18 is the first probe, not the final answer.
#   - DO NOT auto-promote on dev-10 numbers; only the LB ranks. v6/0.12 sacred.

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
    print('[wheelhouse] Skipping install. If swegemma/vllm import fails below, ADD the '
          'gemma-4-developer-agent-wheelhouse dataset as an input to this session.')

# ===== CELL 2: write OUR agent directory inline (v13 = v12 base, budget cut to 18/5min; NO adapter) =====
from swegemma.models import load_tasks
def _resolve_input(candidates, sentinel):
    for c in candidates:
        if (Path(c) / sentinel).exists() or Path(c).is_dir() and sentinel == '':
            return Path(c)
    hits = glob.glob(f'/kaggle/input/**/{sentinel}', recursive=True) if sentinel else []
    if hits:
        return Path(hits[0]).parent
    raise FileNotFoundError(f'could not resolve input dir; tried {candidates} + glob for {sentinel!r}. '
                            f'/kaggle/input has: {sorted(glob.glob("/kaggle/input/*"))}')
DATA_DIR = _resolve_input([
    '/kaggle/input/competitions/gemma-4-developer-agent',
    '/kaggle/input/gemma-4-developer-agent',
], 'tasks.jsonl')
print(f'[data] DATA_DIR = {DATA_DIR}')
WORKING_DIR = Path('/kaggle/working'); WORKING_DIR.mkdir(parents=True, exist_ok=True)
AGENT_DIR = WORKING_DIR / 'submission'
if AGENT_DIR.exists(): shutil.rmtree(AGENT_DIR)
(AGENT_DIR / 'prompts').mkdir(parents=True, exist_ok=True)
(AGENT_DIR / 'configs').mkdir(parents=True, exist_ok=True)

# v13 agent.yaml = v12 (NO adapter). Same 9 tools, no sub-agent.
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
max_output_tokens: 6144
thinking_config:
  thinking_budget: 512
  include_thoughts: true
''', encoding='utf-8')

# v13 eval_config: THE CHANGE. Budget 40 -> 18 (stay inside the instruction-following window), time 6 -> 5 min.
# turns 60 -> 30 (so turns don't let it loop past the call cap). timeout unchanged.
(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 5
  max_tool_calls: 18
  max_turns: 30
  timeout_seconds: 120
''', encoding='utf-8')

# v13 system.md = v12 prompt + TIGHTER budget framing + a sharp STOP-LOCATING rule (edit by ~call 8).
(AGENT_DIR / 'prompts' / 'system.md').write_text('''You are an expert autonomous software engineer. You have a HARD budget of ~18 tool calls and 5 minutes. BE DECISIVE AND FAST. Your instruction-following DEGRADES the longer you go, so FINISH INSIDE THE FIRST ~15 ACTIONS - the budget is tight ON PURPOSE.

## The one rule that matters: LOCATE, then EDIT by call ~8. DO NOT KEEP SEARCHING.
You find the right file FAST and then waste the rest of your budget re-reading it. STOP doing that. The moment you know the FILE and the FUNCTION that contain the bug, you are DONE LOCATING - make your edit. Do NOT read another file, do NOT re-grep, do NOT re-read a file you have already read. Target: first edit_file by call 8. Re-reading something already in your context is a BANNED, wasted call.

## Localize by MEANING first when the problem is a vague symptom
Many problems are a short symptom with NO file named (e.g. "preserve newlines", "fix superfluous space", "proxy isatty"). Plain `grep` of the symptom words often FAILS because the fix lives in code that doesn't contain those words. For a vague symptom:
1. Extract the concrete CODE IDENTIFIER the symptom implies - a class/function/module SYMBOL name, not the English phrase.
2. Prefer `get_code_neighbors(symbol)` (it fuzzy-resolves names: exact->suffix->case-insensitive->substring) to jump to a definition. `search_similar_code` needs a near-exact node key, so if it returns 0 results ONCE, do NOT retry it with another guessed name - switch to grep for a concrete token you have actually seen.
3. Fall back to `grep -nE` for concrete tokens.
Use retrieval first on vague symptoms; use grep for concrete tokens. But cap LOCATING at ~4 calls total - then EDIT.

## Do NOT waste tool calls (you have only ~18 - every wasted one is a fix you don't get to make)
- BATCH searches: ONE `grep -nE 'a|b|c' file.py`, not one grep per symbol.
- NEVER repeat a search that returned nothing; NEVER repeat a tool call that returned the SAME error.
- NEVER re-read a file (or region) you have already read - it is in your context. Re-reading is the #1 way runs die.
- After 2 unproductive searches, STOP and open the single most likely file; a guessed edit beats a 0-char timeout.

## Strategy: conform to the pattern
Most bugs are a DEVIATION from a pattern the surrounding code already follows. Make the buggy code look like its correct siblings. Fix the exact deviation (wrong constant, missing guard/branch, wrong exception, off-by-one, wrong attr/arg, missing return) - nothing else.

## Fix then VERIFY — the test is the judge, and the CLOCK is real
You edit early (by ~call 8), which leaves budget to VERIFY. Obey:
- After your edit, RUN ONLY THE ONE TARGET TEST (the test the problem names, or the obvious test for the file). NEVER run bare pytest.
- IF THE TARGET TEST FAILS, your fix is WRONG - do NOT submit it. A red test means your HYPOTHESIS is wrong: read the failure, form a NEW root-cause hypothesis (the fix often belongs in a sibling/helper file, or is a missing override), and change approach - do not just re-tweak the same edit.
- TIME-AWARE STOP: if you are near the call budget OR the time wall without a green test, make your single best-effort edit and STOP - leave it in the working tree (a plausible patch is recovered and scored; a timeout with no edit scores nothing). NEVER let the clock run out with an empty working tree.
- submit_patch EXACTLY ONCE, after the test passes (or when stopping best-effort). NEVER submit a patch that just failed; NEVER submit twice.

## Match the EXACT contract the problem describes (hidden tests check this)
When your fix changes a user-facing string, error message, exception type, status code, or validation, match the exact wording and every obvious variant:
- Use the problem statement's OWN vocabulary for messages (if it says data is "multi-line", assert it "must be a single line"; mirror the SIBLING check's shape and field interpolation). Tests often do `pytest.raises(..., match="exact phrase")`, so a paraphrase fails.
- INPUT VARIANTS: reject "\\n" AND "\\r" AND "\\r\\n" if you reject one; guard the whole class.
- Apply the change to EVERY field/branch the problem names, not just the first.

## Workflow (tight — target: edit by call 8, submit by call 14)
1. Read the problem. Extract the exact contract AND, if no file is named, the candidate SYMBOL. Vague symptom -> get_code_neighbors(symbol) FIRST; concrete token -> grep. MAX ~4 locate calls.
2. The moment you know file+function: edit_file. Match conventions/strings/types EXACTLY.
3. Run the ONE target test. If red, re-examine root cause (don't submit red). If near the wall, submit best-effort.
4. submit_patch ONCE. The moment it returns "ok", STOP.

## Hard rules
- NEVER modify/create/delete test files (test_*.py, *_test.py, tests/) or runner config (conftest.py, pytest.ini, pyproject.toml) - the harness resets them.
- write_file is JAILED to /workspace and rejects /tmp. Scratch -> run_command heredoc `cat > /tmp/x.py <<'EOF'`. edit_file ONLY for existing files.
- Offline: no pip install. Do NOT refactor unrelated code. Do NOT run bare pytest. Do NOT conclude with an empty patch.
''', encoding='utf-8')

TASKS_PATH = DATA_DIR / 'tasks.jsonl'
tasks = load_tasks(TASKS_PATH)
print(f'Agent dir written (v13 = v12 base, budget 40->18 / 6->5min, NO adapter): {AGENT_DIR}')
print(f'Loaded {len(tasks)} tasks')

# ===== CELL 3: start vLLM server (NO adapter) =====
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

# ===== CELL 4: SERIAL run — representative 10 (rich-weighted read; TIME-TO-FIRST-EDIT tracked) =====
import asyncio, concurrent.futures, yaml
import pandas as pd
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps._configs import EventsCompactionConfig
from swegemma.config import EvalConfig, build_submission_limits
from swegemma.evaluate import Evaluator
import logging
for _n in ('swegemma.sandbox.subprocess', 'asyncio', 'LiteLLM', 'litellm'):
    logging.getLogger(_n).setLevel(logging.CRITICAL)
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
REPR_SAMPLE_IDS = [
    "rich_4077", "rich_4079", "rich_4076", "rich_3469",
    "fastapi_14485", "fastapi_14487", "fastapi_14246", "fastapi_14356",
    "requests_7315", "requests_7502",
]
RICH_IDS = ["rich_4077", "rich_4079", "rich_4076", "rich_3469"]
by_iid = {t.instance_id: t for t in tasks}
SAMPLE_TASKS = [by_iid[i] for i in REPR_SAMPLE_IDS if i in by_iid]
missing = [i for i in REPR_SAMPLE_IDS if i not in by_iid]
print(f'Representative sample: {len(SAMPLE_TASKS)}/{len(REPR_SAMPLE_IDS)} tasks (missing: {missing})')
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
def score_one(task, idx, total):
    r = run_sync(evaluator.evaluate_task, task=task, task_index=idx, total_tasks=total)
    return {'id': task.instance_id, 'repo': task.repo.split('/')[-1],
            'resolved': bool(r.resolved), 'duration_s': round(r.duration_seconds, 1),
            'tool_calls': r.tool_calls, 'patch_chars': len(r.agent_patch or '')}
import time as _time
t_start = _time.time()
rows = []
for i, t in enumerate(SAMPLE_TASKS):
    print(f'[serial {i+1}/{len(SAMPLE_TASKS)}] {t.instance_id} ...', flush=True)
    row = score_one(t, i + 1, len(SAMPLE_TASKS))
    rows.append(row)
    print(f'  [done] {t.instance_id}: resolved={row["resolved"]} '
          f'dur={row["duration_s"]}s calls={row["tool_calls"]} chars={row["patch_chars"]}', flush=True)
wall = _time.time() - t_start
print(f'[serial] wall time {wall:.0f}s for {len(SAMPLE_TASKS)} tasks', flush=True)

tdf = pd.DataFrame(rows)
print(f'\n===== v13 SUMMARY  [SERIAL]  (v12 base + budget 18/5min; stay in instruction-following window) =====')
print('HYPOTHESIS: tight budget stops decay-zone wandering -> earlier edit, fewer calls, lower dur. Watch calls/dur drop vs v12.')
print(tdf.to_string(index=False))
print(f'\nRESOLVED: {tdf.resolved.sum()}/{len(tdf)}  ({100*tdf.resolved.mean():.0f}%)')
print('by repo:', tdf.groupby('repo')['resolved'].agg(['sum', 'count']).to_dict('index'))
_rich = tdf[tdf.id.isin(RICH_IDS)]
print(f'RICH: {int(_rich.resolved.sum())}/{len(_rich)}')
for iid in RICH_IDS:
    row = tdf[tdf.id == iid]
    if len(row): print(f'  rich {iid}: resolved={bool(row.resolved.iloc[0])} calls={int(row.tool_calls.iloc[0])} chars={int(row.patch_chars.iloc[0])} dur={row.duration_s.iloc[0]}s')
print(f'Max tool_calls used: {int(tdf.tool_calls.max())} (cap 18) | mean dur: {round(tdf.duration_s.mean())}s | max dur: {round(tdf.duration_s.max())}s (cap 300)')

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
