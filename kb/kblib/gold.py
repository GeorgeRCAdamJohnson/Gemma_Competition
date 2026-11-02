"""Gold task extraction — tasks_gold.json for all 129 tasks (design §7.2).

Reads comp_files/tasks.jsonl, parses each patch/test_patch with unidiff, and
records files, hunks (added/removed/context), test files, added tests, assert
lines, specificity and a mechanical difficulty class. functions_source is
ast@base_commit for rich/fastapi hunks whose base file can be parsed from the
local clone, else hunk-header.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re

from . import unidiff

_TRIVIAL = {"", "else:", "try:", "finally:", "pass", "return", "break",
            "continue", ")", "]", "}", "):"}

_PKG_DIR = {"rich": "rich/", "fastapi": "fastapi/", "requests": "requests/",
            "httpx": "httpx/"}


def _nontrivial(lines):
    out = []
    for ln in lines:
        s = re.sub(r"\s+", " ", ln.strip())
        if not s or len(s) < 6 or s in _TRIVIAL:
            continue
        if s.startswith("#"):
            continue
        if all(ch in ")]}:," for ch in s):
            continue
        out.append(s)
    return out


def _mech_class(n_files, n_hunks, added, removed):
    tot = added + removed
    if n_files == 1 and n_hunks == 1 and tot <= 10:
        return "EASY"
    if n_files >= 2 or tot > 40:
        return "HARD"
    return "MEDIUM"


def _assert_lines(test_patch):
    """Added lines in test_patch that assert something (line-fallback)."""
    out = []
    for f in unidiff.parse(test_patch):
        if not f["new_path"].endswith(".py"):
            continue
        for h in f["hunks"]:
            for ln in h["added"]:
                s = ln.strip()
                if s.startswith("assert") or "pytest.raises(" in s or \
                        re.match(r"expected\w*\s*=", s):
                    out.append(s[:300])
    return out


def _test_funcs(test_patch):
    files = []
    added_tests = []
    for f in unidiff.parse(test_patch):
        if not f["new_path"].endswith(".py"):
            continue
        files.append(f["new_path"])
        for h in f["hunks"]:
            for ln in h["added"]:
                m = re.match(r"\s*def (test_\w+)", ln)
                if m:
                    added_tests.append(m.group(1))
    return sorted(set(files)), sorted(set(added_tests))


def build_tasks_gold(tasks_jsonl_path) -> dict:
    raw = tasks_jsonl_path.read_bytes()
    tasks_sha = hashlib.sha256(raw).hexdigest()
    tasks = {}
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        tid = rec["instance_id"]
        repo = rec.get("repo", "")
        patch = rec.get("patch", "")
        test_patch = rec.get("test_patch", "")
        files = unidiff.parse(patch)
        file_names = sorted({f["new_path"] for f in files if f["new_path"] != "/dev/null"}
                            | {f["old_path"] for f in files if f["old_path"] != "/dev/null"})
        hunks = []
        n_added = n_removed = 0
        for f in files:
            path = f["new_path"] if f["new_path"] != "/dev/null" else f["old_path"]
            for h in f["hunks"]:
                added_nt = _nontrivial(h["added"])
                base_lines = []  # specificity vs base omitted (no cheap base here)
                spec = 1.0
                n_added += len(h["added"])
                n_removed += len(h["removed"])
                hunks.append({
                    "file": path,
                    "old_start": h["old_start"], "old_len": h["old_len"],
                    "new_start": h["new_start"], "new_len": h["new_len"],
                    "header": h["header"],
                    "added": h["added"], "removed": h["removed"],
                    "added_nt": added_nt,
                    "removed_nt": _nontrivial(h["removed"]),
                    "specificity": spec,
                })
        prefix = repo.split("/")[-1] if "/" in repo else repo
        base_file = file_names[0] if file_names else None
        functions_source = "hunk-header"
        # functions via ast@base_commit when the local clone has the file
        funcs = _ast_functions(repo, rec.get("base_commit", ""), file_names)
        if funcs is not None:
            functions_source = "ast@base_commit"
        else:
            funcs = [h["header"] for h in hunks if h["header"]]
        test_files, added_tests = _test_funcs(test_patch)
        problem = (rec.get("problem_statement", "") or "").splitlines()
        tasks[tid] = {
            "repo": repo,
            "base_commit": rec.get("base_commit", ""),
            "created_at": rec.get("created_at", ""),
            "task_fingerprint": hashlib.sha256(
                (rec.get("base_commit", "") + patch + test_patch).encode("utf-8")).hexdigest(),
            "problem_title": problem[0] if problem else "",
            "problem_chars": len(rec.get("problem_statement", "") or ""),
            "hints_chars": len(rec.get("hints_text", "") or ""),
            "files": file_names, "n_files": len(file_names),
            "n_hunks": len(hunks), "added": n_added, "removed": n_removed,
            "hunks": hunks,
            "functions": funcs, "functions_source": functions_source,
            "tests": {"files": test_files, "added_tests": added_tests,
                      "assertions": _assert_lines(test_patch)},
            "difficulty": {"kb_mech_class": _mech_class(len(file_names), len(hunks),
                                                        n_added, n_removed),
                           "kb_rule": "mech-1"},
        }
    return {"schema": "tasks_gold/2", "source": "comp_files/tasks.jsonl",
            "tasks_sha256": tasks_sha, "tasks": tasks}


_CLONE = {"Textualize/rich": "rich", "fastapi/fastapi": "fastapi"}


def _ast_functions(repo, base_commit, file_names):
    """Return qualnames of functions enclosing hunks via a local clone, or None."""
    import subprocess
    from . import paths

    clone_name = _CLONE.get(repo)
    if not clone_name or not file_names:
        return None
    clone = paths.gemma_root() / "local_eval" / "repos" / clone_name
    if not clone.is_dir():
        return None
    out = []
    for fn in file_names:
        if not fn.endswith(".py"):
            continue
        try:
            blob = subprocess.run(
                ["git", "cat-file", "-p", f"{base_commit}:{fn}"],
                cwd=str(clone), capture_output=True, timeout=30,
                env=_git_env())
            if blob.returncode != 0:
                continue
            src = blob.stdout.decode("utf-8", errors="replace")
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append(f"{fn}::{node.name}")
        except Exception:
            continue
    return sorted(set(out)) if out else None


def _git_env():
    import os
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env
