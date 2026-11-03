"""Unit-test the pure logic of verify-fix/scripts/verify.py against a synthetic repo tree.

No docker, no snapshots, no GPU. Validates:
  - find_test_file: exact-name, prefix, and import-fallback selection + NO_TEST when nothing maps.
  - first_failure_line: picks the informative line out of pytest-shaped output.
The live py_compile + pytest path still needs the GPU-machine rig; this just proves the selection/parse
logic is correct so a wrong test isn't chosen on the real run.
"""
import importlib.util
import os
import tempfile
from pathlib import Path

VERIFY = Path(__file__).resolve().parent / "agent_ctrl_e4b_verify" / "skills" / "verify-fix" / "scripts" / "verify.py"

# verify.py runs find_workspace() at import (git rev-parse walking up the real FS), which hangs on this
# laptop's repo tree. Load the SOURCE without executing the module-level discovery by stubbing the call.
import types
src = VERIFY.read_text(encoding="utf-8")
vm = types.ModuleType("verify_mod")
vm.__dict__["__file__"] = str(VERIFY)
# define a no-op find_workspace BEFORE exec so the top-level `W = find_workspace()` is instant
exec(compile(src.replace("W = find_workspace()", "W = os.getcwd()"), str(VERIFY), "exec"), vm.__dict__)

fails = []


def mktree(root, files):
    for rel, content in files.items():
        p = Path(root) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")


def run_case(name, files, source_rel, expect):
    """Point verify's W at a temp repo and check find_test_file(source_rel)."""
    with tempfile.TemporaryDirectory() as d:
        mktree(d, files)
        vm.W = d  # override the module's workspace root
        got = vm.find_test_file(source_rel)
        got_norm = None if got is None else got.replace("\\", "/")
        ok = got_norm == expect
        print(f"  [{'ok' if ok else 'XX'}] {name}: got={got_norm!r} expect={expect!r}")
        if not ok:
            fails.append(name)


print("=== find_test_file ===")
run_case("exact name match",
         {"rich/table.py": "x=1\n", "tests/test_table.py": "import rich.table\n"},
         "rich/table.py", "tests/test_table.py")

run_case("prefix match (test_<stem>_extra.py)",
         {"rich/markdown.py": "x=1\n", "tests/test_markdown_render.py": "from rich.markdown import X\n"},
         "rich/markdown.py", "tests/test_markdown_render.py")

run_case("leading-underscore stem strips to match",
         {"rich/_null_file.py": "x=1\n", "tests/test_null_file.py": "import rich\n"},
         "rich/_null_file.py", "tests/test_null_file.py")

# import-fallback uses shell `grep` (present in the Linux docker rig, absent on this Windows host).
# On Windows grep is missing -> returns None; on Linux -> the test file. Accept both so the harness
# path (Linux) is asserted where grep exists, and the laptop run doesn't false-fail.
import shutil as _sh
_grep = _sh.which("grep") is not None
run_case("import fallback when no name match",
         {"fastapi/sse.py": "x=1\n",
          "tests/test_streaming.py": "from fastapi.sse import ServerSentEvent\n"},
         "fastapi/sse.py", "tests/test_streaming.py" if _grep else None)

run_case("no test maps -> None (NO_TEST)",
         {"rich/obscure.py": "x=1\n", "tests/test_other.py": "import something_else\n"},
         "rich/obscure.py", None)

print("=== first_failure_line ===")
cases = [
    ("assertion", "    def test_x():\nE       assert 1 == 2\n1 failed", "E       assert 1 == 2"),
    ("error type", "E   ValueError: bad thing\n", "E   ValueError: bad thing"),
    ("summary FAILED", "....\nFAILED tests/test_a.py::test_b - AssertionError\n", "FAILED tests/test_a.py::test_b - AssertionError"),
]
for name, inp, expect in cases:
    got = vm.first_failure_line(inp)
    ok = expect in got or got == expect
    print(f"  [{'ok' if ok else 'XX'}] {name}: got={got!r}")
    if not ok:
        fails.append("ffl:" + name)

print("=" * 60)
if fails:
    print("RESULT: FAIL ->", fails)
    raise SystemExit(1)
print("RESULT: verify.py logic OK")
