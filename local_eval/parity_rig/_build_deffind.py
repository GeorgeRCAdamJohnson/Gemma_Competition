"""Build agent_ctrl_e4b_deffind: ca5 + a DETERMINISTIC definition-finder skill.

Targets the measured E4B reference-vs-definition failure (L14680): the agent greps the issue symbol, finds
a CALL SITE, edits there, never opens the DEFINITION file. The prior fix was a PROMPT rule (grep def/class)
-> 2/7, obeyed ~25% of the time. This replaces the rule with a SKILL the agent calls ONCE: it greps
`def <symbol>` / `class <symbol>` across the repo and returns the DEFINING file(s), so localization is
deterministic, not model-remembered. Ceiling (measured): the 4 LOC-only targets rich_4077, rich_3067,
rich_3480, fastapi_14492.

Prompt change (minimal, additive): after reading the problem, call find-def on the key symbol BEFORE
grepping/editing; edit in the file it returns. One skill call, early. edit_file kept as the editor.
Files UTF-8, no BOM; argv handles the ADK '--' separator.
"""
import shutil
from pathlib import Path

RIG = Path(__file__).resolve().parent
SRC = RIG / "agent_ctrl_e4b"
DST = RIG / "agent_ctrl_e4b_deffind"
if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)
for pc in DST.rglob("__pycache__"):
    shutil.rmtree(pc, ignore_errors=True)
(DST / "skills" / "find-def" / "scripts").mkdir(parents=True, exist_ok=True)


def w(rel, text):
    (DST / rel).write_bytes(text.encode("utf-8"))


# agent.yaml: add the skill
ay = (DST / "agent.yaml").read_text(encoding="utf-8")
assert "skills:" not in ay
ay = ay.replace("generate_content_config:", "skills:\n  - skills/find-def\ngenerate_content_config:")
w("agent.yaml", ay)

# prompt: insert a definition-first step before the existing localization/anchor guidance
pt = (DST / "prompts" / "system.md").read_text(encoding="utf-8")
BLOCK = """## FIND THE DEFINITION FIRST (this is where the fix goes, not where the symbol is mentioned)
The bug is almost always in the file that DEFINES the relevant class/function, not a file that merely
calls or imports it. Grepping the issue's words finds CALL SITES and stops you in the wrong file.
So, as your FIRST locating action: pick the key symbol named in the problem (a class, function, or method
name), and call `run_skill_script` with skill_name "find-def", file_path "scripts/find_def.py",
positional_args ["<Symbol>"]. It greps `def <Symbol>` / `class <Symbol>` across the repo and prints the
file(s) where that symbol is DEFINED. Open the defining file it returns and make your edit THERE.
- If it returns one file, that is your target; read it and edit.
- If it returns several, pick the one whose module matches the problem's topic.
- If it returns none (symbol not found as a def/class), fall back to your normal grep — the symbol may be
  a local variable or the name differs; do not loop on find-def.
Do this ONCE, early. Then follow the anchor/edit rules below in the file it gave you.

"""
# place it right before the existing "## Match the EXACT contract" or the workflow; anchor on a stable header
for marker in ("## Strategy: conform to the pattern", "## Match the EXACT contract", "## Workflow"):
    if marker in pt:
        pt = pt.replace(marker, BLOCK + marker, 1)
        break
else:
    raise SystemExit("no stable insert marker found in ca5 prompt")
w("prompts/system.md", pt)

# SKILL.md (no BOM, starts with ---)
w("skills/find-def/SKILL.md", """---
name: find-def
description: Greps the repo for where a class/function/method symbol is DEFINED (def/class) and prints the defining file(s), so edits land in the definition not a call site.
---
Run `scripts/find_def.py <Symbol>` (a class/function/method name, e.g. FileProxy or isatty).
Prints the file(s) containing `def <Symbol>` or `class <Symbol>`, with the matching line.
""")

w("skills/find-def/scripts/find_def.py", r'''"""find-def: deterministic definition locator. Prints files that DEFINE the given symbol.

One tool call. Greps `def <sym>` / `class <sym>` (and `<sym> =` for module-level assignments / properties)
across the repo source, ranks by definition kind, prints the defining file(s). No LLM, no guessing.
"""
import os
import re
import subprocess
import sys


def find_workspace():
    cands = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p] + ["/workspace"]
    d = os.path.abspath(os.getcwd())
    while d and d != "/":
        cands.append(os.path.join(d, "workspace")); d = os.path.dirname(d)
    for c in cands:
        try:
            r = subprocess.run("git rev-parse --show-toplevel", shell=True, cwd=c,
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
    return os.getcwd()


def argsym():
    for a in sys.argv[1:]:
        a = a.strip()
        if a and a != "--" and not a.startswith("--"):
            return a
    return ""


def main():
    sym = argsym()
    if not sym:
        print("FIND-DEF: no symbol (usage: find_def.py <Symbol>)")
        return
    # strip dotted/paren noise: take the last identifier component
    m = re.search(r"[A-Za-z_]\w*$", sym.split("(")[0].strip().rstrip(":"))
    sym = m.group(0) if m else sym
    W = find_workspace()
    hits = []  # (kind_rank, file, lineno, line)
    patterns = [
        (0, re.compile(r"^\s*class\s+%s\b" % re.escape(sym))),
        (0, re.compile(r"^\s*(async\s+)?def\s+%s\b" % re.escape(sym))),
        (1, re.compile(r"^\s*%s\s*(:\s*[\w\[\], .\"']+)?\s*=" % re.escape(sym))),  # module/class attr
    ]
    for root, dirs, files in os.walk(W):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".tox", "node_modules", "build", "dist")]
        # skip test trees: definitions we want are in the package, not tests
        if os.path.basename(root) in ("tests", "test"):
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            fp = os.path.join(root, fn)
            try:
                lines = open(fp, encoding="utf-8", errors="replace").read().splitlines()
            except Exception:
                continue
            for i, ln in enumerate(lines, 1):
                for rank, pat in patterns:
                    if pat.match(ln):
                        hits.append((rank, os.path.relpath(fp, W).replace(os.sep, "/"), i, ln.strip()[:100]))
                        break
    if not hits:
        print("FIND-DEF: no `def %s` / `class %s` found in the repo. Fall back to normal grep." % (sym, sym))
        return
    hits.sort(key=lambda h: (h[0], len(h[1]), h[1]))
    defs = [h for h in hits if h[0] == 0] or hits
    print("FIND-DEF: `%s` is DEFINED in:" % sym)
    for rank, f, i, ln in defs[:6]:
        print("  %s:%d   %s" % (f, i, ln))
    if len(defs) == 1:
        print("-> edit %s" % defs[0][1])
    else:
        print("-> %d candidates; pick the module matching the problem topic, edit there." % len(defs))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("FIND-DEF: error %s: %s (fall back to grep)" % (type(e).__name__, e))
''')
print("built", DST)
