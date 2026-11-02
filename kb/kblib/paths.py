"""Path roots and conventions (design §4).

G   = Gemma root (default c:\\...\\kAGGLE\\Gemma, overridable with GKB_GEMMA_ROOT for tests).
KB  = G/kb.
ROOT= workspace root (parent of G).

All data files store POSIX paths relative to G. Markdown renders Windows paths
relative to ROOT. These helpers centralise that so no module hardcodes a root.
"""
from __future__ import annotations

import os
import pathlib

_DEFAULT_G = r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma"


def gemma_root() -> pathlib.Path:
    env = os.environ.get("GKB_GEMMA_ROOT")
    return pathlib.Path(env if env else _DEFAULT_G)


def kb_root() -> pathlib.Path:
    return gemma_root() / "kb"


def workspace_root() -> pathlib.Path:
    return gemma_root().parent


def rel_posix(p: pathlib.Path, base: pathlib.Path | None = None) -> str:
    """Path relative to base (default G), POSIX separators."""
    base = base if base is not None else gemma_root()
    try:
        return p.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return p.resolve().as_posix()


def win_from_g_rel(g_rel: str) -> str:
    """Render a G-relative POSIX path as a workspace-relative Windows path."""
    return ("Gemma/" + g_rel).replace("/", "\\")


# Directory names skipped by the discovery walk (design §5).
SKIP_DIRS = {
    ".git",
    ".train_env",
    "__pycache__",
}
SKIP_DIR_PREFIXES = ("adapter_dataset", "adapter_v2_")
# local_eval/repos is skipped as a path; handled in discover.

MAX_WALK_DEPTH = 8
LARGE_FILE_BYTES = 50 * 1024 * 1024

# REV5 (R5.3): G-relative roots of the local stacks + the steering file the
# baseline banner is computed from (read-only input; joins the fingerprint).
RIG_ROOT = "local_eval/parity_rig"
SWEEP_ROOT = "local_eval/runs"
OWNER_PREFIX = "comfyops/"
FOREIGN_TOOLS = ("build_kb.py", "kb_query.py", "EXPERIMENT_KB.sqlite")


def steering_protocol() -> pathlib.Path:
    return workspace_root() / ".kiro" / "steering" / "gemma-submission-protocol.md"


# Module-level constant (default root); code that honours GKB_GEMMA_ROOT
# calls steering_protocol().
STEERING_PROTOCOL = pathlib.Path(_DEFAULT_G).parent / ".kiro" / "steering" / \
    "gemma-submission-protocol.md"
