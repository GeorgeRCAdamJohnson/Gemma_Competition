# Gemma 4 Developer Agent — v12 (REVISED): v10 base (budget 40, NO LoRA) + retrieval-first localization + time-aware fix-loop.
# RICH-FOCUSED. Attacks the two rich 0-char localization fails (rich_4076, rich_3469) that budget alone cannot touch.
#
# WHY THIS SHAPE (evidence from the session, logged in GEMMA_EXPERIMENT_LOG):
# - LoRA REMOVED: the localizer adapter was net-negative (regressed v10's wins; wrong lever — localization
#   SPEED was never the bottleneck). v12 rebases on the v10 agent (budget 40, no adapter).
# - RETRIEVAL-FIRST (the rich lever): across the ENTIRE v10 run the agent used search_similar_code /
#   get_code_neighbors / get_code_subgraph ZERO times — pure grep+read thrash (121 greps, 108 reads). The two
#   rich misses are signal-poor symptoms ("preserve newlines" -> gold in rich/ansi.py decode(); "fix superfluous
#   space" -> a one-token guard in rich/markdown.py) that keyword grep STRUCTURALLY cannot reach. Semantic/graph
#   retrieval is the right tool and was ignored. HARNESS caveat: search_similar_code resolves a SYMBOL NAME
#   against node keys (offline), NOT a free-form sentence — querying with prose returns garbage. So the prompt
#   teaches: extract a candidate SYMBOL/CLASS/MODULE name and query THAT.
# - TIME-AWARE FIX-LOOP: the binding wall is TIME (committed env mean ~273s/task; boundary tasks pin ~300s).
#   The harness AUTO-RECOVERS an unsubmitted working-tree diff on timeout, so banking a best-effort patch
#   before the wall strictly dominates timing out at 0 chars. Also: never ship a patch that just failed its
#   test, never double-submit, don't lock into the first fix hypothesis (v11 traces showed all three).
# - FASTAPI: explicitly NOT the focus (needs a LoRA / extra logic, deferred). v12 must stay fastapi-NEUTRAL —
#   the retrieval + fix-loop rules are generic skills, so they should not HARM fastapi (and may incidentally help).
#
# CONFIG (locked with user): max_tool_calls 40, max_time_minutes 6 (360s), max_turns 60, timeout 120.
#   360s is runtime-safe: committed-env mean ~273s * 129 ~= 9.8h, worst-plausible ~300s mean ~= 10.75h, both
#   under the ~12h grader wall (fast finishers create headroom; cap only rescues boundary tasks).
#
# PRE-REGISTERED BAR (judge = the hidden-set LB score from a BLIND submission; the 10-task dev sample does NOT
#   predict the LB and is for behavior-debugging only):
#   - NULL to beat: v6/0.12 (the standing scored best).
#   - PRIMARY SIGNAL (rich): the trace shows a search_similar_code/get_code_neighbors call that surfaces the
#     gold file on a vague-symptom task, converting a prior 0-char rich fail.
#   - DO NOT auto-promote on dev-sample numbers; only the LB decides. v6/0.12 stays sacred until the LB beats it.

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

# ===== CELL 2: write OUR agent directory inline (v12 = v10 agent, NO adapter; prompt upgraded) =====
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
    '/kaggle/input/competitions/gemma-4-developer-agent',   # batch/scoring
    '/kaggle/input/gemma-4-developer-agent',                 # interactive Draft Session
], 'tasks.jsonl')
print(f'[data] DATA_DIR = {DATA_DIR}')
WORKING_DIR = Path('/kaggle/working'); WORKING_DIR.mkdir(parents=True, exist_ok=True)
AGENT_DIR = WORKING_DIR / 'submission'
if AGENT_DIR.exists(): shutil.rmtree(AGENT_DIR)
(AGENT_DIR / 'prompts').mkdir(parents=True, exist_ok=True)
(AGENT_DIR / 'configs').mkdir(parents=True, exist_ok=True)

# v12 agent.yaml = v10 (NO adapter line). Same 9 tools, no sub-agent.
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

# sampling: v6/v10 (temp 0.2, thinking 512).
(AGENT_DIR / 'configs' / 'sampling.yaml').write_text('''temperature: 0.2
top_p: 0.95
max_output_tokens: 6144
thinking_config:
  thinking_budget: 512
  include_thoughts: true
''', encoding='utf-8')

# eval_config: budget 40, TIME 6 min (360s), turns 60, timeout 120. (locked with user)
(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 6
  max_tool_calls: 40
  max_turns: 60
  timeout_seconds: 120
''', encoding='utf-8')

# v12 system.md = v10 prompt + (1) RETRIEVAL-FIRST on vague symptoms, (2) TIME-AWARE FIX-LOOP.
(AGENT_DIR / 'prompts' / 'system.md').write_text('''You are an expert autonomous software engineer. You have a HARD budget of ~40 tool calls and 6 minutes. BE DECISIVE AND FAST.

## The one rule that matters: EDIT EARLY, DON'T EXPLORE.
You will run out of time if you keep searching. Spend AT MOST 3-5 tool calls locating the bug, then MAKE YOUR EDIT. One good minimal fix beats endless exploration. If unsure, make your best minimal change and submit - a plausible patch scores, endless searching scores nothing.

## Localize by MEANING first when the problem is a vague symptom (THIS is how you find the right file fast)
Many problem statements are a short symptom with NO file named (e.g. "preserve newlines", "fix superfluous space", "proxy isatty"). Plain `grep` of the symptom words usually FAILS for these, because the fix lives in code whose text does not contain the symptom words. For a vague symptom, do this BEFORE grep:
1. Extract the concrete CODE IDENTIFIER the symptom implies - a class, function, or module SYMBOL name, not the English phrase. ("preserve newlines" in a renderer -> the decode/render path, e.g. a `decode`/`render` method or an `*Decoder` class; "superfluous space" in markdown -> the markdown render/segment path.)
2. Call `search_similar_code` with that SYMBOL NAME (NOT a sentence) - it matches node keys/suffixes offline, so pass `AnsiDecoder` or `decode` or `__rich_console__`, never "preserve newlines in code blocks". Then `get_code_neighbors` on the surfaced symbol to jump to its definition and callers.
3. Only fall back to `grep -nE` once you have a concrete symbol or filename to search for.
Semantic/graph retrieval reaches files that keyword grep cannot. Use it first on vague symptoms; use grep for concrete tokens.

## Do NOT waste tool calls
- BATCH searches: ONE `grep -nE 'a|b|c' file.py`, not one grep per symbol.
- NEVER repeat a search that already returned nothing, and NEVER repeat a tool call that returned the SAME error (fix the arguments it names, or switch tools; looping the same failing call burns the whole budget).
- After 2 unproductive searches, STOP searching and open the single most likely file; guessing an edit beats a 0-char timeout.
- Reading the same file region twice is a wasted call. Read once, remember it.

## Strategy: conform to the pattern
Most bugs are a DEVIATION from a pattern the surrounding code already follows. Make the buggy code look like its correct siblings. Fix the exact deviation (wrong constant, missing guard/branch, wrong exception, off-by-one, wrong attr/arg, missing return) - nothing else.

## Fix then VERIFY — the test is the judge, and the CLOCK is real
Locating the right file is half the job; the hidden test decides the fix. BUT you have a hard ~6-minute wall. Obey:
- After your edit, RUN ONLY THE ONE TARGET TEST (the test the problem names, or the obvious test for the file you changed). NEVER run bare pytest (it times out).
- IF THE TARGET TEST FAILS, your fix is WRONG - do NOT submit it. A red test is not "the test is buggy"; it means your HYPOTHESIS is wrong. Read the failure, form a NEW root-cause hypothesis, and change approach (the fix often belongs in a sibling/helper file, or is a missing override, not the line you first touched). Do not just re-tweak the same edit.
- TIME-AWARE STOP: if you are near the call budget OR near the time wall and do NOT yet have a green test, make your single best-effort edit and STOP - leave the edit in the working tree. A plausible patch left in place is recovered and scored; a timeout with no edit scores nothing. NEVER let the clock run out with an empty working tree.
- submit_patch EXACTLY ONCE, after the target test passes (or when you are stopping best-effort). NEVER submit a patch that just failed its test. NEVER submit the same patch twice - once submitted, you are DONE.

## Match the EXACT contract the problem describes (hidden tests check this)
When your fix introduces/changes a user-facing string, error message, exception type, status code, or validation, match the exact wording and cover every obvious variant:
- Use the problem statement's OWN vocabulary for messages (if it says data is "multi-line", assert it "must be a single line" - mirror the problem's adjective/noun; do NOT invent "must not contain newlines"). Mirror the SIBLING check's message shape and field interpolation. Tests often do `pytest.raises(..., match="exact phrase")`, so a paraphrase fails.
- INPUT VARIANTS: reject "\\n" AND "\\r" AND "\\r\\n" if you reject one; guard the whole obvious class.
- Apply the change to EVERY field/branch the problem names, not just the first.

## Workflow (tight)
1. Read the problem. Extract the exact contract AND, if no file is named, the candidate SYMBOL to retrieve on. Vague symptom -> search_similar_code(symbol) + get_code_neighbors FIRST; concrete token -> grep. MAX 3-5 locate calls.
2. Make the minimal fix with edit_file. Match conventions/strings/types EXACTLY.
3. Run the ONE target test. If red, re-examine root cause (don't submit a red patch). If near the wall, submit best-effort.
4. submit_patch ONCE. The moment it returns "ok", STOP.

## Hard rules
- NEVER modify/create/delete test files (test_*.py, *_test.py, tests/) or runner config (conftest.py, pytest.ini, pyproject.toml) - the harness resets them.
- write_file is JAILED to /workspace and rejects /tmp. Scratch -> run_command heredoc `cat > /tmp/x.py <<'EOF'`. edit_file ONLY for existing files.
- Offline: no pip install. Do NOT refactor unrelated code. Do NOT run bare pytest. Do NOT conclude with an empty patch.
''', encoding='utf-8')

TASKS_PATH = DATA_DIR / 'tasks.jsonl'
tasks = load_tasks(TASKS_PATH)
print(f'Agent dir written (v12 REVISED = v10 base + retrieval-first + time-aware fix-loop, NO adapter): {AGENT_DIR}')
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

# ===== CELL 4: SERIAL run — representative 10 (rich-weighted read) =====
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
print(f'\n===== v12 SUMMARY  [SERIAL]  (REVISED: v10 base + retrieval-first + time-aware fix-loop, NO adapter) =====')
print('RICH-FOCUSED. Watch: do rich_4076 / rich_3469 (prior 0-char fails) now reach a non-empty patch, and does')
print('the trace show a search_similar_code / get_code_neighbors call surfacing the gold file?')
print(tdf.to_string(index=False))
print(f'\nRESOLVED: {tdf.resolved.sum()}/{len(tdf)}  ({100*tdf.resolved.mean():.0f}%)')
print('by repo:', tdf.groupby('repo')['resolved'].agg(['sum', 'count']).to_dict('index'))
_rich = tdf[tdf.id.isin(RICH_IDS)]
print(f'RICH: {int(_rich.resolved.sum())}/{len(_rich)}')
for iid in RICH_IDS:
    row = tdf[tdf.id == iid]
    if len(row): print(f'  rich {iid}: resolved={bool(row.resolved.iloc[0])} calls={int(row.tool_calls.iloc[0])} chars={int(row.patch_chars.iloc[0])}')
print(f'Max tool_calls used: {int(tdf.tool_calls.max())} (cap 40) | max dur: {round(tdf.duration_s.max())}s (cap 360)')

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
