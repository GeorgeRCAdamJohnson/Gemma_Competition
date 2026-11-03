"""Build kaggle_pkg/push_e4b_3arm: the FastAPI-vs-Rich 3-arm experiment in ONE kernel.

Arms (same 12-task balanced cohort, same caps, same model):
  A control  = agent_ctrl_e4b            (plain ca5)
  B global   = agent_ctrl_e4b_sibling    (sibling-mirror everywhere)
  C repocond = agent_ctrl_e4b_repocond   (rich: sibling-mirror; fastapi: contract-first, no mirror)

Cohort (all gold-valid, mix of near-miss / stable / budget-bound, balanced 6 rich + 6 fastapi):
  rich: 4077 3894 3518 3882 3067 3944
  fastapi: 14301 14463 14458 14873 9555 14349

Runs on 4 tp=1 servers (concurrent boot, the fixed parallel harness). For each arm, the 12 tasks are
sharded across the 4 servers. 3 arms x 12 tasks = 36 evals; at ~60-150s each across 4 GPUs this is
roughly 20-30 min after a one-time ~300s concurrent boot.

Reuses the concurrent-boot serve cell from _build_parallel_kernel's push_e4b_verify_par (proven), swaps
in a multi-arm eval cell that materializes all 3 agent dirs and loops arms.
"""
import base64
import json
import re
import shutil
from pathlib import Path

K = Path(__file__).resolve().parent
SRC = K / "push_e4b_verify_par"      # has the concurrent-boot serve cell + embed machinery
DST = K / "push_e4b_3arm"
RIG = K.parent / "local_eval" / "parity_rig"
BUNDLES = {"A_control": RIG / "agent_ctrl_e4b",
           "B_global": RIG / "agent_ctrl_e4b_sibling",
           "C_repocond": RIG / "agent_ctrl_e4b_repocond"}
COHORT = ["rich_4077", "rich_3894", "rich_3518", "rich_3882", "rich_3067", "rich_3944",
          "fastapi_14301", "fastapi_14463", "fastapi_14458", "fastapi_14873", "fastapi_9555", "fastapi_14349"]

assert SRC.is_dir(), "run _build_parallel_kernel.py first (need push_e4b_verify_par)"
for n, b in BUNDLES.items():
    assert b.is_dir(), f"missing bundle {n}: {b}"
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir()

# embed every file of every bundle under ARMS[arm][relpath] = b64
ARMS = {}
for arm, b in BUNDLES.items():
    files = {}
    for p in sorted(b.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            files[p.relative_to(b).as_posix()] = base64.b64encode(p.read_bytes()).decode()
    ARMS[arm] = files

nb = json.loads((SRC / "e4b-verify-par.ipynb").read_text(encoding="utf-8"))

# ---- CELL 2: replace the single-bundle EMBED with the multi-arm ARMS + materialize each arm dir ----
cell2 = "".join(nb["cells"][2]["source"])
m_embed = re.search(r'EMBED = json\.loads\("""(.*?)"""\)', cell2, re.S)
tasks_gz = json.loads(m_embed.group(1))["tasks.jsonl_gz"]

# build the new cell2 header: write tasks + materialize all 3 arm dirs into /kaggle/working/arms/<arm>
new_head = '''import os, sys, json, subprocess, shutil, glob, base64, gzip, ast, hashlib
from pathlib import Path
import torch
n = torch.cuda.device_count() if torch.cuda.is_available() else 0
print("device_count:", n)
TP = 1
ARMS = json.loads("""%s""")
TASKS_GZ = "%s"
WORK = Path("/kaggle/working"); WORK.mkdir(parents=True, exist_ok=True)
TASKS = WORK / "tasks.jsonl"
TASKS.write_bytes(gzip.decompress(base64.b64decode(TASKS_GZ)))
n_tasks = sum(1 for l in open(TASKS) if l.strip()); print("tasks:", n_tasks); assert n_tasks == 129
ARMS_DIR = WORK / "arms"
if ARMS_DIR.exists(): shutil.rmtree(ARMS_DIR)
AGENT_DIRS = {}
for _arm, _files in ARMS.items():
    _a = ARMS_DIR / _arm
    _a.mkdir(parents=True, exist_ok=True)
    for _rel, _b64 in _files.items():
        _d = _a / _rel; _d.parent.mkdir(parents=True, exist_ok=True)
        _d.write_bytes(base64.b64decode(_b64))
    for _py in _a.rglob("scripts/*.py"):
        ast.parse(_py.read_text(encoding="utf-8"))
    for _sm in _a.rglob("SKILL.md"):
        assert _sm.read_bytes()[:3] == b"---"
    _sha = hashlib.sha1((_a / "prompts" / "system.md").read_bytes()).hexdigest()[:12]
    print(f"  arm {_arm}: {_sha} ({sum(1 for _ in _a.rglob('*') if _.is_file())} files)")
    AGENT_DIRS[_arm] = _a
# snapshots (reuse the stock resolver already present below)
''' % (json.dumps(ARMS), tasks_gz)

# keep the snapshot-resolution tail from the original cell2 (everything after the tasks/snapshots setup).
# The original cell2 set SNAPS via glob; grab that block.
m_snap = re.search(r'(hits = glob\.glob\("/kaggle/input/\*\*/\*\.tgz".*?INPUTS OK.*?\n)', cell2, re.S)
assert m_snap, "snapshot resolver block not found in cell2"
cell2_new = new_head + m_snap.group(1)
nb["cells"][2]["source"] = cell2_new.splitlines(keepends=True)

# ---- CELL 3 (serve): the inherited serve cell references AGENT (for the declared model + adapters)
# BEFORE our insert point, so define AGENT at the very TOP of the cell. All arms declare the same model
# and ship no adapter, so the control arm dir is a fine stand-in for serve purposes. ----
cell3 = "".join(nb["cells"][3]["source"])
assert "AGENT = AGENT_DIRS" not in cell3
cell3 = "AGENT = AGENT_DIRS['A_control']  # serve stand-in: all arms share model, no adapters\n" + cell3
nb["cells"][3]["source"] = cell3.splitlines(keepends=True)

# ---- CELL 4: multi-arm sharded eval ----
EVAL = r'''# ---------- 3-ARM eval: each arm's 12-task cohort sharded across the 4 servers ----------
import threading, subprocess as _sp, yaml as _yaml, time as _t
COHORT = __COHORT__
PER_GPU_CONC = 3
RESULTS = {}
BASE_DIRS = [s.base_url for s in SERVERS]

def _caps(agent_dir):
    _raw = _yaml.safe_load((Path(agent_dir) / "eval_config.yaml").read_text()) or {}
    c = _raw.get("evaluation", _raw) or {}
    caps = []
    for k, flag in (("max_tool_calls","--max-tool-calls"),("max_time_minutes","--max-time-minutes"),("max_turns","--max-turns")):
        if c.get(k) is not None: caps += [flag, str(c[k])]
    return caps

for ARM, AGENT in AGENT_DIRS.items():
    caps = _caps(AGENT)
    out = WORK / "results" / ARM; out.mkdir(parents=True, exist_ok=True)
    shards = [COHORT[i::len(BASE_URLS)] for i in range(len(BASE_URLS))]
    lock = threading.Lock(); rows = []
    def _run(i, base_url, ids):
        if not ids: return
        so = out / f"shard{i}"; so.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ); env["OPENAI_BASE_URL"] = base_url; env["OPENAI_API_KEY"] = "EMPTY"
        cmd = [sys.executable, "-m", "swegemma", "eval", "--tasks", str(TASKS), "--snapshots-dir", str(SNAPS),
               "--results-dir", str(so), "--submission-dir", str(AGENT), "--sandbox", "subprocess",
               "--concurrency", str(PER_GPU_CONC), "--display", "quiet"] + caps
        for t in ids: cmd += ["--task-id", t]
        p = _sp.run(cmd, env=env, capture_output=True, text=True)
        rf = so / "task_results.jsonl"
        got = [json.loads(l) for l in open(rf)] if rf.exists() else []
        with lock: rows.extend(got)
    ths = [threading.Thread(target=_run, args=(i, BASE_URLS[i], shards[i])) for i in range(len(BASE_URLS))]
    t0 = _t.time()
    print(f"\n=== ARM {ARM}: {len(COHORT)} tasks across {len(BASE_URLS)} GPUs ===", flush=True)
    for th in ths: th.start()
    for th in ths: th.join()
    for r in sorted(rows, key=lambda r: r["instance_id"]):
        print(f"  [{ARM}] {r['instance_id']:<16} resolved={bool(r.get('resolved'))} calls={r.get('tool_calls')} "
              f"patch={r.get('agent_patch_size')} rc={r.get('test_exit_code')}", flush=True)
    k = sum(int(bool(r.get("resolved"))) for r in rows)
    byrepo = {}
    for r in rows:
        rp = r["instance_id"].split("_")[0]; d = byrepo.setdefault(rp,[0,0]); d[0]+=int(bool(r.get("resolved"))); d[1]+=1
    RESULTS[ARM] = {"resolved": k, "total": len(rows), "by_repo": byrepo,
                    "resolved_ids": sorted(r["instance_id"] for r in rows if r.get("resolved"))}
    print(f"  ARM {ARM}: {k}/{len(rows)} in {_t.time()-t0:.0f}s | by_repo {byrepo}", flush=True)

print("\n" + "="*60 + "\n3-ARM SUMMARY (FastAPI vs Rich)\n" + "="*60, flush=True)
for ARM, R in RESULTS.items():
    rr = R["by_repo"].get("rich",[0,0]); fa = R["by_repo"].get("fastapi",[0,0])
    print(f"  {ARM:<12} total {R['resolved']}/{R['total']}  rich {rr[0]}/{rr[1]}  fastapi {fa[0]}/{fa[1]}", flush=True)
print("\nREAD: does B beat A on rich WITHOUT losing fastapi? does C recover fastapi where B lost it?", flush=True)
json.dump(RESULTS, open(WORK / "summary_3arm.json","w"), indent=2)
print("wrote summary_3arm.json", flush=True)
'''
EVAL = EVAL.replace("__COHORT__", json.dumps(COHORT))
nb["cells"][4]["source"] = EVAL.splitlines(keepends=True)

nb["cells"][0]["source"] = [
    "# E4B FastAPI-vs-Rich 3-ARM experiment (A=ca5, B=global sibling, C=repo-conditional)\n",
    f"Balanced 12-task cohort: {COHORT}\n",
    "Q: does the Rich sibling-mirror rule help rich WITHOUT hurting fastapi? does repo-conditional fix it?\n",
]
(DST / "e4b-3arm.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
meta = json.loads((SRC / "kernel-metadata.json").read_text(encoding="utf-8"))
meta.update(id="comfyops/e4b-3arm", title="e4b 3arm fastapi vs rich", code_file="e4b-3arm.ipynb")
(DST / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("wrote", DST, "| arms", list(ARMS), "| cohort", len(COHORT))
