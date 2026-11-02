"""Build agent_ctrl_ddv2 = ca5 + GENERIC DDV rules (no task-specific vocabulary).
The leaky ddv arm named io.TextIOBase.isatty()/self.__file.isatty() = the exact gold patch.
ddv2 keeps the REASONING RULE only, so a win cannot be attributed to answer leakage.
Verified by leak audit: must contain none of the 4077 tokens."""
import hashlib
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
SRC = RIG / "agent_ctrl_v5"
DST = RIG / "agent_ctrl_ddv2"
CA5_SHA = "b08b32a2438d"
BANNED = ("TextIOBase", "isatty", "__file", "FileProxy", "RawIOBase", "fileno")

DEF_SITE = """## FIX THE DEFINITION, NOT THE CALLER
When a value is wrong, find the code that DEFINES it, not the code that uses it. Editing a call site is the most common wasted run: the caller often looks guilty, but the value is created elsewhere and your patch changes nothing.
- **Inherited base-class methods shadow composition.** If a class derives from a stdlib base (`dict`, `list`, `MutableMapping`, the `io` base classes, `str`, `Exception`...), that base may ALREADY define the exact member in question, returning a concrete default. Attribute lookup finds the inherited member FIRST, so a `__getattr__`/`__getattribute__` forwarder is never reached and NO edit to a caller can change the value. Override the member IN THE DERIVED CLASS.
- **A wrapper must FORWARD.** If a class composes another object (it stores one as an attribute and pretends to be it), the correct body delegates to that object. NEVER hardcode a constant such as `return True`, `return False`, `return None`, `return 0` - a hidden test usually supplies a collaborator whose behaviour is the OPPOSITE of the default, so a literal that happens to match the default always fails.

"""

VERIFY = """## VERIFY THE EDIT - one call, before you submit
An unchecked patch is a guess, and a wrong guess scores 0. After editing, in ONE `run_command`:
- build the object with a collaborator that behaves DIFFERENTLY from the built-in default (not the trivial case), then assert the contract the problem describes;
- if the assertion fails, the fix is wrong: re-read the definition site and edit again. Do NOT submit a patch you know fails.
One call turns a guess into a fact. A 1-line `python3 -c` import+assert is enough - this is NOT the banned "bare pytest".

"""


def main():
    src_md = (SRC / "prompts" / "system.md").read_text(encoding="utf-8")
    have = hashlib.sha1(src_md.encode()).hexdigest()[:12]
    assert have == CA5_SHA, f"source is not ca5 (got {have})"
    assert "~28 tool calls and 8 minutes" in src_md

    md = src_md
    a1 = "## Match the EXACT contract the problem describes"
    a2 = "## Hard rules"
    assert a1 in md and a2 in md
    md = md.replace(a1, DEF_SITE + a1, 1)
    md = md.replace(a2, VERIFY + a2, 1)
    md = md.replace(
        "Do NOT run bare pytest (it times out) - if you test, run ONLY the 1 target test.",
        "Do NOT run bare pytest (it times out) - if you test, run ONLY the 1 target test, or better a 1-line `python3 -c` behaviour assert.",
    )

    leaks = [b for b in BANNED if re.search(re.escape(b), md, re.I)]
    assert not leaks, f"LEAK: {leaks}"

    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)
    (DST / "prompts" / "system.md").write_text(md, encoding="utf-8")

    # model must match what vLLM serves
    yml = (DST / "agent.yaml").read_text(encoding="utf-8")
    yml = yml.replace("gemma-4-31b-it-qat-w4a16-ct", "gemma-4-12b-it-qat-w4a16-ct")
    (DST / "agent.yaml").write_text(yml, encoding="utf-8")

    print(f"built {DST.name}: ca5={have} -> ddv2={hashlib.sha1(md.encode()).hexdigest()[:12]} "
          f"({len(src_md)} -> {len(md)} chars)")
    print(f"  leak audit ({len(BANNED)} banned tokens): CLEAN")
    print(f"  header preserved: {'~28 tool calls and 8 minutes' in md}")
    print(f"  model line: {'gemma-4-12b-it-qat-w4a16-ct' in yml}")


if __name__ == "__main__":
    main()
