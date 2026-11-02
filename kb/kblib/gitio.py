"""Single git entry point with a verb allowlist (design §13.2).

Every git call in the replay engine goes through git(). The allowlist makes
`commit`, `push`, `fetch`, `config`, `stash`, `gc` and main-clone
`reset`/`checkout` impossible to issue. Worktree-scoped commands carry the EOL
overrides (F10); main-clone snapshots never do.
"""
from __future__ import annotations

import os
import subprocess

# (scope, first-token[, second-token]) -> allowed
_MAIN_RO = {
    ("rev-parse",), ("status",), ("diff",), ("ls-files",), ("for-each-ref",),
    ("worktree", "list"), ("count-objects",), ("cat-file",),
}
_MAIN_WORKTREE = {
    ("worktree", "add"), ("worktree", "remove"), ("worktree", "prune"),
}
_WT_SCOPE = {
    ("reset",), ("clean",), ("apply",), ("add",), ("diff",),
    ("checkout",), ("rev-parse",), ("cat-file",), ("status",),
}

EOL_FLAGS = ["-c", "core.autocrlf=false", "-c", "core.eol=lf"]


class GitError(Exception):
    pass


def _key(args):
    if not args:
        raise GitError("empty git args")
    first = args[0]
    if first in ("worktree", "count-objects", "for-each-ref", "ls-files") and len(args) > 1:
        return (first, args[1]) if (first, args[1]) in (_MAIN_RO | _MAIN_WORKTREE | _WT_SCOPE) else (first,)
    return (first,)


def _allowed(scope, args):
    first = args[0] if args else None
    second = args[1] if len(args) > 1 else None
    if scope == "main-ro":
        return (first,) in _MAIN_RO or (first, second) in _MAIN_RO
    if scope == "main-worktree":
        return (first, second) in _MAIN_WORKTREE
    if scope == "worktree":
        return (first,) in _WT_SCOPE
    return False


def _env(worktree=False, odb=None, alt=None):
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["PYTHONUTF8"] = "1"
    if worktree and odb:
        env["GIT_OBJECT_DIRECTORY"] = str(odb)
        if alt:
            env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = str(alt)
    return env


def git(repo, *args, scope, eol=False, odb=None, alt=None, timeout=300,
        extra_env=None, binary=False):
    """Run a git command under the verb allowlist.

    scope: 'main-ro' | 'main-worktree' | 'worktree'. eol adds the CRLF->LF
    overrides (only for worktree-scoped commands and cat-file). odb/alt redirect
    object writes to the throwaway store (worktree scope). extra_env is merged
    into the child env (e.g. GIT_CONFIG_COUNT/KEY/VALUE for core.excludesFile;
    the verb allowlist still applies to args). binary=True returns bytes
    stdout/stderr (e.g. `diff --binary`).
    """
    args = [str(a) for a in args]
    if not _allowed(scope, args):
        raise GitError(f"git verb not allowed in scope {scope}: {' '.join(args[:2])}")
    cmd = ["git", "-C", str(repo)]
    if eol:
        cmd += EOL_FLAGS
    cmd += args
    env = _env(worktree=(scope == "worktree"), odb=odb, alt=alt)
    if extra_env:
        env.update({str(k): str(v) for k, v in extra_env.items()})
    if binary:
        return subprocess.run(cmd, capture_output=True, timeout=timeout, env=env)
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, env=env)


def allowlist_tokens():
    """For the unit test that asserts the exact allowlist."""
    return {"main-ro": sorted(_MAIN_RO), "main-worktree": sorted(_MAIN_WORKTREE),
            "worktree": sorted(_WT_SCOPE)}
