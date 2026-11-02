"""Harness edit_file emulation (design §8.3).

Loads the competition harness's OWN `apply_replacement` from the on-disk wheel
`Gemma/_whl_inspect/adk_eval_core-0.1.0-py3-none-any.whl` and uses it to emulate
`edit_file`. This is harness source, not agent code — nothing the agent authored
is ever executed here.

The wheel's `adk_eval_core.editing.edit` imports only stdlib plus one exception
class (`adk_eval_core.errors.AmbiguousMatchError`). We register four stub modules
in sys.modules before exec, exactly as the harness's own loader (run_local.py)
does, so `adk_eval_core/__init__` (which needs pydantic) is never imported.
"""
from __future__ import annotations

import pathlib
import types
import zipfile

from . import io, paths

_WHEEL_REL = "_whl_inspect/adk_eval_core-0.1.0-py3-none-any.whl"

_LOADED = None          # (apply_replacement, make_diff, AmbiguousMatchError)
_WHEEL_INFO = {"sha256": None, "members": []}


def wheel_path() -> pathlib.Path:
    return paths.gemma_root() / _WHEEL_REL


def wheel_info() -> dict:
    """sha256 + member names of the loaded wheel (recorded in replay evidence)."""
    _load()
    return dict(_WHEEL_INFO)


def available() -> bool:
    return wheel_path().is_file()


def _load():
    global _LOADED
    if _LOADED is not None:
        return _LOADED
    wp = wheel_path()
    z = zipfile.ZipFile(wp)
    _WHEEL_INFO["sha256"] = io.sha256_bytes(wp.read_bytes())
    members = ("adk_eval_core/errors.py", "adk_eval_core/editing/edit.py")
    _WHEEL_INFO["members"] = list(members)

    import sys
    if "adk_eval_core" not in sys.modules:
        pkg = types.ModuleType("adk_eval_core")
        pkg.__path__ = []
        editing = types.ModuleType("adk_eval_core.editing")
        editing.__path__ = []
        errors = types.ModuleType("adk_eval_core.errors")
        edit = types.ModuleType("adk_eval_core.editing.edit")
        edit.__name__ = "adk_eval_core.editing.edit"
        # register all four BEFORE exec (edit.py resolves its dataclasses'
        # module through sys.modules under `from __future__ import annotations`)
        sys.modules["adk_eval_core"] = pkg
        sys.modules["adk_eval_core.editing"] = editing
        sys.modules["adk_eval_core.errors"] = errors
        sys.modules["adk_eval_core.editing.edit"] = edit
        exec(compile(z.read(members[0]).decode("utf-8"), members[0], "exec"),
             errors.__dict__)
        exec(compile(z.read(members[1]).decode("utf-8"), members[1], "exec"),
             edit.__dict__)
    edit = sys.modules["adk_eval_core.editing.edit"]
    errors = sys.modules["adk_eval_core.errors"]
    _LOADED = (edit.apply_replacement, edit.make_diff, errors.AmbiguousMatchError)
    return _LOADED


def emulate_edit_file(content: str | None, old_string: str, new_string: str,
                      allow_multiple=False) -> dict:
    """Emulate the harness edit_file wrapper (HARNESS_README §6.2).

    Returns {status, strategy?, occurrences?, new_content?, diff?, error_type?,
    error_message?}. A missing file is a FileReadError; the empty-old_string and
    not-found branches come straight from the wheel's apply_replacement.
    """
    if content is None:
        return {"status": "error", "error_type": "FileReadError",
                "error_message": "File not found"}
    apply_replacement, make_diff, ambig = _load()
    try:
        res = apply_replacement(content, old_string, new_string,
                                bool(allow_multiple))
    except ambig as e:  # noqa: F841
        return {"status": "error", "error_type": "FileEditError",
                "error_message": str(e)}
    if res.error_message:
        return {"status": "error", "error_type": "FileEditError",
                "error_message": res.error_message}
    diff = make_diff(content, res.new_content, "file")
    return {"status": "ok", "strategy": res.strategy,
            "occurrences": res.occurrences, "new_content": res.new_content,
            "diff": diff}
