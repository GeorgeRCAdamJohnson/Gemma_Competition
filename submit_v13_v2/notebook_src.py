# Gemma 4 Developer Agent — v13 v2: v13 base (budget 18/5min) + ONE change: PATCH-HYGIENE discipline.
# RICH-FOCUSED.
#
# WHY (v13 dev-10 full trace, read task-by-task — this OVERTURNS "v13 is a null, revert"):
#   The model LOCALIZES CORRECTLY on ~8/10 and produced CORRECT, SELF-VERIFIED fixes that still scored 0
#   because of THREE MECHANICAL LEAKS, none of which is "wandering" or "budget too small":
#   1. PHANTOM PATCH (requests_7502): ONE correct edit on src/requests/models.py, repro PASSED, submitted at
#      call 15 with 3 to spare -> files_changed:3, patch_size:2247 -> resolved=False. The model itself flagged
#      "2247 chars for a one-line change?? files_changed:3 but I edited once." The 2 EXTRA files are the scratch
#      files the model wrote INTO THE REPO ROOT (test_getattr_wrapper.py, reproduce_issue.py). A test-looking
#      scratch file in the diff makes the patch fail to apply against the gold test_patch -> a CORRECT fix lost.
#      (Also rich_3469 "patch_size 414, I made no edits"; rich_4076 files_changed:2 for a 1-file edit.)
#   2. SANDBOX IMPORT SHADOW (requests_7315): repro imported the pip-installed `requests`, NOT /workspace/src,
#      so the model's CORRECT edit "didn't work" and it burned ~6 calls chasing a ghost before finding it needed
#      PYTHONPATH=/workspace/src. Model-agnostic; hits any repo with a src/ layout.
#   3. GUILLOTINE ON EDIT (4485/4487/14246): model KNEW the fix; edit_file -> BudgetExceeded. The edit must
#      happen BEFORE calls are spent on verification that may not fit.
#
# ASSUMED vs MEASURED (rule 9): the scratch-pollution CAUSE is inferred from the trace arithmetic
#   (1 edited + 2 repo-scratch = files_changed:3) + the model's own confusion; the swegemma patch-capture
#   source is wheelhouse-only and not readable locally, so this is a STRONG HYPOTHESIS, not a verified read.
#   The fix is safe either way: keeping scratch OUT of the repo can only help (if untracked files are captured
#   it removes pollution; if they are not, it costs nothing).
#
# THE CHANGE vs v13 (ONE variable — prompt ONLY; eval_config/budget/tools/sampling all IDENTICAL to v13):
#   A hard PATCH-HYGIENE block: (a) ALL scratch/repro/test files -> /tmp ONLY, NEVER the repo (edit_file only
#   touches the real source file); (b) run every repro with PYTHONPATH=<repo src> so you test LOCAL code;
#   (c) EDIT-BEFORE-YOU-VERIFY ordering: land the best-effort edit the moment you know the fix, THEN verify, so
#   a found fix is never guillotined; (d) a pre-submit self-check: your patch must touch ONLY the source
#   file(s) you intended — if git shows extra files, you leaked scratch into the repo.
#   Budget STAYS 18/5min on purpose: we are isolating whether the LEAKS (not the budget) caused v13's 0/10.
#
# PRE-REGISTERED BAR (rule 2; judge = hidden-set LB; dev-10 is MECHANISM-debug only):
#   - SUCCESS on dev-10: requests_7502 AND fastapi_14356 (both had CORRECT edits lost to pollution/cutoff) flip
#     to resolved=True, AND files_changed == the number of SOURCE files the model actually edited (no phantom
#     files, no test/scratch files in any diff). If the phantom files persist, the cause is NOT scratch -> the
#     hypothesis is FALSIFIED and reported as such (rule 3, honest null).
#   - NULL to beat on LB: v6 / 0.12 (SACRED). Do NOT auto-promote on dev-10; only the LB ranks.
#   - TUNE/NEXT: if hygiene flips the lost-but-correct tasks, THEN sweep budget (15/18/22) separately (rule 13).

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

# ===== CELL 2: write OUR agent directory inline (v13 v2 = v13 base + PATCH-HYGIENE prompt; NO adapter) =====
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

# v13 v2 agent.yaml = v13 (NO adapter). Same 9 tools, no sub-agent. IDENTICAL to v13.
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

# IDENTICAL to v13.
(AGENT_DIR / 'configs' / 'sampling.yaml').write_text('''temperature: 0.2
top_p: 0.95
max_output_tokens: 6144
thinking_config:
  thinking_budget: 512
  include_thoughts: true
''', encoding='utf-8')

# IDENTICAL to v13: budget 18/5min. We are isolating the LEAK fix, not changing the budget.
(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 5
  max_tool_calls: 18
  max_turns: 30
  timeout_seconds: 120
''', encoding='utf-8')

# v13 v2 system.md = v13 prompt + the PATCH-HYGIENE block (the ONE change). Everything else is v13 verbatim.
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

## PATCH HYGIENE - YOUR SCORE IS THE DIFF OF /workspace. KEEP IT CLEAN. (read this twice)
The grader scores the git diff of the repo working tree. ANY file you create inside the repo lands in that diff. A stray reproduce/test scratch file in your patch makes it FAIL TO APPLY against the hidden tests - so a CORRECT one-line fix scores ZERO. This is the #1 silent killer. Obey ALL of:
- NEVER create a scratch, reproduction, or test file inside the repo/workspace. ALL scratch goes in /tmp ONLY: `cat > /tmp/repro.py <<'EOF' ... EOF` then `python3 /tmp/repro.py`. NEVER `cat > reproduce.py` (that writes into the repo).
- edit_file is ONLY for the real SOURCE file(s) that contain the bug. Do not edit_file/write_file anything else.
- When you run a reproduction, IMPORT THE LOCAL CODE, not the installed package. Prefix EVERY repro with the repo source on the path, e.g. `PYTHONPATH=/workspace/src python3 /tmp/repro.py` (use /workspace if there is no src/). If a repro "shows the bug is still there" right after your edit, you are almost certainly importing the installed package - add PYTHONPATH and re-run ONCE, do not go hunting.
- BEFORE submit_patch, run `git -C /workspace status --porcelain` (or the repo root). The ONLY changed files must be the source file(s) you intended to fix. If you see a reproduce/test/scratch file, DELETE it from the repo (`rm /workspace/<file>`) before submitting. A clean, minimal diff is required.

## Fix then VERIFY — EDIT FIRST so a found fix is never lost to the budget
Land your fix BEFORE you spend calls verifying. The budget is tight and verification can run you out. Order:
1. The MOMENT you know file+function: edit_file. This is your floor - a plausible edit in the tree always beats a 0-char timeout.
2. THEN verify with ONE target test (the test the problem names, or the obvious test for the file). NEVER run bare pytest. Run it with PYTHONPATH set to the local source (see PATCH HYGIENE).
3. IF THE TARGET TEST FAILS, your fix is WRONG - do NOT just re-tweak: a red test means a NEW root-cause hypothesis (the fix often belongs in a sibling/helper file, or is a missing override). Change approach. But NEVER revert your edit to an empty tree - keep your best edit in place.
- submit_patch EXACTLY ONCE, after the test passes (or when stopping best-effort), AND after the git-status hygiene check. NEVER submit a patch that just failed; NEVER submit twice.

## Match the EXACT contract the problem describes (hidden tests check this)
When your fix changes a user-facing string, error message, exception type, status code, or validation, match the exact wording and every obvious variant:
- Use the problem statement's OWN vocabulary for messages (if it says data is "multi-line", assert it "must be a single line"; mirror the SIBLING check's shape and field interpolation). Tests often do `pytest.raises(..., match="exact phrase")`, so a paraphrase fails.
- INPUT VARIANTS: reject "\\n" AND "\\r" AND "\\r\\n" if you reject one; guard the whole class.
- Apply the change to EVERY field/branch the problem names, not just the first.

## Workflow (tight — target: edit by call 8, submit by call 14)
1. Read the problem. Extract the exact contract AND, if no file is named, the candidate SYMBOL. Vague symptom -> get_code_neighbors(symbol) FIRST; concrete token -> grep. MAX ~4 locate calls.
2. The moment you know file+function: edit_file. Match conventions/strings/types EXACTLY.
3. Verify with the ONE target test (scratch in /tmp, PYTHONPATH=local). If red, re-examine root cause (don't submit red; don't empty the tree). If near the wall, keep your best edit.
4. git-status hygiene check: only your source file(s) changed; delete any scratch that leaked into the repo.
5. submit_patch ONCE. The moment it returns "ok", STOP.

## Hard rules
- NEVER modify/create/delete test files (test_*.py, *_test.py, tests/) or runner config (conftest.py, pytest.ini, pyproject.toml) - the harness resets them AND they poison your diff.
- write_file is JAILED to /workspace and rejects /tmp. Scratch -> run_command heredoc `cat > /tmp/x.py <<'EOF'`. edit_file ONLY for existing source files.
- Offline: no pip install. Do NOT refactor unrelated code. Do NOT run bare pytest. Do NOT conclude with an empty patch.
''', encoding='utf-8')

TASKS_PATH = DATA_DIR / 'tasks.jsonl'
tasks = load_tasks(TASKS_PATH)
print(f'Agent dir written (v13 v2 = v13 base + patch-hygiene prompt, budget 18/5min, NO adapter): {AGENT_DIR}')
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
print(f'\n===== v13 v2 SUMMARY  [SERIAL]  (v13 base + PATCH-HYGIENE; budget 18/5min UNCHANGED) =====')
print('HYPOTHESIS: scratch/path/edit-order leaks (not budget) caused v13 0/10. Watch requests_7502 + fastapi_14356 flip; watch patch_chars shrink to a clean minimal diff.')
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
