"""Ablation builder: ca5 + selected DDV blocks.
MODE=def     -> definition-site rule only  (tests knowledge without the paralysis trigger)
MODE=verify  -> verify rule only          (tests whether VERIFY alone causes the edit collapse)
Both modes pass a banned-token leak audit."""
import hashlib
import os
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
SRC = RIG / "agent_ctrl_v5"
CA5_SHA = "b08b32a2438d"
BANNED = ("TextIOBase", "isatty", "__file", "FileProxy", "RawIOBase", "fileno")
MODE = os.environ.get("MODE", "def")
DST = RIG / ("agent_ctrl_ddv3" if MODE == "def" else "agent_ctrl_ddv4")

DEF_SITE = """## FIX THE DEFINITION, NOT THE CALLER
When a value is wrong, find the code that DEFINES it, not the code that uses it. Editing a call site is the most common wasted run: the caller often looks guilty, but the value is created elsewhere and your patch changes nothing.
- **Inherited base-class methods shadow composition.** If a class derives from a stdlib base (`dict`, `list`, `MutableMapping`, the `io` base classes, `str`, `Exception`...), that base may ALREADY define the exact member in question, returning a concrete default. Attribute lookup finds the inherited member FIRST, so a `__getattr__`/`__getattribute__` forwarder is never reached and NO edit to a caller can change the value. Override the member IN THE DERIVED CLASS.
- **A wrapper must FORWARD.** If a class composes another object (it stores one as an attribute and pretends to be it), the correct body delegates to that object. NEVER hardcode a constant such as `return True`, `return False`, `return None`, `return 0` - a hidden test usually supplies a collaborator whose behaviour is the OPPOSITE of the default, so a literal always fails.
Locating this costs 1-2 greps, not 10. Decide, edit, and keep the commit-under-budget rule above.

"""

VERIFY = """## VERIFY THE EDIT - at most ONE call, and only with budget to spare
An unchecked patch is a guess. If - and only if - you still have more than 6 tool calls left after editing, spend exactly ONE `run_command` building the object with a collaborator that behaves differently from the default and asserting the contract. If it fails, fix once and move on.
If you have 6 or fewer calls, SKIP verification and submit: an unverified patch scores; an unmade patch is a guaranteed 0. A 1-line `python3 -c` assert is enough - this is NOT the banned "bare pytest".

"""


def main():
    src = (SRC / "prompts" / "system.md").read_text(encoding="utf-8")
    assert hashlib.sha1(src.encode()).hexdigest()[:12] == CA5_SHA, "source is not ca5"
    md = src
    a1 = "## Match the EXACT contract the problem describes"
    a2 = "## Hard rules"
    if MODE == "def":
        md = md.replace(a1, DEF_SITE + a1, 1)
    else:
        md = md.replace(a2, VERIFY + a2, 1)

    leaks = [b for b in BANNED if re.search(re.escape(b), md, re.I)]
    assert not leaks, f"LEAK: {leaks}"

    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)
    (DST / "prompts" / "system.md").write_text(md, encoding="utf-8")
    yml = (DST / "agent.yaml").read_text(encoding="utf-8").replace(
        "gemma-4-31b-it-qat-w4a16-ct", "gemma-4-12b-it-qat-w4a16-ct")
    (DST / "agent.yaml").write_text(yml, encoding="utf-8")

    print(f"MODE={MODE} -> {DST.name} sha={hashlib.sha1(md.encode()).hexdigest()[:12]} "
          f"({len(src)} -> {len(md)} chars) leak=CLEAN "
          f"has_def={'FIX THE DEFINITION' in md} has_verify={'VERIFY THE EDIT' in md}")


if __name__ == "__main__":
    main()
