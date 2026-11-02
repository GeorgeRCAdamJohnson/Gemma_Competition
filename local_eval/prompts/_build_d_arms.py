"""Build three directive/clarity arms from A3, all LENGTH-CONTROLLED.

Why length control matters: A4 broke A3 by adding length (corruption 0.006 -> 0.040), and
A18 (+14.5%) is my leading explanation for its null. So every arm here is a SUBSTITUTION
that stays within +/-3% of A3's 7551 chars. If an arm wins, length is not the cause; if it
loses, length is not the excuse.

A3 is ALREADY ~90% imperative: 13 "Do NOT"/"NEVER", 3 "MUST". The only genuinely
permissive text is L20 ("you are still allowed to edit") and L36 ("Prefer"). So the
"more directive" surface is small -- which is itself the finding.

Three DISTINCT axes, not three flavours of the same thing:
  D1  WORDING   -- strip the remaining permission/hedge language. The clean "more
                  directive" test. Closest prior run is A5 (framing), which was clean
                  and NULL (p=1.000), so this is a near-replicate with a tighter edit.
  D2  STRUCTURE -- same words, restructured into a terse numbered checklist with explicit
                  STOP gates. Tests layout, not tone. No prior arm isolated this.
  D3  LENGTH    -- A3 cut DOWN ~20% by removing redundancy. Tests the length hypothesis
                  directly: if shorter is better, A18's failure was displacement.
"""
import json
from pathlib import Path

A3 = Path("e4b_A3_delim.md").read_text(encoding="utf-8")
BASE = len(A3)
print(f"A3 baseline: {BASE} chars\n")

built = {}


def sub(text, old, new, label):
    """Substitute exactly one occurrence; assert it existed."""
    assert text.count(old) == 1, f"{label}: expected 1 occurrence, got {text.count(old)}"
    return text.replace(old, new)


# ============================================================ D1: wording
d1 = A3
d1 = sub(d1,
    "**When you are out of locating budget you are still allowed to edit.** The budget limits READS AND EDITS equally, which is why you must bank the edit before you run dry.",
    "**When you run out of locating budget, EDIT ANYWAY.** The budget limits READS AND EDITS equally. Bank the edit before you run dry.",
    "D1/L20")
d1 = sub(d1,
    "Prefer asserting the behavior described in the problem's own words.",
    "Assert the behavior described in the problem's own words.",
    "D1/L36")
d1 = sub(d1,
    "Find the code with ONE `run_command` grep, or `read_file` for a whole file.",
    "Find the code with ONE `run_command` grep or `read_file`.",
    "D1/L39")
d1 = sub(d1,
    "Run a python heredoc via `run_command` ONLY as a fallback if `edit_file` reports it could not match the anchor.",
    "Run a python heredoc via `run_command` ONLY if `edit_file` reports it could not match the anchor.",
    "D1/L40")
d1 = sub(d1,
    "Most bugs are a DEVIATION from a pattern the surrounding code already follows.",
    "Most bugs are a DEVIATION from a pattern the surrounding code follows.",
    "D1/L29")
built["e4b_D1_direct.md"] = d1

# ============================================================ D2: structure
# Same content, restructured: the Workflow becomes a numbered checklist where every step
# ends in an explicit STOP gate. No new instructions, no removed instructions.
d2 = A3
d2 = sub(d2,
    "## Workflow (tight)\n1. Read the problem statement. Extract the file/function/error AND the exact contract (messages, variants, every field named). Find the code with ONE `run_command` grep, or `read_file` for a whole file. Then call `get_status` (free) to see where you stand.",
    "## Workflow (tight)\n1. LOCATE. Read the problem statement. Extract the file/function/error AND the exact contract (messages, variants, every field named). Find the code with ONE `run_command` grep or `read_file`. Call `get_status` (free).\n   STOP WHEN: you know the file and the line. Do not read more.",
    "D2/L39")
d2 = sub(d2,
    "2. Make the minimal fix with ONE `edit_file` call. That is your PRIMARY edit mechanism.",
    "2. EDIT. Make the minimal fix with ONE `edit_file` call. That is your PRIMARY edit mechanism.",
    "D2/L40")
d2 = sub(d2,
    "3. Call `get_status` again. If `patch_size` is still 0, you have not actually edited anything \u2014 fix that before submitting.",
    "3. VERIFY. Call `get_status` again. If `patch_size` is still 0 you have not edited anything.\n   STOP WHEN: patch_size > 0.",
    "D2/L48")
d2 = sub(d2,
    "4. Call submit_patch ONCE (it is FREE and works even at 0 tool calls remaining). The moment it returns status \"ok\", you are DONE: write a one-sentence summary and make NO more tool calls. NEVER call submit_patch twice.",
    "4. SUBMIT. Call submit_patch ONCE (FREE, works at 0 calls remaining). When it returns \"ok\" you are DONE: write a one-sentence summary and make NO more tool calls. NEVER call submit_patch twice.\n   STOP WHEN: submit_patch returned \"ok\". Make no further calls.",
    "D2/L49")
built["e4b_D2_checklist.md"] = d2

# ============================================================ D3: shorter
# Cut redundancy. A3 repeats "a partial fix that is submitted scores" three times and
# states the budget oracle twice. Keep every DISTINCT instruction; drop the repeats.
d3 = A3
d3 = sub(d3,
    "Spend AT MOST 3-4 tool calls locating the bug, then MAKE YOUR EDIT. Do NOT attempt large multi-file refactors \u2014 land the SMALLEST fix that addresses the problem and SUBMIT. The moment you have ANY applying patch, call `submit_patch`: a partial fix that is submitted scores; a perfect refactor that times out unsubmitted scores NOTHING.",
    "Spend AT MOST 3-4 tool calls locating the bug, then MAKE YOUR EDIT. Do NOT attempt large multi-file refactors \u2014 land the SMALLEST fix and SUBMIT. The moment you have ANY applying patch, call `submit_patch`: a partial fix that is submitted scores; a perfect refactor that times out unsubmitted scores NOTHING.",
    "D3/L26")
d3 = sub(d3,
    "If the problem needs several changes, apply EACH ONE the moment you locate it \u2014 do not trace the entire plan first and edit at the end. A partial fix that is submitted scores. A complete plan that never gets written scores nothing.",
    "If the problem needs several changes, apply EACH ONE the moment you locate it \u2014 do not trace the entire plan first and edit at the end. A complete plan that never gets written scores nothing.",
    "D3/L23")
d3 = sub(d3,
    "The hidden test asserts a PRECISE observable contract, not just \"the behavior is roughly right\". When your fix introduces or changes a user-facing string, error message, exception type, status code, or validation, you MUST match the exact wording and cover every obvious input variant:",
    "The hidden test asserts a PRECISE observable contract, not just \"the behavior is roughly right\". When your fix changes a user-facing string, error message, exception type, status code, or validation, you MUST match the exact wording and cover every obvious input variant:",
    "D3/L32")
d3 = sub(d3,
    "- ERROR / VALIDATION messages: use the exact phrasing the problem statement implies, and mirror the style of the SIBLING check already in the file (same message shape, same field-name interpolation). Do NOT invent your own wording - a test often does `pytest.raises(..., match=\"exact phrase\")`, so a paraphrase FAILS even when the logic is right.",
    "- ERROR / VALIDATION messages: use the exact phrasing the problem implies, and mirror the SIBLING check already in the file (same message shape, same field-name interpolation). Do NOT invent wording - a test often does `pytest.raises(..., match=\"exact phrase\")`, so a paraphrase FAILS even when the logic is right.",
    "D3/L33")
d3 = sub(d3,
    "- INPUT VARIANTS: if you reject newlines, reject \"\\n\" AND \"\\r\" AND \"\\r\\n\". If you guard one special char, guard the whole obvious class. Tests parametrize across all of them.",
    "- INPUT VARIANTS: if you reject newlines, reject \"\\n\" AND \"\\r\" AND \"\\r\\n\". If you guard one special char, guard the whole class. Tests parametrize across all of them.",
    "D3/L34")
d3 = sub(d3,
    "- Apply the change to EVERY field/argument/branch the problem mentions, not just the first - if the problem says \"id or event\", fix BOTH, mirroring how an existing validated field is wired.",
    "- Apply the change to EVERY field/argument/branch the problem mentions, not just the first - if it says \"id or event\", fix BOTH, mirroring how an existing validated field is wired.",
    "D3/L35")
d3 = sub(d3,
    "- A self-written test only counts as verification if it asserts the SAME exact string and the SAME variants the problem implies. If your test passes but only checks your own paraphrase, it proves nothing. Prefer asserting the behavior described in the problem's own words.",
    "- A self-written test only counts as verification if it asserts the SAME exact string and the SAME variants the problem implies. If it passes but only checks your own paraphrase, it proves nothing.",
    "D3/L36")
d3 = sub(d3,
    "`old_string` = the exact current text copied byte-for-byte from `read_file` (NO line-number gutter), kept SHORT and UNIQUE; `new_string` = the replacement. The matcher is forgiving: exact, then whitespace-flexible (re-indenting for you), then regex. Match existing conventions/strings/types EXACTLY, including the sibling's message style.",
    "`old_string` = the exact current text copied byte-for-byte from `read_file` (NO line-number gutter), kept SHORT and UNIQUE; `new_string` = the replacement. The matcher is forgiving: exact, then whitespace-flexible, then regex. Match existing conventions/strings/types EXACTLY, including the sibling's message style.",
    "D3/L43")
d3 = sub(d3,
    "Fallback only: run a python heredoc that reads the file, asserts the old text is present, replaces it once, and writes it back. Use python triple-DOUBLE-quoted strings for the OLD and NEW blocks. Pattern (one run_command call): start a `python3` heredoc; set p = pathlib.Path to the source file; s = p.read_text(); set OLD to the exact current text; set NEW to the replacement; assert OLD in s; p.write_text(s.replace(OLD, NEW, 1)); print OK; end the heredoc.",
    "Fallback only: run a python heredoc that reads the file, asserts the old text is present, replaces it once, and writes it back. Use python triple-DOUBLE-quoted strings for OLD and NEW. Pattern (one run_command call): start a `python3` heredoc; p = pathlib.Path to the source file; s = p.read_text(); OLD = the exact current text; NEW = the replacement; assert OLD in s; p.write_text(s.replace(OLD, NEW, 1)); print OK; end the heredoc.",
    "D3/L45")
built["e4b_D3_shorter.md"] = d3

# ============================================================ write + report
for name, text in built.items():
    Path(name).write_text(text, encoding="utf-8")
    delta = (len(text) - BASE) / BASE * 100
    flag = "OK" if abs(delta) <= 3 else "LENGTH RISK"
    print(f"{name:<24} {len(text):>5} chars  ({delta:+.1f}%)  {flag}")

# ============================================================ verify A3 mechanisms survive
print("\n--- A3 mechanisms that MUST survive in every arm ---")
must = [
    ("delimiter example", '<|"|>{"filepath": <|"|>rich/highlighter.py<|"|>'),
    ("CLOSING DELIMITER rule", "CLOSING DELIMITER OR `old_string` IS LOST"),
    ("fallback heredoc", "Fallback only: run a python heredoc"),
    ("sed note", "use `run_command` with `sed -n 'A,Bp' <file>`"),
    ("submit-once", "NEVER call submit_patch twice"),
    ("budget oracle", "THE BUDGET ORACLE"),
    ("danger zone", "tool_calls_remaining <= 7"),
    ("no test edits", "NEVER modify/create/delete test files"),
    ("no scope creep", "Do NOT attempt large multi-file refactors"),
    ("conform to pattern", "conform to the pattern"),
]
ok = True
for name, text in built.items():
    missing = [label for label, frag in must if frag not in text]
    print(f"  {name:<24} {'all intact' if not missing else 'MISSING: ' + str(missing)}")
    if missing:
        ok = False

print("\nALL A3 MECHANISMS INTACT" if ok else "SOMETHING WAS LOST")
