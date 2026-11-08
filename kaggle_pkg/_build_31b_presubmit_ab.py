"""Build kaggle_pkg/push_31b_cap_ab: PAIRED 31B A/B of the two cap packs on the 85 live tasks.

  ARM A = ca5, eval_config 40 calls / 12 min / 120 turns   (v7 cap-sim: 31/129)
  ARM B = ca5, eval_config 50 calls / 20 min / 120 turns   (v7 cap-sim: 35/129)

Forks push_129_off31 (the v7 kernel behind 35/129) exactly as _build_31b_sibling_ab.py did:
ONE tp=4 31B server, both arms concurrently, 2 agent loops each (4 total = v7's CONC=4 regime, so
elapsed-time caps bind the way the simulation assumed). system.md is IDENTICAL in both arms
(sha1 b08b32a2438d asserted); only eval_config.yaml differs. Caps are read PER ARM from that arm's
eval_config and passed to swegemma eval (the grader's behaviour).

Task set = kaggle_pkg/live_ids_31b_ab.json order (85 live: rich + fastapi, dead + src-layout excluded).
Every round runs all 85 (not rich-only), time-boxed like the sibling A/B.
Output: cap_ab.json (rows rewritten after every chunk) + results.tar.gz.
"""
import json
import re
import shutil
from pathlib import Path

import base64

K = Path(__file__).resolve().parent
SRC = K / "push_129_off31"
import os
# TASKSET=85 (default now): all 85 live, 1 round, 6 h hard budget (user: option 2, 16 GPU-h left).
# TASKSET=39: the original 39 ever-solved x 2 rounds (31B ~85% there -> ceiling-bound; superseded).
TASKSET = os.environ.get("TASKSET", "85")
PER_ARM_CONC = 2          # = ab31 / cap-ab regime (4 concurrent on one tp=4 server) -> comparable timings
CHUNK = 10
SAVE_RESERVE_SECONDS = 12 * 60
BUNDLE = K.parent / "local_eval" / "parity_rig" / "agent_31b_ca5_presubmit"
ARMS = {"A_ca5": None, "B_presubmit": BUNDLE}   # A = AGENT unchanged (28/8/120 board caps)
live = json.loads((K / "live_ids_31b_ab.json").read_text(encoding="utf-8"))
if TASKSET == "timeout":
    # The 6 RECOVERABLE timeout tasks (31B solves each in other runs; the 8-min clock blocks it) x 6 reps x 3 arms.
    # ONLY eval_config differs: A = ca5 28/8/120/300 (control), B = timeout_seconds 300 -> 60 (kill hung repro
    # scripts), C = max_time_minutes 8 -> 10 (does time alone recover them? scorer-runtime risk, see 50/20).
    BASE_EVAL = (K.parent / "Outputs" / "v7_31b_full129" / "agentcfg" / "agent_ca5" / "eval_config.yaml").read_text(encoding="utf-8")
    assert "timeout_seconds: 300" in BASE_EVAL and "max_time_minutes: 8" in BASE_EVAL, BASE_EVAL
    ARMS = {"A_ca5": None,
            "B_cmd60": {"eval_config.yaml": BASE_EVAL.replace("timeout_seconds: 300", "timeout_seconds: 60").encode()},
            "C_time10": {"eval_config.yaml": BASE_EVAL.replace("max_time_minutes: 8", "max_time_minutes: 10").encode()}}
    DST = K / "push_31b_timeout_ab"
    SLUG = "ca5-31b-timeout-ab"
    EVAL_BUDGET_SECONDS = int(3.6 * 3600)     # 8 GPU-h left; expected ~2.3 h of eval
    MAX_ROUNDS = 6
    CHUNK = 6
    order = ["rich_3480", "fastapi_14616", "fastapi_14851", "rich_3506", "fastapi_14419", "rich_3521"]
    assert all(t in set(live["order"]) for t in order)
elif TASKSET == "think":
    # 31B thinking-budget dose test. Control (ca5, thinking 4096, 28/8) is ALREADY measured 4x on these 85
    # (ab31 A 34 / B 33, presubmit-85 A 32 / B 33), so both arms are treatments. ONLY thinking_budget changes.
    SAMP = (K.parent / "Outputs" / "v7_31b_full129" / "agentcfg" / "agent_ca5" / "configs" / "sampling.yaml").read_text(encoding="utf-8")
    assert SAMP.count("thinking_budget: 4096") == 1, SAMP
    ARMS = {f"{a}_think{tb}": {"configs/sampling.yaml": SAMP.replace("thinking_budget: 4096", f"thinking_budget: {tb}").encode()}
            for a, tb in (("A", 2048), ("B", 1024))}
    DST = K / "push_31b_think_85"
    SLUG = "ca5-31b-think-85"
    EVAL_BUDGET_SECONDS = int(4.6 * 3600)     # 8 GPU-h left this week; last 85-task round took 4.08 h at 4096
    MAX_ROUNDS = 1
    order = list(live["order"])
    assert len(order) == 85 and len(set(order)) == 85, len(order)
elif TASKSET == "85":
    DST = K / "push_31b_presubmit_85"
    SLUG = "ca5-31b-presubmit-85"
    EVAL_BUDGET_SECONDS = int(6.0 * 3600)
    MAX_ROUNDS = 1
    order = list(live["order"])
    assert len(order) == 85 and len(set(order)) == 85, len(order)
else:
    DST = K / "push_31b_presubmit_ab"
    SLUG = "ca5-31b-presubmit-ab"
    EVAL_BUDGET_SECONDS = int(7.0 * 3600)
    MAX_ROUNDS = 2
    ever = set(json.loads((K.parent / "Outputs" / "_solvable85.json").read_text(encoding="utf-8"))["ever"])
    order = [t for t in live["order"] if t in ever]
    assert len(order) == 39 and len(set(order)) == 39, len(order)

nb = json.loads((SRC / "ca5-31b-full129.ipynb").read_text(encoding="utf-8"))
cell2 = "".join(nb["cells"][2]["source"])
cell3 = "".join(nb["cells"][3]["source"])
ASSERT = re.search(r'assert sha == "b08b32a2438d".*?\n', cell2)
assert ASSERT, "ca5 sha assert not found in cell 2"
assert "os.environ['OPENAI_BASE_URL']" in cell3 and "tensor_parallel_size" in cell3


def eval_yaml(calls, mins, turns):
    return (f"evaluation:\n  max_time_minutes: {mins}\n  max_tool_calls: {calls}\n"
            f"  max_turns: {turns}\n  timeout_seconds: 300\n")


ARM_CODE = "import shutil as _sh, hashlib as _hl\nAGENT_DIRS = {}\n"
for arm, bdir in ARMS.items():
    if isinstance(bdir, dict):      # inline overrides: {relpath: bytes}
        over = {rel: base64.b64encode(b).decode() for rel, b in bdir.items()}
    else:
        over = {} if bdir is None else {p.relative_to(bdir).as_posix(): base64.b64encode(p.read_bytes()).decode()
                                        for p in sorted(bdir.rglob("*")) if p.is_file()}
    if bdir is not None and not isinstance(bdir, dict):
        # the bundle must equal the embedded ca5 agent except system.md (one line), agent.yaml (+skills) and the skill
        assert set(over) == {"agent.yaml", "eval_config.yaml", "configs/sampling.yaml", "prompts/system.md",
                             "skills/presubmit-check/SKILL.md", "skills/presubmit-check/scripts/check.py"}, sorted(over)
    ARM_CODE += f'''_d = Path("/kaggle/working/agent_{arm}")
if _d.exists():
    _sh.rmtree(_d)
_sh.copytree(AGENT, _d)
for _rel, _b in json.loads({json.dumps(json.dumps(over))}).items():
    _p = _d / _rel; _p.parent.mkdir(parents=True, exist_ok=True); _p.write_bytes(base64.b64decode(_b))
AGENT_DIRS[{arm!r}] = _d
print({arm!r}, "prompt sha", _hl.sha1((_d / "prompts" / "system.md").read_bytes()).hexdigest()[:12],
      "| eval:", (_d / "eval_config.yaml").read_text().replace(chr(10), " "),
      "| files:", sorted(p.relative_to(_d).as_posix() for p in _d.rglob("*") if p.is_file()))
'''
if set(ARMS) == {"A_ca5", "B_presubmit"}:
    ARM_CODE += '''assert (AGENT_DIRS["A_ca5"] / "eval_config.yaml").read_bytes() == (AGENT_DIRS["B_presubmit"] / "eval_config.yaml").read_bytes()
assert (AGENT_DIRS["A_ca5"] / "configs" / "sampling.yaml").read_bytes() == (AGENT_DIRS["B_presubmit"] / "configs" / "sampling.yaml").read_bytes()
'''
else:
    # every non-control arm may differ from A_ca5 ONLY in the files it overrides
    ARM_CODE += '''for _arm, _dir in AGENT_DIRS.items():
    for _rel in ("agent.yaml", "prompts/system.md", "configs/sampling.yaml", "eval_config.yaml"):
        _same = (_dir / _rel).read_bytes() == (AGENT_DIRS["A_ca5"] / _rel).read_bytes()
        print(f"   {_arm:10s} {_rel:24s} {'same as A' if _same else 'DIFFERS'}")
'''
cell2 = cell2.replace(ASSERT.group(0), ASSERT.group(0) + ARM_CODE, 1)
nb["cells"][2]["source"] = cell2.splitlines(keepends=True)

EVAL = r'''# ---------- PAIRED 31B A/B: ca5 (A) vs ca5 + presubmit-check skill (B), 28/8 board caps, same server, same chunks ----------
import threading, subprocess as _sp, yaml as _yaml, time as _t, tarfile, shutil, urllib.request as _ur, re as _re
MAX_ROUNDS = __ROUNDS__
# ---- telemetry: vLLM /metrics + nvidia-smi every 60 s -> is the 4xL4 31B server actually busy? ----
TELE = Path("/kaggle/working/telemetry.jsonl")
_TELE_STOP = threading.Event()
_MET = ("vllm:num_requests_running", "vllm:num_requests_waiting", "vllm:gpu_cache_usage_perc", "vllm:kv_cache_usage_perc",
        "vllm:generation_tokens_total", "vllm:prompt_tokens_total", "vllm:num_preemptions_total")
def _tele():
    base = os.environ["OPENAI_BASE_URL"].rstrip("/").rsplit("/v1", 1)[0]
    while not _TELE_STOP.is_set():
        rec = {"t": round(_t.time() - START, 1)}
        try:
            txt = _ur.urlopen(base + "/metrics", timeout=10).read().decode()
            for line in txt.splitlines():
                for m in _MET:
                    if line.startswith(m) and not line.startswith("#"):
                        try: rec[m] = rec.get(m, 0.0) + float(line.rsplit(" ", 1)[1])
                        except Exception: pass
        except Exception as e:
            rec["metrics_err"] = str(e)[:80]
        try:
            q = _sp.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,temperature.gpu,clocks.sm,power.draw",
                         "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=20).stdout
            rec["gpu"] = [[float(x) for x in l.split(",")] for l in q.strip().splitlines()]
        except Exception as e:
            rec["gpu_err"] = str(e)[:80]
        try:
            rec["load1"] = os.getloadavg()[0]
            rec["procs_pytest"] = int(_sp.run("pgrep -fc pytest", shell=True, capture_output=True, text=True).stdout.strip() or 0)
        except Exception:
            pass
        with open(TELE, "a") as f:
            f.write(json.dumps(rec) + "\n")
        _TELE_STOP.wait(60)
LIVE_ORDER = __ORDER__
EVAL_BUDGET = __BUDGET__
SAVE_RESERVE = __RESERVE__
PER_ARM_CONC = __CONC__
CHUNK = __CHUNK__
START = _t.time(); HARD_STOP = START + EVAL_BUDGET; DEADLINE = HARD_STOP - SAVE_RESERVE
OUT = Path("/kaggle/working/results"); OUT.mkdir(parents=True, exist_ok=True)
AB = Path("/kaggle/working/presubmit_ab.json")
ARM_NAMES = list(AGENT_DIRS)
threading.Thread(target=_tele, daemon=True).start()

def _caps(agent_dir):
    raw = _yaml.safe_load((Path(agent_dir) / "eval_config.yaml").read_text()) or {}
    c = raw.get("evaluation", raw) or {}
    out = []
    # timeout_seconds -> --timeout-seconds: the scorer applies evaluation.timeout_seconds as the per-command timeout
    # (HARNESS_README L559); earlier kernels did NOT forward it (harmless then: everyone used 300 = CLI default).
    for k_, flag in (("max_tool_calls", "--max-tool-calls"), ("max_time_minutes", "--max-time-minutes"),
                     ("max_turns", "--max-turns"), ("timeout_seconds", "--timeout-seconds")):
        if c.get(k_) is not None: out += [flag, str(c[k_])]
    return out
CAPS = {a: _caps(d) for a, d in AGENT_DIRS.items()}
if len(ARM_NAMES) == 2 and "B_presubmit" in ARM_NAMES:
    assert CAPS[ARM_NAMES[0]] == CAPS[ARM_NAMES[1]], "arms must share the 28/8 board caps"
_all = {json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()}
assert all(t in _all for t in LIVE_ORDER), "live list has ids not in tasks.jsonl"
print(f"31B presubmit A/B: {len(LIVE_ORDER)} ever-solved tasks x {MAX_ROUNDS} rounds, arms {ARM_NAMES}, conc/arm {PER_ARM_CONC}, chunk {CHUNK}, "
      f"budget {EVAL_BUDGET/3600:.1f}h, caps {CAPS}", flush=True)

ROWS = []
def _save():
    json.dump({"rows": ROWS, "meta": {"live": len(LIVE_ORDER), "chunk": CHUNK, "conc_per_arm": PER_ARM_CONC, "caps": CAPS}}, open(AB, "w"))

def _run_arm(arm, agent_dir, ids, tag, sink, timeout):
    out = OUT / tag / arm; out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "swegemma", "eval", "--tasks", str(TASKS), "--snapshots-dir", str(SNAPS),
           "--results-dir", str(out), "--submission-dir", str(agent_dir), "--sandbox", "subprocess",
           "--concurrency", str(PER_ARM_CONC), "--display", "quiet"] + CAPS[arm]
    for t in ids: cmd += ["--task-id", t]
    to = False
    try:
        _sp.run(cmd, env=dict(os.environ), capture_output=True, text=True, timeout=max(60, timeout))
    except _sp.TimeoutExpired:
        to = True
    rf = out / "task_results.jsonl"
    got = []
    if rf.exists():
        for l in open(rf):
            if l.strip():
                try: got.append(json.loads(l))
                except Exception: pass
    sink[arm] = (got, to)

def _chunk(round_no, ci, ids):
    tag = f"r{round_no}_c{ci}"
    sink = {}
    ths = [threading.Thread(target=_run_arm, args=(arm, d, ids, tag, sink, HARD_STOP - _t.time())) for arm, d in AGENT_DIRS.items()]
    t0 = _t.time()
    for th in ths: th.start()
    for th in ths: th.join()
    dur = _t.time() - t0
    complete = all(not sink[a][1] and len(sink[a][0]) >= len(ids) for a in AGENT_DIRS)
    for arm in AGENT_DIRS:
        for r in sink[arm][0]:
            ROWS.append({"round": round_no, "chunk": ci, "arm": arm, "id": r["instance_id"], "resolved": bool(r.get("resolved")),
                         "calls": r.get("tool_calls"), "patch": r.get("agent_patch_size"), "dur": r.get("duration_seconds"),
                         "rc": r.get("test_exit_code"), "err": str(r.get("error") or "")[:80], "chunk_complete": complete})
    _save()
    ks = {a: sum(bool(r.get("resolved")) for r in sink[a][0]) for a in AGENT_DIRS}
    tot = {a: sum(1 for r in ROWS if r["arm"] == a and r["resolved"]) for a in AGENT_DIRS}
    print(f"[{tag}] {len(ids)} tasks: {ks} | cumulative {tot} | {dur/60:.1f} min | complete={complete} | "
          f"elapsed {(_t.time()-START)/3600:.2f}h", flush=True)
    return dur, complete

longest = 2400.0
round_no = 0; stop = False
while not stop:
    round_no += 1
    if round_no > MAX_ROUNDS:
        round_no -= 1
        print(f"done: {MAX_ROUNDS} rounds complete", flush=True)
        break
    chunks = [LIVE_ORDER[i:i + CHUNK] for i in range(0, len(LIVE_ORDER), CHUNK)]
    for ci, ids in enumerate(chunks, start=1):
        remaining = DEADLINE - _t.time()
        if remaining < longest * 1.25:
            print(f"stopping: remaining {remaining/60:.0f} min < 1.25 x longest chunk {longest/60:.0f} min", flush=True)
            stop = True; break
        dur, ok = _chunk(round_no, ci, ids)
        if ok: longest = max(longest, dur)

good = [r for r in ROWS if r["chunk_complete"]]
A_, B_ = ARM_NAMES[0], ARM_NAMES[1]
pa = {(r["round"], r["id"]): r["resolved"] for r in good if r["arm"] == A_}
pb = {(r["round"], r["id"]): r["resolved"] for r in good if r["arm"] == B_}
keys = sorted(set(pa) & set(pb))
def repo(k): return k[1].split("_")[0]
summary = {
    "paired_runs": len(keys), A_: sum(pa[k] for k in keys), B_: sum(pb[k] for k in keys),
    "both": sum(1 for k in keys if pa[k] and pb[k]),
    A_ + "_only": [list(k) for k in keys if pa[k] and not pb[k]],
    B_ + "_only": [list(k) for k in keys if pb[k] and not pa[k]],
    "by_repo": {rp: {A_: sum(pa[k] for k in keys if repo(k) == rp), B_: sum(pb[k] for k in keys if repo(k) == rp),
                     "n": sum(1 for k in keys if repo(k) == rp)} for rp in ("rich", "fastapi")},
    "round1_complete_pairs": sum(1 for k in keys if k[0] == 1),
    "round1": {A_: sum(pa[k] for k in keys if k[0] == 1), B_: sum(pb[k] for k in keys if k[0] == 1)},
    "rounds_run": round_no, "elapsed_h": round((_t.time() - START) / 3600, 2),
}
# every arm, per task: solved / runs / timeouts (works for any number of arms)
summary["per_arm"] = {}
for a in ARM_NAMES:
    ra = [r for r in good if r["arm"] == a]
    summary["per_arm"][a] = {
        "solved": sum(r["resolved"] for r in ra), "runs": len(ra),
        "timeouts": sum("timeout" in (r["err"] or "") for r in ra),
        "per_task": {t: f"{sum(r['resolved'] for r in ra if r['id'] == t)}/{sum(1 for r in ra if r['id'] == t)}"
                     for t in LIVE_ORDER},
        "mean_dur": round(sum((r["dur"] or 0) for r in ra) / max(1, len(ra)), 1)}
_TELE_STOP.set()
json.dump({"rows": ROWS, "summary": summary, "caps": CAPS}, open(AB, "w"))
print("\n" + "=" * 64 + "\n31B PRESUBMIT A/B SUMMARY (complete chunks only)\n" + "=" * 64, flush=True)
try:
    _tl = [json.loads(l) for l in open(TELE) if l.strip()]
    _run = [r.get("vllm:num_requests_running", 0) for r in _tl]
    _wait = [r.get("vllm:num_requests_waiting", 0) for r in _tl]
    _kv = [r.get("vllm:gpu_cache_usage_perc", r.get("vllm:kv_cache_usage_perc", 0)) for r in _tl]
    _gu = [sum(g[0] for g in r["gpu"]) / len(r["gpu"]) for r in _tl if r.get("gpu")]
    _g = [r.get("vllm:generation_tokens_total", 0) for r in _tl]
    _tps = (_g[-1] - _g[0]) / max(1, _tl[-1]["t"] - _tl[0]["t"]) if len(_g) > 1 else 0
    print(f"TELEMETRY {len(_tl)} samples | running mean {sum(_run)/len(_run):.2f} max {max(_run):.0f} | waiting max {max(_wait):.0f} | "
          f"KV use mean {100*sum(_kv)/len(_kv):.0f}% max {100*max(_kv):.0f}% | GPU util mean {sum(_gu)/max(1,len(_gu)):.0f}% | "
          f"gen tok/s {_tps:.1f}", flush=True)
except Exception as e:
    print("telemetry summary failed:", e, flush=True)
for k_, v_ in summary.items():
    print(f"  {k_}: {v_}", flush=True)
try:
    with tarfile.open("/kaggle/working/results.tar.gz", "w:gz") as tf:
        tf.add(str(OUT), arcname="results")
    shutil.rmtree(OUT, ignore_errors=True)
    print("packed results.tar.gz", flush=True)
except Exception as e:
    print("tar failed (results dir kept):", e, flush=True)
print("wrote presubmit_ab.json", flush=True)
'''
EVAL = (EVAL.replace("__ORDER__", json.dumps(order)).replace("__BUDGET__", str(EVAL_BUDGET_SECONDS))
        .replace("__RESERVE__", str(SAVE_RESERVE_SECONDS)).replace("__CONC__", str(PER_ARM_CONC))
        .replace("__CHUNK__", str(CHUNK)).replace("__ROUNDS__", str(MAX_ROUNDS)))
compile(EVAL, "cell4", "exec"); compile(cell2, "cell2", "exec"); compile(cell3, "cell3", "exec")
nb["cells"][4]["source"] = EVAL.splitlines(keepends=True)
nb["cells"][0]["source"] = [
    "# 31B PAIRED A/B: ca5 (A) vs ca5 + presubmit-check skill (B), 28/8 board caps, %d tasks x %d round(s), %.1f h budget.\n"
    % (len(order), MAX_ROUNDS, EVAL_BUDGET_SECONDS / 3600),
    "ONE tp=4 server, same chunks, 2 loops/arm. Telemetry: vLLM /metrics + nvidia-smi every 60 s.\n",
    "Output: presubmit_ab.json + telemetry.jsonl + results.tar.gz.\n",
]
for c in nb["cells"]:
    if c.get("cell_type") == "code":
        c["outputs"] = []; c["execution_count"] = None
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir()
(DST / f"{SLUG}.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
meta = json.loads((SRC / "kernel-metadata.json").read_text(encoding="utf-8"))
meta.pop("id_no", None)
meta.update(id=f"comfyops/{SLUG}", title=SLUG.replace("-", " "), code_file=f"{SLUG}.ipynb")
(DST / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("wrote", DST, "| tasks", len(order), "| arms", ARMS)
print("metadata:", json.dumps({k: meta[k] for k in ("id", "enable_gpu", "machine_shape", "model_sources", "dataset_sources")}))
