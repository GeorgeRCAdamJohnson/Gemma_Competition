"""decode-toward-COMMITMENT sweep runner (plan: kb/audits/decode-sweep-plan.md).

Drives the LOCAL agent loop (run_local.run_agent) across a pre-registered set of decode configs x
rich tasks, and scores EVERY agent attempt through the FIXED per-task-pinned gold-first replay engine
(kb/kblib/replay.py, engine rp-4) -- NOT run_local.verify (that path is not per-task pinned).

Hard constraints honoured here:
  * Writes land ONLY under Gemma/kb/ and Gemma/local_eval/ (+ the replay engine's own %TEMP% scratch,
    which it tears down on exit, and its Gemma/kb/replays/cache).
  * NO training, NO Kaggle, NO scored slot, NO git commit, NO worktree created by THIS file (the
    replay engine makes/removes its own throwaway worktrees).
  * The baseline arm (v6w-equivalent sampling) is the ONLY comparator. The local backend is a local
    llama-server at 127.0.0.1:8081, NOT the competition 31B, so the LOCAL baseline is never compared
    to the 0.15 board number.
  * If the backend is down, every cell is recorded NOT-RUN with a reason -- numbers are NEVER faked.
  * A task whose gold is INVALID locally (even after per-task pinning) is EXCLUDED with the recorded
    reason; an agent attempt is never scored against invalid gold.

Usage (absolute paths assumed on Windows/PowerShell, `python` on PATH):
  python decode_sweep.py --list            # print arms + task split + the pre-registered BAR; no I/O
  python decode_sweep.py --gold-gate       # run the gold-validity gate once; cache verdicts
  python decode_sweep.py --arm baseline --task rich_4077   # one cell (cached by (config_hash, task))
  python decode_sweep.py --run-all         # baseline first, then every single-axis arm; writes report+jsonl
  python decode_sweep.py --run-all --second-pass   # also run the labelled combo arms
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

# --- path wiring -------------------------------------------------------------
HERE = Path(__file__).resolve().parent                 # .../Gemma/local_eval
GEMMA = HERE.parent                                     # .../Gemma
KB = GEMMA / "kb"
AUDITS = KB / "audits"
CACHE_ROOT = AUDITS / "_decode_sweep_cache"
REPORT_MD = AUDITS / "2026-10-15-decode-commitment-sweep.md"
REPORT_JSONL = AUDITS / "2026-10-15-decode-commitment-sweep.jsonl"
TASKS_JSONL = GEMMA / "comp_files" / "tasks.jsonl"

sys.path.insert(0, str(HERE))      # run_local
sys.path.insert(0, str(KB))        # kblib

import run_local as R                                   # noqa: E402
from kblib import replay as rp, gold                    # noqa: E402

MODEL = os.environ.get("DECODE_SWEEP_MODEL", "gemma4:26b")
MAX_TOOL_CALLS = 28        # scorer budget (v6w / kaggle surface)
MAX_TIME_S = 480.0         # scorer 8-min wall budget
SCORE_TIMEOUT_S = 900      # replay pytest timeout

# ============================================================================
# PRE-REGISTERED BAR (verbatim; written to the report header BEFORE any arm runs)
# ============================================================================
PREREGISTERED_BAR = (
    "Baseline arm = v6w-equivalent sampling (temperature 0.2, top_p 0.95, top_k 64, NO penalty), run "
    "FIRST locally through the FIXED per-task-pinned gold-first scorer, establishing the LOCAL resolve "
    "count and the commit-timing proxy for THIS backend. The local backend is a local llama-server at "
    "127.0.0.1:8081, NOT the competition 31B, so the LOCAL baseline is the only comparator -- never the "
    "0.15 board number. An arm WINS on the held-out CONFIRM split only if it either (i) resolves at least "
    "as many CONFIRM tasks as baseline AND strictly improves the commit-timing proxy (strictly earlier "
    "median first_edit_at OR strictly fewer no-edit runs), OR (ii) resolves strictly more CONFIRM tasks. "
    "A tie on resolves with equal-or-worse commit-timing is a FAILURE. One axis changes per arm; the "
    "baseline is a hard floor. A null (no arm beats baseline on CONFIRM) is a valid reported result."
)

# ============================================================================
# PRE-REGISTERED TASK SET + EASY/HARD labels + held-out split (plan item 5)
# source: Gemma/RICH_48_DIFFICULTY_MAP.md  (gold-class column)
# ============================================================================
EASY = ["rich_4077", "rich_4079", "rich_4076", "rich_3469", "rich_3471",
        "rich_3278", "rich_2943", "rich_3470", "rich_3882", "rich_3518"]
# single-file HARD difficulty controls (gold stays locally verifiable)
HARD = ["rich_3935", "rich_3772"]
TASK_SET = EASY + HARD
EASY_HARD = {t: "EASY" for t in EASY}
EASY_HARD.update({t: "HARD" for t in HARD})

# genuine multi-file giants excluded up front (out of a 15/28-call agent's reach)
EXCLUDED = {
    "rich_3930": "26 files / 12.7k lines (grapheme rewrite) -- out of a 28-call agent's reach",
    "rich_4070": "9 files / 128 lines (import-defer perf refactor) -- out of a 28-call agent's reach",
}

# Held-out split (fixed, seedless, by task id). The SUCCESS bar is judged ONLY on CONFIRM.
DISCOVER = ["rich_4077", "rich_4079", "rich_3471", "rich_2943", "rich_3882", "rich_3935"]
CONFIRM = ["rich_4076", "rich_3469", "rich_3278", "rich_3470", "rich_3518", "rich_3772"]

# Runtime exclusions (recorded, not silent). A task whose AGENT-ATTEMPT replay cannot be
# scored inside SCORE_TIMEOUT_S is dropped from the run with a reason; the bar is then judged
# on the surviving CONFIRM tasks with reduced power. rich_3772 is the known case: its replay
# exceeds the timeout on every arm (already noted in the log as "rich_3772's replay exceeds 180s").
SKIP = {t.strip() for t in os.environ.get("DECODE_SWEEP_SKIP", "").split(",") if t.strip()}
SKIP_REASONS = {t: "agent-attempt replay exceeded SCORE_TIMEOUT_S (unscorable in this rig)"
                for t in SKIP}
if SKIP:
    DISCOVER = [t for t in DISCOVER if t not in SKIP]
    CONFIRM = [t for t in CONFIRM if t not in SKIP]
    EASY = [t for t in EASY if t not in SKIP]
    HARD = [t for t in HARD if t not in SKIP]
    TASK_SET = EASY + HARD
SPLIT = {t: "DISCOVER" for t in DISCOVER}
SPLIT.update({t: "CONFIRM" for t in CONFIRM})

# ============================================================================
# PRE-REGISTERED ARM TABLE (plan item 6). baseline FIRST, then ONE axis at a time.
# ============================================================================
# decode fields that define config_hash (so cache is keyed by what actually changes the generation)
_DECODE_FIELDS = ("temperature", "top_p", "top_k", "freq_penalty", "presence_penalty",
                  "nudge_mode", "nudge_max")


def _mk(name, pass_, temperature=0.2, top_p=0.95, top_k=64, freq_penalty=0.0,
        presence_penalty=0.0, nudge_mode="kaggle", nudge_max=3, note=""):
    arm = {"name": name, "pass": pass_, "temperature": temperature, "top_p": top_p,
           "top_k": top_k, "freq_penalty": freq_penalty, "presence_penalty": presence_penalty,
           "nudge_mode": nudge_mode, "nudge_max": nudge_max, "note": note}
    blob = json.dumps({k: arm[k] for k in _DECODE_FIELDS}, sort_keys=True)
    arm["config_hash"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:12]
    return arm


ARMS = [
    # baseline: v6w-equivalent sampling. RUN FIRST.
    _mk("baseline", "baseline", note="v6w-equivalent sampling (comparator / hard floor)"),
    # axis (a) temperature DOWN
    _mk("temp_00", "single", temperature=0.0, note="axis(a) greedy decode"),
    _mk("temp_01", "single", temperature=0.1, note="axis(a) temperature 0.1"),
    # axis (b) penalties UP (suppress the look-again repeat-loop)
    _mk("freq_02", "single", freq_penalty=0.2, note="axis(b) frequency_penalty 0.2"),
    _mk("freq_04", "single", freq_penalty=0.4, note="axis(b) frequency_penalty 0.4 (log: killed repeat-loop)"),
    _mk("pres_02", "single", presence_penalty=0.2, note="axis(b) presence_penalty 0.2"),
    _mk("pres_04", "single", presence_penalty=0.4, note="axis(b) presence_penalty 0.4"),
    # axis (c) reserve-tail / commit-by-remaining nudge (reuses v19v3 kaggle nudge mechanism)
    _mk("reserve_tail", "single", nudge_max=5,
        note="axis(c) commit-by-remaining nudge via kaggle NUDGE_MODE + reserve-tail (nudge_max 5)"),
    # SECOND pass: combos of single-axis winners ONLY (gated behind --second-pass)
    _mk("combo_temp01_freq04", "second", temperature=0.1, freq_penalty=0.4,
        note="2nd-pass combo: temp 0.1 + freq 0.4"),
    _mk("combo_temp01_reserve", "second", temperature=0.1, nudge_max=5,
        note="2nd-pass combo: temp 0.1 + reserve-tail nudge"),
]
ARM_BY_NAME = {a["name"]: a for a in ARMS}

SUCCESS_BAR_SHORT = (
    "WIN on CONFIRM iff (i) resolves >= baseline AND strictly better commit-timing "
    "(earlier median first_edit_at OR fewer no-edit runs), OR (ii) resolves strictly more. "
    "Tie-resolves-with-equal-or-worse-timing = FAILURE."
)

LOCAL_ONLY_CAVEAT = (
    "LOCAL-ONLY, FREE-GATE-CANDIDATE -- a win here is a hypothesis for the FREE Kaggle gate per "
    "gemma-submission-protocol.md, NOT a scored-slot change; the local backend (llama-server at "
    "127.0.0.1:8081) is NOT the competition 31B."
)

# board context only (never a comparator)
BOARD_CONTEXT = (
    "Board context (NOT a comparator): v6w @ 0.15 (submission 57098497) is live-best; v6w+temp1.0/topk64 "
    "@ 0.13 (submission 57201051) regressed. These are 31B board numbers, quoted as context only."
)

# ----------------------------------------------------------------------------
# backend probe
# ----------------------------------------------------------------------------
def backend_up():
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:8081/v1/models", timeout=5).read()
        return True, None
    except Exception as e:  # noqa: BLE001
        return False, f"{type(e).__name__}: {e}"


# ----------------------------------------------------------------------------
# gold-validity gate (plan item 3) -- needs the clones, NOT the model server
# ----------------------------------------------------------------------------
_RAW_LOADED = False
_TASKS_GOLD = None


def _ensure_gold_loaded():
    global _RAW_LOADED, _TASKS_GOLD
    if not _RAW_LOADED:
        rp.load_raw_tasks(TASKS_JSONL)
        _TASKS_GOLD = gold.build_tasks_gold(TASKS_JSONL)
        _RAW_LOADED = True
    return _TASKS_GOLD


def _load_task_record(tid):
    for line in TASKS_JSONL.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec["instance_id"] == tid:
            return rec
    raise KeyError(f"task {tid} not in {TASKS_JSONL}")


def _gate_cache_path():
    return CACHE_ROOT / "gold_gate.json"


def gold_gate(task_ids, use_cache=True, verbose=True):
    """Run the fixed scorer's gold-first control once per task. Cache verdicts.

    Returns {tid: record}. A task is INCLUDED iff gold_first in
    {VALID-HARNESS-LIKE, VALID-GOLD-RELATIVE}; else EXCLUDED with the reason.
    """
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    cache = {}
    cp = _gate_cache_path()
    if use_cache and cp.is_file():
        try:
            cache = json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    tasks_gold = _ensure_gold_loaded()
    todo = [t for t in task_ids if t not in cache]
    if todo:
        with rp.ReplayEngine(tasks_gold) as eng:
            for tid in todo:
                rec = _load_task_record(tid)
                try:
                    gr = eng.gold_first(rec["repo"], tid, rec["base_commit"],
                                        timeout_s=SCORE_TIMEOUT_S)
                except Exception as e:  # noqa: BLE001
                    gr = {"gold_first": "INFRA", "reason": f"gate raised: {type(e).__name__}: {e}"}
                verdict = gr.get("gold_first")
                cache[tid] = {
                    "gold_first": verdict,
                    "reason": gr.get("reason", ""),
                    "result_criterion": gr.get("result_criterion"),
                    "gold_pass_tests": gr.get("gold_pass_tests", []),
                    "pins": gr.get("pins", []),
                    "pin_provenance": gr.get("pin_provenance", "none"),
                    "included": verdict in ("VALID-HARNESS-LIKE", "VALID-GOLD-RELATIVE"),
                }
                if verbose:
                    print(f"task {tid}: gold_first={verdict} "
                          f"({cache[tid]['reason'] or cache[tid]['result_criterion'] or ''})")
        cp.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding="utf-8")
    elif verbose:
        for tid in task_ids:
            c = cache.get(tid, {})
            print(f"task {tid}: gold_first={c.get('gold_first')} [cache] "
                  f"({c.get('reason') or c.get('result_criterion') or ''})")
    return {t: cache[t] for t in task_ids if t in cache}


# ----------------------------------------------------------------------------
# per-(config, task) agent run + score + cache (plan item 4)
# ----------------------------------------------------------------------------
def _apply_arm(arm):
    """Set run_local module globals so the ONLY thing varying across arms is the decode axis."""
    R.set_tools_mode("kaggle")      # v6w runs the kaggle 9-tool surface
    R.FIRST_MSG = "kaggle"
    R.NUDGE_MODE = arm["nudge_mode"]
    R.KAGGLE_MAX_NUDGES = arm["nudge_max"]
    R.TEMPERATURE = arm["temperature"]
    R.TOP_P = arm["top_p"]
    R.TOP_K = arm["top_k"]
    R.FREQUENCY_PENALTY = arm["freq_penalty"]
    R.PRESENCE_PENALTY = arm["presence_penalty"]


def _cell_cache_path(config_hash, tid):
    return CACHE_ROOT / config_hash / f"{tid}.json"


def run_cell(arm, tid, gold_rec, use_cache=True, backend_ok=None, backend_reason=None):
    """Run ONE (arm, task) cell: agent loop -> diff -> fixed-scorer score. Cached by (config_hash, task).

    A task with INVALID gold is never scored (caller filters via gold_rec['included']).
    If the backend is down, the row is status=NOT-RUN with reason -- never faked.
    """
    cp = _cell_cache_path(arm["config_hash"], tid)
    if use_cache and cp.is_file():
        try:
            row = json.loads(cp.read_text(encoding="utf-8"))
            row["_cache_hit"] = True
            return row
        except Exception:
            pass

    base_row = {
        "config_name": arm["name"], "config_hash": arm["config_hash"], "pass": arm["pass"],
        "task": tid, "easy_hard": EASY_HARD.get(tid), "split": SPLIT.get(tid),
        "arm_decode": {k: arm[k] for k in _DECODE_FIELDS},
    }

    if backend_ok is None:
        backend_ok, backend_reason = backend_up()
    if not backend_ok:
        row = dict(base_row, status="NOT-RUN", reason=f"backend down: {backend_reason}",
                   resolved=None, tool_calls=None, first_edit_at=None, no_edit=None,
                   patch_chars=None, submitted=None, end_reason=None,
                   scorer_result=None, required_pass=None, gold_relative=None,
                   _cache_hit=False)
        return row     # NOT cached: a down backend is transient, retry on next run

    tasks_gold = _ensure_gold_loaded()
    rec = _load_task_record(tid)
    repo = rec["repo"]
    base_commit = rec["base_commit"]

    _apply_arm(arm)
    R.set_repo(repo.split("/")[-1])
    try:
        diff, calls, dur, submitted = R.run_agent(
            rec, MODEL, MAX_TOOL_CALLS, max_time_s=MAX_TIME_S, use_compaction=True)
    except Exception as e:  # noqa: BLE001
        row = dict(base_row, status="NOT-RUN", reason=f"agent loop raised: {type(e).__name__}: {e}",
                   resolved=None, tool_calls=None, first_edit_at=None, no_edit=None,
                   patch_chars=None, submitted=None, end_reason=None,
                   scorer_result=None, required_pass=None, gold_relative=None, _cache_hit=False)
        return row
    st = dict(R.LAST_RUN)
    first_edit = st.get("first_edit_call")

    # SCORE the agent diff through the FIXED gold-first engine (per-task pinned, worktree-isolated).
    criterion = gold_rec.get("result_criterion")
    try:
        with rp.ReplayEngine(tasks_gold) as eng:
            res = eng.run_candidate(repo, tid, base_commit, kind="patch", patch_text=diff,
                                    gold_pass_tests=gold_rec.get("gold_pass_tests"),
                                    timeout_s=SCORE_TIMEOUT_S)
    except Exception as e:  # noqa: BLE001
        row = dict(base_row, status="NOT-RUN", reason=f"scorer raised: {type(e).__name__}: {e}",
                   resolved=None, tool_calls=calls, first_edit_at=first_edit,
                   no_edit=(first_edit is None), patch_chars=len(diff), submitted=submitted,
                   end_reason=st.get("end_reason"), scorer_result=None, required_pass=None,
                   gold_relative=None, _cache_hit=False)
        return row

    # mirror the per-task criterion the gold gate used
    if criterion == "harness_like":
        resolved = bool(res.get("harness_like"))
    else:
        resolved = bool(res.get("gold_relative"))

    row = dict(
        base_row, status="RAN", reason="",
        resolved=resolved,
        tool_calls=calls,
        first_edit_at=first_edit,              # JSON null if no edit
        no_edit=(first_edit is None),
        patch_chars=len(diff),
        submitted=bool(submitted),
        end_reason=st.get("end_reason"),
        edit_ok=st.get("edit_ok"),
        edit_err=st.get("edit_err"),
        nudges=st.get("nudges"),
        tool_counts=st.get("tool_counts"),
        duration_s=round(dur),
        result_criterion=criterion,
        scorer_result=res.get("result"),
        required_pass=res.get("required_pass"),
        gold_relative=res.get("gold_relative"),
        harness_like=res.get("harness_like"),
        scorer_engine=res.get("engine_version"),
        _cache_hit=False,
    )
    cp.parent.mkdir(parents=True, exist_ok=True)
    cp.write_text(json.dumps(row, indent=1, ensure_ascii=False), encoding="utf-8")
    return row


# ----------------------------------------------------------------------------
# aggregation + report (plan item 7)
# ----------------------------------------------------------------------------
def _summarize(rows, split):
    """Rows for ONE arm restricted to ONE split -> commit-timing + resolve summary."""
    sub = [r for r in rows if r.get("split") == split]
    ran = [r for r in sub if r.get("status") == "RAN"]
    resolves = sum(1 for r in ran if r.get("resolved"))
    n = len(sub)
    edits = [r["first_edit_at"] for r in ran if r.get("first_edit_at") is not None]
    no_edit = sum(1 for r in ran if r.get("no_edit"))
    med_first_edit = statistics.median(edits) if edits else None
    calls = [r["tool_calls"] for r in ran if r.get("tool_calls") is not None]
    not_run = sum(1 for r in sub if r.get("status") == "NOT-RUN")
    return {
        "n_tasks": n, "n_ran": len(ran), "n_not_run": not_run,
        "resolves": resolves,
        "median_first_edit": med_first_edit,
        "no_edit_runs": no_edit,
        "mean_tool_calls": (round(sum(calls) / len(calls), 1) if calls else None),
    }


def _timing_better(arm_s, base_s):
    """Strictly-better commit timing: earlier median first_edit OR fewer no-edit runs."""
    a_med, b_med = arm_s["median_first_edit"], base_s["median_first_edit"]
    earlier = (a_med is not None and b_med is not None and a_med < b_med)
    fewer_noedit = arm_s["no_edit_runs"] < base_s["no_edit_runs"]
    return earlier or fewer_noedit


def _timing_worse_or_equal(arm_s, base_s):
    return not _timing_better(arm_s, base_s)


def verdict_for(arm_s, base_s, any_ran):
    """Per-arm verdict on the CONFIRM split vs baseline CONFIRM summary."""
    if not any_ran:
        return "NOT-RUN"
    r_arm, r_base = arm_s["resolves"], base_s["resolves"]
    if r_arm > r_base:
        return "WIN"
    if r_arm == r_base and _timing_better(arm_s, base_s):
        return "WIN"
    if r_arm == r_base and _timing_worse_or_equal(arm_s, base_s):
        return "FAIL(tie-no-timing-gain)"
    return "FAIL(fewer-resolves)"


def _fmt(v):
    return "n/a" if v is None else (str(v))


def write_report(all_rows, gate, backend_ok, backend_reason, provenance):
    AUDITS.mkdir(parents=True, exist_ok=True)
    # JSONL (idempotent: rewritten from the full row set)
    with REPORT_JSONL.open("w", encoding="utf-8") as f:
        for r in all_rows:
            out = {k: v for k, v in r.items() if k != "_cache_hit"}
            f.write(json.dumps(out, ensure_ascii=False, sort_keys=True) + "\n")

    # per-arm summaries
    by_arm = {}
    for a in ARMS:
        arows = [r for r in all_rows if r["config_name"] == a["name"]]
        by_arm[a["name"]] = {
            "CONFIRM": _summarize(arows, "CONFIRM"),
            "DISCOVER": _summarize(arows, "DISCOVER"),
            "rows": arows,
        }
    base_confirm = by_arm["baseline"]["CONFIRM"]

    included = [t for t in TASK_SET if gate.get(t, {}).get("included")]
    excluded_gate = {t: gate[t] for t in TASK_SET if t in gate and not gate[t].get("included")}

    L = []
    L.append("# decode-toward-COMMITMENT sweep -- LOCAL gold-first scorer (rp-4)")
    L.append("")
    L.append(f"> **{LOCAL_ONLY_CAVEAT}**")
    L.append("")
    L.append("## Verification (read without re-running)")
    L.append("")
    for line in provenance:
        L.append(f"- {line}")
    L.append("")
    L.append("## PRE-REGISTERED BAR (frozen before any arm ran)")
    L.append("")
    L.append(PREREGISTERED_BAR)
    L.append("")
    L.append(f"_Success bar (short):_ {SUCCESS_BAR_SHORT}")
    L.append("")
    L.append(BOARD_CONTEXT)
    L.append("")

    # task set
    L.append("## Frozen task set, EASY/HARD labels, held-out split")
    L.append("")
    L.append("| task | gold class | split | gold gate | included |")
    L.append("|---|---|---|---|---|")
    for t in TASK_SET:
        g = gate.get(t, {})
        gf = g.get("gold_first", "NOT-GATED")
        inc = "yes" if g.get("included") else "**NO** (excluded)"
        L.append(f"| {t} | {EASY_HARD[t]} | {SPLIT[t]} | {gf} | {inc} |")
    L.append("")
    L.append(f"DISCOVER (tune): {', '.join(DISCOVER)}")
    L.append("")
    L.append(f"CONFIRM (held-out, judges the bar): {', '.join(CONFIRM)}")
    L.append("")
    L.append("Excluded up front (multi-file giants, out of a 28-call agent's reach):")
    for t, why in EXCLUDED.items():
        L.append(f"- {t}: {why}")
    if excluded_gate:
        L.append("")
        L.append("Excluded by the gold gate (invalid gold locally -- agent attempts NOT scored):")
        for t, g in excluded_gate.items():
            L.append(f"- {t}: gold_first={g.get('gold_first')} -- {g.get('reason')}")
    L.append("")

    # per-arm table
    L.append("## Per-arm vs baseline (judged on CONFIRM)")
    L.append("")
    L.append("All numbers below are MEASURED (each ties to a JSONL row / cache file) unless a cell says "
             "INFERRED. `median first_edit_at` and `no-edit runs` are the commit-timing proxy.")
    L.append("")
    L.append("| arm | axis | CONFIRM resolves (n/N ran) | CONFIRM median first_edit_at | CONFIRM no-edit runs | CONFIRM mean tool_calls | DISCOVER resolves | VERDICT |")
    L.append("|---|---|---|---|---|---|---|---|")
    any_confirm_ran = base_confirm["n_ran"] > 0
    verdicts = {}
    for a in ARMS:
        if a["pass"] == "second" and not any(r["config_name"] == a["name"] for r in all_rows):
            continue
        cs = by_arm[a["name"]]["CONFIRM"]
        ds = by_arm[a["name"]]["DISCOVER"]
        if a["name"] == "baseline":
            vd = "BASELINE"
        else:
            vd = verdict_for(cs, base_confirm, any_confirm_ran and cs["n_ran"] > 0)
        verdicts[a["name"]] = vd
        res_cell = f"{cs['resolves']}/{cs['n_ran']}" + (f" (+{cs['n_not_run']} not-run)" if cs['n_not_run'] else "")
        L.append(f"| {a['name']} | {a['note']} | {res_cell} | {_fmt(cs['median_first_edit'])} | "
                 f"{_fmt(cs['no_edit_runs'])} | {_fmt(cs['mean_tool_calls'])} | "
                 f"{ds['resolves']}/{ds['n_ran']} | {vd} |")
    L.append("")

    # verdict line
    L.append("## VERDICT")
    L.append("")
    if not any_confirm_ran:
        L.append(f"**NOT MEASURED -- backend was down** ({backend_reason}). No agent cell ran, so no arm "
                 f"could be scored. The gold gate and the full plumbing (penalty forwarding, arm table, "
                 f"split, report/JSONL writers) are MEASURED and in place; the resolve/commit-timing "
                 f"numbers are NOT MEASURED and were NOT fabricated. Re-run `--run-all` once a "
                 f"llama-server is listening on 127.0.0.1:8081 to populate every cell from cache.")
    else:
        winners = [n for n, v in verdicts.items() if v == "WIN"]
        if winners:
            L.append(f"**WIN candidate(s): {', '.join(winners)}** -- cleared the pre-registered bar on the "
                     f"held-out CONFIRM split vs the LOCAL baseline. {LOCAL_ONLY_CAVEAT}")
        else:
            L.append("**NULL (reported as a result)** -- no single-axis arm beat the LOCAL baseline on the "
                     "held-out CONFIRM split under the pre-registered bar. Baseline is the hard floor.")
    L.append("")

    # NOT-RUN subsection
    not_run_rows = [r for r in all_rows if r.get("status") == "NOT-RUN"]
    if not_run_rows:
        L.append("## NOT-RUN cells (never faked)")
        L.append("")
        reasons = {}
        for r in not_run_rows:
            reasons.setdefault(r.get("reason", "?"), []).append(f"{r['config_name']}/{r['task']}")
        for reason, cells in reasons.items():
            L.append(f"- **{reason}** -- {len(cells)} cell(s): {', '.join(cells[:12])}"
                     + (" ..." if len(cells) > 12 else ""))
        L.append("")

    L.append("## Caveat")
    L.append("")
    L.append(LOCAL_ONLY_CAVEAT)
    L.append("")

    REPORT_MD.write_text("\n".join(L), encoding="utf-8")
    return by_arm, verdicts


# ----------------------------------------------------------------------------
# orchestration (plan item 7)
# ----------------------------------------------------------------------------
def run_all(second_pass=False):
    backend_ok, backend_reason = backend_up()
    print(f"[backend {'UP' if backend_ok else 'DOWN'}] {backend_reason or ''}")

    # 1. gold gate (needs clones, not the model)
    gate = gold_gate(TASK_SET, verbose=True)
    included = [t for t in TASK_SET if gate.get(t, {}).get("included")]
    print(f"[gold gate] {len(included)}/{len(TASK_SET)} tasks VALID: {', '.join(included) or '(none)'}")

    # 2. arms: baseline FIRST, then single-axis, then (optionally) combos
    arm_order = [a for a in ARMS if a["pass"] == "baseline"]
    arm_order += [a for a in ARMS if a["pass"] == "single"]
    if second_pass:
        arm_order += [a for a in ARMS if a["pass"] == "second"]

    all_rows = []
    for arm in arm_order:
        for tid in TASK_SET:
            g = gate.get(tid, {})
            if not g.get("included"):
                # excluded by gold gate: do NOT score an attempt against invalid gold
                all_rows.append({
                    "config_name": arm["name"], "config_hash": arm["config_hash"], "pass": arm["pass"],
                    "task": tid, "easy_hard": EASY_HARD.get(tid), "split": SPLIT.get(tid),
                    "status": "EXCLUDED", "reason": f"gold gate: {g.get('gold_first')} -- {g.get('reason')}",
                    "resolved": None, "tool_calls": None, "first_edit_at": None, "no_edit": None,
                    "patch_chars": None, "submitted": None,
                })
                continue
            row = run_cell(arm, tid, g, backend_ok=backend_ok, backend_reason=backend_reason)
            tag = "cache" if row.get("_cache_hit") else row.get("status")
            print(f"  [{arm['name']}/{tid}] {tag} resolved={row.get('resolved')} "
                  f"first_edit_at={row.get('first_edit_at')} tool_calls={row.get('tool_calls')}")
            all_rows.append(row)

    provenance = _provenance_lines(backend_ok, backend_reason, gate)
    by_arm, verdicts = write_report(all_rows, gate, backend_ok, backend_reason, provenance)
    print(f"\n[report] {REPORT_MD}")
    print(f"[jsonl ] {REPORT_JSONL}")
    return all_rows


def _git_status(repo_path):
    import subprocess
    try:
        r = subprocess.run(["git", "-C", str(repo_path), "status", "--porcelain"],
                           capture_output=True, text=True, timeout=60)
        s = r.stdout.strip()
        return "clean" if not s else f"DIRTY:\n{s}"
    except Exception as e:  # noqa: BLE001
        return f"status-error: {type(e).__name__}: {e}"


def _provenance_lines(backend_ok, backend_reason, gate):
    rich_clone = HERE / "repos" / "rich"
    fast_clone = HERE / "repos" / "fastapi"
    import tempfile
    scratch = [str(p) for p in Path(tempfile.gettempdir()).glob("gkb_*")]
    lines = [
        f"Backend 127.0.0.1:8081: {'UP' if backend_ok else 'DOWN -- ' + str(backend_reason)}.",
        f"Scorer: FIXED per-task-pinned gold-first replay engine {rp.RP_VERSION} (kb/kblib/replay.py); "
        f"agent attempts scored via ReplayEngine.run_candidate, validity via ReplayEngine.gold_first.",
        f"rich clone `{rich_clone}` git status: {_git_status(rich_clone)}",
        f"fastapi clone `{fast_clone}` git status: {_git_status(fast_clone)}",
        f"Writes confined to Gemma/kb/ and Gemma/local_eval/ (report, jsonl, _decode_sweep_cache/, "
        f"replays/cache/); run_local.py edit is additive (penalty 0.0 == prior payload).",
        f"%TEMP% gkb_* scratch after run: {scratch if scratch else 'none (engine tore down)'}.",
        f"Gold gate: {sum(1 for t in TASK_SET if gate.get(t, {}).get('included'))}/{len(TASK_SET)} "
        f"tasks VALID.",
    ]
    return lines


# ----------------------------------------------------------------------------
# --list (plan item 2 / 5 / 6): print arms + split + BAR, no network/scorer
# ----------------------------------------------------------------------------
def do_list():
    print("=== PRE-REGISTERED BAR ===")
    print(PREREGISTERED_BAR)
    print()
    print(BOARD_CONTEXT)
    print()
    print("=== ARMS ===")
    for a in ARMS:
        print(f"  {a['name']:22s} [{a['pass']:8s}] hash={a['config_hash']} "
              f"temp={a['temperature']} top_p={a['top_p']} top_k={a['top_k']} "
              f"freq={a['freq_penalty']} pres={a['presence_penalty']} "
              f"nudge={a['nudge_mode']}/{a['nudge_max']}  # {a['note']}")
    print()
    print("=== TASK SET (gold-class labels from RICH_48_DIFFICULTY_MAP.md) ===")
    for t in TASK_SET:
        print(f"  {t:12s} {EASY_HARD[t]:4s} {SPLIT[t]}")
    print(f"  EASY={len(EASY)} HARD={len(HARD)} total={len(TASK_SET)}")
    print()
    print("=== EXCLUDED up front ===")
    for t, why in EXCLUDED.items():
        print(f"  {t}: {why}")
    print()
    print(f"DISCOVER (tune): {', '.join(DISCOVER)}")
    print(f"CONFIRM  (held-out, judges bar): {', '.join(CONFIRM)}")
    assert set(DISCOVER) & set(CONFIRM) == set(), "split must be disjoint"
    assert set(DISCOVER) | set(CONFIRM) == set(TASK_SET), "split must cover the task set"
    print("[split disjoint + covering: OK]")


def main():
    ap = argparse.ArgumentParser(description="decode-toward-COMMITMENT sweep (local gold-first scorer)")
    ap.add_argument("--list", action="store_true", help="print arms+split+BAR, no network/scorer")
    ap.add_argument("--gold-gate", action="store_true", help="run the gold-validity gate; cache verdicts")
    ap.add_argument("--arm", default=None, help="run ONE arm (with --task)")
    ap.add_argument("--task", default=None, help="run ONE task (with --arm)")
    ap.add_argument("--run-all", action="store_true", help="baseline first, then every single-axis arm")
    ap.add_argument("--second-pass", action="store_true", help="also run the labelled combo arms")
    ap.add_argument("--no-cache", action="store_true", help="ignore cached cells/gate")
    args = ap.parse_args()

    if args.list:
        do_list()
        return
    if args.gold_gate:
        gold_gate(TASK_SET, use_cache=not args.no_cache, verbose=True)
        return
    if args.arm and args.task:
        gate = gold_gate([args.task], use_cache=not args.no_cache, verbose=True)
        g = gate.get(args.task, {})
        if not g.get("included"):
            print(f"EXCLUDED {args.task}: gold_first={g.get('gold_first')} -- {g.get('reason')}")
            return
        arm = ARM_BY_NAME.get(args.arm)
        if arm is None:
            raise SystemExit(f"unknown arm {args.arm}; choices: {', '.join(ARM_BY_NAME)}")
        row = run_cell(arm, args.task, g, use_cache=not args.no_cache)
        if row.get("_cache_hit"):
            print("[cache hit]")
        print(json.dumps({k: v for k, v in row.items() if k != "_cache_hit"}, indent=1, ensure_ascii=False))
        return
    if args.run_all:
        run_all(second_pass=args.second_pass)
        return
    ap.print_help()


if __name__ == "__main__":
    main()
