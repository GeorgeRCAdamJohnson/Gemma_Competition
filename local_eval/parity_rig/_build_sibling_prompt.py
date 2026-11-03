"""Build agent_ctrl_e4b_sibling: ATTRIBUTION arm. ca5 + the sibling-mirror/smallest-diff rule, NO skill.

WHY: the guardrail win (rich_4077 5/6) came from the PROMPT rule, not the verify skill (verify returned
PASS and caught nothing; the agent produced the gold fix on the FIRST edit by mirroring the sibling). This
arm removes the skill entirely to test whether the prompt rule ALONE gets 5/6. If yes -> ship a pure-prompt
change (no skill-call budget, applies to the hidden-test class verify can't help). If it drops -> the skill
contributed and stays.

The rule is placed as a PRE-EDIT principle (not a verify-FAIL repair branch), because in the guardrail run
it fired correctly on the first edit. No run_skill_script, no skills/ dir, tools = stock ca5.
"""
import shutil
from pathlib import Path

RIG = Path(__file__).resolve().parent
SRC = RIG / "agent_ctrl_e4b"          # stock ca5, NO skill
DST = RIG / "agent_ctrl_e4b_sibling"
if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)
for pc in DST.rglob("__pycache__"):
    shutil.rmtree(pc, ignore_errors=True)

pt = (DST / "prompts" / "system.md").read_text(encoding="utf-8")

# Insert the rule right after the "conform to the pattern" strategy section, strengthening it with the
# concrete delegate-not-reconstruct + smallest-diff guidance the guardrail proved.
SIBLING_RULE = """## MIRROR THE ADJACENT SIBLING — the exact-shape rule (this is what makes the fix correct)
When you add or change a method/branch, look at the method DIRECTLY ABOVE or BELOW it and give your fix
the SAME shape. Most correct fixes are a one-line delegation or a small guard that matches a neighbor:
- DELEGATE, do not reconstruct. If the sibling `fileno()` is `return self.__file.fileno()`, then the
  `isatty` fix is `return self.__file.isatty()` — forward to the wrapped object. Do NOT re-derive it a
  different way (no `os.isatty(...fileno())`, no reaching for a lower-level API the neighbor doesn't use).
- SMALLEST DIFF. The correct fix is almost always SMALLER than your first instinct. Prefer ADDING a guard
  or a single line over REPLACING a working line. If you replace a line that already works, you likely
  regress a passing test — restore it and ADD the minimal change instead.
- Match the neighbor's EXACT attribute/call/return shape; do not substitute a different attribute
  (e.g. do not swap `__name__` for `__qualname__`) unless the problem explicitly requires it.

"""

marker = "## Strategy: conform to the pattern"
assert marker in pt, "ca5 'conform to the pattern' section not found"
# place the sibling rule immediately BEFORE the conform section so it reads as the concrete how-to
pt = pt.replace(marker, SIBLING_RULE + marker, 1)
(DST / "prompts" / "system.md").write_bytes(pt.encode("utf-8"))

# sanity: no skill anywhere
ay = (DST / "agent.yaml").read_text(encoding="utf-8")
assert "skills:" not in ay, "stock ca5 should have no skills; unexpected"
assert not (DST / "skills").exists()
print("built", DST, "| prompt bytes", len((DST / 'prompts' / 'system.md').read_bytes()), "| skill:", (DST/'skills').exists())
