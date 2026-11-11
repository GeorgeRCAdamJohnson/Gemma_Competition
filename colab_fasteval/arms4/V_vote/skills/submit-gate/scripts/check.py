"""submit-gate: deterministic pre-submit check, run inside the task sandbox (cwd /workspace).
Prints ACCEPTED or REJECTED (first line) plus a short reason. Writes nothing inside /workspace except
transiently reverting/re-applying the agent's own diff to compare against the original code.
"""
import hashlib
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


_ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def _purge_pyc():
    subprocess.run("find . -path ./.git -prune -o -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null",
                   shell=True, cwd=W, capture_output=True, timeout=60)


def sh(cmd, timeout=60):
    if "pytest" in cmd or "repro_issue" in cmd:
        _purge_pyc()
    try:
        r = subprocess.run(cmd, shell=True, cwd=W, capture_output=True, text=True, timeout=timeout, env=_ENV)
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


MAX_ATTEMPTS = 3

REPRO = False
REPRO_NAME = "repro_issue.py"


def _state_dir():
    import tempfile
    d = os.path.join(os.environ.get("HOME") or tempfile.gettempdir(), ".submit_gate")
    os.makedirs(d, exist_ok=True)
    return d


def _relocate_repro():
    """Move the tester's script out of the workspace so it never lands in the patch."""
    import shutil
    src = os.path.join(W, REPRO_NAME)
    dst = os.path.join(_state_dir(), REPRO_NAME)
    if os.path.exists(src):
        if not os.path.exists(dst):
            shutil.move(src, dst)
        else:
            os.unlink(src)
    return dst if os.path.exists(dst) else None


def _run_repro(path):
    rc, out = sh("timeout 60 python3 %s" % path, timeout=75)
    return out


def _repro_verdict():
    """Returns (valid, resolved, tail) or None when no repro script exists."""
    import json
    import tempfile
    path = _relocate_repro()
    if not path:
        return None
    sp = os.path.join(_state_dir(), "repro.json")
    st = json.load(open(sp)) if os.path.exists(sp) else {}
    base = diff_base()
    src = _src_files(base)
    if "base_out" not in st:
        fd, g = tempfile.mkstemp(prefix="_repro_", suffix=".diff")
        os.close(fd)
        reverted = False
        if src:
            sh("git diff --binary %s -- %s > %s" % (base, " ".join(src), g))
            if os.path.getsize(g) > 0:
                sh("git apply -R %s" % g)
                reverted = True
        try:
            st["base_out"] = _run_repro(path)[-1500:]
        finally:
            if reverted:
                rc2, _ = sh("git apply %s" % g)
                if rc2 != 0:
                    sh("git apply --3way %s" % g)
            try:
                os.unlink(g)
            except OSError:
                pass
        json.dump(st, open(sp, "w"))
    b = st["base_out"]
    valid = ("Issue reproduced" in b) and ("Issue resolved" not in b) and ("Other issues" not in b)
    if not valid:
        return (False, False, b[-300:])
    p = _run_repro(path)
    return (True, "Issue resolved" in p, p[-700:])


def _src_files(base):
    harness_files = {"conftest.py", "pytest.ini", "_swegemma_stubs.py", "sitecustomize.py", "usercustomize.py"}
    _, names = sh("git diff --name-only %s" % base)
    return [n.strip() for n in names.splitlines() if n.strip().endswith(".py") and not is_test(n.strip())
            and n.strip() not in harness_files and not os.path.basename(n).startswith(".adk_exec_")]


def _score(msg):
    # lower is better: how bad was this attempt
    if "REPRO_FAIL" in msg:
        m = re.search(r"makes (\d+) existing test", msg)
        return 50 + (int(m.group(1)) if m else 0)
    if msg.startswith("ACCEPTED"):
        return 0
    m = re.search(r"makes (\d+) existing test", msg)
    if m:
        return int(m.group(1))
    if "breaks import/collection" in msg:
        return 500
    if "syntax error" in msg:
        return 900
    return 1000  # no source change


def _norm_diff(path):
    """Comparable form of an attempt: changed file names + added/removed lines with ALL whitespace removed."""
    try:
        t = open(path, errors="replace").read()
    except OSError:
        return ""
    keep = []
    for ln in t.splitlines():
        if ln.startswith("+++ ") or ln.startswith("--- "):
            keep.append(ln[:4] + ln[4:].strip())
        elif (ln.startswith("+") or ln.startswith("-")) and not ln.startswith(("+++", "---")):
            s = re.sub(r"\s+", "", ln[1:])
            if s:
                keep.append(ln[0] + s)
    return "\n".join(keep)


def _finalize(msg):
    import json
    import tempfile
    state_dir = os.path.join(os.environ.get("HOME") or tempfile.gettempdir(), ".submit_gate")
    os.makedirs(state_dir, exist_ok=True)
    sp = os.path.join(state_dir, "state.json")
    st = json.load(open(sp)) if os.path.exists(sp) else {"n": 0, "attempts": []}
    base = diff_base()
    src = _src_files(base)
    st["n"] += 1
    n = st["n"]
    dpath = os.path.join(state_dir, "attempt_%d.diff" % n)
    if src:
        sh("git diff --binary %s -- %s > %s" % (base, " ".join(src), dpath))
    else:
        open(dpath, "w").close()
    st["attempts"].append({"n": n, "score": _score(msg), "diff": dpath, "size": os.path.getsize(dpath)})
    json.dump(st, open(sp, "w"))
    head = msg.split("\n", 1)[0]
    rest = msg.split("\n", 1)[1] if "\n" in msg else ""
    if msg.startswith("ACCEPTED"):
        st["attempts"][-1]["norm"] = hashlib.sha1(_norm_diff(dpath).encode()).hexdigest() if os.path.getsize(dpath) > 0 else ""
        json.dump(st, open(sp, "w"))
        acc = [a for a in st["attempts"] if a.get("norm")]
        cur = st["attempts"][-1].get("norm")
        agree = [a for a in acc if a["norm"] == cur]
        if cur and len(agree) >= 2:
            print("%s\nVOTE: %d independent attempts made the SAME change. Call submit_patch now." % (msg, len(agree)))
            return
        if n < MAX_ATTEMPTS:
            if src and os.path.getsize(dpath) > 0:
                rcu, _ = sh("git apply -R %s" % dpath)
                if rcu != 0:
                    sh("git checkout %s -- %s" % (base, " ".join(src)))
            print("%s (attempt %d of %d)\nCONFIRM: this fix passed the checks. It has been UNDONE so a SECOND independent attempt can confirm it.\nReply RETRY (no tool calls). The fixer will solve the task again from scratch."
                  % (head, n, MAX_ATTEMPTS))
            return
        # last attempt accepted but no agreement: keep the most frequent accepted diff (tie -> earliest)
        cnt = {}
        for a in acc:
            cnt[a["norm"]] = cnt.get(a["norm"], 0) + 1
        best = min(acc, key=lambda a: (-cnt[a["norm"]], a["n"]))
        if best["n"] != n:
            if src and os.path.getsize(dpath) > 0:
                sh("git apply -R %s" % dpath)
            sh("git apply %s || git apply --3way %s" % (best["diff"], best["diff"]))
        print("%s\nVOTE: no two attempts agreed; restored accepted attempt #%d. Call submit_patch now." % (msg, best["n"]))
        return
    if n < MAX_ATTEMPTS:
        if src and os.path.getsize(dpath) > 0:
            sh("git apply -R %s" % dpath)  # undo this attempt: files back to the original text
        print("%s (attempt %d of %d)\n%s\nThe edit has been UNDONE: the source files are back to their ORIGINAL text.\n"
              "Reply RETRY (no tool calls). The fixer will make a fresh attempt with a different approach."
              % (head, n, MAX_ATTEMPTS, rest))
        return
    # out of attempts: put back the best attempt (lowest score, prefer non-empty)
    cands = [a for a in st["attempts"] if a["size"] > 0] or st["attempts"]
    best = min(cands, key=lambda a: (a["score"], a["n"]))  # ties -> EARLIEST attempt
    if src and os.path.getsize(dpath) > 0:
        sh("git apply -R %s" % dpath)
    if best["size"] > 0:
        sh("git apply %s || git apply --3way %s" % (best["diff"], best["diff"]))
    print("%s (attempt %d of %d - no attempts left)\nRestored the best attempt so far (#%d, score %d). Call submit_patch now."
          % (head, n, MAX_ATTEMPTS, best["n"], best["score"]))


if __name__ == "__main__":
    import contextlib
    import io
    buf = io.StringIO()
    try:
        if REPRO:
            try:
                _relocate_repro()  # before anything diffs the workspace
            except Exception:
                pass
        with contextlib.redirect_stdout(buf):
            main()
        msg = buf.getvalue().strip() or "REJECTED: gate produced no verdict"
        if REPRO and (msg.startswith("ACCEPTED") or "existing test(s) fail" in msg) and "GATE_ERROR" not in msg:
            try:
                rv = _repro_verdict()
            except Exception as e:
                rv = None
                msg += "\n(repro check skipped: %s)" % type(e).__name__
            if rv and rv[0] and not rv[1]:
                head = "REJECTED: REPRO_FAIL your fix does not make the reproduction test print 'Issue resolved'"
                if msg.startswith("REJECTED"):
                    head += "; also " + msg.split("\n", 1)[0][len("REJECTED: "):]
                msg = head + ".\n--- reproduction output on your fix ---\n" + rv[2]
            elif rv and rv[0] and rv[1] and msg.startswith("ACCEPTED"):
                msg = msg + " Reproduction test now prints 'Issue resolved'."
        _finalize(msg)
    except Exception as e:  # never crash the agent loop
        print("ACCEPTED: GATE_ERROR (%s: %s) - check skipped.\nCall submit_patch now." % (type(e).__name__, e))
