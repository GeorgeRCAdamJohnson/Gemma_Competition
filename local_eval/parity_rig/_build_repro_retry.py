"""Build two E4B LoopAgent bundles from the LF ca5 prompt (sha1 b08b32a2438d), caps 80 calls / 30 min / 200 turns:

  agent_e4b_retry_fresh : LoopAgent(max 3)[fixer, verifier]         gate = existing tests (retry2 design)
  agent_e4b_retry_repro : LoopAgent(max 3)[tester, fixer, verifier] gate = existing tests + the tester's repro test

The two bundles are identical except for the tester sub-agent and the repro block inside check.py (REPRO flag).
Changes vs retry2 (shared by both arms):
  - fixer prompt rebuilt from the LF 31B ca5 bytes (retry2 used the CRLF E4B copy);
  - best-attempt restore breaks score ties toward the EARLIEST attempt (attempt 1 == plain ca5 behaviour), so a
    bad repro test that rejects every attempt degrades to the ungated first attempt, not to a later guess;
  - eval_config 80/30/200 (a test + 3 fresh attempts must fit; the cap itself was measured null today).
Repro gate: the tester writes repro_issue.py at the repo root. On its first run the gate MOVES it out of the
workspace (so it never lands in the patch), runs it on the ORIGINAL code once (cached) and on the patched code.
It only counts if the original run prints "Issue reproduced" (and not "Issue resolved"/"Other issues"); then a
patch that does not print "Issue resolved" is REJECTED with reason REPRO_FAIL (score +50).
Files written UTF-8 without BOM.
"""
import hashlib
import shutil
from pathlib import Path

RIG = Path(__file__).resolve().parent
ROOT = RIG.parents[1]
CA5 = ROOT / "Outputs" / "v7_31b_full129" / "agentcfg" / "agent_ca5"
RETRY2 = RIG / "agent_ctrl_e4b_retry2"
ca5 = (CA5 / "prompts" / "system.md").read_bytes()
assert hashlib.sha1(ca5).hexdigest()[:12] == "b08b32a2438d" and b"\r" not in ca5
SAMPLING = (CA5 / "configs" / "sampling.yaml").read_text(encoding="utf-8")
EVAL = "evaluation:\n  max_time_minutes: 30\n  max_tool_calls: 80\n  max_turns: 200\n  timeout_seconds: 300\n"
MODEL = "gemma-4-e4b-it-qat-w4a16-ct"

# ---------- fixer prompt: same transformation as _build_retry.py, applied to the LF ca5 ----------
lines = ca5.decode("utf-8").split("\n")
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
lines[48] = ("4. A VERIFIER agent runs next: it tests your edit and submits it. Do not try to test or submit yourself.\n"
             "5. RETRY RULE: if the latest message is `RETRY: ...`, a previous attempt was rejected and UNDONE - the "
             "source files are back to their ORIGINAL text. Start fresh from the task below: locate, re-read the exact "
             "span, and make a DIFFERENT fix than the one that failed (the RETRY line names what broke). Then reply "
             "`DONE:` as usual.")
FIXER_MD = ("## THE TASK (always visible to you, also on retries)\n"
            "{problem_description}\n\n{hints?}\n\n---\n\n") + "\n".join(lines)

VERIFIER_MD = (RETRY2 / "sub_agents" / "prompts" / "verifier.md").read_text(encoding="utf-8")
FIXER_YAML = (RETRY2 / "sub_agents" / "fixer.yaml").read_text(encoding="utf-8")
VERIFIER_YAML = (RETRY2 / "sub_agents" / "verifier.yaml").read_text(encoding="utf-8")
GATE_SKILL = (RETRY2 / "skills" / "submit-gate" / "SKILL.md").read_text(encoding="utf-8")
CHECK = (RETRY2 / "skills" / "submit-gate" / "scripts" / "check.py").read_text(encoding="utf-8")
assert "include_contents: none" in FIXER_YAML and MODEL in FIXER_YAML and MODEL in VERIFIER_YAML

# ---------- check.py: shared STALE-BYTECODE fix (found by _test_repro_gate.sh) ----------
# The gate reverts the edit, runs tests, re-applies it within the same second. Python validates .pyc by source
# mtime (1 s) + size, so a same-size edit (`a - b` -> `a + b`) re-uses the ORIGINAL code's bytecode and a correct
# fix is judged as the original. Latent in retry2's existing-test comparison too. Fix: gate subprocesses never
# write bytecode, and every pytest / repro run first purges __pycache__ outside .git.
OLD_SH = '''def sh(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, shell=True, cwd=W, capture_output=True, text=True, timeout=timeout)'''
assert CHECK.count(OLD_SH) == 1
CHECK = CHECK.replace(OLD_SH, '''_ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


def _purge_pyc():
    subprocess.run("find . -path ./.git -prune -o -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null",
                   shell=True, cwd=W, capture_output=True, timeout=60)


def sh(cmd, timeout=60):
    if "pytest" in cmd or "repro_issue" in cmd:
        _purge_pyc()
    try:
        r = subprocess.run(cmd, shell=True, cwd=W, capture_output=True, text=True, timeout=timeout, env=_ENV)''')

# ---------- check.py: shared tie-break change ----------
OLD_TIE = 'best = min(cands, key=lambda a: (a["score"], -a["n"]))'
assert CHECK.count(OLD_TIE) == 1
CHECK = CHECK.replace(OLD_TIE, 'best = min(cands, key=lambda a: (a["score"], a["n"]))  # ties -> EARLIEST attempt')

# ---------- check.py: repro block (REPRO arm only; inert when REPRO = False) ----------
OLD_SCORE = '''def _score(msg):
    # lower is better: how bad was this attempt
    if msg.startswith("ACCEPTED"):'''
assert CHECK.count(OLD_SCORE) == 1
CHECK = CHECK.replace(OLD_SCORE, '''def _score(msg):
    # lower is better: how bad was this attempt
    if "REPRO_FAIL" in msg:
        m = re.search(r"makes (\\d+) existing test", msg)
        return 50 + (int(m.group(1)) if m else 0)
    if msg.startswith("ACCEPTED"):''')

REPRO_FUNCS = r'''
REPRO = __REPRO__
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
'''
OLD_MAIN = '''if __name__ == "__main__":
    import contextlib
    import io
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            main()
        _finalize(buf.getvalue().strip() or "REJECTED: gate produced no verdict")'''
assert CHECK.count(OLD_MAIN) == 1
NEW_MAIN = '''if __name__ == "__main__":
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
                msg += "\\n(repro check skipped: %s)" % type(e).__name__
            if rv and rv[0] and not rv[1]:
                head = "REJECTED: REPRO_FAIL your fix does not make the reproduction test print 'Issue resolved'"
                if msg.startswith("REJECTED"):
                    head += "; also " + msg.split("\\n", 1)[0][len("REJECTED: "):]
                msg = head + ".\\n--- reproduction output on your fix ---\\n" + rv[2]
            elif rv and rv[0] and rv[1] and msg.startswith("ACCEPTED"):
                msg = msg + " Reproduction test now prints 'Issue resolved'."
        _finalize(msg)'''
CHECK = CHECK.replace(OLD_MAIN, NEW_MAIN)
CHECK = CHECK.replace("\nMAX_ATTEMPTS = 3\n", "\nMAX_ATTEMPTS = 3\n" + REPRO_FUNCS, 1)
assert "REPRO = __REPRO__" in CHECK

TESTER_MD = """You are the TESTER. You run FIRST, once. Your ONLY job: write ONE standalone script `repro_issue.py` that reproduces the problem described in the task. You do NOT fix the bug and you NEVER edit source files. Another agent fixes the code after you.

SKIP RULE: if the conversation already contains a message `TESTER DONE`, reply exactly `TESTER DONE` and make NO tool calls.

Use about 10 tool calls.
1. Find the source file the problem is about: 1-2 `run_command` greps for the class/function/error named in the problem.
2. Call `run_skill_script` with skill_name "test-context", file_path "scripts/context.py", positional_args ["<that source file path>"]. It prints the module's classes/functions and how the existing tests import and use them. Use it - do not guess import paths.
3. Write `repro_issue.py` at the repository root with `write_file` (filepath "repro_issue.py"). Use EXACTLY this shape:

```python
<imports - copy the import style shown by test-context>

def test_issue():
    try:
        <set up the objects the problem describes>
        <call the code path the problem describes and capture the result>
    except Exception as e:
        print("Other issues", repr(e))
        return
    try:
        assert <the CORRECT behaviour the problem asks for>
        print("Issue resolved")
    except AssertionError:
        print("Issue reproduced")

test_issue()
```

   Use the REAL package classes/functions - never re-define or mock the code under test. The assert must check the behaviour the problem says SHOULD happen after the fix (exact values, messages, types). On the current buggy code it must print `Issue reproduced`.
4. Run it once: `run_command` with `python3 repro_issue.py`.
   - Prints `Issue reproduced` -> step 5.
   - Prints `Other issues` or raises -> fix the SCRIPT once with `write_file`, run it again, then step 5 whatever it prints.
   - Prints `Issue resolved` on the unfixed code -> your assert misses the bug: rewrite the assert once, run again, then step 5.
5. Reply exactly `TESTER DONE` and make NO more tool calls.

Rules: never modify any file except `repro_issue.py`. You do not have `submit_patch`. No network. Keep thinking short.
"""
TESTER_YAML = f"""name: tester
model: {MODEL}
instruction: !include prompts/tester.md
tools:
  - run_command
  - read_file
  - write_file
  - get_status
skills:
  - ../skills/test-context
generate_content_config: !include configs/sampling.yaml
"""
TC = RIG / "agent_ctrl_e4b_testwriter" / "skills" / "test-context"
TC_SKILL = (TC / "SKILL.md").read_text(encoding="utf-8")
TC_PY = (TC / "scripts" / "context.py").read_text(encoding="utf-8")
# skill path in sub-agent YAMLs: copy the convention the working retry2 verifier uses
VERIFIER_SKILL_LINE = [l for l in VERIFIER_YAML.splitlines() if "submit-gate" in l]
assert len(VERIFIER_SKILL_LINE) == 1
TESTER_YAML = TESTER_YAML.replace("  - ../skills/test-context",
                                  VERIFIER_SKILL_LINE[0].replace("submit-gate", "test-context"))


def build(name, repro):
    dst = RIG / name
    if dst.exists():
        shutil.rmtree(dst)
    files = {
        "eval_config.yaml": EVAL,
        "sub_agents/prompts/fixer.md": FIXER_MD,
        "sub_agents/prompts/verifier.md": VERIFIER_MD,
        "sub_agents/configs/sampling.yaml": SAMPLING,
        "sub_agents/fixer.yaml": FIXER_YAML,
        "sub_agents/verifier.yaml": VERIFIER_YAML,
        "skills/submit-gate/SKILL.md": GATE_SKILL,
        "skills/submit-gate/scripts/check.py": CHECK.replace("__REPRO__", "True" if repro else "False"),
    }
    subs = ["sub_agents/fixer.yaml", "sub_agents/verifier.yaml"]
    if repro:
        files["sub_agents/prompts/tester.md"] = TESTER_MD
        files["sub_agents/tester.yaml"] = TESTER_YAML
        files["skills/test-context/SKILL.md"] = TC_SKILL
        files["skills/test-context/scripts/context.py"] = TC_PY
        subs = ["sub_agents/tester.yaml"] + subs
    desc = ("tester writes a repro test, fixer attempts, gate checks existing tests + repro; on reject the attempt is "
            "undone and the fixer retries fresh (max 3); only the verifier submits" if repro else
            "fixer attempts, gate checks existing tests; on reject the attempt is undone and the fixer retries fresh "
            "(max 3); only the verifier submits")
    files["agent.yaml"] = ("name: %s\nagent_class: LoopAgent\nmax_iterations: 3\ndescription: %s\nsub_agents:\n%s"
                           % (name, desc, "".join("  - config_path: %s\n" % s for s in subs)))
    for rel, text in files.items():
        p = dst / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
    compile(files["skills/submit-gate/scripts/check.py"], "check.py", "exec")
    print("built", dst.name)
    for rel in sorted(files):
        print("   %-40s %6d B" % (rel, len(files[rel].encode())))


build("agent_e4b_retry_fresh", repro=False)
build("agent_e4b_retry_repro", repro=True)
print("fixer.md sha1", hashlib.sha1(FIXER_MD.encode()).hexdigest()[:12], "| tester skill line:",
      [l for l in TESTER_YAML.splitlines() if "test-context" in l])
