"""Kernel-log and pasted-log parsing (design §6.1).

Extracts per-(pass, task) result rows and run-level + harness-logger events.
Supports JSON-array kernel logs and plain/pasted text logs, pass segmentation,
line rules P1h/P1r/P2h/P2/P3/P4/P5, run-level H1-H4/A1, and L1 harness events.
"""
from __future__ import annotations

import json
import re

from . import paths  # noqa: F401

# --- line rules (design §6.1) ---
P1H = re.compile(r"^\[(\d+)/(\d+)\] (?:Evaluating )?(\S+) \(([^)]+)\)\.\.\.")
P1R = re.compile(r"^\s*-> resolved=(True|False)\b(.*)$")
P1R_FIELD = re.compile(r"\b(duration|tool_calls|patch_chars|exit_code)=(-?[\d.]+)s?")
P2H = re.compile(r"^\[serial (\d+)/(\d+)\] (\S+) \.\.\.")
P2 = re.compile(
    r"^\s*\[done\] (\S+): resolved=(True|False) dur=([\d.]+)s calls=(\d+) chars=(\d+)")
P3 = re.compile(
    r"^\s*\[par done\] (\S+): resolved=(True|False) dur=([\d.]+)s calls=(\d+) chars=(\d+)")
P4 = re.compile(
    r"^\s*((?:rich|fastapi|requests|httpx)_\d+)\s+(\w+)\s+(True|False)\s+([\d.]+)\s+(\d+)\s+(\d+)\s*$")

PASS_START = re.compile(
    r"^\[parallel\] running|^\[serial 1/\d+\]|^\[1/\d+\] (?:Evaluating )?\S+ \(")
PASS_LABEL = re.compile(r"^(Representative sample|A/B sample|RICH sample)\b")

H1 = re.compile(r"^Agent dir written \(([^=():]+?)\s*=")
H3 = re.compile(r"Max tool_calls used: (\d+) \(cap (\d+)\)")
H4 = re.compile(r"Installing (\d+) wheels")
A1 = re.compile(r"^\[adapter\] (RESOLVED|copied) (.*)$")

L1 = re.compile(r"^(WARNING|ERROR|CRITICAL):(swegemma[\w.]*):(.*)$")
SERVED = re.compile(r"served model ids:\s*\[([^\]\n]*)\]")
TASK_IN_MSG = re.compile(r"\b((?:rich|fastapi|requests|httpx)_\d+)\b")

_EVENT_TEMPLATES = [
    ("NO_SUBMIT_EMPTY_TREE",
     "completed without explicit submit_patch call and no working tree modifications"),
    ("TIME_CAP", "agent timed out"),
    ("NUDGE_EXHAUSTED", "Reached maximum continuation nudges"),
    ("TURN_CAP", "exceeded turns budget"),
    ("VERIFY_TEST_PATCH_FAIL", "Failed to apply test patch"),
    ("VERIFY_AGENT_PATCH_FAIL", "Failed to apply agent patch"),
    ("SANDBOX_NO_PIP", "ensurepip unavailable"),
]
_CALL_CAP = re.compile(r"Tool call budget \((\d+)\) exhausted")


def _load(path) -> tuple[str, str, bool]:
    """Return (stdout_text, stderr_text, is_json)."""
    raw = path.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        text = raw.decode("utf-16", errors="replace")
    else:
        if raw[:3] == b"\xef\xbb\xbf":
            raw = raw[3:]
        text = raw.decode("utf-8", errors="replace")
    stripped = text.lstrip()
    if stripped.startswith("["):
        try:
            data = json.loads(text)
            if isinstance(data, list) and data and isinstance(data[0], dict) \
                    and "stream_name" in data[0]:
                out = "".join(
                    e.get("data", "") for e in data
                    if isinstance(e, dict) and e.get("stream_name") == "stdout")
                err = "".join(
                    e.get("data", "") for e in data
                    if isinstance(e, dict) and e.get("stream_name") == "stderr")
                return out, err, True
        except Exception:
            pass
    return text, "", False


def _parse_result_line(line: str, lineno: int):
    m = P2.match(line) or P3.match(line)
    if m:
        return {
            "task": m.group(1), "resolved": m.group(2) == "True",
            "duration_s": float(m.group(3)), "tool_calls": int(m.group(4)),
            "patch_chars": int(m.group(5)), "rule": "P2/P3", "line": lineno,
            "self_id": True,
        }
    m = P4.match(line)
    if m:
        return {
            "task": m.group(1), "resolved": m.group(3) == "True",
            "duration_s": float(m.group(4)), "tool_calls": int(m.group(5)),
            "patch_chars": int(m.group(6)), "rule": "P4", "line": lineno,
            "self_id": True,
        }
    m = P1R.match(line)
    if m:
        fields = {k: v for k, v in P1R_FIELD.findall(m.group(2))}
        return {
            "task": None, "resolved": m.group(1) == "True",
            "duration_s": float(fields["duration"]) if "duration" in fields else None,
            "tool_calls": int(float(fields["tool_calls"])) if "tool_calls" in fields else None,
            "patch_chars": int(float(fields["patch_chars"])) if "patch_chars" in fields else None,
            "exit_code": int(float(fields["exit_code"])) if "exit_code" in fields else None,
            "rule": "P1", "line": lineno, "self_id": False,
        }
    return None


def parse_log(path) -> dict:
    """Parse a kernel/pasted log into {outcomes: {task: row}, events, run_level}."""
    stdout, stderr, is_json = _load(path)
    lines = stdout.splitlines()

    outcomes: dict[str, dict] = {}
    pending_header = None  # (task, lineno)
    run_level = {"agent_dir_label": None, "max_tool_calls": None,
                 "adapter_source": None, "wheels": None, "summary_label": None,
                 "served_model_ids": None}
    # REV5 (D5-1): the kernel's own "served model ids: [...]" line is the only
    # evidence that names the SERVED model (vs the declared agent.yaml model).
    for m in SERVED.finditer(stdout + "\n" + stderr):
        ids = sorted(set(re.findall(r"'([^']+)'", m.group(1))))
        run_level["served_model_ids"] = sorted(set(run_level["served_model_ids"] or []) | set(ids))

    for i, line in enumerate(lines, 1):
        m = H1.match(line)
        if m:
            run_level["agent_dir_label"] = m.group(1).strip()
        m = H3.search(line)
        if m:
            run_level["max_tool_calls"] = int(m.group(1))
        m = H4.search(line)
        if m:
            run_level["wheels"] = int(m.group(1))
        m = A1.match(line)
        if m:
            run_level["adapter_source"] = m.group(2).strip()

        hm = P1H.match(line)
        if hm:
            pending_header = (hm.group(3), i)
            continue
        hm = P2H.match(line)
        if hm:
            pending_header = (hm.group(3), i)
            continue
        row = _parse_result_line(line, i)
        if row:
            task = row["task"]
            if task is None and pending_header is not None:
                task = pending_header[0]
            if task is None:
                continue
            prev = outcomes.get(task)
            # self-identifying rows win over P1 pairings
            if prev is None or (row.get("self_id") and not prev.get("self_id")):
                outcomes[task] = row
            pending_header = None

    # harness events from stderr (JSON) or whole text
    events: list[dict] = []
    event_src = stderr if is_json else stdout
    seen = set()
    for raw in event_src.splitlines():
        m = L1.match(raw)
        if not m:
            continue
        level, logger, msg = m.group(1), m.group(2), m.group(3)
        tm = TASK_IN_MSG.search(msg)
        task = tm.group(1) if tm else None
        template = "UNKNOWN"
        for name, needle in _EVENT_TEMPLATES:
            if needle in msg:
                template = name
                break
        if template == "UNKNOWN" and _CALL_CAP.search(msg):
            template = "CALL_CAP"
        key = (task, level, logger, msg)
        if key in seen:
            continue
        seen.add(key)
        events.append({"template": template, "level": level, "logger": logger,
                       "task": task, "text": msg[:300]})

    return {"outcomes": outcomes, "events": events, "run_level": run_level,
            "is_json": is_json, "n_lines": len(lines)}
