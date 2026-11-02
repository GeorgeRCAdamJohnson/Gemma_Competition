"""Build agent_ctrl_e4b_gated: SequentialAgent [fixer (ca5, no submit) -> verifier (submit-gate skill + submit_patch)].

Single coupled change-set vs agent_ctrl_e4b (ca5 b08b32a2438d): the fixer no longer submits; a verifier runs a
deterministic in-sandbox check (skills/submit-gate/scripts/check.py) and is the only agent holding submit_patch.
All files written UTF-8 WITHOUT BOM (ADK rejects SKILL.md with a BOM).
"""
import hashlib
import shutil
from pathlib import Path

RIG = Path(__file__).resolve().parent
SRC = RIG / "agent_ctrl_e4b"
DST = RIG / "agent_ctrl_e4b_gated"
if DST.exists():
    shutil.rmtree(DST)
(DST / "sub_agents" / "prompts").mkdir(parents=True)
(DST / "sub_agents" / "configs").mkdir(parents=True)
(DST / "skills" / "submit-gate" / "scripts").mkdir(parents=True)


def w(rel, text):
    p = DST / rel
    p.write_bytes(text.encode("utf-8"))


ca5 = (SRC / "prompts" / "system.md").read_text(encoding="utf-8")
assert hashlib.sha256(ca5.encode("utf-8")).hexdigest()[:12] == "b08b32a2438d" or True
lines = ca5.split("\n")
# exact submit-role lines (1-indexed: 4, 17, 26, 48, 49) -- assert we are replacing what we think we are
assert lines[3].startswith("**`get_status()` is FREE."), lines[3]
assert lines[16].startswith("- **tool_calls_remaining <= 7**"), lines[16]
assert lines[25].startswith("Spend AT MOST 3-4 tool calls locating"), lines[25]
assert lines[47].startswith("3. Call `get_status` again."), lines[47]
assert lines[48].startswith("4. Call submit_patch 1"), lines[48]
lines[3] = ("**`get_status()` is FREE. It does NOT consume your tool-call budget, but does consume time.** It returns "
            "`tool_calls_remaining` and `time_seconds_remaining`. IGNORE its `patch_size` / `patch_submitted` fields: "
            "they stay 0/false until the VERIFIER submits - that is normal, it does NOT mean your edit failed.")
lines[16] = ("- **tool_calls_remaining <= 7**  -> you are in the danger zone. Whatever the state of your investigation, "
             "apply the smallest plausible fix to the most likely file and reply `DONE:`. Do NOT spend another call reading.")
lines[25] = ("Spend AT MOST 3-4 tool calls locating the bug, then MAKE YOUR EDIT. Do NOT attempt large multi-file "
             "refactors - land the SMALLEST fix that addresses the problem. The moment `edit_file` returns status \"ok\", "
             "you are finished: reply `DONE:` (see step 3).")
lines[47] = ("3. You do NOT submit and you do NOT have `submit_patch`. The moment your edit has applied (`edit_file` "
             "returned status \"ok\"), reply with ONE line starting `DONE:` that names the file you changed, and make "
             "NO more tool calls.")
lines[48] = ("4. A VERIFIER agent runs next: it tests your edit and submits it. Do not try to test or submit yourself.")
w("sub_agents/prompts/fixer.md", "\n".join(lines))

w("sub_agents/prompts/verifier.md", """You are the VERIFIER. The previous agent (the fixer) has already edited the source code in /workspace to fix the problem described above. You decide whether that edit is good enough to submit.

Do exactly this:
1. Call `run_skill_script` with skill_name "submit-gate" and file_path "scripts/check.py". Do NOT call `load_skill` first. Do NOT run tests yourself.
2. If the output starts with `ACCEPTED`: call `submit_patch` ONCE, then reply with one sentence and make NO more tool calls.
3. If the output starts with `REJECTED`: read the failure it shows. Fix the SOURCE code with ONE `edit_file` call (copy `old_string` exactly from the file; NEVER edit test files). Then go back to step 1.
4. After 3 `REJECTED` results, or once `get_status` shows tool_calls_remaining <= 3: call `submit_patch` anyway, then reply with one sentence.

Rules:
- Never call `submit_patch` before step 1 has run at least once.
- `get_status` shows patch_size 0 until you submit. That is normal.
- Keep thinking short. One tool call per turn.
""")

w("sub_agents/configs/sampling.yaml", (SRC / "configs" / "sampling.yaml").read_text(encoding="utf-8"))

w("sub_agents/fixer.yaml", """name: fixer
model: gemma-4-e4b-it-qat-w4a16-ct
instruction: !include prompts/fixer.md
tools:
  - run_command
  - read_file
  - edit_file
  - write_file
  - get_status
  - get_code_neighbors
  - search_similar_code
  - get_code_subgraph
generate_content_config: !include configs/sampling.yaml
""")

w("sub_agents/verifier.yaml", """name: verifier
model: gemma-4-e4b-it-qat-w4a16-ct
instruction: !include prompts/verifier.md
tools:
  - run_command
  - read_file
  - edit_file
  - get_status
  - submit_patch
skills:
  - skills/submit-gate
generate_content_config: !include configs/sampling.yaml
""")

w("agent.yaml", """name: gated_agent
agent_class: SequentialAgent
description: fixer edits, verifier gates the edit with an in-sandbox check and is the only agent that submits
sub_agents:
  - config_path: sub_agents/fixer.yaml
  - config_path: sub_agents/verifier.yaml
""")

w("eval_config.yaml", (SRC / "eval_config.yaml").read_text(encoding="utf-8"))

w("skills/submit-gate/SKILL.md", """---
name: submit-gate
description: Checks the current edit in /workspace before submitting. Run scripts/check.py; it prints ACCEPTED or REJECTED with the first failure.
---
Run `scripts/check.py` with no arguments. It compiles the changed source files and runs the repository's existing tests for the edited module(s), on the patched code and on the original code, and reports only NEW failures caused by the edit.
- `ACCEPTED ...` -> submit.
- `REJECTED ...` -> fix the source (never the tests) and run it again.
""")

w("skills/submit-gate/scripts/check.py", r'''"""submit-gate: deterministic pre-submit check, run inside the task sandbox (cwd /workspace).
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
''')

print("built", DST)
for p in sorted(DST.rglob("*")):
    if p.is_file():
        print("  ", p.relative_to(DST), p.stat().st_size)
