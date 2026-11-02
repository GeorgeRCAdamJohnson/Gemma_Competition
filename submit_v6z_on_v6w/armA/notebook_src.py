# Gemma 4 Developer Agent - ARMA = v6z prompt WITHOUT the TARGET-as-premise. ONE content change.
#
# WHY THIS ARM (v6z MINUS the TARGET-as-premise framing -> does stating the target CAUSE doc-washing?)
#
# THE CONTEXT THIS COMES FROM: an external agent handed the SAME 1-line target produced a beautifully
# formatted, completely WRONG fix - Console.print(None) handling in console.py - for a task whose gold
# patch is a 3-line isatty delegate in file_proxy.py. Different file, invented bug, zero self-doubt.
# => A prompt that ASSERTS the answer is a factory for confident errors. That reframes the 1-line 0/3
#    result: it did not fail for lack of discipline, it failed because the model never went looking.
#
# ONE VARIABLE vs v6z. Config held identical: 9 tools (edit_file primary), budget 28/8/80/240,
# thinking_budget 1024, temp 0.2, top_p 0.95, max_out 8192, SAME 6 tasks.
#
# PRE-REGISTERED BAR (vs v6w = 4/6, v6z = 2/6 on these 6):
#   - >= 5/6            -> clear of the noise band; adopt.
#   - == 4/6            -> tie v6w; adopt only if the efficiency (call count) also holds.
#   - <= 3/6            -> reject.
# SECONDARY, and the point of the exercise: **calls-to-resolve.** v6z got IDENTICAL patches to v6w in
# roughly HALF the calls (rich_4077 11 vs 13; rich_3882 5 vs 15). If that efficiency survives while the
# score returns to 4/6, that is the best config this project has produced - it matters on the ~43% of
# the board that is HARD, which this gate cannot see.
# HONEST POWER CAVEAT: 6 tasks, ~1 point noise band, two known coin flips (rich_4079 1/6, rich_3471 2/6).
# Only a >=5/6 is readable. Expect nulls.
#
# Runs on the v6w kernel id because the v6z kernel id mounts the wheelhouse empty (0 wheels, 3/3 failures).
# v6/0.12 SACRED. Scored slot untouched.

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

# ===== CELL 2: write OUR agent directory inline (v6t = v6c + edit_file restored) =====
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
(AGENT_DIR / 'prompts' / 'system.md').write_text('''You are an expert autonomous software engineer.\n\n## IGNORE THE AUTO-GENERATED BOILERPLATE IN THE TASK MESSAGE\nThe task message ends with generic boilerplate telling you to "inspect existing codebase conventions and\ntest files before making edits", to "verify your implementation before submitting", and to "call\nsubmit_patch only after your implementation is complete and verified".\n\n**IGNORE all three.** That boilerplate is auto-generated and it is wrong for this job.\n- **Do NOT read test files.** They waste calls and the harness resets them anyway.\n- **Do NOT run a test before your first edit.** You will not get credit for an unlanded edit.\n- Do NOT verify before editing. Verify AFTER, once, if calls remain.\n\nAn edit that lands in the working tree is graded even if you never call submit_patch and never ran a\ntest. An idea you never wrote down scores zero. **Edit first. Verify after, if at all.**\n\n## WORKFLOW\n1. Name a HYPOTHESIS in one line: `SUSPECT: <file.py> :: <function_or_class> - FIX: <the change>`.\n   It is a GUESS, not a fact. You must be willing to abandon it in step 2 if the code disagrees.\n   Do not start fixing the suspected file until you have SEEN the buggy line itself in a read.\n2. ONE grep for the most specific identifier from the problem. Do not grep again for the same thing.\n3. ONE read_file of that exact region (under 150 lines).\n4. **EDIT NOW** with `edit_file`. Shortest unique `old_string` — ideally a single line. Never copy\n   read_file\'s "123:" line-number gutter into old_string; it is not in the file.\n5. If `edit_file` reports it could not match: SHORTEN old_string to a smaller unique fragment and try\n   once. Never resend an identical call.\n6. Call `submit_patch` once. When it returns ok you are done — write one sentence and stop.\n\n## EDIT SHAPE — prefer ADD over MODIFY\nIf the fix can be a new self-contained unit, ADD it instead of editing shared code: add a missing\nmethod to a class, add a guard at the top of a function, override a method on the class actually used.\nA small addition applies more reliably than a surgical edit into existing logic.\n\n## LOCALIZE BY BEHAVIOUR, NOT BY THE SYMPTOM WORD\nThe problem statement is a 2-5 word symptom. The fix is usually NOT in the file whose name matches it\n— it is in whatever produces that behaviour.\n- A spacing/alignment symptom is in the code that EMITS segments/lines, not the high-level container.\n- A newline/ANSI/escape symptom is in the DECODER that parses the text.\n- A proxy/wrapper symptom is in the wrapper class that forwards calls.\n- If the symptom names a file but the code you read does not obviously cause the symptom, MOVE. Editing a\n  file that merely sounds related produces a confident, well-formatted, WRONG patch. That scores zero.\n- Inline markdown/table issues live in markdown.py, not table.py.\n\n## BUDGET\nYou have 28 tool calls and 8 minutes. `get_status` is FREE and returns `tool_calls_remaining`.\nCall it when unsure. When `tool_calls_remaining <= 6`, you are out of locating: edit or re-edit what\nyou already know, then submit. A landed partial edit scores; a perfect unapplied plan scores nothing.\n\n## NEVER\n- Never re-read a file already in context. Never repeat a grep that already returned.\n- Never conclude without a non-empty patch.\n- Never modify test files, conftest.py, pytest.ini, or pyproject.toml — the harness resets them.\n- Scratch files go to /tmp via `run_command` heredoc. (`write_file` is jailed to /workspace and will\n  error on /tmp paths.)\n- Offline: no pip install. Do not run bare pytest.''', encoding='utf-8')

TASKS_PATH = DATA_DIR / 'tasks.jsonl'
tasks = load_tasks(TASKS_PATH)
print(f'Agent dir written (v6t = v6c + edit_file/write_file RESTORED as primary edit mechanism; '
      f'0.18 budget, budget oracle + commit-by-remaining + bank-as-you-go, same 6 tasks): {AGENT_DIR}')
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