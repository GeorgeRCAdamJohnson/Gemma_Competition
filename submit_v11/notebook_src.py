# Gemma 4 Developer Agent — v11 (BUDGET + LoRA, BUNDLED ON PURPOSE under a GPU-time crunch; branched from v10)
# WHY BUNDLED (user directive, GPU budget <12 hrs/week left, NO local eval): we cannot afford two separate
# serial runs (v10 budget-only, then v11 LoRA-only). So v11 carries BOTH structural levers at once:
#   (1) tool-call budget 22 -> 40 (from v10; v9 serial showed 8/10 tasks pinned at the 22 cap).
#   (2) adapter: localizer_v1 (the trained localization LoRA, r=16, cross-quantizer onto w4a16).
# This is NOT the local "one-variable" rule — that rule is for free local iteration we no longer have. On
# Kaggle, a run is expensive; we spend it to move the number. If v11 beats v9=0/10 we KEEP it and do not
# care which lever did it. If v11 fails, we learn budget+LoRA together are insufficient on this sample.
#
# This run also DOUBLES as the Stage-2 LoRA LOAD GATE (so we don't burn a separate probe run):
#   GATE A: does vLLM start WITH enable_lora + localizer_v1 over the w4a16 model, no shape/rank error?
#   GATE B: with the adapter active, do tasks still emit NON-EMPTY patches (no regression to 0)?
# If GATE A throws, it is a DEBUGGING task on the adapter encoding/target-modules (rule 11), NOT idea-death.
#
# PRE-REGISTERED BAR (judge = real 31B on the representative-10, SERIAL):
#   - NULL to beat: v9 serial 0/10 on this exact sample.
#   - SUCCESS: >=1/10 resolved. (Any resolve beats the 0/10 null; with runs this scarce, a single clean
#     resolve on the real model is the signal we're chasing.)
#   - GATES (reported regardless): A = vLLM started with adapter; B = non-empty-patch count.
#   - CAVEAT (stated, not hidden): v11 moves TWO things vs v9, so a WIN does not attribute to budget vs LoRA.
#     We accept that trade for GPU time. If v11 wins and we later want attribution, v10 (already pushed,
#     budget-only) gives the budget-alone number for free whenever GPU allows.
#   DO NOT auto-submit to the scored LB on this alone; v6/0.12 stays sacred live-best.
# RUN: interactive Draft Session (Edit->Run All). ATTACH: wheelhouse + competition + w4a16 model +
#   comfyops/gemma-localizer-v1-adapter. SERIAL (parallel rejected — corrupts verdicts).

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

# ===== CELL 2: write agent dir (v9/v10 agent) + COPY adapter into adapters/localizer_v1 =====
from swegemma.models import load_tasks
def _resolve_input(candidates, sentinel):
    for c in candidates:
        if sentinel and (Path(c) / sentinel).exists(): return Path(c)
        if not sentinel and Path(c).is_dir(): return Path(c)
    hits = glob.glob(f'/kaggle/input/**/{sentinel}', recursive=True) if sentinel else []
    if hits: return Path(hits[0]).parent
    raise FileNotFoundError(f'resolve failed: {candidates} + glob {sentinel!r}; /kaggle/input={sorted(glob.glob("/kaggle/input/*"))}')
DATA_DIR = _resolve_input([
    '/kaggle/input/competitions/gemma-4-developer-agent',   # batch/scoring
    '/kaggle/input/gemma-4-developer-agent',                 # interactive Draft Session
], 'tasks.jsonl')
print(f'[data] DATA_DIR = {DATA_DIR}')

# locate the trained adapter among mounted inputs (ATTACH comfyops/gemma-localizer-v1-adapter first).
# the dataset was uploaded in zip mode, so Kaggle may mount it as a .zip OR an unzipped dir — handle both.
import zipfile
_adapter_cfg = glob.glob('/kaggle/input/**/adapter_config.json', recursive=True)
if not _adapter_cfg:
    _zips = glob.glob('/kaggle/input/**/localizer_v1*.zip', recursive=True) or glob.glob('/kaggle/input/**/*.zip', recursive=True)
    for z in _zips:
        ex = Path('/tmp/_adapter_unzip') / Path(z).stem
        ex.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(z) as zf: zf.extractall(ex)
        hit = glob.glob(str(ex / '**' / 'adapter_config.json'), recursive=True)
        if hit:
            _adapter_cfg = hit; break
assert _adapter_cfg, ('localizer_v1 adapter NOT mounted. ATTACH comfyops/gemma-localizer-v1-adapter to this '
                      f'session. /kaggle/input={sorted(glob.glob("/kaggle/input/*"))}')
ADAPTER_SRC = Path(_adapter_cfg[0]).parent
print(f'[adapter] source = {ADAPTER_SRC}')

WORKING_DIR = Path('/kaggle/working'); WORKING_DIR.mkdir(parents=True, exist_ok=True)
AGENT_DIR = WORKING_DIR / 'submission'
if AGENT_DIR.exists(): shutil.rmtree(AGENT_DIR)
(AGENT_DIR / 'prompts').mkdir(parents=True, exist_ok=True)
(AGENT_DIR / 'configs').mkdir(parents=True, exist_ok=True)
# copy ONLY the 2 allowed files into the submission adapters/ dir
dst = AGENT_DIR / 'adapters' / 'localizer_v1'; dst.mkdir(parents=True, exist_ok=True)
for fn in ('adapter_config.json', 'adapter_model.safetensors'):
    shutil.copy2(ADAPTER_SRC / fn, dst / fn)
sz = sum(f.stat().st_size for f in dst.glob('*'))
print(f'[adapter] copied -> {dst} ({sz/1e6:.1f} MB); files: {[f.name for f in dst.glob("*")]}')
assert sz < 3 * 1024**3, 'adapter over 3GiB cap'

# v11 agent.yaml = v9/v10 agent + `adapter: localizer_v1` on the root coder. Same tools, no sub-agent.
(AGENT_DIR / 'agent.yaml').write_text('''name: sibling_conform_agent
model: gemma-4-31b-it-qat-w4a16-ct
adapter: localizer_v1
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

# sampling: same as v9/v10/v6 (temp 0.2, thinking_budget 512). thinking_budget is an allowed field (0-32768,
# HARNESS_FACTS); no change needed for LoRA. Keeping 512 so sampling is not an extra moving part.
(AGENT_DIR / 'configs' / 'sampling.yaml').write_text('''temperature: 0.2
top_p: 0.95
max_output_tokens: 6144
thinking_config:
  thinking_budget: 512
  include_thoughts: true
''', encoding='utf-8')

# eval_config = v10 (budget 40, turns 60).
(AGENT_DIR / 'eval_config.yaml').write_text('''evaluation:
  max_time_minutes: 5
  max_tool_calls: 40
  max_turns: 60
  timeout_seconds: 120
''', encoding='utf-8')

# system.md = v10's prompt verbatim (budget line says ~40). The adapter is the new lever; the prompt is held.
(AGENT_DIR / 'prompts' / 'system.md').write_text('''You are an expert autonomous software engineer. You have a HARD budget of ~40 tool calls and 5 minutes. BE DECISIVE AND FAST.

## The one rule that matters: EDIT EARLY, DON'T EXPLORE.
You will run out of time if you keep searching. Spend AT MOST 3-4 tool calls locating the bug, then MAKE YOUR EDIT. One good minimal fix beats endless exploration. If unsure, make your best minimal change and submit - a plausible patch scores, endless searching scores nothing.

## Do NOT waste tool calls (this is what makes you run out before you fix the bug)
Your budget is small. Most failures are running out of calls while still searching. Obey:
- BATCH your searches. Need to find several symbols? Use ONE grep with alternation: `grep -nE 'isclass|currentframe|zlib|escape|_svg_hash' file.py` - not one grep per symbol. One call, all locations.
- NEVER repeat a search that already failed. If a grep returned nothing, a slightly reworded version of the SAME grep will also return nothing. Do not run it again. Change approach or move on.
- NEVER repeat a tool CALL that returned the SAME error. If a tool call fails (e.g. "mandatory parameter filepath not present"), the identical call will fail identically - do NOT retry it unchanged. Read the error, FIX the arguments it names, and call once more; if it fails a second time, switch tools (e.g. use run_command heredoc `cat > /path <<'EOF'` instead of write_file) or abandon that step. Looping the same failing call wastes your whole budget and times you out with a 0-char patch.
- After 2 searches that return nothing useful, STOP searching. Open the single most likely file with read_file and make your best edit from what you can see. Guessing an edit beats burning the budget to zero with a 0-char patch.
- Reading the same file region twice is a wasted call. Read once, remember it.
Every call you save on searching is a call you can spend making or correcting the fix.

## Strategy: conform to the pattern
Most bugs are a DEVIATION from a pattern the surrounding code already follows. Make the buggy code look like its correct siblings (the function before/after it, or similar functions in the same file). Fix the exact deviation (wrong constant, missing guard/branch, wrong exception, off-by-one, wrong attr/arg, missing return) - nothing else.

## Match the EXACT contract the problem describes (this is what the hidden tests check)
The hidden test asserts a PRECISE observable contract, not just "the behavior is roughly right". When your fix introduces or changes a user-facing string, error message, exception type, status code, or validation, you MUST match the exact wording and cover every obvious input variant:
- ERROR / VALIDATION messages: use the exact phrasing the problem statement implies, and mirror the style of the SIBLING check already in the file (same message shape, same field-name interpolation). Do NOT invent your own wording - a test often does `pytest.raises(..., match="exact phrase")`, so a paraphrase FAILS even when the logic is right.
- PHRASE THE MESSAGE IN THE PROBLEM'S OWN VOCABULARY, not a mechanical description of your check. The hidden test's expected message echoes the WORDS the problem uses to describe the bad state. If the problem says the data is "multi-line content", the message should assert it "must be a single line" (mirror the problem's own adjective/noun - here "multi-line" -> "single line") - do NOT write your own mechanical phrasing like "must not contain newlines". Scan the problem statement for the noun/adjective it uses for the invalid condition and build the message from THAT word, interpolating the field name the same way the sibling check does.
- INPUT VARIANTS: if you reject newlines, reject "\\n" AND "\\r" AND "\\r\\n". If you guard one special char, guard the whole obvious class. Tests parametrize across all of them.
- Apply the change to EVERY field/argument/branch the problem mentions, not just the first - if the problem says "id or event", fix BOTH, mirroring how an existing validated field is wired.
- A self-written test only counts as verification if it asserts the SAME exact string and the SAME variants the problem implies. If your test passes but only checks your own paraphrase, it proves nothing. Prefer asserting the behavior described in the problem's own words.

## Workflow (tight)
1. Read the problem statement. Extract the file/function/error AND the exact contract (messages, variants, every field named). Open the code with read_file (or ONE batched `grep -nE` via run_command if no path given). MAX 3-4 locate calls.
2. Make the minimal fix with edit_file (small edits only). Match existing conventions/strings/types EXACTLY, including the sibling's message style.
3. Call submit_patch ONCE. The moment it returns status "ok", you are DONE: write a one-sentence summary and make NO more tool calls. NEVER call submit_patch twice.

## Hard rules
- NEVER modify/create/delete test files (test_*.py, *_test.py, tests/) or runner config (conftest.py, pytest.ini, pyproject.toml) - the harness resets them; it pollutes your diff or auto-fails.
- write_file is JAILED to /workspace and rejects /tmp. For scratch, use run_command heredoc: `cat > /tmp/x.py <<'EOF'`. For a NEW repo file, use run_command heredoc to the real path. Use edit_file ONLY for existing files.
- Offline: no pip install. Do NOT refactor unrelated code. Do NOT run bare pytest (it times out) - if you test, run ONLY the one target test.
- Do NOT conclude without a non-empty patch.
''', encoding='utf-8')

TASKS_PATH = DATA_DIR / 'tasks.jsonl'
tasks = load_tasks(TASKS_PATH)
print(f'Agent dir written (v11 = v10 budget + adapter localizer_v1): {AGENT_DIR}')
print(f'Loaded {len(tasks)} tasks')

# ===== CELL 3: start vLLM server WITH the adapter — GATE A (watch this cell's logs) =====
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
print(f'[adapter] discover_adapters found: {adapters}')
assert adapters, 'discover_adapters found NO adapters — wiring is wrong before vLLM even starts'
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
print('[gate A] starting vLLM WITH enable_lora + localizer_v1 over w4a16 — watch for a LoRA-load error...', flush=True)
server_instance.start()   # <-- GATE A: incompatible adapter throws HERE.
print(f'[gate A PASS] vLLM started on {server_instance.base_url} (tp={tp_size}) WITH adapter loaded', flush=True)
models = server_instance.create_model_registry(
    aliases=[declared_model, TARGET_MODEL_NAME], model_prefix='openai/', api_key='EMPTY')

# ===== CELL 4: SERIAL run — representative 10 (same as v9/v10) WITH adapter active =====
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
ANCHOR_IDS = ["rich_4077", "rich_4079", "rich_4076"]
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
    print(f'[serial {i+1}/{len(SAMPLE_TASKS)}] {t.instance_id} (adapter ACTIVE) ...', flush=True)
    row = score_one(t, i + 1, len(SAMPLE_TASKS))
    rows.append(row)
    print(f'  [done] {t.instance_id}: resolved={row["resolved"]} '
          f'dur={row["duration_s"]}s calls={row["tool_calls"]} chars={row["patch_chars"]}', flush=True)
wall = _time.time() - t_start
print(f'[serial] wall time {wall:.0f}s for {len(SAMPLE_TASKS)} tasks', flush=True)

tdf = pd.DataFrame(rows)
print(f'\n===== v11 SUMMARY  [SERIAL + LoRA]  (REPRESENTATIVE 10, SMALL_SINGLE_FILE) =====')
print('CHANGE vs v9: max_tool_calls 22->40 AND adapter: localizer_v1 (BUNDLED under GPU-time crunch).')
print('Bar: beat v9=0/10 (>=1 resolved). GATE A=vLLM-started-with-adapter. GATE B=non-empty patches.')
print(tdf.to_string(index=False))
print(f'\nRESOLVED: {tdf.resolved.sum()}/{len(tdf)}  ({100*tdf.resolved.mean():.0f}%)')
print('by repo:', tdf.groupby('repo')['resolved'].agg(['sum', 'count']).to_dict('index'))
for iid in ANCHOR_IDS:
    row = tdf[tdf.id == iid]
    if len(row): print(f'  anchor {iid}: resolved={bool(row.resolved.iloc[0])}')
nonempty = int((tdf.patch_chars > 0).sum())
print(f'[gate A] vLLM started WITH adapter: PASS (reached the eval loop)')
print(f'[gate B] non-empty patches with adapter active: {nonempty}/{len(tdf)} '
      f'-> {"PASS (adapter does not break generation)" if nonempty == len(tdf) else "CHECK (some empty — inspect)"}')
print(f'Max tool_calls used: {int(tdf.tool_calls.max())} (cap 40) | max dur: {round(tdf.duration_s.max())}s (cap 300)')
_over22 = tdf[tdf.tool_calls > 22]
print(f'  tasks that used >22 calls (only possible with the raised cap): {list(_over22.id)} ({len(_over22)}/10)')

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
