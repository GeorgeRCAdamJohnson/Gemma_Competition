import sys, pathlib
HS = pathlib.Path(__file__).resolve().parent.parent / "harness_src" / "x"
sys.path.insert(0, str(HS))
try:
    from adk_eval_core.editing.edit import apply_replacement
    print("IMPORT OK", apply_replacement)
except Exception as e:
    print("IMPORT FAIL", type(e).__name__, e)
    raise
src = "def f(x):\n    if x:\n        return 0\n    return 1\n"
for old, new in [
    ("    if x:\n        return 0", "    if x:\n        return 1"),                 # exact
    ("if x:\n    return 0", "if x:\n    return 1"),                                  # flexible (indent)
    ("if x :\n return 0", "if x:\n    return 1"),                                    # regex (spacing)
    ('return \\"0\\"', "return 1"),                                                   # unescaped (no match expected)
]:
    r = apply_replacement(src, old, new)
    print(r.strategy, r.occurrences, repr(r.error_message)[:80])
    if r.error_message is None:
        print(r.new_content)
