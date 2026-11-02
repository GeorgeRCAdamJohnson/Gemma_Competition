"""Verdict merge (design §18.3).

Parses line 1 of two audit reports, computes the stricter verdict using
PROCEED(0) < REVISE(1) < NEEDS-DATA(2) < REJECT(3), and writes a NEW final
report (refusing to overwrite). An invalid line 1 counts as INVALID and forces
final >= NEEDS-DATA.
"""
from __future__ import annotations

import pathlib
import re

ORDER = {"PROCEED": 0, "REVISE": 1, "NEEDS-DATA": 2, "REJECT": 3}
INV = {v: k for k, v in ORDER.items()}
_LINE1 = re.compile(r"^VERDICT: (PROCEED|REVISE|NEEDS-DATA|REJECT)$")


def parse_verdict(report_path: pathlib.Path):
    try:
        first = report_path.read_text(encoding="utf-8").lstrip("\ufeff").splitlines()[0].rstrip()
    except Exception:
        return None
    m = _LINE1.match(first)
    return m.group(1) if m else None


def stricter(a, b):
    ra = ORDER.get(a, 2)  # INVALID -> NEEDS-DATA floor
    rb = ORDER.get(b, 2)
    return INV[max(ra, rb)]


def derive_date_slug(path: pathlib.Path):
    name = path.name
    m = re.match(r"(\d{4}-\d{2}-\d{2})-(.+?)(?:-refute|-final)?\.md$", name)
    if not m:
        return None, None
    return m.group(1), m.group(2)
