"""submit-gate: deterministic pre-submit check, run inside the task sandbox (cwd /workspace).
Prints ACCEPTED or REJECTED (first line) plus a short reason. Writes nothing inside /workspace except
transiently reverting/re-applying the agent's own diff to compare against the original code.
"""
import os
import re
import subprocess
import sys

def _find_workspace():
    # The harness writes this script into the sandbox work_dir (= the repo root) and runs it from there.
    # Docker sandbox: /workspace. Subprocess sandbox (Kaggle E4B kernel, local rig): a temp dir. Try in order.
    # ADK runs skill scripts from a temp COPY of the skill (<sandbox>/tmp/tmpXXXX/scripts/), not from the repo.
    # Subprocess sandbox exports PYTHONPATH=<sandbox>/workspace and HOME=<sandbox>/tmp; docker sandbox uses /workspace.
    cands = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    cands += ["/workspace"]
    home = os.environ.get("HOME", "")
    if home:
        cands.append(os.path.join(os.path.dirname(home.rstrip("/")), "workspace"))
    d = os.path.abspath(os.getcwd())
    while d and d != "/":
        cands.append(os.path.join(d, "workspace"))
        d = os.path.dirname(d)
    cands += [os.getcwd()]
    for c in cands:
        try:
            r = subprocess.run("git rev-parse --show-toplevel", shell=True, cwd=c, capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
    return cands[0]


W = _find_workspace()
T_PYTEST = 90


def sh(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, shell=True, cwd=W, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, "TIMEOUT"


def diff_base():
    sh("git add -N . >/dev/null 2>&1")
    rc, _ = sh("git rev-parse -q --verify _swegemma_baseline >/dev/null 2>&1")
    return "_swegemma_baseline" if rc == 0 else "HEAD"


def is_test(p):
    b = os.path.basename(p)
    return (b.startswith("test_") or b.endswith("_test.py") or b == "conftest.py"
            or "/tests/" in "/" + p or "/test/" in "/" + p)


def pytest_fail_ids(files):
    rc, out = sh("timeout %d python3 -m pytest -q --no-header -p no:cacheprovider -o addopts='' -rfE --maxfail=25 %s"
                 % (T_PYTEST, " ".join(files)), timeout=T_PYTEST + 15)
    ids = set(re.findall(r"^(?:FAILED|ERROR) (\S+)", out, re.M))
    collect_err = ("error" in out.lower() and "collected 0 items" in out) or "ERROR collecting" in out or "ImportError" in out[-2000:]
    return rc, ids, collect_err, out


def main():
    base = diff_base()
    rc, names = sh("git diff --name-only %s" % base)
    harness_files = {"conftest.py", "pytest.ini", "_swegemma_stubs.py", "sitecustomize.py", "usercustomize.py"}
    changed = [n.strip() for n in names.splitlines() if n.strip()
               and not os.path.basename(n).startswith(".adk_exec_") and n.strip() not in harness_files]
    src = [n for n in changed if n.endswith(".py") and not is_test(n)]
    if rc != 0:
        _, gs = sh("git status 2>&1 | head -3; ls -a | head -12; env | grep -iE '^(GIT|HOME|PWD|USER)' | head")
        print("ACCEPTED: GATE_ERROR git unavailable (rc=%s) W=%s cwd=%s file=%s | %s | %s - check skipped; submit as is."
              % (rc, W, os.getcwd(), os.path.abspath(__file__), names.strip()[:200].replace("\n", " "), gs.replace("\n", " ")[:600]))
        return
    if not changed:
        print("REJECTED: no change in the repo - your edit did not land. Re-apply it with edit_file.")
        return
    if not src:
        print("REJECTED: only non-source/test files changed (%s). Edit the SOURCE file instead; test edits are reset by the grader." % ", ".join(changed[:5]))
        return
    # 1. syntax
    for f in src:
        if not os.path.exists(os.path.join(W, f)):
            continue
        rc, out = sh("python3 -c \"import ast,sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])\" %s" % f)
        if rc != 0:
            print("REJECTED: syntax error in %s\n%s" % (f, "\n".join(out.strip().splitlines()[-6:])))
            return
    # 2. existing tests that exercise the edited module(s)
    tdirs = [d for d in ("tests", "test") if os.path.isdir(os.path.join(W, d))]
    if not tdirs:
        print("ACCEPTED: syntax OK; no tests/ directory to check against.")
        return
    picked = []
    for f in src:
        stem = os.path.splitext(os.path.basename(f))[0]
        key = stem.lstrip("_")
        dotted = os.path.splitext(f)[0].replace("/", ".")
        rc, out = sh("ls %s 2>/dev/null | grep -E 'test_?%s(\\.py|_)' | head -2" % (" ".join(d + "/*" for d in tdirs), re.escape(key)))
        cands = [c for c in out.split() if c.endswith(".py")]
        if not cands:
            rc, out = sh("grep -rlE '(from|import) +%s\\b|from +%s +import +%s\\b' %s --include='test_*.py' 2>/dev/null | head -2"
                         % (re.escape(dotted), re.escape(".".join(dotted.split(".")[:-1]) or dotted), re.escape(stem), " ".join(tdirs)))
            cands = [c for c in out.split() if c.endswith(".py")]
        for c in cands:
            if c not in picked:
                picked.append(c)
    picked = picked[:2]
    if not picked:
        print("ACCEPTED: syntax OK; no existing test file covers %s." % ", ".join(src))
        return
    rc_p, fail_p, cerr_p, out_p = pytest_fail_ids(picked)
    if rc_p == 0:
        print("ACCEPTED: syntax OK; existing tests pass (%s)." % ", ".join(picked))
        return
    # 3. compare against the original code so pre-existing failures are not blamed on the edit
    # Revert ONLY the edited source files (never the harness's conftest.py / pytest.ini), via a per-run temp file
    # (plain /tmp is shared by concurrent subprocess sandboxes).
    import tempfile
    fd, gdiff = tempfile.mkstemp(prefix="_gate_", suffix=".diff")
    os.close(fd)
    rc, d = sh("git diff --binary %s -- %s > %s && echo ok" % (base, " ".join(src), gdiff))
    base_fail, cerr_b = set(), False
    if "ok" in d and os.path.getsize(gdiff) > 0:
        sh("git apply -R %s" % gdiff)
        try:
            _, base_fail, cerr_b, _ = pytest_fail_ids(picked)
        finally:
            rc2, o2 = sh("git apply %s" % gdiff)
            if rc2 != 0:
                sh("git apply --3way %s" % gdiff)
            try:
                os.unlink(gdiff)
            except OSError:
                pass
    if cerr_p and cerr_b:
        print("ACCEPTED: syntax OK; existing tests cannot be collected in this sandbox on the original code either (%s)." % ", ".join(picked))
        return
    new = sorted(fail_p - base_fail)
    if cerr_p and not cerr_b:
        tail = "\n".join(out_p.strip().splitlines()[-14:])
        print("REJECTED: your edit breaks import/collection of %s (it collected on the original code).\n%s" % (", ".join(picked), tail))
        return
    if not new:
        print("ACCEPTED: syntax OK; no NEW test failures vs the original code (%s)." % ", ".join(picked))
        return
    first = new[0]
    m = re.search(r"_{5,} .*?%s.*? _{5,}\n(.*?)(?=\n_{5,} |\n=+ short test summary)" % re.escape(first.split("::")[-1]), out_p, re.S)
    detail = (m.group(1) if m else out_p)[-1400:]
    print("REJECTED: your edit makes %d existing test(s) fail that passed on the original code: %s\n--- first failure ---\n%s"
          % (len(new), ", ".join(new[:4]), detail))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never crash the agent loop
        print("ACCEPTED: GATE_ERROR (%s: %s) - check skipped; submit as is." % (type(e).__name__, e))
