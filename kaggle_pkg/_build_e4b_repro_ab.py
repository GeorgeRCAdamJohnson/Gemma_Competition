"""Build kaggle_pkg/push_e4b_repro_ab: E4B PER-NODE A/B of two LoopAgent bundles on the 39 ever-solved live tasks.

  node0,node1 = ARM_F_retry_fresh : LoopAgent[fixer, verifier], gate = existing tests          (80/30/200)
  node2,node3 = ARM_R_retry_repro : LoopAgent[tester, fixer, verifier], gate = existing + repro (80/30/200)

Bundles come from local_eval/parity_rig/_build_repro_retry.py (gate unit-tested offline: _test_repro_gate.sh 15/15).
Control (plain ca5, LF, same 85-task harness, same day) = comfyops/e4b-cap-ab passes restricted to these 39 ids.
Forks push_e4b_cap_ab; changes: arm files embedded with RELATIVE PATH keys (multi-file bundles), a 1-task smoke
per arm before the main loop (fail fast on config/compile errors), the 39-id task list, and a richer per-row record
(error, duration) so per-task conversion and scorer-time feasibility can be read from variance_ab.json.
"""
import base64
import hashlib
import json
import re
import shutil
from pathlib import Path

import os

K = Path(__file__).resolve().parent
RIG = K.parent / "local_eval" / "parity_rig"
SRC = K / "push_e4b_cap_ab"
# MODE=repro (default, the original 39-task F vs R run) | MODE=pack (pre-submission validation: pack 1 vs pack 2, all 129)
MODE = os.environ.get("MODE", "repro")
SMOKE_ID = "fastapi_14786"
PACKS = {"ARM_P1_retry_fresh": RIG / "agent_e4b_retry_fresh", "ARM_P2_retry_vnone": RIG / "agent_e4b_retry_fresh_vnone"}
if MODE.startswith("pack"):
    # pack = both packs, 2 nodes each; pack1 / pack2 = ONE pack on all 4 nodes (one Kaggle session per pack)
    sel = {"pack": list(PACKS), "pack1": ["ARM_P1_retry_fresh"], "pack2": ["ARM_P2_retry_vnone"]}[MODE]
    ARM_DIRS = {a: PACKS[a] for a in sel}
    SLUG = {"pack": "e4b-pack-ab", "pack1": "e4b-pack1-val", "pack2": "e4b-pack2-val"}[MODE]
    DST = K / ("push_" + SLUG.replace("-", "_"))
    BUDGET_SECONDS = int(4.5 * 3600)
    order = [json.loads(l)["instance_id"] for l in (K / "taskdefs" / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    N_IDS = 129
else:
    DST = K / "push_e4b_repro_ab"
    SLUG = "e4b-repro-ab"
    BUDGET_SECONDS = int(4.0 * 3600)
    ARM_DIRS = {"ARM_F_retry_fresh": RIG / "agent_e4b_retry_fresh", "ARM_R_retry_repro": RIG / "agent_e4b_retry_repro"}
    ever = json.loads((K.parent / "Outputs" / "_solvable85.json").read_text(encoding="utf-8"))["ever"]
    order = [t for t in json.loads((K / "live_ids_31b_ab.json").read_text(encoding="utf-8"))["order"] if t in set(ever)]
    N_IDS = 39
assert len(order) == N_IDS and len(set(order)) == N_IDS and SMOKE_ID in order, len(order)

nb = json.loads((SRC / "e4b-cap-ab.ipynb").read_text(encoding="utf-8"))
c2 = "".join(nb["cells"][2]["source"])
m = re.search(r'ARMS = json\.loads\("""(.*?)"""\)', c2, re.S)
old = json.loads(m.group(1))
tasks_gz = old["ARM_A_cap40_12"]["tasks.jsonl_gz"]

b64 = lambda b: base64.b64encode(b).decode()
arms = {}
for arm, d in ARM_DIRS.items():
    files = {p.relative_to(d).as_posix(): b64(p.read_bytes()) for p in sorted(d.rglob("*")) if p.is_file()}
    assert "agent.yaml" in files and "skills/submit-gate/scripts/check.py" in files
    for rel, v in files.items():
        raw = base64.b64decode(v)
        assert b"\r" not in raw and not raw.startswith(b"\xef\xbb\xbf"), f"{arm}/{rel}: CRLF or BOM"
    arms[arm] = files
first = list(ARM_DIRS)[0]
arms[first]["tasks.jsonl_gz"] = tasks_gz
c2 = c2.replace(m.group(0), 'ARMS = json.loads("""%s""")' % json.dumps(arms), 1)
c2 = c2.replace('ARMS["ARM_A_cap40_12"]["tasks.jsonl_gz"]', f'ARMS["{first}"]["tasks.jsonl_gz"]')
c2 = c2.replace('AGENT = AGENT_DIRS["ARM_A_cap40_12"]', f'AGENT = AGENT_DIRS["{first}"]')
OLD_W = '_d = _a / _PATHS[_rel]; _d.parent.mkdir(parents=True, exist_ok=True)'
assert c2.count(OLD_W) == 1
c2 = c2.replace(OLD_W, '_d = _a / _PATHS.get(_rel, _rel); _d.parent.mkdir(parents=True, exist_ok=True)')
OLD_NEED = 'for _need in ("agent.yaml", "prompts/system.md", "configs/sampling.yaml", "eval_config.yaml"):'
assert c2.count(OLD_NEED) == 1
c2 = c2.replace(OLD_NEED, 'for _need in ("agent.yaml", "eval_config.yaml", "skills/submit-gate/scripts/check.py"):')
OLD_SHA = '_sha = hashlib.sha1((_a / "prompts" / "system.md").read_bytes()).hexdigest()[:12]'
assert c2.count(OLD_SHA) == 1
c2 = c2.replace(OLD_SHA, '_sha = hashlib.sha1(b"".join(p.read_bytes() for p in sorted(_a.rglob("*")) if p.is_file())).hexdigest()[:12]; '
                         'print("    files:", sorted(p.relative_to(_a).as_posix() for p in _a.rglob("*") if p.is_file()))')
assert "ARM_A_cap40_12" not in c2 and "ARM_B_cap50_20" not in c2
compile(c2, "cell2", "exec")
nb["cells"][2]["source"] = c2.splitlines(keepends=True)

c4 = "".join(nb["cells"][4]["source"])
c4 = re.sub(r"BUDGET_SECONDS = \d+", f"BUDGET_SECONDS = {BUDGET_SECONDS}", c4, count=1)
_names = list(ARM_DIRS)
A1, A2 = (_names[0], _names[-1])  # single-arm modes: all 4 nodes run the same pack
c4 = c4.replace('NODE_ARM = {0: "ARM_A_cap40_12", 1: "ARM_A_cap40_12", 2: "ARM_B_cap50_20", 3: "ARM_B_cap50_20"}',
                'NODE_ARM = {0: "%s", 1: "%s", 2: "%s", 3: "%s"}' % (A1, A1, A2, A2))
c4 = re.sub(r"LIVE = \[.*?\]\nassert set\(LIVE\) <= set\(ALL_IDS\) and len\(LIVE\) == 85",
            "LIVE = %s\nassert set(LIVE) <= set(ALL_IDS) and len(LIVE) == %d" % (json.dumps(order).replace("\\", "\\\\"), N_IDS),
            c4, count=1, flags=re.S)
OLD_ROW = '''compact = [{"id": r["instance_id"], "resolved": bool(r.get("resolved")), "calls": r.get("tool_calls"),
                    "patch": r.get("agent_patch_size")} for r in rows]'''
assert c4.count(OLD_ROW) == 1
c4 = c4.replace(OLD_ROW, '''compact = [{"id": r["instance_id"], "resolved": bool(r.get("resolved")), "calls": r.get("tool_calls"),
                    "patch": r.get("agent_patch_size"), "dur": r.get("duration_seconds"),
                    "llm": r.get("total_llm_calls"), "err": str(r.get("error") or "")[:120]} for r in rows]''')
# keep pass-1 forensics for BOTH nodes of each arm (gate outputs live in the logs)
c4 = c4.replace("        if k > 1:\n            for d in (\"logs\", \"traces\", \"test_outputs\"):",
                "        if k > 2:\n            for d in (\"logs\", \"traces\", \"test_outputs\"):")
SMOKE = r'''
# ---------- SMOKE: 1 task per arm, fail fast on config/compile errors before spending the budget ----------
def _smoke(arm):
    out = OUT / "smoke" / arm; out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ); env["OPENAI_BASE_URL"] = BASE_URLS[0]; env["OPENAI_API_KEY"] = "EMPTY"
    cmd = [sys.executable, "-m", "swegemma", "eval", "--tasks", str(TASKS), "--snapshots-dir", str(SNAPS),
           "--results-dir", str(out), "--submission-dir", str(AGENT_DIRS[arm]), "--sandbox", "subprocess",
           "--concurrency", "1", "--display", "quiet", "--task-id", "__SMOKE__"] + _caps(AGENT_DIRS[arm])
    p = _sp.run(cmd, env=env, capture_output=True, text=True, timeout=2400)
    rf = out / "task_results.jsonl"
    rows = [json.loads(l) for l in open(rf) if l.strip()] if rf.exists() else []
    print(f"[smoke {arm}] rc={p.returncode} rows={len(rows)} " + (json.dumps({k: rows[0].get(k) for k in
          ("resolved", "tool_calls", "total_llm_calls", "agent_patch_size", "duration_seconds", "error")}) if rows else ""), flush=True)
    if not rows or (rows[0].get("error") and not rows[0].get("tool_calls")):
        print("STDOUT tail:", (p.stdout or "")[-2500:], "\nSTDERR tail:", (p.stderr or "")[-2500:], flush=True)
        raise SystemExit(f"smoke failed for {arm}: no usable result row")
_st = _t.time()
_errs_smoke = []
def _wrap(a):
    try: _smoke(a)
    except SystemExit as e: _errs_smoke.append(str(e))
_ths = [threading.Thread(target=_wrap, args=(a,)) for a in AGENT_DIRS]
for th in _ths: th.start()
for th in _ths: th.join()
if _errs_smoke:
    raise SystemExit("; ".join(_errs_smoke))
print(f"SMOKE OK for all arms in {(_t.time()-_st)/60:.1f} min", flush=True)
START = _t.time(); HARD_STOP = START + BUDGET_SECONDS; DEADLINE = HARD_STOP - SAVE_RESERVE
'''.replace("__SMOKE__", SMOKE_ID)
ANCHOR = "PASSES = []\nplock = threading.Lock()"
assert c4.count(ANCHOR) == 1 and "def _caps(agent_dir):" in c4 and c4.index("def _caps(agent_dir):") < c4.index(ANCHOR)
c4 = c4.replace(ANCHOR, SMOKE + ANCHOR, 1)
c4 = c4.replace("# ---------- E4B PER-NODE CAP A/B: node0/1 = 40/12, node2/3 = 50/20, 85 live tasks. No cross-node barrier. ----------",
                "# ---------- E4B PER-NODE A/B: node0/1 = %s, node2/3 = %s, %d tasks ----------" % (A1, A2, N_IDS))
for must in (A1, A2, "len(LIVE) == %d" % N_IDS, f"BUDGET_SECONDS = {BUDGET_SECONDS}", "SMOKE OK for all arms", '"dur": r.get("duration_seconds")'):
    assert must in c4, must
assert "ARM_A_cap40_12" not in c4
compile(c4, "cell4", "exec")
nb["cells"][4]["source"] = c4.splitlines(keepends=True)
nb["cells"][0]["source"] = [
    "# E4B PER-NODE A/B (%s): %s (node0,1) vs %s (node2,3), %d tasks\n" % (MODE, A1, A2, N_IDS),
    ("Pre-submission validation of the two E4B ship packs on the full 129 (score + scorer-runtime proxy).\n" if MODE == "pack"
     else "Control = comfyops/e4b-cap-ab (plain ca5 LF, same harness) restricted to the same 39 ids.\n"),
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
print("wrote", DST, "| tasks", len(order), "| budget h", BUDGET_SECONDS / 3600)
for arm, files in arms.items():
    print(" ", arm, len([k for k in files if k != "tasks.jsonl_gz"]), "files")
