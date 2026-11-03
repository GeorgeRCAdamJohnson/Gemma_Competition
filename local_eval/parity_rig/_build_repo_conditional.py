"""Build agent_ctrl_e4b_repocond: ca5 + REPO-CONDITIONAL strategy (rich vs fastapi).

The model sees the repo name in line 1 of the task prompt ("...for repository Textualize/rich" /
"fastapi/fastapi"), so it CAN branch on it (verified in agent_runner.build_agent_prompt). This is the
repo-conditional TEXT lever (distinct from the refuted routing-AGENT).

Rich = high-redundancy -> sibling-mirror / smallest-diff works (proved: rich_4077 converted).
FastAPI = low-redundancy, contract-synthesis -> sibling-mirror is the WRONG instinct; the fix is not
sitting in a neighbor. For fastapi, steer to EXACT-CONTRACT matching (messages/types/variants) and do
NOT force a sibling shape.

Arm C in the 3-arm FastAPI-vs-Rich experiment (A=plain ca5, B=global sibling, C=this).
"""
import shutil
from pathlib import Path

RIG = Path(__file__).resolve().parent
SRC = RIG / "agent_ctrl_e4b"   # plain ca5, no skill
DST = RIG / "agent_ctrl_e4b_repocond"
if DST.exists():
    shutil.rmtree(DST)
shutil.copytree(SRC, DST)
for pc in DST.rglob("__pycache__"):
    shutil.rmtree(pc, ignore_errors=True)

pt = (DST / "prompts" / "system.md").read_text(encoding="utf-8")

REPO_COND = """## CHOOSE YOUR STRATEGY BY REPOSITORY (the task prompt names the repo on its first line)
Read the repository name. The right fix STYLE differs by repo:

- If the repo is **Textualize/rich**: it is a highly-patterned codebase. MIRROR THE ADJACENT SIBLING —
  the method/branch directly above or below the one you change. Give your fix the SAME shape: DELEGATE
  like the neighbor (if `fileno()` is `return self.__file.fileno()`, the isatty fix is
  `return self.__file.isatty()`), do NOT reconstruct via a lower-level API. Make the SMALLEST diff —
  prefer ADDING a guard or one line over REPLACING a working line; if you replaced a working line you
  likely regressed a passing test, so restore it and add the minimal change.

- If the repo is **fastapi/fastapi** (or requests/httpx): the fix is usually NOT sitting in an adjacent
  sibling — do NOT force a sibling shape. Instead match the EXACT CONTRACT the problem describes: the
  precise error/validation message wording, the exact type, the status code, and EVERY input variant
  and field the problem names. Change only what the contract requires; keep the diff minimal and do not
  rewrite working lines. When you add an import, put it on its OWN new line (never splice it into an
  existing import line).

"""

marker = "## Strategy: conform to the pattern"
assert marker in pt, "ca5 conform section not found"
pt = pt.replace(marker, REPO_COND + marker, 1)
(DST / "prompts" / "system.md").write_bytes(pt.encode("utf-8"))

assert "skills:" not in (DST / "agent.yaml").read_text(encoding="utf-8")
print("built", DST, "| prompt bytes", len((DST / 'prompts' / 'system.md').read_bytes()))
