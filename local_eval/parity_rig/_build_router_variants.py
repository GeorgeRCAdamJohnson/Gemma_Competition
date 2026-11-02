"""Build agent_router_v4/v5/v6: three single-change tuning patterns on top of v3.

Goal per user: LAND MORE CONSISTENTLY. Evidence from batches 1-3 (see GEMMA_EXPERIMENT_LOG):
  - wrong-anchor near-misses (concept right, method/file wrong) decide most non-resolves;
  - v1's one GREAT dispatch (4077) used a THINKING specialist (budget 1024), v2/v3's
    thinking-off specialists are reliable but shallow;
  - decisive grep-locate (ctrl pattern) + exact-anchor edits win in 5-7 calls.

Arms (each ONE deliberate change vs v3; agent.yaml/eval/sampling byte-identical):
  v4 depth:      specialist thinking_budget 0 -> 1024 (yaml only)
  v5 anchor:     + pre-edit anchor-grep rule (step 2 span)
  v6 test-oracle:+ locate-via-tests rule (Strategy section span; tests are READ-ONLY)
Decision rules (prereg): reps=2 x 7 tasks = 14 obs/arm.
  >=5/14 resolved -> pattern advances (reps3 + then board/quota consideration)
  <=2/14 -> pattern dead locally; 3-4 -> inconclusive, may extend if mechanism metrics shine
"""
import hashlib
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
LE = Path(__file__).resolve().parent.parent
RIG = Path(__file__).resolve().parent
SRC = RIG / "agent_router_v3"
# variants are deltas vs v3-ON-DISK (built and asserted by _build_router_v3.py) - read it directly
v3_prompt = (SRC / "prompts" / "system.md").read_text(encoding="utf-8")
assert v3_prompt.startswith("You are an expert autonomous code reviewer"), "unexpected v3 prompt base"

# ---- span for v5: pre-edit anchor confirmation (single sentence, step 2) ----
V5_ANCHOR_OLD = "2. Make the minimal fix with 1 `edit_file` call. That is your PRIMARY edit mechanism."
V5_SPAN_NEW = (
    "2. BEFORE the edit: grep your anchor - run `grep -n -A 20 '<the exact symbol you are "
    "about to edit>' <file>` and confirm the problem's symbol/behaviour appears INSIDE that "
    "span. If it does not, you are at the wrong anchor: find the right function first (the "
    "shortest correct anchor beats the nearest plausible one). THEN make the minimal fix with "
    "1 `edit_file` call. That is your PRIMARY edit mechanism."
)

# ---- span for v6: test-oracle locate (Strategy section, tests READ-ONLY) ----
V6_ANCHOR_OLD = (
    "Most bugs are a DEVIATION from a pattern the surrounding code already follows."
)
V6_SPAN_NEW = (
    "The repository's own TESTS name the exact target: first `grep -rn '<problem symbol>' "
    "tests/` (READ-ONLY - never edit tests) and edit the function the test exercises, at the "
    "line the test's assertions reach. Most bugs are a DEVIATION from a pattern the "
    "surrounding code already follows."
)


def mk(name, prompt_text=None, locator=None, logic=None):
    dst = RIG / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(SRC, dst)
    if prompt_text is not None:
        (dst / "prompts" / "system.md").write_text(prompt_text, encoding="utf-8")
        (dst / "prompts" / f"{name.replace('agent_', '')}.md").write_text(prompt_text, encoding="utf-8")
    if locator:
        (dst / "sub_agents" / "locator.yaml").write_text(locator, encoding="utf-8")
    if logic:
        (dst / "sub_agents" / "logic.yaml").write_text(logic, encoding="utf-8")
    # invariants
    ag = (dst / "agent.yaml").read_text(encoding="utf-8")
    assert ag.count("agent_tool:") == 2 and "skip_summarization: false" in ag
    assert (dst / "eval_config.yaml").read_bytes() == (SRC / "eval_config.yaml").read_bytes()
    assert (dst / "configs" / "sampling.yaml").read_bytes() == (SRC / "configs" / "sampling.yaml").read_bytes()
    print("%s: prompt sha %s  locator sha %s" % (
        name,
        hashlib.sha256((dst / "prompts" / "system.md").read_bytes()).hexdigest()[:12],
        hashlib.sha256((dst / "sub_agents" / "locator.yaml").read_bytes()).hexdigest()[:12]))
    return dst


def main():
    # v4: thinking back on in specialists (yaml-only single change)
    def with_thinking(path):
        t = Path(path).read_text(encoding="utf-8")
        t2 = t.replace("thinking_budget: 0", "thinking_budget: 1024")
        assert t2 != t, path
        return t2
    loc4 = with_thinking(SRC / "sub_agents" / "locator.yaml")
    log4 = with_thinking(SRC / "sub_agents" / "logic.yaml")
    mk("agent_router_v4", None, loc4, log4)

    # v5: anchor-grep rule (one span vs v3)
    assert v3_prompt.count(V5_ANCHOR_OLD) == 1, "v5 anchor count %d" % v3_prompt.count(V5_ANCHOR_OLD)
    p5 = v3_prompt.replace(V5_ANCHOR_OLD, V5_SPAN_NEW, 1)
    assert p5.replace(V5_SPAN_NEW, V5_ANCHOR_OLD, 1) == v3_prompt
    mk("agent_router_v5", p5)

    # v6: test-oracle rule (one span vs v3)
    assert v3_prompt.count(V6_ANCHOR_OLD) == 1, "v6 anchor count %d" % v3_prompt.count(V6_ANCHOR_OLD)
    p6 = v3_prompt.replace(V6_ANCHOR_OLD, V6_SPAN_NEW, 1)
    assert p6.replace(V6_SPAN_NEW, V6_ANCHOR_OLD, 1) == v3_prompt
    mk("agent_router_v6", p6)

    print("all three variants built (each = v3 + ONE change)")


if __name__ == "__main__":
    main()
