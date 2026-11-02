"""Build the E4B prompt arms for the 2026-10-24 sweep.

DISCIPLINE (from the log): SUBSTITUTE, never append. Every arm is derived from A3 by
replacing exactly one span; every other byte of A3 must survive verbatim. The builder
asserts that, so a silent edit cannot creep in.

ARMS
  A3  control            e4b_A3_delim.md (untouched)
  D2  structure/STOP     e4b_D2_checklist.md (already built; diffed, not rebuilt)
  A19 short-anchor       A3 with "kept SHORT and UNIQUE" replaced by a hard
                         single-line constraint. Targets the measured length effect
                         (single-line anchors 52.5% vs multi-line 34.4%, and the
                         effect holds WITHIN task). A18 tested copy-fidelity, not
                         length, so this is a different axis.
"""
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
A3_PATH = os.path.join(HERE, "e4b_A3_delim.md")
D2_PATH = os.path.join(HERE, "e4b_D2_checklist.md")
OUT = os.path.join(HERE, "e4b_A19_shortanchor.md")


def sha(b):
    return hashlib.sha256(b).hexdigest()[:12]


def main():
    a3 = open(A3_PATH, "rb").read()
    print("A3  %6d B  sha %s" % (len(a3), sha(a3)))

    # ---- the one span A19 replaces -------------------------------------------------
    old_span = b"kept SHORT and UNIQUE"
    n = a3.count(old_span)
    if n != 1:
        sys.exit("FATAL: expected exactly 1 occurrence of the anchor span, found %d" % n)

    new_span = (
        b"ONE line and at most 80 characters -- a multi-line old_string fails "
        b"about half the time, a single short line succeeds; if the fix spans "
        b"several lines, anchor on the ONE line that actually changes"
    )
    a19 = a3.replace(old_span, new_span, 1)

    # ---- verify: everything else is byte-identical ---------------------------------
    # Rebuild A3 from A19 by reversing the substitution and compare.
    back = a19.replace(new_span, old_span, 1)
    if back != a3:
        sys.exit("FATAL: A19 is not a clean single-span substitution of A3")
    if a19.count(old_span) != 0:
        sys.exit("FATAL: the old span survived in A19")

    open(OUT, "wb").write(a19)
    print("A19 %6d B  sha %s  (%+d chars vs A3)" % (len(a19), sha(a19), len(a19) - len(a3)))
    print("     wrote %s" % OUT)

    # ---- D2: report the delta, do not rebuild --------------------------------------
    if os.path.exists(D2_PATH):
        d2 = open(D2_PATH, "rb").read()
        print("D2  %6d B  sha %s  (%+d chars vs A3)" % (len(d2), sha(d2), len(d2) - len(a3)))
        a3l = a3.decode("utf-8", "replace").split("\n")
        d2l = d2.decode("utf-8", "replace").split("\n")
        import difflib
        changed = [l for l in difflib.unified_diff(a3l, d2l, lineterm="", n=0)
                   if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]
        print("     D2 differs from A3 on %d lines" % len(changed))
    else:
        print("D2  MISSING at %s" % D2_PATH)

    # ---- ASCII check (the notebook build asserts this too) -------------------------
    for name, b in (("A3", a3), ("A19", a19)):
        bad = [i for i, ch in enumerate(b) if ch > 127]
        print("     %s non-ASCII bytes: %d" % (name, len(bad)))


if __name__ == "__main__":
    main()
