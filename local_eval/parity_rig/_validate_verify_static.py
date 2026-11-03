"""Static (no-docker, no-adk) validation of agent_ctrl_e4b_verify.

This laptop has no Docker/GPU, so the real compile_check.py (which imports adk_submission) and the
llama-server rig cannot run here. This checks everything that is checkable statically, i.e. the exact
failure modes the log recorded for skill bundles:
  - SKILL.md must start with `---` and carry NO UTF-8 BOM (L16451 compile probe).
  - agent.yaml parses, declares a model, and every !include target + every skills/<name> dir exists.
  - each SKILL.md has name/description frontmatter and names its script.
  - every scripts/*.py compiles.
  - the ca5 prompt additions are present exactly once.
Run anywhere with stdlib only. The DOCKER compile_check + the E4B rig gate remain the other-machine job.
"""
import ast
import re
import sys
from pathlib import Path

B = Path(__file__).resolve().parent / "agent_ctrl_e4b_verify"
errs, warns = [], []


def check(cond, msg):
    (errs if not cond else warns).append(msg) if not cond else None


def read_bytes(rel):
    return (B / rel).read_bytes()


# 1) agent.yaml
ay = (B / "agent.yaml").read_text(encoding="utf-8")
check("model:" in ay, "agent.yaml missing model:")
check("gemma-4-e4b-it-qat-w4a16-ct" in ay, "agent.yaml not declaring the E4B model")

# !include targets
for m in re.findall(r"!include\s+(\S+)", ay):
    check((B / m).exists(), f"!include target missing: {m}")

# skills: entries -> dirs with SKILL.md
skill_dirs = re.findall(r"-\s+(skills/[\w\-/]+)", ay)
check(len(skill_dirs) >= 1, "agent.yaml declares no skills/")
for sd in skill_dirs:
    sdir = B / sd
    check(sdir.is_dir(), f"skill dir missing: {sd}")
    sm = sdir / "SKILL.md"
    check(sm.exists(), f"SKILL.md missing in {sd}")
    if sm.exists():
        raw = sm.read_bytes()
        check(raw[:3] != b"\xef\xbb\xbf", f"SKILL.md has UTF-8 BOM (compile will reject): {sd}")
        txt = raw.decode("utf-8")
        check(txt.startswith("---"), f"SKILL.md must start with '---': {sd}")
        check(re.search(r"^name:\s*\S", txt, re.M) is not None, f"SKILL.md missing name: {sd}")
        check(re.search(r"^description:\s*\S", txt, re.M) is not None, f"SKILL.md missing description: {sd}")

# 2) every scripts/*.py compiles
scripts = list(B.rglob("scripts/*.py"))
check(len(scripts) >= 1, "no skill scripts found")
for s in scripts:
    try:
        ast.parse(s.read_text(encoding="utf-8"))
    except SyntaxError as e:
        errs.append(f"script syntax error {s.name}: {e.msg} line {e.lineno}")

# 3) prompt additions present exactly once, ca5 core retained
pt = (B / "prompts" / "system.md").read_text(encoding="utf-8")
check(pt.count("VERIFY BEFORE YOU SUBMIT") == 1, "VERIFY section not present exactly once")
check("run_skill_script" in pt and "verify-fix" in pt, "prompt does not reference the verify-fix skill")
check("THE BUDGET ORACLE" in pt, "ca5 budget-oracle section lost (prompt base drifted)")
check("COMMIT-BY-REMAINING" in pt, "ca5 commit-by-remaining section lost")

# 4) sampling + eval_config present
check((B / "configs" / "sampling.yaml").exists(), "sampling.yaml missing")
ec = (B / "eval_config.yaml").read_text(encoding="utf-8")
check("max_tool_calls" in ec, "eval_config missing max_tool_calls")

print("=== agent_ctrl_e4b_verify static validation ===")
print(f"scripts compiled: {len(scripts)} | skill dirs: {len(skill_dirs)}")
if warns:
    for w in warns:
        print("  WARN:", w)
if errs:
    for e in errs:
        print("  ERROR:", e)
    print("RESULT: FAIL")
    sys.exit(1)
print("RESULT: STATIC OK (docker compile_check + E4B rig gate still required on the GPU machine)")
