VERDICT: REJECT
# Final audit verdict — max-tool-calls-28-to-50 (2026-10-14)
- Pass 1 (AUDIT): REJECT — c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\audits\2026-10-14-max-tool-calls-28-to-50.md
- Pass 2 (REFUTE): REVISE — c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\audits\2026-10-14-max-tool-calls-28-to-50-refute.md
- Rule: final = stricter of the two (PROCEED < REVISE < NEEDS-DATA < REJECT); never softened.
## Mechanical disagreements
- pass1=REJECT pass2=REVISE; stricter=REJECT

## Narrative disagreements
- Prior-art framing (P1): pass 1 calls the proposal a RE-RUN of a measured regression (`2026-10-14-max-tool-calls-28-to-50.md` §2); pass 2 OVERTURNS this, finding no exact v6b 28→50 / eight-minute scalar run exists (`2026-10-14-max-tool-calls-28-to-50-refute.md` §2, §13 P1).
- Rules 15 / one-change (P2): pass 1 rules the build VIOLATES floor-guaranteed composition and one-change discipline (`2026-10-14-max-tool-calls-28-to-50.md` §8); pass 2 OVERTURNS, arguing a non-live v6b-vs-v6b free-gate ablation neither overwrites nor composes onto live-best (`2026-10-14-max-tool-calls-28-to-50-refute.md` §8, §13 P2).
- Reject rationale on refused calls (P4): pass 1 treats the two malformed refused calls as sufficient to reject 50 (`2026-10-14-max-tool-calls-28-to-50.md` §10); pass 2 OVERTURNS, holding they only kill the one-call-short story, not all post-28 trajectories (`2026-10-14-max-tool-calls-28-to-50-refute.md` §13 P4).
- Timing / 8-minute fit (A7): pass 1 reads the duration/call distribution as showing 50 calls do not fit 480 s (`2026-10-14-max-tool-calls-28-to-50.md` §9, A7); pass 2 OVERTURNS, labelling that an extrapolation and noting both targets project under 480 s at observed averages (`2026-10-14-max-tool-calls-28-to-50-refute.md` §7, §13 A7).
- Only pro-budget datum (A3): pass 1 says the lone pro-budget result (v10 2/10) is retracted (`2026-10-14-max-tool-calls-28-to-50.md` §2, A3); pass 2 OVERTURNS, citing v5's isolated 15→22 recovery of rich_4077 as a second positive cap datum (`2026-10-14-max-tool-calls-28-to-50-refute.md` §2, §13 A3).
- Variance / replicate uniqueness (A10): pass 1 calls v10 vs _v10_kaggle_pull the only same-config replicate pair and infers a 5-task n=1 gate cannot resolve the effect (`2026-10-14-max-tool-calls-28-to-50.md` §7, A10); pass 2 OVERTURNS the uniqueness and the "cannot resolve" as inference, not measured fact (`2026-10-14-max-tool-calls-28-to-50-refute.md` §7, §13 A10).
- Final verdict level: pass 1 concludes REJECT on three independent grounds (`2026-10-14-max-tool-calls-28-to-50.md` §10); pass 2 concludes REVISE, holding the honest state is unknown and a paired free gate can settle it (`2026-10-14-max-tool-calls-28-to-50-refute.md` §10).
- Agreement for the record (A1, A4, A5, A8, A11, A12): both passes concur the call wall bound rich_4070 with ~250 s left, the refused edits were wrong/non-gold, rich_4070 is HARD, live-best is v6w @ 0.15, and gold-first INVALID blocks any replay verdict (`2026-10-14-max-tool-calls-28-to-50-refute.md` §13 A1/A4/A5/A8/A11/A12 vs `2026-10-14-max-tool-calls-28-to-50.md` §4, §8, §12).
