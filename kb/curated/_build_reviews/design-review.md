# Design review: Gemma auditor (design revision 3)

**Reviewed:** `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\.kiro\specs\gemma-auditor\design.md`, Revision 3 (280,455 bytes, mtime 2026-10-13 18:58).

**Checked against:**
- the user brief and the workflow's design prompt in `C:\Users\Biges\.kiro\sessions\857524a8a80cd052\workflows\wf_9b642c39833fc067\workflow-definition.json`;
- the previous review (revision 2), which this file and its JSON replace;
- the raw data on disk, re-measured on 2026-10-13 between 19:00 and 22:00 local time.

**Verdict: CHANGES_REQUESTED.** There is 1 HIGH finding, 5 MEDIUM and 8 NIT.

**How the review was done.**
- I read the design in full.
- The probes were read-only Python scripts under `%TEMP%\gkb_rev3_review_probe\`, deleted afterwards.
- No git command was run. Nothing was built and no replay was run.
- Nothing under `Gemma\` was modified except the two files in this directory.

**Summary.**

Revision 3 resolves the second review's 26 findings. Its new parser facts hold on today's larger data set (155 traces, 29 run dirs, 30 JSON kernel logs, 8,555 log lines):
- the cm-2 count model has residual 0 on 155 of 155 traces;
- all 140 ARG_REJECTED calls are `edit_file` calls missing `old_string`;
- the log's heading blocks, correction lines and anchors are as stated;
- the S14 swallowed-argument shapes match exactly;
- `send_message` reaches custom agents in workflow steps.

The remaining problems:
1. **Claim extraction (D3-1, D3-2).** Claims are still created only from lexicon matches, so most version-bound resolve counts and LB scores never become facts. That includes the log's newest and most consequential claim: v6w scored 0.15, and "v6 @ 0.12 is no longer sacred". F1 also manufactures contradictions out of pre-registered bars.
2. **Config evidence (D3-3, D3-4, D3-5).** Three kinds are invisible:
   - the live-best baseline is a constant (D3-3);
   - the staged scored-submission dirs are never parsed (D3-4);
   - dev-harness settings in notebook code are not captured. `compaction_interval` is the only lever of the newest arm (D3-5).
3. **Test anchoring (D3-6).** The slow acceptance facts are pinned to absolute line numbers. The standing-truth block above them is now contradicted by a later entry, so it is likely to be edited in place, which would shift every pinned line.

Each finding gives the evidence, then a concrete fix. Measurements are labelled MEASURED.

---

## Findings

### HIGH

**D3-1. [HIGH] Facts come only from lexicon-matching claims, so most version-bound resolve counts and LB scores are never auto-checked, including the newest LB claim.**

*Where:*
- §12.3: claim units, rules 1–4.
- §12.4: facts are extracted from claims only; the F5 pattern; the type-B rule that a row's first cell must hold a task id.
- §7.5, section 7.
- §19.1 and §19.2: the armB F1v test.

*Problem.* §12.4 extracts facts only from claims. §12.3 creates claims from only three sources:
- READ-THIS-FIRST items;
- recognised table rows;
- paragraphs or heading blocks that match `VERDICT_RX` or `CORRECTION_RX`.

LB entries are worded "SCORED", "SCORE", "LEADERBOARD" or "LIVE-BEST", and per-version totals sit in plain prose, so they fall outside every rule. MEASURED with a read-only probe that mirrors rules 1–4 (approximate: a paragraph is a run of consecutive non-blank, non-table lines, and the 12-line cap is ignored):

| fact type (the line also carries a version token or alias) | lines | lines no claim rule reaches |
|---|---|---|
| F1: N/M plus a resolve keyword | 53 | 31 |
| F5: LB keyword plus `0.xx` (3 more lines match only case-insensitively) | 25 (+3) | 16 (+2) |
| F1v: `<version> = N/M` | 9 | 3 |

Concrete misses:
- **The newest LB claim produces no fact at all.** It spans:
  - L8389: `## ### v6w SCORED **0.15** ? NEW LIVE-BEST …`;
  - L8391: `Submission 57098497 (scored 2026-10-13). **Beats v6 @ 0.12 …**`;
  - the LB-history table at L8393–8401, which starts with `| date | config | score |` and ends with `| **10-12** | **v6w: 0.18 budget 28/8/80/240 …** | **0.15** <- **LIVE-BEST** |`;
  - L8436: `v6w @ 0.15 is now the live-best and the bar for anything that follows. v6 @ 0.12 is no longer sacred.`

  None of these lines holds a lexicon word, and the table's first header cell is `date`, so it is neither type A nor type B. The entry overturns READ-THIS-FIRST #4 (L27, "LIVE-BEST = v6 @ 0.12 (SACRED) … Never beaten"). That is exactly the kind of contradiction between log entries the brief requires listing.
- **The first LB anchor produces no fact either:** L529 `## SUBMISSION v2 — LEADERBOARD SCORE: 0.10 (first real anchor, external judge)` and L531 `v2 scored **0.10** on the actual competition leaderboard.` The design also never says F5 is case-insensitive, so `LEADERBOARD SCORE` and `SCORED` would be missed even inside a claim.
- **The design's own F1v example fails on the real log.** L7796, `**armB = 3/6, same as armC, below v6w's 4/6.**`, is the example in §12.4 and §19.1. It is a standalone paragraph with no lexicon word, so it never becomes a claim. The §19.1 test can only pass on a synthetic snippet.
- **Per-version totals in type-B tables are dropped.** L7793 `| **TOTAL** | **4/6** | 2/6 | 2/6 | 3/6 | **3/6** |` is skipped because the row's first cell is not a task id.
- **A diagnosis heading is skipped:** L790 `## DIAGNOSIS: v3 patches 3/6 but resolves 1/6 …` has no lexicon word.

Consequences:
- The "log-claimed LB values" column in KB_SUMMARY section 7 lacks both the first and the newest LB claim.
- Contradictions about the live-best and about per-version totals are never formed.
- The brief's "auto-checks … resolved counts … LB scores" is met only for the version-history table and lexicon paragraphs.

*Fix.*
1. **Add §12.3 rule 5, fact lines.** Outside code fences, every line or table row that yields at least one F1, F1v, F2b, F5 or F10 fact is a claim (`kind: fact-line`), whatever the lexicon says. The fact's version must bind through attribution rules 1–3: a token or alias on the same line or row, or the row's version column. The unit-level fallback does not count. The claim id uses the same formula.
2. **Widen F5.** Make it case-insensitive, with the keywords `LB|leaderboard|public(?: score)?|scored?`. Add the log's own idiom `(<version>)\s*@\s*(0\.\d{2,3})\b` (L27 `v6 @ 0.12`, L8391, L8436).
3. **Add type-C tables (LB history).**
   - Detection: the first header cell is `date`, or any header cell is `score`, `LB` or `public`.
   - Each row binds to the single version token or alias in its `config`, `version` or `description` cell. Zero or two-plus tokens make the row free text.
   - The score cell yields F5.
   - The row's quoted description (e.g. `"beat...beat"`) is also emitted as a description-to-version mapping hint for KB_SUMMARY section 7. Submission descriptions carry no version tags (`"One shot"`), so the date-only mapping is weak without this.
4. **Read TOTAL rows in type-B tables.** A row whose first cell is `TOTAL`, `total` or `sum` yields one F1 fact per version column, from `(\d+)/(\d+)`.
5. **Add fact F10, `live_best`.** It matches `(?i)live[- ]best\s*(?:=|:|is)\s*`, `(?i)new live[- ]best` or `(?i)is now the live[- ]best`, and binds to the nearest version token. F10 facts are grouped together, so a later unit naming a different version forms a contradiction pair with L27 and L163.
6. **Test on the real log,** with lines located by content (D3-6):
   - L529, L531, L7793, L7796, L8389, L8391, L8401 and L8436;
   - L27, which must yield F5 v6 0.12 through the `@` idiom, and F10 v6.

### MEDIUM

**D3-2. [MEDIUM] F1 turns bars and non-resolve counts into resolve outcomes, which manufactures CONTRADICTED statuses. It also misses the READ-THIS-FIRST #4 count.**

*Where:* §12.4 F1 (the keyword may be anywhere on the line; the only exclusions are quad chains, N > M, M > 200 and M = 0), F2b, and the example in §12.7.

*Problem* (MEASURED):
- **Bars become outcomes.** 37 N/M values on lines with a resolve keyword are pre-registered bars or comparisons:
  - L816 `Bar for v4: >=2/6`;
  - L1029 `Hard bar: **>=2/6 resolved**`;
  - L677 `resolve >=1/6`;
  - L1183 `<1/6 = regression`.

  F1 reads the first as "v4 resolved 2/6". Once T12 pulls v4's output (0/6), that becomes CONTRADICTED. This is a manufactured contradiction, the failure the accountability rules forbid.
- **Other counts become outcomes.** 4 N/M values are followed by a non-resolve unit:
  - L7829 `**0/6 resolved but 6/6 BANKED A REAL PATCH.**` gives 6/6, which is CONTRADICTED for the hard gate;
  - L8423 `(0/6, 6/6 patches banked)`;
  - L3977 `submitted in 7/22 calls`.
- **Lines with several counts are ambiguous.** 26 non-table lines hold two or more eligible N/M values plus a resolve keyword. Example: L790 `v3 patches 3/6 but resolves 1/6` gives 3/6, which is CONTRADICTED for v3.
- **Recall gap.** L27–29 (READ-THIS-FIRST #4, `2/6 (rich_4077 + rich_4079)`) contain none of `resolv|RESOLVED|score|dev`, so F1 and F2b extract nothing there. §12.7's example "v6 F1 2/6 at L27" is wrong under the design's own rule; the contradiction pair still forms from L163 vs L6742.

*Fix.* Replace F1's line-level keyword test with these rules, applied in order:
1. **Bar.** An N/M preceded within 12 characters (after stripping `*`) by `>=`, `≥`, `>`, `<=`, `≤`, `<`, `at least`, `bar`, `target`, `need`, `expect\w*` or `ideally` becomes a fact with field `bar`. It is recorded and never checked as an outcome.
2. **Unit.** An N/M followed within 3 characters by `calls?`, `c\b`, `patch(?:es)?`, `banked`, `edits?`, `chars?`, `ch\b`, `tests?`, `files?`, `hunks?`, `turns?`, `lines?` or `min` is not F1. `N/M calls` stays F3/F3t.
3. **Keyed.** F1 applies only when one of these holds:
   - a resolve keyword (`resolv\w*`, `RESOLVED`, `scored?`, `dev`) lies within 3 tokens of the N/M;
   - the N/M is followed by a parenthesized task-id group (the F2b idiom, which then also yields F2b);
   - the N/M is an F1v.

   Otherwise the N/M is `unkeyed`: recorded, not checked.
4. **Unit tests:**
   - L790 yields only 1/6;
   - L816 yields a bar;
   - L7829 yields only 0/6;
   - L3977 yields no F1;
   - L27 yields F1 2/6 plus F2b {rich_4077, rich_4079}.

**D3-3. [MEDIUM] The live-best baseline is a hard-coded constant, and the design does not say how to handle the conflict that now exists.**

*Where:*
- §12.8: "(b) the live-best v6 config (`_v6out/submission`)";
- §7.5, section 6: "vs live-best v6";
- §17 item 5: the rules check "v6 @ 0.12 sacred";
- §18.4: the BLOCK-K, P2 and P3 prompts.

*Problem* (MEASURED). The sources now disagree:
- **v6 @ 0.12:** the user brief ("Keep these: Live-best v6 @ 0.12 is sacred.") and `.kiro\steering\gemma-submission-protocol.md` L23 (mtime 2026-10-11).
- **v6w @ 0.15:** the log. L8389–8436 (2026-10-13) say v6w scored 0.15 in submission 57098497. L8436 says "v6w @ 0.15 is now the live-best … v6 @ 0.12 is no longer sacred.", and L8552 repeats it (`- v6w @ **0.15** = live-best.`).

Neither claim has been checked against the submissions history, which is not pulled. The design diffs levers against a literal `_v6out`, and the agent text hard-codes "v6 @ 0.12 sacred" without saying which source wins. So:
- the audit and refute passes can legitimately pick different baselines, which shows up as a spurious disagreement;
- a PROCEED bar of "beat the baseline" is ambiguous.

*Fix.*
1. **Make the baseline a curated input.** Add `curated\run_labels.json:baseline`, seeded in T1:

   ```json
   {"label": "v6", "run_id": "_v6out", "lb": 0.12,
    "source": "user brief 'Keep these'; .kiro\\steering\\gemma-submission-protocol.md L23"}
   ```

   §12.8 (b) and KB_SUMMARY section 6 diff against it. The builder never changes it.
2. **Add "Live-best claims" to KB_SUMMARY section 7.**
   - List every F5 or F10 live-best claim (L27, L163, L8389, L8391, L8436, L8552, …) with its status vs `submissions.csv`.
   - A claim naming a different live-best from the curated baseline is listed first, as `BASELINE CONFLICT`.
   - It is also shown in a one-line banner directly below the two stamp lines. That banner is an ordinary input-determined line, not a stamp line.
3. **Tell the agent which source wins (§17 item 5).**
   - The sacred baseline for policy is the one named in `gemma-submission-protocol.md`, read in full.
   - A conflicting log or LB claim is a finding to report.
   - A PROCEED whose bar depends on the baseline must name which baseline it uses and why.
   - That PROCEED is NEEDS-DATA while `submissions.csv` has not been pulled (`build_kb.py pull --submissions` is read-only and allowed).
   - Never adopt a new baseline on the log's word.
4. **Unit test:** the L8436 claim produces `BASELINE CONFLICT` against the seed.

**D3-4. [MEDIUM] Staged scored-submission configs are invisible to discovery and config parsing.**

*Where:* the §5 kinds table (`submit-dir`, `submission-folder`, `non-run`), the §6.3 sources, the LB mapping in §7.5 section 7, and §6.4.

*Problem* (MEASURED):
- **What is on disk.** `G\submit_t4096\` and `G\submit_branch_final\` each hold `agent.yaml`, `eval_config.yaml`, `configs\sampling.yaml`, `prompts\system.md` and a `submission.zip` (4,121 and 4,163 bytes). Neither has a `kernel-metadata.json`, a `notebook_src.py` or a `submission\` subfolder.
- **What they differ in.** `submit_t4096\configs\sampling.yaml` sets `thinking_budget: 4096`; `submit_branch_final` sets 1024.
- **What they are for.** The log says they are the next scored submissions:
  - L8502: `t4096 (thinking_budget 4096 vs 1024) is built and staged, ready for the next slot`;
  - L8501: `Branch submission still PENDING vs 0.15`;
  - L8553–8554 repeat both.
- **How §5 treats them.** They are not `submission-folder`s, because the directory name is not `submission`. Whether they are `submit-dir`s is ambiguous: "a top-level G\submit_* dir, or any dir nested inside one …, that holds kernel-metadata.json …" can be read with the condition applying to both, or only to nested dirs. They are also not among the named `non-run` items.
- **Result.** Under either reading, §6.3 never parses their YAML. When either is scored, the LB mapping in KB_SUMMARY section 7 cannot tie the LB row to its config, and the lever table cannot diff it. An audit of "submit t4096" would have no KB config to check.

*Fix.*
1. **§5:** state that a `submit-dir`, top-level or nested, must hold the `kernel-metadata.json`.
2. **New kind `staged-submission`, checked before `non-run`:** any directory outside run dirs and pulls that directly holds `agent.yaml` and `eval_config.yaml`.
   - It is parsed with §6.3's field paths, relative to that directory.
   - Its label is the directory name minus `submit_`, normalized and then passed through aliases.
   - Its prompt sha joins prompt-twin matching.
3. **Check the zip.** If a `submission.zip` sits beside it, hash each zip member (with `zipfile`) and compare it with the loose file. Record differences as `zip_drift: [paths]`, because the zip is what gets uploaded.
4. **LB mapping.** In KB_SUMMARY section 7, a submission row may map to a staged label, with basis `staged-label`. The Coverage and Levers sections list staged configs as columns without outcomes.
5. **Acceptance fact:** both dirs are `staged-submission`; `submit_t4096` yields `thinking_budget` 4096 and `submit_branch_final` yields 1024.

**D3-5. [MEDIUM] Dev-harness settings in notebook code are not captured, so the newest arm's only lever is invisible.**

*Where:* §6.3 (sources and field paths), §7.1 `config`, §12.8 (levers), §11 (harness semantics).

*Problem* (MEASURED):
- **Every notebook sets the dev harness the same way, except one.** Every `notebook_src.py` under `submit_*` that builds the dev harness passes `events_compaction_config=EventsCompactionConfig(compaction_interval=15, overlap_size=2, token_threshold=14336, event_retention_size=5)` and `context_cache_config=ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10)`. Examples: `submit_v6\notebook_src.py` L197, `submit_v19_lora_v2\notebook_src.py` L361, `submit_v15\notebook_src.py` L281. `submit_v15_cpu` builds none.
- **`compact5` changes only that setting.** `submit_v6z_on_v6w\compact5\notebook_src.py` L229 passes `compaction_interval=5`. Its header states that the submission schema has no compaction field (L21) and that only `compaction_interval` changes (L28).
- **Its submission folder cannot show the change.** `compact5\out\submission\` is hash-identical to `branch\out\submission\` in all four files: `agent.yaml`, `eval_config.yaml`, `configs\sampling.yaml` and `prompts\system.md`.
- **A text search would get it wrong.** `submit_v15\notebook_src.py` mentions `compaction_interval=5` in a header comment (L5), while its constructor passes 15 (L281). Only an AST read of the constructor call is reliable.
- **The scorer runs a different value.** HARNESS_README §7.2 (L554–562) documents the scorer's `compaction_interval = 5`. The log (L8441–8445, L8500) claims the 15-vs-5 mismatch affected every gate and "may partly explain why gate and board have disagreed all project".

§6.3 reads only the submission YAML and `write_text` constants. So in the KB:
- `compact5` is indistinguishable from `branch`;
- the lever table shows no change for it, and the prior-art check would tag it RE-RUN;
- the dev-vs-scorer mismatch, a confound on every gate verdict, is not represented anywhere.

*Fix.*
1. **Extract the settings (§6.3, tiers 2 and 3).** An AST pass over the notebook source records the constant keyword arguments of:
   - every `Call` named `EventsCompactionConfig` or `ContextCacheConfig`;
   - any `Call` passed as a keyword argument ending in `_config` to the same constructor call.

   Store them as `config.dev_harness = {"EventsCompactionConfig.compaction_interval": {value, source: "<nb>:L<n>"}, …}`. Non-constant values become `dynamic`; unknown classes go to `dev_harness_extra`. Comments are never read.
2. **Record the scorer's values.** Read them from README §7.2 (anchor `compaction_interval = `) as `scorer_reference` (DOCUMENTED, with its line), and set a per-run flag `dev_harness_matches_scorer`.
3. **Treat differences as levers (§12.8).** Dev-harness differences become lever instances with `kind: dev-harness`. KB_SUMMARY section 9 gets a new row, "Does the dev harness match the scorer?", with the per-run values.
4. **Acceptance:**
   - `compact5/out` yields 5;
   - every other in-scope run with a notebook source that builds the harness yields 15;
   - `compact5` has a lever instance vs `branch`;
   - `submit_v15` yields 15, not the 5 in its comment.

**D3-6. [MEDIUM] The acceptance tests are pinned to absolute line numbers in a log that gets edited in place.**

*Where:* §19.1 (the claims tests cite L558–559, L3958–3967, L4451–4489, L3115–3119, L7303, L7391, L6826/L6828, L7723, L6985, L7531 and L8094), §19.2 facts 13, 18 and 22, and the §12.7 tests on the 12 correction lines.

*Problem.*
- **The log is still growing.** It went from 8,436 to 8,555 lines during this review alone (mtime 2026-10-13 19:16). This time the growth was append-only, and every pinned anchor still holds (MEASURED).
- **It has been edited in place before.** §2.14 records that READ-THIS-FIRST was edited in place once, which shifted later entries by 28 lines.
- **Another edit is likely.** Item #4 (L27, "LIVE-BEST = v6 @ 0.12 … Never beaten") is now contradicted by L8436.
- **One edit breaks every pinned test.** A single edit above L558 shifts every pinned line at once. The pre-registered bars would then be "missed" for reasons that have nothing to do with the parser, or the coder would edit the line numbers after the fact. §19 forbids both.
- **The fixture source is unstated.** The design never says whether the unit tests use copied fixtures or the live log.

*Fix.*
1. **Unit tests read copies.** Copy the needed snippets once in T1 into `KB\tests\fixtures\log\`. Each copy records its source line and the log's sha256 at copy time.
2. **Slow tests anchor by content.** Tests on the live log locate lines through one helper, `find_line(prefix, occurrence=1)`, and assert spans and offsets, never absolute numbers. Example: the block that starts at the line beginning `### REVISED STANCE: my "v8 is a net negative"` spans 10 lines.
3. **Record the log version.** `build_verification.md` records the log's sha256 and line count at test time.

### NIT

**D3-7. [NIT] Snapshot counts and cross-references have drifted or disagree.**
- **Conflicting snapshots.** §0 says "the 2026-10-13 07:28 snapshot" and an "8,384-line" log. §2.1 says 18:24, and §2.14 says 8,436 lines.
- **Current counts** (MEASURED): 155 traces in 29 run dirs; 30 JSON kernel logs; 8,555 log lines, with 210 `##` lines, 1,371 `###` lines and 504 `###` blocks.
- **New arms.** `compact5` uses slug v6w. `m12` has a new slug, `…-m12`, and its `agent.yaml` declares `gemma-4-12b-it-qat-w4a16-ct`, so §6.3 makes it `out_of_scope: non-31B model`. `…-v6w` now backs 10 dirs, not 8.
- **Fact 19's count is wrong.** It says 10 traces have "3 consecutive nudges and nothing after"; the right count is **9**. 10 traces reach 3 nudges, but `Outputs\v19_lora` rich_3469 has 3 nudges followed by 16 valid calls, and it ended by CALL_CAP (harness event `Tool call budget (15) exhausted`).
- **Header vs row.** §12.4 cites "L7303 rich_4077", while §19.2 fact 18 cites L7305. L7303 is the table header; L7305 is the rich_4077 row.

*Fix:* restate the counts as one snapshot, set fact 19 to 9, and cite L7305.

**D3-8. [NIT] The §7.1 `config` example leaves out fields that §6.3 defines.** It lacks `stop_sequences`, `sampling_extra` and, with D3-5, `dev_harness`. Add them so the schema matches the extractor.

**D3-9. [NIT] PASS_START does not accept the format P1h was widened for.**
- P1h accepts `[i/N] Evaluating <task> (<repo>)...` (S12), but PASS_START's `^\[1/\d+\] \S+ \(` does not.
- The format comes from the competition's sample loop (`G\compeition\getting started`, L375 and L399).
- A multi-pass log in that format would have its passes merged.

*Fix:* use `^\[1/\d+\] (?:Evaluating )?\S+ \(`.

**D3-10. [NIT] A text call quoted in prose becomes a duplicate edit attempt.**
- In `v2_gate_out2` rich_4070, step 6 repeats the step-4 call in prose: "Wait, looking at my previous response:\n`call:edit_file{filepath:"rich/logging.py",new_string:…`".
- §6.2 parses every `call:\w+\{` match, so this becomes a second AS_TEXT edit attempt.

*Fix:* skip matches inside backticks, or dedupe identical `(fn, args_raw)` pairs within a trace, keeping the first and recording `quoted_repeat: n`.

**D3-11. [NIT] The read-event definition and the aligned-range table disagree.**
- The §6.2 returned-range table lists "python prints" under aligned ranges.
- The read-event definition covers only `read_file`, `cat|sed -n|head|tail|nl|awk|grep` with a path operand, and `edit_file` diffs.

*Fix:* pick one. Either any `run_command` observation that aligns at least 2 consecutive lines of a gold file at that call is a read event for that file (`via: aligned`), or drop "python prints" from the table.

**D3-12. [NIT] Paragraphs longer than 12 lines are unspecified.**
- §12.3 says "every paragraph (consecutive non-blank lines, ≤ 12)" but not what happens to longer ones.
- MEASURED: 37 paragraphs exceed 12 lines, e.g. L79–93 and L468–482.

*Fix:* split them at line boundaries into consecutive chunks of at most 12 lines, each a candidate claim with `chunk: k/n`.

**D3-13. [NIT] A6's time window rejects the earliest runs.**
- A6's trace-timestamp window starts at 2026-10-01.
- But the log has 2026-09-30 dates (3 tokens), S13 accepts log dates back to 2026-09-01, and T12 pulls the earliest versions (v1–v5).

*Fix:* use 2026-09-01 as the lower bound for both A6 and S13.

**D3-14. [NIT] A23's stated basis points the wrong way.**
- README L351 resets the nudge counter when `turn_has_tool_call == True`. That reads as "the turn emitted a tool call", which includes ARG_REJECTED calls.
- A23 assumes the opposite: that rejected calls do not reset the counter.
- MEASURED: today the two variants give identical histograms over 155 traces ({0: 131, 1: 12, 2: 2, 3: 10}), so nothing changes now.

*Fix:* make the any-call reset primary (it is the README's literal condition), keep the valid-call variant as the alternate, and cite L351 in A23.

---

## Verified assumptions (checked against source or data during this review)

1. **Inventory.**
   - 155 ATIF-v1.7 traces in 29 run dirs.
   - No step holds more than one tool call, and no observation is an orphan.
   - Every step `extra.timestamp` is numeric epoch seconds.
   - Trace run dates span 2026-10-03 (`_v6out`) to 2026-10-14 UTC (`compact5`, `m12`).
2. **Count model cm-2** (§2.2, §6.2): residual 0 on **155 of 155** traces that have a harness value (β = 1).
3. **ARG_REJECTED.** 140 calls in 12 runs, split per run exactly as §2.2 states. All 140 list `old_string` and only `old_string` as missing, which settles §2.2's "72 not re-checked".
4. **Multiple submits.** 13 traces have more than one OK submit. In the three where the sizes differ, the harness `patch_chars` equals the last one: v6s rich_3882 = 511, v6x rich_4076 = 371, v6x rich_4077 = 324.
5. **Nudges.**
   - The maximum is 3, and 10 traces reach it.
   - The histogram is the same under both reset variants.
   - README L349–352: `max_nudges = 3`; the count goes 1, 2, 3; the loop ends when it exceeds 3.
6. **Harness events.**
   - Deduped templates across the JSON logs: 24 NO_SUBMIT_EMPTY_TREE, 11 TIME_CAP, 9 NUDGE_EXHAUSTED, 7 CALL_CAP, 7 TURN_CAP and 1 VERIFY_TEST_PATCH_FAIL. None is UNKNOWN.
   - Every per-task line appears twice.
7. **S14 swallowed arguments.** `hard\out` rich_4070 steps 29–33 and rich_3486 step 13 have exactly the argument shapes in §2.17. §6.2's salvage steps yield the stated OLD.
8. **Text calls.** `v2_gate_out2` traces use plain double-quoted values (`call:read_file{filepath:"rich/markdown.py",start_line:159,end_line:171}`), so the lenient §6.2 regex fits.
9. **Log structure.**
   - **Size.** 8,555 lines today, with 210 `##` lines, 1,371 `###` lines and 504 `###` blocks.
   - **Blocks.** 99 multi-line blocks hold 966 lines; 52 have at least 5 lines; the longest has 45. No two `##` lines are adjacent. The blocks at L558–559, L3958–3967, L4451–4489 and L3115–3119 are as stated.
   - **Corrections and dates.** 75 `##`/`###` lines match CORRECTION_RX: the 12 named positives match, and L4362 does not. L8094 (`2026-12-12`) is the only heading date outside the window.
   - **Anchors.** The READ-THIS-FIRST items sit at L12, 19, 23, 27, 30 and 33. The anchors cited in §2.14, §12.4 and §12.6 hold.
   - **The brief's named claim** ("v6b rich_4070 made 31 calls … not ONE python-replace edit", L6834–6838) sits in a paragraph that matches VERDICT_RX and CORRECTION_RX (`VERDICT`, `FALSIFIES`), so §12.3 reaches it.
10. **Kernel ids and submit dirs.**
    - Every dir under `submit_*` that holds a `kernel-metadata.json` uses the prefix `comfyops/gemma-sibling-conform-`.
    - `submit_v19_lora_v2`, `submit_v18`, `submit_v19_lora`, `submit_v10` and `submit_v6` exist, so the §6.4 run-to-submit-dir mapping works.
    - `_v12_kaggle_pull` holds a `kernel-metadata.json` and an `.ipynb`; `pulled_v6` holds only an `.ipynb`; `_v10v2_pull` is empty.
11. **Notebook extraction.** 51 `notebook_src.py` files make 228 `write_text` calls. Only `submit_v6s`'s `system.md` is dynamic (`STOCK_SYSTEM_MD`).
12. **YAML subset.** Across 100 submission YAMLs, the only construct beyond plain scalars and `!include` is serA's quoted list item `- "<|tool_call>"`.
13. **Model ids.** 31B runs declare `gemma-4-31b-it-qat-w4a16-ct`. `m12` declares `gemma-4-12b-it-qat-w4a16-ct`, so the §6.3 out-of-scope rule applies.
14. **Workflow engine.** In `extension.js`, `filterTools` adds `send_message` through `policyBypassToolIds(…, isWorkflowStepSession)`. So `gemma-auditor`, whose tools are `[read, write, shell]`, can still send the lifecycle signals that P2 and P3 rely on.
15. **Agent draft.** `.kiro\agents\gemma-auditor.md` (8,144 bytes) has exactly the frontmatter keys §17 keeps: `name`, `description`, `tools: [read, write, shell]` and `welcomeMessage`.
16. **README.**
    - Output caps: L325–327, L382 and L436 (5,000-character command output; `read_file` returns at most 150 lines and 10,000 characters).
    - §7.2 (L554–562) gives the scorer's compaction and cache values.
17. **rich's pytest config** is only `testpaths = ["tests"]` (`pyproject.toml` L64–65). So `-o timeout=0`, without pytest-timeout installed, produces only a warning.
18. **Steering.** `gemma-submission-protocol.md` L23 still says "v6 @ 0.12 is SACRED" (mtime 2026-10-11).

## Unverified or wrong assumptions

**Wrong (contradicted by measurement):**
- **§12.7, "v6 F1 2/6 at L27".** L27–29 carry no F1 keyword (D3-2).
- **§12.4 and §19.1, F1v at L7796.** That line never becomes a claim on the real log (D3-1).
- **"Live-best = v6 @ 0.12" as a fixed fact (§12.8, §17).** The log contradicts it at L8389–8436 and L8552. The claim has not yet been checked either way against the submissions history (D3-3).
- **§6.3 completeness.** It misses the dev-harness settings (D3-5) and the staged submission dirs (D3-4).
- **Fact 19's count and the §0/§2 snapshot numbers** (D3-7).

**Unverified (not checkable from disk, or not re-checked here):**
- **A2:** that the model ids are in the user's live catalog.
- **A4:** that `patch_chars` counts characters rather than bytes.
- **A18:** how long a replay populate takes.
- **The build-time bar:** a non-replay build in at most 300 s.
- **R1's 359-character occurrence at base.** The second review and §2.17 measured it; I ran no git.
- **Fact 5** (the `Outputs\v14` pairing conflict) and the SAMPLE_ADAPTER hashes.
- **The Kaggle CLI line citations** (L6541/L6666/L6691). The second review verified the behaviour; I did not re-read the source.
- **The submissions history** that D3-3 depends on, which has not been pulled.

## Second-review findings (revision 3 responses)

**Spot-checked on disk; the responses hold:**
- F1 and F2: the regexes, heading blocks and counts.
- F6: nudge semantics.
- F7: scoring of the last submit.
- F8: stage classes; the INFRA templates are present in the logs.
- N15: `observation.extra.tool_name`.
- N16: `submit_v6z_on_v6w` holds only its `.ipynb`.
- S12: the getting-started format.
- S13: L8094.
- S14: the swallowed arguments.
- S16: serA's `stop_sequences`.

**Partly holding:** F3. Its version-column rule is sound, but its TOTAL rows and its F1v example depend on D3-1.

**Not re-checked:** F5 (the performance numbers), F9, F10 (the clone measurements), F11, F13, N18 and N19–N26.
