"""Build kaggle_pkg/push_31b_sibling_ab: PAIRED 31B A/B of ca5 vs ca5+MIRROR THE ADJACENT SIBLING, 8h wall budget.

Design (user, 2026-11-04): ~8 wall-clock hours of Kaggle GPU; do not spend it on unsolvable tasks.
- Forks push_129_off31 (the kernel that produced ca5-31B 35/129): ONE tp=4 31B server, ca5 agent embedded
  verbatim (system.md sha b08b32a2438d, 28 calls / 8 min / 120 turns, thinking 4096). That is ARM A (control).
- ARM B = ARM A with exactly one change: the 12-line MIRROR THE ADJACENT SIBLING section inserted before
  "## Strategy: conform to the pattern" (same text/position as the E4B arm). Verified in this builder.
- Both arms run CONCURRENTLY on the same server (2 agent loops each, 4 total = the reference run's regime),
  in paired CHUNKS of the same task ids, so server state/time conditions are identical and a stop mid-round
  still leaves balanced pairs.
- Task set = LIVE tasks only: rich + fastapi, minus tasks whose tests cannot be collected in the Kaggle image
  (missing inline_snapshot / dirty_equals / scripts.prepare_release; list from kaggle_pkg/live_dead_129.json,
  + fastapi_14266 which had no run_1 log but fails the gold-test scan), minus requests/httpx (src-layout:
  the subprocess sandbox skips the editable install, so src/ edits cannot register in this harness).
- Round 1 = all live tasks (fixed shuffled order). Later rounds = rich only. Time-boxed: a chunk starts only
  if remaining time > 1.25x the longest chunk so far; a chunk subprocess is killed at the hard deadline.
- Output: ab31.json (every run row, rewritten after every chunk) + results.tar.gz (forensics) so the
  download is two files, not thousands.
"""
import base64
import json
import random
import re
import shutil
from pathlib import Path

K = Path(__file__).resolve().parent
SRC = K / "push_129_off31"
DST = K / "push_31b_sibling_ab"
EVAL_BUDGET_SECONDS = int(7.2 * 3600)   # from start of the eval cell; boot + wheelhouse ~0.3h before it
SAVE_RESERVE_SECONDS = 12 * 60
PER_ARM_CONC = 2
CHUNK = 10

# ---------------- live task list ----------------
ld = json.loads((K / "live_dead_129.json").read_text(encoding="utf-8"))
dead = set(ld["dead"]) | {"fastapi_14266"}
all_ids = [json.loads(l)["instance_id"] for l in (K / "taskdefs" / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
live = [t for t in all_ids if t.split("_")[0] in ("rich", "fastapi") and t not in dead]
assert len(live) == 85, len(live)
order = list(live)
random.Random(7).shuffle(order)
rich_order = [t for t in order if t.startswith("rich_")]
print("live:", len(live), "| rich", len(rich_order), "| fastapi", len(live) - len(rich_order))

# ---------------- ARM B prompt ----------------
nb = json.loads((SRC / "ca5-31b-full129.ipynb").read_text(encoding="utf-8"))
cell2 = "".join(nb["cells"][2]["source"])
m = re.search(r'EMBED = json\.loads\("""(.*?)"""\)', cell2, re.S)
emb = json.loads(m.group(1))
sys_a = base64.b64decode(emb["system.md"]).decode("utf-8")
nl = "\r\n" if "\r\n" in sys_a else "\n"
RULE = nl.join([
    "## MIRROR THE ADJACENT SIBLING \u2014 the exact-shape rule (this is what makes the fix correct)",
    "When you add or change a method/branch, look at the method DIRECTLY ABOVE or BELOW it and give your fix",
    "the SAME shape. Most correct fixes are a one-line delegation or a small guard that matches a neighbor:",
    "- DELEGATE, do not reconstruct. If the sibling `fileno()` is `return self.__file.fileno()`, then the",
    "  `isatty` fix is `return self.__file.isatty()` \u2014 forward to the wrapped object. Do NOT re-derive it a",
    "  different way (no `os.isatty(...fileno())`, no reaching for a lower-level API the neighbor doesn't use).",
    "- SMALLEST DIFF. The correct fix is almost always SMALLER than your first instinct. Prefer ADDING a guard",
    "  or a single line over REPLACING a working line. If you replace a line that already works, you likely",
    "  regress a passing test \u2014 restore it and ADD the minimal change instead.",
    "- Match the neighbor's EXACT attribute/call/return shape; do not substitute a different attribute",
    "  (e.g. do not swap `__name__` for `__qualname__`) unless the problem explicitly requires it.",
]) + nl + nl
MARK = "## Strategy: conform to the pattern"
assert sys_a.count(MARK) == 1
sys_b = sys_a.replace(MARK, RULE + MARK, 1)
assert sys_b.replace(RULE, "", 1) == sys_a, "ARM B must differ from ARM A only by the inserted rule"
emb["system_sibling.md"] = base64.b64encode(sys_b.encode("utf-8")).decode()

# ---------------- cell 2: add ARM B dir after the ca5 sha assert ----------------
ASSERT = re.search(r'assert sha == "b08b32a2438d".*?\n', cell2)
assert ASSERT, "ca5 sha assert not found in cell 2"
ARM_B_CODE = '''import shutil as _sh
AGENT_B = Path("/kaggle/working/agent_ca5_sibling")
if AGENT_B.exists():
    _sh.rmtree(AGENT_B)
_sh.copytree(AGENT, AGENT_B)
(AGENT_B / "prompts" / "system.md").write_bytes(base64.b64decode(EMBED["system_sibling.md"]))
_sha_b = hashlib.sha1((AGENT_B / "prompts" / "system.md").read_bytes()).hexdigest()[:12]
print("ARM A (control) prompt sha:", sha, "| ARM B (sibling) prompt sha:", _sha_b)
assert _sha_b != sha and (AGENT_B / "prompts" / "system.md").stat().st_size > (AGENT / "prompts" / "system.md").stat().st_size
AGENT_DIRS = {"A_control": AGENT, "B_sibling": AGENT_B}
'''
cell2 = cell2.replace(m.group(0), 'EMBED = json.loads("""%s""")' % json.dumps(emb), 1)
cell2 = cell2.replace(ASSERT.group(0), ASSERT.group(0) + ARM_B_CODE, 1)
nb["cells"][2]["source"] = cell2.splitlines(keepends=True)

# ---------------- cell 3 sanity: serve cell must export OPENAI_BASE_URL for subprocesses ----------------
cell3 = "".join(nb["cells"][3]["source"])
assert "os.environ['OPENAI_BASE_URL']" in cell3, "serve cell no longer exports OPENAI_BASE_URL"
assert "tensor_parallel_size" in cell3

# ---------------- cell 4: paired chunk loop ----------------
EVAL = r'''# ---------- PAIRED 31B A/B: ca5 (A) vs ca5 + MIRROR THE ADJACENT SIBLING (B), same server, same chunks ----------
import threading, subprocess as _sp, yaml as _yaml, time as _t, tarfile, shutil, statistics as _stats
from collections import Counter
LIVE_ORDER = __ORDER__
RICH_ORDER = __RICH__
EVAL_BUDGET = __BUDGET__
SAVE_RESERVE = __RESERVE__
PER_ARM_CONC = __CONC__
CHUNK = __CHUNK__
START = _t.time(); HARD_STOP = START + EVAL_BUDGET; DEADLINE = HARD_STOP - SAVE_RESERVE
OUT = Path("/kaggle/working/results"); OUT.mkdir(parents=True, exist_ok=True)
AB = Path("/kaggle/working/ab31.json")
_raw = _yaml.safe_load((AGENT / "eval_config.yaml").read_text()) or {}
_c = _raw.get("evaluation", _raw) or {}
CAPS = []
for k_, flag in (("max_tool_calls", "--max-tool-calls"), ("max_time_minutes", "--max-time-minutes"), ("max_turns", "--max-turns")):
    if _c.get(k_) is not None: CAPS += [flag, str(_c[k_])]
_all = {json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()}
assert all(t in _all for t in LIVE_ORDER), "live list has ids not in tasks.jsonl"
print(f"31B paired A/B: {len(LIVE_ORDER)} live tasks (rich {len(RICH_ORDER)}), arms {list(AGENT_DIRS)}, "
      f"conc/arm {PER_ARM_CONC}, chunk {CHUNK}, budget {EVAL_BUDGET/3600:.1f}h, caps {CAPS}", flush=True)

ROWS = []
def _save():
    json.dump({"rows": ROWS, "meta": {"live": len(LIVE_ORDER), "chunk": CHUNK, "conc_per_arm": PER_ARM_CONC}}, open(AB, "w"))

def _run_arm(arm, agent_dir, ids, tag, sink, timeout):
    out = OUT / tag / arm; out.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "swegemma", "eval", "--tasks", str(TASKS), "--snapshots-dir", str(SNAPS),
           "--results-dir", str(out), "--submission-dir", str(agent_dir), "--sandbox", "subprocess",
           "--concurrency", str(PER_ARM_CONC), "--display", "quiet"] + CAPS
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
    ka = sum(bool(r.get("resolved")) for r in sink["A_control"][0]); kb = sum(bool(r.get("resolved")) for r in sink["B_sibling"][0])
    print(f"[{tag}] {len(ids)} tasks: A {ka} | B {kb} | {dur/60:.1f} min | complete={complete} | elapsed {(_t.time()-START)/3600:.2f}h", flush=True)
    return dur, complete

longest = 2400.0   # initial guess for a 10-task paired chunk (s); replaced by the max observed
round_no = 0; stop = False
while not stop:
    round_no += 1
    seq = LIVE_ORDER if round_no == 1 else RICH_ORDER
    chunks = [seq[i:i + CHUNK] for i in range(0, len(seq), CHUNK)]
    for ci, ids in enumerate(chunks, start=1):
        remaining = DEADLINE - _t.time()
        if remaining < longest * 1.25:
            print(f"stopping: remaining {remaining/60:.0f} min < 1.25 x longest chunk {longest/60:.0f} min", flush=True)
            stop = True; break
        dur, ok = _chunk(round_no, ci, ids)
        if ok: longest = max(longest, dur)

# ---------------- paired analysis over COMPLETE chunks ----------------
good = [r for r in ROWS if r["chunk_complete"]]
def _by(arm):
    return [r for r in good if r["arm"] == arm]
A, B = _by("A_control"), _by("B_sibling")
def _key(r): return (r["round"], r["id"])
pa = {_key(r): r["resolved"] for r in A}; pb = {_key(r): r["resolved"] for r in B}
keys = sorted(set(pa) & set(pb))
a_only = sorted(k for k in keys if pa[k] and not pb[k]); b_only = sorted(k for k in keys if pb[k] and not pa[k])
both = sum(1 for k in keys if pa[k] and pb[k])
def repo(k): return k[1].split("_")[0]
summary = {
    "paired_runs": len(keys), "A_solved": sum(pa[k] for k in keys), "B_solved": sum(pb[k] for k in keys),
    "both": both, "A_only": [list(k) for k in a_only], "B_only": [list(k) for k in b_only],
    "by_repo": {rp: {"A": sum(pa[k] for k in keys if repo(k) == rp), "B": sum(pb[k] for k in keys if repo(k) == rp),
                     "n": sum(1 for k in keys if repo(k) == rp)} for rp in ("rich", "fastapi")},
    "rich_4077": {"A": [pa[k] for k in keys if k[1] == "rich_4077"], "B": [pb[k] for k in keys if k[1] == "rich_4077"]},
    "rounds_run": round_no, "elapsed_h": round((_t.time() - START) / 3600, 2),
}
json.dump({"rows": ROWS, "summary": summary}, open(AB, "w"))
print("\n" + "=" * 64 + "\n31B PAIRED A/B SUMMARY (complete chunks only)\n" + "=" * 64, flush=True)
print(f"  paired runs {summary['paired_runs']} | A solved {summary['A_solved']} | B solved {summary['B_solved']} | both {both}", flush=True)
print(f"  by repo: {summary['by_repo']}", flush=True)
print(f"  A-only: {summary['A_only']}", flush=True)
print(f"  B-only: {summary['B_only']}", flush=True)
print(f"  rich_4077 A/B: {summary['rich_4077']}", flush=True)
# forensics -> one tarball, then delete the many small files so the download stays small
try:
    with tarfile.open("/kaggle/working/results.tar.gz", "w:gz") as tf:
        tf.add(str(OUT), arcname="results")
    shutil.rmtree(OUT, ignore_errors=True)
    print("packed results.tar.gz", flush=True)
except Exception as e:
    print("tar failed (results dir kept):", e, flush=True)
print("wrote ab31.json", flush=True)
'''
EVAL = (EVAL.replace("__ORDER__", json.dumps(order)).replace("__RICH__", json.dumps(rich_order))
        .replace("__BUDGET__", str(EVAL_BUDGET_SECONDS)).replace("__RESERVE__", str(SAVE_RESERVE_SECONDS))
        .replace("__CONC__", str(PER_ARM_CONC)).replace("__CHUNK__", str(CHUNK)))
compile(EVAL, "cell4", "exec")                       # syntax gates before any push
compile(cell2, "cell2", "exec"); compile(cell3, "cell3", "exec")
nb["cells"][4]["source"] = EVAL.splitlines(keepends=True)
nb["cells"][0]["source"] = [
    "# 31B PAIRED A/B: ca5 vs ca5 + MIRROR THE ADJACENT SIBLING (live tasks only: rich + fastapi, dead + src-layout excluded)\n",
    "Both arms share ONE tp=4 server and run the same task chunks concurrently. Output: ab31.json + results.tar.gz.\n",
]
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir()
(DST / "ca5-31b-sibling-ab.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
meta = json.loads((SRC / "kernel-metadata.json").read_text(encoding="utf-8"))
meta.update(id="comfyops/ca5-31b-sibling-ab", title="ca5 31b sibling ab", code_file="ca5-31b-sibling-ab.ipynb")
(DST / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
(K / "live_ids_31b_ab.json").write_text(json.dumps({"order": order, "rich": rich_order, "excluded_dead": sorted(dead)}, indent=1), encoding="utf-8")
print("wrote", DST, "| arm B size delta bytes:", len(sys_b.encode()) - len(sys_a.encode()))
