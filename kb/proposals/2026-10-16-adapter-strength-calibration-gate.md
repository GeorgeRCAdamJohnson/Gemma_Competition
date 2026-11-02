# Proposal: adapter strength/span calibration — FREE rich gate (2026-10-16)

Type: free-gate experiment (NO training, NO scored slot). Status: UNAUDITED.
Origin: the "exactly what to collect" item #1 of the content-correctness LoRA audit
(`Gemma\kb\audits\2026-10-15-content-correctness-lora.md` §10). The user has approved spending a FREE gate.

## Why (the gap this closes)
The adapter path has one un-measured knob that blocks every future LoRA decision: **at what strength/span does a
multi-layer adapter stay ACTIVE without OVERBAKING the agent into paralysis?** The on-disk A/B is bimodal with
nothing in between (all MEASURED, cited in the content-LoRA audit §2/§4/§9):
- `v2_gate_out` served the competition SAMPLE layer-0 stub (r4/alpha8, layers_to_transform:[0], q_proj/o_proj;
  weights 217,672 B) -> behaved baseline-like: edits on 5/5, rich_4077 RESOLVED.
- `v2_gate_out2` served a 410-module multi-layer adapter (r32/alpha64, 979,558,760 B) on the SAME scored stack
  -> **tool_calls=0, patch_chars=0, NUDGE_EXHAUSTED on 5/5** (over-strong; the agent never acts).
- `v2_gate_s05c` served the same weights with alpha rewritten to 16 (serve-scale 0.5) -> partial: some tasks
  read the gold file, rich_4070 attempted edits (13/22 malformed), rich_4077 RESOLVED. So lowering effective
  strength moved it from "paralyzed" toward "acting."

We have NEVER swept strength deliberately to locate the usable band. Without it, any trained content LoRA is
shipped blind to whether its strength paralyzes the agent (the exact v2 failure). This gate measures the knob,
not a trained skill.

## The change (one lever: adapter STRENGTH, nothing trained)
Serve a KNOWN-SHAPE, already-on-disk multi-layer adapter at >=2 effective strengths alongside the no-adapter
v6w arm, on a FREE 5-task rich gate, and measure whether the agent still ACTS (edit-attempt rate, patch_chars,
malformation share, resolves) vs paralyzes. Use `make_variant.py` to rewrite `lora_alpha` (serve-scale) on an
EXISTING adapter artifact — NO training, NO new weights, NO gold/fingerprints in the config.

Candidate known-shape artifact (pick one, state which): the 110-module r32 adapter in
`submit_v6z_on_v6w\lora025` (175 MB) OR the 410-module artifact in `v2_gate_out2` (979 MB) — the 110-module one
is preferred (smaller, closer to a plausible real adapter span). Whatever is chosen, its weights are FIXED; only
`lora_alpha` (serve-scale) varies across arms.

Arms (single flat agent, no sub-agents — curated J-subagents-regress):
- ARM 0 (control): no adapter, byte-identical v6w (28/8/80/240, 9-tool, thinking 1024).
- ARM 1: the known adapter at a LOW serve-scale (e.g. effective alpha/r ~= 0.25).
- ARM 2: the same adapter at a MID serve-scale (e.g. alpha/r ~= 0.5, the v2_gate_s05c point that partially acted).
(Keep to 2 adapter strengths + control to fit one 5-task gate. If the gate harness allows >3 model ids cheaply,
add a third strength; otherwise 3 arms total.)

## Pre-registered task set (rich only; EASY+HARD; each with difficulty class)
Reuse a rich-only 5-task gate. Pre-register the exact ids and classes from `Gemma\RICH_48_DIFFICULTY_MAP.md`
before pushing. Include the always-solve rich_4077 (EASY) as a CONTROL — if an adapter arm loses rich_4077 that
baseline v6w solves, that arm is over-strong by definition. Suggested set (finalize against the gate harness):
rich_4077 (EASY, control), rich_4079 (EASY), rich_3469 (EASY), rich_3675 (HARD), rich_3934 (HARD). State the set
explicitly; do not change it after seeing results.

## Pre-registered bar (this is a CALIBRATION, not a resolve-chase)
The question is NOT "does an adapter resolve more" (no trained skill here). It is "which serve-strength keeps the
agent ACTING like the no-adapter arm." Per arm, per task, record: resolved, tool_calls, first_edit_at, n_edit,
edit_fail, patch_chars, malformation share, end_reason.
- An adapter strength s is **ADMISSIBLE** iff on >=4/5 tasks its edit-attempt rate AND patch_chars are NOT below
  ARM 0 (no-adapter), AND it does not lose rich_4077. (I.e. the adapter is active but not paralyzing.)
- An adapter strength s is **OVER-STRONG** (the v2 failure) iff it drops tool_calls / patch_chars / edit-attempts
  materially below ARM 0 on >=2 tasks, or loses rich_4077.
- OUTCOME = the admissible strength band (possibly empty). An EMPTY band is a valid, valuable NULL: it would say
  "even a benign random/known adapter at usable strength paralyzes this agent's loop," which would REVISE the
  whole content-LoRA plan before any training. A non-empty band hands the content-LoRA recipe a serve-strength
  prior and the overbake guard it currently lacks.
Resolves are a secondary read only (the adapter is not trained to resolve; any resolve delta is noise unless large).

## Hard constraints / integrity
- FREE gate only; the scored slot is NOT used. v6w @ 0.15 remains live-best and is ARM 0 itself.
- NO training, NO new weights — only `make_variant.py` serve-scale rewrites of an EXISTING adapter.
- The adapter weights are a KNOWN artifact (random-ish / prior-trained), carrying NO gold patches and NO
  problem-statement fingerprints. `leakcheck --scope config` must pass on the gate config (no bare task ids in
  any prompt/config text — the prior proposal failed this on rich_4079/rich_3535; keep task ids out of config).
- One change per arm vs ARM 0: ONLY `lora_alpha`/adapter-attached differs; prompt, tools, budget, sampling identical.
- Single flat agent, no sub-agents.

## What the audit must settle before this is pushed
- Is this NEW vs a RE-RUN of v2_gate_s05c? (s05c already ran ONE serve-scale; this adds the control arm + a second
  strength + a pre-registered admissibility bar. State the delta honestly; if it is just s05c again, say so.)
- Does the free-gate harness actually serve multiple adapter strengths as distinct model ids in one run, or does
  each arm need its own gate push? (Determines whether this is 1 gate or N.)
- Which known artifact to serve (110-module vs 410-module), and the exact serve-scales, so "strength" is
  one-variable and comparable to the s05c datum.
- Is the admissibility bar measurable from the kernel log + ATTRIBUTION table the gate already emits (tool_calls,
  n_edit, edit_fail, first_edit_at, patch_chars)? If first_edit_at / malformation share are not in the gate
  output, say how they are obtained (trace parse) or drop them from the bar.
