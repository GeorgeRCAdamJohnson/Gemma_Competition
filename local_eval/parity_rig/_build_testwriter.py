"""Build agent_ctrl_e4b_testwriter: measures E4B's good_test_rate (Konwinski-style F2P reproduction tests).

Single LlmAgent. It locates the code, calls the `test-context` skill (deterministic: signatures of the source module
+ imports / test names / one example test from the matching existing test file), writes `repro_issue.py` at the repo
root in the Konwinski print format, runs it once on the ORIGINAL code, fixes it at most once if it errors, then submits.
It never edits source. The repro file lands in the captured patch, which is how the offline scorer recovers it.
Files written UTF-8 without BOM.
"""
import shutil
from pathlib import Path

RIG = Path(__file__).resolve().parent
SRC = RIG / "agent_ctrl_e4b"
DST = RIG / "agent_ctrl_e4b_testwriter"
if DST.exists():
    shutil.rmtree(DST)
(DST / "prompts").mkdir(parents=True)
(DST / "configs").mkdir(parents=True)
(DST / "skills" / "test-context" / "scripts").mkdir(parents=True)


def w(rel, text):
    (DST / rel).write_bytes(text.encode("utf-8"))


w("configs/sampling.yaml", (SRC / "configs" / "sampling.yaml").read_text(encoding="utf-8"))
w("eval_config.yaml", (SRC / "eval_config.yaml").read_text(encoding="utf-8"))

w("agent.yaml", """name: test_writer
model: gemma-4-e4b-it-qat-w4a16-ct
instruction: !include prompts/system.md
tools:
  - run_command
  - read_file
  - write_file
  - get_status
  - submit_patch
skills:
  - skills/test-context
generate_content_config: !include configs/sampling.yaml
""")

w("prompts/system.md", """You are a test engineer. Your ONLY job: write ONE standalone script `repro_issue.py` that reproduces the problem described in the task. You do NOT fix the bug and you NEVER edit source files.

Budget: ~28 tool calls / 8 minutes. Use about 10.

Steps:
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

   The assert must check the behaviour the problem says SHOULD happen after the fix (exact values, messages, types). On the current buggy code it must print `Issue reproduced`.
4. Run it once: `run_command` with `python3 repro_issue.py`.
   - Prints `Issue reproduced` -> go to step 5.
   - Prints `Other issues` or raises (ImportError, NameError, TypeError in your setup) -> fix the SCRIPT once with `write_file`, run it again, then go to step 5 whatever it prints.
   - Prints `Issue resolved` on the unfixed code -> your assert does not capture the bug: rewrite the assert once, run again, then step 5.
5. Call `submit_patch`, then reply with one sentence. Do not call any more tools.

Rules: never modify files other than `repro_issue.py`. No network. Keep thinking short.
""")

w("skills/test-context/SKILL.md", """---
name: test-context
description: Prints the classes/functions of a source module and how existing tests import and use them, to help write a correct reproduction script.
---
Run `scripts/context.py <source_file_path>` (path relative to the repository root, e.g. rich/table.py).
""")

w("skills/test-context/scripts/context.py", r'''"""test-context: deterministic context for writing a reproduction test (no LLM). Prints <= ~5 KB."""
import ast
import os
import re
import subprocess
import sys


def find_workspace():
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


W = find_workspace()


def sigs(path, limit=60):
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except Exception as e:
        return ["  (could not parse: %s)" % e]
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append("  def %s(%s)  # line %d" % (node.name, ast.unparse(node.args)[:120], node.lineno))
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)[:80]
            out.append("  class %s(%s)  # line %d" % (node.name, bases, node.lineno))
            for b in node.body:
                if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append("      def %s(%s)" % (b.name, ast.unparse(b.args)[:110]))
        if len(out) >= limit:
            out.append("  ...")
            break
    return out


def main():
    if len(sys.argv) < 2:
        print("usage: context.py <source_file_path>")
        return
    rel = sys.argv[1].strip().lstrip("/")
    if rel.startswith("workspace/"):
        rel = rel[len("workspace/"):]
    src = os.path.join(W, rel)
    if not os.path.exists(src):
        print("not found: %s (paths are relative to the repo root)" % rel)
        return
    dotted = os.path.splitext(rel)[0].replace("/", ".")
    print("== import path for %s:\n  import %s   /   from %s import <name>" % (rel, dotted, dotted))
    print("== classes/functions in %s:" % rel)
    print("\n".join(sigs(src)))
    stem = os.path.splitext(os.path.basename(rel))[0].lstrip("_")
    tests = []
    for d in ("tests", "test"):
        td = os.path.join(W, d)
        if os.path.isdir(td):
            for f in sorted(os.listdir(td)):
                if f.endswith(".py") and re.search(r"test_?%s(\.py|_)" % re.escape(stem), f):
                    tests.append(os.path.join(d, f))
    if not tests:
        r = subprocess.run("grep -rlE '(from|import) +%s\\b' tests test --include='test_*.py' 2>/dev/null | head -2" % re.escape(dotted),
                           shell=True, cwd=W, capture_output=True, text=True)
        tests = [t for t in r.stdout.split() if t]
    if not tests:
        print("== no existing test file found for %s" % rel)
        return
    t = tests[0]
    text = open(os.path.join(W, t), encoding="utf-8", errors="replace").read()
    imports = [l for l in text.splitlines() if re.match(r"^(from|import) ", l)][:25]
    print("== existing test file %s - its imports (copy this style):" % t)
    print("\n".join("  " + l for l in imports))
    names = re.findall(r"^def (test_\w+)", text, re.M)
    print("== %d tests in it, e.g.: %s" % (len(names), ", ".join(names[:12])))
    m = re.search(r"^def test_\w+\(.*?(?=^def |\Z)", text, re.M | re.S)
    if m:
        body = "\n".join(m.group(0).rstrip().splitlines()[:30])
        print("== example test from %s:\n%s" % (t, body))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("test-context error: %s: %s" % (type(e).__name__, e))
''')
print("built", DST)
