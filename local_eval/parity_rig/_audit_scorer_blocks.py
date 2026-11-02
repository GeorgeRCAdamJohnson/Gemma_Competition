"""Audit all 129 tasks for scorer-blocking patterns (the rich_3486 class + siblings).

Classes (all evaluated against the REAL harness code, py3.13 semantics = Dockerfile.public):
  A1 required-always-skipped : a required node's own test is skip-dead on py>=3.13/linux
                               (FAIL_TO_PASS absent -> extracted from test_patch, or listed
                               but dead)
  A2 skipped-prefix-collision : a skip-DEAD test S prefix-matches (req_base + '_') a REQUIRED
                               node R -> has_non_pass fires (the rich_3486 mechanism)
  B  async-tests-vs-ini      : test_patch adds `async def test_` AND the repo's own
                               pytest.ini/setup.cfg declares asyncio_mode=auto (harness
                               overwrites the ini -> collection of async tests breaks)
  C  non-test-py-targets     : test_patch adds .py files under tests/ that are NOT test_*.py
                               (harness treats every test_patch .py as a pytest target)
  D  anyio-fixture-users     : test_patch (or its tests) reference anyio_backend /
                               pytest.mark.anyio fixtures (the -p no:anyio killer)
Run INSIDE the rig container (PYTHONPATH=/x) so _extract_test_functions_from_patch is real.
"""
import json
import os
import re
import sys

sys.path.insert(0, "/x")
from swegemma.harness.verification import (  # noqa: E402
    _extract_test_functions_from_patch,
    _node_matches_requirement,
)

TASKS = "/data/tasks.jsonl"
REPOS = "/repos"  # local clones mounted for the asyncio_mode check

SKIP_DEAD_TRUE_PATTERNS = [
    # conditions that evaluate TRUE on py3.13/linux -> test skips
    (re.compile(r"sys\.version_info\.minor\s*>=\s*(\d+)"), lambda m: int(m.group(1)) <= 13),
    (re.compile(r"sys\.version_info\s*>=\s*\(?3,\s*(\d+)"), lambda m: int(m.group(1)) <= 13),
    (re.compile(r"platform\.system\(\)\s*==\s*['\"]Windows"), lambda m: True),
    (re.compile(r"sys\.platform\s*==\s*['\"]win32"), lambda m: True),
    (re.compile(r"sys\.platform\.startswith\(\s*['\"]win"), lambda m: True),
    (re.compile(r"platform\.python_implementation\(\)\s*!=\s*['\"]CPython"), lambda m: False),
]


def skip_decorator_for(func_src_block: str):
    return func_src_block


def dead_on_our_python(skipif_arg: str) -> bool:
    """True if the skipif condition is TRUE on py3.13 linux (=> test always skipped)."""
    for pat, fn in SKIP_DEAD_TRUE_PATTERNS:
        m = pat.search(skipif_arg)
        if m and fn(m):
            return True
    # skipif with plain False / True
    if skipif_arg.strip().startswith("False"):
        return False
    if skipif_arg.strip().startswith("True"):
        return True
    return False  # unparseable -> assume alive (conservative)


def added_test_defs(test_patch: str):
    """Return {name: skip_dead?} for tests ADDED by the test_patch (lines starting +)."""
    added = [l[1:] for l in test_patch.splitlines() if l.startswith("+") and not l.startswith("+++")]
    src = "\n".join(added)
    out = {}
    # split on decorators+def blocks
    for m in re.finditer(
        r"((?:@[^\n]*\n)*)(?:async\s+)?def\s+(test_\w+)\s*\(", src
    ):
        decorators, name = m.group(1), m.group(2)
        dead = False
        sm = re.search(r"skipif\((.*?)\)\s*\n", decorators, re.S)
        if sm:
            dead = dead_on_our_python(sm.group(1))
        out[name] = dead
    return out, src


def main():
    repo_async_cfg = {}  # repo -> has asyncio_mode=auto somewhere in original config

    rows = []
    for l in open(TASKS, encoding="utf-8"):
        if not l.strip():
            continue
        t = json.loads(l)
        tid = t["instance_id"]
        tp = t.get("test_patch", "") or ""
        f2p_raw = t.get("FAIL_TO_PASS") or t.get("fail_to_pass") or ()
        if isinstance(f2p_raw, str):
            try:
                f2p = tuple(json.loads(f2p_raw))
            except Exception:
                f2p = tuple(x.strip() for x in f2p_raw.split(",") if x.strip())
        else:
            f2p = tuple(f2p_raw)

        tests, added_src = added_test_defs(tp)
        # required nodes, using the REAL harness derivation
        if f2p:
            required = list(f2p)
        else:
            required = list(_extract_test_functions_from_patch(tp))

        cls = set()

        # A1: required node itself is skip-dead
        for req in required:
            short = req.split("::")[-1].split("[")[0]
            if tests.get(short) is True:
                cls.add("A1_required_always_skipped")

        # A2: skip-dead sibling prefix-matches a required node (rich_3486 mechanism)
        for req in required:
            req_short = req.split("::")[-1]
            req_base = req_short.split("[", 1)[0]
            for sname, sdead in tests.items():
                if sdead and sname != short and _node_matches_requirement(
                    sname, req, req_short, req_base
                ):
                    cls.add("A2_skipped_prefix_collision")

        # B: async tests added AND repo wants asyncio_mode=auto (ini overwritten by harness)
        if re.search(r"\+\s*(?:async\s+def\s+test_)", tp) or re.search(
            r"^\+\s*async\s+def\s+test_", added_src, re.M
        ):
            repo = t.get("repo", "")
            if repo not in repo_async_cfg:
                repo_async_cfg[repo] = None  # resolved lazily below
            cls.add("B_async_tests_added")

        # C: non-test .py added under tests/
        for m in re.finditer(r"^\+\+\+ b/(\S+)", tp, re.M):
            p = m.group(1)
            if re.match(r"(tests|test)/", p) and p.endswith(".py"):
                base = p.rsplit("/", 1)[-1]
                if not (base.startswith("test_") or base.endswith("_test.py") or base == "conftest.py"):
                    cls.add("C_nontest_py_target")

        # D: anyio fixture users in ADDED test code
        if re.search(r"anyio_backend|pytest\.mark\.anyio|from anyio import", added_src):
            cls.add("D_anyio_fixture_user")

        if cls:
            rows.append((tid, sorted(cls)))

    # B refinement: check whether the repo's OWN config declares asyncio_mode (local clones)
    import glob as _g
    for repo_field in {t.split("/")[1] for (t, _) in rows
                       if "B_async_tests_added" in dict(rows).get(t, [])} if False else []:
        pass
    # simpler: use local repos
    repo_mode = {}
    for repo_name in ("fastapi", "requests", "rich", "httpx"):
        root = f"{REPOS}/{repo_name}"
        found = False
        for cfg in ("pytest.ini", "setup.cfg", "tox.ini", "pyproject.toml", "conftest.py"):
            p = f"{root}/{cfg}"
            if os.path.exists(p):
                try:
                    txt = open(p, encoding="utf-8", errors="replace").read()
                    if "asyncio_mode" in txt or "anyio_mode" in txt:
                        found = True
                except Exception:
                    pass
        repo_mode[repo_name] = found

    # filter B to repos that actually rely on asyncio/anyio mode
    final = []
    for tid, cls in rows:
        repo = tid.split("_")[0]
        if "B_async_tests_added" in cls and not repo_mode.get(repo, False):
            cls = [c for c in cls if c != "B_async_tests_added"]
        if cls:
            final.append((tid, cls))

    counts = {}
    for tid, cls in final:
        for c in cls:
            counts[c] = counts.get(c, 0) + 1
    print("=== 129-TASK SCORER-BLOCKER AUDIT (real harness code, py3.13) ===")
    for k in sorted(counts):
        print("  %-34s %d tasks" % (k, counts[k]))
    blocked = {t for t, _ in final}
    print("  %-34s %d / 129" % ("ANY structural class", len(blocked)))
    print("repo asyncio_mode/anyio_mode in original config:", repo_mode)

    # overlap with never-solved (use the saved union from earlier if present; else just print list)
    print()
    for tid, cls in sorted(final):
        print("  %-18s %s" % (tid, ",".join(cls)))


if __name__ == "__main__":
    main()
