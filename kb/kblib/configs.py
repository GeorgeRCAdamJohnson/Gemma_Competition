"""Config extraction from a run's submission folder (design §6.3).

A strict in-house YAML subset parser handles the tiny machine-generated agent.yaml,
eval_config.yaml and configs/sampling.yaml, including the `!include` tag. This
module reads the run's own submission/ folder (tier 1), which is what the run
actually used. Deeper tiers (notebook AST, pulled kernels, log text) are out of
this build's scope and recorded as absent.
"""
from __future__ import annotations

import hashlib
import json
import re


class YamlSubsetError(Exception):
    pass


def _parse_scalar(s: str):
    s = s.strip()
    if s == "" or s == "~" or s == "null":
        return None
    if s in ("true", "True"):
        return True
    if s in ("false", "False"):
        return False
    if s.startswith('"') and s.endswith('"'):
        try:
            return json.loads(s)
        except Exception:
            return s[1:-1]
    if s.startswith("'") and s.endswith("'"):
        return s[1:-1].replace("''", "'")
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    return s


def _load_yaml_subset(text: str, base_dir):
    """Parse a very small YAML subset into a dict. Supports nested maps, lists,
    and `!include <relpath>`. Raises YamlSubsetError on anything unexpected."""
    lines = [ln.rstrip("\n") for ln in text.split("\n")]

    def parse_block(idx, indent):
        result = {}
        list_result = None
        while idx < len(lines):
            raw = lines[idx]
            if not raw.strip() or raw.lstrip().startswith("#"):
                idx += 1
                continue
            cur_indent = len(raw) - len(raw.lstrip(" "))
            if cur_indent < indent:
                break
            if cur_indent > indent:
                raise YamlSubsetError(f"unexpected indent at: {raw!r}")
            stripped = raw.strip()
            if stripped.startswith("- "):
                if list_result is None:
                    list_result = []
                item = stripped[2:].strip()
                if ":" in item and not item.startswith(('"', "'")):
                    # one-key mapping start
                    sub, idx = parse_block(idx, cur_indent + 2) if False else ({}, idx)
                    k, _, v = item.partition(":")
                    list_result.append({k.strip(): _parse_scalar(v)})
                    idx += 1
                else:
                    list_result.append(_parse_scalar(item))
                    idx += 1
                continue
            if ":" not in stripped:
                raise YamlSubsetError(f"no key in: {raw!r}")
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            if val.startswith("!include "):
                inc = val[len("!include "):].strip()
                result[key] = _resolve_include(inc, base_dir)
                idx += 1
            elif val == "":
                sub, idx = parse_block(idx + 1, cur_indent + 2)
                result[key] = sub
            else:
                result[key] = _parse_scalar(val)
                idx += 1
        return (list_result if list_result is not None else result), idx

    obj, _ = parse_block(0, 0)
    return obj


def _resolve_include(inc, base_dir, depth=0):
    if depth > 10:
        raise YamlSubsetError("include depth exceeded")
    p = base_dir / inc
    if not p.exists():
        return {"!include_missing": inc}
    if inc.endswith((".md", ".txt")):
        return p.read_text(encoding="utf-8", errors="replace")
    if inc.endswith((".yaml", ".yml")):
        return _load_yaml_subset(p.read_text(encoding="utf-8", errors="replace"), p.parent)
    return p.read_text(encoding="utf-8", errors="replace")


def _sha256_lf(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def extract_config(submission_dir, source: str = "run submission folder") -> dict:
    """Extract config fields from an agent package dir.

    `submission_dir` is a run's submission/ folder (tier 1, unchanged) or, in
    REV5 (D5-3), a single `agent_*` child of a kaggle_pkg eval run, a rig arm
    dir (`parity_rig/agent_<arm>` / `agent_ctrl_<arm>`) or a staged dir; the
    caller names it via `source`, recorded as `config_confidence`.
    """
    cfg = {"config_confidence": source}
    if submission_dir is None or not submission_dir.is_dir():
        cfg["config_confidence"] = "no submission folder"
        return cfg
    agent_p = submission_dir / "agent.yaml"
    eval_p = submission_dir / "eval_config.yaml"
    agent = eval_ = {}
    try:
        if agent_p.is_file():
            agent = _load_yaml_subset(agent_p.read_text(encoding="utf-8", errors="replace"),
                                      agent_p.parent) or {}
    except YamlSubsetError as e:
        cfg["agent_yaml_error"] = str(e)
    try:
        if eval_p.is_file():
            eval_ = _load_yaml_subset(eval_p.read_text(encoding="utf-8", errors="replace"),
                                      eval_p.parent) or {}
    except YamlSubsetError as e:
        cfg["eval_yaml_error"] = str(e)

    ev = eval_.get("evaluation", {}) if isinstance(eval_, dict) else {}
    for k in ("max_tool_calls", "max_time_minutes", "max_turns", "timeout_seconds"):
        cfg[k] = ev.get(k) if isinstance(ev, dict) else None
    cfg["model"] = agent.get("model") if isinstance(agent, dict) else None
    cfg["adapter"] = agent.get("adapter") if isinstance(agent, dict) else None

    gcc = agent.get("generate_content_config") if isinstance(agent, dict) else None
    if isinstance(gcc, dict):
        for k in ("temperature", "top_p", "top_k", "max_output_tokens",
                  "frequency_penalty", "presence_penalty", "seed", "stop_sequences"):
            cfg[k] = gcc.get(k)
        tc = gcc.get("thinking_config")
        if isinstance(tc, dict):
            cfg["thinking_budget"] = tc.get("thinking_budget")
            cfg["include_thoughts"] = tc.get("include_thoughts")

    tools = agent.get("tools") if isinstance(agent, dict) else None
    if isinstance(tools, list):
        cfg["tools"] = sorted(str(t) for t in tools if isinstance(t, str))

    instr = agent.get("instruction") if isinstance(agent, dict) else None
    prompt_text = None
    sys_md = submission_dir / "prompts" / "system.md"
    if sys_md.is_file():
        prompt_text = sys_md.read_text(encoding="utf-8", errors="replace")
    elif isinstance(instr, str):
        prompt_text = instr
    if prompt_text is not None:
        cfg["prompt_sha256"] = _sha256_lf(prompt_text)
        cfg["prompt_chars"] = len(prompt_text)

    # out-of-scope model
    if cfg.get("model") and cfg["model"] != "gemma-4-31b-it-qat-w4a16-ct":
        cfg["out_of_scope"] = "non-31B model"
    return cfg


# --------------------------------------------------------------- zip drift (D3-4)

_PKG_FIXED = ("agent.yaml", "eval_config.yaml", "configs/sampling.yaml")


def _pkg_member_ok(name: str) -> bool:
    return name in _PKG_FIXED or (
        name.startswith("prompts/") and name.endswith(".md") and name.count("/") == 1)


def zip_drift(pkg_dir, zip_path=None) -> str:
    """D3-4/D5-7: compare an agent package dir with its submission.zip.

    Files: agent.yaml, eval_config.yaml, configs/sampling.yaml, prompts/*.md.
    The zip is read in memory with stdlib zipfile (never extracted). Hashes are
    sha256 over LF-normalised text, so a CRLF-only difference is not drift.
    A file present on one side only counts as drift. Returns
    `MATCH` | `DRIFT(['a', ...])` | `NO_ZIP`.
    """
    import pathlib
    import zipfile

    pkg_dir = pathlib.Path(pkg_dir)
    zp = pathlib.Path(zip_path) if zip_path is not None else pkg_dir / "submission.zip"
    if not zp.is_file():
        return "NO_ZIP"

    def h(data: bytes) -> str:
        return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()

    dir_h = {}
    for rel in _PKG_FIXED:
        p = pkg_dir / rel
        if p.is_file():
            dir_h[rel] = h(p.read_bytes())
    pdir = pkg_dir / "prompts"
    if pdir.is_dir():
        for p in sorted(pdir.glob("*.md")):
            dir_h["prompts/" + p.name] = h(p.read_bytes())
    zip_h = {}
    try:
        with zipfile.ZipFile(zp) as zf:
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                if info.is_dir() or not _pkg_member_ok(name):
                    continue
                zip_h[name] = h(zf.read(info))
    except zipfile.BadZipFile:
        return "DRIFT(['<bad zip>'])"
    drift = sorted(k for k in set(dir_h) | set(zip_h) if dir_h.get(k) != zip_h.get(k))
    return "MATCH" if not drift else f"DRIFT({drift!r})"


def config_one_liner(cfg: dict) -> str:
    """Compact config summary for KB_SUMMARY tables."""
    def v(k):
        x = cfg.get(k)
        return "-" if x is None else str(x)
    tools = cfg.get("tools")
    sha = cfg.get("prompt_sha256")
    return (f"model={v('model')} budget={v('max_tool_calls')}/{v('max_time_minutes')}/"
            f"{v('max_turns')}/{v('timeout_seconds')} temp={v('temperature')} "
            f"top_k={v('top_k')} thinking={v('thinking_budget')} "
            f"tools={len(tools) if isinstance(tools, list) else '-'} "
            f"prompt={sha[:12] if sha else '-'}")
