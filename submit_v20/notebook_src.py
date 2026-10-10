# Gemma 4 Developer Agent — v18: EDIT-VIA-run_command (sidestep the malformed edit_file wall). RICH-FOCUSED.
#
# WHY (v17 data, measured): localization is now SOLVED (commit-to-path reaches the right file on all word-
# traps). The WALL moved to EDIT-EXECUTION: the model CANNOT reliably emit a valid multi-line
# edit_file(old_string=,new_string=) call - rich_4076 and rich_4070 each tried edit_file 10-15x, every one
# failed "mandatory input old_string not present", narrating "I keep forgetting old_string," never landed.
# BUT the model's run_command FALLBACK (sed/python) WORKED where edit_file failed (rich_3469, rich_4070 both
# landed via sed). run_command takes a SINGLE command string the gemma4 parser emits reliably. So v18 routes
# ALL edits through run_command (python replace one-liner / sed), the one edit mechanism the model formats
# correctly. ONE change vs v17 (STEP 2 edit mechanism); commit-to-path localization / budget 15 / 5-task KEPT.
# RISK (rule 9): sed/python edits can corrupt or touch test files -> prompt constrains to the committed
# source file + verify; the python one-liner asserts `old in s` so a miss is caught, not silently wrong.
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

# v16 eval_config: budget 15 (reach+land the edit), 24 turns (non-binding), 8 min (time not a confound for rich).
(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 8
  max_tool_calls: 15
  max_turns: 24
  timeout_seconds: 120
''', encoding='utf-8')

# v16 system.md = v15 anti-word-trap localization + EDIT-EARLY + RESERVE-TAIL + ANTI-LOOP.
(AGENT_DIR / 'prompts' / 'system.md').write_text("""You are a senior Python engineer doing a focused code review. You are NOT evaluating anything, and this task is NOT special — it is one ordinary bug in one file. Ignore PR boilerplate, emoji, discussion links, and issue numbers in the problem statement. Budget: ~15 tool calls. Be decisive.

MOVE 1 (NO tool call yet). Restate the issue as a concrete defect, one line:
`BUG: <path/file.py>::<function_or_class> — <the wrong behavior> | FIX: <the one change>`
The symptom word is rarely the fix file. Name the function that PRODUCES the behavior (what RENDERS/DECODES/FORWARDS the output), not the file whose name matches the symptom.

MOVE 2. read_file that ONE file; confirm the function exists (1-2 calls). get_status is FREE (0 budget) — call it; the moment tool_calls_remaining <= 4, stop reading and EDIT NOW. If the file was wrong, re-state BUG once with the right file, then edit.

MOVE 3. Fix it with edit_file, using the EASIEST shape:
- ADD/OVERRIDE a new self-contained unit (best): a new method, a forwarding/override method, a guard at the top. If the bug is in a shared base method, override it on the class actually used.
- WHOLE-FUNCTION replace: old_string = the entire `def name(`…end, new_string = the corrected function. Short unique anchor, no fragile inner span.
- One unique line.
edit_file has a 3-tier matcher (exact/flexible/regex) so a SHORT unique snippet is enough — no byte-perfect whitespace needed. NEVER put read_file's "NNN:" line-number prefix into old_string.

If a call FAILS, do NOT resend it — change the old_string, the shape, or the file. Never repeat a failed call. Ignore any hint to "split into smaller edits" if it makes you repeat.

MOVE 4. submit_patch once, then STOP. Never run pytest. Never touch test files, conftest.py, or pytest.ini. No pip install. Do not refactor unrelated code. Do not submit an empty patch.
""", encoding='utf-8')

TASKS_PATH = DATA_DIR / 'tasks.jsonl'
tasks = load_tasks(TASKS_PATH)
print(f'Agent dir written (v20 = v19 four levers + LEAN ~190w FRAME-OVERRIDE prompt [code-reviewer, not evaluator; restate-as-defect first]): {AGENT_DIR}')
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
for idx, task in enumerate(SAMPLE_TASKS, start=1):
    print(f'[{idx}/{len(SAMPLE_TASKS)}] {task.instance_id} ({task.repo})...', flush=True)
    result = run_sync(evaluator.evaluate_task, task=task, task_index=idx, total_tasks=len(SAMPLE_TASKS))
    timing.append({'id': task.instance_id, 'repo': task.repo.split('/')[-1],
                   'resolved': bool(result.resolved), 'duration_s': round(result.duration_seconds, 1),
                   'tool_calls': result.tool_calls, 'patch_chars': len(result.agent_patch or '')})
    print(f'  -> resolved={result.resolved} duration={result.duration_seconds:.1f}s '
          f'tool_calls={result.tool_calls} patch_chars={len(result.agent_patch or "")}', flush=True)
tdf = pd.DataFrame(timing)
print('\n===== v20 SUMMARY (v19 4 levers + LEAN frame-override prompt; A/B vs v19; budget 15, 5-task; bar: >=v19 resolved AND loss-task first-thought shorter) =====')
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
        first_thought_len = None  # len of the FIRST agent reasoning message (decisive vs ramble)
        for s in t.get('steps', []):
            if s.get('source') != 'agent':
                continue
            if first_thought_len is None:
                _msg = s.get('message') or ''
                if _msg.strip():
                    first_thought_len = len(_msg)
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
                     'edit_fail': n_edit_failed, 'search': n_search, 'read': n_read, 'max_repeat': max_rep,
                     'first_thought_chars': first_thought_len})
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
        _ft = adf.first_thought_chars.dropna()
        if len(_ft):
            print(f'first-thought chars (decisive<~300, ramble>~600): '
                  f'median={_ft.median():.0f} min={_ft.min():.0f} max={_ft.max():.0f}  '
                  f'per-task={dict(zip(adf.id, adf.first_thought_chars))}')
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
