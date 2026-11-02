"""Build ca5-DELIT: ca5 with every LITERAL SHELL EXAMPLE rewritten as prose.

Evidence (GEMMA_EXPERIMENT_LOG L~1060, our own replay measurement):
  literal shell examples in the prompt -> 30/96 (31%) MALFORMED TOOL NAMES
  same commands described in PROSE bound to run_command -> 5/96 (5%)
A malformed call (e.g. `call:grep -rn...`) is not parsed: it stays in content,
triggers the token-limit nudge, and 3 nudges end the session.

This is a REPLACEMENT (no added rules), so it carries no action tax.
Targets the whole pool, not one task -> no task-specific vocabulary.
"""
import hashlib
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
SRC = RIG / "agent_ctrl_v5"
DST = RIG / "agent_ctrl_ca5delit"
CA5_SHA = "b08b32a2438d"

# (old_substring, new_prose) -- each removes a literal shell invocation
REPLACEMENTS = [
    (
        "BEFORE the edit: grep your anchor - run `grep -n -A 20 '<the exact symbol you are about to edit>' <file>` "
        "and confirm the problem's symbol/behaviour appears INSIDE that span.",
        "BEFORE the edit, SEARCH for your anchor: use `run_command` with a grep pattern matching the exact symbol "
        "you are about to edit, requesting line numbers and about twenty lines of trailing context in that file, "
        "and confirm the problem's symbol/behaviour appears INSIDE the returned span.",
    ),
    (
        "NOTE on reading a span: use `run_command` with `sed -n 'A,Bp' <file>` \u2014 that reliably returns the exact "
        "lines you asked for.",
        "NOTE on reading a span: use `run_command` with sed in quiet mode, printing only the line range you want "
        "\u2014 that reliably returns the exact lines.",
    ),
    (
        "Scratch/repro files go to /tmp via run_command heredoc `cat > /tmp/x.py <<'EOF'`.",
        "Scratch/repro files go under /tmp, written with `run_command` using a heredoc.",
    ),
    (
        "Pattern (1 run_command call): start a `python3` heredoc; set p = pathlib.Path to the source file; "
        "s = p.read_text(); set OLD to the exact current text; set NEW to the replacement; assert OLD in s; "
        "p.write_text(s.replace(OLD, NEW, 1)); print OK; end the heredoc.",
        "Pattern (1 run_command call): run a Python heredoc; set p = pathlib.Path to the source file; "
        "s = p.read_text(); set OLD to the exact current text; set NEW to the replacement; assert OLD in s; "
        "p.write_text(s.replace(OLD, NEW, 1)); print OK; end the heredoc.",
    ),
    (
        "Do NOT run bare pytest (it times out) - if you test, run ONLY the 1 target test.",
        "Do NOT invoke the repository's whole test suite (it times out) - if you test, run ONLY the 1 target test.",
    ),
]

SHELL_PAT = re.compile(r"`(?:grep|sed|cat|awk|find|python3?\s)[^`]*`")


def main():
    src = (SRC / "prompts" / "system.md").read_text(encoding="utf-8")
    assert hashlib.sha1(src.encode()).hexdigest()[:12] == CA5_SHA, "source is not ca5"
    before_shell = SHELL_PAT.findall(src)

    md = src
    applied = 0
    for old, new in REPLACEMENTS:
        assert old in md, f"anchor not found: {old[:70]!r}"
        md = md.replace(old, new, 1)
        applied += 1

    after_shell = SHELL_PAT.findall(md)
    print(f"replacements applied: {applied}/{len(REPLACEMENTS)}")
    print(f"literal shell examples: {len(before_shell)} -> {len(after_shell)}")
    for s in before_shell:
        print(f"  BEFORE: {s[:90]}")
    for s in after_shell:
        print(f"  AFTER : {s[:90]}")
    print(f"chars: {len(src)} -> {len(md)}  (delta {len(md)-len(src):+d})")

    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)
    (DST / "prompts" / "system.md").write_text(md, encoding="utf-8")
    yml = (DST / "agent.yaml").read_text(encoding="utf-8")
    assert "gemma-4-31b-it-qat-w4a16-ct" in yml
    print(f"built {DST.name} sha={hashlib.sha1(md.encode()).hexdigest()[:12]}")


if __name__ == "__main__":
    main()
