VERDICT: REVISE
# Final audit verdict — rich-near-miss-forensic (2026-10-14)
- Pass 1 (AUDIT): REVISE — c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\audits\2026-10-14-rich-near-miss-forensic.md
- Pass 2 (REFUTE): REVISE — c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\audits\2026-10-14-rich-near-miss-forensic-refute.md
- Rule: final = stricter of the two (PROCEED < REVISE < NEEDS-DATA < REJECT); never softened.
## Mechanical disagreements
- pass1=REVISE pass2=REVISE; stricter=REVISE

## Narrative disagreements
- Target outcome counts: refute recounts rich_4076 0/32, rich_4077 26/32, rich_4079 6/32, rich_3469 0/18, rich_3471 3/11 and explicitly OVERTURNS pass 1's 0/26, 24/32, 6/31, 0/15, 4/11 as stale/wrong despite the same KB fingerprint (`2026-10-14-rich-near-miss-forensic-refute.md` §6/§11/claim A7 vs `2026-10-14-rich-near-miss-forensic.md` §4).
- Gold symbol for rich_4079: refute names it `TableDataElement.on_text` and OVERTURNS pass 1's `TextElement.on_text` in exact form (`2026-10-14-rich-near-miss-forensic-refute.md` §3/claim A12 vs `2026-10-14-rich-near-miss-forensic.md` §3/§4).
- Prior-exposure claim: refute finds rich_3067, rich_3472, rich_3894 had local exposure and OVERTURNS pass 1's "no prior Kaggle or local exposure" for the fresh gate tasks (`2026-10-14-rich-near-miss-forensic-refute.md` §8/claim R14 vs `2026-10-14-rich-near-miss-forensic.md` §10 proposed task set).
- Proposed gate shape: refute rejects pass 1's six-task one-arm gate as non-protocol (standing five-task rule) and not floor-guaranteed, requiring a paired baseline/change gate instead (`2026-10-14-rich-near-miss-forensic-refute.md` §8/§10/claim R15 vs `2026-10-14-rich-near-miss-forensic.md` §10).
- Mechanism bar validity: refute argues a zero-malformed-key bar can pass vacuously without a ranged-read-opportunity denominator; pass 1 pre-registers the absolute "0 malformed keys" bar without that conditioning (`2026-10-14-rich-near-miss-forensic-refute.md` §8/§9 vs `2026-10-14-rich-near-miss-forensic.md` §10 bar).
- Malformed-key row count for rich_4076: refute recounts 6 rows/10 calls and OVERTURNS pass 1's "7 malformed-key rows" (`2026-10-14-rich-near-miss-forensic-refute.md` §6/claim R13 vs `2026-10-14-rich-near-miss-forensic.md` §9).
- v6b rich_4079/rich_4070 characterization: refute stresses "no edit" vs "no successful edit" — refused structured calls were edit-bearing attempts, not absence of attempts (`2026-10-14-rich-near-miss-forensic-refute.md` §1/§5/§11 vs `2026-10-14-rich-near-miss-forensic.md` §4 lead 1).
- Variance framing: refute flags "coin flip" as descriptive, not a measured same-config probability (no same-config replicates), tempering pass 1's variance read (`2026-10-14-rich-near-miss-forensic-refute.md` §7 vs `2026-10-14-rich-near-miss-forensic.md` §7).
- Newer submission statuses: refute holds ref 57201051 and 57146757 as UNVERIFIABLE/PENDING against curated submissions, where pass 1 cites the log's receipt of 57201051 as a spent-slot fact (`2026-10-14-rich-near-miss-forensic-refute.md` §8/claim A10 vs `2026-10-14-rich-near-miss-forensic.md` §8/§10).
- The refuted candidate's test outcome: refute marks "would not have passed" UNVERIFIABLE (no valid gold-first replay), where pass 1 states it as an INFERRED static-diff conclusion (`2026-10-14-rich-near-miss-forensic-refute.md` claim A11 vs `2026-10-14-rich-near-miss-forensic.md` §4 lead 1).
