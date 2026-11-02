# OUTSIDE REVIEW — REVIEWER A

Independent, adversarial, read-only audit of claims A1–G1 in
`Gemma/AUDIT_PROMPT_OUTSIDE_REVIEW.md`. Everything below was re-derived from raw artifacts
(run dirs' `task_results.jsonl`, `test_outputs/*.log`, `traces/*.json` via
`steps[].tool_calls[].arguments`, the replay JSONs, the harness source, `lb.csv`) and from the
log located through `kb/kblib/logdb.py`, never from a KB-derived summary. No project file was
modified; scratch under `%TEMP%` was removed.

Tags: **MEASURED** = I recomputed it from a raw artifact. **INFERRED** = follows from two or more
measured facts. **ASSUMED / UNVERIFIED** = I could not settle it.

Two environment notes that bound this review: (1) `Gemma/kb/` was being rebuilt during the audit
(`kb/.build.lock` present, `runs.jsonl` 16.3 MB on disk vs the brief's 13.7 MB / 4,486 records),
so no claim below rests on `runs.jsonl`, `near_miss.jsonl` or `KB_SUMMARY.md`; `logdb.sqlite`
(mtime 2026-11-01 14:38) was used only as a line index into the markdown log and was internally
consistent with it (406 `## ` units in the file, 406 rows in `units`). (2) `kaggle_pkg/out_e4b/results/summary.json`
and `task_results.jsonl` describe a 9-task slice; the real 129-task Kaggle record is
`task_results.all.jsonl` — anyone reading the first two files will get 1/9, not 10/129.

---

## 1. FINDINGS TABLE (ordered by severity)

| # | sev | claim | what the evidence supports | basis |
|---|---|---|---|---|
| F1 | **blocking** | C1: "run-to-run noise is ±2 tasks per 129", evidence 12/14 + a third at 14 | There are **five** completed same-config 129-task runs, not three. Genuine (phantoms removed) = **7, 9, 11, 11, 12**; sd 2.0, **range 5**. The 7 comes from `m1_full129/ca5_v2` (10 recorded) and the 12 from `m1_full129/ca5` (15 recorded) — identical docker argv, identical `--submission-dir /rig/agent_ctrl_v5` (`_m1_full129_ca5.py:48-57` vs `_m1_full129_ca5_v2.py:48-57`). The project knows both numbers: its own table at log **L14978** lists 12 / 15 / 10 → 7-9 / 12 / 7. A "±2 noise floor" is 1 sd stated as a bound; the 95% band is ≈±4 and the observed spread is 5. | MEASURED |
| F2 | **blocking** | A1/A2: "60 tasks pass with the gold patch; 59 truly solvable; fastapi 29 gold-valid; rich 30" | The 60 is the sum of **two incompatible replay rules**, and both undercount. (a) `out_gold_fa/replay_result.json` ran in **node mode**: `nodes = [f'{f}::{fn}' for f in files for fn in fns]` (`replay_verify2.py:96-99`) is a **cross product**, so any task whose `test_patch` touches >1 test file demands node ids that do not exist and pytest returns `ERROR: not found`. **0 of the 24 multi-file fastapi tasks are recorded gold-valid — 0/24, by construction.** (b) `replay_gold129_files.json` (rich/requests) ran in files mode but scores `skipped` as failure (`replay_verify2.py:111-113`), while the real harness takes `resolved = test_res.exit_code == 0` plus a JUnit check that tolerates unrelated skips (`harness_src/x/swegemma/harness/verification.py:289-300, 622-628`). **13 rich tasks are excluded on skips alone; 8 of them pass their required nodes individually**, so they would resolve on the grader. Floor correction: gold-valid ≥ **68**, truly solvable ≥ **67**, not 59 — and 24 fastapi + 12 requests tasks are *unjudged*, not unsolvable. | MEASURED (a,b); INFERRED (the 8) |
| F3 | **blocking** | A1: "34 tasks are dead because the **official** eval image cannot collect their tests… all 34 are fastapi" | 34 is the **union of the official image and the local rig** (`_live_dead_split.py:40-45`: `dead = kb \| lb`). Recomputed with the project's own strict rule: official image **28**, local rig **32**, union **34**, all fastapi. The 6 local-only tasks are not shown dead on the grader: `fastapi_11355, 14099, 14455, 14962` have official logs whose collection errors have other causes (14962 = `NameError`), and `fastapi_14356` / `15745` have **no official log at all** (they died on a context overflow and an 8-min timeout respectively, so their tests never ran). Defensible dead count on the grader = **28**; live = 101, not 95. Every rate quoted "/95" is computed on a denominator 6 tasks too small. | MEASURED |
| F4 | **blocking** | D1: prompt worth "+2 to +4"; "3 tasks solved in all three ca5 runs and never by the empty prompt" | Reproduces **only on the 3 runs selected**. Across all five same-config runs the always-solved set is **2** tasks (`fastapi_14463`, `rich_3905`); `fastapi_14616` is not solved by `ca5` or `ca5_v2`. The empty prompt's **7 genuine equals `ca5_v2`'s 7 genuine** — the whole claimed effect is inside the prompt arm's own range. McNemar across all five pairs is p = **0.180–1.000** (not 0.29–0.75), and `ca5_v2` vs no-prompt is an exact 3/3 tie. The no-prompt arm also uniquely solves `rich_2725`, which **no** prompt run ever solves — a reverse-direction discordance the claim omits. The no-prompt arm has n=1. | MEASURED |
| F5 | **material** | A1 / L15314 / L15382: "stable AND gold-valid = 5", therefore "we need +8"; `fastapi_14786` discounted as gold-invalid | `fastapi_14786`'s gold replay failure is the **cross-product bug the project already identified** (log L14978: "fastapi_14786 — no counts — artifact — my node cross-product bug"): 2 test files × 4 fns = 8 demanded node ids. The official Kaggle run resolved it: `test_outputs/fastapi_14786.log` = "9 passed in 0.45s", `task_results.all.jsonl` `resolved=true, test_exit_code=0`. So the stable-and-solvable count is **6, not 5**, and the gap under the project's own Model A falls from "+1.1" to ≈"+0.1". A C-bucket instrument bug logged as *corrected* is still load-bearing in the headline inventory. | MEASURED |
| F6 | **material** | L15152: "`fastapi_14077` is a genuine solve but a **dead** task, so it can never count on the real grader" | 14077 is **not in the dead set** under the project's own rule (recomputed: absent from both the official and local blocked sets), and the official run **resolved** it (`test_outputs/fastapi_14077.log` = "3 passed"). Its local r0 collection error is `invalid syntax` from the agent's own patch — which the project's strict definition explicitly excludes from "dead" (`_live_dead_split.py:28-31`). The same entry counts 14077 inside the 15-task union over the 95 "live" denominator while calling it dead: a double standard in one entry. | MEASURED |
| F7 | **material** | C2: "every arm landed within ±1–3 tasks… all measured below the noise floor, so the nulls are uninformative" | False for at least two arms on the **identical** 7-task rich cohort (`rich_3006, 3454, 3518, 3777, 3882, 3905, 4077`, verified identical across all 15 arms): `router_v2` n=3 = {1,1,2} (mean 1.33) vs `ca5` n=29 = {2…6} (mean 3.55, min 2) → P(three independent ca5 draws all ≤2) ≈ 3×10⁻⁴; `off12` n=13 = {4…5} (mean 4.77) vs ca5 → P ≈ 1.5×10⁻⁴. Even `ca5` (3.55, n=29) vs `ctrl` (2.91, n=11) is Welch p ≈ 0.02. The instrument resolves sub-1-task effects **when replicated**; what was missing was replication, not resolution. "All nulls are uninformative" lets a real negative result (multi-agent routing hurts) off the hook. | MEASURED |
| F8 | **material** | F1: the sweep's pre-registration is "frozen (2026-10-15)" and the reported task set is the registered one | `kb/audits/decode-sweep-plan.md:138,143-144` pre-registers **CONFIRM = {4076, 3469, 3278, 3470, 3518, rich_3772}** (6 tasks) and `rich_3772` as one of only **two HARD difficulty controls**. The frozen report on disk lists 11 tasks, CONFIRM = 5, names only `rich_3930`/`rich_4070` under "Excluded up front", and **does not record the removal of `rich_3772` anywhere**. Both files carry mtime 2026-11-01 12:04 (report and results written together). Effect: CONFIRM became 5 EASY tasks with zero difficulty coverage, and the deviation is invisible to a reader of the report. | MEASURED |
| F9 | **material** | F1: the eight arms are comparable against the baseline floor | The **baseline arm was scored by a different engine version than every other arm**: in the 88 rows, `scorer_engine` = `rp-4` for all 11 baseline rows and `rp-5` for all 77 arm rows. The report header claims "Scorer: FIXED … rp-5" while the title says "rp-4". Every "WIN" is arm(rp-5) vs floor(rp-4). | MEASURED |
| F10 | **material** | F1: "4 WIN verdicts" | Confirmed as noise and worse than the brief states. Each (arm, task) cell is **one run** — 88 rows = 11 tasks × 8 arms, **no replicates**. `temp_00` and `pres_02` resolve **0 of 11 tasks** (baseline resolves 1) and are declared WIN purely on a 1-call median `first_edit_at` shift over 5 single runs. `freq_04` gains `rich_3518` but **loses** the baseline's `rich_4077`: the arms are not supersets. The report's VERDICT section as it stands on disk still reads "WIN candidate(s): temp_00, freq_02, freq_04, pres_02" with no noise caveat. The brief's framing ("the bar is the finding") is right; the artifact does not say so. | MEASURED |
| F11 | **material** | B2: "the local rig never produced a context-overflow or a wall-clock death" | Local r0 has **2 context-window errors** (`requests_7328`, request 31,484 tokens; `fastapi_14266`, 30,376 tokens — consistent with the 30,208 per-slot figure), vs Kaggle's 6. The wall-clock half is correct (local max 404 s < 480 s cap; Kaggle max 730 s, 2 timeout deaths). The error profiles differ in *degree*, not in kind — but the asymmetry is load-bearing in the other direction: the 2 Kaggle timeouts and 6 overflows remove 8 tasks from Kaggle's reachable set, and 2 of them (`fastapi_14356`, `15745`) are exactly the tasks counted as "dead for everyone" in F3. | MEASURED |
| F12 | **material** | §4 retraction: the stated budget was "verified non-binding (max 22 calls, max 419 s)" | Non-binding **locally** only. On the grader `fastapi_14978` and `fastapi_15745` died with "Agent exceeded session timeout (8.0 min)" and max observed duration is **730 s**. A retraction scoped to the local rig is being carried as a general fact. | MEASURED |
| F13 | **material** | B2/A1: "Kaggle E4B 10/129 with zero provable false positives" | One of the 10 is `requests_6644`, the single task that resolves with an **empty** patch (`replay_empty129_files.json`: exactly 1 `resolved_here`) — the project's own L15382 calls it "a freebie". Kaggle genuine is **9**, not 10. The comparison that produces "the rigs agree" also pairs Kaggle's 10 against the **best** of two identical local runs (ca5 = 12); against `ca5_v2` the same comparison is 7 vs 10. | MEASURED |
| F14 | **minor-material** | A2: per-repo table "fastapi 67 / rich 48" | `comp_files/tasks.jsonl` is fastapi 67, **rich 48, requests 13, httpx 1**. A2 as written accounts for 115 of 129 tasks. `requests` gold-validity (1/13) was measured in whole-file mode in the environment the project itself declares defective for `requests` (B1): the 12 failures show 185–197 collection **errors**, so they are **unjudged**, not unsolvable. They nonetheless sit in the "70 unsolvable / unmeasurable" bucket. | MEASURED |
| F15 | **minor-material** | B1: "the rig false-positives on **exactly** 3 tasks", mechanism proven | The 3 `requests` false positives are solid: the replay fails on the **required node** with plain assertion failures, confirmed on a CPU Kaggle kernel with identical per-task counts (L14827). "Exactly 3" is not established: only the 8 local-only solves plus the 10 Kaggle solves were replayed (18 patch-verdicts of 129×5), and `fastapi_14873` *did* fail replay and was reclassified as a warning-as-error artifact by judgement, not by a test. The sabotage test (`_rig_import_test.sh`, lines C/D) was executed on **`rich` only** (`rich/__init__.py`, task `rich_3006`); the extension to `fastapi` is INFERRED from package layout, not measured. The 3 phantoms *were* correctly removed from the later headline numbers. | MEASURED + INFERRED |
| F16 | **minor** | `replay_verify2.py` documents itself as mirroring swegemma | Its docstring ("runs only those [extracted nodes]") and its in-body comment (`REPLAY_MODE == 'files'` → "Match swegemma: run the WHOLE test files, not extracted nodes") contradict each other. The harness truth is files mode (`verification.py:619-628`: `pytest_targets = target_test_files`). The file's own default mode is the unfaithful one, which is how F2(a) happened. | MEASURED |
| F17 | **minor** | G1: "44 distinct corrected errors, 13 (30%) retrieval failures", buckets A13/B2/C16/D9/E4 | Arithmetic is consistent (13+2+16+9+4 = 44; 13/44 = 29.5%). **The classification is not reproducible and no per-event list exists anywhere in the repo** (no `A_RETRIEVAL` string outside the log entry at L15518). `_audit_transcript.py` only prints regex marker counts and user turns; it does not emit 44 events or any bucket. Of the stated pipeline, "853 user turns" reproduces exactly; "179 raw retraction markers" and "~147 assistant blocks" do **not** (the script's patterns give 811 total / 205 retraction-like markers over 3,717 assistant blocks). The A-bucket exemplar is real and verifiable: L5237, 2026-10-05, "18 fastapi tasks may be UNSCORABLE". Verdict: **UNVERIFIED**, with one adverse structural observation — the C-bucket "cross-product" bug is counted as corrected while still driving the A1/A2/F5 numbers. | MEASURED (what exists) / UNVERIFIED (the 44) |
| F18 | **minor** | `SCORING_ANALYSIS.md` presented as a current project document | Stale and contradicts current facts: "best 0.12", "ceiling 0.24", "rank 1050 / 2497", "zero fastapi has ever resolved" (overturned at L12572), "our 6-task gate". `lb.csv` has 3,871 teams, not 2,497. It carries no superseded banner. | MEASURED |
| F19 | **survives** | A3: public denominator 58, score = `floor(k/58*100)/100` | Independently reproduced. `local_eval/leaderboard/lb.csv`: 3,871 teams, 3,712 scored (159 at 0.00), 14 distinct non-zero values with counts 76/136/154/152/226/265/319/397/547/649/534/206/47/4 — matching L12905 exactly. Brute force over N ∈ [10, 2000] × {truncate, half-up, half-even} requiring the achievable set in [0.01, 0.24] to equal the observed 14: **unique solution (58, truncate)**. Residual assumptions, which the log states: equal per-task credit, every achievable value populated by ≥1 of 3,712 teams, N ≤ 2000. The "58 + 71 = 129" subset reading remains labelled strong-but-unproven, correctly. | MEASURED |
| F20 | **survives** | E1: the definition-grep rule executed repo-wide 0/7; 3/7 ran a single-file definition grep; both solves came from runs that never ran the rule | Verified from `steps[].tool_calls[].arguments` in `m1_refdef/agent_ctrl_e4b_def_r0/traces/*.json` (21 `run_command` calls total). The mandated form is `grep -rn 'def <symbol>' .` (prompt line 40 of `agent_ctrl_e4b_def/prompts/system.md`; the only diff vs `agent_ctrl_e4b`). **0** calls use a repo root with `def`/`class`. Single-file definition greps: `fastapi_14458` (step 5), `fastapi_9555` (step 4), `rich_3480` (steps 6/9/11/13/15) = **3**. Both solves (`rich_3067` step 2/4, `rich_4077` step 3/4) ran usage greps only. No alternative definition-search tool was used (tool mix: get_status 8, run_command 21, read_file 28, edit_file 9, submit_patch 7 — zero `search_similar_code`/`get_code_neighbors`). No surviving conclusion in the audited entries depends on the retracted "100% compliant" or "~25% compliant" readings. | MEASURED |
| F21 | **new / unresolved** | all cross-arm local comparisons | `agent_ctrl_12b` differs from `agent_ctrl_e4b` in **one string** — `model: gemma-4-12b-…` vs `gemma-4-e4b-…`; prompts, sampling and eval_config are byte-identical (sha256 match). Yet arm `off12` (= `agent_ctrl_12b`) scores 4.77/7 (n=13) vs `ca5` 3.55/7 (n=29), p ≈ 10⁻⁴. Either the model declaration **is** honoured — in which case "all local runs are E4B" (§4) is false for this arm and cross-arm comparisons are confounded by whichever GGUF was loaded — or it is ignored, in which case two sets of replications of the *identical* config differ by 1.2 tasks and the **between-batch** variance dwarfs the within-batch variance the ±2 model is built on. The server logs on disk (`llmsrv*_err.log`, `ls3/ls4_err.log`) are all from 2026-10-13/14 and name no GGUF, so I cannot settle which. **UNVERIFIED — and it is a blocking-level risk to every local A/B.** | MEASURED (the gap) / UNVERIFIED (the cause) |

### Per-claim verdicts (coverage of A1–G1)

| claim | verdict |
|---|---|
| **A1** | **Contradicted in its numbers.** "1 degenerate (`requests_6644`)" ✓ MEASURED. "60 gold-valid / 59 solvable" = mixed-rule undercount (F2); floor is ≥68 / ≥67. "34 dead on the official image" = 28 on the official image, 34 only as a local∪official union (F3). "Dead" as a *classification* is right in principle (the exclusion rule in `_live_dead_split.py:28-31` is correct and matches the strict/loose 34-vs-49 note at L15152), but it was **not applied consistently**: `fastapi_14077` is called dead in prose while absent from the computed set and resolved on the grader (F6). |
| **A2** | **Reproducible on the stated selection, incomplete as a partition.** fastapi 8 genuine / 4 stable and rich 7 / 2 recomputed exactly from the 3 cited runs; with all 5 same-config runs stable becomes fastapi 3 / rich 2. The live fastapi denominator is stated two ways in the log (33 at L15152 and L16130 vs 29 gold-valid) — both appear, which is defensible only because they mean different things; the table omits requests 13 and httpx 1 (F14), and the "4 stable fastapi" includes `fastapi_14786`, elsewhere subtracted as gold-invalid (F5). |
| **A3** | **Verified** (F19). |
| **B1** | **Core verified, scope overstated** (F15, F16). |
| **B2** | **Not defensible as "they agree".** The agreement rests on the best of two identical local runs vs a Kaggle count that includes a freebie (F13), and the "no overflow locally" premise is false (F11). Honest statement: local genuine 7–12 (5 runs) vs Kaggle genuine 9 — overlapping, with Kaggle losing 8 tasks to overflow/timeout that the local rig mostly survives, so the two rigs' *reachable sets* differ systematically. |
| **C1** | **Contradicted** (F1). |
| **C2** | **Interpretation wrong** (F7). |
| **D1** | **Contradicted / selection-dependent** (F4). |
| **E1** | **Verified** (F20). |
| **F1** | **Verified in substance, with two integrity defects the brief does not mention**: the undisclosed pre-registration deviation (F8) and the baseline/arm scorer-version mismatch (F9). The "4 wins are noise" reading is correct and understated (F10). On the brief's own question — yes, the bar is badly designed (a tie on resolves + a 1-unit median shift = WIN) and that *is* the finding; the artifact does not state it, so the distinction is not currently recorded anywhere a reader would find it. |
| **G1** | **UNVERIFIED** (F17). |

---

## 2. THE THREE CLAIMS MOST LIKELY TO BE WRONG, AND THE TEST THAT SETTLES EACH

1. **C1 "noise is ±2/129" (and therefore every null built on it, including C2 and D1).**
   Test, free, no GPU: nothing to run — the deciding data is already on disk. Report the five
   same-config genuine counts {7, 9, 11, 11, 12} as the arm distribution instead of {9, 11, 11}.
   Then the one missing measurement: **3 more replicates of the 0-byte-prompt arm** (`m1_noprompt129`),
   so the two arms are compared as distributions. Pre-register: the prompt is worth >0 only if the
   two 4-run distributions separate (e.g. Mann-Whitney p < 0.05); with the current n=1 vs n=5 and
   the no-prompt value equal to a prompt run, the correct current verdict is "no measured effect".

2. **A1/A2 "59 truly solvable / 34 dead" (the denominator under every rate and the "+8 stable solves" target).**
   Test, free, CPU-only: re-run `replay_verify2.py` with `REPLAY_MODE=files` on **all 67 fastapi
   tasks** on the same CPU Kaggle kernel that produced `out_gold_fa`, and change `resolved_here` to
   the harness rule (`passed > 0 and failed == error == 0`, skips tolerated unless a required node
   is skipped). Pre-register: if ≥5 of the 24 multi-file fastapi tasks resolve, the published
   inventory (60/59/34/95) is retired and every rate recomputed. Expected to also re-home 8 rich
   tasks (`rich_3043, 3105, 3470, 3676, 3772, 3777, 3894, 4075`) from "unsolvable" to "solvable".

3. **D1 "the prompt is worth +2 to +4 and stabilises a named 3-task core".**
   Test: the pairwise comparison restricted to the intersection of **all five** same-config runs
   plus the replicated no-prompt arm from (1). Already-measurable half: the always-solved set is 2,
   not 3, and `rich_2725` goes the other way. Pre-register: the "stabilising core" claim survives
   only if `fastapi_14463`, `fastapi_14616`, `rich_3905` are solved in ≥4 of 4 prompt runs **and**
   0 of 4 no-prompt runs.

Runner-up, and arguably more urgent than any of the three: **F21**. Settle it by running the same
bundle twice with the GGUF pinned and `/props` captured into the run dir, and by recording the
served model in every `summary.json`. Until then no cross-batch local A/B in this project has a
verified common backend.

---

## 3. NUMBERS THAT APPEAR IN MORE THAN ONE PLACE WITH DIFFERENT VALUES

| quantity | occurrence A | occurrence B (and C) |
|---|---|---|
| gold patch validates | **60 / 129** — log L15382 ("60 (rich 30, fastapi 29, requests 1)"), L15314 | **31 / 129 (24%)** — log L15242 entry ("gold patch validates 31/129", "fastapi 0"). Recomputed under the harness rule: **≥68** |
| fastapi gold-valid | **29** — L15314, L16130, brief A2 | **0** — L15242 ("gold-winnable repo mix: rich 30, requests 1, fastapi 0"); and **0 of 24 multi-file fastapi tasks judgeable** (F2) |
| requests gold-valid | **1** — L15382 | **0** — L16130 per-repo table (column labelled "gold-valid") |
| dead tasks | **34** — L15152 heading, brief A1 | **28** (Kaggle) / **32** (local) in that same entry's own table; **49** under the loose definition (same entry); **18** — L5237 (2026-10-05) |
| "missing modules" counts | **`inline_snapshot` 48, `dirty_equals` 32** — L15152 table | per-**task** counts are 21 and 8 (Kaggle), 25 and 9 (local); the 48/32 are line occurrences, presented in a column next to a task count |
| local genuine, capped r0 | **7–9** — L14978 | **9** — brief B2/D1 and L16081 table |
| ca5 (uncapped) genuine | **12** — L14978, L14827 | brief C1 cites 12/14/14 and "15 in an earlier uncapped run" but never the **10 recorded / 7 genuine** of `ca5_v2`, which L14978 and L14797 both list |
| Kaggle E4B genuine | **10** — brief B2 | **9** after removing the `requests_6644` freebie — L15382 |
| stable + solvable | **5** — L15314, L15382, L16081 | **6** once `fastapi_14786` is credited (official log: 9 passed) — F5 |
| rich tasks "one failing test away" | **6** — L15152, L15382 | **14** — L16130 table |
| CONFIRM split size | **6 tasks incl. `rich_3772`** — `kb/audits/decode-sweep-plan.md:143-144` | **5 tasks, `rich_3772` absent and unmentioned** — `kb/audits/2026-10-15-decode-commitment-sweep.md` |
| decode-sweep scorer | **rp-4** — report title | **rp-5** — report "Verification" header; actual JSONL: rp-4 for the 11 baseline rows, rp-5 for the 77 arm rows |
| budget observed max | **22 calls / 419 s** — brief §4 | **20 calls / 404 s** (local r0) and **24 calls / 730 s with 2 timeout deaths** (Kaggle) |
| log size | **~16,200 lines** — brief §2 (actual 16,181 ✓) | **15,578 lines** — log L15600-area entry |
| logdb contents | **396 units / 1,180 claims** — log L15600-area | **406 units / 1,206 claims** — live `logdb.sqlite` (brief's 1,206 ✓) |
| `runs.jsonl` | **4,486 records / 13.7 MB** — brief §2 | 16.3 MB on disk during this review (rebuild in progress) |
| teams on the board | **3,871** — `lb.csv`, L12905 | **2,497** — `SCORING_ANALYSIS.md` §2 |
| our best score | **0.20 main / 0.03 E4B** — brief §1 | **0.12 main, ceiling 0.24, rank 1050/2497** — `SCORING_ANALYSIS.md` §1-2 |

---

## 4. WHAT THIS PROJECT HAS ACTUALLY ESTABLISHED

Stated conservatively enough to defend:

1. **The public score is `floor(k/58*100)/100`.** Unique fit over N ∈ [10, 2000] × 3 display modes
   against 3,712 scored teams, including the 0.14/0.16/0.19 holes. One displayed 0.01 = 1 task.
   (MEASURED; assumes equal per-task credit and that every achievable value is populated.)
2. **A substantial, all-fastapi slice of the practice set cannot resolve for anyone.** Floor: **28
   tasks** fail collection on the official image for want of `inline_snapshot`, `dirty_equals` or
   `scripts.prepare_release`. (MEASURED on the official `test_outputs`.) The 34 figure is a
   local∪official union and 6 of it is unproven on the grader.
3. **Exactly one task (`requests_6644`) resolves with an empty patch**, and the official E4B run
   counted it — so that run's genuine total is 9. (MEASURED.)
4. **The local rig's three `requests` solves are false positives.** The replay fails on the required
   node with assertion failures, reproduced on a CPU Kaggle kernel with identical counts. Treat all
   local `requests` coverage as zero. The *mechanism* (editable install not taking → site-packages
   import) is probable, not proven, and the sabotage test that supports it was run on `rich` only.
5. **The modified "grep the definition" rule was never executed as written** — 0 repo-wide
   definition greps in 7 runs, read from tool-call arguments; both solves in that arm came from runs
   that never attempted it. This is the cleanest result in the project: a prompt rule can be fully
   ignored while the arm still scores. (MEASURED.)
6. **A single 5–11-task gate cannot see a 1–2-task effect, but replication can.** On one fixed
   7-task cohort, 29 replicates of one config span 2–6 (mean 3.55, sd 0.83); with n=29 vs n=11 a
   0.64-task difference reaches p ≈ 0.02. (MEASURED.) The usable form of C2 is "arms run at n ≤ 3
   are uninformative", not "the effects are below the noise floor".
7. **Budget caps are not the local constraint** (max 20 calls / 404 s against 28 / 480 s) but they
   *are* binding on the grader for 2 of 129 tasks, and context overflow costs the grader 6 more.
   (MEASURED.)
8. **The decode sweep is a null.** Across all 11 tasks: baseline 1 resolve, `freq_02` 2, `freq_04` 2,
   `reserve_tail` 2, and `temp_00`/`temp_01`/`pres_02`/`pres_04` **0** — with `temp_00` and
   `pres_02` nonetheless labelled WIN. One run per cell. (MEASURED.)

What is **not** established: the size of the solvable set (floor ≥67, upper bound unknown because 24
fastapi and 12 requests tasks were never judged by a faithful rule); that the local rig is a faithful
proxy (F11, F13, F21); that the prompt is worth anything measurable (F4); that the local arms share a
common backend (F21); and the 44-error process audit (F17).

---

## 5. WHAT I WOULD DO NEXT (1 submission/day, no GPU for the local rig, target E4B 0.03 → ≥0.10)

Ordered by expected value per unit of the only scarce resources you have: daily slots and your own
attention. Nothing here needs a GPU.

1. **Fix the measuring stick before spending another slot (CPU-only, free, hours).** Re-run the gold
   replay in files mode with the harness's skip rule over all 129, as in §2(2). This is the single
   highest-leverage action because every target number you are steering by — "59 solvable", "95
   live", "5 stable", "we need +8" — is computed from the broken version, and the corrected version
   moves the target *toward* you (Model A's gap drops to ≈0). Also re-run the **empty** patch in the
   same mode: a second degenerate task would change the floor.
2. **Settle F21 in one local run pair**, with the GGUF pinned and `/props` recorded into
   `summary.json`. If the model declaration is live, several published A/B comparisons are
   model-confounded and must be re-labelled; if it is inert, your between-batch variance is larger
   than your stated noise floor and every n≤3 arm result should be withdrawn, not just restated.
3. **Spend the daily slots on variance harvesting of the known-best artifact, not on new configs.**
   Measured: genuine rate ≈ 9–10/129 ⇒ E[k] on 58 ≈ 4.5, σ ≈ 2.0, so P(k ≥ 6) ≈ 0.25 per draw.
   Re-submitting the same verified bundle reaches 0.10 with ~0.75 probability inside 5 draws, at
   zero engineering risk. No prompt arm you can currently measure has a defensible effect that large.
   (INFERRED from the measured rate and the verified `floor(k/58)` mapping.)
4. **Then, and only then, work content on the rich near-miss set** — the one place with a
   mechanism-level story: 8 rich tasks whose gold passes whole-file with skips (`rich_3043, 3105,
   3470, 3676, 3772, 3777, 3894, 4075`) plus the "one failing test away" set. Convert by reading the
   failing assertion, not by changing sampling. Pre-register per task: "this task flips in ≥3 of 4
   replicates" — a single flip is inside the measured per-task noise.
5. **Stop running 1-cell experiments.** Minimum viable arm in this rig is ~8 replicates on a fixed
   cohort (from the 29-rep distribution: 8 reps separate a 1-task mean shift at p≈0.05). An arm you
   cannot afford to replicate 8 times is an arm you cannot afford to interpret.
6. **Housekeeping that prevents the next retraction:** mark `SCORING_ANALYSIS.md` superseded (F18);
   append the `rich_3772` deviation and the rp-4/rp-5 mismatch to the decode-sweep report rather
   than leaving a clean-looking "frozen" artifact (F8, F9); change `replay_verify2.py`'s default to
   files mode or make node mode refuse multi-file tasks (F16); and store the 44-event classification
   as a machine-readable list or withdraw the percentage (F17).
