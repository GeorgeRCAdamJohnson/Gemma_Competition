"""Gold-first git-worktree replay engine (design §13, version rp-5).

rp-5 (REVISION 5, D5-19): gold-first records cached in replays/gold/<task>.json
keyed by (engine_version, pins, required_mode, task_fingerprint, env) and reused;
gold that exits 0 with 0 failed / 0 errors whose missing required nodes were all
SKIPPED is INFRA (platform skip, JUnit skip messages recorded) instead of INVALID;
`required_mode` 'added' (default, = rp-4 required set) | 'hunk' (adds the
enclosing test functions of every modified test_patch hunk; never removes a
node); every git call goes through gitio (add -N / diff --binary included); a
base-env `pip freeze --all` before/after artifact proves the base env is never
mutated.

rp-4 adds PER-TASK dependency pinning: each task's tests run against the
pygments/markdown-it-py versions its own poetry.lock pinned (lockfile wins; a
small hardcoded fallback is a last resort), installed into an ISOLATED %TEMP%
--target dir prepended to the test subprocess PYTHONPATH only. The shared
.venv/sys.executable env is NEVER mutated and the scorer-judging logic
(_required_pass, harness_like, gold_relative, JUnit parse, the exit-97
rich.__file__-under-worktree assertion, the required-node set) is UNCHANGED.


Replays candidate patches against the real tests in throwaway %TEMP% worktrees,
GOLD FIRST. For every replayed task the gold patch + test_patch run first; if
gold does not pass locally, every agent replay for that task is INFRA/UNVERIFIED
(never a counted pass/fail). The main clones are never dirtied: all work happens
in `%TEMP%/gkb_<pid>_<hex>/wt_<task>` worktrees, torn down in finally, with git
objects redirected to a throwaway store. CloneGuard proves the clones are
byte-identical before and after.

Cached by (task, candidate sha256) under KB/replays/cache so a second
`build --replay` with no new candidates re-runs nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import shutil
import tempfile
import time
import xml.etree.ElementTree as ET

from . import gitio, io, paths, unidiff

RP_VERSION = "rp-5"
REQUIRED_MODES = ("added", "hunk")

# Module-level warnings (e.g. 'PIN-FALLBACK <task> <pkg>==<ver>'); build_kb.py
# writes them sorted+unique into build_log.txt.
WARNINGS = []


class EnvFreezeError(Exception):
    """The base interpreter's `pip freeze --all` changed across a replay session."""

_CLONE = {"Textualize/rich": "rich", "fastapi/fastapi": "fastapi",
          "psf/requests": "requests", "encode/httpx": "httpx"}
_PKG = {"rich": "rich", "fastapi": "fastapi", "requests": "requests", "httpx": "httpx"}

# ------------------------------------------------------------- per-task dep pins
# Rich tests hard-code exact ANSI/pygments byte output, so each task's tests must
# run against the pygments/markdown-it-py versions its own poetry.lock pinned. We
# NEVER mutate the shared .venv/sys.executable env: pins are installed into an
# isolated %TEMP% --target dir that is prepended to the test subprocess PYTHONPATH
# (AFTER the worktree, so the worktree `rich` still imports first and the exit-97
# `rich.__file__`-under-worktree assertion keeps working). This changes ONLY which
# library versions are present, never which tests must pass or how pass is judged.
_PIN_PKGS = ("pygments", "markdown-it-py")
# Backstop ONLY when a task's poetry.lock cannot be parsed (recorded as fallback
# provenance with a warning on the replay record). Lockfile always wins.
_PIN_FALLBACK = {"rich_3469": {"pygments": "2.17.2"},
                 "rich_4070": {"pygments": "2.19.2"},
                 "rich_4079": {"pygments": "2.19.2"}}


def _norm_pkg(name):
    return name.strip().lower().replace("_", "-")


def _parse_lock_pins(worktree):
    """Parse <worktree>/poetry.lock for the _PIN_PKGS versions. Return
    {normalized_name: version}; {} if the lock is missing/unparseable.

    Scans `[[package]]` blocks for the `name = "..."` / `version = "..."` pair
    (stdlib line scanner, no TOML dependency). Case/`-`vs`_` normalized so
    `Pygments`/`markdown-it-py` match regardless of how the lock spells them.
    """
    lock = pathlib.Path(worktree) / "poetry.lock"
    if not lock.is_file():
        return {}
    try:
        text = lock.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    return _parse_lock_text(text)


def _parse_lock_text(text):
    """poetry.lock text -> {normalized_name: version} for _PIN_PKGS."""
    wanted = {_norm_pkg(p) for p in _PIN_PKGS}
    pins = {}
    cur_name = None
    for raw in text.splitlines():
        line = raw.strip()
        if line == "[[package]]":
            cur_name = None
            continue
        m = re.match(r'name\s*=\s*"([^"]+)"', line)
        if m:
            cur_name = _norm_pkg(m.group(1))
            continue
        m = re.match(r'version\s*=\s*"([^"]+)"', line)
        if m and cur_name in wanted and cur_name not in pins:
            pins[cur_name] = m.group(1)
    return pins


def _resolve_pins(repo, task, worktree):
    """Return (pins, provenance, warnings).

    Non-rich repos get an empty pin set (their tests do not depend on the
    pygments/markdown-it-py byte output), so fastapi/requests replays are
    byte-identical to the pre-fix engine. For rich, prefer the task's own
    poetry.lock at base_commit; fall back to the hardcoded map only when the
    lock yields no pygments pin (recorded with a warning).
    """
    if _CLONE.get(repo) != "rich":
        return {}, "none", []
    return _resolve_from_lock(task, _parse_lock_pins(worktree))


def pins_at_commit(repo, task, base_commit):
    """The pin set run_candidate would resolve, WITHOUT a worktree: reads
    `<base_commit>:poetry.lock` from the main clone via the read-only
    `cat-file` (gitio main-ro). Used as a gold-cache key field.
    Returns sorted ['pkg==ver', ...]."""
    if _CLONE.get(repo) != "rich":
        return []
    clone, _ = clone_for(repo)
    if clone is None:
        return []
    r = gitio.git(clone, "cat-file", "-p", f"{base_commit}:poetry.lock",
                  scope="main-ro", eol=True)
    text = r.stdout if r.returncode == 0 else ""
    pins, _prov, _w = _resolve_from_lock(task, _parse_lock_text(text) if text else {})
    return sorted(f"{k}=={v}" for k, v in pins.items())


def _resolve_from_lock(task, pins):
    warnings = []
    if "pygments" in pins:
        return pins, "lockfile", warnings
    fb = dict(_PIN_FALLBACK.get(task, {}))
    if fb:
        warnings.append(
            f"poetry.lock yielded no pygments pin for {task}; using hardcoded "
            f"FALLBACK {fb} (provenance=fallback)")
        for k, v in sorted(fb.items()):
            WARNINGS.append(f"PIN-FALLBACK {task} {k}=={v}")
        # keep any lockfile-derived markdown-it-py pin alongside the fallback
        merged = dict(fb)
        for k, v in pins.items():
            merged.setdefault(k, v)
        return merged, "fallback", warnings
    if pins:
        # lock parsed but had only markdown-it-py (no pygments and no fallback)
        return pins, "lockfile", warnings
    return {}, "none", []

_EXCLUDE = ["__pycache__/", "*.pyc", ".pytest_cache/", "*.egg-info/", "build/",
            "dist/", ".coverage"]

_PROTECTED_RE = [
    re.compile(r"(^|/)test_[^/]*\.py$"), re.compile(r"(^|/)[^/]*_test\.py$"),
    re.compile(r"(^|/)tests?/.*\.py$"), re.compile(r"(^|/)testing/.*\.py$"),
    re.compile(r"(^|/)conftest\.py$"),
]
_PROTECTED_NAMES = {"pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg",
                    ".pytest.ini", "sitecustomize.py", "usercustomize.py",
                    "_swegemma_stubs.py"}


def clone_for(repo: str):
    name = _CLONE.get(repo)
    if not name:
        return None, None
    clone = paths.gemma_root() / "local_eval" / "repos" / name
    return (clone if clone.is_dir() else None), name


# --------------------------------------------------------------------- CloneGuard

class CloneGuard:
    """Snapshot each main clone before/after; the bar is identical (§13.3)."""

    def __init__(self, repos):
        self.repos = repos           # [pathlib.Path]
        self.before = {}

    def _snapshot(self, repo):
        snap = {}
        snap["head"] = _rc(gitio.git(repo, "rev-parse", "HEAD", scope="main-ro"))
        st = gitio.git(repo, "status", "--porcelain=v1", "-uall", scope="main-ro").stdout
        snap["status_lines"] = st.count("\n")
        snap["status_sha"] = io.sha256_text(st)
        snap["diff_sha"] = io.sha256_text(
            gitio.git(repo, "diff", scope="main-ro").stdout)
        snap["refs_sha"] = io.sha256_text(gitio.git(
            repo, "for-each-ref", "--format=%(refname) %(objectname)",
            scope="main-ro").stdout)
        try:
            snap["config_sha"] = io.sha256_bytes((repo / ".git" / "config").read_bytes())
        except OSError:
            snap["config_sha"] = None
        snap["index_sha"] = io.sha256_text(
            gitio.git(repo, "ls-files", "-s", scope="main-ro").stdout)
        co = gitio.git(repo, "count-objects", "-v", scope="main-ro").stdout
        snap["count_objects"] = {k: v for k, v in
                                 re.findall(r"(\w[\w-]*): (\d+)", co)}
        return snap

    def snapshot_before(self):
        for repo in self.repos:
            self.before[str(repo)] = self._snapshot(repo)

    # Fields the BUILDER can affect. HEAD/index/status/diff can move when the
    # user checks the clone out to a different commit mid-build (design §2.10,
    # §13.3: "the user moves this checkout between tasks"); those are EXTERNAL
    # drift, not a builder violation. The builder provably never moves HEAD,
    # writes the index, or writes to the main object store (objects are
    # redirected to the throwaway store, worktrees are detached at base_commit).
    _BUILDER_FIELDS = ("refs_sha", "config_sha", "count_objects")
    _EXTERNAL_FIELDS = ("head", "index_sha", "status_sha", "status_lines", "diff_sha")

    def verify_after(self):
        """Return (ok, report).

        `ok` is True iff no BUILDER-attributable field changed (new objects in
        the main store, new refs, config/stash edits). External drift (the user
        moving HEAD) is recorded separately and does NOT fail the guard.
        """
        report = {}
        ok = True
        for repo in self.repos:
            after = self._snapshot(repo)
            before = self.before.get(str(repo), {})
            builder_diffs = {}
            external_diffs = {}
            for k in before:
                if before[k] != after.get(k):
                    rec = {"before": before[k], "after": after.get(k)}
                    if k in self._BUILDER_FIELDS:
                        builder_diffs[k] = rec
                    else:
                        external_diffs[k] = rec
            if builder_diffs:
                ok = False
            report[str(repo)] = {"builder_diffs": builder_diffs,
                                 "external_drift": sorted(external_diffs.keys())}
        return ok, report


# --------------------------------------------------------------------- Engine

class ReplayEngine:
    def __init__(self, tasks_gold, env_python=None, env_pytest=None, freeze=True):
        self.tasks_gold = tasks_gold
        self.kb = paths.kb_root()
        self.cache_root = self.kb / "replays" / "cache"
        self.gold_root = self.kb / "replays" / "gold"
        self.build_root = None
        self.env_python = env_python or _python_version()
        self.env_pytest = env_pytest or _pytest_version()
        self.module_file_checks = []   # recorded __file__ assertions
        self.freeze = freeze
        self.freeze_check = None
        self._freeze_before = None

    # -- lifecycle --
    def __enter__(self):
        if self.freeze:
            # D5-19e: base-env evidence BEFORE any replay work
            self._freeze_before = _pip_freeze()
            io.safe_write(self.kb / "replays" / "env_freeze_before.txt",
                          "\n".join(self._freeze_before) + "\n")
        self._cleanup_stale_roots()
        self.build_root = pathlib.Path(tempfile.mkdtemp(
            prefix=f"gkb_{os.getpid()}_", dir=tempfile.gettempdir()))
        (self.build_root / ".gkb_owner").write_text(str(os.getpid()), encoding="utf-8")
        self.odb = self.build_root / "odb"
        self.odb.mkdir(exist_ok=True)
        (self.build_root / "exclude").write_text("\n".join(_EXCLUDE) + "\n",
                                                 encoding="utf-8")
        self._worktrees = []
        return self

    def __exit__(self, *exc):
        for (clone, wt) in self._worktrees:
            for _ in range(3):
                r = gitio.git(clone, "worktree", "remove", "--force", str(wt),
                              scope="main-worktree")
                if r.returncode == 0:
                    break
                time.sleep(1.0)
        if self.build_root and self.build_root.exists():
            shutil.rmtree(self.build_root, onerror=_rm_readonly)
        seen = set()
        for (clone, _wt) in self._worktrees:
            if str(clone) not in seen:
                gitio.git(clone, "worktree", "prune", scope="main-worktree")
                seen.add(str(clone))
        if self.freeze and self._freeze_before is not None:
            after = _pip_freeze()
            io.safe_write(self.kb / "replays" / "env_freeze_after.txt",
                          "\n".join(after) + "\n")
            self.freeze_check = {"identical": after == self._freeze_before,
                                 "n_before": len(self._freeze_before),
                                 "n_after": len(after),
                                 "python": self.env_python}
            io.safe_write(self.kb / "replays" / "env_freeze_check.json",
                          io.dumps_json(self.freeze_check))
            if not self.freeze_check["identical"]:
                raise EnvFreezeError(
                    "base interpreter `pip freeze --all` changed during the replay "
                    "session (see replays/env_freeze_{before,after}.txt)")

    def _cleanup_stale_roots(self):
        tmp = pathlib.Path(tempfile.gettempdir())
        for d in tmp.glob("gkb_*"):
            if (d / ".gkb_owner").is_file():
                try:
                    shutil.rmtree(d, onerror=_rm_readonly)
                except OSError:
                    pass

    # -- worktree management --
    def _add_worktree(self, clone, task, base_commit):
        wt = self.build_root / f"wt_{task}"
        if wt.exists():
            return wt
        # verify base commit present (no fetch)
        chk = gitio.git(clone, "cat-file", "-e", f"{base_commit}^{{commit}}",
                        scope="main-ro", eol=True)
        if chk.returncode != 0:
            raise _InfraError("base commit missing")
        r = gitio.git(clone, "worktree", "add", "--detach", str(wt), base_commit,
                      scope="main-worktree", eol=True)
        if r.returncode != 0:
            raise _InfraError(f"worktree add failed: {r.stderr[:200]}")
        self._worktrees.append((clone, wt))
        return wt

    def _assert_worktree(self, clone, wt):
        if self.build_root not in wt.parents and wt.parent != self.build_root:
            raise _InfraError("worktree not under build root")
        wl = gitio.git(clone, "worktree", "list", "--porcelain",
                       scope="main-ro").stdout
        if str(wt).replace("\\", "/") not in wl.replace("\\", "/"):
            raise _InfraError("worktree not registered")
        if wt.resolve() == clone.resolve():
            raise _InfraError("refuse to reset the clone itself")

    def _reset_worktree(self, clone, wt, base_commit):
        self._assert_worktree(clone, wt)
        gitio.git(wt, "reset", "--hard", base_commit, scope="worktree", eol=True,
                  odb=self.odb, alt=clone / ".git" / "objects")
        gitio.git(wt, "clean", "-fdx", scope="worktree", eol=True,
                  odb=self.odb, alt=clone / ".git" / "objects")

    # -- isolated per-task dependency pins --
    def _ensure_pins(self, pins):
        """Install `pins` into an isolated %TEMP% --target dir. Returns
        (target_dir | None, install_log, infra_reason).

        NEVER mutates the base interpreter/.venv: installs ONLY into --target.
        The target dir is keyed by the sorted pkg==ver set under
        build_root/pins/<sha12>, so an identical pin set (e.g. pygments 2.19.2
        shared by 4070 and 4079) installs once and is reused. The whole dir lives
        under build_root (%TEMP%) and is torn down in __exit__. On a failed/absent
        install (offline, uncached, yanked) returns (None, log, reason) and the
        caller records the replay as INFRA/UNVERIFIED — never a wrong-version pass.
        """
        import subprocess
        import sys
        if not pins:
            return None, [], None
        spec = sorted(f"{k}=={v}" for k, v in pins.items())
        key = hashlib.sha256("\n".join(spec).encode("utf-8")).hexdigest()[:12]
        target = self.build_root / "pins" / key
        done = target / ".gkb_pins_ok"
        if done.is_file():
            return target, [{"cached": True, "spec": spec}], None
        target.mkdir(parents=True, exist_ok=True)
        # Allow pip's local cache (offline-friendly); do NOT pin an --index-url.
        cmd = [sys.executable, "-m", "pip", "install", "--no-input",
               "--disable-pip-version-check", "--target", str(target)] + spec
        try:
            r = subprocess.run(cmd, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=600)
        except Exception as e:  # noqa: BLE001 - infra, not a scorer path
            return None, [{"spec": spec, "error": f"{type(e).__name__}: {e}"}], \
                f"pin install raised: {type(e).__name__}: {e}"
        log = [{"spec": spec, "rc": r.returncode,
                "stderr_tail": (r.stderr or "")[-300:]}]
        if r.returncode != 0:
            return None, log, f"pin install failed (rc={r.returncode}): " \
                              f"{(r.stderr or r.stdout or '')[-200:]}"
        done.write_text("ok", encoding="utf-8")
        return target, log, None

    # -- candidate execution --
    def run_candidate(self, repo, task, base_commit, *, kind, patch_text=None,
                      vfs_files=None, timeout_s=300, gold_pass_tests=None,
                      required_mode="added"):
        """Run one candidate in a reset worktree. Returns a result dict."""
        if required_mode not in REQUIRED_MODES:
            raise ValueError(f"required_mode must be one of {REQUIRED_MODES}")
        clone, _name = clone_for(repo)
        if clone is None:
            return {"result": "INFRA", "reason": "no local clone for repo",
                    "verdict_valid": False}
        gt = self.tasks_gold["tasks"].get(task)
        if gt is None:
            return {"result": "INFRA", "reason": "task not in gold",
                    "verdict_valid": False}
        try:
            wt = self._add_worktree(clone, task, base_commit)
            self._reset_worktree(clone, wt, base_commit)
        except _InfraError as e:
            return {"result": "INFRA", "reason": str(e), "verdict_valid": False}

        apply_log = []
        # 1. write candidate
        if kind == "patch":
            method, ok = self._apply_ladder(wt, clone, patch_text, apply_log)
            if not ok:
                return {"result": "APPLY_FAIL", "reason": "candidate patch did not apply",
                        "apply": {"method": None, "log": apply_log}, "verdict_valid": False}
        else:  # vfs-write
            for rel, content in (vfs_files or {}).items():
                target = wt / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8", newline="\n")
            method = "vfs-write"

        # 2. candidate.patch (add -N . ; diff --binary) with excludes
        diff_bytes = self._candidate_diff(wt, clone)
        git_diff_len_chars = len(diff_bytes.decode("utf-8", "surrogateescape"))

        # 3. protected reset
        self._protected_reset(wt, clone, gt, diff_bytes)

        # 4. apply test_patch
        tp = gt_test_patch(self.tasks_gold, task)
        tmethod, tok = self._apply_ladder(wt, clone, tp, apply_log, label="test_patch")
        if not tok:
            return {"result": "INFRA", "reason": "test_patch did not apply",
                    "apply": {"method": method, "log": apply_log},
                    "git_diff_len_chars": git_diff_len_chars, "verdict_valid": False}

        # 4b. resolve + install this task's dependency pins into an ISOLATED
        # target dir (base env untouched). The worktree is at base_commit, so the
        # task's own poetry.lock is on disk here (lockfile provenance preferred).
        pins, pin_provenance, pin_warnings = _resolve_pins(repo, task, wt)
        pin_target, pin_log, pin_infra = self._ensure_pins(pins)
        if pin_infra is not None:
            # NEVER run tests on a wrong-version env (hard constraint 2).
            return {"result": "INFRA", "reason": f"pin unavailable: {pin_infra}",
                    "apply": {"method": method, "test_patch_method": tmethod,
                              "log": apply_log},
                    "git_diff_len_chars": git_diff_len_chars,
                    "pins": sorted(f"{k}=={v}" for k, v in pins.items()),
                    "pin_provenance": pin_provenance, "pin_warnings": pin_warnings,
                    "pin_log": pin_log, "engine_version": RP_VERSION,
                    "verdict_valid": False}

        # 5. py_compile changed files + 6. run tests
        test_files = gt["tests"]["files"] or []
        res = self._run_pytest(wt, repo, test_files, timeout_s, pin_target=pin_target)
        res["apply"] = {"method": method, "test_patch_method": tmethod, "log": apply_log}
        res["git_diff_len_chars"] = git_diff_len_chars
        res["pins"] = sorted(f"{k}=={v}" for k, v in pins.items())
        res["pin_provenance"] = pin_provenance
        res["pin_warnings"] = pin_warnings
        res["pin_log"] = pin_log
        res["engine_version"] = RP_VERSION
        res["env"] = {"python": self.env_python, "pytest": self.env_pytest,
                      "platform": "win32",
                      "pins": sorted(f"{k}=={v}" for k, v in pins.items()),
                      "pin_provenance": pin_provenance,
                      "deviations": ["windows-not-linux", "local-pytest",
                                     "no-PYTHONSAFEPATH"]}

        # required tests: 'added' = test_patch added defs (rp-4, unchanged);
        # 'hunk' = added ∪ enclosing test functions of modified test_patch hunks
        required, hunk_nodes = _required_tests(gt, wt, required_mode, tp)
        res["required_mode"] = required_mode
        if required_mode == "hunk":
            res["hunk_nodes"] = hunk_nodes
        res["required_tests"] = required
        res["required_pass"] = self._required_pass(res, required)
        res["missing_required"] = _missing_required(res, required)
        res["harness_like"] = (res.get("exit_code") == 0 and res.get("junit_present")
                               and res.get("passed", 0) >= 1
                               and res.get("failed", 0) == 0 and res.get("errors", 0) == 0
                               and res["required_pass"])
        if gold_pass_tests is not None:
            regr = [t for t in gold_pass_tests if t in res.get("failed_names", [])
                    or t in res.get("error_names", [])]
            res["regressions_vs_gold"] = regr
            res["gold_relative"] = res["required_pass"] and not regr
        return res

    # -- apply ladder (gold/manual patch candidates), §13.4 step 1 --
    def _apply_ladder(self, wt, clone, patch_text, apply_log, label="candidate"):
        if not patch_text:
            return None, True
        pf = self.build_root / f"_{label}_{os.getpid()}.patch"
        pf.write_text(patch_text if patch_text.endswith("\n") else patch_text + "\n",
                      encoding="utf-8", newline="\n")
        rungs = [["apply", str(pf)],
                 ["apply", "--3way", str(pf)],
                 ["apply", "--ignore-space-change", "--ignore-whitespace", str(pf)],
                 ["apply", "--recount", str(pf)]]
        for rung in rungs:
            r = gitio.git(wt, *rung, scope="worktree", eol=True, odb=self.odb,
                          alt=clone / ".git" / "objects")
            apply_log.append({"rung": " ".join(rung[:2]), "rc": r.returncode,
                              "stderr": r.stderr[:300]})
            if r.returncode == 0:
                return rung[1] if rung[1].startswith("--") else "plain", True
        return None, False

    def _candidate_diff(self, wt, clone):
        # core.excludesFile is passed through the env (GIT_CONFIG_*) so the
        # allowlisted verb stays args[0]; both calls go through gitio.
        exclude = self.build_root / "exclude"
        env_excl = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.excludesFile",
                    "GIT_CONFIG_VALUE_0": str(exclude)}
        alt = clone / ".git" / "objects"
        gitio.git(wt, "add", "-N", ".", scope="worktree", eol=True, odb=self.odb,
                  alt=alt, extra_env=env_excl, binary=True, timeout=120)
        r = gitio.git(wt, "diff", "--binary", scope="worktree", eol=True,
                      odb=self.odb, alt=alt, extra_env=env_excl, binary=True,
                      timeout=120)
        return r.stdout

    def _protected_reset(self, wt, clone, gt, diff_bytes):
        changed = _changed_paths(diff_bytes)
        tp_files = set(gt["tests"]["files"] or [])
        prot = [p for p in changed if p in tp_files or _is_protected(p)]
        if not prot:
            return
        gitio.git(wt, "checkout", "HEAD", "--", *prot, scope="worktree", eol=True,
                  odb=self.odb, alt=clone / ".git" / "objects")
        gitio.git(wt, "clean", "-f", "--", *prot, scope="worktree", eol=True,
                  odb=self.odb, alt=clone / ".git" / "objects")

    def _run_pytest(self, wt, repo, test_files, timeout_s, pin_target=None):
        import subprocess
        pkg = _PKG[_CLONE[repo]]
        junit = self.build_root / f"junit_{os.getpid()}_{int(time.time()*1000)%100000}.xml"
        # NOTE: for `python -c "<code>" a b c`, sys.argv == ['-c', 'a', 'b', ...].
        # argv[1] is the worktree marker; pytest gets argv[2:].
        bootstrap = (
            "import sys,importlib;"
            f"m=importlib.import_module({pkg!r});"
            "f=getattr(m,'__file__','');"
            "wt=sys.argv[1];"
            "print('IMPORT',f);"
            "sys.exit(97) if (not f or wt not in f) else None;"
            "import pytest;sys.exit(pytest.main(sys.argv[2:]))"
        )
        args = [str(wt)] + [str(wt / tf) for tf in test_files] + [
            "-q", "-p", "no:cacheprovider", "-p", "no:anyio", "-o", "timeout=0",
            "-o", "python_classes=Test* *Test", f"--junitxml={junit}"]
        env = {k: v for k, v in os.environ.items()
               if k not in ("PYTHONPATH", "FORCE_COLOR", "NO_COLOR", "COLUMNS",
                            "LINES", "TERM", "CI", "GITHUB_ACTIONS", "PYTEST_ADDOPTS")}
        # Worktree FIRST so the under-test package (e.g. rich) imports from the
        # worktree (keeps the exit-97 rich.__file__ assertion valid); the pin
        # --target dir is appended so ONLY pygments/markdown_it resolve from it.
        if pin_target is not None:
            env["PYTHONPATH"] = os.pathsep.join([str(wt), str(pin_target)])
        else:
            env["PYTHONPATH"] = str(wt)
        env["PYTHONUTF8"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        import sys
        cmd = [sys.executable, "-c", bootstrap] + args
        try:
            r = subprocess.run(cmd, cwd=str(wt), capture_output=True, text=True,
                               encoding="utf-8", errors="replace",
                               timeout=max(1, int(timeout_s)), env=env)
        except subprocess.TimeoutExpired:
            return {"result": "TIMEOUT", "exit_code": None, "junit_present": False,
                    "passed": 0, "failed": 0, "errors": 0, "skipped": 0,
                    "failed_names": [], "error_names": [], "passed_names": [],
                    "import_file": None, "import_ok": None}
        import_file = None
        for ln in (r.stdout or "").splitlines():
            if ln.startswith("IMPORT "):
                import_file = ln[len("IMPORT "):].strip()
                break
        import_ok = bool(import_file and str(wt) in import_file)
        self.module_file_checks.append({"repo": repo, "import_file": import_file,
                                        "under_worktree": import_ok})
        if r.returncode == 97:
            return {"result": "INFRA", "reason": "import check failed (module not in worktree)",
                    "exit_code": 97, "junit_present": False, "passed": 0,
                    "failed": 0, "errors": 0, "skipped": 0, "failed_names": [],
                    "error_names": [], "passed_names": [], "import_file": import_file,
                    "import_ok": import_ok, "verdict_valid": False}
        parsed = _parse_junit(junit)
        parsed["result"] = "RAN"
        parsed["exit_code"] = r.returncode
        parsed["import_file"] = import_file
        parsed["import_ok"] = import_ok
        parsed["stdout_tail"] = (r.stdout or "")[-800:]
        # test-time imports missing from the base env (collection errors)
        # (pytest collection errors print to stdout; a bootstrap import failure of
        # the package under test prints its traceback to stderr)
        parsed["missing_modules"] = sorted(set(re.findall(
            r"ModuleNotFoundError: No module named '([^']+)'",
            (r.stdout or "") + "\n" + (r.stderr or ""))))
        if not import_ok:
            parsed["stderr_tail"] = (r.stderr or "")[-400:]
        return parsed

    def _required_pass(self, res, required):
        if not required:
            # no explicit required tests: fall back to "ran, no failures/errors"
            return (res.get("passed", 0) >= 1 and res.get("failed", 0) == 0
                    and res.get("errors", 0) == 0)
        names = set(res.get("passed_names", []))
        failed = set(res.get("failed_names", []) + res.get("error_names", []))
        for req in required:
            matched = [n for n in (names | failed) if n == req or n.startswith(req + "[")]
            if not matched:
                return False
            if any(n in failed for n in matched):
                return False
        return True

    # -- gold-first controls (§13.5) --
    def gold_first(self, repo, task, base_commit, timeout_s=300, required_mode="added"):
        """Run gold and base controls; return the gold_first validity record."""
        gt = self.tasks_gold["tasks"].get(task)
        patch = gt_patch(self.tasks_gold, task)
        gold = self.run_candidate(repo, task, base_commit, kind="patch",
                                  patch_text=patch, timeout_s=timeout_s,
                                  required_mode=required_mode)
        base = self.run_candidate(repo, task, base_commit, kind="patch",
                                  patch_text=None, timeout_s=timeout_s,
                                  required_mode=required_mode)
        rec = {"task": task, "repo": repo, "base_commit": base_commit,
               "gold": _slim(gold), "base": _slim(base),
               "gold_pass_tests": gold.get("passed_names", []),
               "pins": gold.get("pins", []),
               "pin_provenance": gold.get("pin_provenance", "none"),
               "pin_warnings": gold.get("pin_warnings", []),
               "module_file_check": {"import_file": gold.get("import_file"),
                                     "under_worktree": gold.get("import_ok")},
               "engine_version": RP_VERSION,
               # rp-5 gold-cache key fields (D5-19a)
               "required_mode": required_mode,
               "required_tests": gold.get("required_tests", []),
               "task_fingerprint": (gt or {}).get("task_fingerprint"),
               "env": {"python": self.env_python, "pytest": self.env_pytest}}
        if required_mode == "hunk":
            rec["hunk_nodes"] = gold.get("hunk_nodes", [])
        gold_req = gold.get("required_pass")
        gold_hl = gold.get("harness_like")
        base_fails = not base.get("required_pass", False)
        missing = gold.get("missing_required", [])
        skipped = set(gold.get("skipped_names", []))
        if gold.get("result") in ("INFRA", "APPLY_FAIL", "TIMEOUT"):
            rec["gold_first"] = "INFRA"
            rec["reason"] = gold.get("reason") or gold.get("result")
        elif (not gold_req and gold.get("exit_code") == 0
              and gold.get("failed", 0) == 0 and gold.get("errors", 0) == 0
              and missing and all(m in skipped for m in missing)):
            # D5-19b: required nodes were SKIPPED on this platform -> INFRA
            msgs = sorted({(gold.get("skip_reasons", {}) or {}).get(m) or "(no message)"
                           for m in missing})
            rec["gold_first"] = "INFRA"
            rec["reason"] = ("required nodes skipped on this platform: "
                             + " | ".join(msgs))
            rec["skipped_required"] = sorted(missing)
        elif (not gold_req and gold.get("passed", 0) == 0
              and (gold.get("errors", 0) > 0 or gold.get("import_ok") is False)
              and gold.get("missing_modules")):
            # collection (or the package-under-test import) failed on a module
            # absent from the base env (never installed into it): an environment
            # cause, not a gold failure
            rec["gold_first"] = "INFRA"
            where = ("package under test failed to import"
                     if gold.get("import_ok") is False else "test dependency missing")
            rec["reason"] = (f"{where} in the base env: missing "
                             + ", ".join(gold["missing_modules"]))
        elif not gold_req:
            rec["gold_first"] = "INVALID"
            rec["reason"] = "gold does not pass required tests locally"
        elif not base_fails:
            rec["gold_first"] = "INVALID"
            rec["reason"] = "base already passes required tests"
        elif gold_hl:
            rec["gold_first"] = "VALID-HARNESS-LIKE"
            rec["result_criterion"] = "harness_like"
        else:
            rec["gold_first"] = "VALID-GOLD-RELATIVE"
            rec["result_criterion"] = "gold_relative"
            rec["env_noise"] = [n for n in gold.get("failed_names", [])
                                if n not in gold.get("required_tests", [])]
        return rec


# ----------------------------------------------------------------- cache helpers

def candidate_sha_vfs(vfs_files: dict) -> str:
    parts = []
    for path in sorted(vfs_files):
        h = hashlib.sha256(vfs_files[path].encode("utf-8")).hexdigest()
        parts.append(f"{path}\0{h}")
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def candidate_sha_patch(patch_text: str) -> str:
    norm = (patch_text or "").replace("\r\n", "\n")
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def cache_dir(task: str, cand_sha: str, required_mode: str = "added") -> pathlib.Path:
    # 'added' keeps the rp-4 layout; other modes get a suffixed sibling dir so the
    # two judgings of one candidate never collide (required_mode is a key field).
    leaf = cand_sha[:12] if required_mode == "added" else f"{cand_sha[:12]}-{required_mode}"
    return paths.kb_root() / "replays" / "cache" / task / leaf


def read_cache(task, cand_sha, task_fingerprint, env_python, env_pytest,
               required_mode="added"):
    d = cache_dir(task, cand_sha, required_mode)
    rj = d / "result.json"
    if not rj.is_file():
        return None
    try:
        rec = json.loads(rj.read_text(encoding="utf-8"))
    except Exception:
        return None
    if (rec.get("engine_version") != RP_VERSION
            or rec.get("task_fingerprint") != task_fingerprint
            or rec.get("required_mode", "added") != required_mode
            or rec.get("env", {}).get("python") != env_python
            or rec.get("env", {}).get("pytest") != env_pytest):
        return None
    return rec


def write_cache(task, cand_sha, rec, required_mode="added"):
    rec = dict(rec)
    rec.setdefault("required_mode", required_mode)
    io.safe_write(cache_dir(task, cand_sha, required_mode) / "result.json",
                  io.dumps_json(rec))


# -------------------------------------------------------- gold-first record cache

def gold_record_path(task, required_mode="added"):
    """replays/gold/<task>.json ('added', the default judging) or
    replays/gold/hunk/<task>.json (hunk-mode verdicts recorded separately)."""
    root = paths.kb_root() / "replays" / "gold"
    return root / f"{task}.json" if required_mode == "added" else \
        root / required_mode / f"{task}.json"


def gold_key(task_fingerprint, pins, required_mode, env_python, env_pytest):
    return {"engine_version": RP_VERSION, "pins": sorted(pins or []),
            "required_mode": required_mode, "task_fingerprint": task_fingerprint,
            "env": {"python": env_python, "pytest": env_pytest}}


def gold_key_of(rec):
    env = rec.get("env") or {}
    return {"engine_version": rec.get("engine_version"),
            "pins": sorted(rec.get("pins") or []),
            "required_mode": rec.get("required_mode"),
            "task_fingerprint": rec.get("task_fingerprint"),
            "env": {"python": env.get("python"), "pytest": env.get("pytest")}}


def read_gold(task, key):
    """Return the cached gold-first record iff every key field matches."""
    p = gold_record_path(task, key["required_mode"])
    if not p.is_file():
        return None
    try:
        rec = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return rec if gold_key_of(rec) == key else None


def write_gold(task, rec):
    io.safe_write(gold_record_path(task, rec.get("required_mode", "added")),
                  io.dumps_json(rec))


# ------------------------------------------------------ required-node selection

def _required_tests(gt, wt, mode, test_patch=""):
    """Return (required_names, hunk_nodes).

    'added' = sorted(set(added_tests)) exactly as rp-4. 'hunk' = added ∪ the
    enclosing `def test_*` of every modified hunk of test_patch (post-test_patch
    file in the worktree, AST line ranges); stricter-or-equal: never removes an
    added node. Names are bare function names because JUnit testcase names are
    bare; hunk_nodes keeps the `Class::method` form for the record.
    """
    added = sorted(set(gt["tests"]["added_tests"]))
    if mode != "hunk":
        return added, []

    def _read(rel):
        p = pathlib.Path(wt) / rel
        try:
            return p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
    names, nodes = hunk_test_nodes(test_patch, _read)
    return sorted(set(added) | names), nodes


def hunk_test_nodes(test_patch, read_file):
    """Static: (bare test names, ['file::Class::method' | 'file::func']) of the
    test functions enclosing a changed new-side line of a test_patch hunk.
    `read_file(rel_path) -> text | None` supplies the post-test_patch file."""
    import ast
    names, nodes = set(), set()
    try:
        files = unidiff.parse(test_patch or "")
    except unidiff.UniDiffError:
        return names, []
    for f in files:
        path = f["new_path"]
        if path == "/dev/null" or not path.endswith(".py"):
            continue
        changed = set()
        for h in f["hunks"]:
            changed.update(h.get("added_new_lines", []))
            changed.update(h.get("removed_at_new", []))
        if not changed:
            continue
        text = read_file(path)
        if text is None:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue

        def _span(fn):
            start = min([fn.lineno] + [d.lineno for d in fn.decorator_list])
            return start, getattr(fn, "end_lineno", fn.lineno)

        def _hit(fn):
            s, e = _span(fn)
            return any(s <= ln <= e for ln in changed)

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test") and _hit(node):
                    names.add(node.name)
                    nodes.add(f"{path}::{node.name}")
            elif isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if (isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef))
                            and sub.name.startswith("test") and _hit(sub)):
                        names.add(sub.name)
                        nodes.add(f"{path}::{node.name}::{sub.name}")
    return names, sorted(nodes)


def _missing_required(res, required):
    """Required nodes with no passed/failed/error testcase (e.g. skipped)."""
    seen = set(res.get("passed_names", []) + res.get("failed_names", [])
               + res.get("error_names", []))
    return sorted(req for req in required
                  if not any(n == req or n.startswith(req + "[") for n in seen))


# ----------------------------------------------------------------- small helpers

def gt_patch(tasks_gold, task):
    return _TASKS_RAW.get(task, {}).get("patch", "")


def gt_test_patch(tasks_gold, task):
    return _TASKS_RAW.get(task, {}).get("test_patch", "")


_TASKS_RAW = {}


def load_raw_tasks(tasks_jsonl_path):
    """Load patch/test_patch text (not stored in tasks_gold.json) for replay."""
    global _TASKS_RAW
    _TASKS_RAW = {}
    raw = pathlib.Path(tasks_jsonl_path).read_text(encoding="utf-8", errors="replace")
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        _TASKS_RAW[rec["instance_id"]] = {"patch": rec.get("patch", ""),
                                          "test_patch": rec.get("test_patch", "")}
    return _TASKS_RAW


def _slim(res):
    keep = ("result", "exit_code", "passed", "failed", "errors", "skipped",
            "required_pass", "harness_like", "import_ok", "reason",
            "pins", "pin_provenance", "missing_required", "missing_modules")
    return {k: res.get(k) for k in keep if k in res}


def _changed_paths(diff_bytes):
    out = []
    for ln in diff_bytes.decode("utf-8", "surrogateescape").splitlines():
        m = re.match(r"^\+\+\+ b/(.+)$", ln)
        if m and m.group(1) != "/dev/null":
            out.append(m.group(1))
    return out


def _is_protected(path):
    base = path.split("/")[-1]
    if base in _PROTECTED_NAMES or base.endswith(".pth"):
        return True
    return any(rx.search(path) for rx in _PROTECTED_RE)


def _parse_junit(junit):
    out = {"junit_present": False, "passed": 0, "failed": 0, "errors": 0,
           "skipped": 0, "passed_names": [], "failed_names": [], "error_names": [],
           "skipped_names": [], "skip_reasons": {}}
    if not junit.is_file():
        return out
    out["junit_present"] = True
    try:
        tree = ET.parse(junit)
    except ET.ParseError:
        return out
    for tc in tree.iter("testcase"):
        name = tc.get("name", "")
        base = re.sub(r"\[.*\]$", "", name)
        failed = tc.find("failure") is not None
        error = tc.find("error") is not None
        skipped = tc.find("skipped") is not None
        if error:
            out["errors"] += 1
            out["error_names"].append(base)
        elif failed:
            out["failed"] += 1
            out["failed_names"].append(base)
        elif skipped:
            out["skipped"] += 1
            out["skipped_names"].append(base)
            sk = tc.find("skipped")
            msg = (sk.get("message") or (sk.text or "")).strip()
            if base not in out["skip_reasons"]:
                out["skip_reasons"][base] = msg
        else:
            out["passed"] += 1
            out["passed_names"].append(base)
    for k in ("passed_names", "failed_names", "error_names", "skipped_names"):
        out[k] = sorted(set(out[k]))
    return out


def _pip_freeze():
    """Sorted `python -m pip freeze --all` lines of the BASE interpreter."""
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "-m", "pip", "freeze", "--all",
                        "--disable-pip-version-check"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=300)
    lines = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
    if r.returncode != 0:
        lines.append(f"# pip freeze rc={r.returncode}")
    return sorted(lines)


def _rc(res):
    return res.stdout.strip()


def _python_version():
    import sys
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _pytest_version():
    try:
        import pytest
        return pytest.__version__
    except Exception:
        return "unknown"


def _rm_readonly(func, path, _exc):
    import stat
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


class _InfraError(Exception):
    pass
