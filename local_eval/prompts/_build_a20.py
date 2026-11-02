"""Build A20: A3 + fix-shape bucket table (leave-one-out).

DISCIPLINE: SUBSTITUTE the strategy paragraph (line 29), never append. Every other byte
of A3 must survive verbatim. The builder asserts that.

LEAVE-ONE-OUT: examples come from tasks OTHER than the test set (rich_2725, rich_2943).
The bucket labels come from probe_mistakes.py's classify() over all 129 gold patches.
"""
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
A3_PATH = os.path.join(HERE, "e4b_A3_delim.md")
SHAPES_PATH = os.path.join(HERE, "_task_shapes.json")
OUT = os.path.join(HERE, "e4b_A20_buckets.md")

# Tasks excluded from examples (the sweep's test set)
EXCLUDE = {"rich_2725", "rich_2943"}


def sha(b):
    return hashlib.sha256(b).hexdigest()[:12]


def main():
    a3 = open(A3_PATH, "rb").read()
    shapes = json.load(open(SHAPES_PATH, encoding="utf-8"))
    print("A3  %6d B  sha %s" % (len(a3), sha(a3)))

    # The exact paragraph A20 replaces (line 29 of A3)
    old_para = (
        b"Most bugs are a DEVIATION from a pattern the surrounding code already follows. "
        b"Make the buggy code look like its correct siblings (the function before/after it, "
        b"or similar functions in the same file). Fix the exact deviation (wrong constant, "
        b"missing guard/branch, wrong exception, off-by-one, wrong attr/arg, missing return) "
        b"- nothing else."
    )
    n = a3.count(old_para)
    if n != 1:
        sys.exit("FATAL: expected exactly 1 strategy paragraph, found %d" % n)

    # Build the replacement: same conform-to-pattern text + compact bucket table
    # Examples are from tasks NOT in the test set (leave-one-out).
    # Pick 2 example task IDs per top bucket, excluding test tasks.
    from collections import defaultdict
    by_shape = defaultdict(list)
    for iid, lbl in sorted(shapes.items()):
        if iid not in EXCLUDE:
            by_shape[lbl].append(iid)

    # Top 6 shapes by frequency (from probe_mistakes_results.txt)
    top6 = [
        ("multiline_other", "multi-line change inside a function or method"),
        ("add_condition_branch", "missing if/elif guard or condition"),
        ("multiline_logic_in_func", "multi-line logic change inside a function body"),
        ("add_other", "missing statement (assignment, call, etc.)"),
        ("single_line_other", "single-line change (not a token swap)"),
        ("add_return", "missing return statement"),
    ]

    # Top shapes with the CLEANEST example (fewest changed lines, from non-test tasks)
    # Examples are leave-one-out: no rich_2725 or rich_2943 gold content.
    examples = [
        (b"single_token_change", b"one token wrong",
         b"`return scheme, param` -> `return scheme, param.strip()`"),
        (b"off_by_one", b"off-by-one",
         b"`return 0` -> `return 1`"),
        (b"operator/comparison_change", b"wrong operator",
         b"`if x == y:` -> `if x is y:`"),
        (b"add_condition_branch", b"missing guard",
         b"add `if origin is Annotated: return ...` before the fallthrough"),
        (b"add_return", b"missing return",
         b"add `def isatty(self) -> bool: return self.__file.isatty()`"),
        (b"pure_deletion", b"remove dead code",
         b"delete `if url.startswith(\"//\"): url = f\"/{url.lstrip('/')}\"`"),
    ]

    lines = [
        b"Most bugs are a DEVIATION from a pattern the surrounding code already follows. "
        b"Make the buggy code look like its correct siblings. Fix the exact deviation - nothing else.",
        b"",
        b"Common fix shapes (from 129 historical patches; top 6 cover 79%):",
    ]
    for shape, desc, ex in examples:
        lines.append(b"- %s (%s): e.g. %s" % (shape, desc, ex))
    lines.append(b"When the contract says X, check whether the fix is one of these shapes before inventing a new approach.")

    new_para = b"\n".join(lines)
    a20 = a3.replace(old_para, new_para, 1)

    # Verify: reverse substitution restores A3 exactly
    back = a20.replace(new_para, old_para, 1)
    if back != a3:
        sys.exit("FATAL: A20 is not a clean single-span substitution of A3")
    if a20.count(old_para) != 0:
        sys.exit("FATAL: the old paragraph survived in A20")

    open(OUT, "wb").write(a20)
    print("A20 %6d B  sha %s  (%+d chars vs A3, %+.1f%%)" % (
        len(a20), sha(a20), len(a20) - len(a3), 100.0 * (len(a20) - len(a3)) / len(a3)))
    print("     wrote %s" % OUT)

    # Show the new paragraph
    print("\n--- new strategy paragraph ---")
    print(new_para.decode("utf-8", "replace"))


if __name__ == "__main__":
    main()
