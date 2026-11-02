"""Generate the Kaggle kernel that evaluates ca5-31B on ALL 129 local tasks on NvidiaL4.
Cloned from our working 31B kernels (machine_shape NvidiaL4, wheelhouse + 31B model source);
the only change of substance is the eval target: our snapshots/tasks instead of the hidden set.
"""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parent.parent      # .../Gemma
import os


def _env(k: str, d: str) -> str:
    return os.environ.get(k, d)


MODEL_SLUG = _env("K_MODEL", "gemma-4-31b-it-qat-w4a16-ct")
MODEL_VER = _env("K_VER", "2")
TP_OVERRIDE = _env("K_TP", "")
CONC_SET = _env("K_CONC", "4")
CAPS_SET = _env("K_CAPS", "ca5")
K_ID = _env("K_ID", "comfyops/ca5-31b-full129-eval")
K_TITLE = _env("K_TITLE", "ca5 31b full129 eval")
K_CODE = _env("K_CODE", "ca5-31b-full129.ipynb")
OUT = ROOT / "kaggle_pkg" / _env("K_OUTDIR", "push_129_off31")
OUT.mkdir(parents=True, exist_ok=True)

WHEELS = r'''
# ---------- install the competition wheelhouse (adk_submission / swegemma / adk_eval_core) ----------
import glob, os, shutil, subprocess, sys
from pathlib import Path

print("listing /kaggle/input:", sorted(os.listdir("/kaggle/input")))
CANDIDATES = [
    Path("/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse"),  # layout observed 2026-10-30
    Path("/kaggle/input/gemma-4-developer-agent-wheelhouse"),                  # legacy flat layout
    Path("/kaggle/input/gemma-4-developer-agent-wheelhouse/datasets"),
]
WHEELHOUSE_DIR = next((p for p in CANDIDATES if p.is_dir()), None)
if WHEELHOUSE_DIR is None:
    for p in glob.glob("/kaggle/input/**/gemma-4-developer-agent-wheelhouse", recursive=True):
        WHEELHOUSE_DIR = Path(p)
        break
assert WHEELHOUSE_DIR is not None, "wheelhouse dataset not mounted"
print("WHEELHOUSE:", WHEELHOUSE_DIR)

for pat in ("/usr/local/lib/python*/dist-packages/*cutlass*.pth",
            "/usr/local/lib/python*/site-packages/*cutlass*.pth"):
    for pth in glob.glob(pat):
        try:
            os.unlink(pth)
        except OSError:
            pass

tmp_whl = Path("/tmp/wheelhouse")
if tmp_whl.exists():
    shutil.rmtree(tmp_whl)
tmp_whl.mkdir(parents=True, exist_ok=True)
for w in WHEELHOUSE_DIR.glob("*.whl"):
    if "cutlass" in w.name.lower():
        continue
    name = w.name.replace("cu128", "+cu128") if ("cu128" in w.name and "+" not in w.name) else w.name
    target = tmp_whl / name
    if not target.exists():
        os.symlink(w, target)
wheels = sorted(str(w) for w in tmp_whl.glob("*.whl"))
names = [w.rsplit("/", 1)[-1] for w in wheels]
print(f"WHEELHOUSE globbed={len(wheels)} swegemma={any('swegemma' in n for n in names)}")
assert any("swegemma" in n for n in names), "wheelhouse lacks swegemma (wrong dataset version)"
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps",
                "--force-reinstall", *wheels], check=True)
import adk_submission, swegemma
print("IMPORTS OK: adk_submission", getattr(adk_submission, "__version__", "?"),
      "| swegemma", getattr(swegemma, "__version__", "?"))
'''

SETUP = r'''
import os, sys, json, subprocess, shutil, glob, base64
from pathlib import Path

# ---------- 0. PREFLIGHT: what machine did we actually get? ----------
import torch
n = torch.cuda.device_count() if torch.cuda.is_available() else 0
print("device_count:", n, "| bf16_supported:", torch.cuda.is_bf16_supported() if n else False)
for i in range(n):
    p = torch.cuda.get_device_properties(i)
    print(f"  gpu{i}: {p.name}  {p.total_memory/1e9:.1f} GB")
TP = 4 if n >= 4 else (2 if n >= 2 else 1)
print("tensor_parallel_size ->", TP)
if n == 0:
    raise SystemExit("no GPU")
if n == 1 and torch.cuda.get_device_properties(0).total_memory < 30e9:
    raise SystemExit("single <=30GB GPU: 31B will not fit; abort before burning quota")
print("PREFLIGHT OK")

# ---------- 1. Rebuild the ca5 agent dir + tasks ENTIRELY from embedded bytes ----------
print("listing /kaggle/input:", sorted(os.listdir("/kaggle/input")))
EMBED = json.loads("""__EMBED__""")

AGENT = Path("/kaggle/working/agent_ca5")
for d in ("prompts", "configs"):
    (AGENT / d).mkdir(parents=True, exist_ok=True)
WANT = {"system.md": AGENT / "prompts" / "system.md",
        "agent.yaml": AGENT / "agent.yaml",
        "sampling.yaml": AGENT / "configs" / "sampling.yaml",
        "eval_config.yaml": AGENT / "eval_config.yaml"}
for name, dst in WANT.items():
    dst.write_bytes(base64.b64decode(EMBED[name]))
    print(f"  {name}: {dst.stat().st_size} B <- embedded")

import hashlib
sha = hashlib.sha1((AGENT / "prompts" / "system.md").read_bytes()).hexdigest()[:12]
print("agent prompt sha:", sha)
assert sha == "b08b32a2438d", f"prompt drifted from ca5: {sha}"

TASKS = Path("/kaggle/working/tasks.jsonl")
import gzip
TASKS.write_bytes(gzip.decompress(base64.b64decode(EMBED["tasks.jsonl_gz"])))
n_tasks = sum(1 for l in open(TASKS) if l.strip())
print("tasks:", n_tasks, "(", TASKS.stat().st_size, "B )")
assert n_tasks == 129, n_tasks

# ---------- 2. Snapshots MUST come from the dataset: find them wherever they mounted ----------
hits = glob.glob("/kaggle/input/**/*.tgz", recursive=True)
print("tgz found under /kaggle/input:", len(hits))
SNAPS = None
if len(hits) >= 129:
    SNAPS = Path(hits[0]).parent
else:
    tars = glob.glob("/kaggle/input/**/snapshots.tar", recursive=True)
    print("snapshots.tar candidates:", tars)
    if tars:
        import tarfile
        SNAPS = Path("/tmp/snaps")
        SNAPS.mkdir(parents=True, exist_ok=True)
        if len(list(SNAPS.glob("*.tgz"))) < 129:
            print("extracting", tars[0], "->", SNAPS)
            with tarfile.open(tars[0]) as tf:
                try:
                    tf.extractall(SNAPS, filter="data")
                except TypeError:
                    tf.extractall(SNAPS)

if SNAPS is None or len(list(SNAPS.glob("*.tgz"))) < 129:
    # fail fast WITH diagnostics so one failed version still teaches us the layout
    for root in ("/kaggle/input",):
        for dirpath, dirnames, filenames in os.walk(root):
            depth = dirpath[len(root):].count(os.sep)
            if depth <= 2:
                print(f"  {dirpath}: {len(filenames)} files")
            if depth > 2:
                dirnames[:] = []
    raise SystemExit("snapshots not found (see /kaggle/input tree above)")

n_snaps = len(list(SNAPS.glob("*.tgz")))
print("snapshots:", n_snaps, "at", SNAPS)
assert n_snaps == 129, n_snaps
print("INPUTS OK")
'''

SERVE = r'''
# ---------- 2. Serve the official 31B QAT model (competition recipe) ----------
import litellm
from adk_submission import VllmConfig, VllmServer, discover_adapters

# defensive: swegemma.models.discovery was REMOVED in the current wheelhouse (module moved)
validate_single_declared_model = None
for _mp in ('swegemma.models.discovery', 'swegemma.models.registry', 'swegemma.submission',
            'swegemma.config', 'swegemma.models'):
    try:
        _m = __import__(_mp, fromlist=['validate_single_declared_model'])
        validate_single_declared_model = getattr(_m, 'validate_single_declared_model', None)
        if validate_single_declared_model is not None:
            print('[import] validate_single_declared_model <-', _mp)
            break
    except Exception:
        continue
if validate_single_declared_model is None:
    print('[import] validate_single_declared_model NOT FOUND; no-op (agent.yaml declares one model)')
    def validate_single_declared_model(agent_dir):
        return 'gemma-4-31b-it-qat-w4a16-ct'

try:
    from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
except Exception:
    ALLOWED_ADAPTER_EXTENSIONS = frozenset({'.safetensors', '.bin', '.pt', '.pth', '.gguf', '.ggml'})

litellm.drop_params = True
TARGET_MODEL_NAME = 'gemma-4-31b-it-qat-w4a16-ct'
MODEL_PATH = Path('/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2')
print("model path exists:", MODEL_PATH.exists())
if not MODEL_PATH.exists():
    hits = glob.glob('/kaggle/input/models/google/gemma-4/**/config.json', recursive=True)
    print("model config candidates:", hits[:5])
    raise SystemExit("31B model source not mounted")

declared_model = validate_single_declared_model(str(AGENT))
adapters = discover_adapters(str(AGENT), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS)
print("declared:", declared_model, "| adapters:", len(getattr(adapters, "adapters", {}) or {}))

cfg_kwargs = dict(
    model=str(MODEL_PATH), port=8000, host='127.0.0.1',
    tool_call_parser='gemma4', reasoning_parser='gemma4',
    dtype='bfloat16' if torch.cuda.is_bf16_supported() else 'auto',
    enable_auto_tool_choice=True,
    enable_lora=False,          # no adapter shipped -> frees the LoRA workspace/cache
    # vLLM defaults its served id to the model dir basename ('2'); the harness asks for the
    # friendly name, so advertise both or every LLM call 404s.
    extra_args=['--served-model-name', TARGET_MODEL_NAME, '2'],
)
ATTEMPTS = [
    dict(max_model_len=32768, gpu_memory_utilization=0.85),
    dict(max_model_len=24576, gpu_memory_utilization=0.78),
    dict(max_model_len=16384, gpu_memory_utilization=0.70),
]
server = None
for i, over in enumerate(ATTEMPTS, 1):
    try:
        print(f"[serve] attempt {i}: {over}", flush=True)
        s = VllmServer(VllmConfig(tensor_parallel_size=TP, startup_timeout=60 * 25, **cfg_kwargs, **over),
                       adapter_manifest=adapters)
        s.start()
        server = s
        print("server up:", server.base_url, "|", over, flush=True)
        break
    except Exception as e:
        msg = str(e)
        print(f"[serve] attempt {i} FAILED: {type(e).__name__}: {msg[:400]}", flush=True)
        if "out of memory" not in msg.lower() and "startup" not in msg.lower():
            raise
if server is None:
    raise SystemExit("all serve configs OOM'd - lower gpu_memory_utilization further")

_alias_map = {a: TARGET_MODEL_NAME for a in (declared_model, TARGET_MODEL_NAME) if a}
# the agent resolves its model from agent.yaml, not from our alias list: include it or
# every rep dies with "model ... does not exist" (seen 2026-10-31, E4B run, 0/129)
import re as _re2
_m2 = _re2.search(r'(?m)^\s*model:\s*(\S+)', (AGENT / 'agent.yaml').read_text(encoding='utf-8'))
_declared_in_pack = _m2.group(1) if _m2 else None
print('agent.yaml declares:', _declared_in_pack, '| serving:', TARGET_MODEL_NAME)
if _declared_in_pack:
    _alias_map[_declared_in_pack] = TARGET_MODEL_NAME
print('alias map:', _alias_map)
models = server.create_model_registry(aliases=_alias_map,
                                      model_prefix='openai/', api_key='EMPTY')
os.environ['OPENAI_BASE_URL'] = server.base_url
os.environ['OPENAI_API_KEY'] = 'EMPTY'
print("OPENAI_BASE_URL:", os.environ['OPENAI_BASE_URL'])

# Probe the exact model ids the API advertises, then prove a real completion works.
# A name mismatch here costs 2 s instead of a whole eval run.
import json as _json, urllib.request as _req
_ids = [m['id'] for m in _json.load(_req.urlopen(server.base_url.rstrip('/') + '/models'))['data']]
print('served model ids:', _ids)
if TARGET_MODEL_NAME not in _ids:
    raise SystemExit(f'served ids {_ids} do not include {TARGET_MODEL_NAME!r}')
# probe the id the AGENT will actually ask for, not just the one we advertised
for _probe_model in {_declared_in_pack, TARGET_MODEL_NAME} - {None}:
    _body = _json.dumps({'model': _probe_model, 'max_tokens': 8,
                         'messages': [{'role': 'user', 'content': 'Reply with OK'}]}).encode()
    _r = _req.Request(server.base_url.rstrip('/') + '/chat/completions', data=_body,
                      headers={'Content-Type': 'application/json', 'Authorization': 'EMPTY'})
    _resp = _json.load(_req.urlopen(_r))
    print('SMOKE OK (%s) ->' % _probe_model, repr(_resp['choices'][0]['message'].get('content'))[:60], flush=True)
'''

EVAL = r'''
# ---------- 3. Evaluate ALL 129 tasks (resumable, chunked so one crash is not fatal) ----------
OUT = Path("/kaggle/working/results")
OUT.mkdir(parents=True, exist_ok=True)
res = OUT / "task_results.jsonl"          # rewritten by EVERY invocation: holds only the current chunk
accum = OUT / "task_results.all.jsonl"    # our durable accumulator across chunks / restarts

# --- mirror the GRADER: it reads eval_config.yaml (timeout_seconds, max_tool_calls,
# max_time_minutes, max_turns) and enforces those caps. The CLI defaults are
# 60 minutes / no call cap, which is NOT the board. Without this, our pool score
# is measured in a regime the grader never runs.
import yaml as _yaml
_cfg = {}
_ec = Path(AGENT) / "eval_config.yaml"
if _ec.exists():
    _raw = _yaml.safe_load(_ec.read_text()) or {}
    _cfg = _raw.get("evaluation", _raw) or {}
CAPS = []
for _k, _flag in (("max_tool_calls", "--max-tool-calls"),
                  ("max_time_minutes", "--max-time-minutes"),
                  ("max_turns", "--max-turns")):
    if _cfg.get(_k) is not None:
        CAPS += [_flag, str(_cfg[_k])]
if os.environ.get("BOARD_CAPS", "1") == "0":
    CAPS = []
    print("WARNING: BOARD_CAPS=0 -> running in the harness default regime (60 min, no call cap)")
print("board caps:", CAPS or "(none)", flush=True)

rows_all = []
if accum.exists():
    rows_all = [json.loads(l) for l in open(accum) if l.strip()]
done = {r["instance_id"] for r in rows_all}
all_ids = [json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()]
todo = [t for t in all_ids if t not in done]
print(f"todo {len(todo)}/{len(all_ids)} (resumed {len(done)})")

CONC = "4"
CHUNK = 20
for i in range(0, len(todo), CHUNK):
    batch = todo[i:i + CHUNK]
    cmd = [sys.executable, "-m", "swegemma", "eval",
           "--tasks", str(TASKS), "--snapshots-dir", str(SNAPS),
           "--results-dir", str(OUT), "--submission-dir", str(AGENT),
           "--sandbox", "subprocess", "--concurrency", CONC, "--display", "quiet"] + CAPS
    for t in batch:
        cmd += ["--task-id", t]
    print(f"--- chunk {i//CHUNK+1}: {len(batch)} tasks ---", flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True)
    print("  rc:", p.returncode, (p.stdout or "")[-300:], (p.stderr or "")[-300:], flush=True)

    # harvest this chunk's rows into the accumulator before the next chunk destroys them
    seen = {r["instance_id"] for r in rows_all}
    if res.exists():
        for l in open(res):
            if l.strip():
                r = json.loads(l)
                if r["instance_id"] not in seen:
                    rows_all.append(r)
                    seen.add(r["instance_id"])
    with open(accum, "w") as f:
        for r in rows_all:
            f.write(json.dumps(r) + "\n")
    k_chunk = sum(int(bool(r.get("resolved"))) for r in rows_all)
    print(f"  cumulative: {k_chunk}/{len(rows_all)}", flush=True)

rows = rows_all
k = sum(int(bool(r.get("resolved"))) for r in rows)
print(f"\n=== ca5-31B FULL POOL: {k}/{len(rows)}" + (f" = {k/len(rows):.3f}" if rows else "") + " ===")
print("refs: 31B-v10 34/129 | E4B ca5 15/129 & 10/129 | off12(12B) pending")
by = {}
for r in rows:
    repo = r.get("repo") or r["instance_id"].split("_")[0]
    d = by.setdefault(repo, [0, 0]); d[0] += int(bool(r.get("resolved"))); d[1] += 1
for repo, (kk, nn) in sorted(by.items()):
    print(f"  {repo:<22} {kk:>3}/{nn:<3}")
with open("/kaggle/working/summary.json", "w") as f:
    json.dump({"resolved": k, "total": len(rows), "rate": (k / len(rows) if rows else 0),
               "by_repo": by, "prompt_sha": sha}, f, indent=2)
print("wrote /kaggle/working/summary.json")
'''


def cell(src, kind="code"):
    if kind == "code":
        return {"cell_type": "code", "metadata": {}, "execution_count": None,
                "outputs": [], "source": src.splitlines(keepends=True)}
    return {"cell_type": "markdown", "metadata": {}, "source": src.splitlines(keepends=True)}


# embed the four ca5 agent files so the notebook never depends on dataset version pinning
import base64
SRC_AGENT = ROOT / "local_eval" / "parity_rig" / "agent_ctrl_v5"
FILES = {
    "system.md": SRC_AGENT / "prompts" / "system.md",
    "agent.yaml": SRC_AGENT / "agent.yaml",
    "sampling.yaml": SRC_AGENT / "configs" / "sampling.yaml",
    "eval_config.yaml": SRC_AGENT / "eval_config.yaml",
    "tasks.jsonl": ROOT / "comp_files" / "tasks.jsonl",
}
embed = {}
for k, v in FILES.items():
    raw = v.read_bytes()
    if k == "tasks.jsonl":
        import gzip
        embed["tasks.jsonl_gz"] = base64.b64encode(gzip.compress(raw, 9)).decode()
    else:
        embed[k] = base64.b64encode(raw).decode()

# The 0.20 board submission = ca5 prompt + v10 caps; the E4B 0.03 submission used the
# same v10 caps. Overriding eval_config is what makes an arm board-comparable.
if CAPS_SET == "v10":
    V10 = "evaluation:\n  max_time_minutes: 6\n  max_tool_calls: 40\n  max_turns: 60\n  timeout_seconds: 120\n"
    embed["eval_config.yaml"] = base64.b64encode(V10.encode()).decode()
    print("caps: v10-as-40/6 (NOTE: our log defines 'v10 caps' as 8 min / 28 calls)")
else:
    print("caps: as shipped in the agent pack (ca5 default = 28 calls / 8 min / 120 turns / 300 s)")

# The pack's agent.yaml declares its model. Serving a DIFFERENT model without rewriting
# this makes the agent ask for an id the server never advertises -> NotFoundError on every rep.
import re as _re
_ag_txt = base64.b64decode(embed["agent.yaml"]).decode("utf-8")
_declared = (_re.search(r"(?m)^\s*model:\s*(\S+)", _ag_txt) or [None, None])[1]
print("agent.yaml declares model:", _declared)
if _declared and _declared != MODEL_SLUG:
    _ag_new = _re.sub(r"(?m)^(\s*model:\s*)\S+", r"\g<1>" + MODEL_SLUG, _ag_txt, count=1)
    embed["agent.yaml"] = base64.b64encode(_ag_new.encode()).decode()
    print("  rewrote agent.yaml model ->", MODEL_SLUG,
          "(prompt untouched; sha asserted in cell 1)")
import hashlib
assert hashlib.sha1(FILES["system.md"].read_bytes()).hexdigest()[:12] == "b08b32a2438d", "not ca5"
SETUP_RENDERED = SETUP.replace("__EMBED__", json.dumps(embed))
assert "__EMBED__" not in SETUP_RENDERED
print("embedded agent files:", {k: len(v) for k, v in embed.items()})

# --- parametrize the serve/eval cells so E4B/12B/31B share byte-identical logic ---
SERVE_RENDERED = (SERVE
                  .replace("gemma-4-31b-it-qat-w4a16-ct", MODEL_SLUG)
                  .replace(f"gemma-4-e4b-it-qat-w4a16-ct/2", f"{MODEL_SLUG}/{MODEL_VER}")
                  .replace(f"gemma-4-31b-it-qat-w4a16-ct/2", f"{MODEL_SLUG}/{MODEL_VER}"))
if TP_OVERRIDE:
    SERVE_RENDERED = SERVE_RENDERED.replace("tensor_parallel_size=TP", f"tensor_parallel_size={TP_OVERRIDE}")
EVAL_RENDERED = EVAL.replace('CONC = "4"', f'CONC = "{CONC_SET}"')
assert MODEL_SLUG in SERVE_RENDERED
print(f"model: {MODEL_SLUG}/{MODEL_VER} | tp={TP_OVERRIDE or 'auto'} | conc={CONC_SET} | caps={CAPS_SET}")


nb = {
    "cells": [
        cell("# ca5 on ALL 129 local tasks (NvidiaL4)\n\n"
             "Purpose: the column we have never measured — the **scored model family** on the full local pool,\n"
             "under the **v10 caps used by the 0.20 and the E4B 0.03 board submissions** (6 min / 40 calls).\n\n"
             "| arm | full-129 | model |\n|---|---|---|\n| 31B v10 | 34/129 | 31B |\n"
             "| ca5 | 15/129 | **12B** (was mislabeled E4B) |\n| ca5_v2 | 10/129 | **12B** (was mislabeled E4B) |\n"
             "| **this run** | **?** | see `model id` printed in cell 1 |\n\n"
             "Prompt held to ca5 (`b08b32a2438d`, asserted in cell 1). Same harness, same tasks, same caps.\n"
             "Caps come from `eval_config.yaml` and are passed to the evaluator, mirroring the grader.", "markdown"),
        cell(WHEELS), cell(SETUP_RENDERED), cell(SERVE_RENDERED), cell(EVAL_RENDERED),
    ],
    "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                 "language_info": {"name": "python"}},
    "nbformat": 4, "nbformat_minor": 5,
}

nb_path = OUT / K_CODE
nb_path.write_text(json.dumps(nb, indent=1), encoding="utf-8")

meta = {
    "id": K_ID,
    "title": K_TITLE,
    "code_file": K_CODE,
    "language": "python",
    "kernel_type": "notebook",
    "is_private": True,
    "enable_gpu": True,
    "enable_tpu": False,
    "enable_internet": False,
    "keywords": ["gpu"],
    "dataset_sources": ["metric/gemma-4-developer-agent-wheelhouse",
                        "comfyops/gemma129-taskdefs",
                        "comfyops/gemma129-snapshots"],
    "kernel_sources": [],
    "competition_sources": ["gemma-4-developer-agent"],
    "model_sources": [f"google/gemma-4/Other/{MODEL_SLUG}/{MODEL_VER}"],
    "docker_image": "gcr.io/kaggle-private-byod/python@sha256:37c64f7dd9c54116ecd1bcc88817c5469b88387388fade02bfa8bf3fc647d461",
    "machine_shape": "NvidiaL4",
}
(OUT / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

print(f"wrote {nb_path} ({nb_path.stat().st_size} B)")
print(f"wrote {OUT / 'kernel-metadata.json'}")
print("cells:", len(nb["cells"]), "| datasets:", meta["dataset_sources"])
