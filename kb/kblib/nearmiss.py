"""Near-miss line-level fuzzy matcher (design §9, version nm-3).

Computes, per (run, task), how close the agent got to the gold fix across stages
(READ_GOLD_FILE -> SAW_GOLD_HUNK -> WROTE_GOLD_CHANGE -> TRIED_APPLY -> APPLIED
-> SCORED_NONEMPTY -> RESOLVED), citing trace step_ids, with a real line
similarity score. Cross-task false-positive control (§9.4) is in cross_task_fp.

Matching: normalize lines, drop trivial/blank/punctuation lines, then an exact
normalized-line lookup first and a difflib + identifier-Jaccard fuzzy fallback
(ratio >= 0.90 AND identifier Jaccard >= 0.70) against the gold added lines.
"""
from __future__ import annotations

import difflib
import hashlib
import keyword
import re

from . import reconstruct

NM_VERSION = "nm-3"
FP_CAP = 40  # REV5 D5-24: cross-task FP control samples <= 40 other tasks/trace

STAGES = ["READ_GOLD_FILE", "SAW_GOLD_HUNK", "WROTE_GOLD_CHANGE", "TRIED_APPLY",
          "APPLIED", "SCORED_NONEMPTY", "RESOLVED"]

_RATIO = 0.90
_JACCARD = 0.70

_TRIVIAL = {"else:", "try:", "finally:", "pass", "return", "break", "continue",
            ")", "]", "}", "),", "],", "},", '"""', "'''", "):"}
_IDENT = re.compile(r"[A-Za-z_]\w*")
_KW = frozenset(keyword.kwlist)
_GUTTER = re.compile(r"^\s*(?:[\w./-]+:)?\d+[:-]\s?")


def norm(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def is_trivial(nline: str) -> bool:
    if nline == "" or len(nline) < 6:
        return True
    if nline in _TRIVIAL:
        return True
    if nline.startswith("#"):
        return True
    if all(ch in ")]}:," for ch in nline):
        return True
    return False


def _idents(nline: str) -> frozenset:
    return frozenset(t for t in _IDENT.findall(nline) if t not in _KW)


def _split_lines(text: str):
    """Split candidate text into normalized non-trivial lines (gutter-stripped)."""
    out = []
    for raw in text.replace("\\n", "\n").split("\n"):
        s = raw
        if _GUTTER.match(s):
            s = _GUTTER.sub("", s)
        n = norm(s)
        if not is_trivial(n):
            out.append(n)
    return out


# --------------------------------------------------------------------- indexes

class GoldIndex:
    """Built once per build over tasks_gold."""

    def __init__(self, tasks_gold):
        self.by_task = {}          # task -> [hunk dicts with normalized sets]
        self.exact_added = {}      # normalized added line -> [(task, hunk_i)]
        self.ident_added = {}      # identifier -> set((task, hunk_i, nline))
        self._built = False
        for task, gt in tasks_gold["tasks"].items():
            hunks = []
            for hi, h in enumerate(gt.get("hunks", [])):
                added = [norm(x) for x in h.get("added", [])]
                added_nt = [n for n in added if not is_trivial(n)]
                removed_nt = [norm(x) for x in h.get("removed", [])
                              if not is_trivial(norm(x))]
                hunks.append({
                    "file": h["file"], "old_start": h["old_start"],
                    "old_len": h["old_len"],
                    "added_nt": added_nt, "removed_nt": removed_nt,
                    "specificity": h.get("specificity", 1.0),
                })
                for n in added_nt:
                    self.exact_added.setdefault(n, []).append((task, hi))
                    for ident in _idents(n):
                        self.ident_added.setdefault(ident, set()).add((task, hi, n))
            self.by_task[task] = hunks
        # determinism: freeze inverted-index values to SORTED tuples so set
        # iteration order (hash-randomized) can never leak into output ordering.
        for ident in list(self.ident_added):
            self.ident_added[ident] = tuple(sorted(self.ident_added[ident]))

    def candidate_hits(self, cand_lines, task):
        """Which gold added lines of `task` the candidate lines match.

        Returns {hunk_i: set(matched_added_nt)}. Exact first, then fuzzy via the
        identifier inverted index (restricted to this task's hunks).
        """
        hits = {}
        hunks = self.by_task.get(task, [])
        for cl in cand_lines:
            # exact
            matched = False
            for (t, hi) in self.exact_added.get(cl, []):
                if t == task:
                    hits.setdefault(hi, set()).add(cl)
                    matched = True
            if matched:
                continue
            # fuzzy: only against gold added lines sharing >=1 identifier
            cids = _idents(cl)
            if not cids:
                continue
            cand_hunk_lines = set()
            for ident in cids:
                for (t, hi, n) in self.ident_added.get(ident, ()):
                    if t == task:
                        cand_hunk_lines.add((hi, n))
            for (hi, n) in sorted(cand_hunk_lines):
                if _fuzzy_match(cl, n, cids):
                    hits.setdefault(hi, set()).add(n)
        return hits


def _fuzzy_match(a, b, aids=None):
    if abs(len(a) - len(b)) > 0.3 * max(len(a), len(b)):
        return False
    aids = aids if aids is not None else _idents(a)
    bids = _idents(b)
    if not aids or not bids:
        return False
    jac = len(aids & bids) / len(aids | bids)
    if jac < _JACCARD:
        return False
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < _RATIO or sm.quick_ratio() < _RATIO:
        return False
    return sm.ratio() >= _RATIO


# --------------------------------------------------------------------- compute

def compute(trace, outcome, gold_task, index=None):
    """Return a near_miss row (without row_id/run_id)."""
    stages = {s: {"reached": False} for s in STAGES}
    stopped_by = "UNKNOWN"
    score = None
    matched_hunk = None

    if gold_task is None:
        return {"has_trace": trace is not None, "heuristic_version": NM_VERSION,
                "stages": stages, "furthest_stage": None,
                "stopped_by": "NO_GOLD", "confidence": "n/a (no gold)",
                "similarity": None}

    gold_files = set(gold_task.get("files", []))
    hunks = index.by_task.get(_task_of(gold_task), []) if index else []

    if trace is None:
        if outcome and outcome.get("resolved"):
            stages["RESOLVED"]["reached"] = True
            stages["SCORED_NONEMPTY"]["reached"] = True
        elif outcome and (outcome.get("patch_chars") or 0) > 0:
            stages["SCORED_NONEMPTY"]["reached"] = True
        return {"has_trace": False, "heuristic_version": NM_VERSION,
                "stages": stages, "furthest_stage": _furthest(stages),
                "stopped_by": "NO_TRACE", "confidence": "low (no trace)",
                "similarity": None}

    calls = trace.get("_calls", [])

    # READ_GOLD_FILE / SAW_GOLD_HUNK from read observations
    for c in calls:
        rp = c.get("read_path")
        if rp and _norm_path(rp) in {_norm_path(g) for g in gold_files}:
            if not stages["READ_GOLD_FILE"]["reached"]:
                stages["READ_GOLD_FILE"] = {"reached": True, "call": c["call_index"],
                                            "step_id": c["step_id"], "file": rp}
            # SAW: observation content contains >= half the removed_nt of a hunk
            obs = c.get("obs_text") or ""
            obs_lines = set(_split_lines(obs))
            for hi, h in enumerate(hunks):
                if h["file"] and _norm_path(h["file"]) != _norm_path(rp):
                    continue
                rnt = h["removed_nt"]
                if rnt:
                    need = max(1, (len(rnt) + 1) // 2)
                    present = sum(1 for r in rnt if r in obs_lines)
                    if present >= need and not stages["SAW_GOLD_HUNK"]["reached"]:
                        stages["SAW_GOLD_HUNK"] = {
                            "reached": True, "call": c["call_index"],
                            "step_id": c["step_id"], "hunk": hi, "via": "content"}

    # WROTE_GOLD_CHANGE / TRIED_APPLY / APPLIED from edit attempts (NEW side)
    best_hit_frac = 0.0
    for c in calls:
        if not c.get("is_edit"):
            continue
        on_gold = any(_norm_path(f) in {_norm_path(g) for g in gold_files}
                      for f in (c.get("edit_files") or []))
        # NEW-side candidate text
        new_text = _new_side_text(c)
        cand_lines = _split_lines(new_text) if new_text else []
        task_id = _task_of(gold_task)
        hits = index.candidate_hits(cand_lines, task_id) if (index and cand_lines) else {}
        if hits:
            for hi in sorted(hits):
                matched = hits[hi]
                total = max(1, len(hunks[hi]["added_nt"]) if hi < len(hunks) else 1)
                frac = len(matched) / total
                threshold = 1.0 if total == 1 else 0.6
                if frac >= threshold:
                    stages["WROTE_GOLD_CHANGE"] = {
                        "reached": True, "call": c["call_index"],
                        "step_id": c["step_id"], "where": "args", "hunk": hi,
                        "coverage": round(frac, 3)}
                    matched_hunk = hi
                best_hit_frac = max(best_hit_frac, frac)
        if on_gold:
            stages["TRIED_APPLY"] = {"reached": True, "call": c["call_index"],
                                     "step_id": c["step_id"]}
            if c["obs_class"] == "OK":
                stages["APPLIED"] = {"reached": True, "call": c["call_index"],
                                     "step_id": c["step_id"], "detail": "observed-only"}
            else:
                stopped_by = c["obs_class"]
    if best_hit_frac:
        score = round(best_hit_frac, 3)

    # also check WROTE in agent text messages (where: text), with provenance guard
    if not stages["WROTE_GOLD_CHANGE"]["reached"] and index:
        for c in calls:
            msg = c.get("msg")
            if not msg:
                continue
            cand_lines = _split_lines(msg)
            if not cand_lines:
                continue
            hits = index.candidate_hits(cand_lines, _task_of(gold_task))
            for hi in sorted(hits):
                matched = hits[hi]
                total = max(1, len(hunks[hi]["added_nt"]) if hi < len(hunks) else 1)
                frac = len(matched) / total
                if frac >= (1.0 if total == 1 else 0.6):
                    stages["WROTE_GOLD_CHANGE"] = {
                        "reached": True, "call": c["call_index"],
                        "step_id": c["step_id"], "where": "text", "hunk": hi,
                        "coverage": round(frac, 3)}
                    score = max(score or 0, round(frac, 3))

    if (outcome or {}).get("patch_chars", 0) and (outcome["patch_chars"] or 0) > 0:
        stages["SCORED_NONEMPTY"]["reached"] = True
    if (outcome or {}).get("resolved"):
        stages["RESOLVED"]["reached"] = True
        stages["SCORED_NONEMPTY"]["reached"] = True

    furthest = _furthest(stages)
    if stopped_by == "UNKNOWN":
        if trace.get("refused"):
            stopped_by = trace["refused"][0]["kind"]
        elif furthest in (None, "READ_GOLD_FILE", "SAW_GOLD_HUNK",
                          "WROTE_GOLD_CHANGE"):
            stopped_by = "NEVER_ATTEMPTED"
    conf = "measured (nm-3 line-level)" if index else "low (no index)"
    return {"has_trace": True, "heuristic_version": NM_VERSION, "stages": stages,
            "furthest_stage": furthest, "stopped_by": stopped_by,
            "confidence": conf, "similarity": score, "matched_hunk": matched_hunk}


def _new_side_text(call):
    """NEW-side content of an edit attempt (G2: NEW side only)."""
    if call.get("new_payload") is not None:
        return str(call["new_payload"])
    raw = call.get("raw_cmd")
    if raw:
        # statically reconstruct NEW-side literals from the command
        try:
            vfs = reconstruct.VFS(loader=lambda p: None)
            res = reconstruct.reconstruct_run_command(raw, vfs)
            if res.new_literals:
                return "\n".join(str(x) for x in res.new_literals if x)
        except Exception:
            return raw
        return raw
    return None


def _task_of(gold_task):
    return gold_task.get("_task_id")


def _norm_path(p):
    return (p or "").replace("\\", "/").strip().lstrip("/")


def _furthest(stages):
    best = None
    for s in STAGES:
        if stages[s].get("reached"):
            best = s
    return best


# --------------------------------------------------------------- cross-task FP

def cross_task_fp(trace_rows, tasks_gold, index):
    """§9.4 cross-task false-positive control.

    For every (trace, other-task A in the same repo) pair, evaluate
    WROTE_GOLD_CHANGE(A) on the trace's NEW-side content. The pre-registered bar
    is an FP rate <= 1% of (trace, other-task) pairs. Returns the measured rate.
    """
    # repo -> tasks
    repo_tasks = {}
    for task, gt in tasks_gold["tasks"].items():
        repo_tasks.setdefault(gt["repo"], []).append(task)
    sample_cache = {}

    def others_for(own_task, repo):
        # REV5 D5-24 scale guard: the FP_CAP same-repo other tasks with the
        # smallest sha256(task_id + other_id) (all if fewer). Deterministic.
        key = (own_task, repo)
        if key not in sample_cache:
            cands = [o for o in repo_tasks.get(repo, []) if o != own_task]
            cands.sort(key=lambda o: (hashlib.sha256((own_task + o).encode("utf-8"))
                                      .hexdigest(), o))
            sample_cache[key] = cands[:FP_CAP]
        return sample_cache[key]

    pairs = 0
    wrote_fp = 0
    saw_fp = 0
    for row in trace_rows:
        trace = row.get("_trace")
        if trace is None:
            continue
        own_task = row["task"]
        gt_own = tasks_gold["tasks"].get(own_task)
        if not gt_own:
            continue
        repo = gt_own["repo"]
        # candidate NEW-side lines of this trace (all edit attempts)
        cand_lines = []
        for c in trace.get("_calls", []):
            if c.get("is_edit"):
                t = _new_side_text(c)
                if t:
                    cand_lines.extend(_split_lines(t))
        cand_lines = list(dict.fromkeys(cand_lines))
        if not cand_lines:
            continue
        for other in others_for(own_task, repo):
            pairs += 1
            hits = index.candidate_hits(cand_lines, other)
            # WROTE fires if any hunk reaches coverage threshold
            fired = False
            for hi, matched in hits.items():
                hunks = index.by_task.get(other, [])
                total = max(1, len(hunks[hi]["added_nt"]) if hi < len(hunks) else 1)
                frac = len(matched) / total
                if frac >= (1.0 if total == 1 else 0.6):
                    fired = True
                    break
            if fired:
                wrote_fp += 1
    rate = (wrote_fp / pairs) if pairs else 0.0
    return {"pairs": pairs, "wrote_gold_change_fp": wrote_fp,
            "wrote_gold_change_fp_rate": round(rate, 5),
            "bar": 0.01, "passes_bar": rate <= 0.01,
            "sampling": f"hash-cap-{FP_CAP}"}
