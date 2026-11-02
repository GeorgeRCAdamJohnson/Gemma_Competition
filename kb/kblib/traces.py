"""ATIF trace parsing (design §6.2).

Produces the trace facts runs.jsonl needs: per-call obs_class, refusals,
ARG_REJECTED, malformed calls, free/agent-tool classification, calls emitted as
text, nudges, count model cm-2, submits + scored-state basis, end reason, and
lexical edit-attempt detection. Agent code is never executed.
"""
from __future__ import annotations

import json
import re

HARNESS_TOOLS = {
    "run_command", "read_file", "edit_file", "write_file", "get_code_neighbors",
    "search_similar_code", "get_code_subgraph", "get_status", "submit_patch",
}
FREE_TOOLS = {"submit_patch", "get_status"}

TOOL_PARAMS = {
    "run_command": {"command"},
    "read_file": {"filepath", "start_line", "end_line"},
    "edit_file": {"filepath", "old_string", "new_string", "allow_multiple"},
    "write_file": {"filepath", "content"},
    "get_code_neighbors": {"node", "edge_type", "max_neighbors"},
    "search_similar_code": {"query", "k"},
    "get_code_subgraph": {"nodes"},
}
REQUIRED_PARAMS = {
    "run_command": {"command"},
    "read_file": {"filepath"},
    "edit_file": {"filepath", "old_string", "new_string"},
    "write_file": {"filepath", "content"},
    "get_code_neighbors": {"node"},
    "search_similar_code": {"query"},
    "get_code_subgraph": {"nodes"},
}

_ARG_REJECT_TEXT = re.compile(
    r"^Invoking `(\w+)\(\)` failed as the following mandatory input parameters "
    r"are not present:\n(.+?)\nYou could retry", re.S)
_EDIT_HINT = re.compile(
    r"write_text\(|\.write\(|open\([^)]*['\"]w['\"]|sed -i|perl -i|"
    r"\.replace\(|cat >|tee ", re.S)
_TARGET_RE = re.compile(r"""(?:Path\(\s*|open\(\s*|filepath["']?\s*[:=]\s*)['"]([^'"]+)['"]""")
_TEXTCALL = re.compile(r"call:(\w+)\{")


def _decode_content(content):
    if isinstance(content, str):
        try:
            return json.loads(content)
        except Exception:
            return content
    return content


def _obs_class(obs: dict | None, fn: str):
    if obs is None:
        return "MISSING", None
    content = _decode_content(obs.get("content"))
    if isinstance(content, dict):
        if "error" in content and "status" not in content:
            m = _ARG_REJECT_TEXT.match(str(content.get("error", "")))
            missing = []
            if m:
                missing = [x.strip() for x in m.group(2).splitlines() if x.strip()]
            return "ARG_REJECTED", {"missing_params": missing}
        et = content.get("error_type")
        em = str(content.get("error_message", ""))
        if et == "BudgetExceeded":
            if re.match(r"^Tool call budget exhausted \((\d+) calls\)", em):
                return "REFUSED_CALLS", {"message": em}
            if re.match(r"^Turn budget exhausted", em):
                return "REFUSED_TURNS", {"message": em}
            return "REFUSED_OTHER", {"message": em}
        blob = " ".join(str(content.get(k, "")) for k in
                         ("error_message", "stderr", "stdout"))
        if re.search(r"(?i)execution time budget exceeded|time budget (exceeded|exhausted)", blob):
            return "REFUSED_TIME", {"message": blob[:200]}
        st = content.get("status")
        if st == "ok":
            return "OK", {"patch_size": content.get("patch_size"),
                          "files_changed": content.get("files_changed")}
        if st == "error":
            return "TOOL_ERROR", {"error_type": content.get("error_type")}
        return "OK", {}
    if isinstance(content, str):
        m = _ARG_REJECT_TEXT.match(content)
        if m:
            missing = [x.strip() for x in m.group(2).splitlines() if x.strip()]
            return "ARG_REJECTED", {"missing_params": missing}
        return "TEXT", None
    return "TEXT", None


def _malformed(fn: str, args) -> list[str]:
    reasons = []
    if fn not in TOOL_PARAMS:
        return reasons
    if not isinstance(args, dict):
        return ["arguments not a dict"]
    params = TOOL_PARAMS[fn]
    for k in args:
        if k not in params:
            reasons.append(f"unknown arg key {k!r}")
        if any(ch in k for ch in ('"', "\\", ":", ",", "`", " ")):
            reasons.append(f"collapsed key {k!r}")
    for req in REQUIRED_PARAMS.get(fn, set()):
        if req not in args:
            reasons.append(f"required param absent: {req}")
    return reasons


def _is_edit_attempt(fn: str, args) -> tuple[bool, list[str]]:
    if fn in ("edit_file", "write_file"):
        files = []
        if isinstance(args, dict) and args.get("filepath"):
            files = [_clean_target(str(args["filepath"]))]
        return True, files
    if fn == "run_command" and isinstance(args, dict):
        cmd = str(args.get("command", ""))
        if _EDIT_HINT.search(cmd):
            files = _TARGET_RE.findall(cmd)
            # sed -i / cat > operands
            m = re.search(r"(?:sed -i\S*\s+'[^']*'\s+|cat >\s*|tee\s+)([^\s;&|]+)", cmd)
            if m:
                files.append(m.group(1))
            files = [_clean_target(f) for f in files]
            return True, [f for f in files if f]
    return False, []


def _clean_target(p: str):
    p = (p or "").strip().strip("'\"")
    if p.startswith("/workspace/"):
        p = p[len("/workspace/"):]
    return p.lstrip("/")


def _edit_shape(fn, args, cmd):
    """Classify the edit-attempt shape (design §8 / piece 1)."""
    if fn == "edit_file":
        return "edit_file"
    if fn == "write_file":
        return "write_file"
    if "<<" in cmd and "python" in cmd:
        return "python-heredoc"
    if re.search(r"python3?\s+-c", cmd):
        return "python-replace"
    if "cat >" in cmd or "tee " in cmd:
        return "heredoc-write"
    if "sed -i" in cmd:
        return "sed-i"
    return "run_command"


def _edit_payloads(fn, args):
    """Extract OLD/NEW payloads for edit_file / write_file tool args (piece 1).

    run_command payloads are reconstructed by kblib.reconstruct at replay time;
    here we record the raw command for that stage.
    """
    if not isinstance(args, dict):
        return None, None, None
    if fn == "edit_file":
        return args.get("old_string"), args.get("new_string"), None
    if fn == "write_file":
        return None, args.get("content"), None
    return None, None, str(args.get("command", ""))


def parse_trace(path, harness_tool_calls=None) -> dict | None:
    try:
        d = json.loads(path.read_bytes().decode("utf-8", errors="replace"))
    except Exception:
        return {"trace_error": "json decode failed"}
    schema = str(d.get("schema_version", ""))
    if not schema.startswith("ATIF-"):
        return {"trace_error": "unexpected schema"}
    steps = d.get("steps", [])
    calls = []
    call_index = 0
    for st in steps:
        for c in (st.get("tool_calls") or []):
            call_index += 1
            fn = c.get("function_name")
            args = c.get("arguments")
            obs = st.get("observation")
            cls, extra = _obs_class(obs, fn)
            malformed = _malformed(fn, args)
            if cls == "ARG_REJECTED":
                malformed = malformed or ["arg rejected by framework"]
            edit, files = _is_edit_attempt(fn, args)
            cmd = args.get("command", "") if isinstance(args, dict) else ""
            old_p, new_p, raw_cmd = _edit_payloads(fn, args) if edit else (None, None, None)
            # read-event observation text (for near-miss SAW/READ stages)
            obs_text = None
            obs_content = _decode_content(obs.get("content")) if isinstance(obs, dict) else None
            if isinstance(obs_content, dict):
                obs_text = obs_content.get("content") or obs_content.get("diff") \
                    or obs_content.get("stdout")
            elif isinstance(obs_content, str):
                obs_text = obs_content
            read_path = None
            if fn == "read_file" and isinstance(args, dict):
                read_path = _clean_target(str(args.get("filepath", "")))
            calls.append({
                "call_index": call_index,
                "step_id": st.get("step_id"),
                "fn": fn,
                "obs_class": cls,
                "obs_extra": extra,
                "obs_text": obs_text if isinstance(obs_text, str) else None,
                "read_path": read_path,
                "malformed": malformed,
                "is_edit": edit,
                "edit_files": files,
                "edit_shape": _edit_shape(fn, args, cmd) if edit else None,
                "old_payload": old_p,
                "new_payload": new_p,
                "raw_cmd": raw_cmd,
                "msg": st.get("message") if isinstance(st.get("message"), str) else None,
            })

    # nudges (consecutive, reset by any structured call)
    max_nudges = 0
    cur = 0
    for st in steps:
        ev = (st.get("extra") or {}).get("event_type") if isinstance(st.get("extra"), dict) else None
        if st.get("source") == "system" and ev == "continuation_nudge":
            cur += 1
            max_nudges = max(max_nudges, cur)
        elif st.get("tool_calls"):
            cur = 0

    # text calls (calls emitted as agent text)
    text_calls = []
    seen_fa = set()
    for st in steps:
        if st.get("tool_calls"):
            continue
        msg = st.get("message")
        if not isinstance(msg, str):
            continue
        # skip backtick spans crudely: drop content inside inline/fenced backticks
        stripped = re.sub(r"`[^`]*`", "", msg)
        for m in _TEXTCALL.finditer(stripped):
            fa = m.group(0)
            if fa in seen_fa:
                continue
            seen_fa.add(fa)
            text_calls.append({"step_id": st.get("step_id"), "fn": m.group(1)})

    # count model cm-2
    calls_total = len(calls)
    free_calls = sum(1 for c in calls if c["fn"] in FREE_TOOLS)
    refused = sum(1 for c in calls if c["obs_class"].startswith("REFUSED_"))
    arg_rejected = sum(1 for c in calls if c["obs_class"] == "ARG_REJECTED")
    agent_tool = sum(1 for c in calls if c["fn"] not in HARNESS_TOOLS)
    # harness tool_calls comes from the kernel log outcome row (not the trace).
    harness = harness_tool_calls
    predicted = calls_total - free_calls - refused - arg_rejected
    beta_term = 0
    residual = None
    if harness is not None:
        for beta in (0, 1):
            pred = predicted - beta * agent_tool
            if pred == harness:
                beta_term = beta
                predicted = pred
                residual = 0
                break
        if residual is None:
            residual = predicted - harness

    # submits + scored-state basis
    submit_calls = [c for c in calls if c["fn"] == "submit_patch"]
    ok_submits = [c for c in submit_calls if c["obs_class"] == "OK"]
    last_ok = ok_submits[-1] if ok_submits else None
    if last_ok is not None:
        scored_basis = "last-ok-submit"
    elif submit_calls:
        scored_basis = "ambiguous (submit_patch errored)"
    else:
        scored_basis = "final-state (no submit; harness recovery)"
    post_submit = []
    if last_ok is not None:
        post_submit = [c for c in calls
                       if c["call_index"] > last_ok["call_index"] and c["is_edit"]
                       and c["obs_class"] == "OK"]

    # end reason (trace-level)
    end_reason = "UNKNOWN"
    refusals = [c for c in calls if c["obs_class"].startswith("REFUSED_")]
    if refusals:
        kind = refusals[0]["obs_class"]
        end_reason = {"REFUSED_CALLS": "CALL_CAP", "REFUSED_TURNS": "TURN_CAP",
                      "REFUSED_TIME": "TIME_CAP"}.get(kind, "REFUSED_OTHER")
    elif ok_submits:
        end_reason = "SUBMITTED"
    elif max_nudges >= 3:
        end_reason = "NUDGE_EXHAUSTED"

    edit_attempts = []
    for c in calls:
        if not c["is_edit"]:
            continue
        shape = c["edit_shape"]
        old_v, new_v = c["old_payload"], c["new_payload"]
        # for python/heredoc run_command shapes, OLD/NEW are reconstructed at
        # replay time; here mark as pending-reconstruction with the raw command.
        kind = {"edit_file": "edit_file", "write_file": "write_file",
                "python-replace": "python-replace", "python-heredoc": "python-replace",
                "heredoc-write": "python-replace", "sed-i": "python-replace"}.get(
                    shape, "run_command")
        if c["obs_class"] == "ARG_REJECTED":
            kind = "edit_file"
        if (c["msg"] is None) and shape not in ("edit_file", "write_file") \
                and not c.get("raw_cmd"):
            recon = "UNPARSED"
        else:
            recon = None
        edit_attempts.append({
            "call": c["call_index"], "step_id": c["step_id"], "fn": c["fn"],
            "shape": shape, "kind": kind, "files": c["edit_files"],
            "observed": c["obs_class"],
            "observed_error": (c["obs_extra"] or {}).get("message")
                              or (c["obs_extra"] or {}).get("error_type"),
            "old": _cap(old_v) if old_v is not None else recon,
            "new": _cap(new_v) if new_v is not None else recon,
            "command": _cap(c.get("raw_cmd")),
            "after_last_submit": (last_ok is not None
                                  and c["call_index"] > last_ok["call_index"]),
        })

    structured = calls_total
    malformed_n = sum(1 for c in calls if c["malformed"])
    as_text = len(text_calls)
    share = (malformed_n + as_text) / max(1, structured + as_text)

    return {
        "steps": len(steps),
        "calls_total": calls_total,
        "free_calls": free_calls,
        "agent_tool_calls": agent_tool,
        "obs_by_class": _count_by(calls, "obs_class"),
        "calls_by_fn": _count_by(calls, "fn"),
        "refused": [{"call": c["call_index"], "step_id": c["step_id"], "fn": c["fn"],
                     "kind": c["obs_class"]} for c in refusals],
        "arg_rejected": [{"call": c["call_index"], "step_id": c["step_id"],
                          "fn": c["fn"],
                          "missing_params": (c["obs_extra"] or {}).get("missing_params", [])}
                         for c in calls if c["obs_class"] == "ARG_REJECTED"],
        "count_model": {"harness": harness, "predicted": predicted,
                        "residual": residual, "beta": beta_term, "model": "cm-2",
                        "terms": {"calls": calls_total, "free": free_calls,
                                  "refused": refused, "arg_rejected": arg_rejected,
                                  "agent_tool": agent_tool}},
        "tool_calls_as_text": as_text,
        "text_calls": text_calls,
        "tool_call_malformation": {"structured": structured, "arg_rejected": arg_rejected,
                                   "malformed": malformed_n, "as_text": as_text,
                                   "share": round(share, 4)},
        "max_consecutive_nudges": max_nudges,
        "edit_attempts": edit_attempts,
        "submit_calls": [{"call": c["call_index"], "step_id": c["step_id"],
                          "obs_class": c["obs_class"],
                          "patch_size": (c["obs_extra"] or {}).get("patch_size")}
                         for c in submit_calls],
        "last_ok_submit_call": last_ok["call_index"] if last_ok else None,
        "scored_state_basis": scored_basis,
        "post_submit_edits": [{"call": c["call_index"], "step_id": c["step_id"],
                               "files": c["edit_files"]} for c in post_submit],
        "end_reason": end_reason,
        "_calls": calls,  # internal, for near-miss; dropped before serialization
    }


def _cap(s, n=4000):
    if s is None:
        return None
    s = str(s)
    return s if len(s) <= n else s[:n] + f"...[+{len(s) - n} chars]"


def _count_by(calls, key):
    out = {}
    for c in calls:
        out[c[key]] = out.get(c[key], 0) + 1
    return out
