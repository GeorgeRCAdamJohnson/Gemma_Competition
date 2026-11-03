"""Build agent_ctrl_e4b_verify: ca5 (0.20 live-best prompt) + a one-call VERIFY-FIX skill + a
reserved-back-half verify->repair loop.

RATIONALE (grounded in the log):
- 46 of 52 E4B misses on reachable tasks were WRONG PATCHES SUBMITTED UNTESTED (outside-review 6).
  The fix is structural: edit -> verify -> (repair once) -> submit, not more prompt wording.
- User's cap insight (L16854/L16944 cap-15 null): 64/67 E4B solves used <=15 calls, so localize+edit
  fits in ~13. That leaves the back half of a 28-call budget for ONE cheap verify->repair cycle.
- The earlier `run_skill_script` cost problem (one test ~7-10 calls) is attacked by making verify a
  SINGLE call that does everything deterministically: py_compile the edited file + find and run the
  ONE most-relevant existing test for the edited module, print a terse PASS/FAIL + first failure line.
  So verify costs 1 tool call, not a multi-call probe the model drives.

WHAT IS HELD CONSTANT vs agent_ctrl_e4b (ca5): model, sampling, the entire localization+edit+contract
prose. The ONLY additions are: the verify-fix skill, two prompt sections (reserve-and-verify), and
`skills:` in agent.yaml. eval_config cap stays 28 (the back half is the reserve).

Files written UTF-8 WITHOUT BOM (SKILL.md must start with `---`, no BOM, per the compile probe at L16451).
"""
import shutil
from pathlib import Path

RIG = Path(__file__).resolve().parent
SRC = RIG / "agent_ctrl_e4b"
DST = RIG / "agent_ctrl_e4b_verify"
if DST.exists():
    shutil.rmtree(DST)
(DST / "prompts").mkdir(parents=True)
(DST / "configs").mkdir(parents=True)
(DST / "skills" / "verify-fix" / "scripts").mkdir(parents=True)


def w(rel, text):
    (DST / rel).write_bytes(text.encode("utf-8"))


# --- held constant from ca5 ---
w("configs/sampling.yaml", (SRC / "configs" / "sampling.yaml").read_text(encoding="utf-8"))
w("eval_config.yaml", (SRC / "eval_config.yaml").read_text(encoding="utf-8"))

# --- agent.yaml: ca5 tools + the verify-fix skill (edit_file kept; this is a FIXER, not a testwriter) ---
w("agent.yaml", """name: sibling_conform_agent
model: gemma-4-e4b-it-qat-w4a16-ct
instruction: !include prompts/system.md
tools:
  - run_command
  - read_file
  - edit_file
  - write_file
  - get_status
  - submit_patch
  - get_code_neighbors
  - search_similar_code
  - get_code_subgraph
skills:
  - skills/verify-fix
generate_content_config: !include configs/sampling.yaml
""")

# --- prompt: ca5 verbatim + a VERIFY section inserted before "Hard rules" ---
ca5 = (SRC / "prompts" / "system.md").read_text(encoding="utf-8")

VERIFY_BLOCK = """## VERIFY BEFORE YOU SUBMIT — the one new rule that converts wrong patches
Most losses are a patch that APPLIED but was WRONG, submitted without ever being run. You have budget to
check. The split is: spend your FIRST ~13 calls to LOCATE and make your edit; RESERVE the remaining calls
for ONE verify->repair cycle before submit.

After your edit lands (patch_size > 0) and BEFORE submit_patch, run the verifier ONCE:
- Call `run_skill_script` with skill_name "verify-fix", file_path "scripts/verify.py",
  positional_args ["<the source file you edited>"].
- It does everything in ONE call: it py_compiles your edited file (catches syntax breaks) and runs the
  single most-relevant EXISTING test for that module, then prints `VERIFY: PASS` or `VERIFY: FAIL`
  followed by the first failing assertion/error line. It never counts as more than one tool call.

Read the result:
- `VERIFY: PASS` -> submit_patch immediately. You are done.
- `VERIFY: FAIL <reason>` -> you have ONE repair. The reason names the exact failure. Re-read the span,
  fix the deviation the reason points to with ONE edit_file, then submit_patch (do NOT verify twice —
  the second verify is not worth the call; one repair then submit).
- `VERIFY: NO_TEST` -> there is no existing test for this module; submit your best patch as-is.

Do NOT skip verify when you have >=7 calls remaining after the edit. Do NOT verify if you are already in
the danger zone (tool_calls_remaining <= 7) — in that regime bank the edit and submit, per COMMIT-BY-REMAINING.

"""

marker = "## Hard rules"
assert marker in ca5, "ca5 prompt shape changed; update the insert marker"
new_prompt = ca5.replace(marker, VERIFY_BLOCK + marker, 1)
w("prompts/system.md", new_prompt)

# --- SKILL.md (no BOM; starts with ---) ---
w("skills/verify-fix/SKILL.md", """---
name: verify-fix
description: Compiles the edited source file and runs the single most-relevant existing test for that module, printing VERIFY PASS or FAIL with the first failure line. One call, deterministic, no LLM.
---
Run `scripts/verify.py <source_file_path>` (path relative to the repository root, e.g. rich/table.py).
It py_compiles the file and runs the one existing test file that imports that module, then prints
`VERIFY: PASS`, `VERIFY: FAIL <first failure line>`, or `VERIFY: NO_TEST`.
""")

# --- the verify script: deterministic, single call, picks the narrowest relevant existing test ---
w("skills/verify-fix/scripts/verify.py", r'''"""verify-fix: compile the edited module + run its ONE most-relevant existing test. Terse PASS/FAIL.

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


def main():
    if len(sys.argv) < 2:
        print("VERIFY: NO_TEST (usage: verify.py <source_file_path>)")
        return
    rel = sys.argv[1].strip().lstrip("/")
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
''')
print("built", DST)
