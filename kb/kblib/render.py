"""Rendering KB_SUMMARY.md and log_claims.md (design §7.4, §7.5).

Deterministic text output. The ONLY wall-clock/per-build lines are the two
build-stamp lines (prefixes `<!-- build-stamp:` and `Build stamp:`), which the
idempotence check excludes.
"""
from __future__ import annotations

from . import paths

MATRIX_LEGEND = (
    "Legend: R resolved · W wrong-fix · W* junk-patch-only · N landed-not-submitted"
    " · F found-not-landed · S saw-only · L locate · I infra · ? no-trace · · not-in-run"
    " · ~ tool-call malformation share>=0.5 · ^ edit after last submit")

_CELL = {
    ("RESOLVED", None): "R",
    ("WRONG-FIX", None): "W",
    ("LANDED-NOT-SUBMITTED", None): "N",
    ("FOUND-NOT-LANDED", None): "F",
    ("LOCATE", None): "L",
    ("INFRA", None): "I",
}


def cell_letter(fc, sub):
    if fc == "RESOLVED":
        return "R"
    if fc == "WRONG-FIX":
        return "W*" if sub == "JUNK_PATCH_ONLY" else "W"
    if fc == "LANDED-NOT-SUBMITTED":
        return "N"
    if fc == "FOUND-NOT-LANDED":
        return "S" if sub == "SAW_ONLY" else "F"
    if fc == "LOCATE":
        return "L"
    if fc == "INFRA":
        return "I"
    return "?"


def kb_summary(stamp_lines, baseline_banner, build_meta, coverage, matrix,
               harness_semantics, levers, lb_section, claims_summary,
               nearmiss_section, replay_section, limitations):
    out = []
    out.extend(stamp_lines)
    out.append(baseline_banner)
    out.append("")
    out.append("# KB_SUMMARY")
    out.append("")
    out.append("## 2. Coverage")
    out.extend(coverage)
    out.append("")
    out.append("## 3. Task x run outcome matrix")
    out.extend(matrix)
    out.append("")
    out.append(MATRIX_LEGEND)
    out.append("")
    out.append("## 7. LB scores and live-best")
    out.extend(lb_section)
    out.append("")
    out.append("## 8. Log claims")
    out.extend(claims_summary)
    out.append("")
    out.append("## 9. Harness semantics")
    out.extend(harness_semantics)
    out.append("")
    out.append("## 10. Near-miss and cross-task false-positive control")
    out.extend(nearmiss_section)
    out.append("")
    out.append("## 13. Replay table (gold-first)")
    out.extend(replay_section)
    out.append("")
    out.append("## 6. Levers")
    out.extend(levers)
    out.append("")
    out.append("## 11. Known limitations")
    out.extend(limitations)
    out.append("")
    return "\n".join(out) + "\n"
