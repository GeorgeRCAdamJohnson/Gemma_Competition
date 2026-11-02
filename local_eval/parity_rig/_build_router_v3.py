"""Build agent_router_v3 from agent_router_v2.

ONE deliberate change vs v2: the stop-signal travels INSIDE the specialist's answer -
every final message must end with a machine-like consumed-marker line, because system-prompt
prohibitions demonstrably failed (v2: multi-dispatch on 8/14 tasks, up to 12 calls on
rich_3905, despite an AT MOST ONE prohibition). Models obey text in front of them.

ONE repair (unintended v2 diff): v2's step-1 rewrite silently dropped v1's sentence
describing WHAT the locator returns ("it returns file, line, the deviation, and the correct
sibling/reference pattern in <=8 lines"). Restored.

Kept from v2 (proven): thinking OFF in specialists + explicit plain-text-final rule
(empty returns 13 -> 0), call caps 4/3, hardened step-1 cap language.
agent.yaml / eval_config / sampling byte-identical to v1 (== shipped A3 family).
"""
import hashlib
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
LE = Path(__file__).resolve().parent.parent
RIG = LE / "parity_rig"
TAIL = (LE / "kern_src" / "_a25_router_tail.py").read_text(encoding="utf-8")
step1_old = re.search(r'_step1_old = """(.*?)"""', TAIL, re.S).group(1)

EXPECT = ("it returns file, line, the deviation, and the correct sibling/reference pattern "
          "in <=8 lines")
STOP_SIG = ("  FINAL LINE REQUIREMENT: your last message MUST end with exactly this line: "
            "[DISPATCH CONSUMED - no further specialist calls are permitted for this task]")

step1_v3 = (
    "1. Read the problem statement. Extract the file/function/error AND the exact contract "
    "(messages, variants, every field named). Classify the task in one word before acting: "
    "LOCATE (a wrong value, constant, pattern, or deviation hidden somewhere in the code), "
    "LOGIC (control flow, guard, algorithm, or argument wiring wrong once the site is found), "
    "or TEST-DRIVEN (the contract is an exact string/exception/variant set). "
    "LOCATE-class: you may call `code_locator` - AT MOST ONE DISPATCH FOR THE WHOLE TASK: "
    + EXPECT + ". "
    "After that single call, NEVER call any specialist again, no matter what it returned "
    "(including an empty answer): work from its answer or your own greps. "
    "LOGIC-class: you may call `logic_analyst` - again AT MOST ONE DISPATCH total "
    "(<=8-line fix design). "
    "TEST-DRIVEN or unclear: use no specialist. Specialists never edit files - YOU make the "
    "single edit. If you used no specialist, find the site with 1 `run_command` grep or "
    "`read_file`, then call `get_status` (free) to see where you stand."
)

LOCATOR_V3 = """name: code_locator
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
  FINAL LINE REQUIREMENT: your last message MUST end with exactly this line:
  [DISPATCH CONSUMED - no further specialist calls are permitted for this task]
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

LOGIC_V3 = """name: logic_analyst
model: gemma-4-31b-it-qat-w4a16-ct
instruction: |
  You are a fix-design specialist inside a SWE bug-fixing harness. Input: a bug report plus (optionally) the main agent's code span.
  Use AT MOST 3 tool calls (read_file / run_command sed / search_similar_code) to confirm the span, then IMMEDIATELY STOP calling tools.
  Design the MINIMAL fix: exact old->new text, matching the surrounding style and EVERY input variant the report implies.
  Do NOT edit files.
  YOUR FINAL MESSAGE IS THE ANSWER: after your last tool call, write the fix design as PLAIN TEXT in the very next message - not a thought, not a tool call, not an empty response. <=8 lines. Ending on a tool call instead of text makes your entire analysis DISCARD the caller.
  FINAL LINE REQUIREMENT: your last message MUST end with exactly this line:
  [DISPATCH CONSUMED - no further specialist calls are permitted for this task]
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
    src = RIG / "agent_router_v2"
    dst = RIG / "agent_router_v3"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)

    shipped = (LE / "pull_31ba3hard_out" / "submission" / "prompts" / "system.md").read_text(encoding="utf-8")
    assert shipped.count(step1_old) == 1, "anchor count %d" % shipped.count(step1_old)
    v3_prompt = shipped.replace(step1_old, step1_v3, 1)
    assert v3_prompt.replace(step1_v3, step1_old, 1) == shipped, "not reversible"
    assert EXPECT in v3_prompt, "expectation sentence missing"
    assert v3_prompt.count("DISPATCH CONSUMED") == 0, "stop-signal must not be in main prompt"
    (dst / "prompts" / "system.md").write_text(v3_prompt, encoding="utf-8")
    (dst / "prompts" / "system_router_v3.md").write_text(v3_prompt, encoding="utf-8")
    (dst / "sub_agents" / "locator.yaml").write_text(LOCATOR_V3, encoding="utf-8")
    (dst / "sub_agents" / "logic.yaml").write_text(LOGIC_V3, encoding="utf-8")

    ag = (dst / "agent.yaml").read_text(encoding="utf-8")
    assert ag.count("agent_tool:") == 2 and "skip_summarization: false" in ag
    assert (dst / "eval_config.yaml").read_bytes() == (src / "eval_config.yaml").read_bytes()
    assert (dst / "configs" / "sampling.yaml").read_bytes() == (src / "configs" / "sampling.yaml").read_bytes()
    assert LOCATOR_V3.count("DISPATCH CONSUMED") == 1 and LOGIC_V3.count("DISPATCH CONSUMED") == 1

    print("agent_router_v3 ready:")
    print("  prompt chars:", len(v3_prompt), "sha:", hashlib.sha256(v3_prompt.encode()).hexdigest()[:12])
    print("  locator sha:", hashlib.sha256(LOCATOR_V3.encode()).hexdigest()[:12],
          "| logic sha:", hashlib.sha256(LOGIC_V3.encode()).hexdigest()[:12])
    print("  changes vs v2: +stop-signal in specialist returns (deliberate), "
          "+expectation sentence restored (repair); everything else byte-identical")


if __name__ == "__main__":
    main()
