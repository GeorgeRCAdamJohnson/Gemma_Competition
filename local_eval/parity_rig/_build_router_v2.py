"""Build agent_router_v2: the A25 router with three evidence-driven fixes.

Evidence from batch1 (m1_batch, 14 router traces + ADK agent_tool.py source):
  1. code_locator returned {'raw': ''} (empty string). Root cause (google.adk agent_tool.run_async):
     returns '' when the sub-agent session's last event has no NON-thought TEXT part - i.e. the
     specialist ENDED ON A TOOL CALL (or a thought-only final). Fix: specialist instructions get
     an explicit "STOP CALLING TOOLS, WRITE YOUR ANSWER AS PLAIN TEXT" closing rule, call cap
     lowered 6->4 (and 4->3 for logic), and thinking DISABLED (thinking_budget 0) so no
     thought-only finals are possible and dispatches get cheaper.
  2. The <=1 dispatch rule was violated (up to 4 code_locator calls per task). Fix: step-1 span
     hardened with an absolute after-the-first-call prohibition.
  3. logic_analyst: 0 calls in 14 runs. KEPT (2-specialist structure matches the in-flight
     board submission; zero usage is a measurement, not yet a defect).

Everything else byte-identical to agent_router. Single-source texts from kern_src tail where
unchanged; v2-specific text defined here.
"""
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
LE = Path(__file__).resolve().parent.parent
RIG = LE / "parity_rig"
TAIL = (LE / "kern_src" / "_a25_router_tail.py").read_text(encoding="utf-8")

step1_old = re.search(r'_step1_old = """(.*?)"""', TAIL, re.S).group(1)   # A3's original step 1
step1_v1 = re.search(r'_step1_new = """(.*?)"""', TAIL, re.S).group(1)    # A25 v1 span

# ---- v2 step-1 span: same structure, hardened cap + absolute one-dispatch rule ----
step1_v2 = (
    "1. Read the problem statement. Extract the file/function/error AND the exact contract "
    "(messages, variants, every field named). Classify the task in one word before acting: "
    "LOCATE (a wrong value, constant, pattern, or deviation hidden somewhere in the code), "
    "LOGIC (control flow, guard, algorithm, or argument wiring wrong once the site is found), "
    "or TEST-DRIVEN (the contract is an exact string/exception/variant set). "
    "LOCATE-class: you may call `code_locator` - AT MOST ONE DISPATCH FOR THE WHOLE TASK. "
    "After that single call, NEVER call any specialist again, no matter what it returned "
    "(including an empty answer): work from its answer or your own greps. "
    "LOGIC-class: you may call `logic_analyst` - again AT MOST ONE DISPATCH total. "
    "TEST-DRIVEN or unclear: use no specialist. Specialists never edit files - YOU make the "
    "single edit. If you used no specialist, find the site with 1 `run_command` grep or "
    "`read_file`, then call `get_status` (free) to see where you stand."
)
assert step1_v2 != step1_v1

LOCATOR_V2 = """name: code_locator
model: gemma-4-31b-it-qat-w4a16-ct
instruction: |
  You are a code-locator specialist inside a SWE bug-fixing harness. Input: a bug report/problem statement.
  Use AT MOST 4 tool calls total (run_command grep / read_file / search_similar_code), then IMMEDIATELY STOP calling tools.
  Find:
  1. the exact file and line of the deviation,
  2. the correct pattern as implemented in a sibling function/file or the repo's own conventions - quote it exactly,
  3. the smallest old->new edit concept in <=3 lines.
  Do NOT edit files.
  YOUR FINAL MESSAGE IS THE ANSWER: after your last tool call, write your findings as PLAIN TEXT in the very next message - not a thought, not a tool call, not an empty response. <=8 lines; no full file dumps; no code block longer than 4 lines. Ending on a tool call instead of text makes your entire analysis DISCARD the caller.
tools:
  - run_command
  - read_file
  - search_similar_code
generate_content_config:
  temperature: 0.2
  top_p: 0.95
  max_output_tokens: 1024
  thinking_config:
    thinking_budget: 0
    include_thoughts: false
"""

LOGIC_V2 = """name: logic_analyst
model: gemma-4-31b-it-qat-w4a16-ct
instruction: |
  You are a fix-design specialist inside a SWE bug-fixing harness. Input: a bug report plus (optionally) the main agent's code span.
  Use AT MOST 3 tool calls (read_file / run_command sed / search_similar_code) to confirm the span, then IMMEDIATELY STOP calling tools.
  Design the MINIMAL fix: exact old->new text, matching the surrounding style and EVERY input variant the report implies.
  Do NOT edit files.
  YOUR FINAL MESSAGE IS THE ANSWER: after your last tool call, write the fix design as PLAIN TEXT in the very next message - not a thought, not a tool call, not an empty response. <=8 lines. Ending on a tool call instead of text makes your entire analysis DISCARD the caller.
tools:
  - read_file
  - run_command
  - search_similar_code
generate_content_config:
  temperature: 0.2
  top_p: 0.95
  max_output_tokens: 1024
  thinking_config:
    thinking_budget: 0
    include_thoughts: false
"""


def main():
    src = RIG / "agent_router"
    dst = RIG / "agent_router_v2"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    # prompt: A3 + step1_v2 (reversible, exactly one anchor)
    shipped = (LE / "pull_31ba3hard_out" / "submission" / "prompts" / "system.md").read_text(encoding="utf-8")
    assert shipped.count(step1_old) == 1, "anchor count %d" % shipped.count(step1_old)
    v2_prompt = shipped.replace(step1_old, step1_v2, 1)
    assert v2_prompt.replace(step1_v2, step1_old, 1) == shipped, "not reversible"
    (dst / "prompts" / "system.md").write_text(v2_prompt, encoding="utf-8")
    (dst / "prompts" / "system_router_v2.md").write_text(v2_prompt, encoding="utf-8")

    (dst / "sub_agents" / "locator.yaml").write_text(LOCATOR_V2, encoding="utf-8")
    (dst / "sub_agents" / "logic.yaml").write_text(LOGIC_V2, encoding="utf-8")

    # verify agent.yaml untouched (2 agent_tool, skip_summarization false) + eval/sampling identical to v1
    ag = (dst / "agent.yaml").read_text(encoding="utf-8")
    assert ag.count("agent_tool:") == 2 and "skip_summarization: false" in ag
    assert (dst / "eval_config.yaml").read_bytes() == (src / "eval_config.yaml").read_bytes()
    assert (dst / "configs" / "sampling.yaml").read_bytes() == (src / "configs" / "sampling.yaml").read_bytes()

    import hashlib
    print("agent_router_v2 ready:")
    print("  prompt chars:", len(v2_prompt), "sha:", hashlib.sha256(v2_prompt.encode()).hexdigest()[:12])
    print("  locator sha:", hashlib.sha256(LOCATOR_V2.encode()).hexdigest()[:12])
    print("  logic sha:  ", hashlib.sha256(LOGIC_V2.encode()).hexdigest()[:12])
    print("  changed vs v1: prompt step-1 (cap hardening), locator+logic (thinking off, "
          "text-final rule, call caps 6->4/4->3); agent.yaml/eval/sampling unchanged")


if __name__ == "__main__":
    main()
