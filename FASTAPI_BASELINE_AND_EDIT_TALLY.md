# FastAPI Difficulty Baseline + Edit-Outcome Tally

Read-only investigation. Zero GPU. No code changed, nothing submitted, nothing re-run on the model.
Sources of truth:

- `Gemma/comp_files/tasks.jsonl` (129 records; 67 with repo `fastapi/fastapi`) — gold `patch` of each task.
- Every `results/traces/trace_*.json` under `Gemma/` (51 trajectories across 9 run folders).
- Run-log resolution ground truth parsed from the `gemma-sibling-conform-*.log` stream events
  (per-task `resolved=.. calls=.. chars=..` lines).
- `Gemma/local_eval/_batch_all.txt` (15 local-eval trajectories = 3 prompt variants x 5 rich tasks),
  which carries verbatim `edit_file` old_string/new_string sequences and a terminal outcome per task.

Methodology mirrors `Gemma/RICH_48_DIFFICULTY_MAP.md` (same EASY/MEDIUM/HARD rubric, same
"don't trust problem_statement length" caveat).

---

## 0. SUMMARY ANSWER (read this first)

**Part A — fastapi is MEASURABLY HARDER than rich by gold-patch mechanics, so deprioritizing it is the
right call *if the goal is easy resolves*.** Of 67 fastapi tasks: **19 EASY / 8 MEDIUM / 40 HARD**
(28% / 12% / 60%). Rich was **20 / 12 / 16** (42% / 25% / 33%) of 48. fastapi has a *larger absolute*
easy slice than rich (19 vs 20) but a far *smaller fraction* and a much heavier HARD tail (60% vs 33%,
driven by multi-file refactors and one 2047-line patch). Rough fastapi-only paper LB ceilings:
**EASY-only ~19/129 = 0.147**, **EASY+MEDIUM ~27/129 = 0.209** (labeled rough — they assume perfect
conversion, which Part B shows the agent does not achieve).

**Part B — the earlier muddled claim is REFUTED as a single-mechanic story. Both mechanics are real and
SEARCH-DEATH dominates, but EDIT-NOT-LANDING is a genuine, separately-attested second mechanic — it was
hidden because on the Kaggle GPU runs it manifests as an empty-argument tool-call failure, not as a
clean anchor mismatch.** Across 66 classified trajectories (51 Kaggle traces + 15 local-eval), the
non-resolved split is:

| bucket | count | % of non-resolved (N=60) |
|---|---|---|
| SEARCH-DEATH (never produced a landing edit) | 36 | **60.0%** |
| TEST-FAIL (patch applied, pytest fails) | 19 | **31.7%** |
| MALFORMED-TOOLCALL (edit_file args arrive empty) | 3 | 5.0% |
| EDIT-NOT-LANDING (correct-intent edit re-emitted >=3x, never applies) | 2 | 3.3% |

**Verdict:** SEARCH-DEATH (agent never commits a landing edit) is the dominant mechanic at ~60% of
failures; TEST-FAIL (wrong/incomplete patch) is second at ~32%. The pure "edit-not-landing" bucket is
numerically small (3.3%) **but that number understates the mechanic**: the 3 MALFORMED-TOOLCALL cases
are the *same* behavior at the transport layer (the agent re-emits a correct-looking `edit_file` 5-6
times and every call arrives with empty `old_string`/`path`), and several SEARCH-DEATH cases
degenerate from an edit-not-landing loop (anchor never matches, agent falls back to searching). Counting
MALFORMED + EDIT-NOT-LANDING together as "the agent tried to edit and the edit never landed" gives
5/60 = 8.3% as *terminal* bucket, but the behavior is visible inside a larger share of trajectories as a
contributing loop. See Section 7 verbatim examples.

The two earlier data points that caused the muddle are both confirmed and are NOT in conflict:
- rich_4079/4076/3469 at `patch_chars=0` (the v2 gate summary) = **SEARCH-DEATH** — confirmed.
- rich_2943 emitting a correct edit ~10x without it applying = **EDIT-NOT-LANDING** — confirmed verbatim
  in `_batch_all.txt` (10 identical `style._hash = None` edits, then `test_fail`).
They describe *different tasks*; neither is "the" dominant mechanic. The honest answer is a split, led
by search-death.

---

## PART A — FASTAPI DIFFICULTY BASELINE (67 tasks)

### A.1 Method

For each of the 67 `fastapi/fastapi` tasks, the gold `patch` was parsed (test_patch excluded) to count
source files changed, hunks (`@@`), added/removed lines, the edit SHAPE, and an overall class. Rubric
(identical to the rich pass):

- **SHAPE**: `ADD` (pure additions, <=2 hunks, <=15 net), `ONE-LINE` (<=2 net), `MODIFY-SMALL` (1 file,
  <=3 hunks, <=12 net), else `MULTI/SPRAWLING`.
- **CLASS EASY**: 1 file AND (an ADD, or 1 hunk with <=10 net, or <=3 net). **HARD**: >=2 files, or
  sprawling, or >40 net, or >=5 hunks. Else **MEDIUM**.
- **CAVEAT (carried from the rich pass, pressure-tested):** `problem_statement` length is NOT used as a
  difficulty axis. fastapi statements range from 63 to 10,095 chars and the length is uncorrelated with
  fix size — e.g. `fastapi_14463` has a 10,095-char statement but a 3-line gold fix (EASY), while
  `fastapi_14609` has a 144-char statement and a 2047-line patch (HARD). The `pstmt_len` column is shown
  for transparency only; class is driven by edit mechanics.

### A.2 Full 67-row table

Columns: `files` = source files in gold patch (tests excluded); `net (+/-)` = added+removed; `hunks`;
`shape`; `class`; `pstmt_len` = problem_statement length (NOT a difficulty signal, shown per caveat).

| instance_id | files | net (+/-) | hunks | shape | class | pstmt_len | file(s) |
|---|---|---|---|---|---|---|---|
| fastapi_11194 | 1 | 7 (3/4) | 1 | MODIFY-SMALL | **EASY** | 617 | fastapi/dependencies/utils.py |
| fastapi_11355 | 1 | 11 (9/2) | 3 | MODIFY-SMALL | MEDIUM | 299 | fastapi/dependencies/utils.py |
| fastapi_12942 | 1 | 3 (3/0) | 1 | ADD | **EASY** | 1392 | fastapi/_compat.py |
| fastapi_13207 | 1 | 14 (12/2) | 2 | MULTI/SPRAWLING | HARD | 354 | fastapi/_compat/v2.py |
| fastapi_13537 | 1 | 3 (2/1) | 1 | MODIFY-SMALL | **EASY** | 1650 | fastapi/dependencies/utils.py |
| fastapi_13713 | 2 | 31 (31/0) | 5 | MULTI/SPRAWLING | HARD | 756 | fastapi/applications.py; fastapi/openapi/utils.py |
| fastapi_13786 | 11 | 259 (176/83) | 25 | MULTI/SPRAWLING | HARD | 5328 | 11 files |
| fastapi_13920 | 1 | 4 (4/0) | 2 | ADD | **EASY** | 225 | fastapi/dependencies/utils.py |
| fastapi_14077 | 3 | 11 (5/6) | 6 | MULTI/SPRAWLING | HARD | 677 | 3 files |
| fastapi_14099 | 5 | 477 (346/131) | 13 | MULTI/SPRAWLING | HARD | 644 | 5 files |
| fastapi_14186 | 10 | 364 (266/98) | 51 | MULTI/SPRAWLING | HARD | 1009 | 10 files |
| fastapi_14246 | 1 | 28 (24/4) | 1 | MULTI/SPRAWLING | HARD | 273 | fastapi/_compat/v2.py |
| fastapi_14258 | 1 | 4 (4/0) | 1 | ADD | **EASY** | 418 | fastapi/routing.py |
| fastapi_14262 | 10 | 266 (196/70) | 29 | MULTI/SPRAWLING | HARD | 2437 | 10 files |
| fastapi_14266 | 1 | 18 (8/10) | 2 | MULTI/SPRAWLING | HARD | 247 | fastapi/dependencies/utils.py |
| fastapi_14297 | 1 | 7 (7/0) | 1 | ADD | **EASY** | 1219 | fastapi/_compat/v2.py |
| fastapi_14301 | 1 | 5 (4/1) | 1 | MODIFY-SMALL | **EASY** | 739 | fastapi/dependencies/utils.py |
| fastapi_14303 | 1 | 8 (6/2) | 1 | MODIFY-SMALL | **EASY** | 2644 | fastapi/dependencies/utils.py |
| fastapi_14306 | 2 | 137 (121/16) | 12 | MULTI/SPRAWLING | HARD | 2791 | fastapi/exceptions.py; fastapi/routing.py |
| fastapi_14349 | 1 | 12 (6/6) | 1 | MODIFY-SMALL | MEDIUM | 169 | fastapi/_compat/v2.py |
| fastapi_14356 | 1 | 11 (9/2) | 1 | MODIFY-SMALL | MEDIUM | 1481 | fastapi/dependencies/utils.py |
| fastapi_14360 | 1 | 3 (1/2) | 1 | MODIFY-SMALL | **EASY** | 753 | fastapi/dependencies/utils.py |
| fastapi_14361 | 1 | 2 (1/1) | 1 | ONE-LINE | **EASY** | 96 | fastapi/_compat/v2.py |
| fastapi_14371 | 4 | 62 (46/16) | 12 | MULTI/SPRAWLING | HARD | 397 | 4 files |
| fastapi_14372 | 2 | 7 (4/3) | 3 | MULTI/SPRAWLING | HARD | 1160 | fastapi/dependencies/utils.py; fastapi/params.py |
| fastapi_14419 | 2 | 62 (42/20) | 7 | MULTI/SPRAWLING | HARD | 689 | fastapi/dependencies/models.py; fastapi/dependencies/utils.py |
| fastapi_14430 | 1 | 4 (2/2) | 2 | MODIFY-SMALL | MEDIUM | 335 | fastapi/_compat/v2.py |
| fastapi_14448 | 2 | 106 (82/24) | 3 | MULTI/SPRAWLING | HARD | 1226 | fastapi/dependencies/models.py; fastapi/dependencies/utils.py |
| fastapi_14455 | 1 | 13 (11/2) | 2 | MULTI/SPRAWLING | HARD | 283 | fastapi/openapi/utils.py |
| fastapi_14458 | 1 | 7 (6/1) | 4 | MULTI/SPRAWLING | HARD | 591 | fastapi/dependencies/models.py |
| fastapi_14459 | 3 | 71 (49/22) | 8 | MULTI/SPRAWLING | HARD | 815 | 3 files |
| fastapi_14463 | 1 | 3 (2/1) | 2 | MODIFY-SMALL | **EASY** | 10095 | fastapi/openapi/utils.py |
| fastapi_14479 | 1 | 2 (1/1) | 1 | ONE-LINE | **EASY** | 2455 | fastapi/dependencies/utils.py |
| fastapi_14482 | 1 | 32 (25/7) | 5 | MULTI/SPRAWLING | HARD | 266 | fastapi/_compat/v2.py |
| fastapi_14485 | 1 | 19 (13/6) | 2 | MULTI/SPRAWLING | HARD | 317 | fastapi/dependencies/utils.py |
| fastapi_14487 | 1 | 7 (5/2) | 1 | MODIFY-SMALL | **EASY** | 204 | docs_src/handling_errors/tutorial004.py |
| fastapi_14492 | 1 | 2 (1/1) | 1 | ONE-LINE | **EASY** | 159 | docs_src/metadata/tutorial001_1_py39.py |
| fastapi_14512 | 1 | 52 (48/4) | 3 | MULTI/SPRAWLING | HARD | 289 | fastapi/_compat/v2.py |
| fastapi_14583 | 2 | 24 (24/0) | 6 | MULTI/SPRAWLING | HARD | 104 | fastapi/dependencies/utils.py; fastapi/routing.py |
| fastapi_14605 | 7 | 44 (28/16) | 20 | MULTI/SPRAWLING | HARD | 242 | 7 files |
| fastapi_14609 | 20 | 2047 (192/1855) | 92 | MULTI/SPRAWLING | HARD | 144 | 20 files |
| fastapi_14616 | 1 | 12 (10/2) | 2 | MODIFY-SMALL | MEDIUM | 1176 | fastapi/dependencies/utils.py |
| fastapi_14786 | 1 | 2 (1/1) | 1 | ONE-LINE | **EASY** | 2303 | fastapi/security/utils.py |
| fastapi_14791 | 1 | 2 (2/0) | 1 | ADD | **EASY** | 591 | fastapi/openapi/utils.py |
| fastapi_14794 | 1 | 5 (3/2) | 2 | MODIFY-SMALL | MEDIUM | 816 | fastapi/dependencies/utils.py |
| fastapi_14851 | 1 | 157 (153/4) | 5 | MULTI/SPRAWLING | HARD | 464 | fastapi/routing.py |
| fastapi_14873 | 1 | 21 (11/10) | 2 | MULTI/SPRAWLING | HARD | 674 | fastapi/routing.py |
| fastapi_14953 | 4 | 104 (102/2) | 5 | MULTI/SPRAWLING | HARD | 1775 | 4 files |
| fastapi_14962 | 3 | 55 (49/6) | 6 | MULTI/SPRAWLING | HARD | 210 | 3 files |
| fastapi_14964 | 1 | 52 (44/8) | 2 | MULTI/SPRAWLING | HARD | 370 | fastapi/responses.py |
| fastapi_14978 | 3 | 82 (81/1) | 14 | MULTI/SPRAWLING | HARD | 112 | 3 files |
| fastapi_14986 | 2 | 34 (25/9) | 4 | MULTI/SPRAWLING | HARD | 1000 | fastapi/applications.py; fastapi/openapi/docs.py |
| fastapi_15023 | 1 | 26 (18/8) | 1 | MULTI/SPRAWLING | HARD | 112 | docs_src/stream_data/tutorial002_py310.py |
| fastapi_15030 | 9 | 560 (525/35) | 17 | MULTI/SPRAWLING | HARD | 148 | 9 files |
| fastapi_15280 | 2 | 72 (71/1) | 3 | MULTI/SPRAWLING | HARD | 64 | docs_src/vibe/tutorial001_py310.py; fastapi/applications.py |
| fastapi_15588 | 1 | 23 (18/5) | 2 | MULTI/SPRAWLING | HARD | 1891 | fastapi/sse.py |
| fastapi_15589 | 1 | 4 (4/0) | 1 | ADD | **EASY** | 1247 | fastapi/dependencies/utils.py |
| fastapi_15661 | 1 | 216 (216/0) | 1 | MULTI/SPRAWLING | HARD | 1025 | scripts/prepare_release.py |
| fastapi_15745 | 4 | 1230 (939/291) | 21 | MULTI/SPRAWLING | HARD | 4304 | 4 files |
| fastapi_15763 | 1 | 13 (10/3) | 1 | MULTI/SPRAWLING | HARD | 1064 | fastapi/routing.py |
| fastapi_15785 | 2 | 81 (66/15) | 6 | MULTI/SPRAWLING | HARD | 1263 | fastapi/openapi/utils.py; fastapi/routing.py |
| fastapi_15800 | 8 | 654 (649/5) | 20 | MULTI/SPRAWLING | HARD | 1236 | 8 files |
| fastapi_5077 | 1 | 6 (4/2) | 2 | MODIFY-SMALL | MEDIUM | 2679 | fastapi/dependencies/utils.py |
| fastapi_5624 | 1 | 4 (3/1) | 1 | MODIFY-SMALL | **EASY** | 63 | fastapi/dependencies/utils.py |
| fastapi_9425 | 1 | 2 (2/0) | 1 | ADD | **EASY** | 235 | fastapi/dependencies/utils.py |
| fastapi_9555 | 1 | 22 (14/8) | 1 | MULTI/SPRAWLING | HARD | 2934 | fastapi/dependencies/models.py |
| fastapi_9753 | 1 | 7 (5/2) | 2 | MODIFY-SMALL | MEDIUM | 689 | fastapi/dependencies/models.py |

### A.3 Counts (MEASURED from gold patches)

- **EASY : 19 / 67** (28.4%)
- **MEDIUM: 8 / 67** (11.9%)
- **HARD : 40 / 67** (59.7%)

Shape histogram: `ONE-LINE 4`, `ADD 7`, `MODIFY-SMALL 16`, `MULTI/SPRAWLING 40`.
Single-file: 43 / 67. File-count tail: 9 tasks touch >=3 files; extremes are `fastapi_14609`
(20 files / 2047 net), `fastapi_15745` (4 files / 1230 net), `fastapi_15800` (8 files / 654 net).

The 19 EASY fastapi tasks (the harvestable slice): `fastapi_11194, 12942, 13537, 13920, 14258, 14297,
14301, 14303, 14360, 14361, 14463, 14479, 14487, 14492, 14786, 14791, 15589, 5624, 9425`. Note the EASY
slice is heavily concentrated in `fastapi/dependencies/utils.py` (8 of 19), which is a useful
localization prior if fastapi is ever prioritized.

### A.4 Rough paper LB ceilings (fastapi-only, /129 total board)

These are **upper bounds that assume perfect conversion** (Part B shows conversion is far from perfect);
label them paper ceilings, not projections.

- EASY-only : **19 / 129 = 0.147**
- EASY+MEDIUM: **27 / 129 = 0.209**

### A.5 rich-vs-fastapi comparison and HARDER/EASIER verdict

| axis | rich (48) | fastapi (67) |
|---|---|---|
| EASY | 20 (41.7%) | 19 (28.4%) |
| MEDIUM | 12 (25.0%) | 8 (11.9%) |
| HARD | 16 (33.3%) | 40 (**59.7%**) |
| single-file share | 37/48 (77%) | 43/67 (64%) |
| sprawling share | 21/48 (44%) | 40/67 (60%) |

**Verdict: fastapi is HARDER than rich by gold-patch mechanics.** It has essentially the same *number*
of EASY tasks (19 vs 20) but a much smaller EASY *fraction* and nearly double the HARD fraction (60% vs
33%). The fastapi HARD tail is also heavier in absolute terms (multi-file dependency-injection
refactors, large `_compat/v2.py` rewrites, a 20-file 2047-line patch). The EASY+MEDIUM paper ceiling
is actually *lower* than rich's (0.209 vs rich's 0.248) despite fastapi being 52% of the board.

**Strategic read (measurement, not a recommendation to change the model):** deprioritizing fastapi in
favor of rich is defensible *for maximizing easy resolves per unit effort* — rich offers a higher
density of mechanically-trivial fixes. However, fastapi still contains 19 genuinely easy tasks worth
~0.147 on their own, and they cluster in one file; they are not worthless, just lower-density. The
user's framing ("rich seemed easier to solve") is consistent with the mechanics: rich is easier *per
task*, not *in total count*.

---

## PART B — EDIT-OUTCOME TALLY (settle the dominant mechanic)

### B.1 Method and bucket definitions

Every trajectory was classified into exactly one terminal bucket:

1. **SEARCH-DEATH** — zero landing edits and no non-empty patch (`patch_chars`/`chars` = 0). The agent
   explored (grep/read/search) and/or reproduced the bug but never committed a surviving edit.
2. **EDIT-NOT-LANDING** — >=1 `edit_file` the agent clearly intends as correct, whose observation is an
   error/no-op (anchor not found, 0 occurrences, identical), AND the same/similar edit re-emitted >=3x,
   with final `chars` = 0.
3. **MALFORMED-TOOLCALL** — `edit_file` args structurally broken (here: `old_string`/`path` arrive
   EMPTY, triggering "mandatory input parameters are not present"), re-emitted, no landing edit.
4. **TEST-FAIL** — a non-empty patch WAS produced and applied (`chars` > 0) but the task is unresolved
   (fails hermetic pytest). Real patch, wrong/incomplete fix.
5. **RESOLVED** — committed and resolved=True in the run log.

Resolution ground truth for the Kaggle traces comes from the run-log `resolved=.. chars=..` lines (the
trace JSON itself carries no resolved flag). For the local-eval trajectories the outcome token
(`resolved`/`test_fail`/`no_patch`/`err:*`) IS the external verdict.

**Edit-detection correction made during this pass (recorded per the accountability rule to distinguish
measured from mistaken):** an initial parser counted `cat > /tmp/repro.py <<'EOF'` reproduction scripts
as "edits," inflating `fastapi_14246` and `rich_3469` to 10 successful edits. Those write to `/tmp`, not
to repo source. The corrected parser counts a `run_command` edit only when it writes to a repo path
(`rich/`, `fastapi/`, `docs_src/`, `scripts/`). After the fix both are correctly SEARCH-DEATH (pure
explore/repro, patch=0). This is exactly the "compulsive reproduction" explore-death noted in
`GEMMA_EXPERIMENT_LOG.md`.

### B.2 Per-trajectory table — Kaggle on-GPU traces (N=51)

`n_edit` = edit_file + repo-path run_command edits; `n_succ` = edits whose observation reports a diff;
`max_rep` = max count of one identical edit signature; `pchars` = authoritative patch size (run-log,
else submit_patch); `resolved` = run-log verdict (None = that run log carries no resolved line for the
task, i.e. a pulled-trace-only run).

| run | task | n_edit | n_succ | max_rep | patch>0 | pchars | resolved | bucket |
|---|---|---|---|---|---|---|---|---|
| v18 | rich_3469 | 0 | 0 | 0 | 0 | 0 | False | SEARCH-DEATH |
| v18 | rich_4070 | 5 | 3 | 1 | 1 | 3157 | (unlogged) | TEST-FAIL |
| v18 | rich_4076 | 0 | 0 | 0 | 0 | 0 | False | SEARCH-DEATH |
| v18 | rich_4077 | 1 | 1 | 1 | 1 | 396 | True | RESOLVED |
| v18 | rich_4079 | 0 | 0 | 0 | 0 | 0 | False | SEARCH-DEATH |
| v19 | rich_3469 | 1 | 0 | 1 | 0 | 0 | False | SEARCH-DEATH |
| v19 | rich_4070 | 5 | 2 | 2 | 1 | 1047 | (unlogged) | TEST-FAIL |
| v19 | rich_4076 | 1 | 0 | 1 | 0 | 0 | False | SEARCH-DEATH |
| v19 | rich_4077 | 1 | 1 | 1 | 1 | 324 | True | RESOLVED |
| v19 | rich_4079 | 1 | 0 | 1 | 0 | 0 | False | SEARCH-DEATH |
| v19_lora | rich_3469 | 0 | 0 | 0 | 0 | 0 | False | SEARCH-DEATH |
| v19_lora | rich_4070 | 18 | 0 | 18 | 0 | 0 | (unlogged) | MALFORMED-TOOLCALL |
| v19_lora | rich_4076 | 0 | 0 | 0 | 0 | 0 | False | SEARCH-DEATH |
| v19_lora | rich_4077 | 3 | 1 | 2 | 1 | 324 | True | RESOLVED |
| v19_lora | rich_4079 | 6 | 0 | 6 | 0 | 0 | False | MALFORMED-TOOLCALL |
| v19v3 | rich_3469 | 0 | 0 | 0 | 0 | 0 | False | SEARCH-DEATH |
| v19v3 | rich_4070 | 7 | 4 | 3 | 1 | 1428 | (unlogged) | TEST-FAIL |
| v19v3 | rich_4076 | 7 | 2 | 5 | 1 | 552 | False | TEST-FAIL |
| v19v3 | rich_4077 | 1 | 1 | 1 | 1 | 324 | True | RESOLVED |
| v19v3 | rich_4079 | 0 | 0 | 0 | 0 | 0 | False | SEARCH-DEATH |
| _v10_kaggle_pull | fastapi_14246 | 0 | 0 | 0 | 0 | 0 | (unlogged) | SEARCH-DEATH |
| _v10_kaggle_pull | fastapi_14356 | 1 | 1 | 1 | 1 | 3192 | (unlogged) | TEST-FAIL |
| _v10_kaggle_pull | fastapi_14485 | 3 | 2 | 1 | 1 | 1096 | (unlogged) | TEST-FAIL |
| _v10_kaggle_pull | fastapi_14487 | 4 | 4 | 1 | 1 | 8719 | (unlogged) | TEST-FAIL |
| _v10_kaggle_pull | requests_7315 | 3 | 3 | 1 | 1 | 1395 | (unlogged) | TEST-FAIL |
| _v10_kaggle_pull | requests_7502 | 3 | 3 | 1 | 1 | 1513 | (unlogged) | TEST-FAIL |
| _v10_kaggle_pull | rich_3469 | 0 | 0 | 0 | 0 | 0 | (unlogged) | SEARCH-DEATH |
| _v10_kaggle_pull | rich_4076 | 0 | 0 | 0 | 0 | 0 | (unlogged) | SEARCH-DEATH |
| _v10_kaggle_pull | rich_4077 | 0 | 0 | 0 | 0 | 0 | (unlogged) | SEARCH-DEATH |
| _v10_kaggle_pull | rich_4079 | 3 | 3 | 1 | 0 | 0 | (unlogged) | SEARCH-DEATH |
| _v6out | fastapi_15588 | 3 | 3 | 1 | 1 | 1513 | (unlogged) | TEST-FAIL |
| _v6out | fastapi_15661 | 0 | 0 | 0 | 1 | 2435 | (unlogged) | TEST-FAIL |
| _v6out | rich_4070 | 4 | 4 | 1 | 1 | 2223 | (unlogged) | TEST-FAIL |
| _v6out | rich_4076 | 0 | 0 | 0 | 0 | 0 | (unlogged) | SEARCH-DEATH |
| _v6out | rich_4077 | 1 | 1 | 1 | 1 | 396 | (unlogged) | TEST-FAIL |
| _v6out | rich_4079 | 2 | 1 | 2 | 1 | 562 | (unlogged) | TEST-FAIL |
| v2_gate_out2 | rich_3469 | 0 | 0 | 0 | 0 | 0 | False | SEARCH-DEATH |
| v2_gate_out2 | rich_4070 | 0 | 0 | 0 | 0 | 0 | (unlogged) | SEARCH-DEATH |
| v2_gate_out2 | rich_4076 | 0 | 0 | 0 | 0 | 0 | False | SEARCH-DEATH |
| v2_gate_out2 | rich_4077 | 0 | 0 | 0 | 0 | 0 | False | SEARCH-DEATH |
| v2_gate_out2 | rich_4079 | 0 | 0 | 0 | 0 | 0 | False | SEARCH-DEATH |
| v2_gate_out | rich_3469 | 1 | 0 | 1 | 0 | 0 | False | SEARCH-DEATH |
| v2_gate_out | rich_4070 | 12 | 1 | 10 | 0 | 0 | (unlogged) | SEARCH-DEATH |
| v2_gate_out | rich_4076 | 1 | 1 | 1 | 1 | 473 | False | TEST-FAIL |
| v2_gate_out | rich_4077 | 1 | 1 | 1 | 1 | 396 | True | RESOLVED |
| v2_gate_out | rich_4079 | 6 | 0 | 5 | 0 | 0 | False | MALFORMED-TOOLCALL |
| v2_gate_s05c | rich_3469 | 0 | 0 | 0 | 0 | 0 | False | SEARCH-DEATH |
| v2_gate_s05c | rich_4070 | 16 | 2 | 13 | 0 | 0 | (unlogged) | SEARCH-DEATH |
| v2_gate_s05c | rich_4076 | 0 | 0 | 0 | 0 | 0 | False | SEARCH-DEATH |
| v2_gate_s05c | rich_4077 | 1 | 1 | 1 | 1 | 324 | True | RESOLVED |
| v2_gate_s05c | rich_4079 | 0 | 0 | 0 | 0 | 0 | False | SEARCH-DEATH |

Note on the three "(unlogged)" TEST-FAIL rows for `v2_gate_out2` — all five v2_gate_out2 tasks have
patch=0 and resolved=False, so none is TEST-FAIL there; the "(unlogged)" tag only means the resolved
line was read from a sibling v2 log. The v2_gate_out2 rows are all SEARCH-DEATH (the agent produced no
patch at all in that run — consistent with the v19-LORA-v2 regression the user pasted).

### B.3 Per-trajectory table — local-eval traces (`_batch_all.txt`, N=15)

These carry verbatim `edit_file` sequences and an external outcome token. `escaped_nl` = the edit anchor
contained a literal backslash-n (`\n`) instead of a real newline.

| variant | task | n_edit | max_rep | patch>0 | chars | outcome | bucket | escaped_nl_anchor |
|---|---|---|---|---|---|---|---|---|
| baseline | rich_4077 | 3 | 3 | 1 | 686 | test_fail | TEST-FAIL | no |
| baseline | rich_3278 | 0 | 0 | 0 | 0 | err:AttributeError | SEARCH-DEATH | no |
| baseline | rich_2943 | 10 | 10 | 1 | 434 | test_fail | TEST-FAIL* | no |
| baseline | rich_3470 | 0 | 0 | 0 | 0 | no_patch | SEARCH-DEATH | no |
| baseline | rich_3471 | 8 | 7 | 0 | 0 | no_patch | EDIT-NOT-LANDING | **yes** |
| anti_noop | rich_4077 | 2 | 2 | 1 | 644 | test_fail | TEST-FAIL | no |
| anti_noop | rich_3278 | 0 | 0 | 0 | 0 | no_patch | SEARCH-DEATH | no |
| anti_noop | rich_2943 | 0 | 0 | 0 | 0 | no_patch | SEARCH-DEATH | no |
| anti_noop | rich_3470 | 0 | 0 | 0 | 0 | no_patch | SEARCH-DEATH | no |
| anti_noop | rich_3471 | 0 | 0 | 0 | 0 | no_patch | SEARCH-DEATH | no |
| sibling | rich_4077 | 1 | 1 | 1 | 680 | test_fail | TEST-FAIL | no |
| sibling | rich_3278 | 0 | 0 | 0 | 0 | no_patch | SEARCH-DEATH | no |
| sibling | rich_2943 | 11 | 8 | 0 | 0 | no_patch | EDIT-NOT-LANDING | **yes** |
| sibling | rich_3470 | 0 | 0 | 0 | 0 | no_patch | SEARCH-DEATH | no |
| sibling | rich_3471 | 0 | 0 | 0 | 0 | no_patch | SEARCH-DEATH | no |

`*` rich_2943/baseline: bucketed TEST-FAIL by the strict rule (a non-empty patch was produced and failed
pytest), but the mechanic that filled the trajectory was EDIT-NOT-LANDING — the agent emitted the
identical `style._hash = None` edit **10 times** (steps 6-15) before anything stuck. It is the clearest
single illustration that TEST-FAIL and EDIT-NOT-LANDING are not cleanly separable: a non-landing loop
can terminate in a late, wrong-ish patch.

### B.4 Aggregate 5-bucket counts

| bucket | Kaggle traces (N=51) | local-eval (N=15) | COMBINED (N=66) |
|---|---|---|---|
| SEARCH-DEATH | 27 | 9 | **36** |
| EDIT-NOT-LANDING | 0 | 2 | **2** |
| MALFORMED-TOOLCALL | 3 | 0 | **3** |
| TEST-FAIL | 15 | 4 | **19** |
| RESOLVED | 6 | 0 | **6** |

**Combined non-resolved split (N=60):** SEARCH-DEATH 60.0% · TEST-FAIL 31.7% · MALFORMED-TOOLCALL 5.0%
· EDIT-NOT-LANDING 3.3%.

### B.5 The dominant-mechanic verdict (confirm / refute the muddled claim)

- **SEARCH-DEATH dominates at ~60% of non-resolved trajectories.** The agent most often never produces
  a surviving edit: it loops on `search_code`/`grep` with escalating regexes (`rich_3278`,
  `rich_3470`), or it burns the budget reading and reproducing (`fastapi_14246`), or on the v2-LORA
  gate runs it produces nothing at all (every v2_gate_out2 task = patch 0). This is the mechanic behind
  the v2 gate summary the user pasted (rich_4079/4076/3469 at `patch_chars=0`).
- **TEST-FAIL is a strong second at ~32%.** When the agent DOES land a patch, roughly a third of the
  time the patch is wrong/incomplete and fails pytest (e.g. all three `_v6out` fastapi/rich landings,
  the `_v10` fastapi/requests landings). This is a correctness mechanic, distinct from both of the above.
- **EDIT-NOT-LANDING is real but numerically small as a *terminal* bucket (3.3%), and is the mechanic
  the earlier analysis muddled.** It is attested verbatim (Section 7): a correct-looking `edit_file`
  re-emitted 7-12 times whose anchor never matches, usually because the anchor carries a literal `\n`
  (escaped newline) instead of a real newline. On the Kaggle GPU runs the *same* behavior shows up as
  MALFORMED-TOOLCALL (3 cases) where the `edit_file` call arrives with empty `old_string`/`path` and the
  agent re-emits 5-6 times. Treating MALFORMED-TOOLCALL + EDIT-NOT-LANDING as one "the agent tried to
  edit and nothing landed" family gives 5/60 = **8.3%** as a terminal bucket.

**Explicit answer to the brief's key question — the real split, measured:**
of all non-resolved trajectories, **~60% search-death (never edited), ~32% test-fail (applied but
wrong), ~8% edit-not-landing/malformed (edited correctly in intent but it didn't apply).** The claim
that edit-not-landing was *the* dominant mechanic is **REFUTED**; the claim that it exists and is a real
second failure surface is **CONFIRMED**. The two earlier anecdotes (rich_4079=search-death,
rich_2943=edit-not-landing) are both genuine and describe different tasks.

**One honest caveat on sample composition (stated per the accountability rule):** the trajectory set is
small (66) and heavily weighted toward the five "word-trap" rich tasks (rich_4077/4079/4076/3469/4070)
that every run re-ran, plus a handful of fastapi/requests pulls. It is NOT a uniform sample of the 129
tasks. The ~60/32/8 split is a reliable description of *these logged trajectories*; projecting it to the
full board is an inference, not a measurement. The direction (search-death > test-fail > edit-not-landing)
is robust across both independent sources (Kaggle traces and local-eval), which is the strongest claim
the data supports.

---

## 7. Verbatim EDIT-NOT-LANDING examples (why a correct-looking edit fails to apply)

All three are from `Gemma/local_eval/_batch_all.txt` (local-eval, external pytest verdict) and the
Kaggle `trace_rich_4079.json` files.

### Example 1 — rich_2943, `sibling` variant → `no_patch` (escaped-newline anchor + stray backslash)

The gold fix is a one-line cache clear in `rich/style.py`. The agent found the right line, then emitted
this edit **11 times** (steps 4-15), alternating two broken anchor encodings:

```
edit_file(path='rich/style.py',
          old_string='        style._hash = self._hash\n      ',   # literal backslash-n, not a newline
          new_string='        style._hash = None\n        styl')
...and intermittently (steps 12,13,15):
          old_string='        style._hash = self._hash\\n      '   # a SECOND stray backslash
```

Diagnosis: the anchor contains the two characters `\` `n` instead of an actual line break, so it never
matches the file text (which has a real newline). The agent cannot see the difference in its own output
and loops until the budget dies. `max_rep = 8`, final `chars = 0` → EDIT-NOT-LANDING. (The *single-line*
`baseline` variant of the same task used a correct anchor `style._hash = self._hash`, emitted it 10x,
and DID produce a 434-char patch that then failed pytest → that one lands in TEST-FAIL.)

### Example 2 — rich_3471, `baseline` variant → `no_patch` (escaped-newline anchor)

Gold fix is a +1-line guard in `rich/text.py:append_tokens`. The agent emitted, 7-8 times (steps 6-15):

```
edit_file(path='rich/text.py',
          old_string='        for content, style in tokens:\n  ',  # literal backslash-n
          new_string='        for content, style in tokens:\n  ')
```

Diagnosis: identical escaped-`\n` failure. The `new_string` is also byte-identical to the (intended)
`old_string`, so even if the anchor matched it would be a no-op. `max_rep = 7`, `chars = 0`.

### Example 3 — rich_4079, Kaggle `v2_gate_out` run → `MALFORMED-TOOLCALL` (empty args, transport failure)

Same mechanic at the transport layer rather than the anchor layer. Six consecutive `edit_file` calls,
each observation:

```
{"error": "Invoking `edit_file()` failed as the following mandatory input parameters
 are not present:\nold_string\nYou could retry calling this tool, but it is IMPORTANT
 for you to provide all the mandatory parameters."}
```

Inspecting the tool-call arguments: `path=''`, `old_string=''` — the two-field `edit_file` call arrived
EMPTY. The agent clearly intends an edit (it re-emits 6 times, and the final budget-killed call shows
`old_string='class TableDataElement(MarkdownElement):'`, a correct anchor), but the arguments do not
serialize/transmit. This is the exact `edit_file` unreliability the v18 system prompt warns about
("its two-field old_string/new_string call frequently fails to transmit") — which is why v18/v19 steer
the agent to apply edits via `run_command` instead. `max_rep = 5`, `chars = 0`.

**Common root cause across all three:** the agent produces a semantically correct edit, but the
*mechanism* of delivering it fails — either the anchor is encoded with a literal `\n` (so it can never
match the file) or the two-field `edit_file` arguments arrive empty. In both cases the agent gets no
usable error signal it can act on and re-emits the same broken call until the budget is exhausted. This
is a harness/tool-fidelity failure, not a reasoning failure, and it is the second-order reason some
"EASY" rich tasks never resolve despite a trivial gold fix.

---

## 8. Distinguishing measured from inferred (accountability)

- **MEASURED (gold patches, Part A):** every files/hunks/net/shape number is computed directly from
  `tasks.jsonl` gold `patch` text. The 19/8/40 counts are exact.
- **MEASURED (Part B):** per-trajectory `n_edit`, `max_rep`, `chars`, and bucket are computed from the
  trace JSON tool_calls/observations and the run-log resolved lines. The verbatim edit examples in
  Section 7 are quoted from the files.
- **INFERRED:** (a) the EASY/MEDIUM/HARD *class boundaries* are a rubric, not a ground-truth label — a
  task at a boundary (e.g. `fastapi_14246`, 1 file / 1 hunk / 28 net → HARD) could be argued either way;
  the counts are robust to a few such swaps but not exact to +/-1. (b) The paper LB ceilings assume
  perfect conversion and are explicitly upper bounds. (c) Projecting the ~60/32/8 bucket split to all
  129 tasks is an inference; the measured split describes the 66 logged trajectories, which over-sample
  five rich tasks. (d) The claim that MALFORMED-TOOLCALL and EDIT-NOT-LANDING share a root cause is an
  interpretation supported by Section 7, not a separate measurement.
- **HONEST NULL:** there is no evidence in the data for a large hidden edit-not-landing population on
  the Kaggle runs beyond the 3 malformed cases — on-GPU, non-landing edits are rare because the prompt
  routes edits through `run_command`; the clean edit-not-landing pattern lives mostly in the earlier
  local-eval `edit_file`-based runs.

---

## 9. Recommendations (measurement-driven; nothing implemented, no model/training change proposed)

Per the brief these are observations about *where the measurement points*, not instructions to retrain:

1. **The dominant lever is search-death, not edit-fidelity.** ~60% of failures never commit a landing
   edit. Anything that forces an earlier commit (the agent's own §4 of RICH_48 already notes the commit
   rule was tried and ignored) attacks the largest bucket. The user's note that "the commit rule was
   ignored before" is consistent with the data — a prompt rule did not move the search-death share.
2. **Edit-fidelity (escaped-`\n` anchors, empty two-field args) is a smaller but fully diagnosable bucket.**
   The Section 7 examples show the exact corruption. This is a tool-mechanics debugging task, not a
   reasoning problem — which is why v18/v19 already route edits through `run_command`.
3. **fastapi deprioritization is defensible on density but leaves ~0.147 on the table.** If the harness
   fixes above raise conversion, the 19 EASY fastapi tasks (8 of them in `dependencies/utils.py`) become
   a cheap second front. They are harder per-task than rich but not individually hard.

---

*Scripts used for this read-only pass were throwaway (`_tmp_partA.py`, `_tmp_partB2.py`) and parse-only;
no source, task file, trace, or submission was modified.*
