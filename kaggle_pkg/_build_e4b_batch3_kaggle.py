"""Build kaggle_pkg/push_e4b_batch3: E4B batch-3 A/B on Kaggle (4x L4, one arm per node) on the 26 landable tasks.

  node0 = C_pack1 (84f904c63afd)   node1 = H_hygiene (eccf4b1af3f3)
  node2 = HT5 (41ecd618d3a3)       node3 = HG4 (e8ae58167994)
Arms come from colab_fasteval/arms3 (built by colab_fasteval/_build_arms3.py). Same per-node pass loop as
push_e4b_repro_ab (forked from push_e4b_cap_ab), conc 8/node, 1-task smoke per arm first.
usage: python kaggle_pkg/_build_e4b_batch3_kaggle.py [budget_hours] [batch]   batch = batch3 (default) | batch2
  batch2 = colab_fasteval/arms2: node0 C_pack1, node1 H_hygiene, node2 HR, node3 HR4 (replicate/extension of Colab batch 2)
"""
import base64
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

K = Path(__file__).resolve().parent
ROOT = K.parent
SRC = K / "push_e4b_cap_ab"
BATCH = sys.argv[2] if len(sys.argv) > 2 else "batch3"
SLUG = f"e4b-{BATCH}"
DST = K / f"push_e4b_{BATCH}"
BUDGET_SECONDS = int(float(sys.argv[1] if len(sys.argv) > 1 else 4.0) * 3600)
SMOKE_ID = "fastapi_14786"
CFG = {
    "batch3": ("arms3", ["C_pack1", "H_hygiene", "HT5", "HG4"],
               {"C_pack1": "84f904c63afd", "H_hygiene": "eccf4b1af3f3", "HT5": "41ecd618d3a3", "HG4": "e8ae58167994"}),
    "batch2": ("arms2", ["C_pack1", "H_hygiene", "HR", "HR4"],
               {"C_pack1": "84f904c63afd", "H_hygiene": "eccf4b1af3f3", "HR": "d27caa450589", "HR4": "798bee807618"}),
}
_arms_dir, NODES, WANT = CFG[BATCH]
A3 = ROOT / "colab_fasteval" / _arms_dir
order = json.loads((ROOT / "colab_fasteval" / "ab_tasks.json").read_text(encoding="utf-8"))
N_IDS = len(order)
assert N_IDS == 26 and SMOKE_ID in order

nb = json.loads((SRC / "e4b-cap-ab.ipynb").read_text(encoding="utf-8"))
c2 = "".join(nb["cells"][2]["source"])
m = re.search(r'ARMS = json\.loads\("""(.*?)"""\)', c2, re.S)
tasks_gz = json.loads(m.group(1))["ARM_A_cap40_12"]["tasks.jsonl_gz"]
arms = {}
for a in NODES:
    d = A3 / a
    raw = {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}
    sha = hashlib.sha1(b"".join(raw[n] for n in sorted(raw))).hexdigest()[:12]
    assert sha == WANT[a], (a, sha)
    for rel, b in raw.items():
        assert b"\r" not in b and not b.startswith(b"\xef\xbb\xbf"), f"{a}/{rel}: CRLF or BOM"
    arms[a] = {rel: base64.b64encode(b).decode() for rel, b in raw.items()}
first = NODES[0]
arms[first]["tasks.jsonl_gz"] = tasks_gz
c2 = c2.replace(m.group(0), 'ARMS = json.loads("""%s""")' % json.dumps(arms), 1)
c2 = c2.replace('ARMS["ARM_A_cap40_12"]["tasks.jsonl_gz"]', f'ARMS["{first}"]["tasks.jsonl_gz"]')
c2 = c2.replace('AGENT = AGENT_DIRS["ARM_A_cap40_12"]', f'AGENT = AGENT_DIRS["{first}"]')
for old, new in [
    ('_d = _a / _PATHS[_rel]; _d.parent.mkdir(parents=True, exist_ok=True)',
     '_d = _a / _PATHS.get(_rel, _rel); _d.parent.mkdir(parents=True, exist_ok=True)'),
    ('for _need in ("agent.yaml", "prompts/system.md", "configs/sampling.yaml", "eval_config.yaml"):',
     'for _need in ("agent.yaml", "eval_config.yaml", "skills/submit-gate/scripts/check.py"):'),
    ('_sha = hashlib.sha1((_a / "prompts" / "system.md").read_bytes()).hexdigest()[:12]',
     '_fs = {p.relative_to(_a).as_posix(): p.read_bytes() for p in _a.rglob("*") if p.is_file()}; '
     '_sha = hashlib.sha1(b"".join(_fs[n] for n in sorted(_fs))).hexdigest()[:12]'),
]:
    assert c2.count(old) == 1, old
    c2 = c2.replace(old, new, 1)
assert "ARM_A_cap40_12" not in c2 and "ARM_B_cap50_20" not in c2
compile(c2, "cell2", "exec")
nb["cells"][2]["source"] = c2.splitlines(keepends=True)

c4 = "".join(nb["cells"][4]["source"])
c4 = re.sub(r"BUDGET_SECONDS = \d+", f"BUDGET_SECONDS = {BUDGET_SECONDS}", c4, count=1)
old_na = 'NODE_ARM = {0: "ARM_A_cap40_12", 1: "ARM_A_cap40_12", 2: "ARM_B_cap50_20", 3: "ARM_B_cap50_20"}'
assert c4.count(old_na) == 1
c4 = c4.replace(old_na, "NODE_ARM = {%s}" % ", ".join(f'{i}: "{a}"' for i, a in enumerate(NODES)))
c4, n = re.subn(r"LIVE = \[.*?\]\nassert set\(LIVE\) <= set\(ALL_IDS\) and len\(LIVE\) == 85",
                "LIVE = %s\nassert set(LIVE) <= set(ALL_IDS) and len(LIVE) == %d" % (json.dumps(order), N_IDS), c4, count=1, flags=re.S)
assert n == 1
OLD_ROW = '''compact = [{"id": r["instance_id"], "resolved": bool(r.get("resolved")), "calls": r.get("tool_calls"),
                    "patch": r.get("agent_patch_size")} for r in rows]'''
assert c4.count(OLD_ROW) == 1
c4 = c4.replace(OLD_ROW, '''compact = [{"id": r["instance_id"], "resolved": bool(r.get("resolved")), "calls": r.get("tool_calls"),
                    "patch": r.get("agent_patch_size"), "dur": r.get("duration_seconds"),
                    "llm": r.get("total_llm_calls"), "err": str(r.get("error") or "")[:160]} for r in rows]''')
SMOKE = r'''
# ---------- SMOKE: 1 task per arm, fail fast on config/compile errors before spending the budget ----------
def _smoke(arm):
    out = OUT / "smoke" / arm; out.mkdir(parents=True, exist_ok=True)
    # each arm smokes on its OWN node's server (was BASE_URLS[0] for all: 3 GPUs idle during the smoke)
    _node = next((i for i, a in NODE_ARM.items() if a == arm), 0)
    env = dict(os.environ); env["OPENAI_BASE_URL"] = BASE_URLS[_node % len(BASE_URLS)]; env["OPENAI_API_KEY"] = "EMPTY"
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
assert c4.count(ANCHOR) == 1
c4 = c4.replace(ANCHOR, SMOKE + ANCHOR, 1)
c4 = c4.replace("# ---------- E4B PER-NODE CAP A/B: node0/1 = 40/12, node2/3 = 50/20, 85 live tasks. No cross-node barrier. ----------",
                "# ---------- E4B %s: one arm per node %s, %d landable tasks ----------" % (BATCH.upper(), NODES, N_IDS))
for must in NODES + [f"len(LIVE) == {N_IDS}", f"BUDGET_SECONDS = {BUDGET_SECONDS}", "SMOKE OK for all arms"]:
    assert must in c4, must
assert "ARM_A_cap40_12" not in c4
compile(c4, "cell4", "exec")
nb["cells"][4]["source"] = c4.splitlines(keepends=True)
nb["cells"][0]["source"] = ["# E4B BATCH 3 (Kaggle 4x L4): one arm per node %s, %d landable tasks, %.1f h\n" % (NODES, N_IDS, BUDGET_SECONDS / 3600)]
for c in nb["cells"]:
    if c.get("cell_type") == "code":
        c["outputs"] = []
        c["execution_count"] = None
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir()
(DST / f"{SLUG}.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
meta = json.loads((SRC / "kernel-metadata.json").read_text(encoding="utf-8"))
meta.pop("id_no", None)
meta.update(id=f"comfyops/{SLUG}", title=SLUG.replace("-", " "), code_file=f"{SLUG}.ipynb")
(DST / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("wrote", DST, "| tasks", N_IDS, "| budget h", BUDGET_SECONDS / 3600, "| nodes", NODES)
