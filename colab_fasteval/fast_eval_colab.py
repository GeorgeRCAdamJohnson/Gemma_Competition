# ===================================================================================================
# FAST TEST PIPELINE  (Colab, quota-free, warm-server)  — Gemma 4 Developer Agent
# ===================================================================================================
# WHY: every Kaggle run reloads the 18GB model (~minutes of GPU) then runs tasks serially = one config
# per 40-min run, burning the 45h/week quota. This harness starts vLLM ONCE on a Colab GPU and loops
# MANY agent-config variants against the warm server. Turns "1 config / run" into "N configs / session",
# off Kaggle quota. Uses the REAL swegemma Evaluator + the REAL 31B w4a16 model = trustworthy judge
# (not the local 12B proxy). tp=1 single-GPU adaptation of the harness's tp=4.
#
# RUN ON: Colab with an A100 (40GB) or RTX 6000 / L4-class (the 18GB w4a16 model fits one >=24GB card;
# A100-40 or 96GB RTX6000 are comfortable). Runtime -> Change runtime type -> GPU (A100 preferred).
#
# OUTPUT: a resolve table per variant on the rich sample, printed + saved to /content/fasteval_results.csv.
# This is the DEV GATE. Only configs that WIN here get a scored Kaggle submission.
# ---------------------------------------------------------------------------------------------------

# ===== CELL 1: Kaggle auth + pull model, wheelhouse, comp data (datacenter-speed, no home upload) =====
# Upload your kaggle.json first:  from google.colab import files; files.upload()  (pick kaggle.json)
import os, subprocess, sys, glob, json, time
from pathlib import Path

os.makedirs('/root/.kaggle', exist_ok=True)
# expects kaggle.json already uploaded to /content
if os.path.exists('/content/kaggle.json'):
    subprocess.run(['cp', '/content/kaggle.json', '/root/.kaggle/kaggle.json'])
    os.chmod('/root/.kaggle/kaggle.json', 0o600)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'kaggle'], check=True)

DATA = Path('/content/comp'); DATA.mkdir(parents=True, exist_ok=True)
WHEELS = Path('/content/wheelhouse'); WHEELS.mkdir(parents=True, exist_ok=True)
MODELDIR = Path('/content/model'); MODELDIR.mkdir(parents=True, exist_ok=True)

def sh(cmd):
    print('>', cmd); return subprocess.run(cmd, shell=True, check=False)

# 1) competition data (tasks.jsonl, snapshots, graphs, embeddings)
sh(f'kaggle competitions download -c gemma-4-developer-agent -p {DATA}')
sh(f'cd {DATA} && (unzip -o -q gemma-4-developer-agent.zip || true)')
# 2) wheelhouse (swegemma, adk_submission, adk_eval_core, vllm, ...)
sh(f'kaggle datasets download metric/gemma-4-developer-agent-wheelhouse -p {WHEELS}')
sh(f'cd {WHEELS} && (unzip -o -q gemma-4-developer-agent-wheelhouse.zip || true)')
# 3) model w4a16 (18GB) — pull from the Kaggle model (datacenter speed)
sh(f'kaggle models instances versions download google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2 -p {MODELDIR} || true')
# unpack any model archive
for arch in glob.glob(f'{MODELDIR}/**/*.tar.gz', recursive=True) + glob.glob(f'{MODELDIR}/*.tar.gz'):
    sh(f'tar -xzf "{arch}" -C "{MODELDIR}"')
print('config.json candidates:', glob.glob(f'{MODELDIR}/**/config.json', recursive=True)[:3])

# ===== CELL 2: install wheelhouse (vllm + swegemma stack) =====
whls = [w for w in glob.glob(f'{WHEELS}/*.whl') if 'cutlass' not in w.lower()]
# normalize cu128 local-version tags like the Kaggle notebook does
norm = []
for w in whls:
    base = os.path.basename(w)
    tgt = base.replace('cu128', '+cu128') if ('cu128' in base and '+' not in base) else base
    dst = f'/content/_whl/{tgt}'; os.makedirs('/content/_whl', exist_ok=True)
    if not os.path.exists(dst):
        try: os.symlink(w, dst)
        except FileExistsError: pass
    norm.append(dst)
print(f'installing {len(norm)} wheels...')
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall', *norm])
print('wheelhouse installed.')

# ===== CELL 3: start vLLM ONCE (warm server, tp=1) =====
import torch, litellm
from adk_submission import VllmConfig, VllmServer, discover_adapters
litellm.drop_params = True
TARGET = 'gemma-4-31b-it-qat-w4a16-ct'
MODEL_PATH = Path(sorted(glob.glob(f'{MODELDIR}/**/config.json', recursive=True), key=len)[0]).parent
print('MODEL_PATH =', MODEL_PATH)
vllm_cfg = VllmConfig(
    model=str(MODEL_PATH), port=8000, host='127.0.0.1',
    tool_call_parser='gemma4', reasoning_parser='gemma4', max_model_len=32768,
    dtype='bfloat16' if torch.cuda.is_bf16_supported() else 'auto',
    gpu_memory_utilization=0.92, enable_auto_tool_choice=True,
    enable_lora=True, max_loras=8, max_lora_rank=128,
    tensor_parallel_size=1,                      # <-- single-GPU adaptation (harness uses 4)
    startup_timeout=60 * 20,
)
# NOTE: server is (re)started per variant below only if adapters differ; for pure prompt/config
# variants (no adapter), we start ONCE here and reuse across all variants.
SERVER = {'inst': None, 'models': None}

# ===== CELL 4: the WARM VARIANT LOOP — define variants, eval each against the one warm server =====
import asyncio, concurrent.futures
import pandas as pd
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps._configs import EventsCompactionConfig
from swegemma.models import load_tasks
from swegemma.config import EvalConfig, build_submission_limits
from swegemma.evaluate import Evaluator
from swegemma.models.discovery import validate_single_declared_model
from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
import logging
for _n in ('swegemma.sandbox.subprocess','asyncio','LiteLLM','litellm'):
    logging.getLogger(_n).setLevel(logging.CRITICAL)

TASKS_PATH = DATA / 'tasks.jsonl'
TASKS = load_tasks(TASKS_PATH)
BY = {t.instance_id: t for t in TASKS}
RICH = ['rich_4077','rich_4079','rich_4076','rich_3469']   # the 4 word-trap exemplars (fast read)

def run_sync(fn, *a, **k):
    try: loop = asyncio.get_running_loop()
    except RuntimeError: loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(fn(*a, **k))).result()
    return asyncio.run(fn(*a, **k))

def write_agent_dir(root: Path, system_md: str, sampling_yaml: str, eval_yaml: str, with_subagent=False):
    """Write a variant agent dir. with_subagent False = single LlmAgent (v15 shape)."""
    if root.exists():
        import shutil; shutil.rmtree(root)
    (root/'prompts').mkdir(parents=True); (root/'configs').mkdir(parents=True)
    tools = "  - run_command\n  - read_file\n  - edit_file\n  - write_file\n  - get_status\n  - submit_patch\n  - get_code_neighbors\n  - search_similar_code\n  - get_code_subgraph\n"
    (root/'agent.yaml').write_text(
        "name: sibling_conform_agent\nmodel: gemma-4-31b-it-qat-w4a16-ct\n"
        "instruction: !include prompts/system.md\ntools:\n" + tools +
        "generate_content_config: !include configs/sampling.yaml\n", encoding='utf-8')
    (root/'configs'/'sampling.yaml').write_text(sampling_yaml, encoding='utf-8')
    (root/'eval_config.yaml').write_text(eval_yaml, encoding='utf-8')
    (root/'prompts'/'system.md').write_text(system_md, encoding='utf-8')
    return root

def ensure_server(agent_dir: Path):
    if SERVER['inst'] is None:
        adapters = discover_adapters(str(agent_dir), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)
        inst = VllmServer(vllm_cfg, adapter_manifest=adapters); inst.start()
        declared = validate_single_declared_model(agent_dir)
        SERVER['inst'] = inst
        SERVER['models'] = inst.create_model_registry(
            aliases=[declared, TARGET], model_prefix='openai/', api_key='EMPTY')
        print('vLLM warm server up:', inst.base_url)
    return SERVER['models']

def eval_variant(name: str, agent_dir: Path, task_ids):
    models = ensure_server(agent_dir)
    import yaml
    ev = (yaml.safe_load((agent_dir/'eval_config.yaml').read_text()) or {}).get('evaluation', {})
    limits, gen = build_submission_limits()
    cfg = EvalConfig(
        tasks_path=TASKS_PATH, snapshots_dir=DATA/'snapshots', results_dir=Path('/content/_res')/name,
        submission_dir=agent_dir, models=models, sandbox='subprocess',
        timeout_seconds=int(ev.get('timeout_seconds',120)),
        max_time_minutes=float(ev.get('max_time_minutes',5)),
        max_tool_calls=int(ev.get('max_tool_calls',12)),
        max_turns=int(ev.get('max_turns',20)),
        limits=limits, generation_constraints=gen,
        context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
        events_compaction_config=EventsCompactionConfig(compaction_interval=15, overlap_size=2,
            token_threshold=14336, event_retention_size=5),
        graph_dir=str(DATA/'graphs'), embeddings_dir=str(DATA/'embeddings'),
        wheels_dir=DATA/'wheels', verbose=False)
    ev_obj = Evaluator(cfg)
    rows = []
    for i, tid in enumerate(task_ids, 1):
        t = BY[tid]
        r = run_sync(ev_obj.evaluate_task, task=t, task_index=i, total_tasks=len(task_ids))
        rows.append({'variant': name, 'id': tid, 'resolved': bool(r.resolved),
                     'calls': r.tool_calls, 'dur': round(r.duration_seconds,1),
                     'chars': len(r.agent_patch or '')})
        print(f'  [{name}] {tid}: resolved={r.resolved} calls={r.tool_calls} dur={r.duration_seconds:.0f}s')
    return rows

# ---- DEFINE VARIANTS HERE (edit freely; server loads once) --------------------------------------
V15_SYS = (Path('/content/_v15_system.md').read_text()  # paste v15 system.md here, or inline below
           if os.path.exists('/content/_v15_system.md') else "PASTE_V15_SYSTEM_MD")
SAMPLING_256 = "temperature: 0.2\ntop_p: 0.95\nmax_output_tokens: 4096\nthinking_config:\n  thinking_budget: 256\n  include_thoughts: true\n"
EVAL_12 = "evaluation:\n  max_time_minutes: 5\n  max_tool_calls: 12\n  max_turns: 20\n  timeout_seconds: 120\n"
EVAL_16 = "evaluation:\n  max_time_minutes: 5\n  max_tool_calls: 16\n  max_turns: 26\n  timeout_seconds: 120\n"

VARIANTS = {
    'v15_b12':  (V15_SYS, SAMPLING_256, EVAL_12),
    'v15_b16':  (V15_SYS, SAMPLING_256, EVAL_16),   # budget sweep: is 12 too tight?
}

all_rows = []
for name, (smd, samp, evl) in VARIANTS.items():
    ad = write_agent_dir(Path(f'/content/_agents/{name}'), smd, samp, evl)
    all_rows += eval_variant(name, ad, RICH)

df = pd.DataFrame(all_rows)
df.to_csv('/content/fasteval_results.csv', index=False)
print('\n===== FAST-EVAL SUMMARY (rich word-trap exemplars) =====')
print(df.to_string(index=False))
print('\nby variant resolved:')
print(df.groupby('variant')['resolved'].agg(['sum','count']).to_string())
