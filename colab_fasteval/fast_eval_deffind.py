# FAST-EVAL DEFFIND GATE (Colab, quota-free, warm-server) — E4B, ca5 vs find-def skill
# Adapted from the recovered fast_eval_colab.py (the "N configs / warm session" dev gate). Changes:
#   - MODEL = E4B w4a16 (the exact Kaggle checkpoint), not 31B -> faithful E4B resolves, not GGUF-noisy.
#   - write_agent_dir ALSO writes a skills/ tree (find-def variant ships a skill).
#   - VARIANTS = {control: ca5, deffind: ca5 + MIRROR/DEFINITION rule + find-def skill}.
#   - TASKS = the 7 ref-vs-def targets + 3 stable guards, REPS each (E4B is noisy at n=1).
# This is the DEV GATE: watch (a) does find-def fire, (b) does the agent edit the DEFINITION file,
# (c) do the LOC-only targets (rich_4077/3067/3480, fastapi_14492) convert. Winners -> Kaggle scored slot.
#
# PREREQ in Colab: upload kaggle.json to /content (from google.colab import files; files.upload()).
# Paste the ca5 system.md into /content/_ca5_system.md and the find-def prompt+script inline below,
# OR clone this repo into /content and point SRC at local_eval/parity_rig/agent_ctrl_e4b{,_deffind}.

# ===== CELL 1: Kaggle auth + pull E4B model, wheelhouse, comp data =====
import os, sys, glob, subprocess
from pathlib import Path
os.makedirs('/root/.kaggle', exist_ok=True)
if os.path.exists('/content/kaggle.json'):
    subprocess.run(['cp', '/content/kaggle.json', '/root/.kaggle/kaggle.json'])
    os.chmod('/root/.kaggle/kaggle.json', 0o600)
subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'kaggle'], check=True)
DATA = Path('/content/data'); WHEELS = Path('/content/wheels'); MODELDIR = Path('/content/model')
for d in (DATA, WHEELS, MODELDIR): d.mkdir(parents=True, exist_ok=True)
def sh(cmd):
    print('$', cmd); subprocess.run(cmd, shell=True, check=True)
# competition data (tasks.jsonl + snapshots + graphs + embeddings)
sh(f'kaggle competitions download -c gemma-4-developer-agent -p {DATA}')
sh(f'cd {DATA} && unzip -oq gemma-4-developer-agent.zip')
# wheelhouse
sh(f'kaggle datasets download metric/gemma-4-developer-agent-wheelhouse -p {WHEELS}')
sh(f'cd {WHEELS} && unzip -oq gemma-4-developer-agent-wheelhouse.zip')
# E4B w4a16 model (the exact scorer checkpoint)
sh(f'kaggle models instances versions download google/gemma-4/other/gemma-4-e4b-it-qat-w4a16-ct/2 -p {MODELDIR}')
for z in glob.glob(f'{MODELDIR}/*.zip') + glob.glob(f'{MODELDIR}/*.tar.gz'):
    sh(f'cd {MODELDIR} && (unzip -oq "{z}" || tar xzf "{z}")')

# ===== CELL 2: install wheelhouse (vllm + swegemma stack) =====
whls = sorted(glob.glob(f'{WHEELS}/**/*.whl', recursive=True))
tmp = Path('/content/_whl'); tmp.mkdir(exist_ok=True)
for w in whls:
    name = os.path.basename(w)
    if 'cu128' in name and '+' not in name:
        name = name.replace('cu128', '+cu128')
    t = tmp / name
    if not t.exists():
        try: os.symlink(w, t)
        except FileExistsError: pass
if list(tmp.glob('*.whl')):
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', '--no-deps', '--force-reinstall',
                    *[str(p) for p in tmp.glob('*.whl')]], check=True)
print('wheelhouse installed')

# ===== CELL 3: start vLLM ONCE (warm E4B server, tp=1) =====
import torch, litellm
from adk_submission import VllmConfig, VllmServer, discover_adapters
litellm.drop_params = True
TARGET = 'gemma-4-e4b-it-qat-w4a16-ct'
MODEL_PATH = Path(sorted(glob.glob(f'{MODELDIR}/**/config.json', recursive=True), key=len)[0]).parent
print('MODEL_PATH =', MODEL_PATH)
vllm_cfg = VllmConfig(
    model=str(MODEL_PATH), port=8000, host='127.0.0.1',
    tool_call_parser='gemma4', reasoning_parser='gemma4', max_model_len=32768,
    dtype='bfloat16' if torch.cuda.is_bf16_supported() else 'auto',
    gpu_memory_utilization=0.92, enable_auto_tool_choice=True,
    enable_lora=False, tensor_parallel_size=1, startup_timeout=60 * 20,
)
SERVER = {'inst': None, 'models': None}

# ===== CELL 4: warm variant loop =====
import asyncio, concurrent.futures, shutil, yaml, logging
import pandas as pd
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.apps._configs import EventsCompactionConfig
from swegemma.models import load_tasks
from swegemma.config import EvalConfig, build_submission_limits, ALLOWED_ADAPTER_EXTENSIONS
from swegemma.evaluate import Evaluator
try:
    from swegemma.models.discovery import validate_single_declared_model
except Exception:
    def validate_single_declared_model(agent_dir): return TARGET
for _n in ('swegemma.sandbox.subprocess', 'asyncio', 'LiteLLM', 'litellm'):
    logging.getLogger(_n).setLevel(logging.CRITICAL)

TASKS_PATH = DATA / 'tasks.jsonl'
TASKS = load_tasks(TASKS_PATH); BY = {t.instance_id: t for t in TASKS}
# 7 ref-vs-def targets (4 LOC-only + 3 content-hard) + 3 stable guards
TARGETS = ['rich_4077', 'rich_3067', 'rich_3480', 'fastapi_14492', 'fastapi_14372', 'fastapi_14458', 'fastapi_9555']
GUARDS = ['rich_3006', 'rich_3905', 'fastapi_14301']
COHORT = TARGETS + GUARDS
REPS = 3

def run_sync(fn, *a, **k):
    try: loop = asyncio.get_running_loop()
    except RuntimeError: loop = None
    if loop and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(fn(*a, **k))).result()
    return asyncio.run(fn(*a, **k))

def write_agent_dir(root: Path, system_md: str, skill_files: dict | None = None):
    """Write a variant agent dir. skill_files = {relpath: text} adds a skills/ tree + the skills: list."""
    if root.exists(): shutil.rmtree(root)
    (root / 'prompts').mkdir(parents=True); (root / 'configs').mkdir(parents=True)
    tools = ("  - run_command\n  - read_file\n  - edit_file\n  - write_file\n  - get_status\n"
             "  - submit_patch\n  - get_code_neighbors\n  - search_similar_code\n  - get_code_subgraph\n")
    skills_block = ""
    if skill_files:
        names = sorted({rel.split('/')[0] + '/' + rel.split('/')[1] for rel in skill_files})  # skills/<name>
        skills_block = "skills:\n" + "".join(f"  - {n}\n" for n in names)
        for rel, text in skill_files.items():
            p = root / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(text.encode('utf-8'))
    (root / 'agent.yaml').write_text(
        f"name: sibling_conform_agent\nmodel: {TARGET}\ninstruction: !include prompts/system.md\n"
        "tools:\n" + tools + skills_block + "generate_content_config: !include configs/sampling.yaml\n",
        encoding='utf-8')
    (root / 'configs' / 'sampling.yaml').write_text(
        "temperature: 0.2\ntop_p: 0.95\nmax_output_tokens: 5000\n"
        "thinking_config:\n  thinking_budget: 4096\n  include_thoughts: true\n", encoding='utf-8')
    (root / 'eval_config.yaml').write_text(
        "evaluation:\n  max_time_minutes: 8\n  max_tool_calls: 28\n  max_turns: 120\n  timeout_seconds: 300\n",
        encoding='utf-8')
    (root / 'prompts' / 'system.md').write_text(system_md, encoding='utf-8')
    return root

def ensure_server(agent_dir: Path):
    if SERVER['inst'] is None:
        adapters = discover_adapters(str(agent_dir), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)
        inst = VllmServer(vllm_cfg, adapter_manifest=adapters); inst.start()
        declared = validate_single_declared_model(agent_dir)
        SERVER['inst'] = inst
        SERVER['models'] = inst.create_model_registry(aliases=[declared, TARGET], model_prefix='openai/', api_key='EMPTY')
        print('vLLM warm server up:', inst.base_url)
    return SERVER['models']

def eval_variant(name, agent_dir, task_ids, rep):
    models = ensure_server(agent_dir)
    ev = (yaml.safe_load((agent_dir / 'eval_config.yaml').read_text()) or {}).get('evaluation', {})
    limits, gen = build_submission_limits()
    cfg = EvalConfig(
        tasks_path=TASKS_PATH, snapshots_dir=DATA / 'snapshots', results_dir=Path('/content/_res') / f'{name}_r{rep}',
        submission_dir=agent_dir, models=models, sandbox='subprocess',
        timeout_seconds=int(ev.get('timeout_seconds', 300)), max_time_minutes=float(ev.get('max_time_minutes', 8)),
        max_tool_calls=int(ev.get('max_tool_calls', 28)), max_turns=int(ev.get('max_turns', 120)),
        limits=limits, generation_constraints=gen,
        context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10),
        events_compaction_config=EventsCompactionConfig(compaction_interval=15, overlap_size=2,
            token_threshold=14336, event_retention_size=5),
        graph_dir=str(DATA / 'graphs'), embeddings_dir=str(DATA / 'embeddings'),
        wheels_dir=DATA / 'wheels', verbose=False)
    ev_obj = Evaluator(cfg); rows = []
    for i, tid in enumerate(task_ids, 1):
        r = run_sync(ev_obj.evaluate_task, task=BY[tid], task_index=i, total_tasks=len(task_ids))
        rows.append({'variant': name, 'rep': rep, 'id': tid, 'resolved': bool(r.resolved),
                     'calls': r.tool_calls, 'dur': round(r.duration_seconds, 1), 'chars': len(r.agent_patch or '')})
        print(f'  [{name} r{rep}] {tid}: resolved={r.resolved} calls={r.tool_calls} chars={len(r.agent_patch or "")}')
    return rows

# ---- VARIANTS: paste ca5 system.md + find-def prompt/script, or load from a cloned repo ----
# If the repo is cloned at /content/Gemma_Competition, read the real bundles (preferred):
REPO = Path('/content/Gemma_Competition/local_eval/parity_rig')
if (REPO / 'agent_ctrl_e4b' / 'prompts' / 'system.md').exists():
    CA5_SYS = (REPO / 'agent_ctrl_e4b' / 'prompts' / 'system.md').read_text(encoding='utf-8')
    DEF_SYS = (REPO / 'agent_ctrl_e4b_deffind' / 'prompts' / 'system.md').read_text(encoding='utf-8')
    DEF_SKILL = {
        'skills/find-def/SKILL.md': (REPO / 'agent_ctrl_e4b_deffind' / 'skills' / 'find-def' / 'SKILL.md').read_text(encoding='utf-8'),
        'skills/find-def/scripts/find_def.py': (REPO / 'agent_ctrl_e4b_deffind' / 'skills' / 'find-def' / 'scripts' / 'find_def.py').read_text(encoding='utf-8'),
    }
else:
    CA5_SYS = Path('/content/_ca5_system.md').read_text(encoding='utf-8')
    DEF_SYS = Path('/content/_deffind_system.md').read_text(encoding='utf-8')
    DEF_SKILL = {'skills/find-def/SKILL.md': Path('/content/_find_def_SKILL.md').read_text(encoding='utf-8'),
                 'skills/find-def/scripts/find_def.py': Path('/content/_find_def.py').read_text(encoding='utf-8')}

VARIANTS = {
    'A_control': (CA5_SYS, None),
    'B_deffind': (DEF_SYS, DEF_SKILL),
}

all_rows = []
for rep in range(1, REPS + 1):
    for name, (smd, skills) in VARIANTS.items():
        ad = write_agent_dir(Path(f'/content/_agents/{name}'), smd, skills)
        all_rows += eval_variant(name, ad, COHORT, rep)

df = pd.DataFrame(all_rows)
df.to_csv('/content/deffind_results.csv', index=False)
print('\n===== DEFFIND GATE SUMMARY (7 ref-vs-def targets + 3 guards, %d reps) =====' % REPS)
print(df.to_string(index=False))
piv = df.pivot_table(index='id', columns='variant', values='resolved', aggfunc='sum')
print('\nper-task resolved (sum over reps):'); print(piv.to_string())
print('\nby variant total resolved:'); print(df.groupby('variant')['resolved'].sum().to_string())
print('\nLOC-only targets (the convertible ones): rich_4077, rich_3067, rich_3480, fastapi_14492')
