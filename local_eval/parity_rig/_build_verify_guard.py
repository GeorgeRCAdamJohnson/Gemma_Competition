"""Build agent_ctrl_e4b_verify_guard: the verify-fix bundle + a MINIMIZE-DON'T-REWRITE repair guardrail.

WHY (from the null investigation, 2026-11-02):
- rich_3894 OVER-EDITED: gold ADDS a small guard and keeps the line; the agent REPLACED the line, turning
  `def method` into `def Foo.method` and regressing a PASS_TO_PASS. The gold diff is SMALLER than the
  agent's. Lever: on a wrong fix, shrink the diff, don't rewrite.
- rich_4077 RECONSTRUCTED instead of delegating: wrote `os.isatty(self.__file.fileno())` when the sibling
  `fileno()` right above it is literally `return self.__file.fileno()`. The conform-to-sibling fix is
  `return self.__file.isatty()`. Lever: mirror the adjacent sibling method's EXACT shape.
- User note: rich_4077 HAS resolved on E4B before, so it is not intrinsically unsolvable; the loss was a
  specific wrong CHOICE, which a "mirror the sibling / smallest change" rule targets.

This is a PROMPT-ONLY change vs agent_ctrl_e4b_verify (same skill, same caps, same model/sampling).
Clean A/B: verify (repair=free-form) vs verify_guard (repair=minimize+mirror-sibling).
"""
import shutil
from pathlib import Path

RIG = Path(__file__).resolve().parent
SRC = RIG / "agent_ctrl_e4b_verify"
DST = RIG / "agent_ctrl_e4b_verify_guard"
assert SRC.is_dir(), "build agent_ctrl_e4b_verify first (_build_verify.py)"
if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)
# drop any stray pycache
for pc in DST.rglob("__pycache__"):
    shutil.rmtree(pc, ignore_errors=True)


def w(rel, text):
    (DST / rel).write_bytes(text.encode("utf-8"))


# carry sampling/eval/agent/skill verbatim (copytree already did). Only rewrite the FAIL-branch of the
# VERIFY section in the prompt.
pt = (DST / "prompts" / "system.md").read_text(encoding="utf-8")

OLD_FAIL = """- `VERIFY: FAIL <reason>` -> you have ONE repair. The reason names the exact failure. Re-read the span,
  fix the deviation the reason points to with ONE edit_file, then submit_patch (do NOT verify twice —
  the second verify is not worth the call; one repair then submit)."""

NEW_FAIL = """- `VERIFY: FAIL <reason>` -> you have ONE repair. Repair by MINIMIZING, not rewriting:
  1. MIRROR THE SIBLING. Look at the method/branch DIRECTLY ABOVE or BELOW the one you changed. Your fix
     should have the SAME shape as its working sibling. If `fileno()` next to you is `return self.__file.fileno()`,
     then the isatty fix is `return self.__file.isatty()` — delegate to the wrapped object, do NOT
     reconstruct the call a different way (no `os.isatty(...fileno())`, no re-deriving via a lower-level API).
  2. SMALLEST DIFF. The correct fix is almost always SMALLER than what you wrote. Prefer ADDING a guard
     or a single delegating line over REPLACING an existing line. If you replaced a line that used to
     work, you probably regressed it — restore the original and ADD the minimal change instead.
  3. Make that ONE smaller edit_file, then submit_patch. Do NOT verify twice; do NOT enlarge the diff."""

assert OLD_FAIL in pt, "verify FAIL branch not found; prompt shape changed"
pt = pt.replace(OLD_FAIL, NEW_FAIL, 1)
w("prompts/system.md", pt)

print("built", DST)
print("prompt bytes:", len((DST / "prompts" / "system.md").read_bytes()))
