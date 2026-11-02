# Design review R4 — Gemma Auditor (`design.md` REVISION 4)

Follow-up to the third design review (`design-review.json`, findings D3-1..D3-14: 1 HIGH, 5 MEDIUM,
8 NIT, CHANGES_REQUESTED). This review verifies that REVISION 4 **actually encodes** each fix in the
design body, not merely acknowledges it in the §25 response table. Where a fix depended on a specific,
articulable data claim, I re-checked that claim read-only (I did not re-run the whole measurement suite
the design-fix pass already ran).

## Verdict

**APPROVED.** All 14 findings are resolved and the fixes are encoded in the sections they claim. No HIGH
or MEDIUM issue remains. One NIT is open (a snapshot-count disagreement that the design itself records as
an honest drift); it does not block.

## Method

- Read §25 (the per-finding resolution table) and then opened every section it cites to confirm the fix
  is in the normative text: §5, §6.1, §6.2, §6.3, §6.4, §7.1, §7.5 (§7/§9), §10.3, §12.3, §12.4, §12.8,
  §17 item 5, §19.1 (revision-4 test block), §19.2 (facts 23–29), §20 (A6, A23).
- Read-only re-checks on the specific premises the fixes stand on:
  - `Gemma\kb\curated\submissions.csv` and `Gemma\kb\curated\run_labels.json` exist and contain what the
    design assumes (D3-3's "resolved, not conflict" depends entirely on these being present inputs);
  - `Gemma\submit_t4096\` and `Gemma\submit_branch_final\` exist, hold `agent.yaml`+`eval_config.yaml`
    with **no** `kernel-metadata.json` / `notebook_src.py` (D3-4's `staged-submission` kind premise);
  - the two staged `thinking_budget` values (4096 / 1024).

## Per-finding verification

### D3-1 (was HIGH) — facts only from lexicon claims; LB/live-best never auto-checked → RESOLVED
Encoded, in depth:
- §12.3 **rule 5 "fact-line"**: any line/table row yielding ≥1 fact bound by attribution rules 1–3 is a
  claim regardless of lexicon; dedup against richer paragraph/heading claims so no double count.
- §12.4 **F5 made case-insensitive** (`LB|leaderboard|public( score)?|scored?`) **plus the `<v> @ 0.NN`
  idiom**; **F10 live_best** fact grouped so a later different version forms a contradiction pair
  (v6 L27/L163 ↔ v6w L8436).
- §12.4 **Type-C LB-history tables** (first header cell `date`, or any `score`/`LB`/`public`): per-row F5
  from the score cell bound to the single config-cell version; 0/≥2 tokens → free text; quoted
  `"beat...beat"`→v6 description hint. **TOTAL rows** yield per-version-column F1.
- §7.5 §7 forms the live-best section and surfaces the v6↔v6w pair; §19.1/§19.2 facts 23–24 pin
  content-anchored tests on L27, L529/L531, L7793, L7796, L8389/L8391/L8401/L8436.

The newest LB claims that the brief requires surfacing (the v6w live-best block overturning
READ-THIS-FIRST #4) are now auto-extracted and the contradiction is formed. HIGH is cleared.

### D3-2 (MED) — F1 turns bars / unit counts into resolve outcomes → RESOLVED
§12.4 "F1 bar / unit / keyed classifier" replaces the old keyword-anywhere test with the exact ordered
rule the finding asked for: (1) bar lookbehind within 12 chars → `field: bar`, never checked; (2) unit
word within 3 chars → not F1; (3) keyed only within 3 tokens of a resolve keyword or a trailing F2b
task-group. Worked examples match the finding (L816/L1029 → bar, L7829 → only 0/6, L3977 → no F1, L790 →
only 1/6, L27 → 2/6 + F2b). §19.2 fact 25 tests it, including "no manufactured CONTRADICTED once v4 0/6
is on disk."

### D3-3 (MED) — hard-coded `v6 @ 0.12` baseline, no conflict rule → RESOLVED
Baseline is now the curated pointer `curated\run_labels.json:baseline`, confirmed against the external
`curated\submissions.csv`; the builder never rewrites either (§12.4 external-source block, §12.8 baseline
diff, §7.5 §7 BASELINE banner, §17 item 5 policy rule). §17 states the steering file is read in full,
a conflicting log/LB claim is a reported finding never silently adopted, and a baseline-dependent PROCEED
is NEEDS-DATA while branch_final (57146757) is PENDING.
**Re-checked read-only:** both curated files exist. `submissions.csv` confirms v6w=0.15 (57098497
COMPLETE), v6=0.12 (56806249 COMPLETE), branch_final=57146757 PENDING; `run_labels.json:baseline` = v6w
@ 0.15 with `prior_baseline` v6 and `pending` branch_final. So D3-3's "resolved in favour of the log"
rests on real external data, consistent with accountability rules 1–2 (external judge, pre-registered).

### D3-4 (MED) — staged configs invisible to discovery → RESOLVED
§5 clarifies `submit-dir` **requires** `kernel-metadata.json`; new kind **`staged-submission`** added
before `non-run`. §6.3 parses it with field paths relative to the dir, label = dir name minus `submit_`,
prompt-twin join, zip-drift per member sha. §7.5/§12.8 list staged configs as lever columns without
outcomes. §19.2 fact 26 asserts t4096/branch_final.
**Re-checked read-only:** both dirs exist with exactly `agent.yaml`, `eval_config.yaml`,
`configs\sampling.yaml`, `prompts\system.md`, `submission.zip` and **no** `kernel-metadata.json` /
`notebook_src.py`; `thinking_budget` is 4096 (t4096) and 1024 (branch_final). Premise and acceptance
fact confirmed.

### D3-5 (MED) — dev-harness params in notebook code not captured → RESOLVED
§6.3 "Dev-harness AST pass": records constant kwargs of every `EventsCompactionConfig`/`ContextCacheConfig`
`Call` (and `*_config=` siblings) into `config.dev_harness` with a source line; non-constant → `dynamic`;
unknown class → `dev_harness_extra`; **comments never read** (submit_v15 comment says 5, constructor
passes 15 → AST gives 15). README `compaction_interval = 5` (L556) stored as `scorer_reference` with a
per-run `dev_harness_matches_scorer`. §12.8 makes the 15-vs-5 difference a `dev-harness` lever; §7.5 §9
adds the "Does the dev harness match the scorer?" row. §19.2 fact 27 tests compact5→5, submit_v15→15,
submit_v15_cpu→{}.

### D3-6 (MED) — tests pinned to absolute line numbers in an edited log → RESOLVED
§19.1 "Log fixtures, not the live log": unit tests read fixture copies under `KB\tests\fixtures\log\`
(made in T1, each recording its source line + log sha256). §19.2 "Content-anchored on the live log":
slow tests locate anchors via `find_line(prefix, occurrence)` and assert spans/offsets, never absolute
numbers; `build_verification.md`/`build_meta.json` record the log sha256 + line count at test time. §4
and T1 updated for the fixture dir.

### D3-7 (NIT) — snapshot drift / fact-19 should be 9 / L7305 cite → RESOLVED
§0/§2.1 restate one snapshot; §10.3 and §19.2 fact 19 set the "3 nudges and nothing after" count to **9**
(Outputs/v19_lora rich_3469 → CALL_CAP, not NUDGE_EXHAUSTED); §12.4/§19.2 fact 18 cite **L7305**; the
non-31B `m12` arm → `out_of_scope` (§6.3, fact 28). The design honestly records the `…-v6w` slug now
backs 11 dirs (not 10) and keeps "≥" tests. See the open NIT below for the one residual inconsistency.

### D3-8 (NIT) — 7.1 config example omits fields → RESOLVED
§7.1 example now includes `stop_sequences`, `sampling_extra`, `dev_harness` and
`dev_harness_matches_scorer`.

### D3-9 (NIT) — PASS_START does not accept the `Evaluating` form → RESOLVED
§6.1 `PASS_START` is now `^\[1/\d+\] (?:Evaluating )?\S+ \(`. §19.2 fact 29 tests that a multi-pass log in
that format keeps its passes separate.

### D3-10 (NIT) — text-form call quoted in prose becomes a duplicate edit → RESOLVED
§6.2 "Quoted-in-prose dedupe": `call:…{` matches inside backtick spans are skipped and identical
`(fn, args_raw)` within a trace are deduped (first kept, `quoted_repeat: n`), citing v2_gate_out2
rich_4070 step 6.

### D3-11 (NIT) — read-event definition vs table disagree on python output → RESOLVED
§6.2 drops "python prints" from the returned-range table and states python-script prints are not a
read-event source; definition and table now agree.

### D3-12 (NIT) — paragraphs >12 lines unspecified → RESOLVED
§12.3 "Paragraph chunking": a paragraph >12 lines is split at line boundaries into consecutive ≤12-line
chunks, each a candidate claim with `chunk: k/n`; heading blocks are not chunked.

### D3-13 (NIT) — A6 window rejects earliest runs → RESOLVED
§20 A6 lower bound is now **2026-09-01**, matching S13; cites the 2026-09-30 dates (L970/L1055/L1079).

### D3-14 (NIT) — A23 nudge-reset basis points the wrong way → RESOLVED
§20 A23, §6.2 nudges and §10.3 make the **any-structured-call reset primary** (README L351 literal
`turn_has_tool_call == True`), with the valid-call variant stored as `…_valid_call_reset`; both equal on
the 155-trace histogram today. §7.1 schema carries both fields.

## Verified assumptions (re-checked read-only this pass)
1. `Gemma\kb\curated\submissions.csv` exists and lists v6w=0.15 (57098497, COMPLETE), v6=0.12 (56806249,
   COMPLETE), branch_final=57146757 PENDING (no score), plus the `"beat...beat"` description and the
   `0.18 budget` config-label strings — exactly as §12.4/§2.18 state.
2. `Gemma\kb\curated\run_labels.json:baseline` = v6w @ 0.15, confirmed against submissions.csv, with
   `prior_baseline` v6 @ 0.12 and `pending` branch_final — as §12.8/§17 assume.
3. `Gemma\submit_t4096\` and `Gemma\submit_branch_final\` exist, each holding agent.yaml +
   eval_config.yaml + configs/sampling.yaml + prompts/system.md + submission.zip, with **no**
   kernel-metadata.json or notebook_src.py → correctly classified `staged-submission`, not `submit-dir`.
4. Staged `thinking_budget` = 4096 (t4096) / 1024 (branch_final) — matches D3-4 acceptance fact 26.

## Unverified / wrong assumptions
None found to be wrong. I did not independently re-verify every §2 measurement (e.g. the full 155-trace
nudge histogram, the per-line claim-extraction probe counts, or the compaction AST reads of every
notebook); the brief scoped this pass to confirming the fixes are encoded and to re-checking only where a
specific doubt remained. Those parser facts are pinned by the §19 acceptance tests and will be exercised
at build time; a miss there is reported, not reframed (accountability rule 2).

## Open findings

### R4-1 (NIT, non-blocking) — v6w-slug dir count disagrees between the design and run_labels.json
`design.md` (§0, §2.1, §2.18, §25/D4-b) states the `…-v6w` slug now backs **11** local dirs, while
`curated\run_labels.json:baseline.config_source_hint` still says "slug family ...-v6w (backs ~10 dirs)".
Both are explicitly snapshots and the acceptance tests assert "≥", so neither drives a hard check, and the
design records the drift honestly rather than forcing a number. This is cosmetic and does not block.
Fix (optional, at next curated-file touch): update the `config_source_hint` note to "~11 dirs" or drop the
count, so the design and the curated hint read the same. No code or acceptance-test change is required.
