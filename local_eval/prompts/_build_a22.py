"""Build A22: the kernel control with all FOUR Class-1 contradictions fixed.

CLASS 1 = direct contradictions (the model cannot obey both orders):
  1. Two locate deadlines: line 26 "AT MOST 3-4 tool calls" vs line 16 trigger
     "tool_calls_remaining <= 14". Data: first_edit averages call 19, 90% violate
     both -- likely because they contradict. FIX: one deadline, the trigger table.
  2. One edit vs N edits: line 40 "1 edit_file call" vs line 23 "apply EACH"
     (multi-item). 38 of 129 tasks have multi-file gold. FIX: conditional.
  3. What's free: line 4 "get_status is FREE" (true: count_tool_call=False) vs
     line 20 "budget limits READS AND EDITS equally" + "still allowed to edit"
     (the 3777 BudgetExceeded death: model quoted line 20, harness rejected).
     FIX: name the two free calls explicitly, hard edit deadline.
  4. "implies" vs "exact": line 33 invites inference then forbids paraphrase.
     FIX: delete "implies".

DISCIPLINE: four single-span substitutions of _kernel_31b_a3.md, byte-verified
elsewhere. No additions, no deletions outside the spans.
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CTRL = os.path.join(HERE, "_kernel_31b_a3.md")
OUT = os.path.join(HERE, "_kernel_31b_a22.md")


def sha(b):
    return hashlib.sha256(b).hexdigest()[:12]


def main():
    ctrl = open(CTRL, encoding="utf-8").read()
    print("control: %d chars, sha %s" % (len(ctrl), sha(ctrl.encode())))

    subs = []

    # ---- FIX 1: two locate deadlines -> one (the trigger table) ----
    old1 = ("Spend AT MOST 3-4 tool calls locating the bug, then MAKE YOUR EDIT. "
            "Do NOT attempt large multi-file refactors")
    new1 = ("Locate the bug within the deadline in the trigger table above "
            "(stop locating when tool_calls_remaining <= 14), then MAKE YOUR EDIT. "
            "Do NOT attempt large multi-file refactors")
    subs.append(("locate deadline", old1, new1))

    # ---- FIX 2: 1 edit vs N edits -> conditional ----
    old2 = "Make the minimal fix with 1 `edit_file` call. That is your PRIMARY edit mechanism."
    new2 = ("Make the minimal fix with ONE `edit_file` call when the fix lives in a single file; "
            "when the problem statement names or implies multiple files, make ONE `edit_file` call "
            "PER FILE. That is your PRIMARY edit mechanism.")
    subs.append(("edit count", old2, new2))

    # ---- FIX 3: what's free + hard edit deadline (replaces line 20) ----
    old3 = ("**When you are out of locating budget you are still allowed to edit.** "
            "The budget limits READS AND EDITS equally, which is why you must bank the edit before you run dry.")
    new3 = ("**`get_status` and `submit_patch` are the ONLY free calls.** Every read and every edit "
            "counts against the 28-call budget. You MUST have landed an edit before "
            "tool_calls_remaining reaches 0 -- at 0 the harness rejects edit_file entirely "
            "(BudgetExceeded). Bank the edit before you run dry.")
    subs.append(("free calls", old3, new3))

    # ---- FIX 4: "implies" vs "exact" ----
    old4 = "use the exact phrasing the problem statement implies"
    new4 = "use the exact phrasing the problem statement states"
    subs.append(("implies->states", old4, new4))

    a22 = ctrl
    for name, old, new in subs:
        n = a22.count(old)
        if n != 1:
            sys.exit("FATAL [%s]: span found %d times (need 1)" % (name, n))
        a22 = a22.replace(old, new, 1)
        print("  applied: %-16s (%+d chars)" % (name, len(new) - len(old)))

    # verify: reverse all substitutions restores control exactly
    back = a22
    for name, old, new in reversed(subs):
        back = back.replace(new, old, 1)
    if back != ctrl:
        sys.exit("FATAL: A22 is not a clean quadruple-substitution of the control")

    open(OUT, "w", encoding="utf-8", newline="\n").write(a22)
    print("A22: %d chars, sha %s  (%+d chars vs control, %+.1f%%)" % (
        len(a22), sha(a22.encode()), len(a22) - len(ctrl),
        100.0 * (len(a22) - len(ctrl)) / len(ctrl)))
    print("wrote", OUT)

    # show each fix in context
    for name, old, new in subs:
        i = a22.find(new[:40])
        print("\n--- %s in context ---" % name)
        print(a22[max(0, i - 80):i + len(new) + 80])


if __name__ == "__main__":
    main()
