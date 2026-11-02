# Proposal: content-correctness LoRA (multi-layer), re-derived (2026-10-15)

Type: weights (LoRA/QLoRA adapter on the frozen gemma-4-31b-it-qat-w4a16-ct). Status: UNAUDITED.
Supersedes `2026-10-14-commitment-lora-recipe.md` (audited REVISE, final `2026-10-15-commitment-lora-recipe-final.md`). This revision folds in every REVISE finding plus the 2026-10-15 host intel and the now-fixed local scorer.

## Why this, and why now (what changed since the REVISE)
Three facts moved since the commitment-LoRA recipe was audited REVISE:
1. **The target is fix-CONTENT, not commit-timing.** Curated `J-wrongfix-is-content-not-ask`: of 34 measured wrong_content rich cases, 33 edit gold's symbols in gold's files and are STILL wrong (one-char Unicode-range error on the exact gold line in rich_3535; rich_4079 diffs up to 5.5x gold size still fail). WRONG-FIX dominates (56/149 traced rich rows). The decode sweep (running separately) tests whether commit-timing is decoder-shaped; THIS adapter targets the content the model writes once it is at the right line.
2. **Adapters load + take effect in scoring — host-confirmed** (curated `J-adapter-loads-in-scoring-host-confirmed`). The "no effect" repro was softmax saturation; the scoring wheelhouse == the local wheelhouse. DESIGN RULE from the host: adapt MANY layers, not layer 0 (Gemma Sandwich-RMSNorm renormalizes a single-layer perturbation away). v2 was near-inert partly for this reason.
3. **The local gold-first scorer is fixed** (rp-4 per-task dependency pinning, APPROVED). Resolve is now measurable OFFLINE on the hard-rich tasks, so a resolve-based bar is finally checkable before any scored slot.

## The change (one lever: a multi-layer content-correctness adapter)
Train ONE low-rank QLoRA adapter on the frozen 31B, applied to a BROAD layer span (NOT layer 0), to improve the CONTENT CORRECTNESS of the edit the model writes once localized — distilled from the agent's OWN passing trajectories. Everything else (prompt, tool surface, budget, single flat agent) stays at the v6w baseline. Single flat agent only — no sub-agents (curated `J-subagents-regress`).

## REVISE findings from the prior recipe — resolved here
- **Inverted alpha fix REMOVED.** The prior recipe said "raise alpha/r 0.5 -> 2.0". That was a MISREAD: v2 was trained at alpha/r = 2.0 (r32/alpha64, all-linear; `Gemma\adapter_v2_dataset\adapter_config.json`) and the ledger records that config as OVERBAKED. Do NOT raise alpha on the premise v2 was under-driven. Start from a correctly-shaped low-rank config (below) and treat the real v2 overbake cause as epochs/data-shape, not serve-scale.
- **Edit-ATTEMPT bar REMOVED (it was vacuous).** 32/34 runs already attempt an edit; v19 hit edits 5/5 at resolve 1/5. The bar here is RESOLVE / content-correctness, not whether an edit happened.
- **Resolve clause now MEASURABLE.** The rp-4 scorer validates the hard-rich golds locally; the bar is scored through it, gold-first, with per-task dependency pins.

## Pre-registered success bar (offline-first; no scored slot until cleared)
- Comparator: the v6w-equivalent LOCAL baseline (same prompt/budget/tool-surface, NO adapter), run FIRST through the rp-4 gold-first scorer on a held-out rich set (EASY+HARD mix from `RICH_48_DIFFICULTY_MAP.md`), split so the adapter is not judged on tasks it was distilled from.
- WIN: the adapter resolves strictly MORE held-out rich tasks than the no-adapter baseline on the fixed scorer, with no PASS_TO_PASS regression on tasks the baseline already resolved (floor-guaranteed — w=0/no-adapter is a hard floor). A tie or any regression is a FAILURE, reported as such.
- Only after a local WIN does it become a FREE-GATE candidate (5-task rich gate, pre-registered bar) and only after the free gate clears does the scored slot come into play. v6w @ 0.15 stays live-best.

## Training recipe (each choice tied to the dossier / host rule)
- **Target: MULTI-LAYER** — all 60 layers (or a broad span), target_modules q_proj,k_proj,v_proj,o_proj (+ consider MLP). NOT layer 0 (host rule; Sandwich-RMSNorm). Low rank (start r=16); correctly-shaped scaling (alpha=2r=32 or use_rslora=True) chosen per the PEFT dossier, NOT as a "fix" to a misdiagnosed v2.
- **Data: self-distilled PASSING trajectories** (host-blessed): run the agent on PUBLIC GitHub issues, keep a trajectory ONLY if it ends in pytest-pass. Filter further for CORRECT, minimal edits (the content signal). No gold patches, no problem-statement fingerprints, no task-id conditioning (scorer-gaming; `Gemma\VULN_PUBLIC_TASK_PATCH_STAGING.md`). Few hundred clean, diverse rows, every row round-trip-validated through Gemma's own tool-call parser.
- **Template: never hand-serialize tool calls** (the v2 C3 bug). Build structured messages (arguments as a dict) and render via `apply_chat_template(..., tools=...)` so each argument is its own key:<|"|>value<|"|> pair; assert old_string AND new_string both survive the round trip; drop rows that fail.
- **Loss masking: assistant/tool-call tokens ONLY** (mask prompt + tool-result turns); assert the mask is nonzero and aligned to the edit payload boundary (where v2 broke).
- **Anti-overbake: 1 epoch**, not 4; a few hundred examples, not 23; cosine LR ~1e-4, ~3% warmup, packing off, trajectory held whole (never truncate the terminal edit); mix in replay/anchor rows of normal correct tool use so base ability isn't burned.
- **Keep it small** (KV-cache binds at 32k on 4xL4): one low-rank adapter.

## What the audit must settle (prior art, risk, feasibility)
- Confirm the fix-CONTENT framing against the KB (is WRONG-FIX really editing gold's symbols-and-files? cite rows).
- Prior art: every prior adapter (v2 edit-discipline, the localizer-LoRA plan) with per-task outcomes and WHY each failed (wrong skill / layer-0 / serialization / overbake). Tag this NEW vs VARIANT vs RE-RUN.
- Is "edit content correctness" actually LoRA-shaped, or is it capability (which the dossier warns LoRA struggles to add)? The dossier's R1 verdict (behavior vs capability) must be applied squarely — if content-correctness is capability-not-behavior, this is REVISE/REJECT and the honest lever is elsewhere.
- Feasibility: can the multi-layer adapter be trained on the bf16 twin and served on W4A16 (the proven path), and does the adapter-effect probe (running separately) confirm multi-layer adapters change output on the wheelhouse? If the probe has NOT confirmed effect, this proposal is NEEDS-DATA until it does.
- Scorer-parity caveat: the local scorer's whole-file fallback bar is stricter than the real harness on test_patch-edits-only tasks; note where that could make a local WIN pessimistic or a local tie misleading.

## Explicit NEEDS-DATA gate
This proposal is NEEDS-DATA until BOTH: (a) the adapter-effect probe confirms a multi-layer adapter visibly changes 31B output on the wheelhouse, and (b) the fixed scorer produces a trustworthy no-adapter baseline on the held-out rich set. Do not train before both.
