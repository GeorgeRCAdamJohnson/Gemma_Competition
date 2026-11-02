# Gemma 4 Developer Agent — v6c = v6b + THE BUDGET ORACLE (rich-only gate).
# Evidence (this session, from v6b LIVE traces, not dev-internal CV):
# v6b scored 1/6 on the free gate. The 3 nulls (rich_4079, rich_4070, and the
# rich_4076 near-miss) all died the SAME way, and the traces state it verbatim:
#   rich_4079 step 31: "Wait, `get_status` says 28/28 used. I have 0 left."
#   rich_4070 step 31: "Wait, I'm out of tool calls! I must submit now.
#                       But I haven't made any edits!"
#   rich_4070 step 33: "I am out of tool calls. I cannot make any edits.
#                       I will call `submit_patch` now, although it will be empty."
# Both models HAD the right file and the right diagnosis and spent the entire
# budget reading, then declared themselves unable to edit.
#
# ROOT CAUSE (verified against HARNESS_README §6.2 tool 2 and 3):
#   submit_patch()  -> count_tool_call=False  (FREE; works at 0 calls remaining)
#   get_status()     -> count_tool_call=False  (FREE; returns tool_calls_remaining)
# The v6b prompt NEVER MENTIONS get_status (0 occurrences in system.md). The model
# therefore has no idea a free budget oracle exists, cannot see how much budget it
# has left, and cannot act on the 3-4-locate-call rule it was given. It discovers
# the budget only when the harness kills it — too late to bank a partial edit.
#
# THE FIX (all in our control: prompt text only. Zero GPU. No tool changes.):
#   (1) BUDGET ORACLE RULE  — state that get_status() is FREE and returns
#       tool_calls_remaining; call it after the 2nd tool call and at every
#       decision point, so the budget is a VISIBLE number instead of a surprise.
#   (2) COMMIT-BY-REMAINING — a hard, checkable trigger: if tool_calls_remaining
#       is small, STOP READING AND EDIT NOW. Turns the previously-unenforceable
#       "edit within 3-4 calls" advice into a rule with a measurable trigger.
#   (3) BANK PARTIAL PROGRESS — for a multi-item fix, apply each item as it is
#       located (rich_4070 traced 10+ symbols then died with 0 edits banked).
#   (4) RICH-ONLY gate — drop fastapi. Both verified distinct resolves EVER are
#       rich; fastapi has never resolved and eats the wall clock for a
#       wrong-or-timeout result (v6b: 15661 timed out at 358s for 0 chars).
# KEPT FROM v6b (all measured-good): the 0.18 recipe (thinking 4096, max_out 8192,
# 28/8/80/240), edit_file+write_file dropped in favour of run_command python-replace
# (v6b proved this works: ZERO empty-old_string loops, and rich_4076/15588 both
# produced patches), single-agent (no sub-agent), and v6's contract-anchoring section.
#
# NEW kernel id (comfyops/gemma-sibling-conform-v6c). v6b and the SACRED v6 @ 0.12
# kernels are NOT overwritten.

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

# ===== CELL 2: write OUR agent directory inline (v6c = v6b + budget oracle) =====
from swegemma.models import load_tasks
DATA_DIR = Path('/kaggle/input/competitions/gemma-4-developer-agent')
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
  - get_status
  - submit_patch
  - get_code_neighbors
  - search_similar_code
  - get_code_subgraph
generate_content_config: !include configs/sampling.yaml
''', encoding='utf-8')
# v6c tools: UNCHANGED from v6b. edit_file + write_file stay REMOVED (v6b measured this
# fix works: zero empty-old_string loops; edits go through run_command python-replace).
# read_file STAYS EXPOSED: v21 dropped it and that made read-heavy localization WORSE
# (every region read became a full run_command, eating the call budget faster). The
# v6b prompt already routes line-range reads through `sed -n` via run_command, which
# sidesteps the read_file pagination friction without paying v21's removal cost.

# v6c sampling: UNCHANGED from v6b — matches the verified 0.18 LB recipe exactly.
(AGENT_DIR / 'configs' / 'sampling.yaml').write_text('''temperature: 0.2
top_p: 0.95
max_output_tokens: 8192
thinking_config:
  thinking_budget: 4096
  include_thoughts: true
''', encoding='utf-8')

# v6c eval_config: UNCHANGED 28/8/80/240. Budget-raising is FALSIFIED (v21 vs v6b A/B:
# 15->28 calls resolved ZERO additional tasks), so this knob stays exactly where the
# whole 0.18 LB cluster sits.
(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 8
  max_tool_calls: 28
  max_turns: 80
  timeout_seconds: 240
''', encoding='utf-8')

# ===== v6c system.md =====
# CHANGES vs v6b (THE ENTIRE EXPERIMENT — three additions, all in the "budget" family):
#   + THE BUDGET ORACLE section (get_status is FREE and returns tool_calls_remaining)
#   + COMMIT-BY-REMAINING (a checkable trigger replacing an unenforceable vibe)
#   + BANK AS YOU GO (apply each item as located, don't trace the whole plan first)
#   + a hard "READING PAID FOR" readout framing so reading has an explicit price.
# KEPT VERBATIM: contract-anchoring (v6's lever), the run_command python-replace edit
# recipe (measured to land multi-line edits in v6b), and the hard rules.
(AGENT_DIR / 'prompts' / 'system.md').write_text('''You are an expert autonomous software engineer. You have a HARD budget of ~28 tool calls and 8 minutes.

## THE BUDGET ORACLE — READ THIS FIRST (this is the single most important rule)
**`get_status()` is FREE. It does NOT consume your tool-call budget.** It returns `tool_calls_remaining`, `time_seconds_remaining`, and `patch_size`. You can call it as often as you like.

**Every read you do is spending money. Every status check is free. So check constantly.**
Call `get_status()` RIGHT AFTER your second tool call, and again any time you are about to start a NEW line of investigation. Knowing "I have 19 calls left" changes your behaviour; not knowing it is how runs die.

## COMMIT-BY-REMAINING — the rule that decides whether you score
You WILL run out of budget. Prior runs have died here, verbatim:
  "I'm out of tool calls! I must submit now. But I haven't made any edits!"
  "I have 0 tool calls remaining. I cannot make any edits."
That is a zero. Do not repeat it.

After EVERY `get_status()`, apply this trigger:
- **tool_calls_remaining <= 14** -> you are past locating. STOP searching. Make your edit NOW with your best current hypothesis.
- **tool_calls_remaining <= 7**  -> you are in the danger zone. Whatever the state of your investigation, apply the smallest plausible fix to the most likely file and submit. Do NOT spend another call reading.
- **tool_calls_remaining <= 3**  -> emit the edit immediately. Nothing else.

**When you are out of locating budget you are still allowed to edit.** The budget limits READS AND EDITS equally, which is why you must bank the edit before you run dry.

## BANK PROGRESS AS YOU GO (multi-item fixes)
If the problem needs several changes, apply EACH ONE the moment you locate it — do not trace the entire plan first and edit at the end. A partial fix that is submitted scores. A complete plan that never gets written scores nothing.

## EDIT EARLY, SUBMIT FAST, DON'T SCOPE-CREEP
Spend AT MOST 3-4 tool calls locating the bug, then MAKE YOUR EDIT. Do NOT attempt large multi-file refactors — land the SMALLEST fix that addresses the problem and SUBMIT. The moment you have ANY applying patch, call `submit_patch`: a partial fix that is submitted scores; a perfect refactor that times out unsubmitted scores NOTHING.

## Strategy: conform to the pattern
Most bugs are a DEVIATION from a pattern the surrounding code already follows. Make the buggy code look like its correct siblings (the function before/after it, or similar functions in the same file). Fix the exact deviation (wrong constant, missing guard/branch, wrong exception, off-by-one, wrong attr/arg, missing return) - nothing else.

## Match the EXACT contract the problem describes (this is what the hidden tests check)
The hidden test asserts a PRECISE observable contract, not just "the behavior is roughly right". When your fix introduces or changes a user-facing string, error message, exception type, status code, or validation, you MUST match the exact wording and cover every obvious input variant:
- ERROR / VALIDATION messages: use the exact phrasing the problem statement implies, and mirror the style of the SIBLING check already in the file (same message shape, same field-name interpolation). Do NOT invent your own wording - a test often does `pytest.raises(..., match="exact phrase")`, so a paraphrase FAILS even when the logic is right.
- INPUT VARIANTS: if you reject newlines, reject "\\n" AND "\\r" AND "\\r\\n". If you guard one special char, guard the whole obvious class. Tests parametrize across all of them.
- Apply the change to EVERY field/argument/branch the problem mentions, not just the first - if the problem says "id or event", fix BOTH, mirroring how an existing validated field is wired.
- A self-written test only counts as verification if it asserts the SAME exact string and the SAME variants the problem implies. If your test passes but only checks your own paraphrase, it proves nothing. Prefer asserting the behavior described in the problem's own words.

## Workflow (tight)
1. Read the problem statement. Extract the file/function/error AND the exact contract (messages, variants, every field named). Find the code with ONE `run_command` grep, or `read_file` for a whole file. Then call `get_status` (free) to see where you stand.
2. Make the minimal fix with ONE run_command python-replace call. This is your ONLY edit mechanism (there is no edit_file). Run a python heredoc that reads the file, asserts the old text is present, replaces it once, and writes it back. Use python triple-DOUBLE-quoted strings for the OLD and NEW blocks. Pattern (one run_command call): start a `python3` heredoc; set p = pathlib.Path to the source file; s = p.read_text(); set OLD to the exact current text copied byte-for-byte from read_file (NO line-number gutter); set NEW to the replacement; assert OLD in s; p.write_text(s.replace(OLD, NEW, 1)); print OK; end the heredoc.
   Keep OLD SHORT and UNIQUE. If the assert reports the anchor is not found, re-read that span and copy it exactly — do NOT re-send the same call. Match existing conventions/strings/types EXACTLY, including the sibling's message style.
   NOTE on reading a span: use `run_command` with `sed -n 'A,Bp' <file>` — that reliably returns the exact lines you asked for. `read_file` line-ranges are unreliable in this environment.
3. Call `get_status` again. If `patch_size` is still 0, you have not actually edited anything — fix that before submitting.
4. Call submit_patch ONCE (it is FREE and works even at 0 tool calls remaining). The moment it returns status "ok", you are DONE: write a one-sentence summary and make NO more tool calls. NEVER call submit_patch twice.

## Hard rules
- NEVER modify/create/delete test files (test_*.py, *_test.py, tests/) or runner config (conftest.py, pytest.ini, pyproject.toml) - the harness resets them; it pollutes your diff or auto-fails.
- Apply SOURCE edits with the ONE run_command python-replace shape above. Scratch/repro files go to /tmp via run_command heredoc `cat > /tmp/x.py <<'EOF'`. Only touch the committed source file.
- Offline: no pip install. Do NOT refactor unrelated code. Do NOT run bare pytest (it times out) - if you test, run ONLY the one target test.
- Do NOT conclude without a non-empty patch. If a tool call errors, CHANGE the approach — never re-send an identical failing call.
- NEVER end your turn saying you are out of calls and cannot edit. That is always wrong: check `get_status` (free) and bank the edit you can still make.
''', encoding='utf-8')

TASKS_PATH = DATA_DIR / 'tasks.jsonl'
tasks = load_tasks(TASKS_PATH)
print(f'Agent dir written (v6c = v6b + BUDGET ORACLE: free get_status taught as an oracle, '
      f'commit-by-remaining-calls trigger, bank-as-you-go; rich-only gate): {AGENT_DIR}')
print(f'Loaded {len(tasks)} tasks')

# ===== CELL 3: start vLLM server =====
import litellm, torch
from adk_submission import VllmConfig, VllmServer, discover_adapters
from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
# DEFENSIVE import: swegemma.models.discovery was removed in the current wheelhouse (module moved).
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

# ===== CELL 4: RICH-ONLY gate. Same recipe as v6b; only the task sample changes. =====
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

# RICH-ONLY (user decision 2026-10-11). fastapi is dropped: both verified distinct
# resolves EVER are rich, fastapi has never resolved, and in v6b it burned the most
# wall-clock for the worst outcomes (15661: 358s TIMEOUT for 0 chars; 15588: submitted
# WRONG in 10 calls). Spending the gate on rich concentrates it where resolves happen.
#
# Task choice (from RICH_48_DIFFICULTY_MAP §5, ranked by edit mechanics):
#   rich_4077 - the proven anchor (EASY, +3 ADD). Must STAY resolved; a regression here
#              means the oracle rule broke the working path.
#   rich_4079 - the primary target. v6b reached the RIGHT file + RIGHT diagnosis and
#              died at 0 calls with 0 edits. It is the cleanest test of commit-by-remaining.
#   rich_4076 - secondary target. v6b DID commit and submit here, just the wrong file
#              (pretty.py instead of the gold ansi.py). Tests whether banking earlier
#              also helps it re-localise before committing.
#   rich_3471 - fresh EASY (+1 ADD, rich/text.py, title names the method). Never attempted.
#   rich_3278 - fresh EASY (+1 ADD, rich/ansi.py). Never attempted; was pure search-death.
#   rich_3882 - fresh EASY (1/1, rich/prompt.py). Never attempted.
# rich_4070 is DELIBERATELY EXCLUDED: a 9-file import-defer perf refactor (HARD class)
# that a 28-call agent should not be expected to clear. Including it would spend a sixth
# of the gate on a task whose failure is genuine difficulty, not commitment.
SAMPLE_IDS = ['rich_4077', 'rich_4079', 'rich_4076', 'rich_3471', 'rich_3278', 'rich_3882']
by_id = {t.instance_id: t for t in tasks}
SAMPLE_TASKS = []
for _tid in SAMPLE_IDS:
    if _tid in by_id:
        SAMPLE_TASKS.append(by_id[_tid])
    else:
        print(f'  WARNING: {_tid} not found in tasks.jsonl - skipped')
print(f'RICH-ONLY gate ({len(SAMPLE_TASKS)} tasks): {[t.instance_id for t in SAMPLE_TASKS]}')

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
print('\n===== v6c SUMMARY =====')
print(tdf.to_string(index=False))
print(f'\nRESOLVED: {tdf.resolved.sum()}/{len(tdf)}')
for key in ['4077', '4079']:
    row = tdf[tdf.id.str.contains(key)]
    if len(row): print(f'  {row.id.iloc[0]}: resolved={bool(row.resolved.iloc[0])} (calls={int(row.tool_calls.iloc[0])}, chars={int(row.patch_chars.iloc[0])})')
print('Max tool_calls used:', int(tdf.tool_calls.max()), '| max dur:', round(tdf.duration_s.max()), 's (cap 300)')
print('BASELINE to beat (v6b, same rich tasks): rich_4077=True/13 calls/424ch, '
      'rich_4079=False/28/0ch, rich_4076=False/21/448ch -> 1/3')
print('fresh EASY tasks (3471/3278/3882) were never run -> any resolve is new ground')

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