# Gemma 4 Developer Agent — v22: MODEL SWAP 31b -> 12b base (NO adapter). The 31b wanders and emits 0-char
# patches on everything but the always-solve task; the commitment problem is a property of the quantized 31b.
# 12b is now a legal submission model (was not before). In our OWN local A/B, 12b base produced the biggest,
# most coherent patches (1327 & 595 chars) of any config, and base beats every trained LoRA adapter on
# produce-a-patch (adapters are a logged NEGATIVE). So this swaps ONLY the model, keeping v21's proven interface.
#
# v22 CRASH FIX (CONFIRMED by Kaggle staff Ryan Holbrook + competitor Ziad Samer's repro): the 12b checkpoint
# declares Gemma4UnifiedForConditionalGeneration (model_type gemma4_unified) which vLLM 0.19.1 has no native impl
# for -> Transformers-backend fallback -> profile_run crash. The earlier enforce_eager/VLLM_ENFORCE_EAGER theory
# was WRONG (there is no such env var; it did not fire). The real fix is the staff --hf-overrides arch remap passed
# via VllmConfig(extra_args=...), applied only to the 12b variant (see CELL 3). DEV-EVAL only; real submission ships
# the 4 YAML files and the HOST serves the model.
# RISK: 12b timing on the L4x4 w4a16 kernel is unknown; the gate tells us if it fits the wall.
#
# [v21 header retained below for interface-fix rationale]
# v21: KILL BOTH HARNESS-INTERFACE WALLS (zero-GPU, prompt+tools-whitelist only).
#
# WHY (forensic read of LIVE v19 traces, measured — NOT a model/weights problem): the agent self-diagnoses the
# correct fix on rich tasks and still scores ~0 because TWO harness-interface walls kill it before the edit lands:
#   WALL #1 (READ): read_file(start_line,end_line) returns the TOP of a long file, not the span requested, so the
#     model never sees the function it localized and burns its budget re-reading garbage -> SEARCH-DEATH (~60%).
#   WALL #2 (EDIT): the model CANNOT reliably emit a multi-field edit_file(old_string=,new_string=) call — the
#     gemma4 parser drops the two string args ("mandatory input old_string not present"), so it loops the identical
#     broken call 10-25x until the run dies (rich_4079 live trace: 25 empty edit_file calls).
# THE FIX = three coupled, INSEPARABLE interface changes (we cannot change tool CODE — tools are harness-fixed and
# declarative — but we DO control the tools-whitelist in agent.yaml and the system prompt):
#   R1: REMOVE edit_file from the tools whitelist (physically unexpose the un-serializable tool; v18's half-fix
#       left it exposed and only discouraged it in prose, so the model still reached for it and looped).
#   R2: route ALL edits through ONE run_command python-replace call (read->assert OLD present->replace once->write),
#       the single-string shape the gemma4 parser emits reliably; the assert makes a miss LOUD, not silently wrong.
#   R3: route ALL region reads through run_command `sed -n 'A,Bp' file` and drop read_file from the whitelist, so
#       the broken line-range path is physically unreachable. (These three are one change-set: dropping edit_file
#       FORCES run_command edits, and if reads still used the broken tool, wall#1 would kill the run before the edit.)
# ONE change-set vs v19 (the interface layer); commit-to-path localization / budget 15 / 5-task sample / sampling KEPT.
# RISK (rule 9): sed/python edits can corrupt or touch test files -> prompt constrains to the committed source file,
# forbids editing tests/conftest, and the python replace asserts `OLD in s` so a bad anchor errors instead of lying.
#
# WHY (user insight + v16 data): v16 proved find and fix are DIFFERENT failures jammed into one trajectory.
# rich_4079 FOUND markdown.py but never committed/edited (wandered TableElement vs TableDataElement vs
# on_child_close); rich_3469 never committed to a file and LOOPED (re-read segment.py 5x, narrated it, did it
# again). The edit-early/anti-loop PROMPT RULES decayed and were ignored in the long zone. v17 attacks the root:
# the agent never COMMITS to a decision. So force it to DECLARE the path up front, in writing, as move 0 -
# "TARGET: file::function - FIX: x" - then spend the run CONFIRMING + APPLYING that commitment, not searching.
# The decision (find) is separated from execution (fix) WITHOUT a second agent/shared-budget split: one agent,
# but the path is committed before any tool call, which anchors the whole trajectory against wander/loop.
# ONE knob philosophy change vs v16; budget 15 / thinking 256 / no sub-agent / resolvers all KEPT.
# TEST CUT to 5 rich tasks (4 word-traps + 1) for a faster read.
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
model: gemma-4-12b-it-qat-w4a16-ct
instruction: !include prompts/system.md
tools:
  - run_command
  - get_status
  - submit_patch
  - get_code_neighbors
  - search_similar_code
  - get_code_subgraph
generate_content_config: !include configs/sampling.yaml
''', encoding='utf-8')
# v21 tools-whitelist: edit_file REMOVED (R1 — unserializable, loops to death) and read_file REMOVED (R3 — its
# line-range mode returns the top of long files). Reads go through run_command `sed -n`, edits through run_command
# python-replace. run_command is the one shape the gemma4 parser serializes reliably.

# v19 sampling: + frequency_penalty = DECODING ANTI-REPEAT (kill re-emit-the-broken-call at generation time).
# HARNESS_README L146: presence_penalty/frequency_penalty/stop_sequences/seed all permitted, unrestricted.
# frequency_penalty 0.4 is mild: discourages verbatim token-sequence repetition (the degenerate loop) without
# distorting legitimate code tokens. max_output_tokens 6144 so a WHOLE-FUNCTION edit does not truncate the
# <|tool_call> tag (HARNESS_README gotcha #1). thinking_budget stays small (short trajectory = coherent).
(AGENT_DIR / 'configs' / 'sampling.yaml').write_text('''temperature: 0.2
top_p: 0.95
max_output_tokens: 6144
frequency_penalty: 0.4
thinking_config:
  thinking_budget: 256
  include_thoughts: true
''', encoding='utf-8')

# v22 eval_config: budget 28 / 5 min. A fresh 12b base needs more calls than the tuned-31b 15, and the
# per-task ceiling is ~5 min (8-min configs timed out with no score on the competitor ladder). timeout_seconds
# raised to 200 so a single long tool call does not trip before the 5-min wall.
(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 5
  max_tool_calls: 28
  max_turns: 40
  timeout_seconds: 200
''', encoding='utf-8')

# v16 system.md = v15 anti-word-trap localization + EDIT-EARLY + RESERVE-TAIL + ANTI-LOOP.
(AGENT_DIR / 'prompts' / 'system.md').write_text("""You are an expert autonomous software engineer. You have a HARD budget of ~28 tool calls and 5 minutes. BE DECISIVE.

## STEP 0 — COMMIT TO A PATH FIRST, IN WRITING, BEFORE ANY TOOL CALL.
Your VERY FIRST response must be a one-line commitment, no tool call yet:
`TARGET: <relative/file/path.py> :: <function_or_class> — FIX: <the one specific change>`
Pick it from the problem statement + the workspace file list already shown to you + the localization rules below. This is your PLAN. You will spend the rest of the run CONFIRMING and APPLYING it, NOT searching for a new one.

## STEP 1 — CONFIRM the target in AT MOST 2-3 tool calls, READING VIA sed.
To read a specific span, use run_command with sed line-ranges — this is the ONLY reliable way to read an
exact region: `run_command(command="sed -n '940,1010p' rich/FILE.py")`. (The read_file tool's line-range
arguments are UNRELIABLE on long files — they return the TOP of the file, not the span you asked for, which
burns your budget. ALWAYS read a specific region with `sed -n 'START,ENDp' path`.) To find a symbol first:
`run_command(command="grep -n 'def on_child_close' rich/FILE.py")`, then sed that line range.
Does the function exist and does the buggy behavior flow through it?
- YES -> go straight to STEP 2 (apply the edit).
- NO / wrong file -> RE-DECLARE your TARGET line ONCE with the corrected file, then confirm it. You may re-declare at most ONCE. Do NOT drift from file to file hunting - commit, confirm, edit.

## BUDGET AWARENESS — call get_status, it is FREE (costs 0 of your 28 tool calls).
After EACH tool call, you MAY call get_status (it does NOT consume budget). Read `tool_calls_remaining`.
THE MOMENT `tool_calls_remaining <= 6`: STOP all searching/reading and APPLY YOUR EDIT THIS TURN. Do not read
one more file. A landed edit on your committed TARGET beats a perfect plan you never apply. Trust get_status's
number, not your own memory of how many calls you have made.

## STEP 2 — APPLY THE EDIT with ONE run_command python call. This is the ONLY edit mechanism you have.
You do NOT have an edit_file tool. Every source edit is a SINGLE run_command call that runs a tiny python
script which reads the file, asserts the target text is present, replaces it once, and writes it back. This
ONE-STRING shape is the only edit the model emits reliably (a multi-field edit tool drops its arguments and
loops to death). The assert makes a miss LOUD (it errors) instead of silently wrong. Template:

  run_command(command="python3 - <<'PY'\nimport pathlib\np=pathlib.Path('rich/FILE.py')\ns=p.read_text()\nOLD='''<exact current text>'''\nNEW='''<replacement text>'''\nassert OLD in s, 'anchor not found'\np.write_text(s.replace(OLD,NEW,1))\nprint('EDIT OK')\nPY")

Rules for OLD/NEW:
- Copy OLD verbatim from what `sed -n` printed — the ACTUAL file text, byte for byte (indentation included).
  NEVER include a line-number gutter (e.g. "969:") — sed -n does NOT print one, but if you used grep -n, strip
  the "N:" prefix. OLD must be a substring that exists in the file or the assert fails.
- Keep OLD SHORT and UNIQUE. Pick the EDIT SHAPE that is easiest to express correctly:
  - SHAPE 1 (BEST — ADD/OVERRIDE, don't modify): if the fix can be a NEW self-contained unit, ADD it instead of
    editing existing lines. Make OLD a short unique anchor line (e.g. a class header or the line just before the
    insertion point) and NEW = that same anchor line + the new block. Examples: add a missing method to a class;
    add an override that supersedes the buggy base method on the class actually used; add a guard at a function's
    top. "Insert a block that supersedes the bug" is the shape you express most reliably.
  - SHAPE 2 (WHOLE-FUNCTION REPLACE): if you must change multi-line logic, set OLD = the ENTIRE current function
    (from its `def name(` line through its last line, copied verbatim from sed) and NEW = the ENTIRE corrected
    function. Replacing the whole function removes the need for a fragile inner anchor. sed the function once.
  - SHAPE 3 (one-line change): OLD = that ONE line (unique, verbatim), NEW = the fixed line.
Then VERIFY with ONE targeted check (scratch script in /tmp via run_command, NOT the repo). NEVER run bare pytest.
Then submit_patch ONCE. The moment it returns "ok", STOP.

## NEVER RE-EMIT A FAILED CALL (the #1 way runs die)
If a tool call fails or returns an error, DO NOT send the identical call again — it will fail identically and
waste your budget until the run dies. If the python edit asserts "anchor not found", your OLD text is not an
exact substring: re-read that span with `sed -n` and COPY the text byte-for-byte, or switch to a different edit
SHAPE (whole-function replace, or add-a-new-unit anchored on a line you KNOW exists). Ignore any harness hint to
"split into smaller edits" if it is making you repeat — change the APPROACH instead.
Also: you committed to a TARGET — do NOT re-open the search. Never re-read a file already in context; never
repeat a grep that already returned. If you catch yourself repeating, STOP and EDIT.

## LOCALIZE BY BEHAVIOR, NOT BY THE SYMPTOM WORD (the #1 cause of WRONG fixes)
The problem is usually a 2-5 word SYMPTOM. The fix file is OFTEN NOT the file whose NAME matches that word; it is the code that PRODUCES the behavior.
- Do NOT assume "table"->table.py, "panel"->panel.py, "space"/"newline"->the obvious renderable. The word names the SYMPTOM; the fix is in whatever RENDERS or DECODES that output.
- Patterns: a spacing/alignment/"superfluous" symptom in rendered output is usually in the code that EMITS segments/lines (the markdown/console render path or cell-width math), not the high-level container. A "newline"/ANSI/escape symptom is usually in the DECODER that parses the text. A "proxy"/wrapper symptom is in the wrapper class that forwards calls. "inline" markdown/table issues live in markdown.py, not table.py.
- PROCEDURE: (1) name the exact OBSERVABLE behavior. (2) grep ONCE for the MECHANISM that emits it (the function building the line/segment/string, the decoder, the forwarding method), not the symptom noun. (3) open the one most-likely file. (4) EDIT. If a test is named, trace the symbol/class it constructs to its DEFINING module and fix THERE.
- Cap localization at ~4 calls. Then EDIT.

## Strategy: conform to the pattern
Most bugs are a DEVIATION from a pattern the surrounding code already follows. Make the buggy code look like its correct siblings (the function before/after it, or a similar function in the same file). Fix the exact deviation (wrong constant, missing guard/branch, wrong exception, off-by-one, wrong attr/arg, missing return) - nothing else.

## Workflow (recap): STEP 0 declare TARGET (no tool) -> STEP 1 confirm by reading with `sed -n 'A,Bp' file` in <=2-3 calls (re-declare once if wrong) -> get_status to watch budget (FREE) -> STEP 2 edit via ONE run_command python replace, choosing the easiest edit SHAPE (add / whole-function / one-line) -> verify -> submit_patch ONCE then STOP. Never re-emit a failed call.

## Hard rules
- NEVER modify/create/delete test files (test_*.py, *_test.py, tests/) or runner config (conftest.py, pytest.ini, pyproject.toml) - the harness resets them AND they poison your diff.
- Scratch files go to /tmp via run_command heredoc `cat > /tmp/x.py <<'EOF'`. Apply SOURCE edits with the ONE run_command python-replace shape in STEP 2. Only touch your committed TARGET source file; NEVER edit test files or conftest/pytest.ini (the harness resets them).
- Offline: no pip install. Do NOT refactor unrelated code. Do NOT run bare pytest. Do NOT conclude with an empty patch.
""", encoding='utf-8')

TASKS_PATH = DATA_DIR / 'tasks.jsonl'
tasks = load_tasks(TASKS_PATH)
print(f'Agent dir written (v22 = v21 interface + MODEL SWAP to gemma-4-12b-it-qat-w4a16-ct, NO adapter, budget 28 @ 5min): {AGENT_DIR}')
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
        return 'gemma-4-12b-it-qat-w4a16-ct'
litellm.drop_params = True
TARGET_MODEL_NAME = 'gemma-4-12b-it-qat-w4a16-ct'
def _resolve_model():
    # v22: 12b variant. Try the mirror-of-31b path layout first, then a 12b-specific glob, then any gemma config.
    cands = [
        '/kaggle/input/models/google/gemma-4/other/gemma-4-12b-it-qat-w4a16-ct/1',
        '/kaggle/input/models/google/gemma-4/Other/gemma-4-12b-it-qat-w4a16-ct/1',
        '/kaggle/input/models/google/gemma-4/other/gemma-4-12b-it-qat-w4a16-ct/2',
        '/kaggle/input/models/google/gemma-4/Other/gemma-4-12b-it-qat-w4a16-ct/2',
        '/kaggle/input/gemma-4-12b-it-qat-w4a16-ct',
    ]
    for c in cands:
        if Path(c, 'config.json').exists():
            return Path(c)
    hits = glob.glob('/kaggle/input/**/gemma-4-12b-it-qat-w4a16-ct/**/config.json', recursive=True)
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
# v22 THE REAL FIX (from Kaggle STAFF, Ryan Holbrook, + competitor Ziad Samer's repro): the 12b checkpoint
# declares `Gemma4UnifiedForConditionalGeneration` (model_type gemma4_unified), which vLLM 0.19.1 has NO native
# impl for -> Transformers-backend fallback -> crash in profile_run (`Expected hidden_size 3840, found 256` in
# v_norm). The torch.compile warning was a RED HERRING; the arch mismatch is the real killer, and enforce_eager
# does NOT fix it. STAFF FIX: override the architecture to the plain Gemma4ForCausalLM via --hf-overrides passed
# through VllmConfig(extra_args=...). The real scorer already has this; the Getting-Started notebook will show it.
# Only apply the override for the 12b variant (31b resolves natively and needs no override).
MODEL_VLLM_EXTRA_ARGS = {
    'gemma-4-12b-it-qat-w4a16-ct': (
        '--hf-overrides', '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}',
    ),
}
_extra_args = MODEL_VLLM_EXTRA_ARGS.get(TARGET_MODEL_NAME, ())
_vllm_kwargs = dict(
    model=str(MODEL_PATH), port=8000, host='127.0.0.1',
    tool_call_parser='gemma4', reasoning_parser='gemma4', max_model_len=32768,
    dtype='bfloat16' if (torch.cuda.is_available() and torch.cuda.is_bf16_supported()) else 'auto',
    gpu_memory_utilization=0.90, enable_auto_tool_choice=True,
    enable_lora=True, max_loras=8, max_lora_rank=128,
    tensor_parallel_size=tp_size, startup_timeout=60 * 20,
)
# extra_args is the staff-documented passthrough but may not exist in THIS wheelhouse's VllmConfig; try it,
# and if the kwarg is rejected, FAIL LOUD with a clear message (do not silently drop the override — without it
# the 12b server WILL crash, so a silent fallback would just reproduce the old failure).
try:
    vllm_cfg = VllmConfig(extra_args=_extra_args, **_vllm_kwargs)
    print(f'[vllm] extra_args={_extra_args} (hf-overrides arch remap for 12b)', flush=True)
except TypeError as _e:
    print(f'[vllm] VllmConfig has NO extra_args kwarg in this wheelhouse ({_e}). The 12b arch-override cannot be '
          f'applied -> 12b will not serve on this wheelhouse. Need a newer adk_submission, or run 31b.', flush=True)
    raise
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
# v22-FIX #1 (config-not-honored): the previous dev loop passed max_tool_calls/max_time as loose EvalConfig
# kwargs AND limits=build_submission_limits(); the budget silently resolved to 40/10 instead of our yaml. The
# HARNESS_README documents SWE_MAX_TOOL_CALLS / SWE_MAX_TIME_MINUTES / SWE_MAX_TURNS as the authoritative
# override read by the agent runner regardless of EvalConfig plumbing. Set them from our yaml so the DEV budget
# matches what the REAL scored harness will enforce from the same eval_config.yaml (kills the dev/eval mismatch).
os.environ['SWE_MAX_TOOL_CALLS'] = str(max_tool_calls)
os.environ['SWE_MAX_TIME_MINUTES'] = str(max_time_minutes)
if max_turns is not None:
    os.environ['SWE_MAX_TURNS'] = str(max_turns)
    os.environ['SWE_MAX_LOOP_ITERATIONS'] = str(max_turns)
print(f'[budget] FORCING via env + EvalConfig: max_tool_calls={max_tool_calls} max_time_minutes={max_time_minutes} '
      f'max_turns={max_turns} timeout_seconds={timeout_seconds}', flush=True)
PRIORITY = ["rich_4077", "rich_4079", "rich_4076", "rich_3469"]
by_iid = {t.instance_id: t for t in tasks}
rich_all = [t for t in tasks if t.repo.endswith('rich')]
priority_tasks = [by_iid[i] for i in PRIORITY if i in by_iid]
rest_rich = [t for t in rich_all if t.instance_id not in set(PRIORITY)][:1]  # v17: cut to 5 (4 word-traps + 1) for a fast read
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
# v22-FIX #3 (crash-voids-the-gate): v22 died inside evaluate_task on the LAST task (status=ERROR, empty log,
# NO SUMMARY) so the whole gate was VOID. Wrap EACH task so one task's exception records a failed row and the
# run still reaches SUMMARY. A per-task crash is now a visible 'crashed' row, not a void gate. Also flush a
# partial SUMMARY after every task so even a hard kernel kill leaves the rows-so-far in the log.
for idx, task in enumerate(SAMPLE_TASKS, start=1):
    print(f'[{idx}/{len(SAMPLE_TASKS)}] {task.instance_id} ({task.repo})...', flush=True)
    try:
        result = run_sync(evaluator.evaluate_task, task=task, task_index=idx, total_tasks=len(SAMPLE_TASKS))
        row = {'id': task.instance_id, 'repo': task.repo.split('/')[-1],
               'resolved': bool(result.resolved), 'duration_s': round(result.duration_seconds, 1),
               'tool_calls': result.tool_calls, 'patch_chars': len(result.agent_patch or ''), 'crashed': False}
        print(f'  -> resolved={result.resolved} duration={result.duration_seconds:.1f}s '
              f'tool_calls={result.tool_calls} patch_chars={len(result.agent_patch or "")}', flush=True)
    except Exception as _te:
        import traceback as _tb
        row = {'id': task.instance_id, 'repo': task.repo.split('/')[-1], 'resolved': False,
               'duration_s': -1.0, 'tool_calls': -1, 'patch_chars': 0, 'crashed': True}
        print(f'  -> CRASHED on {task.instance_id}: {type(_te).__name__}: {_te}', flush=True)
        print('  TRACEBACK:', _tb.format_exc(), flush=True)
    timing.append(row)
    # partial-SUMMARY flush: survives a hard kill of a later task
    print(f'[partial after {idx}/{len(SAMPLE_TASKS)}] ' + '; '.join(
        f"{r['id']}:res={r['resolved']},chars={r['patch_chars']},crash={r['crashed']}" for r in timing), flush=True)
tdf = pd.DataFrame(timing)
print('\n===== v22 SUMMARY (MODEL SWAP 31b->12b base, NO adapter, v21 interface, budget 28 @ 5min, 5-task; BAR: >=1 non-4077 task produces a patch AND no timeout-no-score) =====')
print(tdf.to_string(index=False))
print(f'\nRICH RESOLVED: {int(tdf.resolved.sum())}/{len(tdf)}')
for iid in PRIORITY:
    row = tdf[tdf.id == iid]
    if len(row): print(f'  {iid}: resolved={bool(row.resolved.iloc[0])} calls={int(row.tool_calls.iloc[0])} chars={int(row.patch_chars.iloc[0])} dur={row.duration_s.iloc[0]}s')
print('Max tool_calls used:', int(tdf.tool_calls.max()), '(want edits landing by ~12, not 15) | max dur:', round(tdf.duration_s.max()), 's')

# ===== CELL 5: ATTRIBUTION ANALYZER — per-task, per-mechanism diagnostics from the traces =====
# WHY: the competition is slow (1 scored sub/day) so a dev run must test MULTIPLE levers at once AND tell us
# WHICH lever produced WHICH flip. result.resolved alone can't do that. This cell reads the harness traces and
# emits a self-documenting attribution table so value is never ambiguous. It NEVER raises (diagnostics only).
import json as _json, glob as _glob, re as _re
def _analyze_traces(results_dir):
    tdir = Path(results_dir) / 'traces'
    rows = []
    for f in sorted(_glob.glob(str(tdir / 'trace_*.json'))):
        try:
            t = _json.load(open(f, encoding='utf-8'))
        except Exception as e:
            print(f'[attrib] skip {f}: {e}'); continue
        tid = Path(f).stem.replace('trace_', '')
        calls = []          # (fn, arg_signature, failed_bool)
        for s in t.get('steps', []):
            if s.get('source') != 'agent':
                continue
            obs = str(s.get('observation') or '')
            failed = bool(_re.search(r'error|not found|not present|no such|exhaust|invalid|traceback', obs, _re.I))
            for c in (s.get('tool_calls') or []):
                fn = c.get('function_name', '?')
                args = c.get('arguments', {}) or {}
                cmd = args.get('command', '') if isinstance(args, dict) else str(args)
                # classify the action
                head = (cmd.strip().split() or ['?'])[0] if cmd else fn
                is_edit = (fn == 'edit_file') or (fn == 'run_command' and (
                    'write_text' in cmd or _re.search(r'\bsed -i\b', cmd) or '.replace(' in cmd))
                is_search = fn in ('search_code', 'search_similar_code', 'get_code_neighbors') or head in ('grep', 'rg', 'find')
                is_read = fn == 'read_file' or head in ('cat', 'head', 'tail')
                klass = 'EDIT' if is_edit else ('SEARCH' if is_search else ('READ' if is_read else fn))
                sig = (fn + '|' + (cmd[:120] if cmd else _json.dumps(args)[:120]))
                calls.append((klass, sig, failed))
        n = len(calls)
        first_edit = next((i + 1 for i, c in enumerate(calls) if c[0] == 'EDIT'), None)
        n_edit = sum(1 for c in calls if c[0] == 'EDIT')
        n_edit_failed = sum(1 for c in calls if c[0] == 'EDIT' and c[2])
        n_search = sum(1 for c in calls if c[0] == 'SEARCH')
        n_read = sum(1 for c in calls if c[0] == 'READ')
        # the KEY invariant: longest run of IDENTICAL consecutive call signatures (repeat-until-death)
        max_rep = 1; cur = 1
        for i in range(1, n):
            if calls[i][1] == calls[i - 1][1]:
                cur += 1; max_rep = max(max_rep, cur)
            else:
                cur = 1
        rows.append({'id': tid, 'calls': n, 'first_edit_at': first_edit, 'n_edit': n_edit,
                     'edit_fail': n_edit_failed, 'search': n_search, 'read': n_read, 'max_repeat': max_rep})
    return rows
try:
    attrib = _analyze_traces(eval_config.results_dir)
    adf = pd.DataFrame(attrib)
    if len(adf):
        merged = tdf.merge(adf, on='id', how='left')
        print('\n===== ATTRIBUTION TABLE (per-task mechanism diagnostics) =====')
        print(merged.to_string(index=False))
        # aggregate signals that tell us WHERE value comes from
        print('\n--- aggregate mechanism signals ---')
        print(f'resolved: {int(tdf.resolved.sum())}/{len(tdf)}')
        print(f'tasks that NEVER edited (first_edit_at=None): '
              f'{int(adf.first_edit_at.isna().sum())}/{len(adf)}  <- search-death count')
        print(f'tasks with a repeat-loop (max_repeat>=3): '
              f'{int((adf.max_repeat >= 3).sum())}/{len(adf)}  <- repeat-until-death count')
        print(f'tasks with >=1 FAILED edit then more calls: '
              f'{int((adf.edit_fail >= 1).sum())}/{len(adf)}')
        print(f'mean search calls/task: {adf.search.mean():.1f} | mean read: {adf.read.mean():.1f}')
        # per-resolved-task: how did the WIN happen (so a flip is attributable)
        for _, r in merged.iterrows():
            if r.get('resolved'):
                print(f'  WIN {r.id}: first_edit_at={r.first_edit_at} edits={r.n_edit} '
                      f'search={r.search} read={r.read} max_repeat={r.max_repeat}')
    else:
        print('[attrib] no traces found to analyze')
except Exception as _e:
    print(f'[attrib] analyzer error (non-fatal): {_e}')

# ===== CELL 6: package submission.zip =====
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
