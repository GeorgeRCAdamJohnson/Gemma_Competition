"""Source discovery and coverage (design §5).

Walks G to directory depth <= 8, classifies every file/dir with exactly one
`kind` (first match wins), lists large binaries without reading them, and
computes the input + discovery fingerprints used for freshness.
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
import re

from . import paths


@dataclasses.dataclass
class Item:
    g_rel: str
    kind: str
    parsed: bool
    reason: str = ""
    size: int = 0


_PASTED_LOG_EXTS = {"", ".txt", ".log"}
_RESULT_HINT = ("resolved=", "-> resolved", "[done]", "[par done]")


def _is_json_kernel_log(p: pathlib.Path) -> bool:
    try:
        with p.open("r", encoding="utf-8", errors="replace") as fh:
            head = fh.read(4096).lstrip()
        if not head.startswith("["):
            return False
        # cheap probe for the record shape without loading the whole file
        return '"stream_name"' in head and '"data"' in head
    except OSError:
        return False


def _json_log_has_results(p: pathlib.Path) -> bool:
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return False
    if not isinstance(data, list):
        return False
    for entry in data:
        if not isinstance(entry, dict):
            continue
        txt = entry.get("data", "")
        if isinstance(txt, str) and ("resolved=" in txt):
            return True
    return False


def _text_has_result(p: pathlib.Path) -> bool:
    try:
        text, _ = _read_small(p)
    except OSError:
        return False
    return any(h in text for h in _RESULT_HINT)


def _read_small(p: pathlib.Path, limit: int = 200_000) -> tuple[str, int]:
    raw = p.read_bytes()[:limit]
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace"), 0
    if raw[:3] == b"\xef\xbb\xbf":
        raw = raw[3:]
    return raw.decode("utf-8", errors="replace"), 0


def _depth(p: pathlib.Path, g: pathlib.Path) -> int:
    return len(p.resolve().relative_to(g.resolve()).parts)


def _skip_dir(name: str, g_rel: str) -> bool:
    if name in paths.SKIP_DIRS:
        return True
    if any(name.startswith(pre) for pre in paths.SKIP_DIR_PREFIXES):
        return True
    if g_rel == "local_eval/repos" or g_rel.startswith("local_eval/repos/"):
        return True
    # kb/ itself is entered only to reach kb/pulled and kb/replays/manual
    # (REV5: the REV4 rule skipped "kb" outright, so kb/pulled was never seen).
    if g_rel.startswith("kb/") and not (
        g_rel.startswith("kb/pulled")
        or g_rel == "kb/replays"
        or g_rel.startswith("kb/replays/manual")
    ):
        return True
    return False


# --- REV5 helpers (R5.3) ---------------------------------------------------

SWEEP_SUFFIXES = ("results", "pinned", "guard", "trace", "sweep")
_SWEEP_RE = re.compile(r"^(?P<tag>.+?)\.(?P<suf>results|pinned|guard|trace|sweep)\.jsonl$")
# companion files that belong to a tag but are not row sources
_SWEEP_AUX_RE = re.compile(
    r"^(?P<tag>.+?)\.(?:console\.txt|pinned\.console\.txt|sweep\.state\.json|"
    r"trace\.jsonl\.stall\..+|verify\.log|log|console\.log)$")
TASK_RESULTS_NAMES = ("task_results.jsonl",)
NOTEBOOK_NAMES = ("notebook_src.py",)


def kernel_family(kid: str) -> str:
    """D5-5 kernel_family of a comfyops/ kernel id."""
    slug = kid.split("/", 1)[1] if "/" in kid else kid
    if slug.startswith("gemma-sibling-conform-"):
        return "sibling-conform"
    if slug.startswith("gemma-submission-packager"):
        return "packager"
    if "full129" in slug:
        return "full129-eval"
    if "probe" in slug:
        return "probe"
    if "train" in slug:
        return "train"
    return "other"


def task_results_path(run_dir: pathlib.Path) -> pathlib.Path | None:
    """results/task_results.jsonl, else task_results.jsonl beside traces/."""
    for p in (run_dir / "results" / "task_results.jsonl", run_dir / "task_results.jsonl"):
        if p.is_file():
            return p
    return None


def sweep_family(tag: str) -> str:
    """Group key for a sweep tag (coverage rendering): tag minus `_r<N>...`."""
    m = re.match(r"^(.*?)_r(?:ep)?\d+(?:_.*)?$", tag)
    return m.group(1) if m and m.group(1) else tag


def discover(g: pathlib.Path | None = None) -> dict:
    """Return discovery result: run dirs, submit dirs, items, read-file list."""
    g = g if g is not None else paths.gemma_root()
    run_dirs: list[str] = []
    failed_run_dirs: list[str] = []
    empty_run_dirs: list[str] = []
    pasted_logs: list[str] = []
    reference_logs: list[str] = []
    submit_dirs: list[str] = []
    staged_submissions: list[str] = []
    rig_runs: list[str] = []
    eval_runs: list[str] = []
    pulled_runs: list[str] = []
    scored_zips: list[str] = []
    zip_archives: list[str] = []
    lb_snapshots: list[str] = []
    foreign_tools: list[str] = []
    reference_kernels: list[str] = []
    partials: list[str] = []
    kernel_dirs: dict[str, dict] = {}
    sweep_files: dict[str, dict[str, str]] = {}
    sweep_aux: dict[str, list[str]] = {}
    sweep_other: list[str] = []
    items: list[Item] = []
    read_files: list[pathlib.Path] = []
    beyond_depth: list[str] = []

    def add_item(it: Item):
        items.append(it)

    for dirpath, dirnames, filenames in _walk(g):
        d = pathlib.Path(dirpath)
        g_rel = paths.rel_posix(d, g)
        depth = _depth(d, g) if g_rel != "." else 0

        # REV5: incomplete pulls are listed and skipped (never parsed)
        if g_rel != "." and d.name.endswith(".partial"):
            partials.append(g_rel)
            add_item(Item(g_rel, "partial", False, "incomplete pull (.partial), skipped"))
            dirnames[:] = []
            continue
        # kb/ and kb/replays are pass-through containers (their files are ours)
        if g_rel in ("kb", "kb/replays"):
            keep = ("pulled", "replays") if g_rel == "kb" else ("manual",)
            dirnames[:] = sorted(n for n in dirnames if n in keep)
            continue
        # REV5: local sweep runs are grouped per tag, never listed per file
        if g_rel == paths.SWEEP_ROOT:
            for name in sorted(filenames):
                m = _SWEEP_RE.match(name)
                if m:
                    sweep_files.setdefault(m.group("tag"), {})[m.group("suf")] = \
                        g_rel + "/" + name
                    continue
                m = _SWEEP_AUX_RE.match(name)
                if m:
                    sweep_aux.setdefault(m.group("tag"), []).append(g_rel + "/" + name)
                    continue
                sweep_other.append(g_rel + "/" + name)
            for name in sorted(dirnames):
                if name.endswith(".patches"):
                    sweep_aux.setdefault(name[:-len(".patches")], []).append(
                        g_rel + "/" + name)
                else:
                    sweep_other.append(g_rel + "/" + name)
            dirnames[:] = []
            continue

        # prune
        kept = []
        for name in dirnames:
            child_rel = (g_rel + "/" + name) if g_rel != "." else name
            if _skip_dir(name, child_rel):
                continue
            if depth + 1 > paths.MAX_WALK_DEPTH:
                if any((d / name).iterdir()):
                    beyond_depth.append(child_rel)
                continue
            kept.append(name)
        dirnames[:] = kept

        has_traces = (d / "results" / "traces").is_dir()
        has_kmeta = (d / "kernel-metadata.json").is_file()
        has_agent = (d / "agent.yaml").is_file()
        has_eval = (d / "eval_config.yaml").is_file()
        is_top = d.parent.resolve() == g.resolve()
        # a Kaggle run's own results/ dir has the same shape; it is not a rig run
        is_rig = ((d / "traces").is_dir() and (d / "task_results.jsonl").is_file()
                  and not (d.name == "results" and any(d.parent.glob("*.log"))))
        under_pulled = g_rel.startswith("kb/pulled/")

        # classify this directory as a run-ish container
        logs = [f for f in filenames if f.endswith(".log")]
        json_logs = [f for f in logs if _is_json_kernel_log(d / f)]
        # scored-zip = a packager-style output: submission.zip + submission/ and
        # no run results (every Kaggle run dir also carries its own zip)
        is_scored_zip = ((d / "submission.zip").is_file() and (d / "submission").is_dir()
                         and not has_traces and not (d / "results").is_dir())

        if is_rig and not has_traces:
            # local parity rig: traces/ + task_results.jsonl directly in the dir
            rig_runs.append(g_rel)
            add_item(Item(g_rel, "rig-run", True))
            dirnames[:] = []
        elif has_traces or json_logs:
            # a run dir
            jl = json_logs[0] if json_logs else None
            if under_pulled:
                pulled_runs.append(g_rel)
                if (d / "_pull_meta.json").is_file():
                    add_item(Item(g_rel, "pulled-run", True))
                else:
                    add_item(Item(g_rel, "pulled-legacy", True,
                                  "no _pull_meta.json (manual pull; attribution unverified)"))
            elif jl and _json_log_has_results(d / jl):
                run_dirs.append(g_rel)
                add_item(Item(g_rel, "run-dir", True))
            elif jl and has_traces and task_results_path(d) is not None:
                # REV5: full-129 eval kernels log no `resolved=` lines
                eval_runs.append(g_rel)
                add_item(Item(g_rel, "kaggle-eval-run", True,
                              "outcomes from task_results.jsonl (no resolved= lines)"))
            elif jl and is_scored_zip and not has_traces:
                pass  # a packager output: recorded as scored-zip below
            elif jl:
                failed_run_dirs.append(g_rel)
                add_item(Item(g_rel, "run-dir-failed", True, "0 result rows"))
            elif has_traces:
                run_dirs.append(g_rel)
                add_item(Item(g_rel, "run-dir", True))
        elif (d / "submission").is_dir() and all(
            (d / lf).stat().st_size == 0 for lf in logs
        ) and logs:
            empty_run_dirs.append(g_rel)
            add_item(Item(g_rel, "run-dir-empty", True, "0-byte log, no results"))

        if is_scored_zip:
            scored_zips.append(g_rel)
            add_item(Item(g_rel, "scored-zip", True, "submission.zip vs submission/ (zip_drift)"))

        # submit-dir vs staged-submission (D3-4). A kernel source pulled with
        # `kernels pull -m` (kb/pulled/<slug>/<utc>/source) is evidence for that
        # pulled run (dev-harness pass), never a local submit-dir.
        if has_kmeta and under_pulled:
            add_item(Item(g_rel, "pulled-source", False,
                          "kernel source pulled with -m; read for its pulled run"))
        elif has_kmeta:
            try:
                kmeta = json.loads((d / "kernel-metadata.json").read_text(encoding="utf-8"))
                kid = str(kmeta.get("id", ""))
                code_file = str(kmeta.get("code_file", "") or "")
            except Exception:
                kid, code_file = "", ""
            if kid.startswith(paths.OWNER_PREFIX):
                fam = kernel_family(kid)
                submit_dirs.append(g_rel)
                kernel_dirs[g_rel] = {"id": kid, "family": fam, "code_file": code_file}
                add_item(Item(g_rel, "submit-dir", True, f"kernel_family={fam}"))
            else:
                reference_kernels.append(g_rel)
                add_item(Item(g_rel, "reference-kernel", False,
                              f"foreign kernel {kid or '?'} (not comfyops/)"))
        elif has_agent and has_eval and is_top and d.name.startswith("submit_"):
            # D3-4: a top-level submit_* dir with agent.yaml+eval_config.yaml but
            # NO kernel-metadata.json is a staged submission (submit_t4096,
            # submit_branch_final), never a submit-dir or submission-folder.
            staged_submissions.append(g_rel)
            add_item(Item(g_rel, "staged-submission", True))

        # files inside this directory
        for name in filenames:
            fp = d / name
            try:
                size = fp.stat().st_size
            except OSError:
                continue
            frel = (g_rel + "/" + name) if g_rel != "." else name
            ext = fp.suffix.lower()
            if g_rel == "." and name in paths.FOREIGN_TOOLS:
                foreign_tools.append(frel)
                add_item(Item(frel, "foreign-tool", False,
                              "the user's own tool; listed, never run", size))
                continue
            if g_rel == "local_eval/pull_submissions" and ext == ".zip":
                zip_archives.append(frel)
                add_item(Item(frel, "submission-zip-archive", True,
                              "submission zip (config hashes)", size))
                continue
            if name == "lb.csv" and d.name == "leaderboard":
                lb_snapshots.append(frel)
                add_item(Item(frel, "lb-snapshot", False,
                              "public LB snapshot; read by the LB step (FEAT-002)", size))
                continue
            if size > paths.LARGE_FILE_BYTES:
                add_item(Item(frel, "large-binary", False, "over 50 MB, not read", size))
                continue
            # pasted logs: directly inside G or G/Outputs
            parent_rel = g_rel
            if (parent_rel in (".", "Outputs")) and ext in _PASTED_LOG_EXTS:
                if name not in ("build_kb.py",) and _text_has_result(fp):
                    pasted_logs.append(frel)
                    add_item(Item(frel, "pasted-log", True, size=size))
                    read_files.append(fp)
                    continue
            # reference log: result-like text outside run/pasted locations
            if ext in _PASTED_LOG_EXTS and parent_rel not in (".", "Outputs"):
                if _text_has_result(fp) and not has_traces and not json_logs:
                    reference_logs.append(frel)
                    add_item(
                        Item(frel, "reference-log", False,
                             "result-like lines outside pasted-log locations", size))
                    continue

    # sweep tags: one item per tag (never per file)
    sweep_tags = sorted(set(sweep_files) | set(sweep_aux))
    for tag in sweep_tags:
        sufs = sorted(sweep_files.get(tag, {}))
        has_rows = bool({"results", "pinned"} & set(sufs))
        if has_rows:
            reason = "summary-only rows (" + "+".join(sufs) + ")"
        elif sufs == ["sweep"]:
            reason = "aggregate .sweep.jsonl only (per-tag files are the row source)"
        else:
            reason = "no results/pinned file (" + ("+".join(sufs) or "aux files only") + ")"
        add_item(Item(paths.SWEEP_ROOT + "/" + tag, "sweep-tag", has_rows, reason))
    for o in sweep_other:
        add_item(Item(o, "sweep-tag", False, "not attributable to a sweep tag; not parsed"))

    return {
        "run_dirs": sorted(set(run_dirs)),
        "failed_run_dirs": sorted(set(failed_run_dirs)),
        "empty_run_dirs": sorted(set(empty_run_dirs)),
        "pasted_logs": sorted(set(pasted_logs)),
        "reference_logs": sorted(set(reference_logs)),
        "submit_dirs": sorted(set(submit_dirs)),
        "staged_submissions": sorted(set(staged_submissions)),
        "rig_runs": sorted(set(rig_runs)),
        "eval_runs": sorted(set(eval_runs)),
        "pulled_runs": sorted(set(pulled_runs)),
        "scored_zips": sorted(set(scored_zips)),
        "zip_archives": sorted(set(zip_archives)),
        "lb_snapshots": sorted(set(lb_snapshots)),
        "foreign_tools": sorted(set(foreign_tools)),
        "reference_kernels": sorted(set(reference_kernels)),
        "partials": sorted(set(partials)),
        "kernel_dirs": {k: kernel_dirs[k] for k in sorted(kernel_dirs)},
        "sweep_tags": sweep_tags,
        "sweep_tag_files": {t: dict(sorted(sweep_files.get(t, {}).items()))
                            for t in sweep_tags},
        "sweep_aux": {t: sorted(sweep_aux.get(t, [])) for t in sweep_tags},
        "sweep_other": sorted(sweep_other),
        "items": sorted(items, key=lambda i: (i.kind, i.g_rel)),
        "read_files": read_files,
        "beyond_depth": sorted(set(beyond_depth)),
    }


def _walk(g: pathlib.Path):
    import os

    yield from os.walk(g)


def input_fingerprint(g: pathlib.Path, extra_files: list[pathlib.Path]) -> dict:
    """sha256 over (relpath,size,mtime_ns) of the files the build reads.

    Includes curated inputs, log, tasks, harness, run-dir/log/submission files,
    and submit-dir sources. Excludes workflow bookkeeping (build_plan.md,
    build_verification.md, audits/, proposals/, _build_reviews/).
    """
    import hashlib

    seen: dict[str, tuple[int, int]] = {}

    def add(p: pathlib.Path):
        try:
            st = p.stat()
        except OSError:
            return
        seen[paths.rel_posix(p, g)] = (st.st_size, st.st_mtime_ns)

    # curated inputs (five)
    kb = g / "kb"
    for name in ("claims.jsonl", "run_labels.json", "lever_lexicon.json",
                 "replay_set.json", "submissions.csv"):
        add(kb / "curated" / name)
    # top-level inputs
    add(g / "GEMMA_EXPERIMENT_LOG.md")
    add(g / "comp_files" / "tasks.jsonl")
    add(g / "comp_files" / "HARNESS_README.md")
    add(g / "RICH_48_DIFFICULTY_MAP.md")
    add(g / "FASTAPI_BASELINE_AND_EDIT_TALLY.md")
    # REV5 (D5-13): the banner depends on the steering file's own text
    add(g.parent / ".kiro" / "steering" / "gemma-submission-protocol.md")
    for p in extra_files:
        add(p)
    blob = "\n".join(f"{k}:{v[0]}:{v[1]}" for k, v in sorted(seen.items()))
    return {
        "fingerprint": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
        "count": len(seen),
        "files": seen,
    }
