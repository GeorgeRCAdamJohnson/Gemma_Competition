#!/usr/bin/env python3
"""build_kb.py â€” the Gemma knowledge-base builder (design Â§15).

One idempotent entrypoint. Offline by default (network only in `pull`).
Stdlib only. Deterministic ordering; safe to re-run (second run's generated
outputs identical except the build stamp).

Commands:
  build        parse all run artifacts -> runs.jsonl, tasks_gold.json,
               near_miss.jsonl, log_claims.{md,jsonl}, KB_SUMMARY.md,
               build_meta.json, build_stamp.json, build_log.txt
  check-fresh  exit 0 fresh / 3 stale (compares input fingerprint vs build_meta)
  report-path  print an audit report path (workflow helper)
  verdict      merge two audit reports -> a new -final.md (stricter of two)
  leakcheck    scan a file for gold/problem-statement leakage
  preflight    validate workflow inputs
  card         print a run x task card from the KB
  claims       query log claims
  pull         read-only Kaggle pulls (kblib.kaggle): --submissions, --targets,
               --slug S, --max N, --force, --dry-run, --for-ref R
  replay       --task T (--run R | --candidate PATH | --gold) [--kind K] [--force]
               [--required-nodes added|hunk] [--deadline-s D] [--lock-wait-s W]
  gold-gate    --repo rich|fastapi [--tasks ...] [--deadline-s D]
               [--required-nodes added|hunk] (resumable via replays/gold/)
  gate-build   --audit <final.md> --base <G-rel dir> --name N --change-spec <json>
               create ONE new G/submit_<N>/ (refuses unless VERDICT: PROCEED);
               prints the push command for the USER, never runs it
  gate-check   --dir <gate dir>: declared changes only, _assemble.py exit 0,
               leakcheck --scope config, base untouched

Exit codes: 0 ok Â· 1 usage/validation Â· 3 stale Â· 4 clone-guard Â· 5 safe-write
            protected Â· 6 a Kaggle CLI call failed (pull) Â· 8 lock held.
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import sys
import time

sys.dont_write_bytecode = True
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from kblib import (  # noqa: E402
    paths, io, lock, discover, kernellog, traces, configs, gold,
    nearmiss, classify, claims, render, verdict, leak, replay,
    devharness, sources, attribution, levers, standing, goldcov, gitio, gatebuild,
)
from kblib import baseline as bl  # noqa: E402
# NOTE: kblib.kaggle (the network runner) is imported ONLY inside cmd_pull.

ENGINE_VERSIONS = {"fc": classify.FC_VERSION, "nm": nearmiss.NM_VERSION,
                   "cm": "cm-2", "rp": replay.RP_VERSION, "claims": claims.CL_VERSION,
                   "dh": devharness.DH_VERSION, "lv": levers.LV_VERSION}

# REV5 D5-6: the previous build's stamp, frozen so the "since the previous
# build" table is a pure function of the inputs (idempotent).
REV5_PRIOR_BUILD_UTC = "2026-10-16T07:16:10Z"
REV5_PRIOR_LOG_LINES = 10108

ROW_CONFIG_KEYS = ("max_tool_calls", "max_time_minutes", "max_turns",
                   "timeout_seconds", "thinking_budget", "model",
                   "temperature", "top_p", "top_k", "max_output_tokens",
                   "adapter", "tools", "prompt_sha256", "prompt_chars",
                   "out_of_scope", "prompt_file")


def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------- build

def _run_dir_trace_map(g, run_dir):
    """task -> trace file. Kaggle runs keep traces under results/traces; the
    local rig keeps them in traces/ directly under the run dir (REV5)."""
    d = g / run_dir
    out = {}
    for tdir in (d / "results" / "traces", d / "traces"):
        if tdir.is_dir():
            for tf in sorted(tdir.glob("trace_*.json")):
                out.setdefault(tf.stem[len("trace_"):], tf)
    return out


def _find_log(g, run_dir):
    d = g / run_dir
    for lf in sorted(d.glob("*.log")):
        return lf
    return None


def _submission_dir(g, run_dir):
    d = g / run_dir / "submission"
    return d if d.is_dir() else None


# ------------------------------------------------------- REV5 source adapters

class _RowCtx:
    """Shared state for the per-kind row adapters (one build)."""

    def __init__(self, g, disc, tasks_gold, gold_index):
        self.g = g
        self.disc = disc
        self.tasks_gold = tasks_gold
        self.gold_index = gold_index
        self.rows = []
        self.nm_rows = []
        self.fp_rows = []
        self.trace_file_count = 0
        self.rows_by_source = {}     # G-rel source path -> rows produced
        self.kernel_dirs = disc.get("kernel_dirs", {})
        self.slug_dirs = {}
        for k, info in self.kernel_dirs.items():
            self.slug_dirs.setdefault(info["id"].split("/", 1)[-1], []).append(k)
        self.dh_cache = {}
        self.scorer_ref = devharness.scorer_reference(g / "comp_files" / "HARNESS_README.md")
        # REV5 D5-10: attribution inputs (LB source rows + local submission zips)
        self.lb_rows = []
        self.zip_path_by_ref = attribution.local_submission_zips(g)
        self.zip_hash_by_ref = {}
        for ref, rel in sorted(self.zip_path_by_ref.items()):
            zh = attribution.zip_hashes(g / rel)
            if zh is not None:
                self.zip_hash_by_ref[ref] = zh
        self.pulled_attr = []        # one record per pulled run (KB_SUMMARY Â§7)


def _config_for_run(g, rd):
    sub = _submission_dir(g, rd)
    if sub is not None:
        return configs.extract_config(sub, "run submission folder")
    adir = sources.agent_dir_config(g / rd)
    if adir is not None:
        return configs.extract_config(adir, f"agent dir {paths.rel_posix(adir, g)}")
    return configs.extract_config(None)


def _owner_kernel(ctx, rd):
    parts = rd.split("/")
    for i in range(len(parts), 0, -1):
        cand = "/".join(parts[:i])
        if cand in ctx.kernel_dirs:
            return cand
    return None


def _dh_scan(ctx, rel):
    if rel not in ctx.dh_cache:
        info = ctx.kernel_dirs.get(rel, {})
        ctx.dh_cache[rel] = devharness.scan_dir(ctx.g / rel, info.get("code_file"))
    return ctx.dh_cache[rel]


def _dev_harness_for(ctx, rd, log_path):
    """D5-8: notebook values for the run (own dir/source, nearest ancestor
    kernel dir, else the kernel dir whose slug equals the log name)."""
    basis = None
    rec = None
    for rel, b in ((rd + "/source", "pulled source"), (rd, "run dir")):
        if devharness.notebook_files(ctx.g / rel):
            rec, basis = _dh_scan(ctx, rel), b
            break
    if rec is None:
        owner = _owner_kernel(ctx, rd)
        if owner and devharness.notebook_files(ctx.g / owner):
            rec, basis = _dh_scan(ctx, owner), "ancestor kernel dir"
    if rec is None and log_path is not None:
        dirs = sorted(ctx.slug_dirs.get(pathlib.Path(log_path).stem, []))
        dirs = [d for d in dirs if devharness.notebook_files(ctx.g / d)]
        if dirs:
            rec = _dh_scan(ctx, dirs[0])
            basis = ("log-name slug match" if len(dirs) == 1 else
                     f"log-name slug match (ambiguous: {len(dirs)} kernel dirs; first sorted)")
    if rec is None:
        return None
    out = dict(rec)
    out["basis"] = basis
    m, mism = devharness.matches_scorer(rec, ctx.scorer_ref)
    out["matches_scorer"] = m
    out["mismatch_fields"] = mism
    return out


def _label_from_slug(slug):
    slug = slug.split("/", 1)[-1]
    if slug.startswith("gemma-sibling-conform-"):
        return slug[len("gemma-sibling-conform-"):]
    if slug.startswith("gemma-submission-packager"):
        return "packager" + slug[len("gemma-submission-packager"):]
    return slug


def _label_for_run(ctx, rd, log_path, is_pasted):
    parts = rd.split("/")
    legacy = (is_pasted or re.match(r"submit_v\d", parts[0]) or parts[0] == "Outputs"
              or parts[0].startswith(("_v", "v2_gate")))
    if legacy:
        return _label_for(ctx.g, rd, is_pasted)
    owner = _owner_kernel(ctx, rd)
    if owner:
        return _label_from_slug(ctx.kernel_dirs[owner]["id"])
    if log_path is not None:
        return _label_from_slug(pathlib.Path(log_path).stem)
    return _label_for(ctx.g, rd, is_pasted)


def _slim_trace_for_fp(tr):
    # cross_task_fp only reads edit calls' NEW side; keep memory bounded.
    return {"_calls": [c for c in tr.get("_calls", []) if c.get("is_edit")]}


def _emit_row(ctx, *, run_id, task, outcome, outcome_source, trace_path, events,
              cfg, label, run_kind, stack, track, track_basis, arm=None, rep=None,
              patch_trusted=None, summary_disagrees=None, dev_harness=None,
              attribution_rec=None):
    tasks_gold = ctx.tasks_gold
    tr = None
    if trace_path is not None:
        harness_tc = outcome.get("tool_calls") if outcome else None
        tr = traces.parse_trace(trace_path, harness_tool_calls=harness_tc)
        if tr and "trace_error" in tr:
            tr = None
    gt = tasks_gold["tasks"].get(task)
    gt_nm = dict(gt, _task_id=task) if gt else None
    nm = nearmiss.compute(tr, outcome, gt_nm, index=ctx.gold_index)
    if tr is not None:
        ctx.fp_rows.append({"task": task, "_trace": _slim_trace_for_fp(tr)})
    fc, sub, reason, ev = classify.classify(outcome, tr, nm, events, cfg, {"chosen": label})
    row = {
        "row_id": f"{run_id}::{task}",
        "run_id": run_id, "task": task,
        "repo": gt["repo"] if gt else _repo_of(task),
        "version_label": label,
        "run_kind": run_kind,
        "config": {k: cfg.get(k) for k in ROW_CONFIG_KEYS},
        "config_confidence": cfg.get("config_confidence"),
        "outcome": outcome,
        "outcome_source": outcome_source,
        "harness_events": events,
        "trace": _strip_internal(tr) if tr else None,
        "failure_class": fc, "failure_subclass": sub,
        "failure_class_reason": reason,
        "failure_evidence": ev,
        "class_version": classify.FC_VERSION,
        "stack": stack, "track": track, "track_basis": track_basis,
        "arm": arm, "rep": rep,
        "patch_trusted": patch_trusted,
        "summary_disagrees": summary_disagrees,
        "dev_harness": dev_harness,
    }
    if attribution_rec is not None:
        row["attribution"] = attribution_rec
    ctx.rows.append(row)
    nmrow = {"row_id": row["row_id"], "run_id": run_id, "task": task}
    nmrow.update(nm)
    ctx.nm_rows.append(nmrow)
    ctx.rows_by_source[run_id] = ctx.rows_by_source.get(run_id, 0) + 1


def _rows_kernel_run(ctx, rd, run_kind, is_pasted=False):
    """Kaggle kernel output (run dir, full-129 eval run, pulled run) or pasted log."""
    g = ctx.g
    log_path = (g / rd) if is_pasted else _find_log(g, rd)
    parsed = kernellog.parse_log(log_path) if log_path and log_path.is_file() else \
        {"outcomes": {}, "events": [], "run_level": {}, "is_json": False}
    trace_map = {} if is_pasted else _run_dir_trace_map(g, rd)
    ctx.trace_file_count += len(trace_map)
    outcomes = dict(parsed["outcomes"])
    src = {t: "kernel-log" for t in outcomes}
    summ = None
    if not is_pasted:
        d = g / rd
        trp = discover.task_results_path(d)
        tr_out = sources.outcomes_from_task_results(trp) if trp else {}
        for t, o in tr_out.items():
            if t not in outcomes:
                outcomes[t], src[t] = o, "task_results"
        rec = d / "recovered_full129.json"
        if rec.is_file():
            for t, o in sources.outcomes_from_recovered(rec).items():
                if t not in outcomes:
                    outcomes[t], src[t] = o, "recovered-proxy"
        for sp in (d / "results" / "summary.json", d / "summary.json"):
            if sp.is_file() and tr_out:
                summ = sources.summary_disagrees(sp, tr_out, len(trace_map))
                break
    cfg = configs.extract_config(None) if is_pasted else _config_for_run(g, rd)
    label = _label_for_run(ctx, rd, log_path, is_pasted)
    model = cfg.get("model")
    served = (parsed.get("run_level") or {}).get("served_model_ids") or []
    stack, track, basis = sources.stack_and_track(
        "kaggle", model, bool(model and model in served), "harness", label)
    dh = None if is_pasted else _dev_harness_for(ctx, rd, log_path)
    attr = None
    if run_kind in ("kaggle-pulled", "kaggle-pulled-legacy"):
        attr = _pulled_attribution(ctx, rd, run_kind, label, cfg)
    for task in sorted(set(outcomes) | set(trace_map)):
        _emit_row(ctx, run_id=rd, task=task, outcome=outcomes.get(task),
                  outcome_source=src.get(task), trace_path=trace_map.get(task),
                  events=[e for e in parsed["events"] if e.get("task") == task],
                  cfg=cfg, label=label, run_kind=run_kind, stack=stack, track=track,
                  track_basis=basis, summary_disagrees=summ, dev_harness=dh,
                  attribution_rec=attr)


def _pulled_attribution(ctx, rd, run_kind, label, cfg):
    """D5-10: compare a pulled run's config/package with every mapped submission."""
    d = ctx.g / rd
    meta = _read_json(d / "_pull_meta.json", {}) if run_kind == "kaggle-pulled" else {}
    slug = (meta.get("slug") or "").split("/", 1)[-1] or None
    if slug is None:
        lf = _find_log(ctx.g, rd)
        slug = lf.stem.lower() if lf else None
    hashes = attribution.pulled_package_hashes(d)
    mapped = attribution.map_refs(label, slug, ctx.lb_rows, hashes, ctx.zip_hash_by_ref,
                                  for_ref=meta.get("for_ref"))
    per_ref = attribution.attribute(cfg, hashes, mapped, ctx.zip_hash_by_ref,
                                    ctx.zip_path_by_ref)
    rec = {
        "version": attribution.AT_VERSION,
        "kind": "latest-at-pull" if run_kind == "kaggle-pulled" else
                "manual-legacy (no _pull_meta.json; treated as latest-at-pull)",
        "slug": slug, "label": label,
        "pull_utc": meta.get("pull_utc"),
        "deleted": meta.get("deleted", []),
        "per_ref": per_ref,
        "explains_refs": sorted(r["ref"] for r in per_ref
                                if r["flag"] == attribution.CONFIRMED),
    }
    ctx.pulled_attr.append(dict(rec, run_id=rd))
    return rec


def _rows_rig_run(ctx, rd):
    """Local parity-rig run: traces/ + task_results.jsonl in the run dir."""
    g = ctx.g
    d = g / rd
    trace_map = _run_dir_trace_map(g, rd)
    ctx.trace_file_count += len(trace_map)
    outcomes = sources.outcomes_from_task_results(d / "task_results.jsonl")
    summ = sources.summary_disagrees(d / "summary.json", outcomes, len(trace_map)) \
        if (d / "summary.json").is_file() else None
    arm, rep = sources.rig_arm_and_rep(rd)
    adir = sources.rig_arm_config(g, arm)
    if adir is not None:
        cfg = configs.extract_config(adir, f"rig arm dir {paths.rel_posix(adir, g)}")
    else:
        cfg = {"config_confidence": "none"}
    label = arm or rd.split("/")[-1]
    stack, track, basis = sources.stack_and_track(
        "local-rig", cfg.get("model"), False, "rig-local", label)
    for task in sorted(set(outcomes) | set(trace_map)):
        _emit_row(ctx, run_id=rd, task=task, outcome=outcomes.get(task),
                  outcome_source="task_results" if task in outcomes else None,
                  trace_path=trace_map.get(task), events=[], cfg=cfg, label=label,
                  run_kind="local-rig", stack=stack, track=track, track_basis=basis,
                  arm=arm, rep=rep, summary_disagrees=summ, dev_harness=None)


def _rows_sweep_tag(ctx, tag):
    """Local sweep tag (D5-4): summary-only rows, no trace."""
    files = ctx.disc["sweep_tag_files"].get(tag, {})
    run_id = paths.SWEEP_ROOT + "/" + tag
    for sr in sources.sweep_rows(tag, files, ctx.g):
        cfg = sr["config"]
        label = sr["arm"] or discover.sweep_family(tag)
        stack, track, basis = sources.stack_and_track(
            "local-sweep", cfg.get("model"), False, sr["scorer"], label)
        _emit_row(ctx, run_id=run_id, task=sr["task"], outcome=sr["outcome"],
                  outcome_source=sr["scorer"], trace_path=None, events=[], cfg=cfg,
                  label=label, run_kind="local-sweep", stack=stack, track=track,
                  track_basis=basis, arm=sr["arm"], rep=sr["rep"],
                  patch_trusted=sr["patch_trusted"], dev_harness=None)


def _pkg_files(d):
    out = [d / "agent.yaml", d / "eval_config.yaml", d / "configs" / "sampling.yaml"]
    pd = d / "prompts"
    if pd.is_dir():
        out += sorted(pd.glob("*.md"))
    return out


def _input_files(g, disc):
    """Every file the build reads (fingerprint; shared by build + check-fresh)."""
    files = list(disc["read_files"])
    for rd in disc["run_dirs"] + disc["eval_runs"] + disc["pulled_runs"]:
        d = g / rd
        lf = _find_log(g, rd)
        if lf:
            files.append(lf)
        files += list(_run_dir_trace_map(g, rd).values())
        trp = discover.task_results_path(d)
        if trp:
            files.append(trp)
        files += [d / "recovered_full129.json", d / "summary.json",
                  d / "results" / "summary.json", d / "_pull_meta.json"]
        files += _pkg_files(d / "submission")
        adir = sources.agent_dir_config(d)
        if adir is not None:
            files += _pkg_files(adir)
    for rd in disc["rig_runs"]:
        d = g / rd
        files += list(_run_dir_trace_map(g, rd).values())
        files += [d / "task_results.jsonl", d / "summary.json"]
        adir = sources.rig_arm_config(g, sources.rig_arm_and_rep(rd)[0])
        if adir is not None:
            files += _pkg_files(adir)
    for tag in disc["sweep_tags"]:
        for suf in ("results", "pinned", "guard"):
            rel = disc["sweep_tag_files"].get(tag, {}).get(suf)
            if rel:
                files.append(g / rel)
    for s in disc["staged_submissions"]:
        files += _pkg_files(g / s) + [g / s / "submission.zip"]
    for s in disc["scored_zips"]:
        files += _pkg_files(g / s / "submission") + [g / s / "submission.zip"]
    for z in disc["zip_archives"] + disc["lb_snapshots"]:
        files.append(g / z)
    for k in disc["kernel_dirs"]:
        files.append(g / k / "kernel-metadata.json")
        files += devharness.notebook_files(g / k)
    for rd in disc["pulled_runs"]:
        files += devharness.notebook_files(g / rd / "source")
        files.append(g / rd / "submission.zip")
    # REV5 D5-12: pulled submissions snapshots choose the LB source
    snap = g / "kb" / "pulled" / "submissions"
    if snap.is_dir():
        files += sorted(snap.glob("*.csv"))
    files.append(_HERE / "kblib" / "lever_lexicon_default.json")
    # FEAT-003: sweep prompt files read by the prompt-lever pass (levers.py),
    # and the user's rp-4 gold-gate file read by STANDING_TRUTHS.md
    pdir = g / "local_eval" / "prompts"
    if pdir.is_dir():
        files += sorted(pdir.glob("*.md"))
    files.append(g / "kb" / "replays" / "goldgate_all.json")
    # FEAT-004: gold coverage (§13a/§13b) reads the rp-5 gold records and the
    # decode-sweep reference (read-only)
    gdir = g / "kb" / "replays" / "gold"
    if gdir.is_dir():
        files += sorted(gdir.glob("*.json")) + sorted(gdir.glob("hunk/*.json"))
    ds = g / "kb" / "audits" / "_decode_sweep_cache" / "gold_gate.json"
    if ds.is_file():
        files.append(ds)
    return files


def cmd_build(args):
    g = paths.gemma_root()
    kb = paths.kb_root()
    t0 = time.time()
    with lock.BuildLock(kb) as lk:
        try:
            lk.acquire(wait_s=args.lock_wait_s or 0.0)
        except TimeoutError:
            print("build lock held by a live process", file=sys.stderr)
            return 8

        disc = discover.discover(g)
        fp = discover.input_fingerprint(g, _input_files(g, disc))

        # --- gold ---
        tasks_gold = gold.build_tasks_gold(g / "comp_files" / "tasks.jsonl")
        gold_index = nearmiss.GoldIndex(tasks_gold)

        # --- per (run, task) rows: one source adapter per kind (REV5 R5.3) ---
        ctx = _RowCtx(g, disc, tasks_gold, gold_index)
        lb_src = bl.lb_source(kb)                      # D5-12
        ctx.lb_rows = lb_src["rows"]
        for rd in disc["run_dirs"]:
            _rows_kernel_run(ctx, rd, "kaggle-kernel")
        for rd in disc["eval_runs"]:
            _rows_kernel_run(ctx, rd, "kaggle-kernel")
        for rd in disc["pulled_runs"]:
            kind = ("kaggle-pulled" if (g / rd / "_pull_meta.json").is_file()
                    else "kaggle-pulled-legacy")
            _rows_kernel_run(ctx, rd, kind)
        for rd in disc["pasted_logs"]:
            _rows_kernel_run(ctx, rd, "pasted-log", is_pasted=True)
        for rd in disc["rig_runs"]:
            _rows_rig_run(ctx, rd)
        for tag in disc["sweep_tags"]:
            _rows_sweep_tag(ctx, tag)
        rows, nm_rows = ctx.rows, ctx.nm_rows
        trace_rows_for_fp = ctx.fp_rows
        trace_file_count = ctx.trace_file_count

        rows.sort(key=lambda r: r["row_id"])
        nm_rows.sort(key=lambda r: r["row_id"])

        # --- cross-task false-positive control (Â§9.4) ---
        nm_fp = nearmiss.cross_task_fp(trace_rows_for_fp, tasks_gold, gold_index)

        # --- replay (gold-first, cached, bounded) ---
        replay_records = []
        replay_stop_reason = None
        replays_pending = 0
        clone_state = None
        if args.replay:
            replay_records, replay_stop_reason, replays_pending, clone_state = \
                _run_replays(g, tasks_gold, rows, t0, args)
        else:
            replay_records = _read_cached_replays(tasks_gold, rows)

        # --- claims ---
        log_text, _ = io.read_text_bomaware(g / "GEMMA_EXPERIMENT_LOG.md")
        run_labels = _read_json(kb / "curated" / "run_labels.json", {})
        baseline = run_labels.get("baseline", {})
        lexicon = levers.load_lexicon(kb, _HERE / "kblib")
        cl = claims.extract(
            log_text, lb_src["rows"],
            kb / "curated" / "claims.jsonl", baseline, rows,
            lb_source_path=lb_src["path"], run_labels=run_labels,
            lexicon_fn=levers.log_matcher(lexicon))

        # --- baselines per track, banner from the steering text (D5-13) ---
        steering = bl.steering_baseline(g.parent / ".kiro" / "steering" /
                                        "gemma-submission-protocol.md")
        lb_best = bl.track_best(lb_src["rows"])
        proposals_md = bl.proposed_updates(
            run_labels, lb_src, lb_best, steering,
            lexicon_default_path=_HERE / "kblib" / "lever_lexicon_default.json",
            replay_missing=_replay_missing(kb, rows))

        # --- render ---
        stamp_lines, build_utc = _stamp_lines(fp)
        banner = bl.banner(steering, baseline, lb_best, lb_src["path"])
        coverage = _coverage_lines(disc, trace_file_count, len(rows))
        coverage += _rev5_coverage_lines(g, disc, rows, log_text, ctx)
        matrix = _matrix_lines(rows)
        harness = _harness_lines(rows, ctx.scorer_ref)
        lever_res = levers.compute(g, rows, cl, lexicon, baseline.get("label"),
                                   lb_src["rows"], ctx.scorer_ref)
        lever_section = levers.render_lines(lever_res)
        standing_text = standing.render(
            g, fp["fingerprint"][:12], cl, baseline, lb_src, lb_best, steering,
            bl.conflicts(steering, baseline, lb_best), rows, ctx.scorer_ref,
            ctx.pulled_attr)
        lb_section = _lb_lines(cl, baseline, lb_src, lb_best, run_labels, steering,
                               ctx.pulled_attr)
        claims_summary = _claims_summary(cl)
        nearmiss_section = _nearmiss_lines(nm_rows, nm_fp)
        replay_section = _replay_lines(replay_records, replay_stop_reason,
                                       replays_pending, clone_state, args.replay)
        gold_cov = goldcov.build(kb, tasks_gold,
                                 replay.load_raw_tasks(g / "comp_files" / "tasks.jsonl"),
                                 replay.RP_VERSION)
        replay_section += goldcov.render_lines(gold_cov)
        limitations = _limitations_lines(tasks_gold, rows)

        kb_summary_text = render.kb_summary(
            stamp_lines, banner, None, coverage, matrix, harness, lever_section,
            lb_section, claims_summary, nearmiss_section, replay_section,
            limitations)

        # --- write outputs (safe_write, atomic, skip-identical) ---
        generated = []
        _write(kb / "tasks_gold.json", io.dumps_json(tasks_gold), generated)
        _write(kb / "runs.jsonl", io.dumps_jsonl(rows), generated)
        _write(kb / "near_miss.jsonl", io.dumps_jsonl(nm_rows), generated)
        _write(kb / "log_claims.jsonl", io.dumps_jsonl(cl["claims"]), generated)
        _write(kb / "log_claims.md", _log_claims_md(stamp_lines, cl, log_text), generated)
        _write(kb / "KB_SUMMARY.md", kb_summary_text, generated)
        _write(kb / "STANDING_TRUTHS.md", standing_text, generated)
        # D5-14: the ONE generated file under curated/ (exact-path allowlist)
        io.safe_write(kb / "curated" / "_proposed_updates.md", proposals_md)
        generated.append("curated/_proposed_updates.md")
        # D5-22: gold coverage (pure function of the gold records + references)
        io.safe_write(kb / "replays" / "gold_coverage.json", io.dumps_json(gold_cov))
        generated.append("replays/gold_coverage.json")

        from collections import Counter as _Counter
        counts = {"runs_rows": len(rows), "run_dirs": len(disc["run_dirs"]),
                  "pasted_logs": len(disc["pasted_logs"]), "tasks_gold": len(tasks_gold["tasks"]),
                  "traces": trace_file_count, "claims": len(cl["claims"]),
                  "eval_runs": len(disc["eval_runs"]), "rig_runs": len(disc["rig_runs"]),
                  "pulled_runs": len(disc["pulled_runs"]),
                  "sweep_tags": len(disc["sweep_tags"]),
                  "rows_by_run_kind": dict(sorted(_Counter(r["run_kind"] for r in rows).items())),
                  "rows_by_track": dict(sorted(_Counter(r["track"] for r in rows).items()))}
        newest = _newest_input(fp, g)
        build_meta = {
            "schema": "build_meta/3",
            "gemma_root": str(g),
            "inputs_fingerprint": fp["fingerprint"],
            "discovery_fingerprint": _discovery_fp(disc),
            "inputs_count": fp["count"],
            "newest_input": newest,
            "log_sha256": io.sha256_text(log_text),
            "log_lines": log_text.count("\n") + 1,
            "counts": counts,
            "replays_pending": replays_pending,
            "near_miss_fp": nm_fp,
            "warnings": 0,
            "engine_versions": ENGINE_VERSIONS,
            "generated_files": [],
        }
        # generated_files is finalized after we know all names
        gen_names = sorted(set(generated) | {
            "tasks_gold.json", "runs.jsonl", "near_miss.jsonl", "log_claims.jsonl",
            "log_claims.md", "KB_SUMMARY.md", "STANDING_TRUTHS.md", "build_meta.json",
            "build_log.txt",
            "build_stamp.json"})
        build_meta["generated_files"] = gen_names
        _write(kb / "build_meta.json", io.dumps_json(build_meta), generated)

        # replay artifacts (add-only cache already written per candidate;
        # replays.jsonl + clone_state.json are generated outputs)
        if replay_records or args.replay:
            clean = []
            for r in replay_records:
                clean.append({k: v for k, v in r.items() if k != "from_cache"})
            io.safe_write(kb / "replays" / "replays.jsonl",
                          io.dumps_jsonl(sorted(clean,
                                                key=lambda r: (r.get("task", ""),
                                                               r.get("run_id", ""),
                                                               r.get("kind", ""),
                                                               r.get("candidate_sha", "")))))
        if clone_state is not None:
            io.safe_write(kb / "replays" / "clone_state.json",
                          io.dumps_json(clone_state))

        duration = round(time.time() - t0, 2)
        build_stamp = {"schema": "build_stamp/1", "build_utc": build_utc,
                       "duration_s": duration, "cli_args": sys.argv[1:],
                       "replays_run_this_build": sum(1 for r in replay_records
                                                     if not r.get("from_cache")),
                       "replay_stop_reason": replay_stop_reason,
                       "replays_pending": replays_pending}
        if args.replay:
            build_stamp.update({k: _REPLAY_STATS.get(k) for k in (
                "gold_controls_run_this_build", "tiers_left", "replay_scope",
                "required_nodes", "targets", "env_freeze_check")})
            _write_clone_status_final(kb)
        io.safe_write(kb / "build_stamp.json", io.dumps_json(build_stamp))

        # build_log.txt is compared by the idempotence check; keep its non-stamp
        # content a pure function of inputs (no duration/wall-clock below the stamp).
        log_tail = (f"Build stamp: built {build_utc}\n"
                    f"BUILD OK runs={len(rows)} tasks_gold={len(tasks_gold['tasks'])} "
                    f"traces={trace_file_count} claims={len(cl['claims'])} "
                    f"replays_pending={replays_pending}\n")
        # D5-19d: PIN-FALLBACK warnings (sorted, unique)
        for w in sorted(set(replay.WARNINGS)):
            log_tail += f"WARNING {w}\n"
        io.safe_write(kb / "build_log.txt", log_tail)

        # Machine-readable mirror of the log: index EVERY `## ` unit, not only the
        # units that yield a curated claim. Keeps retrieval from depending on grep
        # discipline against a 15k-line markdown file.
        try:
            from kblib import logdb as _logdb
            _db_stats = _logdb.build_logdb(kb, log_text, cl["claims"], tasks_gold)
            generated.append("logdb.sqlite")
            print(f"LOGDB OK units={_db_stats['units']} claims={_db_stats['claims']} "
                  f"tasks={_db_stats['tasks']}")
        except Exception as _e:  # never fail the main build over the index
            print(f"LOGDB WARN: {type(_e).__name__}: {_e}")

    print(f"BUILD OK runs={len(rows)} tasks_gold={len(tasks_gold['tasks'])} "
          f"traces={trace_file_count} duration_s={duration} "
          f"replays_pending={replays_pending}")
    return 0


# ---------------------------------------------------------------- build helpers

def _strip_internal(tr):
    tr = dict(tr)
    tr.pop("_calls", None)
    return tr


def _repo_of(task):
    pre = task.split("_")[0]
    return {"rich": "Textualize/rich", "fastapi": "fastapi/fastapi",
            "requests": "psf/requests", "httpx": "encode/httpx"}.get(pre, pre)


def _label_for(g, rd, is_pasted):
    # local-experiment: nearest ancestor submit_* dir token; else log/file name
    parts = rd.split("/")
    for p in parts:
        if p.startswith("submit_"):
            tok = p[len("submit_"):]
            # nested arm
            if parts[-1] not in (p, f"out_{tok}"):
                return (tok + "-" + parts[-2]).lower() if len(parts) > 2 else tok.lower()
            return tok.lower()
    base = parts[-1]
    base = re.sub(r"^gemma-sibling-conform-", "", base)
    base = re.sub(r"\.log$", "", base)
    return base.replace("_", "-").lower()


def _read_json(p, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path, data, generated):
    io.safe_write(path, data)
    generated.append(path.name)


def _stamp_lines(fp):
    build_utc = _utc_now()
    fp12 = fp["fingerprint"][:12]
    cf = r"python c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\build_kb.py check-fresh"
    l1 = f"<!-- build-stamp: built={build_utc} inputs={fp12} discovery={fp12} -->"
    l2 = f"Build stamp: built {build_utc} Â· inputs {fp12} Â· freshness check: {cf}"
    return [l1, l2], build_utc


def _replay_missing(kb, rows):
    """curated replay_set min-set run ids with no row in this build (D5-14)."""
    run_ids = {r["run_id"] for r in rows}
    rs = _read_json(kb / "curated" / "replay_set.json", {})
    return sorted({f"{e.get('run_id')} ({e.get('task')})" for e in rs.get("min_set", [])
                   if e.get("run_id") not in run_ids})


def _newest_input(fp, g):
    newest = None
    newest_mtime = -1
    for rel, (size, mtime_ns) in fp["files"].items():
        if mtime_ns > newest_mtime:
            newest_mtime = mtime_ns
            newest = rel
    if newest is None:
        return {"path": None, "mtime_utc": None}
    mt = datetime.datetime.fromtimestamp(newest_mtime / 1e9, datetime.timezone.utc)
    return {"path": newest, "mtime_utc": mt.strftime("%Y-%m-%dT%H:%M:%SZ")}


def _discovery_fp(disc):
    blob = "\n".join(sorted(disc["run_dirs"] + disc["pasted_logs"]
                            + disc["failed_run_dirs"] + disc["empty_run_dirs"]
                            + disc["eval_runs"] + disc["rig_runs"] + disc["pulled_runs"]
                            + ["sweep:" + t for t in disc["sweep_tags"]]
                            + disc["staged_submissions"] + disc["scored_zips"]
                            + disc["zip_archives"] + disc["partials"]
                            + list(disc["kernel_dirs"])))
    return io.sha256_text(blob)[:12]


def _utc_epoch(s):
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc).timestamp()


def _item_mtime(g, disc, it):
    """Newest mtime of a discovered source (dir: itself + direct children;
    sweep tag: its files)."""
    paths_ = []
    if it.kind == "sweep-tag" and it.g_rel.startswith(paths.SWEEP_ROOT + "/"):
        tag = it.g_rel[len(paths.SWEEP_ROOT) + 1:]
        rels = list(disc["sweep_tag_files"].get(tag, {}).values()) + \
            list(disc["sweep_aux"].get(tag, []))
        paths_ = [g / r for r in rels] or [g / it.g_rel]
    else:
        p = g / it.g_rel
        paths_ = [p]
        if p.is_dir():
            try:
                paths_ += list(p.iterdir())
            except OSError:
                pass
    best = None
    for p in paths_:
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        best = m if best is None else max(best, m)
    return best


def _rev5_coverage_lines(g, disc, rows, log_text, ctx):
    """REV5 Â§2 additions: rows by stack/track, staged + scored zips with config
    and zip_drift, and the 'since the previous build' table (D5-6)."""
    from collections import Counter, defaultdict
    out = ["", "### Rows by run_kind / track (REV5 R5.2)"]
    kinds = Counter(r["run_kind"] for r in rows)
    tracks = Counter((r["stack"]["platform"], r["track"]) for r in rows)
    out.append("- by run_kind: " + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
    out.append("- by (platform, track): " + ", ".join(
        f"{p}/{t}={v}" for (p, t), v in sorted(tracks.items())))
    out.append(f"- kaggle-eval-runs: {len(disc['eval_runs'])}; rig-runs: "
               f"{len(disc['rig_runs'])}; sweep-tags: {len(disc['sweep_tags'])}; "
               f"pulled-runs: {disc['pulled_runs']}; partial: {disc['partials']}")
    out.append(f"- foreign tools (listed, never run): {disc['foreign_tools']}")
    out.append(f"- reference kernels (not ours): {disc['reference_kernels']}")
    out.append(f"- outcome sources: " + ", ".join(
        f"{k}={v}" for k, v in sorted(Counter(str(r.get('outcome_source'))
                                              for r in rows).items())))

    out += ["", "### Staged submissions and scored zips (D3-4: config + zip_drift)",
            "| dir | kind | zip_drift | config |", "|---|---|---|---|"]
    for s in disc["staged_submissions"]:
        cfg = configs.extract_config(g / s, "staged dir")
        out.append(f"| {s} | staged-submission | {configs.zip_drift(g / s)} | "
                   f"{configs.config_one_liner(cfg)} |")
    for s in disc["scored_zips"]:
        cfg = configs.extract_config(g / s / "submission", "scored-zip submission/")
        out.append(f"| {s} | scored-zip | "
                   f"{configs.zip_drift(g / s / 'submission', g / s / 'submission.zip')} | "
                   f"{configs.config_one_liner(cfg)} |")
    out.append(f"- submission zip archives (local_eval/pull_submissions): {disc['zip_archives']}")
    out.append(f"- LB snapshots: {disc['lb_snapshots']}")

    # --- since the previous build ---
    prior = _utc_epoch(REV5_PRIOR_BUILD_UTC)
    groups = defaultdict(list)
    for it in disc["items"]:
        mt = _item_mtime(g, disc, it)
        if mt is None or mt <= prior:
            continue
        if it.kind == "sweep-tag" and it.g_rel.startswith(paths.SWEEP_ROOT + "/"):
            tag = it.g_rel[len(paths.SWEEP_ROOT) + 1:]
            fam = discover.sweep_family(tag)
            parent = f"{paths.SWEEP_ROOT}/{fam}*"
            member = tag
        else:
            parent, _, member = it.g_rel.rpartition("/")
        reason = it.reason
        if it.parsed and it.kind in ("run-dir", "kaggle-eval-run", "rig-run",
                                     "pulled-run", "pulled-legacy", "sweep-tag"):
            tail = "rows emitted" if ctx.rows_by_source.get(it.g_rel) else "0 rows"
            reason = (reason + "; " if reason else "") + tail
        groups[(it.kind, parent, it.parsed, reason)].append((member, it.g_rel))
    n_new = sum(len(v) for v in groups.values())
    out += ["", f"### Since the previous build ({REV5_PRIOR_BUILD_UTC}; D5-6)",
            f"- {n_new} discovered sources have mtime newer than the previous build "
            f"stamp, in {len(groups)} groups (members listed per group).",
            "| kind | path | n | parsed | reason | members |", "|---|---|---|---|---|---|"]
    for (kind, parent, parsed, reason), members in sorted(
            groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2], kv[0][3])):
        members = sorted(members)
        if len(members) == 1:
            path, mem = members[0][1], "-"
        else:
            path = parent or "."
            mem = ", ".join(m for m, _ in members)
        out.append(f"| {kind} | {path} | {len(members)} | {'yes' if parsed else 'no'} | "
                   f"{(reason or '-').replace('|', '/')} | {mem.replace('|', '/')} |")
    # new log `## ` units by line range
    new_units = [i for i, ln in enumerate(log_text.split("\n"), 1)
                 if ln.startswith("## ") and i > REV5_PRIOR_LOG_LINES]
    if new_units:
        out.append(f"- GEMMA_EXPERIMENT_LOG.md: {len(new_units)} new `## ` units after "
                   f"L{REV5_PRIOR_LOG_LINES} (first L{new_units[0]}, last L{new_units[-1]}); "
                   "parsed: yes (claims engine).")
    else:
        out.append(f"- GEMMA_EXPERIMENT_LOG.md: no new `## ` units after L{REV5_PRIOR_LOG_LINES}.")
    return out


def _coverage_lines(disc, trace_count, n_rows):
    out = [
        f"- run-dirs parsed: {len(disc['run_dirs'])}",
        f"- run-dir-failed: {len(disc['failed_run_dirs'])} {disc['failed_run_dirs']}",
        f"- run-dir-empty: {len(disc['empty_run_dirs'])} {disc['empty_run_dirs']}",
        f"- pasted-logs: {len(disc['pasted_logs'])}",
        f"- reference-logs (not our runs, 0 rows): {disc['reference_logs']} "
        "[LIVE snapshot â€” this list reflects files present at build time; a file "
        "appearing/vanishing in local_eval/runs/ correctly trips freshness]",
        f"- staged-submissions: {disc['staged_submissions']}",
        f"- trace files parsed: {trace_count}",
        f"- runs.jsonl rows: {n_rows}",
        f"- beyond walk depth: {disc['beyond_depth']}",
    ]
    return out


def _matrix_lines(rows):
    tasks = {}
    for r in rows:
        tasks.setdefault(r["task"], {})[r["run_id"]] = render.cell_letter(
            r["failure_class"], r["failure_subclass"])
    runs = sorted({r["run_id"] for r in rows})
    lines = [f"- tasks attempted: {len(tasks)}; runs: {len(runs)}"]
    # compact summary counts rather than a giant table (deterministic)
    from collections import Counter
    cnt = Counter(render.cell_letter(r["failure_class"], r["failure_subclass"]) for r in rows)
    lines.append("- cell counts: " + ", ".join(f"{k}={v}" for k, v in sorted(cnt.items())))
    return lines


def _harness_lines(rows, scorer_ref=None):
    traced = [r for r in rows if r.get("trace")]
    with_h = [r for r in traced if r["trace"]["count_model"]["harness"] is not None]
    resid0 = sum(1 for r in with_h if r["trace"]["count_model"]["residual"] == 0)
    out = [
        "DOCUMENTED: tool_calls budget per HARNESS_README.md Â§6.1; submit_patch/"
        "get_status are free (count_tool_call=False).",
        f"MEASURED (count model cm-2): residual 0 on {resid0}/{len(with_h)} traces "
        f"that carry a harness tool_calls value.",
        "Scored state: last successful submit_patch snapshot, else the working tree "
        "when submit_patch was never called (README Â§6.1 tool 2 / Â§8.1).",
    ]
    # REV5 D5-8 / D3-5: dev-harness AST pass (dh-1)
    sr = scorer_ref or {}
    out.append("DOCUMENTED scorer EventsCompactionConfig (" + str(sr.get("source", "?")) + "): "
               + ", ".join(f"{k} = {sr[k]}" for k in devharness.SCORER_FIELDS if k in sr))
    per_run = {}
    for r in rows:
        per_run.setdefault(r["run_id"], (r.get("dev_harness"),
                                         (r.get("stack") or {}).get("platform", "?")))
    from collections import Counter
    cnt = Counter()
    unk = Counter()
    vals = Counter()
    for rid, (dh, plat) in per_run.items():
        m = (dh or {}).get("matches_scorer")
        key = "match" if m is True else "mismatch" if m is False else "unknown"
        cnt[key] += 1
        if key == "unknown":
            unk[plat] += 1
        if dh and dh.get("found"):
            vals[tuple((k, dh.get(k)) for k in devharness.SCORER_FIELDS)] += 1
    out.append(f"MEASURED (dev-harness AST pass dh-1, per run): matches scorer {cnt['match']}, "
               f"does NOT match {cnt['mismatch']}, unknown {cnt['unknown']} of "
               f"{len(per_run)} runs (unknown = no notebook or no EventsCompactionConfig "
               "call found; by platform: "
               + ", ".join(f"{k}={v}" for k, v in sorted(unk.items())) + ").")
    for key, n in sorted(vals.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        out.append("- dev notebook values " + ", ".join(f"{k}={v}" for k, v in key)
                   + f": {n} runs")
    return out


def _lb_lines(cl, baseline, src, lb_best, run_labels, steering, pulled_attr):
    """Â§7 from the LB source (D5-12..D5-14): every ref, per-track best, the
    curated pointer, stale curated entries, pulled outputs vs submissions."""
    out = [f"- LB source: `{src['path']}` â€” {src['reason']}",
           f"- dates: newest pulled snapshot {src['snapshot_utc'] or 'none'}; "
           f"curated/submissions.csv mtime {src['curated_mtime_utc'] or 'missing'}",
           f"- rows in LB source: {len(src['rows'])}", "",
           "| ref | date | status | publicScore | track | description |",
           "|---|---|---|---|---|---|"]
    rows = sorted(src["rows"], key=lambda r: (r.get("date", ""), str(r.get("ref"))),
                  reverse=True)
    for r in rows:
        st = (r.get("status") or "").replace("SubmissionStatus.", "")
        out.append(f"| {r.get('ref')} | {(r.get('date') or '')[:19]} | {st} | "
                   f"{r.get('publicScore') or '-'} | "
                   f"{attribution.description_track(r.get('description', ''))} | "
                   f"{bl.short_desc(r.get('description', ''), 90)} |")
    out.append("")
    for t in ("main", "small-model", "dev-proxy"):
        b = lb_best.get(t)
        if b:
            ties = f" (ties at this score: {b['tie_refs']})" if b["n_ties"] > 1 else ""
            out.append(f"- LB best {t}: {b['desc']} @ {b['score']:.2f} (ref {b['ref']}, "
                       f"{b['date'][:10]}){ties}")
        else:
            out.append(f"- LB best {t}: none COMPLETE with a score")
    out.append(f"- curated BASELINE pointer (policy, main track): {baseline.get('label')} @ "
               f"{baseline.get('lb')} (submission {baseline.get('submission_ref')})")
    out.append("- curated small-model baseline: "
               + ("set" if run_labels.get("small_model_baseline") else "none"))
    for c in bl.conflicts(steering, baseline, lb_best):
        out.append(f"- BASELINE CONFLICT: {c} â€” not adopted")
    by_ref = {str(r.get("ref")): r for r in src["rows"]}
    stale = {s["ref"]: s for s in bl.stale_pending(run_labels, src["rows"])}
    for p in run_labels.get("pending", []) or []:
        ref = str(p.get("submission_ref"))
        r = by_ref.get(ref)
        if r is not None:
            st = (r.get("status") or "").replace("SubmissionStatus.", "")
            out.append(f"- {p.get('label')} (ref {ref}): {st} {r.get('publicScore') or '-'} "
                       f"(from {src['path']})")
        if ref in stale:
            out.append(f"- curated run_labels.json pending[{p.get('label')}] says "
                       f"{p.get('status')} â€” stale (see curated/_proposed_updates.md)")
    out.append("- log-claim LB checks use the LB source above (scores: "
               + ", ".join(f"{s:.2f}" for s in sorted(cl["scored_submissions"])) + ")")
    out += ["", "### Pulled outputs vs submissions (D5-10; `kernels output` = latest version only)"]
    if not pulled_attr:
        out.append("- no pulled runs")
    for a in sorted(pulled_attr, key=lambda x: x["run_id"]):
        out.append(f"- `{a['run_id']}` slug={a['slug']} label={a['label']} kind={a['kind']} "
                   f"explains_refs={a['explains_refs']} deleted="
                   f"{[d['path'] for d in a.get('deleted') or []]}")
        if not a["per_ref"]:
            out.append("  - no submission maps to this pulled run")
        for pr in a["per_ref"]:
            out.append(f"  - ref {pr['ref']} [{'; '.join(pr['mapped_by'])}]: {pr['detail']}")
    return out


def _fact_brief(f):
    v = f.get("version") or "?"
    t = f" {f['task']}" if f.get("task") else ""
    val = f["value"] if not isinstance(f["value"], list) else "{" + ",".join(f["value"]) + "}"
    st = (f.get("check") or {}).get("status")
    return f"{f['field']} {v}{t}={val}" + (f":{st[:3]}" if st else "")


def _claims_summary(cl):
    from collections import Counter
    st = cl["stats"]
    by_status = dict(sorted(Counter(c["status"] for c in cl["claims"]).items()))
    out = [f"- engine {cl['cl_version']}: {st['claims']} claims from {st['units']} `##`/`###` units; "
           f"by status: {by_status}",
           f"- facts: {st['facts']}; auto-checked: {st['facts_checked']}; decided "
           f"(SUPPORTED/CONTRADICTED): {st['facts_decided']}; disagreements NOT asserted "
           f"(weak binding / different rep / budget sanity, listed in log_claims.md Â§3b): "
           f"{st['disagreements_not_asserted']}",
           f"- supersession: {st['superseded_claims']} claims SUPERSEDED in {st['chains']} chains "
           f"({st['links_applied']} applied links; {len(cl['unresolved_citations'])} unresolved "
           f"citations; {len(cl['candidate_links'])} keyword-overlap candidates, never applied)",
           f"- LB checks against `{cl.get('lb_source_path') or 'none'}`; F10 live-best claims are "
           "checked against curated/run_labels.json:baseline only (never adopted)"]
    chain = [x for x in cl["live_best_chain"] if x["polarity"] == "live-best"]
    steps = []
    for x in chain:
        if not steps or steps[-1][0] != x["version"]:
            steps.append((x["version"], x["line"]))
    out.append("- log live-best chain (F10, first line per change): "
               + " -> ".join(f"{v} L{ln}" for v, ln in steps) if steps else
               "- log live-best chain: none")
    out.append(f"- internal-consistency checks before any CONTRADICTED: {st['quoted_facts']} facts "
               f"inside quoted retractions (never asserted; {st['quoted_fact_links']} quoted-fact "
               f"supersession links); {st['self_disagreements']} facts where the log disagrees "
               f"with itself (log_claims.md §3c); {st['label_collisions']} label collision(s):")
    for h in cl["label_collisions"]:
        out.append(f"  - `{h['token']}` names experiment run(s) {h['experiment_runs_tasks']} AND "
                   f"kernel `{h['kernel_label']}` ({h['kernel_runs_tasks']} tasks); "
                   f"{h['n_log_kernel_version_lines']} log lines use it as the kernel version "
                   f"(e.g. L{', L'.join(str(x) for x in h['log_kernel_version_lines'][:4])}); "
                   f"`{h['token']} config`/`{h['token']} caps` route to the kernel; a bare "
                   f"`{h['token']}` never yields a CONTRADICTED")
    con = [c for c in cl["claims"] if c["status"] == "CONTRADICTED"]
    out.append(f"- CONTRADICTED claims: {len(con)}" + ("" if con else " (none at this build)"))
    for c in sorted(con, key=lambda x: x["line"])[:15]:
        bad = [f for f in c["facts"] if (f.get("check") or {}).get("status") == "CONTRADICTED"]
        f = bad[0] if bad else {}
        ev = (f.get("check") or {}).get("evidence") or [{}]
        out.append(f"  - {c['claim_id']} L{c['line']}: {_fact_brief(f) if f else '-'} â€” "
                   f"{(f.get('check') or {}).get('reason', '')[:160]} â€” evidence: "
                   f"{ev[0].get('path', 'GEMMA_EXPERIMENT_LOG.md')} {ev[0].get('note', '')}".rstrip())
    ok = sum(1 for c in cl["curated"] if c["evidence_ok"])
    out += [f"- curated claims merged: {len(cl['curated'])} ({ok} with all evidence paths present); "
            f"orphans {len(cl['orphans'])}; curation conflicts {len(cl['curation_conflicts'])}",
            "- full tables: log_claims.md; query: `build_kb.py claims --task/--version/--lever/"
            "--text/--status/--limit`"]
    return out


def _limitations_lines(tasks_gold, rows):
    rich = [k for k, v in tasks_gold["tasks"].items() if v["repo"] == "Textualize/rich"]
    ast_rich = sum(1 for k in rich if tasks_gold["tasks"][k]["functions_source"] == "ast@base_commit")
    return [
        f"- functions_source=ast@base_commit on {ast_rich}/{len(rich)} rich tasks; "
        "the 2 misses are pure new-file additions with no base file to parse.",
        "- IMPLEMENTED this iteration: static edit reconstruction (Â§8), near-miss "
        "line-level fuzzy matcher nm-3 (Â§9.2) + cross-task FP control (Â§9.4), and "
        "the gold-first git-worktree replay engine rp-3 (Â§13). See Â§10 and Â§13.",
        "- REV5 FEAT-001: dev-harness AST pass (D3-5, dh-1) and staged-submission "
        "config + zip_drift (D3-4) are implemented; see Â§2 and Â§9.",
        "- REV5 row scope: local-sweep rows are summary-only (no ATIF trace); "
        "local-rig and sweep rows never verify the served model "
        "(stack.model_served_verified=false).",
        "- REV5 FEAT-003: claims cl-4 (Â§12.1-Â§12.7: tables A/B/C, F1 bar/unit/keyed "
        "classifier, ref binding, supersession chains), lever matrix lv-1 (Â§6) and "
        "STANDING_TRUTHS.md are implemented. Heuristic limits: facts come from explicit "
        "regexes only; a disagreement is asserted (CONTRADICTED) only on a same-line / "
        "column / idiom binding to a run of the stack the entry names; weaker bindings "
        "are listed, not asserted (log_claims.md Â§3b).",
        "- lv-1 limits: run dates are not recorded, so `prev-same-label` lineage is run_id "
        "order; non-main tracks have no curated baseline, so their reference is the modal "
        "config (ASSUMED reference); sub-agents / frequency_penalty have no config field "
        "(log mentions only).",
    ]


def _nearmiss_lines(nm_rows, fp):
    traced = [r for r in nm_rows if r.get("has_trace")]
    from collections import Counter
    furthest = Counter(r.get("furthest_stage") for r in traced)
    measured = sum(1 for r in traced if str(r.get("confidence", "")).startswith("measured"))
    out = [
        f"- near_miss rows: {len(nm_rows)} ({len(traced)} with a trace; "
        f"{measured} scored by the nm-3 line-level matcher).",
        "- furthest-stage histogram (traced): "
        + ", ".join(f"{k}={v}" for k, v in sorted(furthest.items(),
                                                   key=lambda kv: str(kv[0]))),
        f"- cross-task FP control (Â§9.4): {fp['wrote_gold_change_fp']}/{fp['pairs']} "
        f"(trace, other-task) pairs fired WROTE_GOLD_CHANGE = "
        f"{fp['wrote_gold_change_fp_rate']*100:.3f}% "
        f"(bar <= {fp['bar']*100:.0f}%: {'PASS' if fp['passes_bar'] else 'MISS'}; "
        f"sampling {fp.get('sampling', 'all-pairs')}: per trace the "
        f"{nearmiss.FP_CAP} same-repo other tasks with the smallest "
        "sha256(task+other), deterministic).",
    ]
    return out


def _replay_lines(records, stop_reason, pending, clone_state, did_replay):
    if not records:
        return ["- replay table: no replay has run yet. Run "
                "`build --replay --deadline-s 1500` to populate "
                "KB/replays/ (gold-first, cached)."]
    from collections import Counter as _C
    cnt = _C((r.get("tier", "-"), r.get("kind", ""), r.get("agent_passed", "?"))
             for r in records)
    out = [f"- replay records: {len(records)}. Counts by (tier, kind, agent result) "
           "(tier 0 = curated min set + all_runs rules; 1 Kaggle main; 2 Kaggle other "
           "tracks; 3 local rig; '-' = cached record of a plain build):", "",
           "| tier | kind | agent | n |", "|---|---|---|---|"]
    for (tier, kind, ag), n in sorted(cnt.items(), key=lambda kv: tuple(map(str, kv[0]))):
        out.append(f"| {tier} | {kind} | {ag} | {n} |")
    detail = [r for r in records if r.get("tier", 0) in (0, "-", None)
              or r.get("agent_passed") == "Y"]
    out += ["", "Per (task, run, candidate) — tier-0 rows, plain-build cached rows and every "
            "agent PASS (cap 80): gold-passed-locally | agent-candidate-passed "
            "| counterfactual-passed | notes.",
            "", "| task | run | candidate | gold-local | agent | counterfactual | notes |",
            "|---|---|---|---|---|---|---|"]
    detail = sorted(detail, key=lambda x: (x.get("task", ""), x.get("run_id") or "",
                                           x.get("kind", ""), x.get("candidate_sha", "")))
    if len(detail) > 80:
        out_more = len(detail) - 80
        detail = detail[:80]
    else:
        out_more = 0
    for r in detail:
        out.append("| {task} | {run} | {kind} | {gl} | {ag} | {cf} | {notes} |".format(
            task=r.get("task", ""), run=(r.get("run_id") or "-"),
            kind=r.get("kind", ""),
            gl=r.get("gold_local", "?"), ag=r.get("agent_passed", "?"),
            cf=r.get("counterfactual_passed", "-"),
            notes=(r.get("notes", "") or "")[:70].replace("|", "/")))
    if out_more:
        out.append(f"| ... | {out_more} more rows in KB/replays/replays.jsonl | | | | | |")
    out.append("")
    if clone_state is not None:
        # Only the STABLE builder-safety verdict goes here (idempotent). The
        # live external-drift flag + HEAD values live in replays/clone_state.json.
        out.append(f"- CloneGuard: {clone_state.get('verdict', '?')} "
                   f"(no new objects/refs/config/stash in the main clones; "
                   f"module __file__ checks all under the %TEMP% worktree: "
                   f"{clone_state.get('module_file_checks_ok')}).")
    out.append(f"- replays_pending={pending}.")
    out.append("- NOTE: the reference-logs list and the clones' HEAD/index are a "
               "LIVE snapshot; the user moves checkouts between tasks, so HEAD "
               "drift during a build is external state, not a builder change "
               "(see replays/clone_state.json). Replays checkout the task's "
               "base_commit explicitly, so HEAD position does not affect them.")
    return out


def _replay_set(kb):
    rs = _read_json(kb / "curated" / "replay_set.json", {})
    return rs


def _candidate_vfs_files(g, tasks_gold, repo, task, base_commit, trace, which):
    """Build vfs-write file contents for a reconstructed candidate.

    which in {as_run, counterfactual}. Returns ({path: content}, notes) or
    (None, reason) when nothing can be reconstructed.
    """
    from kblib import reconstruct, replay as rp
    clone, _name = rp.clone_for(repo)
    if clone is None:
        return None, "no clone"

    def loader(path):
        import subprocess
        r = subprocess.run(["git", "cat-file", "-p", f"{base_commit}:{path}"],
                           cwd=str(clone), capture_output=True,
                           env=_git_env_lf(), timeout=30)
        if r.returncode != 0:
            return None
        return r.stdout.decode("utf-8", "replace")

    vfs = reconstruct.VFS(loader=loader)
    calls = trace.get("_calls", []) if trace else []
    applied_any = False
    notes = []
    # as_run: apply only executed edit attempts (observation OK); counterfactual:
    # also apply the refused/errored ones as-written.
    for c in calls:
        if not c.get("is_edit"):
            continue
        executed = c["obs_class"] in ("OK",)
        if which == "as_run" and not executed:
            continue
        res = _apply_edit_to_vfs(c, vfs, reconstruct)
        if res == "APPLIED":
            applied_any = True
        elif res in ("SYNTAX_ERROR", "ANCHOR_MISS", "UNPARSED", "BASH_ERROR",
                     "TOOL_ERROR"):
            notes.append(f"{c['edit_shape']}@step{c['step_id']}:{res}")
    changed = dict(vfs._files)
    if not changed:
        return None, "no reconstructable change (" + (";".join(notes) or "none") + ")"
    return changed, (";".join(notes) if notes else ("applied" if applied_any else ""))


def _apply_edit_to_vfs(call, vfs, reconstruct):
    """Apply one edit attempt to the VFS (as-written). Returns a prediction."""
    from kblib import harness_edit
    shape = call.get("edit_shape")
    files = call.get("edit_files") or []
    if shape == "edit_file":
        if call.get("old_payload") is None or call.get("new_payload") is None:
            return "UNPARSED"
        path = files[0] if files else None
        if not path:
            return "UNPARSED"
        content = vfs.read(path)
        try:
            r = harness_edit.emulate_edit_file(content, call["old_payload"],
                                               call["new_payload"])
        except Exception as e:  # wheel load issue
            return f"UNPARSED(wheel:{type(e).__name__})"
        if r["status"] == "ok":
            vfs.write(path, r["new_content"])
            return "APPLIED"
        return "TOOL_ERROR"
    if shape == "write_file":
        path = files[0] if files else None
        if path and call.get("new_payload") is not None:
            vfs.write(path, call["new_payload"])
            return "APPLIED"
        return "UNPARSED"
    raw = call.get("raw_cmd")
    if not raw:
        return "UNPARSED"
    res = reconstruct.reconstruct_run_command(raw, vfs)
    return res.prediction


_REPLAY_FORCE = False


_KAGGLE_KINDS = ("kaggle-kernel", "kaggle-pulled", "kaggle-pulled-legacy")
_SCOPE_REPOS = {"min": (), "rich": ("Textualize/rich",),
                "all": ("Textualize/rich", "fastapi/fastapi")}


def _row_has_candidate(r):
    """Design §13.6 scope rule: >= 1 edit attempt or patch_chars > 0."""
    tr = r.get("trace") or {}
    return bool(tr.get("edit_attempts")) or \
        ((r.get("outcome") or {}).get("patch_chars") or 0) > 0


def _replay_tier(r):
    """D5-21 tiers for non-curated rows: 1 Kaggle main-track rows with a trace;
    2 Kaggle other tracks; 3 local-rig rows; None = never (sweep/pasted/no trace)."""
    if r.get("trace") is None:
        return None
    kind = r.get("run_kind")
    if kind in _KAGGLE_KINDS:
        return 1 if r.get("track") == "main" else 2
    if kind == "local-rig":
        return 3
    return None


def replay_targets(rows, replay_set, scope="rich"):
    """Ordered [(tier, run_id, task)] for `build --replay` (D5-21).

    tier 0 = curated min_set + all_runs rules (any scope); tiers 1-3 only for
    scope rich/all and only for repos in that scope; sweep rows never. Within a
    tier: sorted by (run_id, task). Deduplicated (a pair keeps its lowest tier).
    """
    out, seen = [], set()

    def _add(tier, run_id, task):
        if (run_id, task) not in seen:
            seen.add((run_id, task))
            out.append((tier, run_id, task))

    t0 = [(e["run_id"], e["task"]) for e in replay_set.get("min_set", [])]
    for rule in replay_set.get("all_runs_rules", []):
        t0 += sorted((r["run_id"], r["task"]) for r in rows
                     if r["task"] == rule["task"] and r.get("trace") is not None)
    for run_id, task in t0:
        _add(0, run_id, task)
    repos = _SCOPE_REPOS.get(scope, ())
    if repos:
        by_tier = {1: [], 2: [], 3: []}
        for r in rows:
            if _repo_of(r["task"]) not in repos:
                continue
            tier = _replay_tier(r)
            if tier is None or not _row_has_candidate(r):
                continue
            by_tier[tier].append((r["run_id"], r["task"]))
        for tier in (1, 2, 3):
            for run_id, task in sorted(set(by_tier[tier])):
                _add(tier, run_id, task)
    return out


def _gold_cached_or_run(eng, rp, repo, task, gt, mode, force, timeout_s):
    """Reuse a key-matching gold-first record (D5-19a) or run gold+base.
    Returns (record, ran_bool)."""
    key = rp.gold_key(gt["task_fingerprint"],
                      rp.pins_at_commit(repo, task, gt["base_commit"]),
                      mode, eng.env_python, eng.env_pytest)
    if not force:
        cached = rp.read_gold(task, key)
        if cached is not None:
            return cached, False
    try:
        gf = eng.gold_first(repo, task, gt["base_commit"], timeout_s=timeout_s,
                            required_mode=mode)
    except rp.EnvFreezeError:
        raise
    except Exception as e:  # noqa: BLE001 - recorded as INFRA
        gf = {"task": task, "repo": repo, "base_commit": gt["base_commit"],
              "gold_first": "INFRA", "reason": f"{type(e).__name__}: {e}",
              "engine_version": rp.RP_VERSION, "required_mode": mode,
              "task_fingerprint": gt["task_fingerprint"], "pins": key["pins"],
              "env": key["env"]}
    rp.write_gold(task, gf)
    return gf, True


def _run_replays(g, tasks_gold, rows, t0, args):
    """Gold-first replay over the scope tiers (D5-21), bounded and resumable.

    Returns (records, stop_reason, pending, clone_state). Sets the module-level
    _REPLAY_STATS (gold controls run, tiers left) for the build stamp.
    """
    global _REPLAY_FORCE
    _REPLAY_FORCE = bool(getattr(args, "force_replay", False))
    from kblib import replay as rp
    kb = paths.kb_root()
    rp.load_raw_tasks(g / "comp_files" / "tasks.jsonl")
    rs = _replay_set(kb)
    scope = getattr(args, "replay_scope", "rich") or "rich"
    mode = getattr(args, "required_nodes", "added") or "added"
    targets = replay_targets(rows, rs, scope)

    row_by = {(r["run_id"], r["task"]): r for r in rows}
    deadline = args.deadline_s
    budget = args.replay_budget_s or 0.0
    records = []
    pending = 0
    stop_reason = None
    gold_runs = 0
    tiers_left = set()

    clones = [c for c in (rp.clone_for("Textualize/rich")[0],
                          rp.clone_for("fastapi/fastapi")[0]) if c is not None]
    guard = rp.CloneGuard(clones)
    guard.snapshot_before()

    gold_done = {}   # task -> gold_first record
    with rp.ReplayEngine(tasks_gold) as eng:
        phase_start = time.time()

        def time_left():
            left = []
            if deadline:
                reserve = 180.0
                left.append((deadline - reserve) - (time.time() - t0))
            if budget:
                left.append(budget - (time.time() - phase_start))
            return min(left) if left else 1e9

        def _pending(tier, run_id, task, kind="as_run"):
            nonlocal pending, stop_reason
            pending += 1
            tiers_left.add(tier)
            stop_reason = "deadline" if deadline else "replay budget"
            records.append({"task": task, "run_id": run_id, "kind": kind,
                            "tier": tier, "gold_local": "?", "agent_passed": "NOT_RUN",
                            "notes": f"NOT_RUN ({stop_reason})",
                            "candidate_sha": "pending", "from_cache": True})

        for tier, run_id, task in targets:
            row = row_by.get((run_id, task))
            repo = _repo_of(task)
            gt = tasks_gold["tasks"].get(task)
            if gt is None:
                records.append({"task": task, "run_id": run_id, "kind": "as_run",
                                "tier": tier, "gold_local": "N", "agent_passed": "N/A",
                                "notes": "task not in gold", "candidate_sha": "none",
                                "from_cache": True})
                continue
            base_commit = gt["base_commit"]
            if task not in gold_done:
                # cached gold costs no time; only a miss needs budget
                if time_left() < 30:
                    key = rp.gold_key(gt["task_fingerprint"],
                                      rp.pins_at_commit(repo, task, base_commit),
                                      mode, eng.env_python, eng.env_pytest)
                    cached = None if _REPLAY_FORCE else rp.read_gold(task, key)
                    if cached is None:
                        _pending(tier, run_id, task)
                        continue
                    gold_done[task] = cached
                else:
                    gf, ran = _gold_cached_or_run(
                        eng, rp, repo, task, gt, mode, _REPLAY_FORCE,
                        min(300, int(time_left())))
                    gold_runs += int(ran)
                    gold_done[task] = gf
            gf = gold_done[task]
            gold_valid = gf.get("gold_first", "").startswith("VALID")
            gold_pass_tests = gf.get("gold_pass_tests", [])
            if not gold_valid:
                # D5-21: non-VALID gold -> record without running a candidate
                records.append({"task": task, "run_id": run_id, "kind": "as_run",
                                "tier": tier, "gold_local": "N",
                                "gold_first": gf.get("gold_first"),
                                "agent_passed": "UNVERIFIED",
                                "notes": f"gold not valid locally ({gf.get('gold_first')}); "
                                         "candidate not run",
                                "candidate_sha": "not-run", "from_cache": True,
                                "engine_version": rp.RP_VERSION})
                continue
            if time_left() < 30 and not _recon_cached(kb, run_id, task, "as_run", mode,
                                                       tasks_gold, eng):
                _pending(tier, run_id, task)
                continue

            full_trace = _lookup_full_trace_cached(g, kb, run_id, task)
            # as_run candidate
            rec = _replay_candidate(eng, kb, tasks_gold, repo, task, base_commit,
                                    run_id, full_trace, "as_run", gf, gold_valid,
                                    gold_pass_tests, time_left, mode)
            rec["tier"] = tier
            records.append(rec)
            # counterfactual candidate (only if there were non-applied edits)
            if _trace_has_non_applied(kb, run_id, task, full_trace):
                if time_left() < 30 and not _recon_cached(
                        kb, run_id, task, "counterfactual", mode, tasks_gold, eng):
                    _pending(tier, run_id, task, "counterfactual")
                else:
                    cf = _replay_candidate(eng, kb, tasks_gold, repo, task,
                                           base_commit, run_id, full_trace,
                                           "counterfactual", gf, gold_valid,
                                           gold_pass_tests, time_left, mode)
                    cf["tier"] = tier
                    # fold counterfactual pass into the as_run record for the table
                    rec["counterfactual_passed"] = cf.get("agent_passed", "-")
                    records.append(cf)

        module_checks = list(eng.module_file_checks)
    _flush_recon_index(kb)
    _REPLAY_STATS.update({"gold_controls_run_this_build": gold_runs,
                          "tiers_left": sorted(tiers_left),
                          "replay_scope": scope, "required_nodes": mode,
                          "targets": len(targets),
                          "env_freeze_check": eng.freeze_check})

    ok, report = guard.verify_after()
    clone_state = _clone_state_from(ok, report, module_checks)
    return records, stop_reason, pending, clone_state


def _clone_state_from(ok, report, module_checks):
    any_external = any(v["external_drift"] for v in report.values())
    return {
        "builder_safe": ok,
        "verdict": "CLEAN (no builder-attributable change)" if ok
                   else "BUILDER VIOLATION",
        "external_drift_present": any_external,
        "external_drift_note": ("the user moved a clone HEAD/index mid-build "
                                "(external state, design Â§2.10/Â§13.3) â€” not a "
                                "builder change" if any_external else None),
        "repos": {_rel_clone(k): {"builder_diffs": v["builder_diffs"],
                                  "external_drift_fields": v["external_drift"]}
                  for k, v in report.items()},
        "module_file_checks_ok": all(c.get("under_worktree") for c in module_checks),
        "n_module_file_checks": len(module_checks),
    }


def _rel_clone(abs_path):
    return pathlib.Path(abs_path).name


def _write_clone_status_final(kb):
    """`git status --porcelain` of the rich + fastapi clones (via gitio main-ro)
    -> KB/replays/clone_status_final.txt. Deterministic: no timestamps."""
    from kblib import replay as rp
    out = []
    for repo in ("Textualize/rich", "fastapi/fastapi"):
        clone, name = rp.clone_for(repo)
        if clone is None:
            out.append(f"{name}: no clone")
            continue
        r = gitio.git(clone, "status", "--porcelain", scope="main-ro")
        lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
        out.append(f"{name}: {'CLEAN (empty)' if not lines else f'{len(lines)} lines'}"
                   f" rc={r.returncode}")
        out += [f"  {ln}" for ln in lines]
    io.safe_write(kb / "replays" / "clone_status_final.txt", "\n".join(out) + "\n")
    return out


_REPLAY_STATS = {}

# --- reconstruction index (rp-5): (run_id, task, kind) -> candidate sha, so a
# cached `build --replay` neither re-parses traces nor re-reconstructs edits.
_RECON = None
_RECON_DIRTY = False
_RECON_PUTS = 0
_TRACE_MAPS = {}
_RECON_HIT = object()   # sentinel "trace not parsed; index entry is valid"


def _recon_load(kb):
    global _RECON
    if _RECON is None:
        _RECON = _read_json(kb / "replays" / "recon_index.json", {})
    return _RECON


def _flush_recon_index(kb):
    global _RECON_DIRTY
    if _RECON is not None and _RECON_DIRTY:
        io.safe_write(kb / "replays" / "recon_index.json", io.dumps_json(_RECON))
        _RECON_DIRTY = False


def _trace_sig(g, run_id, task):
    if run_id not in _TRACE_MAPS:
        _TRACE_MAPS[run_id] = _run_dir_trace_map(g, run_id)
    tf = _TRACE_MAPS[run_id].get(task)
    if tf is None or not tf.is_file():
        return None
    st = tf.stat()
    return f"{classify.FC_VERSION}:{st.st_size}:{st.st_mtime_ns}"


def _recon_entry(kb, run_id, task, kind):
    ent = _recon_load(kb).get(f"{run_id}|{task}|{kind}")
    if not ent:
        return None
    sig = _trace_sig(paths.gemma_root(), run_id, task)
    return ent if sig is not None and ent.get("trace_sig") == sig else None


def _recon_put(kb, run_id, task, kind, cand_sha, notes, has_non_applied):
    global _RECON_DIRTY
    sig = _trace_sig(paths.gemma_root(), run_id, task)
    if sig is None:
        return
    ent = {"trace_sig": sig, "cand_sha": cand_sha, "notes": notes or "",
           "has_non_applied": bool(has_non_applied)}
    global _RECON_PUTS
    key = f"{run_id}|{task}|{kind}"
    if _recon_load(kb).get(key) != ent:
        _RECON[key] = ent
        _RECON_DIRTY = True
        _RECON_PUTS += 1
        if _RECON_PUTS % 50 == 0:   # resumability if the process is stopped
            _flush_recon_index(kb)


def _recon_cached(kb, run_id, task, kind, mode, tasks_gold, eng):
    """True iff this candidate can be filled from cache at zero cost."""
    from kblib import replay as rp
    if _REPLAY_FORCE:
        return False
    ent = _recon_entry(kb, run_id, task, kind)
    if ent is None:
        return False
    if ent["cand_sha"] is None:
        return True
    tf = tasks_gold["tasks"][task]["task_fingerprint"]
    return rp.read_cache(task, ent["cand_sha"], tf, eng.env_python, eng.env_pytest,
                         mode) is not None


def _lookup_full_trace_cached(g, kb, run_id, task):
    ent = _recon_entry(kb, run_id, task, "as_run")
    if ent is not None and not _REPLAY_FORCE:
        if not ent["has_non_applied"] or _recon_entry(kb, run_id, task,
                                                      "counterfactual") is not None:
            return _RECON_HIT
    return _lookup_full_trace(g, run_id, task)


def _trace_has_non_applied(kb, run_id, task, full_trace):
    if full_trace is _RECON_HIT:
        ent = _recon_entry(kb, run_id, task, "as_run")
        return bool(ent and ent["has_non_applied"])
    return bool(full_trace) and _has_non_applied_edits(full_trace)


def _replay_candidate(eng, kb, tasks_gold, repo, task, base_commit, run_id,
                      trace, kind, gf, gold_valid, gold_pass_tests, time_left,
                      mode="added"):
    from kblib import replay as rp
    g = paths.gemma_root()
    which = "as_run" if kind == "as_run" else "counterfactual"
    tf = tasks_gold["tasks"][task]["task_fingerprint"]
    ent = None if (_REPLAY_FORCE or run_id is None) else \
        _recon_entry(kb, run_id, task, kind)
    vfs_files = None
    if ent is not None:
        cand_sha, notes = ent["cand_sha"], ent["notes"]
    else:
        if trace is _RECON_HIT:
            trace = _lookup_full_trace(g, run_id, task)
        vfs_files, notes = _candidate_vfs_files(g, tasks_gold, repo, task, base_commit,
                                                trace, which)
        cand_sha = rp.candidate_sha_vfs(vfs_files) if vfs_files is not None else None
        if run_id is not None:
            _recon_put(kb, run_id, task, kind, cand_sha, notes,
                       bool(trace) and _has_non_applied_edits(trace))
    rec = {"task": task, "run_id": run_id, "kind": kind,
           "gold_local": "Y" if gold_valid else "N",
           "gold_first": gf.get("gold_first"), "notes": notes or "",
           "pins": gf.get("pins", []),
           "pin_provenance": gf.get("pin_provenance", "none"),
           "engine_version": rp.RP_VERSION, "required_mode": mode}
    if cand_sha is None:
        rec["agent_passed"] = "N/A"
        rec["notes"] = notes or "no reconstructable candidate"
        rec["candidate_sha"] = "none"
        rec["from_cache"] = True
        return rec
    rec["candidate_sha"] = cand_sha
    cached = None if _REPLAY_FORCE else \
        rp.read_cache(task, cand_sha, tf, eng.env_python, eng.env_pytest, mode)
    if cached is not None:
        res = cached
        rec["from_cache"] = True
    else:
        if vfs_files is None:
            # index hit but result cache miss: reconstruct now
            if trace is None or trace is _RECON_HIT:
                trace = _lookup_full_trace(g, run_id, task)
            vfs_files, notes = _candidate_vfs_files(g, tasks_gold, repo, task,
                                                    base_commit, trace, which)
            if vfs_files is None or rp.candidate_sha_vfs(vfs_files) != cand_sha:
                rec["agent_passed"] = "INFRA"
                rec["notes"] = "reconstruction changed since index; rerun build --replay"
                rec["from_cache"] = True
                return rec
        try:
            res = eng.run_candidate(repo, task, base_commit, kind="vfs-write",
                                    vfs_files=vfs_files,
                                    timeout_s=min(300, int(time_left())),
                                    gold_pass_tests=gold_pass_tests,
                                    required_mode=mode)
        except rp.EnvFreezeError:
            raise
        except Exception as e:
            res = {"result": "INFRA", "reason": f"{type(e).__name__}: {e}"}
        res["task_fingerprint"] = tf
        if "env" not in res:
            res["env"] = {"python": eng.env_python, "pytest": eng.env_pytest}
        rp.write_cache(task, cand_sha, res, mode)
        rec["from_cache"] = False
    return _judge(rec, res, gf, gold_valid)


def _judge(rec, res, gf, gold_valid):
    """Fold a candidate result into its replay record (rp-4 judging, unchanged)."""
    # carry pin provenance from the candidate result (lockfile vs fallback)
    if res.get("pins"):
        rec["pins"] = res.get("pins")
    if res.get("pin_provenance"):
        rec["pin_provenance"] = res.get("pin_provenance")
    if res.get("pin_provenance") == "fallback":
        rec["notes"] = (rec["notes"] + "; " if rec["notes"] else "") + \
            "pins=FALLBACK (poetry.lock unparsed)"
    if res.get("result") == "INFRA" and "pin unavailable" in str(res.get("reason", "")):
        rec["notes"] = (rec["notes"] + "; " if rec["notes"] else "") + \
            str(res.get("reason"))
    if not gold_valid:
        rec["agent_passed"] = "UNVERIFIED"
        rec["notes"] = (rec["notes"] + "; " if rec["notes"] else "") + \
            f"gold not valid locally ({gf.get('gold_first')})"
    else:
        passed = res.get("harness_like") if gf.get("result_criterion") == "harness_like" \
            else res.get("gold_relative")
        rec["agent_passed"] = "Y" if passed else "N"
        if res.get("result") in ("INFRA", "APPLY_FAIL", "TIMEOUT"):
            rec["agent_passed"] = res.get("result")
    rec["result"] = res.get("result")
    return rec


def _read_cached_replays(tasks_gold, rows):
    """Plain build: fill the replay table from cached results only (no run)."""
    from kblib import replay as rp
    kb = paths.kb_root()
    records = []
    cache_root = kb / "replays" / "cache"
    if not cache_root.is_dir():
        return records
    for task_dir in sorted(cache_root.iterdir()):
        if not task_dir.is_dir():
            continue
        task = task_dir.name
        gf = _read_json(kb / "replays" / "gold" / f"{task}.json", {})
        for sha_dir in sorted(task_dir.iterdir()):
            rj = sha_dir / "result.json"
            if not rj.is_file() or "-" in sha_dir.name:
                continue   # non-default required_mode dirs (<sha12>-hunk) skipped
            res = _read_json(rj, {})
            gv = str(gf.get("gold_first", "")).startswith("VALID")
            crit = gf.get("result_criterion")
            passed = res.get("harness_like") if crit == "harness_like" \
                else res.get("gold_relative")
            records.append({"task": task, "run_id": "(cached)", "kind": "cached",
                            "gold_local": "Y" if gv else "N",
                            "agent_passed": ("Y" if passed else "N") if gv else "UNVERIFIED",
                            "candidate_sha": sha_dir.name,
                            "notes": "from cache", "result": res.get("result"),
                            "from_cache": True})
    return records


def _has_non_applied_edits(trace):
    for c in trace.get("_calls", []):
        if c.get("is_edit") and c["obs_class"] != "OK":
            return True
    return False


def _lookup_full_trace(g, run_id, task):
    """Re-parse the trace WITH _calls for replay reconstruction."""
    tf = _run_dir_trace_map(g, run_id).get(task)
    if tf is None or not tf.is_file():
        return None
    tr = traces.parse_trace(tf)
    if tr and "trace_error" in tr:
        return None
    return tr


def _git_env_lf():
    import os
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    return env


def _log_claims_md(stamp_lines, cl, log_text):
    def cell(s, n=160):
        s = " ".join(str(s or "").split()).replace("|", "/")
        return s if len(s) <= n else s[:n - 3] + "..."

    out = list(stamp_lines)
    out.append(f"log sha256 (first 12): {io.sha256_text(log_text)[:12]}  lines: "
               f"{log_text.count(chr(10)) + 1}  engine: {cl['cl_version']}")
    out += ["", "## 2. READ-THIS-FIRST truths",
            "| id | line | status | reason | evidence | curated-by |", "|---|---|---|---|---|---|"]
    for c in cl["claims"]:
        if c["kind"] == "standing-truth":
            ev = "; ".join(f"{e.get('path')}" + (f":L{e['line']}" if e.get("line") else "")
                           for e in c["evidence"][:3])
            out.append(f"| {c['claim_id']} | {c['line']} | {c['status']} | {cell(c['reason'], 120)} "
                       f"| {cell(ev, 120)} | - |")
    out += ["", "## 3. Contradictions between log entries (same version/task/field, different values)"]
    if not cl["contradictions"]:
        out.append("- none")
    for x in cl["contradictions"][:120]:
        vals = "; ".join(f"{v['value']} ({v['claim_id']} L{v['line']})" for v in x["values"][:6])
        out.append(f"- {x['field']} {x['version']}{(' ' + x['task']) if x['task'] else ''}: {vals}"
                   + (" â€” resolved by supersession" if x["resolved_by_supersession"] else ""))
    if len(cl["contradictions"]) > 120:
        out.append(f"- ... {len(cl['contradictions']) - 120} more (see log_claims.jsonl facts)")
    out += ["", "### 3b. Disagreements with local data NOT asserted (weak binding / different rep / "
                "budget sanity)"]
    if not cl["weak_disagreements"]:
        out.append("- none")
    for w in cl["weak_disagreements"]:
        out.append(f"- {w['claim_id']} L{w['line']} {w['field']} {w['version']}"
                   f"{(' ' + w['task']) if w.get('task') else ''}={w['value']}: {cell(w['reason'], 220)}")
    out += ["", "### 3c. The log disagrees with itself (no correction links the lines; not asserted)"]
    out += [f"- {x['claim_id']} L{x['line']} {x['field']} {x['version']}={x['value']} vs "
            + "; ".join(f"L{o['line']}={o['value']}" for o in x["other_lines"])
            for x in cl["self_disagreements"]] or ["- none"]
    out += ["", "### 3d. Label collisions (one token, two referents)"]
    out += [f"- `{h['token']}`: experiment runs {h['experiment_runs_tasks']}; kernel "
            f"`{h['kernel_label']}` {h['kernel_runs_tasks']}; kernel-version usage at "
            f"L{', L'.join(str(x) for x in h['log_kernel_version_lines'])}"
            for h in cl["label_collisions"]] or ["- none"]
    out += ["", "## 4. Supersession chains (unit ids oldest -> newest)"]
    if not cl["chains"]:
        out.append("- none")
    for ch in cl["chains"]:
        out.append(f"- {' -> '.join(f'{u} (L{ln})' for u, ln in zip(ch['chain'], ch['lines']))}; "
                   f"newest: {cell(ch['newest_heading'], 120)}")
    out += ["", "### 4a. Links", "| old unit | old line | new unit | new line | basis | cited at | applied |",
            "|---|---|---|---|---|---|---|"]
    for lk in cl["links"]:
        out.append(f"| {lk['old']} | {lk['old_line']} | {lk['new'] or '-'} | {lk['new_line'] or '-'} | "
                   f"{lk['basis']} | {lk['cite_line']} | {lk['applied']} |")
    out += ["", "### 4b. Unresolved citations"]
    out += [f"- {x['unit_id']} L{x['line']} `{x['cite']}`: {x['reason']}"
            for x in cl["unresolved_citations"]] or ["- none"]
    out += ["", "### 4c. Keyword-overlap candidate links (NOT applied; need curation)"]
    out += [f"- {x['new']} (L{x['new_line']}) may correct {x['old']} (L{x['old_line']}); shared "
            f"{x['shared']}" for x in cl["candidate_links"][:80]] or ["- none"]
    if len(cl["candidate_links"]) > 80:
        out.append(f"- ... {len(cl['candidate_links']) - 80} more")
    out += ["", "### 4d. Live-best chain (F10 facts; checked against the curated baseline, never adopted)"]
    out += [f"- L{x['line']} {x['version']} {x['polarity']} (`{x.get('phrase')}`) {x['claim_id']}: "
            f"{x['status']}" + (f" â€” supersedes live-best of {x['supersedes_live_best_of']}"
                                if x.get("supersedes_live_best_of") else "")
            for x in cl["live_best_chain"]] or ["- none"]
    out += ["", "## 5. Claim table",
            "| id | line | status | kind | unit heading | excerpt | facts | reason / evidence |",
            "|---|---|---|---|---|---|---|---|"]
    for c in cl["claims"]:
        facts = "; ".join(_fact_brief(f) for f in c["facts"]
                          if f["field"] not in ("bar", "unkeyed"))[:200]
        why = c["reason"]
        if c["status"] == "SUPERSEDED" and c["superseded_by"]:
            why = f"superseded by {c['superseded_by'][0].get('unit_id') or 'own heading tag'} " \
                  f"({c['superseded_by'][0]['link_basis']})"
        out.append(f"| {c['claim_id']} | {c['line']} | {c['status']} | {c['kind']} | "
                   f"{cell(c['heading'], 80)} | {cell(c['text'], 160)} | {cell(facts, 200) or '-'} | "
                   f"{cell(why, 160)} |")
    out += ["", "## 6. Curated claims (curated/claims.jsonl, read-only) and orphaned curations",
            "| id | kind | status | evidence ok | text | evidence |", "|---|---|---|---|---|---|"]
    for c in cl["curated"]:
        ev = "; ".join(e["path"] or e["raw"][:60] for e in c["evidence"][:4])
        out.append(f"| {c['id']} | {c['kind']} | {c['status']} | "
                   f"{'yes' if c['evidence_ok'] else 'MISSING ' + ', '.join(c['evidence_missing'])} | "
                   f"{cell(c['text'], 160)} | {cell(ev, 200)} |")
    out += [f"- orphan {o['id']}: {o['reason']}" for o in cl["orphans"]] or ["- orphaned curations: none"]
    out += ["", "## 7. Curation conflicts"]
    out += [f"- {x['id']}: auto {x['auto']} vs curated {x['curated']} (curated stands)"
            for x in cl["curation_conflicts"]] or ["- none"]
    out += ["", "## 8. Curated-file parse errors"]
    out += [f"- line {e['line']}: {e['error']}" for e in cl["curated_errors"]] or ["- none"]
    out += ["", "## 9. Unclassified entries (`##` units with kind other)"]
    for u in cl["units"]:
        if u["level"] == 2 and u["kind"] == "other":
            out.append(f"- L{u['start']}: {cell(u['heading'], 80)}")
    out += ["", "## 10. Suspect dates (heading date replaced by the inherited date)"]
    out += [f"- L{u['start']}: date_raw {u['date_raw']} -> {u['date']}"
            for u in cl["units"] if u["date_suspect"]] or ["- none"]
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------ check-fresh

def cmd_check_fresh(args):
    g = paths.gemma_root()
    kb = paths.kb_root()
    bm = _read_json(kb / "build_meta.json", None)
    if bm is None:
        print("STALE: no build_meta.json")
        return 3
    disc = discover.discover(g)
    fp = discover.input_fingerprint(g, _input_files(g, disc))
    if fp["fingerprint"] != bm.get("inputs_fingerprint") or \
            _discovery_fp(disc) != bm.get("discovery_fingerprint"):
        print("STALE")
        return 3
    print("FRESH")
    return 0


# ------------------------------------------------------------------ report-path

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def cmd_report_path(args):
    kb = paths.kb_root()
    audits = kb / "audits"
    if args.frm:
        src = pathlib.Path(args.frm)
        date, slug = verdict.derive_date_slug(src)
        if not date:
            print("bad --from path", file=sys.stderr)
            return 1
        kind = args.kind
    else:
        date, slug, kind = args.date, args.slug, args.kind
        if not date or not _DATE_RE.match(date):
            print("bad date", file=sys.stderr)
            return 1
        if not slug or not _SLUG_RE.match(slug):
            print("bad slug", file=sys.stderr)
            return 1
        if slug.endswith(("-refute", "-final")):
            print("slug must not end with -refute/-final", file=sys.stderr)
            return 1
    suffix = {"audit": "", "refute": "-refute", "final": "-final"}[kind]
    out = audits / f"{date}-{slug}{suffix}.md"
    if out.exists():
        print(f"report already exists: {out}", file=sys.stderr)
        return 1
    print(str(out))
    return 0


# ---------------------------------------------------------------------- preflight

def cmd_preflight(args):
    kb = paths.kb_root()
    prop = pathlib.Path(args.proposal)
    proposals = (kb / "proposals").resolve()
    try:
        prop.resolve().relative_to(proposals)
    except ValueError:
        print("proposal not inside kb/proposals", file=sys.stderr)
        return 1
    if not prop.is_file():
        print("proposal is not a file", file=sys.stderr)
        return 1
    if not _SLUG_RE.match(args.slug or "") or args.slug.endswith(("-refute", "-final")):
        print("bad slug", file=sys.stderr)
        return 1
    if not _DATE_RE.match(args.date or ""):
        print("bad date", file=sys.stderr)
        return 1
    audits = kb / "audits"
    for suf in ("", "-refute", "-final"):
        if (audits / f"{args.date}-{args.slug}{suf}.md").exists():
            print(f"report already exists for {args.date}-{args.slug}{suf}", file=sys.stderr)
            return 1
    print("PREFLIGHT OK")
    return 0


# ----------------------------------------------------------------------- verdict

def cmd_verdict(args):
    a = pathlib.Path(args.a)
    b = pathlib.Path(args.b)
    va = verdict.parse_verdict(a) or "INVALID"
    vb = verdict.parse_verdict(b) or "INVALID"
    final = verdict.stricter(va, vb)
    date, slug = verdict.derive_date_slug(a)
    if not date:
        print("cannot derive date/slug from --a", file=sys.stderr)
        return 2
    final_path = a.parent / f"{date}-{slug}-final.md"
    if final_path.exists():
        print(f"final report exists: {final_path}", file=sys.stderr)
        return 2
    body = (
        f"VERDICT: {final}\n"
        f"# Final audit verdict â€” {slug} ({date})\n"
        f"- Pass 1 (AUDIT): {va} â€” {a}\n"
        f"- Pass 2 (REFUTE): {vb} â€” {b}\n"
        f"- Rule: final = stricter of the two (PROCEED < REVISE < NEEDS-DATA < REJECT); never softened.\n"
        f"## Mechanical disagreements\n"
        f"- pass1={va} pass2={vb}; stricter={final}\n")
    final_path.write_text(body, encoding="utf-8")
    print(f"VERDICT: {final}")
    print(f"final: {final_path}")
    return 0


# ---------------------------------------------------------------------- leakcheck

def cmd_leakcheck(args):
    g = paths.gemma_root()
    text = pathlib.Path(args.file).read_text(encoding="utf-8", errors="replace")
    hits = leak.check(text, g / "comp_files" / "tasks.jsonl", scope=args.scope)
    if hits:
        for h in hits:
            print(f"LEAK {h['type']}: {h['text']}", file=sys.stderr)
        return 1
    print("LEAKCHECK CLEAN")
    return 0


# --------------------------------------------------------------------------- card

def _card_row(r):
    return {"row_id": r["row_id"], "version": r["version_label"],
            "outcome": r["outcome"], "failure_class": r["failure_class"],
            "subclass": r["failure_subclass"]}


def card_group_lines(sel):
    """D5-25: one summary line per (stack.platform, track, version_label)."""
    from collections import Counter
    groups = {}
    for r in sel:
        key = ((r.get("stack") or {}).get("platform", "?"), r.get("track", "?"),
               r.get("version_label") or "?")
        groups.setdefault(key, []).append(r)
    out = []
    for key in sorted(groups):
        rs = groups[key]
        res = sum(1 for r in rs if (r.get("outcome") or {}).get("resolved"))
        cls = Counter(str(r.get("failure_class")) for r in rs)
        out.append(f"GROUP stack={key[0]} track={key[1]} label={key[2]} n={len(rs)} "
                   f"resolved={res} classes=" +
                   ",".join(f"{k}:{v}" for k, v in sorted(cls.items())))
    return out


def cmd_card(args):
    kb = paths.kb_root()
    rows = [json.loads(l) for l in (kb / "runs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.task and not args.run:
        sel = [r for r in rows if r["task"] == args.task]
        if getattr(args, "stack", None):
            sel = [r for r in sel if (r.get("stack") or {}).get("platform") == args.stack]
        sel.sort(key=lambda r: r["row_id"])
        for ln in card_group_lines(sel):
            print(ln)
        limit = getattr(args, "limit", 40)
        for r in sel[:limit] if limit and limit > 0 else sel:
            print(json.dumps(_card_row(r), ensure_ascii=False))
        if limit and limit > 0 and len(sel) > limit:
            print(f"... {len(sel) - limit} more rows (raise --limit or filter --stack)")
        return 0
    elif args.run and args.task:
        sel = [r for r in rows if r["run_id"] == args.run and r["task"] == args.task]
    else:
        print("card RUN TASK | card --task T [--limit N] [--stack S]", file=sys.stderr)
        return 1
    for r in sel:
        print(json.dumps(_card_row(r), ensure_ascii=False))
    return 0


def filter_claims(rows, task=None, version=None, lever=None, text=None, status=None,
                  lever_ids=()):
    """D5-16 claims filters (pure; newest unit first). `lever` is a lexicon id or
    free text (case-insensitive regex over heading + text); `text` is a
    case-insensitive regex over heading + text + facts."""
    sel = []
    vq = claims.canon(version) if version else None
    trx = re.compile(text, re.I) if text else None
    lrx = None
    if lever and lever not in lever_ids:
        try:
            lrx = re.compile(lever, re.I)
        except re.error:
            lrx = re.compile(re.escape(lever), re.I)
    for c in rows:
        if status and c.get("status") != status.upper():
            continue
        if task and task not in (c.get("tasks") or []) and \
                not any(f.get("task") == task for f in c.get("facts") or []):
            continue
        if vq and vq not in [claims.canon(v) for v in c.get("versions") or []] and \
                not any(claims.canon(f.get("version")) == vq for f in c.get("facts") or []):
            continue
        if lever:
            if lrx is None and lever not in (c.get("levers") or []):
                continue
            if lrx is not None and not lrx.search((c.get("heading") or "") + "\n" + (c.get("text") or "")):
                continue
        if trx and not trx.search((c.get("heading") or "") + "\n" + (c.get("text") or "") + "\n"
                                  + json.dumps(c.get("facts") or [], ensure_ascii=False)):
            continue
        sel.append(c)
    sel.sort(key=lambda c: (-int(c.get("unit_start_line") or 0), -int(c.get("line") or 0),
                            c.get("claim_id") or ""))
    return sel


def claim_line(c):
    sup = ""
    if c.get("status") == "SUPERSEDED":
        sb = (c.get("superseded_by") or [{}])[0]
        sup = f" [SUPERSEDED by {sb.get('unit_id') or 'its own heading tag'}]"
    ex = " ".join((c.get("text") or "").split())[:200]
    facts = "; ".join(_fact_brief(f) for f in c.get("facts") or []
                      if f["field"] not in ("bar", "unkeyed"))
    out = (f"L{c.get('line')} {c.get('claim_id')} {c.get('status')}{sup} [{c.get('kind')}] "
           f"{c.get('date') or '-'} v={','.join(c.get('versions') or []) or '-'} :: {ex}")
    if facts:
        out += f"\n    facts: {facts[:400]}"
    if c.get("status") != "SUPPORTED" and c.get("reason") and c.get("status") != "SUPERSEDED":
        out += f"\n    reason: {c['reason'][:200]}"
    return out


def cmd_claims(args):
    kb = paths.kb_root()
    rows = [json.loads(l) for l in (kb / "log_claims.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()]
    lex = levers.load_lexicon(kb, _HERE / "kblib")
    try:
        sel = filter_claims(rows, task=args.task, version=args.version, lever=args.lever,
                            text=args.text, status=args.status,
                            lever_ids={lv["id"] for lv in lex["levers"]})
    except re.error as e:
        print(f"claims: bad --text regex: {e}", file=sys.stderr)
        return 1
    limit = args.limit if args.limit and args.limit > 0 else len(sel)
    filt = {k: getattr(args, k) for k in ("task", "version", "lever", "text", "status")
            if getattr(args, k)}
    print(f"# claims: {len(sel)} matched of {len(rows)}; showing {min(limit, len(sel))} "
          f"(newest unit first); filters: {json.dumps(filt, ensure_ascii=False)}")
    for c in sel[:limit]:
        print(claim_line(c))
    if len(sel) > limit:
        print(f"... {len(sel) - limit} more (raise --limit; 0 = all)")
    return 0


def _pull_targets(g, kb, force):
    """D5-11 auto targets from the newest snapshots + local discovery (offline)."""
    from kblib import attribution, baseline as bl
    src = bl.lb_source(kb)
    klist_rows, klist_path = attribution.newest_kernels_list(kb)
    disc = discover.discover(g)
    log_text, _ = io.read_text_bomaware(g / "GEMMA_EXPERIMENT_LOG.md")
    targets, notes = attribution.pull_targets(
        g, src["rows"], klist_rows, attribution.local_output_slugs(g, disc),
        disc["kernel_dirs"], log_text, force=force)
    notes = [f"LB source: {src['path']} ({src['reason']})",
             f"kernels list: {klist_path or 'none (run `pull --submissions` first)'}"] + notes
    return targets, notes


def cmd_pull(args):
    """Read-only Kaggle pulls (D5-9). Exit 0 ok / 6 any CLI failure / 1 bad args."""
    from kblib import kaggle
    g = paths.gemma_root()
    kb = paths.kb_root()
    try:
        slugs = [kaggle.normalize_slug(s) for s in (args.slug or [])]
    except kaggle.ArgvError as e:
        print(f"bad --slug: {e}", file=sys.stderr)
        return 1
    if not (slugs or args.submissions or args.targets):
        print("pull: give --submissions, --targets and/or --slug S", file=sys.stderr)
        return 1
    if args.max is None or args.max < 0:
        print("pull: --max must be >= 0", file=sys.stderr)
        return 1
    if args.for_ref and not re.fullmatch(r"\d{6,10}", str(args.for_ref)):
        print("pull: --for-ref must be a numeric submission ref", file=sys.stderr)
        return 1
    failures = 0
    utc = kaggle.utc_stamp()
    tag = "DRY-RUN " if args.dry_run else ""
    if args.submissions:
        for name, fn in (("submissions", kaggle.pull_submissions),
                         ("kernels-list", kaggle.list_mine)):
            r = fn(dry_run=args.dry_run, utc=utc)
            print(f"{tag}argv: {json.dumps([kaggle.KAGGLE_EXE] + r['argv'])}")
            if args.dry_run:
                continue
            m = r["meta"]
            print(f"{name}: exit={m['exit']} ok={m['ok']} "
                  f"{('csv=' + m['csv'] + ' rows=' + str(m['rows'])) if m['ok'] else 'FAILED'}")
            if not m["ok"]:
                failures += 1
                print(f"{name} output (first 2000 chars):\n{m['output_text']}")
    queue = []
    for s in slugs:
        if s not in queue:
            queue.append(s)
    if args.targets:
        targets, notes = _pull_targets(g, kb, args.force)
        for n in notes:
            print(f"targets: {n}")
        for t in targets:
            print(f"target: {t['slug']} - {t['reason']}")
            if t["slug"] not in queue:
                queue.append(t["slug"])
    if not args.dry_run:
        for p in kaggle.leftover_partials():
            try:
                print(f"finalized interrupted pull: {kaggle.finalize_partial(p)}")
            except (OSError, ValueError) as e:
                failures += 1
                print(f"could not finalize {p}: {e}")
    fetch, rest = queue[:args.max], queue[args.max:]
    pattern = None
    for slug in fetch:
        done = kaggle.already_pulled(slug)
        if done and not args.force:
            print(f"skip {slug}: already pulled ({done[-1]}); use --force")
            continue
        if pattern is None:
            pattern = kaggle.has_file_pattern(dry_run=args.dry_run)
        for_ref = args.for_ref if slug in slugs else None
        try:
            m = kaggle.pull_output(slug, for_ref=for_ref, dry_run=args.dry_run,
                                   file_pattern=pattern)
        except (OSError, ValueError) as e:
            failures += 1
            print(f"pulled {slug}: ok=False error={type(e).__name__}: {e}")
            continue
        if args.dry_run:
            for a in m["argv"]:
                print(f"{tag}argv: {json.dumps([kaggle.KAGGLE_EXE] + a)}")
            continue
        n_files = len([f for f in m["files"] if not f["path"].startswith("source/")])
        print(f"pulled {slug}: ok={m['ok']} exit={m['exit']} source_exit={m['source_exit']} "
              f"files={n_files} deleted={[d['path'] for d in m['deleted']]}")
        if not m["ok"]:
            failures += 1
            print(f"  output tail: {m['output_text'][-600:]}")
    for slug in rest:
        print(f"not fetched (cap --max {args.max}): {slug}")
    return 6 if failures else 0


# ------------------------------------------------------------- replay / gold-gate

_REPO_ARG = {"rich": "Textualize/rich", "fastapi": "fastapi/fastapi"}


def _replay_clones():
    return [c for c in (replay.clone_for("Textualize/rich")[0],
                        replay.clone_for("fastapi/fastapi")[0]) if c is not None]


def _merge_replays_jsonl(kb, new_records):
    """Replace-or-add records in replays.jsonl keyed by (task, run_id, kind,
    candidate_sha); deterministic sort."""
    p = kb / "replays" / "replays.jsonl"
    old = []
    if p.is_file():
        old = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]

    def key(r):
        return (r.get("task", ""), r.get("run_id") or "", r.get("kind", ""),
                r.get("candidate_sha", ""))
    merged = {key(r): r for r in old}
    for r in new_records:
        merged[key(r)] = {k: v for k, v in r.items() if k != "from_cache"}
    io.safe_write(p, io.dumps_jsonl([merged[k] for k in sorted(merged)]))


def _print_rec(r):
    print(f"{r.get('kind')} {r.get('task')} run={r.get('run_id') or '-'} "
          f"cand={(r.get('candidate_sha') or '')[:12]} gold_local={r.get('gold_local')} "
          f"agent={r.get('agent_passed')} result={r.get('result', '-')} "
          f"cache={'hit' if r.get('from_cache') else 'ran'} notes={r.get('notes', '')[:120]}",
          flush=True)


def _deadline_left(t0, deadline, reserve=60.0):
    return (deadline - reserve) - (time.time() - t0) if deadline else 1e9


def cmd_replay(args):
    """design §15.1 `replay`: specific candidates through the cache, gold first."""
    global _REPLAY_FORCE
    t0 = time.time()
    g, kb = paths.gemma_root(), paths.kb_root()
    if args.kind in ("final", "intent"):
        print(f"NOT_IMPLEMENTED: --kind {args.kind} is not reconstructed by rp-5 "
              "(as_run and counterfactual only)", file=sys.stderr)
        return 1
    tasks_gold = gold.build_tasks_gold(g / "comp_files" / "tasks.jsonl")
    gt = tasks_gold["tasks"].get(args.task)
    if gt is None:
        print(f"unknown task {args.task!r}", file=sys.stderr)
        return 1
    repo = gt["repo"]
    if replay.clone_for(repo)[0] is None:
        print(f"{args.task} INFRA no local clone for {repo}", flush=True)
        return 1
    cand_text = None
    if args.candidate:
        cp = pathlib.Path(args.candidate)
        if not cp.is_file():
            print(f"candidate patch not found: {cp}", file=sys.stderr)
            return 1
        cand_text = cp.read_text(encoding="utf-8", errors="replace")
    mode = args.required_nodes
    _REPLAY_FORCE = bool(args.force)
    replay.load_raw_tasks(g / "comp_files" / "tasks.jsonl")
    with lock.BuildLock(kb) as lk:
        try:
            lk.acquire(wait_s=args.lock_wait_s or 0.0)
        except TimeoutError:
            print("build lock held by a live process", file=sys.stderr)
            return 8
        guard = replay.CloneGuard(_replay_clones())
        guard.snapshot_before()
        records = []

        def time_left():
            return _deadline_left(t0, args.deadline_s)

        with replay.ReplayEngine(tasks_gold) as eng:
            gf, ran = _gold_cached_or_run(eng, replay, repo, args.task, gt, mode,
                                          bool(args.force), min(300, int(time_left())))
            print(f"GOLD {args.task} {gf.get('gold_first')} "
                  f"{'RAN' if ran else 'CACHED'} mode={mode} "
                  f"pins={','.join(gf.get('pins', [])) or '-'} "
                  f"reason={gf.get('reason') or '-'}", flush=True)
            gold_valid = str(gf.get("gold_first", "")).startswith("VALID")
            gpt = gf.get("gold_pass_tests", [])
            if args.candidate:
                sha = replay.candidate_sha_patch(cand_text)
                rec = {"task": args.task, "run_id": None, "kind": "manual",
                       "gold_local": "Y" if gold_valid else "N",
                       "gold_first": gf.get("gold_first"), "notes": f"manual {args.candidate}",
                       "pins": gf.get("pins", []), "candidate_sha": sha,
                       "pin_provenance": gf.get("pin_provenance", "none"),
                       "engine_version": replay.RP_VERSION, "required_mode": mode}
                if not gold_valid:
                    rec.update({"agent_passed": "UNVERIFIED", "from_cache": True,
                                "notes": rec["notes"] + "; gold not valid locally; not run"})
                else:
                    tf = gt["task_fingerprint"]
                    res = None if args.force else replay.read_cache(
                        args.task, sha, tf, eng.env_python, eng.env_pytest, mode)
                    rec["from_cache"] = res is not None
                    if res is None:
                        res = eng.run_candidate(repo, args.task, gt["base_commit"],
                                                kind="patch", patch_text=cand_text,
                                                timeout_s=min(300, int(time_left())),
                                                gold_pass_tests=gpt, required_mode=mode)
                        res["task_fingerprint"] = tf
                        replay.write_cache(args.task, sha, res, mode)
                    rec = _judge(rec, res, gf, gold_valid)
                records.append(rec)
            elif args.run:
                full = _lookup_full_trace(g, args.run, args.task)
                if full is None:
                    print(f"no trace for ({args.run}, {args.task})", file=sys.stderr)
                    return 1
                kinds = [args.kind] if args.kind else ["as_run", "counterfactual"]
                for kind in kinds:
                    if kind == "counterfactual" and not _has_non_applied_edits(full):
                        print(f"counterfactual {args.task} run={args.run} skipped: "
                              "no non-applied edit attempts", flush=True)
                        continue
                    if not gold_valid:
                        records.append({"task": args.task, "run_id": args.run,
                                        "kind": kind, "gold_local": "N",
                                        "gold_first": gf.get("gold_first"),
                                        "agent_passed": "UNVERIFIED",
                                        "candidate_sha": "not-run", "from_cache": True,
                                        "notes": "gold not valid locally; not run"})
                        continue
                    records.append(_replay_candidate(
                        eng, kb, tasks_gold, repo, args.task, gt["base_commit"],
                        args.run, full, kind, gf, gold_valid, gpt, time_left, mode))
            module_checks = list(eng.module_file_checks)
        _flush_recon_index(kb)
        ok, report = guard.verify_after()
        io.safe_write(kb / "replays" / "clone_state.json",
                      io.dumps_json(_clone_state_from(ok, report, module_checks)))
        for r in records:
            _print_rec(r)
        if records:
            _merge_replays_jsonl(kb, records)
        _write_clone_status_final(kb)
    print(f"REPLAY OK task={args.task} gold={gf.get('gold_first')} records={len(records)} "
          f"clone_state={'CLEAN' if ok else 'BUILDER VIOLATION'} "
          f"env_freeze_identical={(eng.freeze_check or {}).get('identical')}", flush=True)
    return 0 if ok else 4


def cmd_gold_gate(args):
    """D5-20: gold-first for every task of one repo (resumable via the gold cache)."""
    t0 = time.time()
    g, kb = paths.gemma_root(), paths.kb_root()
    repo = _REPO_ARG[args.repo]
    tasks_gold = gold.build_tasks_gold(g / "comp_files" / "tasks.jsonl")
    all_tasks = sorted(t for t, v in tasks_gold["tasks"].items() if v["repo"] == repo)
    if args.tasks:
        bad = sorted(set(args.tasks) - set(all_tasks))
        if bad:
            print(f"tasks not in repo {repo}: {', '.join(bad)}", file=sys.stderr)
            return 1
        tasks = sorted(set(args.tasks))
    else:
        tasks = all_tasks
    if replay.clone_for(repo)[0] is None:
        print(f"no local clone for {repo}", file=sys.stderr)
        return 1
    mode = args.required_nodes
    replay.load_raw_tasks(g / "comp_files" / "tasks.jsonl")
    tally = {"cached": 0, "ran": 0, "not_run": 0}
    verdicts = {}
    with lock.BuildLock(kb) as lk:
        try:
            lk.acquire(wait_s=args.lock_wait_s or 0.0)
        except TimeoutError:
            print("build lock held by a live process", file=sys.stderr)
            return 8
        guard = replay.CloneGuard(_replay_clones())
        guard.snapshot_before()
        with replay.ReplayEngine(tasks_gold) as eng:
            for task in tasks:
                gt = tasks_gold["tasks"][task]
                key = replay.gold_key(gt["task_fingerprint"],
                                      replay.pins_at_commit(repo, task, gt["base_commit"]),
                                      mode, eng.env_python, eng.env_pytest)
                cached = None if args.force else replay.read_gold(task, key)
                if cached is not None:
                    tally["cached"] += 1
                    verdicts[task] = cached.get("gold_first")
                    print(f"{task} CACHED {cached.get('gold_first')} mode={mode} "
                          f"reason={cached.get('reason') or '-'}", flush=True)
                    continue
                left = _deadline_left(t0, args.deadline_s)
                if left < 120:
                    tally["not_run"] += 1
                    verdicts[task] = "not run (deadline)"
                    print(f"{task} not run (deadline)", flush=True)
                    continue
                ts = time.time()
                gf, _ran = _gold_cached_or_run(eng, replay, repo, task, gt, mode, True,
                                               max(30, min(300, int((left - 30) / 2))))
                tally["ran"] += 1
                verdicts[task] = gf.get("gold_first")
                print(f"{task} RAN {gf.get('gold_first')} mode={mode} "
                      f"secs={time.time() - ts:.1f} pins={','.join(gf.get('pins', [])) or '-'} "
                      f"reason={gf.get('reason') or '-'}", flush=True)
            module_checks = list(eng.module_file_checks)
        ok, report = guard.verify_after()
        io.safe_write(kb / "replays" / "clone_state.json",
                      io.dumps_json(_clone_state_from(ok, report, module_checks)))
        cov = goldcov.build(kb, tasks_gold, replay._TASKS_RAW, replay.RP_VERSION)
        io.safe_write(kb / "replays" / "gold_coverage.json", io.dumps_json(cov))
        _write_clone_status_final(kb)
    from collections import Counter as _C
    print(f"GOLD-GATE repo={args.repo} mode={mode} tasks={len(tasks)} "
          f"cached={tally['cached']} ran={tally['ran']} not_run={tally['not_run']} "
          f"by_verdict={dict(sorted(_C(verdicts.values()).items()))} "
          f"clone_state={'CLEAN' if ok else 'BUILDER VIOLATION'} "
          f"env_freeze_identical={(eng.freeze_check or {}).get('identical')} "
          f"secs={time.time() - t0:.0f}", flush=True)
    return 0 if ok else 4


# --------------------------------------------------------------- gate-build/check

def cmd_gate_build(args):
    """D5-26: create one new gate dir; prints the push command for the USER only."""
    try:
        r = gatebuild.build_gate(args.audit, args.base, args.name, args.change_spec)
    except gatebuild.GateError as e:
        print(f"GATE-BUILD REFUSED: {e}", file=sys.stderr)
        return 1
    print(f"GATE-BUILD OK {r['dir']}")
    print(f"kernel id: {r['kernel_id']}")
    for a in r["applied"]:
        print(f"applied: {a['file']} ({a['kind']})")
    print(f"prereg: {r['prereg']}")
    print("next: build_kb.py gate-check --dir <dir>; then the USER (never this tool) may run:")
    print(r["push"])
    return 0


def cmd_gate_check(args):
    ok, lines = gatebuild.check_gate(args.dir)
    for ln in lines:
        print(ln)
    return 0 if ok else 1


# ------------------------------------------------------------------------- parser

def build_parser():
    p = argparse.ArgumentParser(prog="build_kb.py", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="build the KB")
    b.add_argument("--replay", action="store_true")
    b.add_argument("--replay-budget-s", type=float, default=0.0)
    b.add_argument("--deadline-s", type=float, default=None)
    b.add_argument("--lock-wait-s", type=float, default=0.0)
    b.add_argument("--force-replay", action="store_true",
                   help="ignore the replay cache and re-run every candidate")
    b.add_argument("--replay-scope", choices=["min", "rich", "all"], default="rich",
                   help="min = curated min set; rich (default) + rich tiers 1-3; "
                        "all = + fastapi")
    b.add_argument("--required-nodes", choices=["added", "hunk"], default="added")
    b.set_defaults(fn=cmd_build)

    r = sub.add_parser("replay", help="replay specific candidates (gold first)")
    r.add_argument("--task", required=True)
    rg = r.add_mutually_exclusive_group(required=True)
    rg.add_argument("--run", help="run_id (G-relative POSIX) of the row to replay")
    rg.add_argument("--candidate", help="manual candidate patch file")
    rg.add_argument("--gold", action="store_true", help="gold/base controls only")
    r.add_argument("--kind", choices=["as_run", "final", "counterfactual", "intent"])
    r.add_argument("--force", action="store_true")
    r.add_argument("--required-nodes", choices=["added", "hunk"], default="added")
    r.add_argument("--deadline-s", type=float, default=None)
    r.add_argument("--lock-wait-s", type=float, default=0.0)
    r.set_defaults(fn=cmd_replay)

    gg = sub.add_parser("gold-gate", help="gold-first for a repo's tasks (resumable)")
    gg.add_argument("--repo", choices=["rich", "fastapi"], required=True)
    gg.add_argument("--tasks", nargs="+")
    gg.add_argument("--deadline-s", type=float, default=None)
    gg.add_argument("--required-nodes", choices=["added", "hunk"], default="added")
    gg.add_argument("--force", action="store_true")
    gg.add_argument("--lock-wait-s", type=float, default=0.0)
    gg.set_defaults(fn=cmd_gold_gate)

    sub.add_parser("check-fresh").set_defaults(fn=cmd_check_fresh)

    rp = sub.add_parser("report-path")
    rp.add_argument("--date")
    rp.add_argument("--slug")
    rp.add_argument("--from", dest="frm")
    rp.add_argument("--kind", choices=["audit", "refute", "final"], default="audit")
    rp.set_defaults(fn=cmd_report_path)

    pf = sub.add_parser("preflight")
    pf.add_argument("--proposal", required=True)
    pf.add_argument("--slug", required=True)
    pf.add_argument("--date", required=True)
    pf.set_defaults(fn=cmd_preflight)

    v = sub.add_parser("verdict")
    v.add_argument("--a", required=True)
    v.add_argument("--b", required=True)
    v.set_defaults(fn=cmd_verdict)

    lc = sub.add_parser("leakcheck")
    lc.add_argument("--scope", choices=["config", "tooling"], default="config")
    lc.add_argument("file")
    lc.set_defaults(fn=cmd_leakcheck)

    c = sub.add_parser("card")
    c.add_argument("run", nargs="?")
    c.add_argument("task", nargs="?")
    c.add_argument("--task", dest="task_opt")
    c.add_argument("--limit", type=int, default=40,
                   help="max rows printed after the group summary (0 = all)")
    c.add_argument("--stack", choices=["kaggle", "local-rig", "local-sweep", "colab",
                                       "unknown"],
                   help="only rows whose stack.platform equals this")
    c.set_defaults(fn=cmd_card)

    cl = sub.add_parser("claims")
    cl.add_argument("--task")
    cl.add_argument("--version")
    cl.add_argument("--lever")
    cl.add_argument("--text", help="case-insensitive regex over heading + text + facts")
    cl.add_argument("--status", help="SUPPORTED | CONTRADICTED | UNVERIFIED | SUPERSEDED")
    cl.add_argument("--limit", type=int, default=50, help="max claims printed (0 = all)")
    cl.set_defaults(fn=cmd_claims)

    pu = sub.add_parser("pull")
    pu.add_argument("--slug", action="append", default=[],
                    help="comfyops/<slug> (repeatable; no /N version suffix)")
    pu.add_argument("--submissions", action="store_true",
                    help="snapshot `competitions submissions` + `kernels list --mine`")
    pu.add_argument("--targets", action="store_true",
                    help="auto pull targets (D5-11) from the newest snapshots")
    pu.add_argument("--max", type=int, default=12, help="max output pulls this run")
    pu.add_argument("--force", action="store_true", help="re-pull already-pulled slugs")
    pu.add_argument("--dry-run", action="store_true",
                    help="print targets/argv only; no subprocess call")
    pu.add_argument("--for-ref", help="submission ref the explicit --slug pull is for")
    pu.set_defaults(fn=cmd_pull)

    gb = sub.add_parser("gate-build", help="create ONE new G\\submit_<name> gate dir from a "
                                           "PROCEED final audit (never pushes)")
    gb.add_argument("--audit", required=True, help="the FINAL report (<date>-<slug>-final.md)")
    gb.add_argument("--base", required=True, help="G-relative frozen base kernel dir")
    gb.add_argument("--name", required=True, help="^[a-z0-9][a-z0-9_]{1,40}$")
    gb.add_argument("--change-spec", required=True, help="JSON {variable, changes:[...]}")
    gb.set_defaults(fn=cmd_gate_build)

    gc = sub.add_parser("gate-check", help="verify a gate dir built by gate-build")
    gc.add_argument("--dir", required=True)
    gc.set_defaults(fn=cmd_gate_check)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    # normalize card --task
    if getattr(args, "cmd", None) == "card" and getattr(args, "task_opt", None):
        args.task = args.task_opt
        args.run = None
    try:
        return args.fn(args)
    except io.SafeWriteError as e:
        print(f"SAFE-WRITE PROTECTED: {e}", file=sys.stderr)
        return 5
    except replay.EnvFreezeError as e:
        print(f"ENV-FREEZE MISMATCH: {e}", file=sys.stderr)
        return 4


if __name__ == "__main__":
    sys.exit(main())
