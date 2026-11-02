"""Failure classification (design §10, version fc-3).

First matching rule wins: RESOLVED, INFRA, WRONG-FIX, LANDED-NOT-SUBMITTED,
FOUND-NOT-LANDED, LOCATE. Tool-call malformation is NOT INFRA (F8); such rows
fall through to stage-based classes. Rows without a trace get only the classes
decidable from the log.
"""
from __future__ import annotations

FC_VERSION = "fc-3"


def classify(outcome, trace, near_miss, harness_events, config, labels):
    """Return (failure_class, failure_subclass, reason, evidence)."""
    evidence = []
    resolved = (outcome or {}).get("resolved")
    patch_chars = (outcome or {}).get("patch_chars") or 0

    # 1. RESOLVED
    if resolved:
        return "RESOLVED", None, None, evidence

    # 2. INFRA
    for ev in harness_events or []:
        if ev["template"] == "VERIFY_TEST_PATCH_FAIL":
            return "INFRA", "VERIFY_TEST_PATCH_FAIL", None, [ev["text"]]
    # SAMPLE_ADAPTER predicate
    if config and config.get("adapter_is_sample") and config.get("adapter"):
        lab = (labels or {}).get("chosen", "") or ""
        if "lora" in lab.lower() or "adapter" in lab.lower() \
                or (config.get("adapter_source") and "sample_submission" in str(config["adapter_source"])):
            return "INFRA", "RUN_INVALID", "SAMPLE_ADAPTER", evidence
    if (outcome or {}).get("missing_reason") == "kernel failed":
        return "INFRA", "KERNEL_FAILED", None, evidence

    if trace is None:
        # only log-level classes are decidable
        if outcome is None:
            return None, None, "no trace; outcome missing", evidence
        return None, None, "no trace: patch_chars cannot separate LOCATE from FOUND-NOT-LANDED", evidence

    # 3. WRONG-FIX
    if patch_chars > 0:
        for ev in harness_events or []:
            if ev["template"] == "VERIFY_AGENT_PATCH_FAIL":
                return "WRONG-FIX", "VERIFY_AGENT_PATCH_FAIL", None, [ev["text"]]
        return "WRONG-FIX", "UNREPLAYED", None, evidence

    # near-miss driven
    furthest = (near_miss or {}).get("furthest_stage")
    stopped = (near_miss or {}).get("stopped_by", "UNKNOWN")

    # 4. LANDED-NOT-SUBMITTED: APPLIED reached but patch_chars==0
    stages = (near_miss or {}).get("stages", {})
    if stages.get("APPLIED", {}).get("reached") and patch_chars == 0:
        if trace.get("post_submit_edits"):
            return "LANDED-NOT-SUBMITTED", "EDIT_AFTER_SUBMIT", None, evidence
        return "LANDED-NOT-SUBMITTED", "RECON_MISMATCH", None, evidence

    # 5. FOUND-NOT-LANDED
    if furthest in ("SAW_GOLD_HUNK", "WROTE_GOLD_CHANGE", "TRIED_APPLY"):
        if furthest == "SAW_GOLD_HUNK":
            return "FOUND-NOT-LANDED", "SAW_ONLY", None, evidence
        sub = stopped if stopped not in ("UNKNOWN", "NEVER_ATTEMPTED") else "NEVER_ATTEMPTED"
        return "FOUND-NOT-LANDED", sub, None, evidence

    # 6. LOCATE
    if furthest == "READ_GOLD_FILE":
        return "LOCATE", "FILE_NOT_HUNK", None, evidence
    return "LOCATE", "NO_GOLD_FILE", None, evidence
