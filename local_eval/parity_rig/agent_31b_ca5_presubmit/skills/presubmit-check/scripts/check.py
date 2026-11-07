"""presubmit-check: did the edit land, do changed .py files parse, do changed modules import. No tests run."""
import os
import subprocess
import sys

ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
HARNESS = {"conftest.py", "pytest.ini", "_swegemma_stubs.py", "sitecustomize.py", "usercustomize.py"}


def find_ws():
    cands = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p] + ["/workspace"]
    home = os.environ.get("HOME", "")
    if home:
        cands.append(os.path.join(os.path.dirname(home.rstrip("/")), "workspace"))
    d = os.path.abspath(os.getcwd())
    while d and d != "/":
        cands.append(os.path.join(d, "workspace"))
        d = os.path.dirname(d)
    for c in cands:
        try:
            r = subprocess.run("git rev-parse --show-toplevel", shell=True, cwd=c, capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
    return os.getcwd()


W = find_ws()


def sh(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, shell=True, cwd=W, capture_output=True, text=True, timeout=timeout, env=ENV)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def is_test(p):
    b = os.path.basename(p)
    return b.startswith("test_") or b.endswith("_test.py") or b == "conftest.py" or "/tests/" in "/" + p or "/test/" in "/" + p


def main():
    sh("git add -N . >/dev/null 2>&1")
    rc, _ = sh("git rev-parse -q --verify _swegemma_baseline >/dev/null 2>&1")
    base = "_swegemma_baseline" if rc == 0 else "HEAD"
    rc, names = sh("git diff --name-only %s" % base)
    if rc != 0:
        print("OK (check skipped: git unavailable). Go to step 4.")
        return
    changed = [n.strip() for n in names.splitlines() if n.strip() and os.path.basename(n.strip()) not in HARNESS
               and not os.path.basename(n.strip()).startswith(".adk_exec_")]
    src = [n for n in changed if not is_test(n)]
    if not changed:
        print("PROBLEM: your patch is EMPTY - no file in the repo has changed. Your edit did not land. "
              "Re-read the exact lines with sed -n, then apply the change (edit_file; if it reports old_string not "
              "found twice, use the python heredoc replace fallback).")
        return
    if not src:
        print("PROBLEM: you only changed test files (%s). The grader resets tests - edit the SOURCE file." % ", ".join(changed[:4]))
        return
    sh("find . -path ./.git -prune -o -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null")
    py = [f for f in src if f.endswith(".py") and os.path.exists(os.path.join(W, f))]
    for f in py:
        rc, out = sh("python3 -c \"import ast,sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])\" %s" % f)
        if rc != 0:
            print("PROBLEM: syntax error in %s:\n%s" % (f, "\n".join(out.strip().splitlines()[-5:])))
            return
    for f in py:
        mod = f[:-3].replace("/", ".")
        if mod.endswith(".__init__"):
            mod = mod[: -len(".__init__")]
        top = mod.split(".")[0]
        if not os.path.isdir(os.path.join(W, top)) and not os.path.exists(os.path.join(W, top + ".py")):
            continue  # not importable from the repo root (scripts/, docs_src/ ...)
        # read-only: flag an import failure ONLY if the traceback points into a file the agent changed
        # (environment failures - missing optional deps - point elsewhere and are ignored)
        rc, out = sh("timeout 40 python3 -c \"import %s\"" % mod, timeout=50)
        if rc != 0 and any(("/" + c) in out or ('"' + c) in out for c in py):
            print("PROBLEM: importing %s fails inside a file you changed:\n%s"
                  % (mod, "\n".join(out.strip().splitlines()[-6:])))
            return
    print("OK: edit landed in %s; changed files parse and import. Go to step 4 (submit_patch)." % ", ".join(src[:4]))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("OK (check error %s: %s). Go to step 4." % (type(e).__name__, e))
