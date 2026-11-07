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

K = Path(__file__).resolve().parent
SRC = K / "push_129_off31"
DST = K / "push_31b_cap_ab"
SLUG = "ca5-31b-cap-ab"
EVAL_BUDGET_SECONDS = int(7.2 * 3600)
SAVE_RESERVE_SECONDS = 12 * 60
PER_ARM_CONC = 2
CHUNK = 10
ARMS = {"A_cap40_12": (40, 12, 120), "B_cap50_20": (50, 20, 120)}

live = json.loads((K / "live_ids_31b_ab.json").read_text(encoding="utf-8"))
order = live["order"]
assert len(order) == 85 and len(set(order)) == 85, len(order)

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
for arm, (c, m, t) in ARMS.items():
    ARM_CODE += f'''_d = Path("/kaggle/working/agent_{arm}")
if _d.exists():
    _sh.rmtree(_d)
_sh.copytree(AGENT, _d)
(_d / "eval_config.yaml").write_text({eval_yaml(c, m, t)!r}, encoding="utf-8", newline="")
assert (_d / "prompts" / "system.md").read_bytes() == (AGENT / "prompts" / "system.md").read_bytes()
AGENT_DIRS[{arm!r}] = _d
print({arm!r}, "prompt sha", _hl.sha1((_d / "prompts" / "system.md").read_bytes()).hexdigest()[:12],
      "| eval:", (_d / "eval_config.yaml").read_text().replace(chr(10), " "))
'''
cell2 = cell2.replace(ASSERT.group(0), ASSERT.group(0) + ARM_CODE, 1)
nb["cells"][2]["source"] = cell2.splitlines(keepends=True)

EVAL = r'''# ---------- PAIRED 31B CAP A/B: same ca5 prompt, eval_config 40/12 (A) vs 50/20 (B), same server, same chunks ----------
import threading, subprocess as _sp, yaml as _yaml, time as _t, tarfile, shutil
LIVE_ORDER = __ORDER__
EVAL_BUDGET = __BUDGET__
SAVE_RESERVE = __RESERVE__
PER_ARM_CONC = __CONC__
CHUNK = __CHUNK__
START = _t.time(); HARD_STOP = START + EVAL_BUDGET; DEADLINE = HARD_STOP - SAVE_RESERVE
OUT = Path("/kaggle/working/results"); OUT.mkdir(parents=True, exist_ok=True)
AB = Path("/kaggle/working/cap_ab.json")
ARM_NAMES = list(AGENT_DIRS)

def _caps(agent_dir):
    raw = _yaml.safe_load((Path(agent_dir) / "eval_config.yaml").read_text()) or {}
    c = raw.get("evaluation", raw) or {}
    out = []
    for k_, flag in (("max_tool_calls", "--max-tool-calls"), ("max_time_minutes", "--max-time-minutes"), ("max_turns", "--max-turns")):
        if c.get(k_) is not None: out += [flag, str(c[k_])]
    return out
CAPS = {a: _caps(d) for a, d in AGENT_DIRS.items()}
assert CAPS[ARM_NAMES[0]] != CAPS[ARM_NAMES[1]], "arms must differ in caps"
_all = {json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()}
assert all(t in _all for t in LIVE_ORDER), "live list has ids not in tasks.jsonl"
print(f"31B cap A/B: {len(LIVE_ORDER)} live tasks, arms {ARM_NAMES}, conc/arm {PER_ARM_CONC}, chunk {CHUNK}, "
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
    chunks = [LIVE_ORDER[i:i + CHUNK] for i in range(0, len(LIVE_ORDER), CHUNK)]
    for ci, ids in enumerate(chunks, start=1):
        remaining = DEADLINE - _t.time()
        if remaining < longest * 1.25:
            print(f"stopping: remaining {remaining/60:.0f} min < 1.25 x longest chunk {longest/60:.0f} min", flush=True)
            stop = True; break
        dur, ok = _chunk(round_no, ci, ids)
        if ok: longest = max(longest, dur)

good = [r for r in ROWS if r["chunk_complete"]]
A_, B_ = ARM_NAMES
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
json.dump({"rows": ROWS, "summary": summary, "caps": CAPS}, open(AB, "w"))
print("\n" + "=" * 64 + "\n31B CAP A/B SUMMARY (complete chunks only)\n" + "=" * 64, flush=True)
for k_, v_ in summary.items():
    print(f"  {k_}: {v_}", flush=True)
try:
    with tarfile.open("/kaggle/working/results.tar.gz", "w:gz") as tf:
        tf.add(str(OUT), arcname="results")
    shutil.rmtree(OUT, ignore_errors=True)
    print("packed results.tar.gz", flush=True)
except Exception as e:
    print("tar failed (results dir kept):", e, flush=True)
print("wrote cap_ab.json", flush=True)
'''
EVAL = (EVAL.replace("__ORDER__", json.dumps(order)).replace("__BUDGET__", str(EVAL_BUDGET_SECONDS))
        .replace("__RESERVE__", str(SAVE_RESERVE_SECONDS)).replace("__CONC__", str(PER_ARM_CONC))
        .replace("__CHUNK__", str(CHUNK)))
compile(EVAL, "cell4", "exec"); compile(cell2, "cell2", "exec"); compile(cell3, "cell3", "exec")
nb["cells"][4]["source"] = EVAL.splitlines(keepends=True)
nb["cells"][0]["source"] = [
    "# 31B PAIRED CAP A/B: ca5 prompt unchanged; eval_config 40/12 (A) vs 50/20 (B). 85 live tasks.\n",
    "Both arms share ONE tp=4 server, same chunks, 2 loops/arm. Output: cap_ab.json + results.tar.gz.\n",
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
