VERDICT: NEEDS-DATA
# Final audit verdict — content-correctness-lora (2026-10-15)
- Pass 1 (AUDIT): NEEDS-DATA — c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\audits\2026-10-15-content-correctness-lora.md
- Pass 2 (REFUTE): NEEDS-DATA — c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\audits\2026-10-15-content-correctness-lora-refute.md
- Rule: final = stricter of the two (PROCEED < REVISE < NEEDS-DATA < REJECT); never softened.
## Mechanical disagreements
- pass1=NEEDS-DATA pass2=NEEDS-DATA; stricter=NEEDS-DATA

## Narrative disagreements
- Both verdicts are NEEDS-DATA, but they split on how much of the audit's own reasoning survives: the AUDIT pass (`2026-10-15-content-correctness-lora.md` §10) treats its blocking rationales as settled, while the REFUTE pass (`2026-10-15-content-correctness-lora-refute.md` §10) explicitly narrows or overturns three of them.
- A3 — multi-layer causation: AUDIT (`...lora.md` §9/§2) frames `v2_gate_out` vs `v2_gate_out2` as a natural A/B establishing that a multi-layer adapter has a large effect; REFUTE (`...lora-refute.md` §13 A3, §9) OVERTURNS this, holding the comparison isolates the *adapter artifact* only, not span vs rank/alpha/modules/weights, so the controlled probe is NOT redundant.
- A10 — correctness signal: AUDIT (`...lora.md` §9 item 5, §10) argues self-distilled passing trajectories cannot carry the discriminative content-correctness signal "by construction"; REFUTE (`...lora-refute.md` §13 A10, §10) OVERTURNS this as false — passing edits do contain correct-content supervision, and transfer is unknown rather than impossible.
- A16 — variance model: AUDIT (`...lora.md` §7) models rich_4079 as a p≈0.19 exchangeable coin to argue a single-run bar is dominated by noise; REFUTE (`...lora-refute.md` §13 A16, §7) OVERTURNS this, holding the 6 resolves came from materially different prompts/budgets/tool surfaces and are not exchangeable Bernoulli replicates.
- A17 — r16/alpha32 prior art: AUDIT (`...lora.md` §2) tags low-rank α=2r as a "RE-RUN of a measured-negative scaling"; REFUTE (`...lora-refute.md` §13 A17, §2) OVERTURNS this, since prior negative arms bundled rank, module span, data and path changes, so the alpha/r ratio was never isolated.
- A14 — leakcheck: AUDIT (`...lora.md` §6/§8) reports `leakcheck --scope config` exits 1 on rich_4079/rich_3535 as a blocking rules FAIL; REFUTE (`...lora-refute.md` §13 A14, §6) OVERTURNS the blocker framing, noting the proposal is a diagnosis document, not deployable prompt/config, while agreeing the eventual artifact must pass independently.
- Resolved-task count: AUDIT (`...lora.md` §5) states 7 distinct rich tasks ever resolved; REFUTE (`...lora-refute.md` §6, §13 A9) counts six trace-backed resolves plus rich_3718 as an untraced summary-only row — agreement on the facts, disagreement on what counts as a verified resolve.
- Cheapest next data: AUDIT (`...lora.md` §10) prioritizes a strength/span calibration gate plus extending rp-4 gold coverage; REFUTE (`...lora-refute.md` §9) adds recovering the distinct kernel output for scored submission 57201051 (the temp-1.0/top_k-64 0.13 run) as the first decisive missing datum, which AUDIT does not foreground.
- Shared, undisputed blockers (both reports): no trained candidate adapter, no named exact held-out task list, only four rp-4 gold-valid rich tasks, no local 31B agent arm, and `train_lora.py` maxlen still defaults to 768 (`...lora.md` §6/§10; `...lora-refute.md` §8/§11).
