"""Per-stack outcome/config source adapters (design REV5 R5.2-R5.4, D5-1..D5-4).

Outcome priority (D5-2): kernel-log `-> resolved=` lines (kernellog) ->
`task_results.jsonl` -> (kaggle_pkg only) the user's recovered proxy
`recovered_full129.json` (labelled, lower priority) -> sweep `.pinned.jsonl`
-> sweep `.results.jsonl`. `summary.json` is only compared, never used.

Config priority (D5-3): `submission/` -> single `agent_*` child -> rig arm dir
(`parity_rig/agent_<arm>` then `agent_ctrl_<arm>`) -> sweep guard cmd flags ->
none. Pure file reads; no process or network APIs.
"""
from __future__ import annotations

import json
import pathlib
import re

from . import paths

MAIN_MODEL = "gemma-4-31b-it-qat-w4a16-ct"


def read_jsonl(path) -> tuple[list[dict], int]:
    """Tolerant JSONL read: (rows, n_bad_lines)."""
    rows, bad = [], 0
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return [], 0
    for ln in text.splitlines():
        if not ln.strip():
            continue
        try:
            obj = json.loads(ln)
        except Exception:
            bad += 1
            continue
        if isinstance(obj, dict):
            rows.append(obj)
        else:
            bad += 1
    return rows, bad


# ------------------------------------------------------------------ outcomes

def outcomes_from_task_results(path) -> dict:
    """{task: outcome} from a harness task_results.jsonl (last row per task wins)."""
    rows, _ = read_jsonl(path)
    out = {}
    for i, r in enumerate(rows, 1):
        task = r.get("instance_id") or r.get("task")
        if not task:
            continue
        err = r.get("error")
        out[task] = {
            "task": task, "resolved": bool(r.get("resolved")),
            "duration_s": r.get("duration_seconds"),
            "tool_calls": r.get("tool_calls"),
            "patch_chars": r.get("agent_patch_size"),
            "exit_code": r.get("test_exit_code"),
            "total_llm_calls": r.get("total_llm_calls"),
            "error": (str(err)[:300] if err else None),
            "rule": "task_results", "line": i, "self_id": True,
        }
    return out


def outcomes_from_recovered(path) -> dict:
    """{task: outcome} from the user's recovered_full129.json (a test-output
    proxy written by local_eval/parity_rig/_recover_full129.py; ASSUMED-grade:
    validated by its author only on the surviving task_results labels)."""
    try:
        d = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {}
    out = {}
    for r in d.get("rows", []) if isinstance(d, dict) else []:
        task = r.get("instance_id")
        if not task:
            continue
        out[task] = {"task": task, "resolved": bool(r.get("resolved")),
                     "verified": bool(r.get("verified")),
                     "counts": r.get("counts") or {},
                     "duration_s": None, "tool_calls": None, "patch_chars": None,
                     "rule": "recovered-proxy", "self_id": True}
    return out


def summary_disagrees(summary_path, outcomes: dict, n_traces: int) -> bool | None:
    """True when summary.json's totals differ from the per-task sources."""
    try:
        s = json.loads(pathlib.Path(summary_path).read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(s, dict):
        return None
    total = s.get("total", s.get("total_tasks"))
    resolved = s.get("resolved")
    n = max(len(outcomes), n_traces)
    n_res = sum(1 for o in outcomes.values() if o.get("resolved"))
    if total is None and resolved is None:
        return None
    return bool((total is not None and total != n) or
                (resolved is not None and resolved != n_res))


# ------------------------------------------------------------------ configs

def agent_dir_config(run_dir) -> pathlib.Path | None:
    """The single `agent_*` child dir with an agent.yaml (kaggle_pkg runs)."""
    d = pathlib.Path(run_dir)
    if not d.is_dir():
        return None
    kids = sorted(c for c in d.iterdir()
                  if c.is_dir() and c.name.startswith("agent_") and (c / "agent.yaml").is_file())
    return kids[0] if len(kids) == 1 else None


def rig_arm_and_rep(rig_rel: str) -> tuple[str | None, int | None]:
    """Arm + rep from a rig run path relative to G."""
    parts = rig_rel.split("/")
    last = parts[-1]
    m = re.fullmatch(r"r(\d+)", last)
    if m and len(parts) >= 2:
        return parts[-2], int(m.group(1))
    m = re.fullmatch(r"(.+)_r(\d+)", last)
    if m:
        return m.group(1), int(m.group(2))
    return last, None


def rig_arm_config(g, arm: str | None) -> pathlib.Path | None:
    """parity_rig/agent_<arm>, else parity_rig/agent_ctrl_<arm> (arm names that
    already start with agent_ map to themselves)."""
    if not arm:
        return None
    root = pathlib.Path(g) / paths.RIG_ROOT
    cands = [root / arm] if arm.startswith("agent_") else []
    cands += [root / f"agent_{arm}", root / f"agent_ctrl_{arm}"]
    for c in cands:
        if (c / "agent.yaml").is_file():
            return c
    return None


_FLAG_RE = re.compile(r"(?:^|\s)--([a-z][a-z0-9-]*)(?:[ =]((?!--)\S+))?")


def guard_flags(cmd: str) -> dict:
    flags = {}
    for name, val in _FLAG_RE.findall(cmd or ""):
        flags[name] = val if val != "" else True
    return flags


def _num(v):
    if v is None or v is True:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return v
    return int(f) if f.is_integer() and "." not in str(v) else f


def config_from_guard(cmd: str) -> dict:
    f = guard_flags(cmd)
    model = f.get("model")
    if isinstance(model, str):
        model = model.replace("\\", "/").rstrip("/").split("/")[-1]
    return {
        "model": model if isinstance(model, str) else None,
        "temperature": _num(f.get("temp")),
        "top_p": _num(f.get("top-p")),
        "max_tool_calls": _num(f.get("max-tool-calls")),
        "max_time_minutes": None,
        "max_time_s": _num(f.get("max-time")),
        "max_output_tokens": _num(f.get("max-tokens")),
        "thinking": f.get("thinking") if isinstance(f.get("thinking"), str) else None,
        "thinking_budget": _num(f.get("think-budget")),
        "prompt_file": f.get("prompt-file") if isinstance(f.get("prompt-file"), str) else None,
        "isolate": bool(f.get("isolate")),
        "config_confidence": "sweep guard cmd",
    }


_TAG_ARM = re.compile(r"(?:^|_)([A-Z]\d{1,2}[a-z]?)_r(\d+)(?:_|$)")


def sweep_rows(tag: str, tag_files: dict, g=None) -> list[dict]:
    """Summary-only rows for one sweep tag (D5-4).

    tag_files: {suffix: G-relative path}. Pinned rescore beats raw results.
    patch_trusted = the guard cmd carries `--isolate` (no guard -> False).
    """
    g = pathlib.Path(g) if g is not None else paths.gemma_root()
    res = {}
    if "results" in tag_files:
        for r in read_jsonl(g / tag_files["results"])[0]:
            if r.get("task"):
                res[r["task"]] = r
    pin = {}
    if "pinned" in tag_files:
        for r in read_jsonl(g / tag_files["pinned"])[0]:
            if r.get("task"):
                pin[r["task"]] = r
    starts = {}
    any_start = None
    if "guard" in tag_files:
        for r in read_jsonl(g / tag_files["guard"])[0]:
            if r.get("ev") == "start":
                any_start = r
                if r.get("task"):
                    starts[r["task"]] = r
    out = []
    for task in sorted(set(res) | set(pin)):
        st = starts.get(task) or any_start
        rr = res.get(task) or {}
        pr = pin.get(task)
        if pr is not None:
            outcome = {"task": task, "resolved": bool(pr.get("pinned_resolved")),
                       "pinned_result": pr.get("pinned_result"),
                       "gate_resolved": pr.get("gate_resolved"),
                       "gold_validity": pr.get("gold_validity"),
                       "required_pass": pr.get("required_pass"),
                       "patch_chars": pr.get("patch_chars", rr.get("patch_chars")),
                       "tool_calls": pr.get("calls", rr.get("calls")),
                       "duration_s": rr.get("dur"),
                       "end_reason": rr.get("end_reason"),
                       "rule": "sweep-pinned", "self_id": True}
            scorer = "sweep-pinned"
        else:
            outcome = {"task": task, "resolved": bool(rr.get("resolved")),
                       "patch_chars": rr.get("patch_chars"),
                       "tool_calls": rr.get("calls"),
                       "duration_s": rr.get("dur"),
                       "end_reason": rr.get("end_reason"),
                       "rule": "sweep-raw", "self_id": True}
            scorer = "sweep-raw"
        if st is not None:
            cfg = config_from_guard(st.get("cmd", ""))
            patch_trusted = bool(cfg.get("isolate"))
        else:
            cfg = {"model": None, "temperature": rr.get("temp"),
                   "thinking": rr.get("thinking"), "isolate": False,
                   "config_confidence": "sweep results row" if rr else "none"}
            patch_trusted = False
        arm = (st or {}).get("arm")
        rep = (st or {}).get("rep")
        if arm is None:
            m = _TAG_ARM.search(tag)
            if m:
                arm, rep = m.group(1), int(m.group(2))
        out.append({"task": task, "outcome": outcome, "config": cfg,
                    "scorer": scorer, "arm": arm,
                    "rep": rep if isinstance(rep, int) else None,
                    "patch_trusted": patch_trusted,
                    "has_guard": st is not None})
    return out


# ------------------------------------------------------------------ stack/track

def track_for(model_declared: str | None, label: str | None, platform: str) -> tuple[str, str]:
    """(track, basis). main = 31B, small-model = E2B/E4B, dev-proxy = 12B/other."""
    def from_text(t):
        t = (t or "").lower()
        if "e2b" in t or "e4b" in t:
            return "small-model"
        if "31b" in t:
            return "main"
        if "12b" in t:
            return "dev-proxy"
        return None
    tr = from_text(model_declared)
    if tr:
        return tr, "model_declared"
    if model_declared:
        return "dev-proxy", "model_declared (non-Gemma-size token)"
    tr = from_text(label)
    if tr:
        return tr, "label token"
    if platform == "kaggle":
        return "main", "ASSUMED: Kaggle kernel default model (31B), no model declared"
    return "dev-proxy", "unknown model"


def stack_and_track(platform: str, model_declared: str | None,
                    served_verified: bool, scorer: str | None = None,
                    label: str | None = None) -> tuple[dict, str, str]:
    """D5-1: (stack, track, track_basis)."""
    if scorer is None:
        scorer = {"kaggle": "harness", "local-rig": "rig-local"}.get(platform, "unknown")
    stack = {"platform": platform, "scorer": scorer,
             "model_declared": model_declared,
             "model_served_verified": bool(served_verified) if platform == "kaggle" else False}
    track, basis = track_for(model_declared, label, platform)
    return stack, track, basis
