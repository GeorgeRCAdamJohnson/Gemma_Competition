"""Build agent_ctrl_ddv = ca5 prompt + DDV rules (Definition-site, Delegation, Verify).
Single-variable vs agent_ctrl_12b under IDENTICAL caps (45 tools / 15 min).
Never modifies agent_ctrl_v5 (frozen ca5, sha b08b32a2438d)."""
import hashlib
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
SRC = RIG / "agent_ctrl_v5"
DST = RIG / "agent_ctrl_ddv"

CA5_SHA = "b08b32a2438d"

DEF_SITE = """## DEFINE IT WHERE IT IS DEFINED - inherited values cannot be fixed at the call site
When a value is wrong, ask "which code DEFINES this value?" - NOT "which code uses it". Call sites are seductive and editing them never works. Two traps that cost real runs:
- **Inherited stdlib methods mask delegation.** A class subclassing `io.TextIOBase`, `io.RawIOBase`, `dict`, `list`, or `MutableMapping` INHERITS a concrete method that already returns the wrong value (e.g. `io.TextIOBase.isatty()` returns False). Attribute lookup finds that inherited method FIRST, so a `__getattr__` forwarder is never reached and editing the CALLER is irrelevant. Override the method IN THE SUBCLASS.
- **A proxy/wrapper must DELEGATE.** If the class wraps another object (`self.__file`, `self._impl`, `self.obj`), the correct body forwards: `return self.__file.isatty()`. NEVER hardcode `return True` / `return False` / any constant - the hidden test builds a stub whose method returns the OPPOSITE value, so a literal always fails.

"""

VERIFY = """## VERIFY THE EDIT - one call, before you submit
A patch you have not checked is a guess, and guesses in this suite score 0. After your edit, in ONE `run_command`:
- instantiate the object with a stub that returns a DIFFERENT value from the default (e.g. a fake file whose `isatty()` returns True), then assert the behaviour the problem describes;
- if the assertion fails, your fix is WRONG: re-read the definition site and edit again. Do NOT submit a known-failing patch.
One call converts a guess into a fact. A 1-line `python3 -c` import+assert is enough - this is NOT the banned "bare pytest".

"""


def main():
    src_md = (SRC / "prompts" / "system.md").read_text(encoding="utf-8")
    have = hashlib.sha1(src_md.encode()).hexdigest()[:12]
    assert have == CA5_SHA, f"source prompt is not ca5 (got {have})"
    assert "DEFINE IT WHERE IT IS DEFINED" not in src_md or "rebuilt" in src_md

    md = src_md
    # keep the header EXACTLY as ca5 states it (28 calls / 8 min) so the ONLY delta is the DDV content
    assert "~28 tool calls and 8 minutes" in md, "ca5 header changed - refusing to build a confounded arm"

    # 2) insert the definition-site / delegation rule before the contract section
    anchor = "## Match the EXACT contract the problem describes"
    assert anchor in md
    md = md.replace(anchor, DEF_SITE + anchor, 1)

    # 3) insert the verify rule before Hard rules
    anchor2 = "## Hard rules"
    assert anchor2 in md
    md = md.replace(anchor2, VERIFY + anchor2, 1)

    # 4) keep the "don't run bare pytest" ban but point at the sanctioned check
    md = md.replace(
        "Do NOT run bare pytest (it times out) - if you test, run ONLY the 1 target test.",
        "Do NOT run bare pytest (it times out) - if you test, run ONLY the 1 target test, or better a 1-line `python3 -c` behaviour assert.",
    )

    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)
    (DST / "prompts" / "system.md").write_text(md, encoding="utf-8")

    new_sha = hashlib.sha1(md.encode()).hexdigest()[:12]
    print(f"built {DST.name}: ca5={have} -> ddv={new_sha}  ({len(src_md)} -> {len(md)} chars)")
    for marker in ("DEFINE IT WHERE IT IS DEFINED", "VERIFY THE EDIT", "~28 tool calls and 8 minutes"):
        print(f"  contains {marker!r}: {marker in md}")


if __name__ == "__main__":
    main()

