"""Build A21: the kernel's 31B A3 prompt with two compliance-salience substitutions.

WHY (from the 129-run compliance analysis, all 129 tasks, Fisher exact):
  - get_status called >=1: 36% solved vs 15% never (p=0.009) -- yet 47% NEVER call it,
    despite rule #1 being "the budget oracle" at the top of the prompt.
  - submitted exactly once: 32% vs 7% (p=0.008) -- 21 runs never submitted, 7 submitted 2-10x.
  - non-empty patch: 33% vs 4% (p=0.001) -- 28 runs (22%) ended with zero patch.
Four content-prompt arms (A18/D2/A19/A20) nulled on E4B; compliance salience on 31B is the
untested axis. A3's proven mechanism is a LITERAL EXAMPLE at the point of action (the
delimiter example), not an exhortation -- so both substitutions add examples, not rules.

CONTROL = the kernel prompt that produced the 129-run (sha 8641826db79b), NOT the local A3.

DISCIPLINE: two single-span substitutions, byte-verified elsewhere. Length kept tight
(A4 grew +666 chars and hurt; A18 +1094 nulled).
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CTRL = os.path.join(HERE, "_kernel_31b_a3.md")
OUT = os.path.join(HERE, "_kernel_31b_a21.md")


def sha(b):
    return hashlib.sha256(b).hexdigest()[:12]


def main():
    ctrl = open(CTRL, encoding="utf-8").read()
    print("control (kernel A3): %d chars, sha %s" % (len(ctrl), sha(ctrl.encode())))

    # ---- SUB 1: budget oracle -> literal get_status example + patch_size trigger ----
    old1 = (
        "**`get_status()` is FREE. It does NOT consume your tool-call budget, but does consume time.** "
        "It returns `tool_calls_remaining`, `time_seconds_remaining`, and `patch_size`. \n"
        "\n"
        "**Every read you do is spending effort. Every status check is free.**\n"
        "Call `get_status()` RIGHT AFTER your second tool call, and again any time you are about to "
        "start a NEW line of investigation. Knowing \"I have 19 calls left\" changes your behaviour; "
        "not knowing it is how runs die."
    )
    new1 = (
        "**`get_status()` is FREE — it does NOT consume your tool-call budget.** It returns "
        "`tool_calls_remaining`, `time_seconds_remaining`, and `patch_size`. A call and its answer:\n"
        "  `get_status` -> `{\"tool_calls_remaining\": 26, \"time_seconds_remaining\": 412, \"patch_size\": 0}`\n"
        "Call it RIGHT AFTER your second tool call, and after EVERY tool call until an edit has landed. "
        "The trigger: if `patch_size` is 0 and you have a hypothesis, you are reading instead of editing "
        "— make the edit NOW. Prior runs that never called get_status died at the wall with budget "
        "they never looked at."
    )
    n1 = ctrl.count(old1)
    if n1 != 1:
        sys.exit("FATAL: budget-oracle span found %d times (need 1)" % n1)

    # ---- SUB 2: workflow step 4 -> literal submit example + never-end-empty ----
    old2 = (
        "4. Call submit_patch 1 (it is FREE and works even at 0 tool calls remaining). The moment it "
        "returns status \"ok\", you are DONE: write a 1-sentence summary and make NO more tool calls. "
        "NEVER call submit_patch twice."
    )
    new2 = (
        "4. Call submit_patch exactly ONCE (it is FREE and works even at 0 tool calls remaining): "
        "`submit_patch` -> `{\"status\": \"ok\", \"patch_size\": 558}`. The moment it returns status "
        "\"ok\", you are DONE: write a 1-sentence summary and make NO more tool calls. NEVER call "
        "submit_patch twice — and never end a run without it: before your last turn call `get_status`; "
        "if `patch_size` is 0, land an edit first, then submit."
    )
    n2 = ctrl.count(old2)
    if n2 != 1:
        sys.exit("FATAL: workflow-step-4 span found %d times (need 1)" % n2)

    a21 = ctrl.replace(old1, new1, 1).replace(old2, new2, 1)

    # verify: reverse substitution restores control exactly
    back = a21.replace(new1, old1, 1).replace(new2, old2, 1)
    if back != ctrl:
        sys.exit("FATAL: A21 is not a clean double-substitution of the control")
    if a21.count(old1) or a21.count(old2):
        sys.exit("FATAL: an old span survived in A21")

    open(OUT, "w", encoding="utf-8", newline="\n").write(a21)
    print("A21: %d chars, sha %s  (%+d chars vs control, %+.1f%%)" % (
        len(a21), sha(a21.encode()), len(a21) - len(ctrl),
        100.0 * (len(a21) - len(ctrl)) / len(ctrl)))
    print("wrote", OUT)
    print()
    print("--- substitution 1 in context ---")
    i = a21.find("get_status()` is FREE")
    print(a21[i - 10:i + 700])
    print()
    print("--- substitution 2 in context ---")
    i = a21.find("4. Call submit_patch")
    print(a21[i:i + 480])


if __name__ == "__main__":
    main()
