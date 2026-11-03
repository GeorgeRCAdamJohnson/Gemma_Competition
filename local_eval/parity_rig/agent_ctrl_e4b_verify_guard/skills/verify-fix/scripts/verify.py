"""verify-fix: compile the edited module + run its ONE most-relevant existing test. Terse PASS/FAIL.

Design goals (from the log):
- ONE tool call for the whole check (the model does not drive a multi-call probe -> fits the cap).
- NEVER run bare pytest (times out). Target exactly one test file, the one that imports the edited module.
- Resilient: if compile fails -> FAIL fast (the most common wrong-edit is a syntax break).
- If no test file maps to the module -> NO_TEST (the agent then submits as-is; never a false hard-fail).
"""
import ast
import os
import re
import subprocess
import sys


def find_workspace():
    cands = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p] + ["/workspace"]
    d = os.path.abspath(os.getcwd())
    while d and d != "/":
        cands.append(os.path.join(d, "workspace"))
        d = os.path.dirname(d)
    for c in cands:
        try:
            r = subprocess.run("git rev-parse --show-toplevel", shell=True, cwd=c,
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
    return os.getcwd()


W = find_workspace()


def first_failure_line(output):
    """Pull the most informative single line out of pytest output."""
    lines = output.splitlines()
    # Prefer an explicit assertion / error line.
    for pat in (r"^E\s+\w*(Error|Exception|assert)", r"^E\s+assert", r"Error:", r"assert "):
        for l in lines:
            if re.search(pat, l):
                return l.strip()[:200]
    # Fall back to the short-test-summary line.
    for l in lines:
        if l.startswith("FAILED") or l.startswith("ERROR"):
            return l.strip()[:200]
    # Last non-empty line.
    for l in reversed(lines):
        if l.strip():
            return l.strip()[:200]
    return "unknown failure"


def module_dotted(rel):
    return os.path.splitext(rel)[0].replace("/", ".")


def find_test_file(rel):
    """The narrowest existing test for this module: test_<stem>.py by name, else one that imports it."""
    stem = os.path.splitext(os.path.basename(rel))[0].lstrip("_")
    for d in ("tests", "test"):
        td = os.path.join(W, d)
        if os.path.isdir(td):
            # exact name match first
            for f in sorted(os.listdir(td)):
                if f.endswith(".py") and re.fullmatch(r"test_?%s\.py" % re.escape(stem), f):
                    return os.path.join(d, f)
            # then prefix match (test_<stem>_*.py)
            for f in sorted(os.listdir(td)):
                if f.endswith(".py") and re.match(r"test_?%s[_.]" % re.escape(stem), f):
                    return os.path.join(d, f)
    # import-based fallback
    dotted = module_dotted(rel)
    r = subprocess.run(
        "grep -rlE '(from|import) +%s\\b' tests test --include='test_*.py' 2>/dev/null | head -1"
        % re.escape(dotted), shell=True, cwd=W, capture_output=True, text=True)
    t = r.stdout.strip().splitlines()
    return t[0] if t else None


def _argpath():
    """The ADK passes skill positional_args after a '--' separator, so sys.argv can be
    ['verify.py', '--', 'rich/x.py'] (argv[1] == '--'). Take the first non-flag token."""
    for a in sys.argv[1:]:
        a = a.strip()
        if a and a != "--" and not a.startswith("--"):
            return a
    return ""


def main():
    rel = _argpath()
    if not rel:
        print("VERIFY: NO_TEST (no source path received; argv=%r)" % (sys.argv[1:],))
        return
    rel = rel.lstrip("/")
    if rel.startswith("workspace/"):
        rel = rel[len("workspace/"):]
    src = os.path.join(W, rel)
    if not os.path.exists(src):
        print("VERIFY: FAIL edited file not found: %s" % rel)
        return

    # 1) compile the edited file (fast, catches the common syntax-break wrong edit)
    try:
        ast.parse(open(src, encoding="utf-8").read())
    except SyntaxError as e:
        print("VERIFY: FAIL SyntaxError %s line %s" % (e.msg, e.lineno))
        return

    # 2) find and run the ONE most-relevant existing test
    test = find_test_file(rel)
    if not test:
        print("VERIFY: NO_TEST (no existing test file maps to %s; submit your best patch)" % rel)
        return
    cmd = [sys.executable, "-m", "pytest", "-x", "-q", "--no-header", "-p", "no:cacheprovider", test]
    try:
        r = subprocess.run(cmd, cwd=W, capture_output=True, text=True, timeout=110)
    except subprocess.TimeoutExpired:
        print("VERIFY: NO_TEST (test %s timed out; submit your best patch)" % test)
        return
    out = (r.stdout or "") + "\n" + (r.stderr or "")
    # collection error (ModuleNotFoundError etc) -> not a verdict on the fix; don't hard-fail
    if "errors during collection" in out or "ERROR collecting" in out:
        print("VERIFY: NO_TEST (could not collect %s; submit your best patch)" % test)
        return
    if r.returncode == 0:
        print("VERIFY: PASS (%s)" % test)
    else:
        print("VERIFY: FAIL %s | %s" % (test, first_failure_line(out)))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("VERIFY: NO_TEST (verifier error %s: %s; submit your best patch)" % (type(e).__name__, e))
