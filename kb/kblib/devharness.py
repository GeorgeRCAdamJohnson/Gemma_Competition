"""Dev-harness AST pass (design REV5 R5.4 / D5-8, closes D3-5; engine dh-1).

Every Gemma eval notebook builds its own ADK `App` with
`EventsCompactionConfig(...)` and `ContextCacheConfig(...)`. The scorer's values
are documented in HARNESS_README §"Events Compaction". This module reads the
notebook values STATICALLY:

- `notebook_src.py` and every `*.ipynb` code cell (cell source joined; lines
  starting with `!` or `%` - IPython magics/shell - are blanked) are parsed with
  `ast.parse`;
- `Call` nodes whose callee is named `EventsCompactionConfig` /
  `ContextCacheConfig` contribute their keyword arguments, decoded with
  `ast.literal_eval` (constants only).

Comments and string contents are never read as config, and nothing is executed
(no exec/eval/compile-to-run; enforced by a static test).
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
import warnings

from . import paths

DH_VERSION = "dh-1"
_TARGETS = ("EventsCompactionConfig", "ContextCacheConfig")
SCORER_FIELDS = ("compaction_interval", "overlap_size", "token_threshold")
_NOTEBOOK_PY = ("notebook_src.py",)


def _blank_magics(src: str) -> str:
    return "\n".join("" if ln.lstrip().startswith(("!", "%")) else ln
                     for ln in src.split("\n"))


def _callee(node: ast.Call) -> str | None:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def scan_source(text: str) -> dict | None:
    """Return {callee: {kw: value}} for the first call of each target, or None
    when the source does not parse."""
    try:
        with warnings.catch_warnings():
            # notebook code may carry e.g. invalid escape sequences; parsing
            # must stay silent (warnings are not config)
            warnings.simplefilter("ignore")
            tree = ast.parse(_blank_magics(text))
    except (SyntaxError, ValueError):
        return None
    found: dict[str, dict] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = _callee(node)
        if name not in _TARGETS or name in found:
            continue
        kws = {}
        for kw in node.keywords:
            if kw.arg is None:
                continue
            try:
                kws[kw.arg] = ast.literal_eval(kw.value)
            except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                kws[kw.arg] = None  # non-constant expression: recorded as unknown
        found[name] = kws
    return found


def _ipynb_cells(path: pathlib.Path) -> list[str]:
    try:
        nb = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return []
    out = []
    for cell in nb.get("cells", []) if isinstance(nb, dict) else []:
        if not isinstance(cell, dict) or cell.get("cell_type") != "code":
            continue
        src = cell.get("source", "")
        out.append("".join(src) if isinstance(src, list) else str(src))
    return out


def scan_file(path: pathlib.Path) -> dict:
    """Merge target calls over a .py file or every code cell of an .ipynb."""
    path = pathlib.Path(path)
    if path.suffix == ".ipynb":
        sources = _ipynb_cells(path)
    else:
        try:
            sources = [path.read_text(encoding="utf-8", errors="replace")]
        except OSError:
            sources = []
    merged: dict[str, dict] = {}
    unparsed = 0
    for src in sources:
        res = scan_source(src)
        if res is None:
            unparsed += 1
            continue
        for k, v in res.items():
            merged.setdefault(k, v)
    return {"calls": merged, "unparsed_cells": unparsed}


def notebook_files(d: pathlib.Path) -> list[pathlib.Path]:
    d = pathlib.Path(d)
    if not d.is_dir():
        return []
    files = [d / n for n in _NOTEBOOK_PY if (d / n).is_file()]
    files += sorted(p for p in d.glob("*.ipynb") if p.is_file())
    return files


def _flatten(calls: dict) -> dict:
    out = {}
    for k, v in sorted((calls.get("EventsCompactionConfig") or {}).items()):
        out[k] = v
    for k, v in sorted((calls.get("ContextCacheConfig") or {}).items()):
        out[k if k.startswith("cache_") else "cache_" + k] = v
    return out


def scan_dir(d, code_file: str | None = None) -> dict | None:
    """Scan a kernel/run dir's notebooks. None when the dir has no notebook.

    The primary file is the kernel-metadata `code_file` when it is present,
    else notebook_src.py, else the first .ipynb. `files_disagree` is true when
    another notebook file in the same dir carries different values.
    """
    d = pathlib.Path(d)
    files = notebook_files(d)
    if not files:
        return None
    per = {}
    for f in files:
        per[f.name] = scan_file(f)
    order = []
    if code_file and code_file in per:
        order.append(code_file)
    order += [f.name for f in files if f.name not in order]
    primary = next((n for n in order if per[n]["calls"].get("EventsCompactionConfig")),
                   order[0])
    vals = _flatten(per[primary]["calls"])
    flats = {n: _flatten(per[n]["calls"]) for n in order if per[n]["calls"]}
    disagree = len({json.dumps(v, sort_keys=True) for v in flats.values()}) > 1
    rec = {"source": paths.rel_posix(d / primary), "files": sorted(per),
           "found": bool(per[primary]["calls"].get("EventsCompactionConfig")),
           "files_disagree": disagree, "version": DH_VERSION}
    rec.update(vals)
    return rec


_BULLET = re.compile(r"`(\w+)\s*=\s*([\d,]+)`")


def scorer_reference(readme_path) -> dict:
    """Read the scorer's EventsCompactionConfig values from HARNESS_README's
    bullets (expected 5 / 2 / 14336). Missing README -> {}."""
    p = pathlib.Path(readme_path)
    try:
        lines = p.read_text(encoding="utf-8", errors="replace").split("\n")
    except OSError:
        return {}
    out: dict = {}
    start = None
    for i, ln in enumerate(lines):
        if "EventsCompactionConfig" in ln and ln.lstrip().startswith("- **"):
            start = i
            break
    if start is None:
        return {}
    for j in range(start + 1, min(len(lines), start + 12)):
        ln = lines[j]
        if ln.lstrip().startswith("- **"):
            break
        for k, v in _BULLET.findall(ln):
            out[k] = int(v.replace(",", ""))
    out["source"] = f"{paths.rel_posix(p)}:L{start + 1}"
    return out


def matches_scorer(dev: dict | None, scorer: dict) -> tuple[bool | None, list[str]]:
    """(matches, mismatching fields). None when either side lacks the values."""
    if not dev or not dev.get("found") or not scorer:
        return None, []
    mism = []
    for k in SCORER_FIELDS:
        if k not in scorer or dev.get(k) is None:
            continue
        if dev.get(k) != scorer[k]:
            mism.append(k)
    compared = [k for k in SCORER_FIELDS if k in scorer and dev.get(k) is not None]
    if not compared:
        return None, []
    return (not mism), mism
