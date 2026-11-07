"""Build agent_31b_ca5_presubmit = 31B ca5 (LF, sha1 b08b32a2438d, 28/8/120 board caps) + a deterministic
`presubmit-check` skill. ONE prompt change: workflow step 3 is REPLACED (not added to):

  old: 3. Call `get_status` again. If `patch_size` is still 0, you have not actually edited anything - fix that ...
  new: 3. Run the presubmit check (run_skill_script presubmit-check scripts/check.py). PROBLEM -> fix exactly that and
       re-run; OK -> step 4.

check.py (no pytest; ~1-3 s): edit landed (non-empty diff vs baseline, source files only), every changed .py parses,
every changed importable module imports. PYTHONDONTWRITEBYTECODE + __pycache__ purge (stale-bytecode lesson).
Files written UTF-8, LF, no BOM.
"""
import hashlib
import shutil
from pathlib import Path

RIG = Path(__file__).resolve().parent
SRC = RIG.parents[1] / "Outputs" / "v7_31b_full129" / "agentcfg" / "agent_ca5"
DST = RIG / "agent_31b_ca5_presubmit"
sysmd = (SRC / "prompts" / "system.md").read_bytes()
assert hashlib.sha1(sysmd).hexdigest()[:12] == "b08b32a2438d" and b"\r" not in sysmd
text = sysmd.decode("utf-8")
lines = text.split("\n")
assert lines[47].startswith("3. Call `get_status` again."), lines[47]
lines[47] = ("3. Run the presubmit check: call `run_skill_script` with skill_name \"presubmit-check\" and file_path "
             "\"scripts/check.py\" (no arguments). It confirms your edit landed and that every changed file parses and "
             "imports. If it prints `PROBLEM`, fix exactly what it names, then run it again. If it prints `OK`, go to step 4.")
new_sys = "\n".join(lines)

agent = (SRC / "agent.yaml").read_text(encoding="utf-8")
assert "generate_content_config:" in agent and "skills:" not in agent
agent_b = agent.replace("generate_content_config:", "skills:\n  - skills/presubmit-check\ngenerate_content_config:", 1)

SKILL_MD = """---
name: presubmit-check
description: Fast pre-submit sanity check of your edit - did it land, do the changed files parse and import. Run scripts/check.py with no arguments before submit_patch.
---
Run `scripts/check.py` (no arguments). Prints `OK ...` or `PROBLEM: ...` naming the file and line.
"""

CHECK = r'''"""presubmit-check: did the edit land, do changed .py files parse, do changed modules import. No tests run."""
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
'''

if DST.exists():
    shutil.rmtree(DST)
files = {
    "agent.yaml": agent_b,
    "eval_config.yaml": (SRC / "eval_config.yaml").read_text(encoding="utf-8"),
    "configs/sampling.yaml": (SRC / "configs" / "sampling.yaml").read_text(encoding="utf-8"),
    "prompts/system.md": new_sys,
    "skills/presubmit-check/SKILL.md": SKILL_MD,
    "skills/presubmit-check/scripts/check.py": CHECK,
}
for rel, t in files.items():
    p = DST / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(t.encode("utf-8"))
compile(CHECK, "check.py", "exec")
diff = [i for i, (a, b) in enumerate(zip(text.split("\n"), new_sys.split("\n"))) if a != b]
print("built", DST.name, "| prompt lines changed:", diff, "| +chars", len(new_sys) - len(text),
      "| eval:", files["eval_config.yaml"].replace("\n", " "))
