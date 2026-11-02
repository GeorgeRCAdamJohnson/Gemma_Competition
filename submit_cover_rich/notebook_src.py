# Gemma 4 Developer Agent - v6w = v6t with thinking_budget QUARTERED 4096 -> 1024. ONE variable.
#
# THIRD POINT ON THE THINKING LADDER (user call 2026-10-11; runs alongside v6v/2048 on the second GPU slot):
#   256  : OUR v6 @ 0.12 - only board score we have. Everything finished inside the wall.
#   1024 : THIS ARM - untested.
#   2048 : v6v, queued in parallel.
#   4096 : what v6b/v6c/v6t ship. NEVER SCORED (36h lag + 1/day). Put rich_3471 on the wall twice.
#   OFF  : v6u - FASTER (rich_3471 481.9s -> 406.2s, off the wall) BUT LOST rich_4079 by committing
#          early and wrong at 150.7s. Same shape as the v11 LoRA failure.
#
# The open question is whether the "commit early, get it wrong" behaviour of thinking-OFF is a
# BUDGET problem (too little deliberation) or an on/off problem (thinking itself). v6u says thinking-OFF
# costs quality. v6v/2048 and v6w/1024 bracket the middle. If 1024 also degrades toward the OFF result,
# the ladder is steep and 2048-4096 is the working range. If 1024 holds 4/6 with no wall task, we may not
# need 4096 at all - which matters because 4096 is the one setting we have never scored on the board.
#
# MEASUREMENT CAVEAT (honest, pre-registered): running two arms in parallel is fine - they are separate
# Kaggle kernels on separate GPUs, so they do not contend for hardware. But it does NOT double the evidence:
# the free gate can only separate configs differing by a 3+ point swing (v6c vs v6t tied 4/6 on a
# wall-boundary coin flip). Three arms on a 6-task set means most outcomes will be indistinguishable from
# noise. Treat any single-arm move of 1 task as NOT evidence.
#
# v6w = v6t EXACTLY, except thinking_budget 4096 -> 1024. Held identical: 9-tool list with edit_file
# primary, budget 28/8/80/240, temperature 0.2, top_p 0.95, max_output_tokens 8192, include_thoughts TRUE,
# the Budget Oracle + Commit-by-Remaining + Bank-as-you-Go sections, and the SAME 6 tasks.
#
# PRE-REGISTERED BAR (vs v6t's 4/6):
#   - >= 5/6                       -> adopt 1024.
#   - == 4/6 AND no task on a wall -> equal quality, materially cheaper in time; prefer it.
#   - == 4/6 with a boundary loss   -> indistinguishable from v6t; keep the higher budget.
#   - <= 3/6                       -> 1024 is below the useful deliberation floor.
# SECONDARY, transfers even on a null: mean seconds/task vs v6t's ~266s and v6u's (faster but wrong).
#
# NEW kernel (comfyops/gemma-sibling-conform-v6w). v6/0.12 SACRED; v6b/c/s/t/u/v all untouched.

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

# REVERTED 2026-10-17 to the PROVEN v6 cell, verbatim. History, so it is not repeated:
#  * The cover-rich v1 failure ("Installing 0 wheels") was NOT a code bug. This exact block
#    produced "Installing 41 wheels..." on the v6 and v6w runs and the 0.15 board score.
#  * I "fixed" it with a resolver that misread its own log line and preferred
#    /kaggle/input/gemma-4-developer-agent/wheels. That dir is the competition WEB APP's
#    dependency set -- 45 starlette versions, 3 pytest versions, cp313 wheels on a py3.12 kernel,
#    no swegemma/vllm/torch/adk -- so it tried to install 124 wrong wheels and died.
#  * The ABI filter I then added was itself buggy: cp3(\d+) captures "312" from cp312, so
#    int("312") == 12 is False; it rejected VALID cp312 wheels and kept cp313 ones.
#  Three self-inflicted bugs in code that never needed changing. The only addition kept is a
#  diagnostic that fires ONLY when the wheel list is empty, so a real mount failure is legible.
# CORRECTED 2026-10-17 by direct evidence, not inference. The DIAG block printed
#   /kaggle/input contains: ['gemma-4-developer-agent', 'gemma-4-developer-agent-wheelhouse', 'models']
# so Kaggle mounts datasets FLAT at /kaggle/input/<dataset-name>. The long-standing path
# '/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse' has a '/datasets/metric/'
# prefix that does NOT exist in the current mount layout, so WHEELHOUSE_DIR.is_dir() was False.
# That path DID work on 2026-10-14 (v6/v6w logs show 'Installing 41 wheels...'), so the platform
# mount layout changed between 10-14 and 10-17. Kept as a fallback in case it comes back.
WHEELHOUSE_DIR = Path('/kaggle/input/gemma-4-developer-agent-wheelhouse')
if not WHEELHOUSE_DIR.is_dir():
    _alt = Path('/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse')
    if _alt.is_dir():
        WHEELHOUSE_DIR = _alt
for pth_pattern in ('/usr/local/lib/python*/dist-packages/*cutlass*.pth',
                    '/usr/local/lib/python*/site-packages/*cutlass*.pth'):
    for pth in glob.glob(pth_pattern):
        try: os.unlink(pth)
        except OSError: pass
tmp_whl = Path('/tmp/wheelhouse')
# Never reuse stale symlinks: the pip list below is built by globbing /tmp/wheelhouse, NOT
# WHEELHOUSE_DIR, so anything left there from an earlier in-session run gets installed. That is
# how 124 leftover app-dependency wheels were pip-installed on 2026-10-17.
if tmp_whl.exists(): shutil.rmtree(tmp_whl)
tmp_whl.mkdir(parents=True, exist_ok=True)
for w in WHEELHOUSE_DIR.glob('*.whl'):
    if 'cutlass' in w.name.lower(): continue
    target_name = (w.name.replace('cu128', '+cu128') if ('cu128' in w.name and '+' not in w.name) else w.name)
    target = tmp_whl / target_name
    if not target.exists(): os.symlink(w, target)
wheels = sorted(str(w) for w in tmp_whl.glob('*.whl'))
_names = [w.rsplit('/', 1)[-1] for w in wheels]
print(f'WHEELHOUSE: {WHEELHOUSE_DIR} exists={WHEELHOUSE_DIR.is_dir()} '
      f'globbed={len(list(WHEELHOUSE_DIR.glob("*.whl"))) if WHEELHOUSE_DIR.is_dir() else 0} '
      f'installing={len(wheels)} swegemma={any("swegemma" in n for n in _names)}')
# The harness wheelhouse is ~41 wheels and MUST contain swegemma. A set without it is the
# competition WEB APP dependency set (124 wheels, 45 starlette versions, cp313 tags, no
# swegemma/vllm/torch/adk) and must never be pip-installed here.
if wheels and not any('swegemma' in n for n in _names):
    raise RuntimeError(
        f'WRONG WHEELHOUSE: {len(wheels)} wheels at {WHEELHOUSE_DIR} but no swegemma wheel. '
        f'First names: {_names[:8]}. This is the competition app dependency set, not the harness '
        'wheelhouse.')
if not wheels:  # diagnostic only -- the proven path and glob above are unchanged
    _root = Path('/kaggle/input')
    print('WHEELHOUSE EMPTY. exists(WHEELHOUSE_DIR) =', WHEELHOUSE_DIR.is_dir())
    print('/kaggle/input contains:',
          sorted(p.name for p in _root.iterdir()) if _root.is_dir() else '<none>')
    raise RuntimeError('wheelhouse dataset not mounted -- see listing printed above')
print(f'Installing {len(wheels)} wheels...')
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *wheels], check=True)
importlib.invalidate_caches()
print('Wheelhouse installation complete.')

# ===== CELL 2: write OUR agent directory inline (v6t = v6c + edit_file restored) =====
from swegemma.models import load_tasks
# CORRECTED 2026-10-17 by the same measured mount listing that fixed the wheelhouse path:
#   /kaggle/input contains ['gemma-4-developer-agent', 'gemma-4-developer-agent-wheelhouse', 'models']
# So the competition data is FLAT at /kaggle/input/gemma-4-developer-agent. The old
# '/kaggle/input/competitions/gemma-4-developer-agent' has a '/competitions/' segment that does not
# exist in the current layout. Old path kept as a fallback.
DATA_DIR = Path('/kaggle/input/gemma-4-developer-agent')
if not DATA_DIR.is_dir():
    _alt = Path('/kaggle/input/competitions/gemma-4-developer-agent')
    if _alt.is_dir():
        DATA_DIR = _alt
assert DATA_DIR.is_dir(), (
    f'Competition data not mounted at {DATA_DIR}. /kaggle/input actually contains: '
    f'{sorted(p.name for p in Path("/kaggle/input").iterdir()) if Path("/kaggle/input").is_dir() else "<none>"}. '
    'competition_sources declares gemma-4-developer-agent; re-attach it rather than editing paths.')
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
# v6t tools: edit_file + write_file RESTORED, giving the same 9-tool list the stock control and the 0.18
# reference kernels ship. run_command stays available for grep/sed/python-heredoc fallback. read_file stays
# exposed: v21 dropped it and that made read-heavy localization WORSE (every region read became a full
# run_command, eating the call budget faster).

# v6c sampling: UNCHANGED from v6b — matches the verified 0.18 LB recipe exactly.
(AGENT_DIR / 'configs' / 'sampling.yaml').write_text('''temperature: 0.2
top_p: 0.95
max_output_tokens: 8192
thinking_config:
  thinking_budget: 1024
  include_thoughts: true
''', encoding='utf-8')

# v6c eval_config: UNCHANGED 28/8/80/240. HELD HERE FOR POOL COMPARABILITY, not because
# budget is believed to be a lever.
# HISTORY OF THIS COMMENT (three revisions, kept so the record is honest):
#  v1 said "Budget-raising is FALSIFIED (v21 vs v6b A/B: 15->28 calls resolved ZERO additional
#     tasks)". Already retracted by the audit at GEMMA_EXPERIMENT_LOG L9287: v21-vs-v6b changed
#     >=5 variables at once, so it was never a one-change budget A/B.
#  v2 (wrong, corrected here) over-read that retraction and implied the budget lever was simply
#     untested, pointing at scored ref 57276407 as "in flight".
#  v3 (this one) is the measured truth as of 2026-10-17:
#     * ref 57276407 (28/8/80 -> 100/500/60) returned NO SCORE -- the scorer threw, so it
#       produced no measurement at all.
#     * A free measurement over 242 traced runs shows the budget axis is NOT BINDING:
#       tool_calls mean 18.9 / median 18, only 20% of runs ever reach the cap of 28;
#       duration mean 218s / median 211s, only 4% ever reach the 8-minute wall;
#       paired n=25 -> call-bound 4, time-bound 1, neither 20.
#       So v6w is overwhelmingly neither-bound: the agent stops voluntarily at ~19 calls and
#       ~3.6 min with headroom on BOTH caps. Raising either axis cannot help the runs that
#       stop early. Budget-as-more-room is therefore CLOSED as a direction, and the measured
#       never_committed failure class (26-33%) is BEHAVIOURAL -- the agent stops without landing
#       the edit -- not a symptom of running out of room.
# This gate therefore stays at 28/8/80/240 for ONE reason only: p_hat is only comparable within
# a single config, and the purpose of this run is to extend the EXISTING v6w coin-flip pool.
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
2. Make the minimal fix with ONE `edit_file` call. That is your PRIMARY edit mechanism. Run a python heredoc via `run_command` ONLY as a fallback if `edit_file` reports it could not match the anchor.
   Using `edit_file`: set `filepath` to the source file, `old_string` to the exact current text copied byte-for-byte from `read_file` (NO line-number gutter), `new_string` to the replacement. Keep `old_string` SHORT and UNIQUE. The matcher is forgiving: it tries exact, then whitespace-flexible (re-indenting for you), then regex. Match existing conventions/strings/types EXACTLY, including the sibling's message style.
   Fallback only: run a python heredoc that reads the file, asserts the old text is present, replaces it once, and writes it back. Use python triple-DOUBLE-quoted strings for the OLD and NEW blocks. Pattern (one run_command call): start a `python3` heredoc; set p = pathlib.Path to the source file; s = p.read_text(); set OLD to the exact current text; set NEW to the replacement; assert OLD in s; p.write_text(s.replace(OLD, NEW, 1)); print OK; end the heredoc.
   If a call fails, re-read that span and copy it exactly — do NOT re-send the same call.
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
print(f'Agent dir written (v6t = v6c + edit_file/write_file RESTORED as primary edit mechanism; '
      f'0.18 budget, budget oracle + commit-by-remaining + bank-as-you-go, same 6 tasks): {AGENT_DIR}')
print(f'Loaded {len(tasks)} tasks')

# ===== RUN FINGERPRINT (2026-10-17) =====
# WHY: on 2026-10-17 an arm forked from an OLD notebook silently inherited that notebook's whole
# config, and we published a 'size curve' in which FIVE variables moved at once (prompt 6825 vs
# 4172 chars, thinking 1024 vs 512, output 8192 vs 6144, eval 28/80/8/240 vs 22/40/5/120, and 9
# tools vs 10-with-a-refuted-subagent). It was only caught by diffing files AFTER the runs. These
# stale print strings are exactly the trap:
#     'Agent dir written (v6 = v5 + contract-anchoring)'   <- names a config nobody is running
#     'A/B sample (same as v1/v3/v4/v5)'                   <- names a task set nobody is running
# So: fingerprint what is ACTUALLY ON DISK, not what a comment claims. One line, and any future
# multi-variable comparison becomes self-evident in the first ten seconds of log output.
import hashlib as _hl, json as _js
def _sha(p):
    try: return _hl.sha256(Path(p).read_bytes()).hexdigest()[:12]
    except Exception: return 'MISSING'
_agtxt = (AGENT_DIR / 'agent.yaml').read_text(encoding='utf-8')
_tools = [l.strip()[2:].strip() for l in _agtxt.splitlines() if l.strip().startswith('- ')]
FINGERPRINT = {
    'model': _agtxt.split('model:')[1].split()[0] if 'model:' in _agtxt else '?',
    'prompt_sha': _sha(AGENT_DIR / 'prompts' / 'system.md'),
    'prompt_chars': len((AGENT_DIR / 'prompts' / 'system.md').read_text(encoding='utf-8')),
    'sampling_sha': _sha(AGENT_DIR / 'configs' / 'sampling.yaml'),
    'eval_sha': _sha(AGENT_DIR / 'eval_config.yaml'),
    'n_tools': len(_tools), 'tools': _tools,
    'has_subagent': any('agent_tool' in t or 'sub_agents' in t for t in _tools),
}
print('RUN_FINGERPRINT(config) ' + _js.dumps(FINGERPRINT, sort_keys=True))
assert not FINGERPRINT['has_subagent'], (
    'Refuted sub-agent present in the tool list (log: dmitrii sweep + our v8 regression). '
    'Remove it or this arm is not a clean single-variable comparison.')

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
# The measured mount listing showed 'models' directly under /kaggle/input, so the
# '/kaggle/input/models/...' prefix is still correct, but the tail after it is unverified in the
# current layout. Resolve it, and fall back to an rglob, because a wrong MODEL_PATH otherwise
# surfaces only AFTER an 18GB load attempt as an opaque vLLM / CUDA-graph error.
MODEL_PATH = Path('/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2')
if not MODEL_PATH.is_dir():
    _mroot = Path('/kaggle/input/models')
    if _mroot.is_dir():
        for _d in sorted(_mroot.rglob('gemma-4-31b-it-qat-w4a16-ct*')):
            if _d.is_dir():
                MODEL_PATH = _d
                break
assert MODEL_PATH.is_dir(), (
    f'31B model not found. /kaggle/input contains: '
    f'{sorted(p.name for p in Path("/kaggle/input").iterdir()) if Path("/kaggle/input").is_dir() else "<none>"}; '
    f'/kaggle/input/models contains: '
    f'{sorted(p.name for p in Path("/kaggle/input/models").iterdir()) if Path("/kaggle/input/models").is_dir() else "<none>"}. '
    'model_sources declares google/gemma-4/Other/gemma-4-31b-it-qat-w4a16-ct/2 -- re-attach it.')
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

# ============================================================================
# COVERAGE RUN 2026-10-16 -- purpose is WIDENING THE COIN-FLIP POOL, not beating 0.15.
#
# WHY THIS TASK SET (measured 2026-10-16, see GEMMA_EXPERIMENT_LOG "ITEM 2"):
# Gate discrimination is bounded by the COUNT OF COIN-FLIP TASKS in the gate, NOT by
# gate size. Simulated on the observed p_hat mix:
#   - adding p=0 never-resolve tasks changes P(arm>base) by NOTHING
#     (6 coin-flips + 0/6/42/123 dead tasks -> 0.575/0.572/0.578/0.580 at lift x1.5)
#   - adding COIN-FLIP tasks moves it a lot
#     (6/12/24/48 coin-flips -> 0.577/0.725/0.850/0.949 at lift x1.5)
# We have exactly 6 traced coin-flip tasks (rich_3278 .75, rich_3471 .25, rich_3676 .12,
# rich_3882 .92, rich_4077 .82, rich_4079 .18). That pool, not GPU hours, is the ceiling.
#
# So this run spends its budget on the 31 rich tasks that have NEVER been traced, one run
# each. Re-running the 6 known coin-flips is deliberately EXCLUDED: replicates shrink
# within-task noise but cannot add tasks, so they buy nothing here.
#
# The already-traced 17 rich tasks split 10 never-resolve (dead, worth re-confirming at
# zero value) + 7 live. The 31 below are the unknown set; any that resolve at least once
# is a confirmed coin-flip candidate and enters the pool for later repeats.
#
# CONFIG IS HELD AT v6w EXACTLY (28 tool calls / 80 turns / 8 min, thinking_budget 1024,
# temp 0.2, same 9-tool surface, same prompt). This is deliberate: the notebook's
# EvalConfig is driven by the eval_config.yaml it writes, so the gate runs at v6w's budget.
# p_hat is only comparable within one config, and the point is to extend the EXISTING
# v6w pool. (The separate budget-raise arm, scored ref 57276407 at 100/500/60, returned NO
# SCORE -- the scorer threw -- and a 242-run measurement then showed the budget axis is not
# binding anyway. See the eval_config comment below for the full three-revision history.)
# fastapi is excluded: 67 tasks, zero verified resolves ever, so its p_hat is ~0 and by the
# dead-task result above it would add nothing but wall clock.
UNTRACED_RICH = [
    'rich_2725', 'rich_2943', 'rich_3006', 'rich_3043', 'rich_3052', 'rich_3061',
    'rich_3063', 'rich_3064', 'rich_3067', 'rich_3105', 'rich_3130', 'rich_3180',
    'rich_3296', 'rich_3454', 'rich_3468', 'rich_3470', 'rich_3472', 'rich_3480',
    'rich_3506', 'rich_3518', 'rich_3521', 'rich_3772', 'rich_3777', 'rich_3782',
    'rich_3894', 'rich_3905', 'rich_3930', 'rich_3935', 'rich_3938', 'rich_3942',
    'rich_3944',
]
SAMPLE_IDS = UNTRACED_RICH

by_id = {t.instance_id: t for t in tasks}
SAMPLE_TASKS = []
for _tid in SAMPLE_IDS:
    if _tid in by_id:
        SAMPLE_TASKS.append(by_id[_tid])
    else:
        print(f'  WARNING: {_tid} not found in tasks.jsonl - skipped')
print(f'RICH-ONLY gate ({len(SAMPLE_TASKS)} tasks): {[t.instance_id for t in SAMPLE_TASKS]}')

# tasks_sha / n_tasks are appended HERE, not in the early fingerprint: SAMPLE_IDS lives in
# CELL 4 and SAMPLE_TASKS only after the by_id loop, so referencing either from CELL 2 raised
# 'NameError' and killed the 12b run on 2026-10-17. Both halves are guarded anyway.
try:
    FINGERPRINT['tasks_sha'] = _hl.sha256(','.join(SAMPLE_IDS).encode()).hexdigest()[:12]
    FINGERPRINT['n_tasks'] = len(SAMPLE_TASKS)
    print('RUN_FINGERPRINT ' + _js.dumps(FINGERPRINT, sort_keys=True))
    Path(WORKING_DIR, 'run_fingerprint.json').write_text(_js.dumps(FINGERPRINT, indent=1), encoding='utf-8')
except Exception as _e:
    print('[fingerprint] task fields deferred-failed: %s: %s' % (type(_e).__name__, _e))

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
# ===== PER-TASK ROWS, FLUSHED PER TASK (2026-10-17) =====
# WHY: until now `predictions` lived only in memory and was NEVER written to disk, and the
# failure classes we care about (never-landed-edit / wrong-file / right-file-wrong-content) had to
# be reconstructed AFTER the fact by a separate classifier -- which was wrong the first time it was
# written today and right the second. Streaming JSONL also survives a crash or an 8h timeout,
# which an in-memory list does not. Gold-path is read best-effort and simply omitted if absent.
ROWS_PATH = WORKING_DIR / 'run_rows.jsonl'
_gold_by_id = {}
try:
    for _l in (TASKS_PATH).read_text(encoding='utf-8', errors='replace').splitlines():
        if _l.strip():
            _r = _js.loads(_l)
            _gold_by_id[_r['instance_id']] = _r.get('patch', '') or ''
except Exception as _e:
    print(f'[rows] gold patch lookup unavailable ({type(_e).__name__}); gold fields omitted')

def _emit(row):
    with open(ROWS_PATH, 'a', encoding='utf-8') as fh:
        fh.write(_js.dumps(row) + '\n'); fh.flush()

for idx, task in enumerate(SAMPLE_TASKS, start=1):
    print(f'[{idx}/{len(SAMPLE_TASKS)}] {task.instance_id} ({task.repo})...')
    result = run_sync(evaluator.evaluate_task, task=task, task_index=idx, total_tasks=len(SAMPLE_TASKS))
    predictions.append({'id': task.instance_id, 'prediction': result.agent_patch or ''})
    row = {'id': task.instance_id, 'repo': task.repo.split('/')[-1],
           'resolved': bool(result.resolved),
           'duration_s': round(result.duration_seconds, 1),
           'tool_calls': int(result.tool_calls),
           'patch_chars': len(result.agent_patch or '')}
    timing.append(row)
    _gold = _gold_by_id.get(task.instance_id, '')
    if _gold:
        import re as _re
        row['gold_files'] = _re.findall(r'^--- a/(\S+)', _gold, _re.M)
        row['n_gold_edits'] = len(row['gold_files'])
    _emit(row)
    print(f'  -> resolved={result.resolved} duration={result.duration_seconds:.1f}s '
          f'tool_calls={result.tool_calls} patch_chars={len(result.agent_patch or "")}')

# ===== TRACE-DERIVED FIELDS (2026-10-17) =====
# The traces DO carry tool_calls[].function_name, full arguments, and edit_file diffs inside
# steps[].observation.content -- I had wrongly assumed otherwise twice today. Aggregate them here
# so every future run emits first-class failure telemetry instead of needing a post-hoc classifier.
try:
    import collections as _co
    _rows = {}
    for _l in ROWS_PATH.read_text(encoding='utf-8').splitlines():
        if _l.strip():
            _r = _js.loads(_l)
            _rows[_r['id']] = _r
    for _tid, _r in _rows.items():
        _tp = WORKING_DIR / 'results' / 'traces' / ('trace_%s.json' % _tid)
        if not _tp.is_file():
            continue
        _tr = _js.loads(_tp.read_text(encoding='utf-8', errors='replace'))
        _cnt = _co.Counter()
        _files = set()
        _first_edit = None
        _bw = 0
        _seen = 0
        for _s in _tr.get('steps', []):
            _c = (_s.get('observation') or {}).get('content')
            if isinstance(_c, str) and 'budget_warning' in _c:
                _bw += _c.count('budget_warning')
            for _tc in (_s.get('tool_calls') or []):
                if not isinstance(_tc, dict):
                    continue
                _fn = _tc.get('function_name', '?')
                _cnt[_fn] += 1
                _seen += 1
                if _fn == 'edit_file' and _first_edit is None:
                    _first_edit = _seen
            if isinstance(_c, str) and '"diff"' in _c:
                try:
                    _j = _js.loads(_c)
                    if isinstance(_j, dict) and _j.get('filepath'):
                        _files.add(_j['filepath'])
                except Exception:
                    pass
        _r.update(edit_file_calls=_cnt.get('edit_file', 0),
                  submit_calls=_cnt.get('submit_patch', 0),
                  get_status_calls=_cnt.get('get_status', 0),
                  run_command_calls=_cnt.get('run_command', 0),
                  read_file_calls=_cnt.get('read_file', 0),
                  files_touched=sorted(_files),
                  budget_warnings=_bw,
                  first_edit_at_call=_first_edit)
        if _r.get('gold_files'):
            _r['gold_file_touched'] = bool(set(_r['gold_files']) & set(_files))
        # first-class failure class, computed the same way every time
        if _r['resolved']:
            _r['failure_class'] = 'RESOLVED'
        elif _r['patch_chars'] == 0:
            _r['failure_class'] = 'NEVER_LANDED_EDIT'
        elif _r.get('gold_file_touched') is False:
            _r['failure_class'] = 'WRONG_FILE'
        else:
            _r['failure_class'] = 'RIGHT_FILE_WRONG_CONTENT'
    ROWS_PATH.write_text(''.join(_js.dumps(_rows[k]) + '\n' for k in _rows), encoding='utf-8')
    print('\nRUN_ROWS written: %s' % ROWS_PATH)
    print('FAILURE_CLASSES', dict(_co.Counter(v.get('failure_class', '?') for v in _rows.values())))
except Exception as _e:
    print('[rows] trace enrichment failed: %s: %s' % (type(_e).__name__, _e))

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