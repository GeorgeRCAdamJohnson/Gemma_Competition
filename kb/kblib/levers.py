"""Lever matrix (design §12.8 + REVISION 5 R5.8; version lv-1).

Lexicon = curated/lever_lexicon.json when it exists, else the code-owned
kblib/lever_lexicon_default.json (KB_SUMMARY names which).

Lever instances (per track; tracks are never pooled):
* config levers: a run's config field differs from the track reference
  (main: the curated baseline label's Kaggle run; other tracks: the modal value
  over the track's runs) or from the previous run of the same label (run_id
  order). `tools` compares the tool set.
* prompt levers: presence of the lexicon `prompt_regex` in the run's prompt text
  (read-only from the run's config source) flips vs the reference / previous.
* dev-harness levers: dev_harness.<field> differs from the scorer value
  (HARNESS_README).
* log levers: no config field; only log mentions (claims) are counted.

Counts are always `rows / distinct tasks` (anti n-inflation). Deterministic.
"""
from __future__ import annotations

import json
import pathlib
import re
from collections import Counter

LV_VERSION = "lv-1"
TRACKS = ("main", "small-model", "dev-proxy")
_DESC_FIELDS = {"temperature", "top_k", "thinking_budget", "max_tool_calls", "max_time_minutes",
                "max_turns", "timeout_seconds", "model"}


def load_lexicon(kb, kblib_dir):
    kb = pathlib.Path(kb)
    cur = kb / "curated" / "lever_lexicon.json"
    if cur.is_file():
        data = json.loads(cur.read_text(encoding="utf-8"))
        source = "curated/lever_lexicon.json"
    else:
        p = pathlib.Path(kblib_dir) / "lever_lexicon_default.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        source = "kblib/lever_lexicon_default.json (code-owned default; curated/lever_lexicon.json absent)"
    levers = []
    compiled = {}
    for lv in data.get("levers", []):
        flags = 0 if lv.get("case_sensitive") else re.I
        compiled[lv["id"]] = ([re.compile(x, flags) for x in lv.get("log_aliases", [])],
                              [re.compile(x) for x in lv.get("prompt_regex", [])])
        levers.append({k: lv.get(k) for k in ("id", "label", "kind", "config_field")})
    return {"source": source, "version": data.get("version", LV_VERSION), "levers": levers,
            "_compiled": compiled}


def log_matcher(lex):
    comp = lex["_compiled"]
    ids = [lv["id"] for lv in lex["levers"]]

    def fn(text):
        return sorted(i for i in ids if any(rx.search(text or "") for rx in comp[i][0]))
    return fn


# ------------------------------------------------------------------ prompt text

def _prompt_paths(g, row):
    cc = row.get("config_confidence") or ""
    cfg = row.get("config") or {}
    if cc.startswith("run submission folder"):
        return sorted((g / row["run_id"] / "submission" / "prompts").glob("*.md"))
    for pre in ("agent dir ", "rig arm dir "):
        if cc.startswith(pre):
            return sorted((g / cc[len(pre):].strip() / "prompts").glob("*.md"))
    pf = cfg.get("prompt_file")
    if pf:
        p = g / "local_eval" / pf.replace("\\", "/")
        return [p] if p.is_file() else []
    return []


def _prompt_text(g, row, cache):
    paths = _prompt_paths(g, row)
    if not paths:
        return None
    key = tuple(str(p) for p in paths)
    if key not in cache:
        parts = []
        for p in paths:
            try:
                parts.append(p.read_text(encoding="utf-8", errors="replace"))
            except OSError:
                pass
        cache[key] = "\n".join(parts) if parts else None
    return cache[key]


# --------------------------------------------------------------------- compute

def _norm_val(v):
    if isinstance(v, list):
        return tuple(sorted(v))
    return v


def _fmt(v):
    if isinstance(v, tuple):
        return f"{len(v)} tools"
    if isinstance(v, bool):
        return "present" if v else "absent"
    if isinstance(v, str) and len(v) > 12:
        return v[:8]
    return str(v)


def _modal(vals):
    c = Counter(v for v in vals if v is not None)
    if not c:
        return None
    top = max(c.values())
    return sorted((v for v, n in c.items() if n == top), key=repr)[0]


def compute(g, rows, claims_out, lex, baseline_label, lb_rows, scorer_ref=None):
    from . import attribution
    g = pathlib.Path(g)
    scorer_ref = scorer_ref or {}
    comp = lex["_compiled"]
    by_run = {}
    for r in rows:
        by_run.setdefault(r["run_id"], []).append(r)
    cache = {}
    runs = []
    for rid in sorted(by_run):
        rs = by_run[rid]
        first = rs[0]
        cfg = first.get("config") or {}
        text = None
        vals = {}
        for lv in lex["levers"]:
            k, fld = lv["kind"], lv.get("config_field")
            if k in ("config", "tools") and fld:
                vals[lv["id"]] = _norm_val(cfg.get(fld))
            elif k == "prompt":
                if text is None:
                    text = _prompt_text(g, first, cache) or ""
                vals[lv["id"]] = (any(rx.search(text) for rx in comp[lv["id"]][1])
                                  if text else None)
            elif k == "dev-harness" and fld:
                dh = first.get("dev_harness") or {}
                vals[lv["id"]] = dh.get(fld) if dh.get("found") else None
            else:
                vals[lv["id"]] = None
        runs.append({"run_id": rid, "label": first.get("version_label") or "",
                     "track": first.get("track") or "unknown",
                     "platform": (first.get("stack") or {}).get("platform") or "unknown",
                     "kind": first.get("run_kind"), "rows": rs, "vals": vals})
    # references per track
    refs = {}
    for t in TRACKS:
        tr = [r for r in runs if r["track"] == t]
        ref, basis = None, "modal value over the track's runs (no curated baseline)"
        if t == "main" and baseline_label:
            cand = [r for r in tr if r["label"] == baseline_label and r["platform"] == "kaggle"
                    and r["kind"] == "kaggle-kernel"]
            if cand:
                ref = cand[0]
                basis = f"curated baseline {baseline_label} run {ref['run_id']}"
        refvals = {}
        for lv in lex["levers"]:
            if lv["kind"] == "dev-harness":
                refvals[lv["id"]] = scorer_ref.get(lv.get("config_field"))
            elif ref is not None and ref["vals"].get(lv["id"]) is not None:
                refvals[lv["id"]] = ref["vals"][lv["id"]]
            else:
                refvals[lv["id"]] = _modal(r["vals"].get(lv["id"]) for r in tr)
        refs[t] = {"basis": basis, "vals": refvals}
    # instances
    inst = {}          # (track, lever) -> {run_id: [(vs, from, to)]}
    prev_by_label = {}
    for r in runs:
        t = r["track"]
        if t not in refs:
            continue
        for lv in lex["levers"]:
            lid = lv["id"]
            v = r["vals"].get(lid)
            if v is None:
                continue
            rv = refs[t]["vals"].get(lid)
            hits = []
            if rv is not None and v != rv:
                vs = "scorer" if lv["kind"] == "dev-harness" else (
                    "baseline" if refs[t]["basis"].startswith("curated") else "modal")
                hits.append((vs, rv, v))
            pv = prev_by_label.get((t, r["label"], lid))
            if lv["kind"] != "dev-harness" and pv is not None and pv != v:
                hits.append(("prev-same-label", pv, v))
            if hits:
                inst.setdefault((t, lid), {})[r["run_id"]] = hits
        for lv in lex["levers"]:
            v = r["vals"].get(lv["id"])
            if v is not None:
                prev_by_label[(t, r["label"], lv["id"])] = v
    # log mentions + latest non-superseded verdict claim per lever (claim track
    # from its model tokens; untagged claims count for every track)
    claims = (claims_out or {}).get("claims", [])
    mentions = {}
    latest = {}
    for c in claims:
        mods = set(c.get("models") or [])
        ct = ("small-model" if mods & {"e4b", "e2b"} else "dev-proxy" if "12b" in mods
              else "main" if "31b" in mods else "any")
        for lid in c.get("levers") or []:
            for t in TRACKS:
                if ct not in ("any", t):
                    continue
                mentions[(t, lid)] = mentions.get((t, lid), 0) + 1
                if c.get("status") == "SUPERSEDED" or c.get("unit_kind") != "verdict":
                    continue
                cur = latest.get((t, lid))
                if cur is None or (c["line"], c["claim_id"]) > (cur["line"], cur["claim_id"]):
                    latest[(t, lid)] = c
    # LB refs per track
    subs = []
    for s in lb_rows or []:
        desc = s.get("description", "") or ""
        subs.append({"ref": str(s.get("ref")), "desc": desc,
                     "track": attribution.description_track(desc),
                     "facts": attribution.description_facts(desc),
                     "score": (s.get("publicScore") or "-")})
    result = {"version": LV_VERSION, "source": lex["source"], "tracks": {}}
    for t in TRACKS:
        trows = [x for r in runs if r["track"] == t for x in r["rows"]]
        out = []
        for lv in lex["levers"]:
            lid = lv["id"]
            ri = inst.get((t, lid), {})
            irows = [x for r in runs if r["run_id"] in ri for x in r["rows"]]
            tasks = Counter(x["task"] for x in irows)
            res = Counter(x["task"] for x in irows if (x.get("outcome") or {}).get("resolved") is True)
            per_task = " ".join(f"{k}:{res.get(k, 0)}R/{n}"
                                for k, n in sorted(tasks.items(), key=lambda kv: (-kv[1], kv[0]))[:5])
            trans = Counter()
            for hits in ri.values():
                for vs, a, b in hits:
                    trans[f"{_fmt(a)}->{_fmt(b)} ({vs})"] += 1
            labels = sorted({r["label"] for r in runs if r["run_id"] in ri})
            stack = Counter(r["platform"] for r in runs if r["run_id"] in ri)
            fld = lv.get("config_field")
            lbrefs = []
            for s in subs:
                if s["track"] != t:
                    continue
                if fld in _DESC_FIELDS and fld in s["facts"]:
                    lbrefs.append(f"{s['ref']}({s['score']})")
                elif fld not in _DESC_FIELDS and any(rx.search(s["desc"]) for rx in comp[lid][0]):
                    lbrefs.append(f"{s['ref']}({s['score']})")
            lc = latest.get((t, lid))
            out.append({"id": lid, "label": lv.get("label"), "kind": lv["kind"],
                        "runs": len(ri), "rows": len(irows), "distinct_tasks": len(tasks),
                        "per_task": per_task, "labels": labels,
                        "stack": dict(sorted(stack.items())),
                        "transitions": [f"{k} x{n}" for k, n in
                                        sorted(trans.items(), key=lambda kv: (-kv[1], kv[0]))[:3]],
                        "lb_refs": sorted(lbrefs)[:6], "log_mentions": mentions.get((t, lid), 0),
                        "latest_verdict": ({"claim_id": lc["claim_id"], "line": lc["line"],
                                            "status": lc["status"]} if lc else None)})
        result["tracks"][t] = {"reference": refs[t]["basis"], "rows": len(trows),
                               "distinct_tasks": len({x["task"] for x in trows}),
                               "levers": out,
                               "levers_with_instances": sum(1 for x in out if x["runs"])}
    return result


def render_lines(res):
    out = [f"- lever matrix {res['version']}; lexicon: `{res['source']}`",
           "- instance = config-field diff vs the track reference or vs the previous run of the "
           "same label; prompt levers = lexicon pattern presence in the run's prompt; dev-harness "
           "= notebook value vs the scorer; log levers have no config field (mentions only).",
           "- counts are `rows / distinct tasks` of the runs carrying an instance (never pooled "
           "across tracks); per-task = `task:resolvedR/rows`."]
    for t in TRACKS:
        tr = res["tracks"].get(t)
        if not tr:
            continue
        out += ["", f"### Track: {t} ({tr['rows']} rows / {tr['distinct_tasks']} distinct tasks; "
                    f"reference: {tr['reference']}; levers with instances: "
                    f"{tr['levers_with_instances']}/{len(tr['levers'])})", "",
                "| lever | kind | runs | rows/distinct | labels/arms | stack | transitions "
                "| per-task outcomes | LB refs | log mentions | latest verdict |",
                "|---|---|---|---|---|---|---|---|---|---|---|"]
        for x in tr["levers"]:
            labs = ", ".join(x["labels"][:6]) + (f" +{len(x['labels']) - 6}" if len(x["labels"]) > 6 else "")
            st = ", ".join(f"{k}:{v}" for k, v in x["stack"].items())
            lv = (f"{x['latest_verdict']['claim_id']} L{x['latest_verdict']['line']} "
                  f"({x['latest_verdict']['status']})" if x["latest_verdict"] else "-")
            out.append(f"| {x['id']} | {x['kind']} | {x['runs']} | {x['rows']}/{x['distinct_tasks']} "
                       f"| {labs or '-'} | {st or '-'} | {'; '.join(x['transitions']) or '-'} "
                       f"| {x['per_task'] or '-'} | {', '.join(x['lb_refs']) or '-'} "
                       f"| {x['log_mentions']} | {lv} |".replace("\n", " "))
    return out
