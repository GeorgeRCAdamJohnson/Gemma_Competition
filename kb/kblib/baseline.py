"""LB source selection, per-track baselines, banner, curated proposals (plan
D5-12..D5-14, design R5.6). Pure and deterministic (no wall clock); reads only.

* lb_source(kb): the newest kb/pulled/submissions/<utc>.csv whose pull time is
  newer than curated/submissions.csv's mtime, else the curated file.
* steering_baseline(path): parsed from the steering file's own text
  (`**<label> @ <score> is SACRED` + the first `submission <ref>` after it).
* banner(...): `BASELINE: ...`, and on any disagreement `BASELINE CONFLICT: ...`.
  Nothing is adopted; the curated baseline stays the policy pointer.
* proposed_updates(...): markdown of proposed JSON patches for the curated files
  (written by the build to curated/_proposed_updates.md, the one allowed path).
"""
from __future__ import annotations

import datetime
import json
import pathlib
import re

from . import attribution

_SACRED = re.compile(r"\*\*(\S+) @ (0\.\d+) is SACRED")
_SUBREF = re.compile(r"submission (\d+)")
_SNAP = re.compile(r"^(\d{8}T\d{6}Z)\.csv$")


def steering_baseline(path) -> dict:
    p = pathlib.Path(path)
    if not p.is_file():
        return {"found": False, "path": str(p), "reason": "steering file missing"}
    text = p.read_text(encoding="utf-8", errors="replace")
    m = _SACRED.search(text)
    if not m:
        return {"found": False, "path": str(p),
                "reason": "no `**<label> @ <score> is SACRED` line"}
    r = _SUBREF.search(text, m.end())
    line = text.count("\n", 0, m.start()) + 1
    return {"found": True, "label": m.group(1), "score": float(m.group(2)),
            "ref": r.group(1) if r else None, "line": line, "path": str(p)}


def _utc_of_name(name):
    m = _SNAP.match(name)
    if not m:
        return None
    return datetime.datetime.strptime(m.group(1), "%Y%m%dT%H%M%SZ").replace(
        tzinfo=datetime.timezone.utc)


def _fmt_utc(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def lb_source(kb) -> dict:
    kb = pathlib.Path(kb)
    cur = kb / "curated" / "submissions.csv"
    cur_mt = None
    if cur.is_file():
        cur_mt = datetime.datetime.fromtimestamp(cur.stat().st_mtime, datetime.timezone.utc)
    snaps = []
    d = kb / "pulled" / "submissions"
    if d.is_dir():
        for p in d.glob("*.csv"):
            t = _utc_of_name(p.name)
            if t is not None:
                snaps.append((t, p))
    snaps.sort()
    newest = snaps[-1] if snaps else None
    if newest and (cur_mt is None or newest[0] > cur_mt):
        path, rel = newest[1], "pulled/submissions/" + newest[1].name
        reason = (f"newest pulled snapshot {_fmt_utc(newest[0])} is newer than "
                  f"curated/submissions.csv (mtime {_fmt_utc(cur_mt)})")
    else:
        path, rel = cur, "curated/submissions.csv"
        reason = ("no pulled snapshot" if not newest else
                  f"newest pulled snapshot {_fmt_utc(newest[0])} is not newer than "
                  f"curated/submissions.csv (mtime {_fmt_utc(cur_mt)})")
    return {"path": rel, "abs": path, "rows": attribution.read_csv_rows(path),
            "reason": reason, "snapshot_utc": _fmt_utc(newest[0]) if newest else None,
            "curated_mtime_utc": _fmt_utc(cur_mt), "curated_rows":
            attribution.read_csv_rows(cur) if rel != "curated/submissions.csv" else None}


def _score(r):
    try:
        return float(r.get("publicScore") or "")
    except ValueError:
        return None


def is_complete(r):
    return "COMPLETE" in (r.get("status") or "")


def track_best(rows) -> dict:
    """{track: {ref, score, desc, date, n_ties}} over COMPLETE scored rows;
    main = 31B or untagged, small-model = description names E4B/E2B. Ties at the
    best score report the newest ref and the tie count."""
    by_track = {}
    for r in rows:
        s = _score(r)
        if s is None or not is_complete(r):
            continue
        t = attribution.description_track(r.get("description", ""))
        by_track.setdefault(t, []).append((s, r.get("date", ""), str(r.get("ref")), r))
    best = {}
    for t, lst in by_track.items():
        top = max(x[0] for x in lst)
        ties = sorted(x for x in lst if x[0] == top)
        s, date, ref, r = ties[-1]          # newest at the best score
        best[t] = {"ref": ref, "score": s, "date": date,
                   "desc": short_desc(r.get("description", "")), "n_ties": len(ties),
                   "tie_refs": [x[2] for x in ties]}
    return best


def short_desc(d, n=60):
    d = " ".join((d or "").split()).replace("|", "/")
    if not d:
        return "(no description)"
    return d if len(d) <= n else d[:n - 3] + "..."


def _lsr(label, score, ref):
    return f"{label}@{score:.2f} {ref}" if score is not None else f"{label}@? {ref}"


def conflicts(steering, curated, lb_best) -> list:
    """Every disagreement between steering text, curated baseline and LB best."""
    out = []
    cl, cs, cr = curated.get("label"), curated.get("lb"), str(curated.get("submission_ref"))
    if not steering.get("found"):
        out.append(f"steering baseline not parsed ({steering.get('reason')})")
    else:
        if (steering["label"], steering["score"], str(steering["ref"])) != (cl, cs, cr):
            out.append(f"steering ({_lsr(steering['label'], steering['score'], steering['ref'])}) "
                       f"!= curated ({_lsr(cl, cs, cr)})")
    m = lb_best.get("main")
    if m and (m["score"] != cs or m["ref"] != cr):
        out.append(f"LB best on main track ({m['desc']} @ {m['score']:.2f}, ref {m['ref']}) "
                   f"!= curated baseline ({_lsr(cl, cs, cr)})")
    return out


def banner(steering, curated, lb_best, source) -> str:
    """Line 3 of KB_SUMMARY (may span lines). Never adopts; never calls the
    steering file stale unless its parsed text disagrees (then: CONFLICT)."""
    if steering.get("found"):
        st = (f"steering says {steering['label']} @ {steering['score']:.2f} "
              f"(ref {steering['ref']}, gemma-submission-protocol.md L{steering['line']})")
    else:
        st = f"steering baseline not parsed ({steering.get('reason')})"
    if curated:
        cu = (f"curated baseline {curated.get('label')} @ {curated.get('lb')} "
              f"(ref {curated.get('submission_ref')})")
    else:
        cu = "curated baseline: not set in curated/run_labels.json"
    m = lb_best.get("main")
    lb = (f"LB best main track (from {source}) {m['desc']} @ {m['score']:.2f} (ref {m['ref']})"
          if m else f"LB best main track (from {source}): none COMPLETE")
    lines = [f"BASELINE: {st}; {cu}; {lb}"]
    cf = conflicts(steering, curated or {}, lb_best)
    if cf:
        stp = (_lsr(steering["label"], steering["score"], steering["ref"])
               if steering.get("found") else "unparsed")
        cup = _lsr(curated.get("label"), curated.get("lb"), curated.get("submission_ref")) \
            if curated else "unset"
        lbp = f"{m['desc']}@{m['score']:.2f} {m['ref']}" if m else "none"
        lines.append(f"BASELINE CONFLICT: steering={stp} curated={cup} lb_best_main={lbp} "
                     f"(source {source}) — nothing adopted; the user decides "
                     f"(see curated/_proposed_updates.md)")
    s = lb_best.get("small-model")
    if s:
        lines.append(f"SMALL-MODEL TRACK: lb_best_small={s['desc']}@{s['score']:.2f} {s['ref']} "
                     f"(source {source}); BASELINE CONFLICT (small-model): no curated "
                     f"small-model baseline")
    else:
        lines.append(f"SMALL-MODEL TRACK: no COMPLETE scored E2B/E4B submission in {source}; "
                     f"no curated small-model baseline")
    return "\n".join(lines)


# ------------------------------------------------------------------ proposals

def stale_pending(run_labels, rows) -> list:
    """Curated pending entries whose ref is COMPLETE (scored) in the LB source."""
    by_ref = {str(r.get("ref")): r for r in rows}
    out = []
    for i, p in enumerate(run_labels.get("pending", []) or []):
        r = by_ref.get(str(p.get("submission_ref")))
        if r and is_complete(r) and (p.get("status") or "") != "COMPLETE":
            out.append({"index": i, "label": p.get("label"), "ref": str(p.get("submission_ref")),
                        "curated_status": p.get("status"), "status": "COMPLETE",
                        "score": _score(r)})
    return out


def proposed_updates(run_labels, src, lb_best, steering, lexicon_default_path=None,
                     replay_missing=None) -> str:
    """Markdown listing each detected curated staleness as a proposed JSON patch.
    Deterministic; never applied by the builder."""
    curated = run_labels.get("baseline", {}) or {}
    rows = src["rows"]
    out = ["# Proposed updates to curated inputs (generated by build_kb.py — NOT applied)",
           "",
           "The builder never writes curated inputs. Each section is a proposed JSON patch",
           "(RFC 6902 style) for the user to review and apply by hand. Nothing here is adopted.",
           f"LB source used: `{src['path']}` ({src['reason']}).", ""]
    n = 0
    for sp in stale_pending(run_labels, rows):
        n += 1
        out += [f"## {n}. run_labels.json: pending[{sp['label']}] is stale",
                f"The LB source shows ref {sp['ref']} {sp['status']} {sp['score']}; curated says "
                f"{sp['curated_status']}.", "```json",
                json.dumps([
                    {"op": "replace", "path": f"/pending/{sp['index']}/status",
                     "value": "COMPLETE"},
                    {"op": "add", "path": f"/pending/{sp['index']}/public_score",
                     "value": sp["score"]},
                    {"op": "add", "path": f"/pending/{sp['index']}/note_scored",
                     "value": f"scored {sp['score']} per {src['path']}"}], indent=1),
                "```",
                "(Or move the entry out of `pending` into a history list; the user decides.)", ""]
    cf = conflicts(steering, curated, lb_best)
    if cf:
        n += 1
        m = lb_best.get("main")
        out += [f"## {n}. Baseline conflict (USER DECISION — not adopted)"]
        out += [f"- {c}" for c in cf]
        if m:
            out += ["If the user confirms the LB best as the new policy baseline:", "```json",
                    json.dumps([{"op": "replace", "path": "/baseline/lb", "value": m["score"]},
                                {"op": "replace", "path": "/baseline/submission_ref",
                                 "value": int(m["ref"])},
                                {"op": "replace", "path": "/baseline/submission_date",
                                 "value": m["date"][:10]},
                                {"op": "replace", "path": "/baseline/label",
                                 "value": "<label for ref " + m["ref"] + ">"}], indent=1),
                    "```",
                    "The steering file (.kiro/steering/gemma-submission-protocol.md) is the "
                    "user's to edit; the builder only reports the disagreement.", ""]
    s = lb_best.get("small-model")
    if not run_labels.get("small_model_baseline"):
        n += 1
        out += [f"## {n}. run_labels.json: no small-model (E2B/E4B) baseline"]
        if s:
            out += [f"Best COMPLETE small-model submission in the LB source: {s['desc']} @ "
                    f"{s['score']:.2f} (ref {s['ref']}, {s['date'][:10]}).", "```json",
                    json.dumps([{"op": "add", "path": "/small_model_baseline",
                                 "value": {"label": "<label>", "lb": s["score"],
                                           "submission_ref": int(s["ref"]),
                                           "submission_date": s["date"][:10],
                                           "status": "COMPLETE",
                                           "confirmed_against": src["path"]}}], indent=1),
                    "```", ""]
        else:
            out += ["No COMPLETE scored E2B/E4B submission in the LB source yet.", ""]
    n += 1
    out += [f"## {n}. lever_lexicon.json is missing"]
    if lexicon_default_path and pathlib.Path(lexicon_default_path).is_file():
        out += [f"Proposed content = `kblib/{pathlib.Path(lexicon_default_path).name}` "
                "(code-owned default):", "```json",
                pathlib.Path(lexicon_default_path).read_text(encoding="utf-8").rstrip("\n"),
                "```", ""]
    else:
        out += ["Placeholder: the code-owned default lexicon "
                "(`kblib/lever_lexicon_default.json`) is added by FEAT-003; its content will "
                "be proposed here once it exists.", ""]
    if src["path"] != "curated/submissions.csv":
        cur_rows = src.get("curated_rows") or []
        cur_refs = {str(r.get("ref")) for r in cur_rows}
        new = [r for r in rows if str(r.get("ref")) not in cur_refs]
        changed = []
        cur_by = {str(r.get("ref")): r for r in cur_rows}
        for r in rows:
            c = cur_by.get(str(r.get("ref")))
            if c and (c.get("status"), c.get("publicScore")) != (r.get("status"),
                                                                   r.get("publicScore")):
                changed.append(str(r.get("ref")))
        n += 1
        out += [f"## {n}. submissions.csv refresh",
                f"Replace `curated/submissions.csv` ({len(cur_rows)} rows) with `{src['path']}` "
                f"({len(rows)} rows).",
                f"- new refs: {', '.join(str(r.get('ref')) for r in new) or 'none'}",
                f"- status/score changed: {', '.join(changed) or 'none'}", ""]
    if replay_missing:
        n += 1
        out += [f"## {n}. replay_set.json: min-set run ids not found on disk"]
        out += [f"- {x}" for x in replay_missing]
        out += [""]
    return "\n".join(out).rstrip("\n") + "\n"
