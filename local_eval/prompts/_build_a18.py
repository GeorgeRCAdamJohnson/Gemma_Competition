"""Build the anchor-landing arm (A18) by SUBSTITUTING A3's L43, never appending.

A4 broke A3's win by ADDING length (corruption 0.006 -> 0.040). So this arm replaces
exactly one line and stays within ~40 chars of the original.

The mechanism, grounded in the measured failure:
  rich_2725 r0 sent the SAME garbled old_string 13 times (15 edit errors, patch=0).
  The real file has:
        if _box:                                      12 spaces
            if last and show_footer:                  16
                yield _Segment(                       20
                    _box.get_row(widths, "foot", ...  24
                )                                     20
                yield new_line                        20
            left, right, _divider = box_segments[...  16
  The model sent `if _box:` then jumped straight to the 24-space get_row line, DROPPING
  `if last and show_footer:`, `yield _Segment(` and the closing `)`, then invented
  `if _box and first and show_header:` which does not exist.
  => It is SUMMARISING the code's structure, not copying a contiguous span.

A3 already says "copied byte-for-byte ... kept SHORT and UNIQUE" and it does not work.
So this arm shows the copy operation literally instead of instructing it -- the same
move that made A3 win (a literal example of the serialization shape).
"""
import pathlib

src = pathlib.Path("e4b_A3_delim.md").read_text(encoding="utf-8")
lines = src.split("\n")

OLD = lines[42]
assert "old_string" in OLD and "byte-for-byte" in OLD, "L43 drifted -- re-check before building"

NEW = (
    "   `old_string` = ONE contiguous span of 1-3 lines, copied character-for-character out of the "
    "`read_file` output you just received (drop the line-number gutter only). Do NOT retype it from "
    "memory, do NOT skip lines, do NOT merge lines from different places. `new_string` = the "
    "replacement. The matcher forgives indentation; it cannot match text you invented. Match "
    "existing conventions/strings/types EXACTLY, including the sibling's message style."
)

# A literal worked example, grounded in real rich/table.py bytes, showing the copy.
EXAMPLE = (
    "   COPY, DON'T RETYPE. `read_file` printed (gutter stripped):\n"
    "   ```\n"
    "               if _box:\n"
    "                   if last and show_footer:\n"
    "                       yield _Segment(\n"
    "                           _box.get_row(widths, \"foot\", edge=show_edge), border_style\n"
    "                       )\n"
    "   ```\n"
    "   Correct `old_string` = a slice of exactly those lines:\n"
    "   `<|\"|>{\"filepath\": <|\"|>rich/table.py<|\"|>, \"old_string\": <|\"|>                    yield _Segment(\n"
    "                       _box.get_row(widths, \"foot\", edge=show_edge), border_style\n"
    "                   )<|\"|>, \"new_string\": <|\"|>                    yield _Segment(\n"
    "                       _box.get_row(widths, \"foot\", edge=show_edge), border_style, new_line\n"
    "                   )<|\"|>}<|\"|>`\n"
    "   WRONG (a real failed run): `if _box:` then the 24-space `get_row` line, dropping "
    "`if last and show_footer:`, `yield _Segment(` and `)`, then inventing "
    "`if _box and first and show_header:` -- a line that does not exist. A summary, not a copy."
)

lines[42] = NEW
lines.insert(43, EXAMPLE)
out = "\n".join(lines)

dst = pathlib.Path("e4b_A18_anchor.md")
dst.write_text(out, encoding="utf-8")

print(f"A3:      {len(src)} chars")
print(f"A18:     {len(out)} chars  (delta {len(out)-len(src):+d})")
print(f"wrote {dst}")
print()
print("--- the substituted line ---")
print(NEW)
print()
print("--- the added example (first 400 chars) ---")
print(EXAMPLE[:400])
