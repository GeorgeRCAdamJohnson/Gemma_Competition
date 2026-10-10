# Paper Finding #1 — two framings, pending the 1-epoch ablation

> Drafted BEFORE the deciding experiment (1-epoch r8 retrain) returns, deliberately, as a guard against
> motivated reasoning. When the 1-epoch held-out result lands, exactly ONE of these two framings becomes
> the paper claim; the other is deleted. The experiment, not the prose, decides. (rules 1, 2, 9, 12)
>
> Why two framings are needed: every degradation measurement so far was on a 4-EPOCH adapter
> (r16/alpha32 original; r8/alpha16 this session — still 4 epochs). theprint's 11 working 2B subdomain
> experts were trained at 1 EPOCH. So "degradation" may be an over-TRAINING artifact, not an intrinsic
> property of agentic SFT. The 1-epoch retrain is the fork.

---

## Shared, framing-independent facts (true under either outcome — these are banked)

These go in the paper regardless of how the 1-epoch test resolves:

1. **Consumer-hardware pipeline.** A full train+eval loop for a Gemma-4 LoRA (up to 12B, 4-bit QLoRA)
   runs on a single 16GB consumer GPU (RTX 5070 Ti, Blackwell sm_120). Resumable checkpointing;
   one-arm-per-process eval; GGUF + llama-server serving at ~64 tok/s (~11x the HF+bitsandbytes path).
   The "needs 80GB" assumption is false for this regime.
2. **The redundancy boundary.** The sibling/neighbor repair method (Plastic Surgery Hypothesis) works
   where the repo is high-redundancy (rich: prompt-saturable) and fails where it is low-redundancy
   (fastapi). This predicts WHICH repos a small specialist can help.
3. **The evaluation caveat.** Scoring a fine-tuned small SWE agent ONLY on end-to-end resolution rate
   can hide a knowledge gain behind an agent-protocol regression. You must separate "fix knowledge"
   (did it emit a correct edit) from "loop completion" (did it stay in the tool-call protocol) to see
   the effect. Our secondary metrics (produced / reached_submit / degen-arg-count) expose it.
4. **The dose-response.** Argument-collapse is monotonic in adapter scale: degen≈0 at serve-scale ≤0.5,
   emerges at 0.75, severe at 1.0 (measured on two fastapi tasks, r16 adapter). So any degradation is at
   minimum SCALE-dependent and removable by lowering serve-strength — it is not an unavoidable property
   of applying the adapter at all.
5. **The fix-knowledge is real.** fastapi_15588 @ serve-scale 0.25: the specialist produced an applying
   patch where the identical base (adapter off) produced nothing, with zero argument-collapse. The
   adapter carries a capability the base lacks; the open question is only whether we can deliver it
   without breaking the loop.

---

## FRAMING A — "capacity-independent degradation" (current headline; SURVIVES only if 1-epoch ALSO degrades)

**Claim.** Naive subdomain SFT for bug-fix knowledge degrades a Gemma-4 agent's tool-call competence in a
model-capacity-independent way: the degradation reproduces at both 2B (E2B) and 12B, via two linked
mechanisms — (i) at 2B, narration/prose turns that emit no parseable tool call and trip early-stop;
(ii) at 12B, tool-call ARGUMENT COLLAPSE under greedy decode (every argument drifts to the literal `1`),
dose-dependent on adapter strength. Teaching WHAT to fix without protecting HOW to stay in the loop is
net-negative on end-to-end resolution.

**What must be true for this framing to hold:** the 1-epoch retrain ALSO shows degen>0 at usable scale
AND produced ≤ base. i.e. reducing epochs 4→1 does NOT rescue it, proving the degradation is intrinsic to
the SFT target/method, not an over-training artifact.

**Evidence block (drop the 1-epoch numbers in here):**
- E2B 4-epoch: base produced 2/6, specialist 0/6 (narration mechanism, raw gens).
- 12B 4-epoch r16: specialist produced 0/6 vs base 1/6; argument-collapse (degen 9/3 at scale 1.0).
- 12B 4-epoch r8: [current sweep result — fill in].
- **12B 1-epoch r8: [PENDING — if this is ALSO degraded, Framing A stands].**

**Risk if we ship this and it's wrong:** a reviewer (or theprint's own 1-epoch cards) points out every
measurement was at 4 epochs → the "intrinsic/capacity-independent" claim is undercut as an over-training
confound. This is why we do NOT ship Framing A until the 1-epoch test confirms degradation persists.

---

## FRAMING B — "degradation UNLESS 1-epoch" (the stronger, more defensible claim; HOLDS if 1-epoch recovers)

**Claim.** Subdomain SFT for bug-fix knowledge degrades a Gemma-4 agent's tool-call competence ONLY when
over-trained. At 4 epochs (loss driven to ~0.3 on ~32 examples), the adapter over-peaks the output
distribution and, under greedy decode on out-of-distribution inputs, collapses tool-call arguments to a
degenerate repetition (all args → `1`) — removable by lowering serve-scale, and a dose-dependent
over-strength artifact. At 1 epoch, the adapter PRESERVES tool-call protocol AND adds fix-knowledge,
yielding net improvement. The actionable rule: for small agentic specialists, UNDER-train (1 epoch,
moderate alpha/r) and serve at reduced scale; the fix-knowledge survives, the protocol does not break.

**What must be true for this framing to hold:** the 1-epoch retrain shows degen≈0 at a usable scale AND
produced ≥ base on held-out. i.e. 4→1 epochs rescues both protocol and knowledge.

**Why this is the STRONGER paper:**
- It converts a pure negative result ("SFT breaks agents") into a positive, actionable recipe ("1-epoch
  SFT is the sweet spot where specialists work").
- It is corroborated by external prior art: theprint's 11 shipped 2B subdomain experts are all 1-epoch.
  Our contribution becomes the AGENTIC-specific boundary those chat-only experts never had to cross —
  we show the 1-epoch rule is what preserves tool-call protocol, which single-turn chat eval cannot
  expose.
- It gives the competition exactly what its thesis asks: a capable agent specialist on consumer hardware,
  with a reproducible training recipe.

**Evidence block (drop the 1-epoch numbers in here):**
- Dose-response + fix-knowledge-is-real facts (shared block above) set up that the capability exists.
- **12B 1-epoch r8: [PENDING — if degen≈0 and produced ≥ base, Framing B is the paper].**

**Honest boundary even if B holds:** demonstrated on one base family (Gemma-4), one repo's data
(fastapi), thin data (~32-35 examples), small held-out n. The RECIPE claim (1 epoch) is supported by our
measurement + theprint's existence proof; the GENERALITY claim stays scoped.

---

## Decision procedure when the number lands (no post-hoc wiggle room)

| 1-epoch r8 held-out result            | Verdict         | Paper framing |
|---------------------------------------|-----------------|---------------|
| degen≈0 AND produced ≥ base           | over-training was the cause | **Framing B** (ship) |
| degen>0 at every usable scale         | intrinsic degradation       | **Framing A** (ship) |
| degen≈0 but produced < base           | protocol fixed, knowledge didn't transfer to rich | NEITHER as-is → report as honest null, investigate domain transfer (fastapi-trained vs rich-eval) |

The third row matters: our 1-epoch test evaluates a FASTAPI-trained adapter on RICH held-out tasks. If
produced doesn't beat base there, it may be a cross-domain-transfer null, NOT a verdict on epochs. In that
case re-run the 1-epoch test on fastapi held-out before concluding.
