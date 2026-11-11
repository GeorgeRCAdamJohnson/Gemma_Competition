"""E4B arm A/B on Colab. Runs ON the GPU VM with /content/venv/bin/python (the Kaggle-matched env).

One vLLM server with the Kaggle kernel's exact VllmConfig. Rounds: every round runs EVERY arm once over the
landable task set (each arm = one `swegemma eval` pass, --concurrency 8 as on the Kaggle nodes). The arm order
rotates each round so drift (thermal, Drive, time of day) cannot favour one arm. After every pass the pass's
results are copied to Drive and /content/ab/progress.json is updated. Stops after N_ROUNDS or at DEADLINE_H.
usage: python gpu_ab_run.py [n_rounds] [deadline_hours]
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import torch
import yaml
from adk_submission import VllmConfig, VllmServer, discover_adapters

try:
    from swegemma.config import ALLOWED_ADAPTER_EXTENSIONS
except Exception:
    ALLOWED_ADAPTER_EXTENSIONS = frozenset({'.safetensors', '.bin', '.pt', '.pth', '.gguf', '.ggml'})

N_ROUNDS = int(sys.argv[1]) if len(sys.argv) > 1 else 10
# multi-server on one GPU (e.g. G4 96 GB): each driver gets its own port, memory share and round range
PORT = int(os.environ.get("AB_PORT", "8000"))
UTIL = float(os.environ.get("AB_UTIL", "0.85"))
ROUND_FROM = int(os.environ.get("AB_ROUND_FROM", "1"))
DEADLINE = time.time() + float(sys.argv[2] if len(sys.argv) > 2 else 20) * 3600
WORK = Path("/content/work")
ARMS_DIR = WORK / os.environ.get("AB_ARMS", "arms")
ARMS = sorted(p.name for p in ARMS_DIR.iterdir() if p.is_dir())
TASK_IDS = json.loads((WORK / "ab_tasks.json").read_text())
TASKS = WORK / "tasks.jsonl"
SNAPS = Path("/content/snaps")
OUT = Path(os.environ.get("AB_OUT", "/content/ab"))
DRIVE_OUT = Path("/content/drive/MyDrive/gemma_fasteval/ab_runs") / os.environ.get("AB_TAG", "e4b_ab")
TARGET_MODEL_NAME = "gemma-4-e4b-it-qat-w4a16-ct"
CONC = 8
T0 = time.time()


def log(*a):
    print(f"[{(time.time() - T0) / 60:7.1f}m]", *a, flush=True)


log("arms", ARMS, "| tasks", len(TASK_IDS), "| rounds", N_ROUNDS, "| conc", CONC)
assert len(list(SNAPS.glob("*.tgz"))) >= len(TASK_IDS)
OUT.mkdir(parents=True, exist_ok=True)

cfg = VllmConfig(model="/content/model", port=PORT, host='127.0.0.1', tool_call_parser='gemma4', reasoning_parser='gemma4',
                 dtype='bfloat16' if torch.cuda.is_bf16_supported() else 'auto', enable_auto_tool_choice=True,
                 enable_lora=False, tensor_parallel_size=1, startup_timeout=60 * 25, max_model_len=32768,
                 gpu_memory_utilization=UTIL, extra_args=['--served-model-name', TARGET_MODEL_NAME, '2'])
log("vLLM port", PORT, "| gpu_memory_utilization", UTIL, "| rounds", ROUND_FROM, "..", N_ROUNDS)
srv = VllmServer(cfg, adapter_manifest=discover_adapters(str(ARMS_DIR / ARMS[0]), adapter_extensions=ALLOWED_ADAPTER_EXTENSIONS))
_orig = srv.build_env
srv.build_env = lambda: {**_orig(), 'CUDA_VISIBLE_DEVICES': '0'}
log("booting vLLM ...")
srv.start()
ids = [m['id'] for m in json.load(urllib.request.urlopen(srv.base_url.rstrip('/') + '/models'))['data']]
assert TARGET_MODEL_NAME in ids, ids
log("vLLM up", srv.base_url)


def caps(agent_dir):
    raw = yaml.safe_load((agent_dir / "eval_config.yaml").read_text()) or {}
    c = raw.get("evaluation", raw) or {}
    out = []
    for k, flag in (("max_tool_calls", "--max-tool-calls"), ("max_time_minutes", "--max-time-minutes"),
                    ("max_turns", "--max-turns")):
        if c.get(k) is not None:
            out += [flag, str(c[k])]
    return out


prog_path = OUT / "progress.json"
prog = json.loads(prog_path.read_text()) if prog_path.exists() else {"passes": []}
done_keys = {(p["round"], p["arm"]) for p in prog["passes"]}
for rnd in range(ROUND_FROM, N_ROUNDS + 1):
    order = ARMS[(rnd - 1) % len(ARMS):] + ARMS[:(rnd - 1) % len(ARMS)]
    for arm in order:
        if (rnd, arm) in done_keys:
            continue
        if time.time() > DEADLINE:
            log("deadline reached; stopping")
            (OUT / "ALL_DONE").write_text("deadline " + time.strftime("%Y-%m-%d %H:%M:%S"))
            try:
                srv.stop()
            finally:
                os._exit(0)
        agent = ARMS_DIR / arm
        out = OUT / arm / f"round_{rnd}"
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        env = dict(os.environ, OPENAI_BASE_URL=srv.base_url, OPENAI_API_KEY="EMPTY")
        cmd = [sys.executable, "-m", "swegemma", "eval", "--tasks", str(TASKS), "--snapshots-dir", str(SNAPS),
               "--results-dir", str(out), "--submission-dir", str(agent), "--sandbox", "subprocess",
               "--concurrency", str(CONC), "--display", "quiet"] + caps(agent)
        for t in TASK_IDS:
            cmd += ["--task-id", t]
        t0 = time.time()
        log(f"round {rnd} arm {arm}: start")
        p = subprocess.run(cmd, env=env, cwd=str(WORK), capture_output=True, text=True, timeout=4 * 3600)
        (out / "eval_stderr.txt").write_text((p.stderr or "")[-20000:])
        rf = out / "task_results.jsonl"
        rows = [json.loads(l) for l in rf.read_text().splitlines() if l.strip()] if rf.exists() else []
        rec = {"round": rnd, "arm": arm, "rc": p.returncode, "seconds": round(time.time() - t0), "n": len(rows),
               "solved": sum(bool(r.get("resolved")) for r in rows),
               "rows": [{"id": r["instance_id"], "resolved": bool(r.get("resolved")), "calls": r.get("tool_calls"),
                         "llm": r.get("total_llm_calls"), "patch": r.get("agent_patch_size"),
                         "dur": r.get("duration_seconds"), "err": str(r.get("error") or "")[:160]} for r in rows]}
        prog["passes"].append(rec)
        prog_path.write_text(json.dumps(prog))
        log(f"round {rnd} arm {arm}: {rec['solved']}/{rec['n']} in {rec['seconds'] / 60:.1f} min rc={p.returncode}")
        try:  # persist to Drive after EVERY pass (VM loss costs at most one pass)
            (DRIVE_OUT / arm).mkdir(parents=True, exist_ok=True)
            shutil.copytree(out, DRIVE_OUT / arm / f"round_{rnd}", dirs_exist_ok=True)
            shutil.copy(prog_path, DRIVE_OUT / "progress.json")
        except Exception as e:
            log("Drive copy failed:", type(e).__name__, e)
log("ALL ROUNDS DONE")
# 2026-11-11 fix: after the last pass the driver used to stay alive (vLLM child held it), so the chain never fired and the
# keep-alive kept an idle L4 billing for ~7 h. Now: write a done marker, stop vLLM, hard-exit.
(OUT / "ALL_DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
try:
    srv.stop()
except Exception as e:
    log("srv.stop failed:", type(e).__name__, e)
os._exit(0)
