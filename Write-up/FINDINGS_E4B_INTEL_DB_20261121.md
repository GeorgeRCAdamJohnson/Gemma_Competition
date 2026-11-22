# Where E4B loses: an attempt-level analysis of 14,739 agent runs

*Findings paper, 2026-11-21. Prepared from two review perspectives: a data analyst (does each number survive its
confounder?) and an ML researcher (what can it establish, and what would a test need?). Correlational throughout;
public tasks only.*

## Abstract

We built an attempt-level database of every E4B and 31B agent run held by the project (14,739 unique attempts,
7,807 full traces, 93,000+ steps, 117,000+ tool calls, vLLM server logs) and validated it against 27 previously
recorded results. Scanning it for losses that are large, mechanistic and untried produced two leads: E4B often makes
**incomplete multi-site fixes**, and its fixer **overflows the context by re-reading files**. An audit then shrank
both. The incomplete-fix gap is mostly between tasks, with thin within-task support; the overflow loss is about 75
solves (+2.9% relative, an upper bound), not 120. Realistic effects of interventions are +0.2 to +0.65 tasks per
39-task round, and our 5-round A/Bs can only detect about +1.5. Edit-anchor failures, the most frequent tool error,
are a symptom of wrong fixes rather than a cause. A tool-state LoRA left every measured behaviour unchanged. The
practical consequences are to test mechanisms on intermediate outcomes and targeted cohorts before solve rates, and to
target adapter training data at specific behaviours, including single-file multi-hunk fixes.

## 1. Data and validation

- **Sources.** swegemma `task_results.jsonl`, `lora_progress.json`, Colab/Kaggle pass summaries, tar archives (the
  only 31B traces), ATIF traces, display logs, vLLM server logs, registrations, bundles, notebooks and the experiment
  log. Built by `kb/attemptdb/build.py`; schema in `kb/attemptdb/README.md`.
- **Deduplication.** The same attempt is often stored 2-4 times; a fingerprint (task, round, arm, outcome, patch size,
  duration to 0.01 s, call counts) merges copies. Checks found and fixed four false-merge bugs during the build.
- **Validation (27/27 checks).** Reproduces the p5 paired result (178 vs 189 verified solves over 624 attempts per arm),
  every pass total of 134 Colab passes, repair-decisions rounds (60; 10/11/13/11/14), bundle hashes in
  pre-registrations; decoded tool-call counts match swegemma's in 97.8% of attempts; all 306 overflow attempts have a
  matching vLLM overflow error on their own GPU lane in their time window.
- **Definitions.** `verified` = resolved, no error, exit 0, non-empty real test output, no routing violation. Analyses
  use E4B attempts with a trace unless stated; "mixed-outcome tasks" are tasks with solve rate 10-90%.

## 2. Findings

Each finding lists the first-pass claim, the audit and a confidence rating (high / medium / low).

### F1. Failure map (high confidence as description)
3,666 failed traced E4B attempts on the 34 tasks E4B has solved at least once: right file but no new test passes
24.2%; right file, no test output on disk 23.2% (unclassifiable); wrong file only 20.6%; context overflow 17.0%;
right-file near miss (some new tests pass) 8.9%; never edited 5.6%; timeout 0.4%. The gate accepts ~80% of
wrong-file and wrong-fix attempts, because it only runs existing tests.

### F2. Incomplete multi-site fixes (DOWNGRADED 2026-11-22: not supported within task)
*Update:* with the full database (103 exp x arm x task strata on the 15 swing tasks), winners and losers on the same task
edit the same number of files (28 vs 25 strata, p 0.78) and make similar-size patches (p 0.43). The pattern below is a
between-task difficulty effect. See the 2026-11-22 log entry "DISCOVERY over the full DB"; the within-task signal is the
location of the first edit and an early-restart opportunity, not the number of sites.
- *First pass:* on multi-hunk tasks, patches covering some gold hunks solve 20.1% vs 52.5% covering all; 654 failed
  attempts covered some-not-all, 3.5x the 189 that covered all and failed. 31B edits 2.09 files per attempt vs E4B 1.19.
- *Audit:* the pooled gap holds at line windows 0/5/15/30 and with runtime-only hunks (16-24% vs 42-70%). Only 5-7 tasks
  have enough attempts in both groups for a within-task comparison; there the gap is +0.23 to +0.34, with full coverage
  winning on 2-5 tasks and losing on 1-2. Missed hunks share an identifier with the agent's own edit 83% of the time,
  against a 58% null (random gold hunk of another task, same repo).
- *Reading:* largely a between-task difficulty difference, with a consistent but sparse within-task signal. A grep
  seeded from the edit carries information but will be noisy.

### F3. Read waste and fixer overflow (medium)
- *First pass:* overflow = 17% of failures; ~120 solves lost; 74.6% of overflow read volume is waste.
- *Audit:* the **fixer** overflows (738/786), not the verifier, so the October `include_contents: none` verifier fix
  would not help. 225 overflow attempts had hidden tests run on their on-disk patch and failed; only 447 are ungraded.
  Corrected loss: ~75 solves (+2.9% relative, +0.39 tasks per 39-task round, upper bound). Overlapping re-reads are 49%
  of overflow read volume (32% normally); model text also doubles (40.0k vs 19.5k characters).
- *Reading:* real and mechanical, but smaller than first stated, and reads explain only part of it. Every bundle ever
  built gives the fixer `read_file`; read limits were only ever prompt rules, which the log records as ignored.

### F4. Edit-anchor failures are a symptom (medium-high)
`edit_file` "old_string not found" is the commonest tool failure (5,673 in 1,475 E4B attempts), and attempts with it
solve 15.9% vs 28.7% within the same 32 tasks. Causes: near miss 41.8%, invented 26.3%, partial 12.7%, stale (text from
before the model's own edit) 11.5%, escaping 6.8%. After one, the next edit to that file fails 71%. But failed-anchor
edits resemble edits from failing attempts, not solving ones: gold-like 12.7% vs 38.6% (exact lines), 44% vs 76%
(token Jaccard >= 0.5). A tolerant edit tool would recover a few percent at most.

### F5. The tool-state LoRA changed no behaviour (high)
p5 adapter vs base, 624 paired attempts each: calls 15.6/15.2, reads 6.2/5.9, failed edits 1.03/1.04, files edited
1.24/1.22, calls before first edit 6.5/6.4, overflow 12.8%/11.7%, solve 28.5%/30.3%. Consistent with its curriculum
holding zero final edit targets.

### F6. 31B vs E4B (low: configurations differ)
On 24 shared tasks 31B makes 9.1 calls before its first edit (E4B 5.7), greps 5.9 times (2.4), edits 2.09 files
(1.19), repeats calls 0.56 times (2.01), overflows 1.7% (9.4%). On fastapi_5077 and rich_3882, E4B edits the gold file
first 99-100% of the time and solves 0-8%; 31B solves 100%. The 31B runs use ca5 (single agent) and E4B mostly pack 1,
and 31B edit detection is weaker (shell-script edits), so this is suggestive only.

### F7. Fix shape predicts E4B difficulty (medium as description)
Over the 129 tasks: 1 file / 1 hunk 17.1% mean solve (21 of 54 tasks ever solved); 1 file / 2+ hunks 5.8% (10 of 34);
2+ files 2.9% (3 of 41); <= 10 changed lines 17.5% vs 41+ lines 0.7%. Task size confounds this for any model.

## 3. Threats to validity (data analyst)
- **Confounding by task.** Pooled comparisons mix easy and hard tasks; within-task versions exist only for a handful
  of tasks.
- **Selection.** Coverage needs a saved patch; traces exist for some experiments only; "right file, no test output"
  (23% of failures) cannot be graded locally.
- **Proxies.** Gold-hunk coverage (line windows), gold-likeness (exact or Jaccard), waste (overlap rule) are heuristics;
  conclusions were checked for sensitivity where possible.
- **Model labels.** Where no trace exists the model is inferred from the path.
- **Public tasks only.** The hidden tasks are private repositories; shares of multi-hunk fixes and overflow may differ.

## 4. Inference and power (ML researcher)
- **Forking paths.** The leads were chosen after examining many features. Treat them as hypotheses for fresh,
  pre-registered data.
- **Effect sizes.** Expected gains: F2 intervention +0.24 to +0.65 tasks per 39-task round (10.8% of attempts in the
  partial bucket x within-task gap 0.23-0.31 x uptake 25-50%); F3 <= +0.39.
- **Power.** Seed39 per-round sd 1.47 over 24 rounds. To reach t >= 2: ~9 rounds per arm for +1.0, ~35 for +0.5, ~96
  for +0.3. Our standard 5-round A/Bs detect only ~+1.5, so many past nulls are uninformative about small real gains.
- **Interactions.** A "find other sites" step adds context and raises overflow risk; F2 and F3 interventions should be
  designed together.

## 5. Recommendations
1. **Mechanism first.** Measure intermediate outcomes that move on almost every attempt: gold-hunk coverage for a
   post-edit sites skill; overlapping re-read volume and overflow rate for a structural read limit (no `read_file` in
   the fixer; a ranged view skill that refuses re-shown ranges and tests/docs). Stop if the mechanism does not move.
2. **Targeted cohorts.** F2 on multi-hunk tasks with frequent partial coverage; F3 on overflow-prone tasks
   (fastapi_14873, rich_2725, rich_3518, fastapi_14616).
3. **Then a solve-rate A/B** with >= 10 rounds per arm, guard tasks and a pre-registered rule.
4. **Adapter data must target a behaviour** (F5), measured with the same intermediate outcomes; candidates are complete
   multi-site edits and non-redundant reading.
5. **Pull the remaining test outputs** so the 23% unclassifiable failures can be graded.

## 6. Comparison with `Outputs/public-repair-triage-20261121-combined-v2/REPORT.md`

The triage report is a different stage of the same programme: mining public PRs from seven non-benchmark repositories
as candidate families for an independent adapter corpus. It reports 35 ranked leads, zero qualifying families, every
lead quarantined, and one multi-file lead (attrs #1328).

| Aspect | This paper | Triage report | Relationship |
|---|---|---|---|
| Question | Where does E4B lose on benchmark tasks? | Which public PRs might become training families? | Diagnosis vs supply |
| Data | 14,739 agent attempts on 129 benchmark tasks | 180 PR IDs from 7 repos outside the benchmark list, metadata only | Different source lists; leakage NOT ruled out (lineage and benchmark overlap unadjudicated) |
| Evidence standard | Correlational, audited, power-assessed | Metadata heuristics, explicitly unverified | Both refuse to overclaim |
| Multi-site emphasis | F2: incomplete multi-site fixes are the largest lead | Ranking gives multi-source-file PRs 20 points vs 10 | **Aligned in direction** |
| Granularity | Hunks within and across files | Changed-file lists only; patches deliberately not retained | **Gap** |
| Size | Small fixes are where E4B succeeds (<= 10 lines 17.5%, 41+ lines 0.7%) | Bonus for <= 8 files and <= 300 changed lines | Thresholds far looser than E4B's range |
| Contract / edge keywords | F1 near misses (8.9%) are edge-case test failures | Edge/contract keywords +2 | Aligned; both small |
| Validation of value | Intermediate outcomes defined (coverage, re-reads, overflow) | "Next bottleneck: ... executable gates" | This paper supplies measurable targets |

**Where they agree.** Both put multi-site repair at the top and both mark everything as provisional. The triage's 35
leads remain unverified: no lineage, benchmark-overlap, licence or executable check has passed. Querying repositories
outside the benchmark list keeps the source lists separate, but that alone does not prove the absence of leakage.

**Where this paper informs the triage.**
1. **Score multi-hunk fixes, not only multi-file ones.** On the benchmark, single-file fixes with 2+ hunks are hard for
   E4B (5.8% mean solve vs 2.9% for multi-file), a comparable share of tasks (34 vs 41 of 129) and more often within
   reach (10 vs 3 ever solved). Changed-file metadata cannot see hunks. Detecting them needs the hunk headers (line ranges
   only), which would not require retaining patch bodies.
2. **Tighten the size window.** E4B solves 17.5% of fixes with <= 10 changed lines and 0.7% above 40; a 300-line
   bonus admits fixes far beyond what the model lands, which makes them poor demonstrations of learnable behaviour.
3. **The supply constraint is severe.** One multi-file lead in 35 means a multi-site curriculum cannot come from
   multi-file PRs alone; single-file multi-hunk PRs widen the pool.
4. **Define acceptance by behaviour.** F5 shows an adapter can train cleanly and change nothing. Before a family counts,
   the protocol should say which measured behaviour it should move (e.g. gold-hunk coverage, re-read volume) so the
   adapter can be evaluated on that behaviour in the database's terms.

**Where the triage report informs this paper.** It confirms that independent, licence-clean, non-benchmark training
data is scarce and slow to qualify (0 of 35 so far, all unverified), so prompt- and skill-level interventions
(Recommendations 1-3) are the cheaper first tests. Its planned lineage and benchmark-overlap adjudication is the right
guard for any adapter derived from F2/F3, and must actually be completed: training on the benchmark tasks studied here,
or on upstream lineage shared with them, would overfit the public set.

## Appendix: reproduction
`python kb/attemptdb/build.py; python kb/attemptdb/verify.py`, then the analyses: `Outputs/_bt_anchor_mechanism.py`,
`_bt_anchor_intent.py`, `_bt_failure_map.py`, `_bt_overflow.py`, `_bt_context_fill.py`, `_bt_read_waste.py`,
`_bt_tool_lists.py`, `_bt_31b_vs_e4b.py`, `_bt_hunk_coverage.py`, `_bt_sites_feasibility.py`, `_bt_log_search.py`,
`_bt_audit.py`, `_bt_audit2.py`, `_bt_task_shape.py`. Experiment-log entries of 2026-11-21 record each step.
