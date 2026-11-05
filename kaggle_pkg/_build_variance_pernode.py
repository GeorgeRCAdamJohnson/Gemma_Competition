"""Build kaggle_pkg/push_e4b_variance_pernode: PER-NODE independent full-129 passes.

User intent (clarified 2026-11-03): run 4 complete 129-task passes AT THE SAME TIME, one per node (GPU),
each node looping its own passes independently. The first variance kernel instead sharded ONE pass across
the 4 servers (passes sequential, each gated by its slowest shard). This one has NO cross-node barrier.

Reuses cells 0-3 of the built push_e4b_variance notebook (ca5 embed, 1 server per GPU, concurrent boot,
the proven config) and replaces ONLY cell 4 (the eval loop).

Per node i: while time remains: run ALL 129 tasks against server i (concurrency NODE_CONC) -> a pass.
A new pass starts only if the remaining time exceeds 1.15x the node's longest pass so far.

Download-friendly: after each pass the heavy dirs (logs/traces/test_outputs) are deleted except for each
node's run_1, and every task row (resolved, calls, patch size, duration) is stored inside variance.json,
so variance.json alone is enough for the analysis.
"""
import json
import shutil
from pathlib import Path

K = Path(__file__).resolve().parent
SRC = K / "push_e4b_variance"
DST = K / "push_e4b_variance_pernode"
assert (SRC / "e4b-variance.ipynb").exists(), "build push_e4b_variance first (_build_variance_kernel.py)"
BUDGET_SECONDS = 3 * 3600
SAVE_RESERVE_SECONDS = 10 * 60
NODE_CONC = 8     # prior single-server full-129 kernel used 10; keep it in the same regime

nb = json.loads((SRC / "e4b-variance.ipynb").read_text(encoding="utf-8"))
c3 = "".join(nb["cells"][3]["source"])
assert "INSTANCES_PER_GPU = 1" in c3, "base kernel must be the 1-server-per-GPU config"

EVAL = r'''# ---------- PER-NODE VARIANCE: each server runs its OWN full-129 passes, all nodes concurrently ----------
import threading, subprocess as _sp, yaml as _yaml, time as _t, statistics as _stats, shutil
from collections import Counter
BUDGET_SECONDS = __BUDGET__
SAVE_RESERVE = __RESERVE__
NODE_CONC = __CONC__
START = _t.time()
HARD_STOP = START + BUDGET_SECONDS
DEADLINE = HARD_STOP - SAVE_RESERVE
OUT = Path("/kaggle/working/results"); OUT.mkdir(parents=True, exist_ok=True)
VAR = Path("/kaggle/working/variance.json")

_raw = _yaml.safe_load((AGENT/'eval_config.yaml').read_text()) or {}
_c = _raw.get("evaluation", _raw) or {}
CAPS = []
for k_, flag in (("max_tool_calls","--max-tool-calls"),("max_time_minutes","--max-time-minutes"),("max_turns","--max-turns")):
    if _c.get(k_) is not None: CAPS += [flag, str(_c[k_])]
ALL_IDS = [json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()]
N_NODES = len(BASE_URLS)
print(f"PER-NODE variance: {N_NODES} nodes, each looping full-{len(ALL_IDS)} passes concurrently | "
      f"conc/node {NODE_CONC} | caps {CAPS} | budget {BUDGET_SECONDS//60}m", flush=True)

PASSES = []
plock = threading.Lock()

def _save():
    with plock:
        json.dump({"passes": PASSES}, open(VAR, "w"))

def _node_loop(i, base_url):
    k = 0; longest = 0.0
    while True:
        remaining = DEADLINE - _t.time()
        if remaining < max(longest * 1.15, 300):
            print(f"[node{i}] stopping after {k} passes (remaining {remaining/60:.0f}m, longest pass {longest/60:.0f}m)", flush=True)
            return
        k += 1
        out = OUT / f"node{i}" / f"run_{k}"
        if out.exists(): shutil.rmtree(out)
        out.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ); env["OPENAI_BASE_URL"] = base_url; env["OPENAI_API_KEY"] = "EMPTY"
        cmd = [sys.executable, "-m", "swegemma", "eval", "--tasks", str(TASKS), "--snapshots-dir", str(SNAPS),
               "--results-dir", str(out), "--submission-dir", str(AGENT), "--sandbox", "subprocess",
               "--concurrency", str(NODE_CONC), "--display", "quiet"] + CAPS
        for t in ALL_IDS: cmd += ["--task-id", t]
        t0 = _t.time(); timed_out = False
        print(f"[node{i}] pass {k} start (elapsed {(t0-START)/60:.1f}m)", flush=True)
        try:
            _sp.run(cmd, env=env, capture_output=True, text=True, timeout=max(120, HARD_STOP - t0))
        except _sp.TimeoutExpired:
            timed_out = True
        dur = _t.time() - t0
        rows = []
        rf = out / "task_results.jsonl"
        if rf.exists():
            for l in open(rf):
                if l.strip():
                    try: rows.append(json.loads(l))
                    except Exception: pass
        compact = [{"id": r["instance_id"], "resolved": bool(r.get("resolved")), "calls": r.get("tool_calls"),
                    "patch": r.get("agent_patch_size"), "dur": r.get("duration_seconds"),
                    "rc": r.get("test_exit_code")} for r in rows]
        n_res = sum(1 for r in compact if r["resolved"])
        entry = {"node": i, "run": k, "n": len(compact), "k": n_res, "seconds": round(dur, 1),
                 "complete": (len(compact) >= len(ALL_IDS) - 4 and not timed_out), "timed_out": timed_out,
                 "rows": compact}
        PASSES.append(entry); _save()
        if entry["complete"]: longest = max(longest, dur)
        print(f"[node{i}] pass {k}: {n_res}/{len(compact)} in {dur/60:.1f}m (complete={entry['complete']})", flush=True)
        if k > 1:   # keep forensic dirs only for each node's first pass (download size)
            for d in ("logs", "traces", "test_outputs"):
                shutil.rmtree(out / d, ignore_errors=True)

threads = [threading.Thread(target=_node_loop, args=(i, BASE_URLS[i])) for i in range(N_NODES)]
for th in threads: th.start()
for th in threads: th.join()

# ---------------- analysis over COMPLETE passes ----------------
good = [p for p in PASSES if p["complete"]]
ks = [p["k"] for p in good]
hit = Counter()
for p in good:
    for r in p["rows"]:
        if r["resolved"]: hit[r["id"]] += 1
P = len(good)
stable = sorted(t for t, c in hit.items() if c == P) if P else []
flaky = sorted(((t, c) for t, c in hit.items() if 0 < c < P), key=lambda x: -x[1])
by_node = {}
for p in good: by_node.setdefault(p["node"], []).append(p["k"])
summary = {
    "complete_passes": P, "all_passes": len(PASSES), "k_per_pass": ks,
    "k_mean": round(_stats.mean(ks), 2) if ks else 0,
    "k_sd": round(_stats.pstdev(ks), 2) if len(ks) > 1 else 0,
    "k_min": min(ks) if ks else 0, "k_max": max(ks) if ks else 0,
    "k_by_node": by_node,
    "stable_n": len(stable), "stable_core": stable,
    "flaky_n": len(flaky), "flaky": [{"task": t, "hits": c, "of": P} for t, c in flaky],
    "ever_solved": len(hit), "never_solved": len(ALL_IDS) - len(hit),
}
json.dump({"passes": PASSES, "summary": summary}, open(VAR, "w"))
print("\n" + "=" * 60 + f"\nPER-NODE VARIANCE SUMMARY ({P} complete passes of {len(ALL_IDS)})\n" + "=" * 60, flush=True)
print(f"  k per pass: {ks}", flush=True)
print(f"  mean {summary['k_mean']} sd {summary['k_sd']} min {summary['k_min']} max {summary['k_max']}", flush=True)
print(f"  k by node: {by_node}", flush=True)
print(f"  STABLE (every pass): {len(stable)} | FLAKY: {len(flaky)} | ever: {len(hit)} | never: {summary['never_solved']}", flush=True)
print(f"  stable core: {stable}", flush=True)
print(f"  flaky: {summary['flaky']}", flush=True)
print("wrote variance.json", flush=True)
'''
EVAL = (EVAL.replace("__BUDGET__", str(BUDGET_SECONDS))
            .replace("__RESERVE__", str(SAVE_RESERVE_SECONDS))
            .replace("__CONC__", str(NODE_CONC)))
compile(EVAL, "cell4", "exec")   # syntax gate before we ever push

nb["cells"][4]["source"] = EVAL.splitlines(keepends=True)
nb["cells"][0]["source"] = [
    "# E4B ca5 PER-NODE VARIANCE - each of the 4 L4 servers loops its OWN full-129 passes concurrently (~3h)\n",
    "No cross-node barrier. variance.json holds every task row, so it is the only file needed to analyse.\n",
]
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir()
(DST / "e4b-variance-pernode.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
meta = json.loads((SRC / "kernel-metadata.json").read_text(encoding="utf-8"))
meta.update(id="comfyops/e4b-variance-pernode", title="e4b variance pernode", code_file="e4b-variance-pernode.ipynb")
(DST / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("wrote", DST, "| nodes follow BASE_URLS (4) | conc/node", NODE_CONC, "| budget", BUDGET_SECONDS, "s")
