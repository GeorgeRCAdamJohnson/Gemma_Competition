"""Gold coverage table + required-node gap docs (REVISION 5, D5-22 / D5-23).

Reads the rp-5 gold-first records in KB/replays/gold/<task>.json (+ hunk-mode
records in KB/replays/gold/hunk/<task>.json) and, READ-ONLY, the rp-4 reference
files KB/replays/goldgate_all.json (user's local_eval/gold_gate_all.py) and
KB/audits/_decode_sweep_cache/gold_gate.json. The reference files feed the
concordance column only; they are never counted as rp-5 gold records.

Deterministic: rows sorted by task, no wall-clock values.
"""
from __future__ import annotations

import json
import re
from collections import Counter

from . import unidiff

GC_VERSION = "gc-1"
_RICH = "Textualize/rich"
_FASTAPI = "fastapi/fastapi"


def _read_json(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _gold_rec(kb, task, mode, rp_version):
    sub = kb / "replays" / "gold"
    p = sub / f"{task}.json" if mode == "added" else sub / mode / f"{task}.json"
    rec = _read_json(p, None) if p.is_file() else None
    if rec and rec.get("engine_version") == rp_version and \
            rec.get("required_mode", "added") == mode:
        return rec
    return None


def _concord(ref, task, verdict):
    if not isinstance(ref, dict) or task not in ref:
        return "absent", None
    rv = (ref[task] or {}).get("gold_first")
    if verdict is None:
        return "n/a (no rp-5 record)", rv
    return ("agree" if rv == verdict else "disagree"), rv


def static_hunk_test_funcs(test_patch):
    """Static count of test functions touched by test_patch hunks (from the hunk
    header's enclosing `def test_*` and any `def test_*` line inside a hunk).
    An approximation: it does not read the post-patch file."""
    names = set()
    try:
        files = unidiff.parse(test_patch or "")
    except unidiff.UniDiffError:
        return []
    for f in files:
        if not f["new_path"].endswith(".py"):
            continue
        for h in f["hunks"]:
            m = re.search(r"def (test_\w+)", h.get("header") or "")
            if m:
                names.add(m.group(1))
            for ln in h["added"] + h["removed"] + h["context"]:
                m = re.match(r"\s*(?:async\s+)?def (test_\w+)", ln)
                if m:
                    names.add(m.group(1))
    return sorted(names)


def build(kb, tasks_gold, tasks_raw, rp_version):
    """Return the gold_coverage.json object.

    tasks_raw: {task: {"patch", "test_patch"}} (replay.load_raw_tasks output).
    """
    ggall = _read_json(kb / "replays" / "goldgate_all.json", {})
    dsweep = _read_json(kb / "audits" / "_decode_sweep_cache" / "gold_gate.json", {})
    rows = []
    for task in sorted(tasks_gold["tasks"]):
        gt = tasks_gold["tasks"][task]
        repo = gt["repo"]
        rec = _gold_rec(kb, task, "added", rp_version)
        hrec = _gold_rec(kb, task, "hunk", rp_version)
        if repo != _RICH and not (repo == _FASTAPI and (rec or hrec)):
            continue
        verdict = rec.get("gold_first") if rec else None
        c_all, v_all = _concord(ggall, task, verdict)
        c_ds, v_ds = _concord(dsweep, task, verdict)
        row = {
            "task": task, "repo": repo,
            "verdict": verdict or "not run (no rp-5 record)",
            "reason": (rec.get("reason") or "") if rec else "",
            "result_criterion": rec.get("result_criterion") if rec else None,
            "pins": rec.get("pins", []) if rec else [],
            "pin_provenance": rec.get("pin_provenance") if rec else None,
            "gold_pass_n": len(rec.get("gold_pass_tests", [])) if rec else None,
            "required_tests_n": len(rec.get("required_tests", [])) if rec else None,
            "required_mode_results": {
                "added": verdict,
                "hunk": hrec.get("gold_first") if hrec else None},
            "hunk_reason": (hrec.get("reason") or "") if hrec else None,
            "hunk_extra_required": (sorted(set(hrec.get("required_tests", []))
                                           - set(gt["tests"]["added_tests"]))
                                    if hrec else None),
            "added_tests_empty": not gt["tests"]["added_tests"],
            "skipped_required": rec.get("skipped_required", []) if rec else [],
            "concordance": {"goldgate_all": c_all, "decode_sweep_gold_gate": c_ds},
            "reference_verdicts": {"goldgate_all": v_all, "decode_sweep_gold_gate": v_ds},
        }
        rows.append(row)
    gap = []
    for task in sorted(tasks_gold["tasks"]):
        gt = tasks_gold["tasks"][task]
        if gt["tests"]["added_tests"]:
            continue
        tp = (tasks_raw.get(task) or {}).get("test_patch", "")
        funcs = static_hunk_test_funcs(tp)
        hrec = _gold_rec(kb, task, "hunk", rp_version)
        gap.append({"task": task, "repo": gt["repo"],
                    "test_files": gt["tests"]["files"],
                    "hunk_test_funcs_static": funcs,
                    "n_hunk_test_funcs_static": len(funcs),
                    "hunk_verdict": hrec.get("gold_first") if hrec else None,
                    "hunk_required_n": len(hrec.get("required_tests", [])) if hrec else None})
    rich = [r for r in rows if r["repo"] == _RICH]
    fa = [r for r in rows if r["repo"] == _FASTAPI]
    return {
        "schema": "gold_coverage/1", "engine": GC_VERSION, "replay_engine": rp_version,
        "note": ("rp-5 gold-first, local Windows env (MEASURED by the engine). "
                 "goldgate_all.json / decode-sweep gold_gate.json are rp-4 reference "
                 "files used for concordance only, never counted."),
        "counts": {
            "rich_rows": len(rich),
            "rich_by_verdict": dict(sorted(Counter(r["verdict"] for r in rich).items())),
            "fastapi_rows": len(fa),
            "fastapi_by_verdict": dict(sorted(Counter(r["verdict"] for r in fa).items())),
            "concordance_goldgate_all": dict(sorted(Counter(
                r["concordance"]["goldgate_all"] for r in rows).items())),
            "whole_file_fallback_tasks": len(gap),
        },
        "rows": rows,
        "whole_file_fallback": gap,
    }


def render_lines(cov):
    """KB_SUMMARY §13a / §13b lines."""
    c = cov["counts"]
    out = ["", "### 13a. Gold coverage (rp-5 gold-first, local Windows; "
               "KB/replays/gold_coverage.json)",
           f"- rich rows: {c['rich_rows']} — by verdict: "
           + (", ".join(f"{k} {v}" for k, v in c["rich_by_verdict"].items()) or "none"),
           f"- fastapi rows attempted: {c['fastapi_rows']} — by verdict: "
           + (", ".join(f"{k} {v}" for k, v in c["fastapi_by_verdict"].items()) or "none"),
           "- concordance with replays/goldgate_all.json (rp-4, reference only): "
           + (", ".join(f"{k} {v}" for k, v in c["concordance_goldgate_all"].items())
              or "none"),
           "", "| task | rp-5 verdict | reason | pins | gold pass n | hunk-mode | "
               "goldgate_all | decode-sweep |",
           "|---|---|---|---|---|---|---|---|"]

    def cell(s, n=90):
        s = " ".join(str(s or "").split()).replace("|", "/")
        return s if len(s) <= n else s[:n - 3] + "..."

    for r in cov["rows"]:
        conc = r["concordance"]
        refs = r["reference_verdicts"]
        out.append(
            f"| {r['task']} | {r['verdict']} | {cell(r['reason'])} | "
            f"{cell(', '.join(r['pins']), 50) or '-'} ({r['pin_provenance'] or '-'}) | "
            f"{'-' if r['gold_pass_n'] is None else r['gold_pass_n']} | "
            f"{r['required_mode_results']['hunk'] or '-'} | "
            f"{conc['goldgate_all']}" + (f" ({refs['goldgate_all']})"
                                         if conc['goldgate_all'] == 'disagree' else "")
            + f" | {conc['decode_sweep_gold_gate']} |")
    out += ["", "### 13b. Required-node gap (tasks whose test_patch adds no `def test_*`: "
                "the local bar falls back to the whole test file)",
            "- the local bar differs from the harness for these tasks (HARNESS_README "
            "L609: required = FAIL_TO_PASS / PASS_TO_PASS / test functions extracted "
            "from test_patch). `n hunk funcs` is static (hunk headers + def lines in "
            "hunks); `hunk` is the rp-5 `--required-nodes hunk` gold verdict where run.",
            "", "| task | test files | n hunk funcs (static) | funcs | hunk verdict | "
                "hunk required n |", "|---|---|---|---|---|---|"]
    for gp in cov["whole_file_fallback"]:
        out.append(f"| {gp['task']} | {cell(', '.join(gp['test_files']), 60)} | "
                   f"{gp['n_hunk_test_funcs_static']} | "
                   f"{cell(', '.join(gp['hunk_test_funcs_static']), 70) or '-'} | "
                   f"{gp['hunk_verdict'] or 'not run'} | "
                   f"{'-' if gp['hunk_required_n'] is None else gp['hunk_required_n']} |")
    return out
