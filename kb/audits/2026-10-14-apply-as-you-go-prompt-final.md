VERDICT: REJECT
# Final audit verdict — apply-as-you-go-prompt (2026-10-14)
- Pass 1 (AUDIT): REJECT — c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\audits\2026-10-14-apply-as-you-go-prompt.md
- Pass 2 (REFUTE): REJECT — c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\audits\2026-10-14-apply-as-you-go-prompt-refute.md
- Rule: final = stricter of the two (PROCEED < REVISE < NEEDS-DATA < REJECT); never softened.
## Mechanical disagreements
- pass1=REJECT pass2=REJECT; stricter=REJECT

## Narrative disagreements
- Verdict agrees (REJECT), but the two passes diverge on four substantive claims; the refute pass explicitly instructs that pass-1 claims A8, A10, A12, A13 "should not be carried forward as written" (refute §13 / `2026-10-14-apply-as-you-go-prompt-refute.md`).
- APPLIED count: audit §4c says `APPLIED` reached in 6 runs across six configs; refute §7 recounts 7 APPLIED rows (v18, v19, v19v3, _v6out, hard, v2_gate_out, v2_gate_s05c) and overturns A13 on exact counts (`2026-10-14-apply-as-you-go-prompt.md` §4c vs `2026-10-14-apply-as-you-go-prompt-refute.md` §7/A13).
- WROTE_GOLD_CHANGE count: audit §4c states 8 of 11 traced runs; refute §7 states 10 rows if two text-only heuristic hits are included, or 8 argument-bearing hits if excluded — pass 1 omitted that qualifier (`2026-10-14-apply-as-you-go-prompt.md` §4c vs `2026-10-14-apply-as-you-go-prompt-refute.md` §7).
- rich_4070 difficulty label: audit §3 argues the HARD label is an artefact of gold-patch sprawl that the small test_patch contradicts; refute OVERTURNS A12, holding HARD is a defined mechanical gold-patch class (9 files/33 hunks) not contradicted by test-patch size (`2026-10-14-apply-as-you-go-prompt.md` §3 vs `2026-10-14-apply-as-you-go-prompt-refute.md` §13/A12).
- Hard-arm partial as a Pass-to-Pass regression: audit §4b/A8 asserts the banked patch is strictly worse than submitting nothing; refute marks A8 UNVERIFIABLE because `gold_first=INVALID` precludes a valid replay verdict — runtime regression is only strongly inferred (`2026-10-14-apply-as-you-go-prompt.md` §4b vs `2026-10-14-apply-as-you-go-prompt-refute.md` §13/A8).
- Fail-to-Pass identity: audit §3/§10 treats `test_input_password` / the getpass-only two-hunk subset as the decisive F2P; refute marks A9 "narrow" and A10 UNVERIFIABLE — the +1 aggregate and gold_pass_tests do not identify which test flipped (`2026-10-14-apply-as-you-go-prompt.md` §3 vs `2026-10-14-apply-as-you-go-prompt-refute.md` §13/A9-A10).
- Hard-arm failure subclass: audit §5 records `stopped_by = ARG_REJECTED`; refute §5 overturns the pass-1 AUDIT-JSON subclass, holding the row is `WRONG-FIX / UNREPLAYED` and ARG_REJECTED is only the stopping mechanism, not the subclass (`2026-10-14-apply-as-you-go-prompt.md` §5 vs `2026-10-14-apply-as-you-go-prompt-refute.md` §5/A18).
- Prompt-contradiction grounds: refute §8 adds a ground pass 1 did not raise — the new sentence contradicts v6b's existing "smallest fix / submit immediately" instruction — as part of its rejection (`2026-10-14-apply-as-you-go-prompt-refute.md` §8).
- Both passes agree on the decisive, un-disputed grounds: the exact instruction already ships verbatim at lines 22-23 of the live-best v6w @ 0.15 prompt (A1, UPHELD), v6b is a lower-floor regression (A14, UPHELD), and early banking has repeatedly failed to resolve the target (A3, UPHELD) (`2026-10-14-apply-as-you-go-prompt.md` §10 and `2026-10-14-apply-as-you-go-prompt-refute.md` §13).
