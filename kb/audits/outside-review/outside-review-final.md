# OUTSIDE REVIEW — FINAL (merged)

Merges `reviewer-a.md` (Reviewer A, claude-opus-5) and `reviewer-b.md` (Reviewer B, gpt-5.6-sol), both executing
`Gemma/AUDIT_PROMPT_OUTSIDE_REVIEW.md`. Where they disagreed, or where a load-bearing number rested on one
reviewer only, I re-checked the raw artifact myself; every such check is named below as "settled by merger
(artifact:line)". Paths are relative to `Gemma/` unless stated. Log = `GEMMA_EXPERIMENT_LOG.md`.

Input status: both reports are present and complete (each has a findings table, per-claim coverage of A1–G1,
three-claims section, number-conflict table, established list, next steps). No gap had to be inherited as
UNVERIFIED for missing coverage.

Environment caveat: `kb/.build.lock` was still present (mtime 2026-11-01 15:17) during this merge, so the KB was
treated as mid-rebuild. Nothing here rests on `runs.jsonl`, `near_miss.jsonl` or `KB_SUMMARY.md`. Raw run dirs,
replay JSONs, test logs, traces (`steps[].tool_calls[].arguments`), harness source and the log (via
`kb/kblib/logdb.py` + targeted line reads) only.

Labels: MEASURED = recomputed from a raw artifact. INFERRED = follows from measured facts. ASSUMED = not checked.
"Both" = confirmed by both reviewers independently. "A" / "B" = one reviewer. "Merger" = raised or settled here.

---

## 1. Findings table (severity order)

| # | sev | claim (where) | what the evidence supports | raised by | label |
|---|---|---|---|---|---|
| M1 | blocking | A1: "59 truly solvable", 60 gold-valid (fastapi 29, rich 30, requests 1) — log L15393-15400, L15322-15330 | **59 is a lower bound produced by a replay rule that is stricter than the grader, not a ceiling.** (a) `kaggle_pkg/out_gold_fa/replay_result.json` ran node mode: all 67 rows carry `file::fn` nodes built as a cross product (`local_eval/parity_rig/replay_verify2.py:95-99`). **0 of the 24 multi-file fastapi tasks** are recorded gold-valid; all 29 come from the 43 single-file tasks. (b) `replay_gold129_files.json` counts `skipped` as failure (`replay_verify2.py:110-113`), while the harness runs whole files and only rejects failures/errors or a *required* node that is skipped (`harness_src/x/swegemma/harness/verification.py:289-300, 319-343, 619-623, 646`). **13 rich tasks fail on skips alone**; in node mode (`replay_gold129.json`) 8 of them pass their required nodes (rich_3043, 3105, 3470, 3676, 3772, 3777, 3894, 4075). (c) The grader itself resolved two tasks the inventory calls gold-invalid: `fastapi_14786` (official `test_outputs/fastapi_14786.log` "9 passed in 0.45s", resolved=true, exit 0) and `rich_3894` (resolved in `out_e4b/results/task_results.all.jsonl`), so the inventory is wrong on at least 2 tasks by external judgement. (d) The 12 failing `requests` gold rows show 195-197 collection errors (e.g. requests_7505) in the environment B1 already calls defective for requests: unjudged, not unsolvable. | Both (A: mechanism + the 8; B: "lower bound, not ceiling"). (c) settled by merger | MEASURED (a,b,c,d); INFERRED that the 8 resolve on the grader (rich_3894 is MEASURED) |
| M2 | blocking | A1: "34 tasks are dead because the **official** eval image cannot collect their tests" — log L15152-15166 | 34 is the **union** of the official image and the local rig (`local_eval/parity_rig/_live_dead_split.py:42`: `dead = kb \| lb`). Settled by merger over `test_outputs/*.log` with the strict three-module rule: official **28**, local capped r0 **32**, both **26**, union **34**, all fastapi. The log's own table at L15160-15161 shows 28 and 32 directly under the heading claiming 34. Local-only six: fastapi_11355, 14099, 14455, 14962 (official logs exist and do not show the strict missing-module error), fastapi_14356, 15745 (**no official log**: they died on context overflow / 8-min timeout, tests never ran). Defensible grader-dead floor = 28. | Both | MEASURED |
| M3 | blocking | C1: "run-to-run noise is ±2 tasks per 129" — log L15065-15068, L15105 | **Contradicted by an identical-config pair already on disk.** Settled by merger: `_m1_full129_ca5.py` and `_m1_full129_ca5_v2.py` differ only in output path and a print label (same `--submission-dir /rig/agent_ctrl_v5`, `--concurrency 2`). They recorded **15 vs 10** (genuine 12 vs 7), discordant 5/0, agreement 124/129, McNemar p = 0.0625. The capped identical pair is 12 vs 14 (121/129). So two identical pairs gave spreads of 5 and 2. ±2 is one observed difference, not a variance estimate. Disagreement resolved: A called all five runs "same-config"; B said the older pair differs "in packaging/history". Both are partly right: ca5/ca5_v2 are identical to each other, but differ from the capped runs in concurrency (2 vs 3, log L14980-14981), explicit cap flags, and the declared model string (next row). The ±2 claim fails on the ca5 pair alone. | Both (disagreement on comparability settled by merger) | MEASURED |
| M4 | minor (downgraded from material, 2026-11-01 user correction) | §4 retraction "all local runs are E4B" (log L14797) | **Mostly resolved.** The user's run history: 31B ran **on Kaggle** (v10 / A3-hard kernel `comfyops/gemma-sibling-conform-31b-a3-hard`, all 129 tasks, 34/129 per log L12572; output in `local_eval/pull_31ba3hard_out/`), plus 1 task locally. 12B ran on roughly 17 tasks. E4B ran all 129 several times. The artifacts agree. `_m1_full129_ca5.py` / `_ca5_v2.py` send to llama-server `:8081`, which serves only the E4B GGUF. The `gemma-4-31b-…` string in `agent_ctrl_v5/agent.yaml` is a stale label that the single-model server ignores, so ca5/ca5_v2 are E4B. `_m1_full129_off12.py:1,20` targets a **separate vLLM server on `:8082` running the official 12B**, and `m1_full129/off12_r0` holds only 6 task rows. So A's `off12` vs `ca5` gap (4.77 vs 3.55 on the 7-task cohort) **compares 12B with E4B**. It is not evidence of between-batch variance, and A's F21 "blocking risk to every local A/B" is withdrawn. What remains: no run dir records the served model (`/props`), so this rests on the scripts plus the user's account rather than a per-run stamp. Fix: write the served model into `summary.json`, and stop shipping a 31B label in an E4B bundle. | A (raised); merger (corrected with user + `_m1_full129_off12.py`) | MEASURED (scripts, ports, row counts); user testimony (run history) |
| M5 | material | D1: prompt worth "+2 to +4"; "3 tasks solved in all 3 ca5 runs and NEVER by the empty prompt" — log L16081-16123 | Settled by merger. Counts and p-values reproduce on the 3 capped/faithful runs (7 vs 9/11/11; 6/4 p=0.754, 6/2 p=0.289, 6/2 p=0.289). Phantom subtraction is not differential: all 6 runs contain all 3 phantoms (B's point, confirmed). With the two ca5 runs that use the same prompt (sha identical) added: `ca5_v2` genuine 7 = no-prompt 7, McNemar 3/3 p=1.00; `ca5` vs no-prompt 7/2 p=0.18. Always-solved across all 5 prompt runs = **2** (fastapi_14463, rich_3905); `fastapi_14616` is missed by `ca5_v2`. The log calls `rich_2725` a task "ca5 only gets flakily" (L16108-16109); **no prompt run solves it** (0/5); it is the only no-prompt-unique solve. No-prompt arm n=1. "Never" = "not in one draw". | Both on n=1 / causality; A on 5-run core and rich_2725 (verified by merger) | MEASURED |
| M6 | material | F1: sweep arms comparable against the baseline floor | Baseline rows scored by **rp-4** (11 rows), all 77 arm rows by **rp-5** (`kb/audits/2026-10-15-decode-commitment-sweep.jsonl`, field `scorer_engine`; settled by merger). Report title says rp-4 (L1), header says rp-5 (L8). One run per (arm, task) cell (88 unique cells, 0 replicates). The rich clone was dirty (`M rich/padding.py`, report L9-10). Cache key = decode-config hash + task (`local_eval/decode_sweep.py:115, 276-289`), with no model/prompt/backend/scorer identity. | Both (rp-4/rp-5); B (dirty clone, cache key) | MEASURED |
| M7 | material | B2: "local and Kaggle agree within noise"; "local never hits overflow or the time wall" — log L14814, L15003-15010 | Count-level overlap only. Settled by merger: Kaggle's 10 solves overlap with local runs by 7 (ca5), 6 (ca5_v2), 5 (cap r0), 8 (cap r1), 7 (faithful), 4 (no-prompt). Local context-window errors: cap r0 2 (`requests_7328` line 16, `fastapi_14266` line 61), cap r1 4, faithful 2, **ca5 2, ca5_v2 3** (the very runs L14814 described as never overflowing), no-prompt 3. Kaggle: 6 overflows + 2 timeouts (`task_results.all.jsonl` lines 10, 19, 34, 56, 72, 77, 86, 93). Time wall is never hit locally (max 454 s); Kaggle max 730 s. Kaggle's 10 include `requests_6644` (line 96), the empty-patch freebie the log itself flags at L15389, so Kaggle genuine = 9. The rigs' reachable sets differ systematically. "Within noise" has no valid noise model behind it (M3). | Both (overflow, transfer); A (freebie); B (overlap 5/8/7) | MEASURED |
| M8 | material | C2: "every arm ±1-3 tasks, all below the noise floor, so nulls are uninformative" — log L15070-15075 | Overstated. The same paragraph lists multi-agent outcomes "0 and -5" (L15070-15071), which is outside ±1-3. B: A19/A20 (18 runs/arm) and A21 (~25/arm) at L12515-12566, L12637-12704 had enough replication to rule out the large projected effects. A: on one fixed 7-task rich cohort, `router_v2` (n=3) and `off12` (n=13) differ from `ca5` (n=29) at p ≈ 3e-4 and 1.5e-4. The instrument lacked replication, not resolution. A's cohort statistics were **not re-derived by merger** (UNVERIFIED here). The `off12` comparison is a 12B-vs-E4B model contrast (M4), not a prompt/arm effect. | Both | B: MEASURED (log lines); A cohort numbers: UNVERIFIED by merger |
| M9 | material | Merger finding. Log L15025-15027, L15078-15083 and both reviewers' §5: "resubmitting the same artifact is +EV; best-of-N reaches 6/58 in ~5-10 draws" | The binomial behind this (E[k]=4.5, σ=2.04 on 58) models **drawing a new 58-task set**. The hidden 58 tasks are fixed. Resubmission redraws only the agent's sampling on the same 58 tasks. The observed E4B score 0.03 = 2/58 is the best available estimate of that fixed set's centre. Measured run-to-run churn on a fixed set is 5-8 discordant tasks of 129 (M3), i.e. roughly 2-4 of 58, split both directions. So P(≥6/58 per resubmit) is plausibly well below A's ≈0.25. The §4 retraction (p=0.163, "ordinary noise") is still a correct statement about task-set sampling. The corollary drawn from it is not. | Merger only (not raised by A or B) | INFERRED |
| M10 | material | B1: "rig false-positives on exactly 3 tasks"; sabotage test proves workspace import for rich **and fastapi** | The 3 requests phantoms are solid (clean assertion failures on the required node, reproduced on a CPU Kaggle kernel, log L14845-14868). "Exactly 3" is untested beyond the 18 replayed patches. `fastapi_14873` was reclassified as a warning-as-error artifact by judgement (L14995). The sabotage test touches only `rich` (`local_eval/parity_rig/_rig_import_test.py:12,28-29`, `_rig_import_test.sh:4,15`; checked by merger). Fastapi is INFERRED from layout. The phantoms were correctly removed from later headline numbers. | Both | MEASURED + INFERRED |
| M11 | material | A1 exclusion rule applied consistently? — log L15229: "`fastapi_14077` is a genuine solve but a **dead** task" | Not in the dead set under the project's own strict rule (absent from both official and local sets, settled by merger). The official grader **resolved** it (`test_outputs/fastapi_14077.log` "3 passed in 0.37s", resolved=true). The exclusion rule (L15168-15170) is correct in principle; this one prose application is wrong. | A (A cited L15152 entry; exact line is L15229) | MEASURED |
| M12 | material | A1/L15340-15345: "stable AND gold-valid = 5"; `fastapi_14786` discounted as gold-invalid | Its gold "failure" is the node cross-product bug the log already named (L14996: "my node cross-product bug"). `replay_result.json` shows 2 test files × 4 fns = 8 nodes with "no match". The official grader resolved it (M1c). It is solved in all 6 local runs **including no-prompt**. Stable-and-solvable is ≥6, not 5. A C-bucket instrument bug logged as corrected is still load-bearing in the inventory. | A (B notes 14786 as the A2 discrepancy) | MEASURED |
| M13 | minor | A2 per-repo table (log L16141-16147) as a partition; fastapi live denominator | Reproduces on the 3 cited runs (fastapi 8/4, rich 7/2). `comp_files/tasks.jsonl` is fastapi 67, rich 48, **requests 13, httpx 1**; the brief's A2 covers 115 of 129. The log table includes requests/httpx rows, so the omission is the brief's, not the log's. Fastapi "33 non-dead" vs "29 gold-valid" both appear and mean different things. Labels are used interchangeably (B). Intersecting the union with the 59 set gives fastapi 7 / rich 6, stable 3 / 2 (B). Every number moves once M1/M2 are corrected. | Both | MEASURED |
| M14 | minor | F1 report as a frozen pre-registration | Plan pre-registers 12 tasks, CONFIRM = 6 incl. `rich_3772` (HARD control) (`kb/audits/decode-sweep-plan.md:138, 143-144`; `local_eval/decode_sweep.py:81, 94`). The report on disk shows CONFIRM = 5 (L42) and never mentions rich_3772. Disagreement settled by merger: A said the removal is "not recorded anywhere". **Wrong**: the log records it as a protocol deviation at L15723-15726, and `DECODE_SWEEP_SKIP` makes it explicit (`decode_sweep.py:98-100`). The defect is the report artifact only. CONFIRM became 5 EASY tasks with no HARD control. | Both (A overstated scope) | MEASURED |
| M15 | minor | F1 "4 WIN verdicts" | Confirmed noise. Settled by merger from the JSONL: resolves are baseline {rich_4077}, freq_02 {4077, 3518}, freq_04 {2943, 3518} (**loses** 4077, A), reserve_tail {4077, 2943}, and 0 for temp_00/temp_01/pres_02/pres_04. Two "WIN"s resolve nothing. The bar's design flaw (tie on resolves + 1-call median shift = WIN) **is** stated in the log (L15768-15771: "A pre-registered bar can fire without power"). A's claim that the distinction is "not recorded anywhere a reader would find it" is wrong. The report's VERDICT line (L65) still lists 4 WIN candidates without a caveat. | Both (A overstated) | MEASURED |
| M16 | minor | G1: 44 corrected errors, 13 (30%) retrieval failures; buckets A13/B2/C16/D9/E4 — log L15518-15526 | Arithmetic consistent (sum 44; 13/44 = 29.5%). Neither reviewer found an event-level ledger. `_audit_transcript.py` exists and, per A, emits only marker counts (A: 853 user turns reproduces; 179 markers / ~147 blocks do not). The one sampled A-bucket exemplar is real (L5237, 2026-10-05, missing inline_snapshot). The C-bucket cross-product bug is "corrected" but still drives M1/M12. | Both | UNVERIFIED (the 44 and the buckets) |
| M17 | minor | Provenance hazards in result dirs | `kaggle_pkg/out_e4b/results/summary.json` and `task_results.jsonl` describe a **9-task** slice (1/9). The real record is `task_results.all.jsonl` (10/129) (merger checked). `local_eval/parity_rig/replay_gold129.json` (node mode, 39: rich 37, requests 2) sits next to the files-mode 31 with no obsolete marker (merger checked). | Both (summary.json); B (39 file) | MEASURED |
| M18 | minor | `replay_verify2.py` "mirrors swegemma's own verification rule" | Docstring L1-7 says "runs only those [nodes], failing on failed/error/skipped". L94-95 says files mode is what matches swegemma. Harness runs whole files and tolerates unrelated skips (`verification.py:619-623, 289-343`). The default mode is the unfaithful one, which produced M1(a). | A (verified by merger) | MEASURED |
| M19 | minor | §4 retraction wording "budget verified non-binding (max 22 calls, 419 s)" | Those maxima are the `m1_full129/ca5` run (merger: 22 calls / 419 s). The log scopes it "locally" (L14966). On the grader `fastapi_14978` and `fastapi_15745` died at "Agent exceeded session timeout (8.0 min)", max 730 s. The retraction (the budget is real) stands. Only the brief's unscoped "non-binding" is wrong. | A | MEASURED |
| M21 | material (added post-merge) | Implicit everywhere: "Kaggle E4B" has more than one 129-task record (`out_e4b`, `out_e4b_v3`) | **`out_e4b_v3` is a copy, not a replicate.** Its `task_results.all.jsonl` matches `out_e4b` on all 129 rows. Per-task durations are identical (median 188.84 s in both). The eval logs carry identical stream timestamps ("server up" at t=429.675387565 in both). Both `agent_ca5` bundles are byte-identical. On the full 129 with the ca5 bundle, Kaggle-side run-to-run variance is therefore **n = 1**. **Scope correction (user, 2026-11-01):** that n = 1 holds only for *this bundle on all 129*. Kaggle holds many more E4B runs. The live inventory (`kaggle_inventory/KAGGLE_INVENTORY.md`, from `kaggle kernels list --mine`) shows 118 kernels, 79 of them Gemma. The E4B kernels are: ca5-e4b-full129-eval (129 tasks), e4b-a3 and e4b-a5 (44 rich tasks each, prompts A3/A5: 2/44 and 3/44), and remap-e4b, size-e4b, v7-e4b (6-task gates: 3/6, 0/6, 2/6). Every task any Kaggle E4B kernel ever solved is inside the local 17-task E4B union. Kernel versions older than the latest cannot be pulled with the CLI, so earlier versions of these kernels are UNVERIFIED. Separately, `kaggle_pkg/out_v7/results/task_results.jsonl` (31B ca5, log L13935 "35/129") has only 9 rows and there is no `.all.jsonl`, so the 35/129 has no full per-task record on disk. The 9-row `summary.json`/`task_results.jsonl` files are explained by the notebook: `push_129_e4b/ca5-e4b-full129.ipynb` cell 4 rewrites `task_results.jsonl` per chunk and keeps the durable record in `task_results.all.jsonl`. That is benign, but a hazard for any consumer (M17). | Merger | MEASURED |
| M23 | **blocking** (added post-merge) | Policy baseline: steering `gemma-submission-protocol.md` says "v6w @ 0.15 is SACRED (live-best)", and `kb/curated/submissions.csv` is cited as its source | **Stale.** The live submission history (`kaggle competitions submissions`, saved to `kaggle_inventory/submissions_live.csv`) has **25** rows; `kb/curated/submissions.csv` has **10**. The live best is **0.20** (57760641, 2026-10-29, "ca5: pre-edit anchor-grep rule, no sub-agents, v10 config"), not v6w 0.15. 57847285 (identical-bytes resubmit of the 0.20 pack) is PENDING. The **only** E4B scored submission is 57807043 = 0.03. Scored results missing from the curated file: 0.17 ×2, 0.18 ×2, 0.13 ×3, 0.12, 0.15 (A17), 0.03 (E4B), plus 3 unscored rows (12B size ladder, budget raise, "Why not"). Every audit that read its baseline from the curated CSV used the wrong live-best. Fix: refresh `curated/submissions.csv` and the steering line from the live pull. That edit is the user's call; nothing was changed. | Merger (prompted by user) | MEASURED |
| M22 | material (added post-merge, user question) | User: "we land 17 but score 2/58; is there an undetected local-vs-board delta?" | (a) **The scored zip is the measured bundle.** `Downloads/submission (3).zip` matches `agent_ctrl_e4b` and `out_e4b/agent_ca5` by sha256 on all four files (agent.yaml BA2E26DCEEEE, eval_config 3B20D99D328D, sampling A49DBD3AAB94, system.md B9AEAA9A53CE). No bundle delta. (b) **17 is the 6-run union, not a per-run number.** One run lands 7–12 genuine (mean 9.8). Expected on 58 (×58/129): from 17/129 → 7.6 (P(≤2) = 0.013); from 10/129 → 4.5 (P = 0.163); from 9/129 genuine → 4.0 (P = 0.221). The real board gap is about 2 tasks, which is unremarkable in isolation. (c) **Local vs Kaggle on the same 129 was measured once:** Kaggle 9 genuine vs local 7–12, inside the local range. (d) The remaining unmeasurable gap is practice-129 vs hidden-58. Whether the 58 are a subset of the 129 is unproven. Kaggle-only losses (6 overflow + 2 timeout) fall on tasks E4B never solves in any run, so they do not explain the missing 2. | Merger | MEASURED (a–c); INFERRED (d) |
| M20 | minor | `SCORING_ANALYSIS.md` presented as current | Stale: "0.12 ← BEST" (L14), "leaderboard top 0.24" (L31), "THE CEILING IS 0.24" (L50), 2,497 teams vs `lb.csv` 3,871. No superseded banner. | A (merger checked L14/29/31/50) | MEASURED |
| S1 | survives | A3: denominator 58, `floor(k/58*100)/100` | Reproduced three times (A, B, merger). `local_eval/leaderboard/lb.csv`: 3,871 rows, 159 zeros, 14 distinct positive values [0.01…0.24]. Brute force N ∈ [10, 2000] × {truncate, half-up, half-even}: unique solution **(58, truncate)**. Conditional on equal-weight binary tasks, one deterministic display rule, every achievable value populated, N ≤ 2000. Strong inference, not proof. | Both + merger | MEASURED (fit); ASSUMED (scorer family) |
| S2 | survives | E1: definition rule executed repo-wide 0/7; 3/7 single-file definition greps; both solves never ran it | Reproduced by merger from `m1_refdef/agent_ctrl_e4b_def_r0/traces/*.json` → `steps[].tool_calls[].arguments`. 0 repo-wide `def`/`class` greps. Single-file definition greps in fastapi_14458, fastapi_9555, rich_3480. Solves rich_3067 and rich_4077 ran usage greps only. Tool totals get_status 8, run_command 21, read_file 28, edit_file 9, submit_patch 7 (identical to A). No surviving conclusion depends on the retracted 100% / ~25% readings. | Both + merger | MEASURED |

### Per-claim coverage, A1–G1

| claim | verdict | findings |
|---|---|---|
| A1 | **Contradicted.** 1 degenerate (`requests_6644`) is verified (`replay_empty129_files.json`: only resolved row). 59/60 is a lower bound from a stricter-than-grader rule, contradicted by the grader on 2 tasks. 34 dead = union; the official image shows 28. The exclusion rule is right in principle but misapplied to fastapi_14077. | M1, M2, M11, M12 |
| A2 | **Reproducible on its selection, not a sound partition.** Denominators are mixed and inherit M1/M2. | M13, M12 |
| A3 | **Verified (conditional).** | S1 |
| B1 | **Core verified, "exactly 3" and fastapi generalisation unverified.** | M10 |
| B2 | **Contradicted as "agree within noise."** The overflow premise is false, the reachable sets differ, and Kaggle genuine is 9. | M7 |
| C1 | **Contradicted.** An identical pair spans 5. | M3 |
| C2 | **Interpretation contradicted.** The log's own −5 and replicated arms. | M8 |
| D1 | **Counts verified; value/core claim contradicted.** 5-run core = 2; ca5_v2 ties no-prompt; rich_2725 misdescribed; n=1. | M5 |
| E1 | **Verified.** | S2 |
| F1 | **"Wins are noise" verified; experiment integrity defective** (scorer mismatch, no reps, dirty clone, report omits deviation). The bar is badly designed. The log says so (L15768); the report does not. | M6, M14, M15 |
| G1 | **UNVERIFIED.** | M16 |

### Dropped / downgraded (and why)

- **B, C1 note "third run changes sampler settings, not an identical replicate."** The brief already discloses the faithful run as sampler-matched (§3 C1). Restating a disclosed fact is not a finding. Dropped as a standalone row; the comparability point is folded into M3.
- **A, numbers "gold validates 31/129, fastapi 0" (L15242 entry, actually L15263) vs 60.** The log self-corrects at L15331-15333 ("Local replay alone reported fastapi 0/67 … Re-running gold on the Kaggle CPU image gives 29/67"). Dropped as a finding (self-correction). Kept in §3 marked superseded.
- **A, F8 "removal of rich_3772 not recorded anywhere"** and **A, F10 "bar-design distinction not recorded anywhere."** Overturned by log L15723-15726 and L15768-15771. Downgraded to report-artifact defects (M14, M15).
- **A, F12 as a contradiction of the §4 retraction.** The retraction (budget is real and read by the grader) is right, and the log scopes "non-binding" to local (L14966). Kept only as a minor wording issue in the brief (M19).
- **A, F1 "five same-config runs."** Partly a §5 trap 1/5 hazard: the five differ in concurrency, cap flags and declared model string. Corrected in M3; the conclusion (C1 contradicted) survives on the ca5 pair alone.
- **B, A1 "a source patch could vendor/provide the missing module."** No test, rule check or artifact behind it. Kept as an ASSUMED possibility in §5 only, not as a finding.

---

## 2. The three claims most likely wrong, and the test that settles each

1. **A1 — "59 truly solvable / 34 dead"** (both reviewers' #1 or #2). The grader already contradicts it on fastapi_14786 and rich_3894 (M1c).
   Settling test (CPU only, free): re-run `replay_verify2.py` in files mode on all 129 in the official image (the same CPU Kaggle kernel path that produced `out_gold_fa`), with `resolved` computed by the harness rule: exit 0, no failures/errors, required nodes passed and not skipped (`verification.py:289-343`). Run the empty patch in the same pass. Pre-register: if ≥2 additional tasks become gold-valid, retire 60/59/34/95 and recompute every rate. Expected under A's evidence: ≥8 rich tasks re-homed plus some of the 24 multi-file fastapi. Separately, re-derive "dead" from the official image only: 28 unless the 6 local-only tasks show the strict error on the official image.

2. **C1 — "noise is ±2 per 129"** (both reviewers' top three). Already falsified on disk by ca5 vs ca5_v2 (15 vs 10).
   Settling test: no new run needed to retract it. To estimate it, run ≥4 more exact replicas (same bundle hash, concurrency, caps, served GGUF recorded via `/props` into the run dir). Pre-register the estimator (run-level SD with a 95% CI). Until then, report "two identical pairs differed by 2 and 5."

3. **D1 — "prompt worth +2 to +4 and stabilises a 3-task core"** (A's #3; B rates it material; chosen over B's F1 because F1's headline, "the wins are noise", is right while D1's headline is not supported).
   Settling test: 3 more replicates of `m1_noprompt129` with the same harness settings as the capped runs and a recorded GGUF. Pre-register: the core claim survives only if fastapi_14463, fastapi_14616 and rich_3905 are solved in ≥4/4 prompt runs **and** 0/4 no-prompt runs. The effect claim survives only if the 4-vs-4 genuine distributions separate (exact permutation p < 0.05). On present data (core = 2, ca5_v2 = no-prompt = 7) the honest verdict is "no measured effect."

(M4, earlier listed here as the runner-up, is resolved: E4B on `:8081` for the 129-task runs, 12B on a separate vLLM `:8082`. See the M4 row.)

---

## 3. Numbers that appear in more than one place with different values

| quantity | occurrence 1 | occurrence 2 (+3) | settled |
|---|---|---|---|
| gold-valid | **60** (log L15329, L15397) | **31/129, fastapi 0** (log L15263; superseded by L15331-15333); **39** (`replay_gold129.json`, node mode: rich 37, requests 2); ≥68 by harness rule (A, INFERRED) | 60 is the logged value; it is a lower bound (M1) |
| requests gold-valid | **1** (L15327, L15397) | **0** (L16145) | 1 in `replay_gold129_files.json`, which is `requests_6644`, the degenerate task, so "0 non-degenerate" is also true. Labels differ. |
| dead tasks | **34** (L15152 heading, L16143) | **28** official / **32** local (same entry's table, L15160-15161); **49** loose (L15170); **18** (L5237) | merger: 28 / 32 / union 34 / overlap 26 |
| missing-module counts | `inline_snapshot` 48, `dirty_equals` 32 (L15160) | per-task 21 / 8 official, 25 / 9 local (A) | A: the 48/32 are line occurrences beside task counts; not re-derived by merger |
| fastapi denominator | **33** non-dead (67−34; L16152-16153) | **29** gold-valid (L15326, L16143) | different quantities used interchangeably (M13) |
| genuine union / stable | **15 / 6** (L16147) | **13 / 5** intersected with the 59 set (L15340) | definitions unnamed (B) |
| stable + solvable | **5** (L15340, L16104) | **≥6** with fastapi_14786 credited (M12) | merger: grader resolved 14786 |
| capped r0 genuine | **7-9** (L15007) | **9** (L15049, L15099, L16089) | 9 = recorded − 3 phantoms; 7 = replay-confirmed only |
| ca5 family recorded | **15, 10** (`m1_full129/ca5`, `ca5_v2`; L14812-14813, L15008-15009) | **12, 14, 14** (capped r0, r1, faithful) | the 15/10 pair is identical-config (M3); brief C1 omits the 10 |
| Kaggle E4B solves | **10** (brief B2; L14234-14238) | **9** genuine after `requests_6644` (L15389) | merger: 6644 resolved at line 96 |
| Kaggle E4B summary | **1/9** (`out_e4b/results/summary.json`) | **10/129** (`task_results.all.jsonl`) | subset-overwritten summary (M17) |
| local overflows | **0** ("never hits overflow", L14814) | ca5 2, ca5_v2 3, cap r0 2, cap r1 4, faithful 2, no-prompt 3 | merger, raw `task_results.jsonl` |
| budget max observed | **22 calls / 419 s** (L14966, brief §4) | cap r0 20 / 404 s (L14982); Kaggle 24 / 730 s with 2 timeouts | all three measured; differ by run |
| noise band | **±2/129** (L15067, L15105) | **±4/37** (L14874-14881, B); identical-pair spread 5 (M3) | neither is an SD estimate |
| "one failing test away" | **6** (L15209, L15370, L15433) | **14** (L16164) | definitions not reconciled; not re-derived by merger |
| decode CONFIRM / cohort | **6 incl. rich_3772**, 12 tasks, 96 cells (plan L143-144; `decode_sweep.py:94`) | **5**, 11 tasks, 88 cells (report L42; log L15720-15726) | deviation in log, not in report (M14) |
| decode scorer | **rp-4** (report L1; baseline rows) | **rp-5** (report L8; arm rows) | M6 |
| log size / index | ~16,200 lines (brief) | 15,578 lines; 396 units / 1,180 claims (log, A) vs 406 / 1,206 live (A) | A only; index is live, log grew. Not re-derived by merger |
| teams on board | **3,871** (`lb.csv`; merger counted 3,871 rows) | **2,497** (`SCORING_ANALYSIS.md`) | M20 |
| best score | 0.20 main / 0.03 E4B (brief §1) | 0.12 best, 0.24 ceiling (`SCORING_ANALYSIS.md` L14, L31) | stale doc |

---

## 4. What is actually established (conservative)

1. **Public score = `floor(k/58*100)/100`** is the unique fit among N ≤ 2000 and three rounding rules to 3,712 non-zero public scores. 0.03 = 2/58. MEASURED fit; conditional on equal-weight binary tasks.
2. **At least 28 fastapi tasks cannot collect on the official image** (missing `inline_snapshot` / `dirty_equals` / `scripts`). MEASURED on official `test_outputs`. 34 is a local∪official union.
3. **At least 59 tasks are gold-valid and non-degenerate under a replay rule stricter than the grader.** It is a floor. The grader resolved two tasks the inventory excludes. MEASURED.
4. **Exactly one task (`requests_6644`) resolves with an empty patch.** The official E4B run counted it, so that run's genuine total is 9/129. MEASURED.
5. **The three local `requests` solves are false positives** (assertion failures on the required node, reproduced on a CPU Kaggle kernel). The mechanism is probable. It was tested on rich only. MEASURED / INFERRED.
6. **The "grep the definition" rule was never executed as written** (0/7 repo-wide, from tool-call arguments), and both solves in that arm skipped it. A prose rule can be fully ignored. MEASURED.
7. **Identical-config 129-task runs disagree on 5-8 tasks** and their totals differ by 2-5. A single run cannot resolve a 2-task effect. Whether replication on a fixed cohort can is reported by A (n=29) but not re-derived here. MEASURED (pairs).
8. **The decode sweep found no decode gain.** One run per cell, mixed scorer versions; the four WINs are one task or one-call timing. MEASURED.
9. **Caps are not binding locally** (max ≤ 24 calls, ≤ 454 s). On the grader the 8-min wall killed 2 tasks and context overflow 6 more. MEASURED.

Not established: the size of the solvable set; a 34-task impossible set; any numeric noise floor; local-to-Kaggle effect transfer; a per-run record of the served model (M4 rests on scripts + user account); a measurable prompt effect; the 13/44 retrieval-error share.

---

## 5. What to do next (1 scored slot/day, no GPU for the local rig, E4B 0.03 → ≥ 0.10)

Ranked by information per scarce resource. Items 1, 2 and 5 need no GPU and no scored slot.

1. **Fix the measuring stick first (CPU, free).** Re-run gold and empty replays over all 129 on the official image with the harness rule (§2 test 1). Every target ("59 solvable", "95 live", "5 stable", "+8 needed") comes from the broken version. Both reviewers rank this first. Also check whether a legal source-side shim can make any collection-blocked task collect (B's idea, currently ASSUMED with no evidence either way).
2. **Record provenance in every run** (served GGUF via `/props`, bundle hash, concurrency, scorer version), and fix the stale 31B label in `agent_ctrl_v5/agent.yaml`. Mark `summary.json` (1/9), `replay_gold129.json`, `SCORING_ANALYSIS.md` and the decode-sweep report (rp-4/rp-5 mismatch, missing rich_3772 deviation, uncaveated WIN line) as superseded or annotated. These are writes to project files, so they are the user's call; nothing was edited here.
3. **Re-examine "resubmit the same artifact" before spending slots on it (M9).** The hidden 58 tasks are fixed, so resubmission only resamples agent behaviour on them, and the observed centre is 2/58, not 4.5. If you do resubmit an unchanged artifact, pre-register it as a replication measurement (B). It is not a change, so the free-gate rule for changes does not obviously apply, but confirm that reading of `gemma-submission-protocol.md` before using the slot. Do not expect it to reach 6/58.
4. **Any content change goes through the free rich gate first** with a pre-registered task-conversion bar (protocol). The best mechanism lead is structural, not prose: E1 shows prose rules are ignored, so enforce definition-site localisation (or another precondition) in the harness/tool layer. Target the rich near-miss set and the 8 skip-only rich tasks once item 1 confirms they are grader-valid. Require a per-task flip in ≥3 of 4 replicates, not a single flip.
5. **Stop single-run arms.** An arm that cannot be replicated (A suggests about 8 reps on a fixed cohort; B suggests ≥20 runs for a run-level SD) cannot be interpreted. Report every past n ≤ 3 arm as "unresolved", not "null".
6. **Keep the current prompt unchanged.** D1 does not prove it helps, but nothing favours removing it. A no-prompt replicate pair is the cheap way to settle D1 when GPU time returns.

---

Scratch files under `%TEMP%` (`orm_*`) were removed after writing this report. No project file outside
`kb/audits/outside-review/` was modified; no Kaggle CLI, git, or KB build was run.

---

## 6. Thesis and areas of improvement (added 2026-11-01 at user request)

Status: **hypotheses, not recommendations.** Per `gemma-submission-protocol.md`, each lever needs a `gemma-audit`
and then a free gate before any scored slot. Numbers are MEASURED from the six E4B 129-task records (ca5, ca5_v2,
capped r0/r1, faithful, Kaggle E4B) and the 31B v10/A3-hard Kaggle run. The 31B run was parsed from the
`resolved=` lines in `local_eval/pull_31ba3hard_out/gemma-sibling-conform-31b-a3-hard.log`: 35 recorded,
including `requests_6644`, so 34 genuine, which matches log L12572. Phantoms `requests_7309/7315/7427` and
`requests_6644` are removed everywhere.

### The measured picture

| measure | value |
|---|---|
| E4B genuine solves per run | 12, 7, 9, 11, 11, Kaggle 9 → **mean 9.8 / 129** |
| E4B union across the 6 runs | **17 / 129** |
| E4B solved in all 6 runs | 5 (fastapi_14301, 14463, 14786, rich_3006, 3905) |
| E4B solved in 1–5 of 6 | **12** (rich_3454 5/6; fastapi_14616 4/6; fastapi_9425, rich_3067, fastapi_14077 3/6; fastapi_14851, 9753, rich_3518, 3894 2/6; rich_3882, fastapi_14873, rich_4077 1/6) |
| 31B v10 (1 Kaggle run) genuine | **34 / 129** |
| E4B union ∩ 31B single run | **17 of 17**. Every task E4B has ever solved, 31B solved in one run |
| solved by 31B, never by E4B | **17** |

### Thesis: E4B has two separable gaps, and both are measured

1. **Reliability gap (in E4B's own reach).** E4B has passed 17 tasks, but one run lands 9.8 of them (58%).
   Scaled to the 58-task board (×58/129, ASSUMED representative), the per-run mean is about 4.4/58 and the union
   about 7.6/58 = 0.13. **A run that reliably converted its own reachable set would clear 0.10 with no new
   capability.**
2. **Capability gap (shown reachable by a sibling model).** 31B, with the same harness and a related prompt
   family, solves 17 more tasks in a single run. Its reach strictly contains E4B's. The gap is therefore not
   "the tasks are impossible". It is "E4B does not find the fix that a bigger Gemma finds under the same tools
   and budget". The 31B fix-shape breakdown (log L12594-12598) says where. Small, contract-shaped fixes convert
   (string/message 3/3, none-guard 1/1, operator 1/1). Additive or structural ones mostly do not (add_raise 0/5,
   add_import 0/3).

Why the past levers failed fits this picture. Prompt rules are skipped (E1: 0/7), decode knobs move nothing
(F1), and the prompt's whole effect is unresolvable (D1). Every null lever tried to change what the model
*thinks* on its first attempt. None changed what the run *does after* a wrong first attempt (gap 1), or what the
model *knows* (gap 2). The concrete mechanism evidence for gap 1: `rich_3518` produced a byte-identical gold patch
in 2 of 3 runs and a wrong-site edit in the third (log L15750-15755).

Caveat (M9): the board's 2/58 sits below the 4.4 scaled mean, so the hidden 58 may be harder than the practice
mix. The thesis then predicts a gain over 2/58, not a guaranteed 6/58.

### Areas of improvement (ranked by evidence behind them)

1. **Close gap 1 with in-run self-verification and retry (structural). HYPOTHESIS.** Before `submit_patch`, the run
   must reproduce the issue or run the existing tests for the edited module. On failure it reverts and retries with
   the remaining budget. There is room in the budget: locally max 20–24 of 28 calls and ≤ 454 s of 480. Kaggle
   E4B is 2–3× slower and 2 runs hit the 8-min wall, so retry must be budget-aware. Enforce it in the tool layer
   (a `submit_patch` precondition), not prose (E1). Bar: on the 12 flaky tasks, ≥3 move from < 50% to ≥ 75% solve
   rate over 4 replicates, with no loss on the 5 stable tasks.
2. **Close gap 1 on wrong-site edits with localisation enforcement. HYPOTHESIS.** The edit tool warns or refuses
   unless a repo-wide definition lookup for the edited symbol happened earlier in the run. Judge it on the flaky
   rich tasks (3518, 3894, 3067, 3454, 4077, 3882).
3. **Close gap 2 with a LoRA adapter distilled from 31B trajectories. HYPOTHESIS, needs GPU.** LoRA is the only
   allowed post-training. Per the staff reply in the user's intel, adapters are applied in the scored vLLM 0.19.1
   build. The sample adapter touches layer 0 only, so it must target all layers. The 31B v10 run already holds
   34 successful tool-call trajectories on this exact harness. Of those, 17 cover tasks E4B never solves, and they
   are the natural training set. Requirements: train on agent trajectories only, never gold `patch`/`test_patch`
   text (`build_kb.py leakcheck --scope config`), and judge the result on a held-out task split so it does not
   memorise the practice set. Rules compliance of distilling from own 31B runs is **UNVERIFIED**. Check the
   competition rules before spending GPU.
4. **Stop losing runs to context/time on the grader. MEASURED loss, small INFERRED gain.** Kaggle E4B lost 8/129
   runs to 6 overflows and 2 timeouts (`task_results.all.jsonl` lines 10, 19, 34, 56, 72, 77, 86, 93). Capping
   `read_file` / `run_command` output in the tool layer is a guardrail. The expected gain is under 1 task on 58,
   because those tasks are mostly large ones neither model solves reliably.
5. **Fix the measuring stick (a precondition for judging 1–3). MEASURED need.** Run the §2 test 1 harness-rule
   gold replay. Record the served model per run (M4). Replicate ≥ 4× (M3). A single run cannot see a 3-of-12
   conversion.

**What would falsify the thesis.** Suppose 4 replicates of item 1 or 2 leave the flaky-12 solve rate unchanged,
while compliance (read from `tool_calls[].arguments`) is high. Then gap 1 is not fixable inside an 8-minute
budget, and gap 2 (item 3) is the only lever left. If an all-layer adapter trained on 31B trajectories moves no
held-out task, the remaining explanation is raw model capacity at 4B.

---

## 7. Kaggle replication run (launched 2026-11-01, PENDING)

Pre-registered in `GEMMA_EXPERIMENT_LOG.md` ("PRE-REGISTERED: Kaggle E4B ca5 REPLICATION"). It re-pushes kernel
`comfyops/ca5-e4b-full129-eval` (`kaggle_pkg/push_129_e4b`) with no change, so the bundle is identical to the
scored 0.03 zip. Free kernel; the scored slot is not used. It settles M21 (Kaggle n = 1) and the user's
local-vs-board question (M22).

- **Void unless:** prompt sha b08b32a2438d, server at max_model_len 32768 / gpu 0.85, caps 28/8/120,
  todo 129/129 resumed 0, 129 rows.
- **KAGGLE == LOCAL:** genuine 7–12 AND overlap with run 1's 9 genuine ≥ 6.
- **KAGGLE DELTA:** genuine ≤ 6 OR overlap ≤ 5. Then run a per-task trace diff on the discordant tasks.
- Also report the discordant count vs run 1, and overflow/timeout vs 6 + 2.

**Result (MEASURED, `kaggle_pkg/out_e4b_r2/results/task_results.all.jsonl`): KAGGLE == LOCAL — PASS.** The run is
valid (all preconditions held) and independent (0/129 durations match run 1).

- **Solves:** 9 recorded / **8 genuine**. **7** overlap with run 1's 9.
- **Agreement with run 1:** discordant on 3 of 129. Run-1-only: fastapi_14077, rich_3894. Run-2-only: fastapi_9753.
- **Errors:** 7 overflows + 6 timeouts (run 1: 6 + 2), on a mostly different set of tasks. fastapi_14873 timed out.
- **Union:** no solve outside the 17-task E4B union.

This settles M21: Kaggle run-to-run for this bundle is now n = 2, 9 vs 8 genuine. It also settles M22: there is no
undetected Kaggle-vs-local delta, so the gap to 2/58 lives in the hidden set and per-run churn.

Chunk 1 of the new run logged `cumulative: 0/20` plus an `ensurepip unavailable` warning. Run 1's log shows the same:
chunk 1 = 0/20, the same warning, then 3/40 → 4/60 → 7/80 → 8/100 → 9/120 → 10/129. That is not an early
failure signal.

Full kernel intel archive: `Gemma/kaggle_archive/` (README, INDEX.md for 79 kernels, LOCAL_PULLS.md for 78
older local runs, live submission history).
