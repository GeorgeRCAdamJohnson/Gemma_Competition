# 129-Task 31B A3 Run — Full Analysis

Kernel: `comfyops/gemma-sibling-conform-31b-a3-hard` · model `gemma-4-31b-it-qat-w4a16-ct` · A3 prompt (sha 0aae1a1e314a) · shipped config 28/8/80/240, thinking 1024, temp 0.2 · 4xL4, tp=4 · public 129-task set, one sample per task, sequential.

## 1. Headline

**34/129 = 0.264** (Wilson 95% CI [0.195, 0.346]). Board score 0.18 ~= 23/129; this run is 0.08 above it. Total wall 10.8 h — inside the 12 h cap (mean 302 s, median 286 s, p90 484 s, max 591 s per task).

## 2. By repository

| repo | tasks | solved | rate | Wilson 95% CI |
|---|---|---|---|---|
| Textualize/rich | 48 | 15 | 31.2% | [20%, 45%] |
| encode/httpx | 1 | 0 | 0.0% | [0%, 79%] |
| fastapi/fastapi | 67 | 18 | 26.9% | [18%, 39%] |
| psf/requests | 13 | 1 | 7.7% | [1%, 33%] |

fastapi resolves at nearly the rich rate. The log's standing claim "Zero fastapi ever resolved" (L28) was an artifact of the v1-v8 era (0/2, 0/6 samples) and is overturned by this run.

## 3. By fix-shape bucket (gold-patch taxonomy, 16 shapes)

| shape | tasks | solved | rate | failure modes (NO_PATCH / WRONG / CAP) |
|---|---|---|---|---|
| multiline_other | 45 | 11 | 24% | 7 / 24 / 3 |
| add_condition_branch | 20 | 6 | 30% | 4 / 8 / 2 |
| multiline_logic_in_func | 14 | 2 | 14% | 6 / 5 / 1 |
| add_other | 8 | 2 | 25% | 2 / 3 / 1 |
| single_line_other | 8 | 2 | 25% | 4 / 2 / 0 |
| add_return | 7 | 1 | 14% | 1 / 5 / 0 |
| single_token_change | 5 | 3 | 60% | 1 / 1 / 0 |
| add_raise/except | 5 | 0 | 0% | 0 / 3 / 2 |
| signature/arg_change | 4 | 2 | 50% | 0 / 2 / 0 |
| add_import | 3 | 0 | 0% | 1 / 1 / 1 |
| string/message_change | 3 | 3 | 100% | 0 / 0 / 0 |
| pure_deletion | 3 | 0 | 0% | 1 / 2 / 0 |
| add_none_guard | 1 | 1 | 100% | 0 / 0 / 0 |
| add_def/class | 1 | 0 | 0% | 0 / 0 / 1 |
| operator/comparison_change | 1 | 1 | 100% | 0 / 0 / 0 |
| off_by_one | 1 | 0 | 0% | 0 / 1 / 0 |

Pattern: small precise contract-shaped fixes convert (string/message 3/3, single_token 3/5, signature 2/4); additive/structural fixes do not (add_raise 0/5, add_import 0/3, pure_deletion 0/3).

## 4. Failure anatomy (95 misses)

| mode | count | share of misses | definition |
|---|---|---|---|
| WRONG_CONTENT | 57 | 60% | landed a patch, tests failed, no call cap |
| NO_PATCH | 27 | 28% | submitted nothing (0 chars) |
| CALL_CAP | 11 | 12% | burned all 28 calls (with patch) |

Of the 27 NO_PATCH: 16 never called submit_patch at all; 16 never called edit_file at all; 11 edited but submitted empty.

## 5. Prompt compliance vs outcome

A3's explicit rules, measured against the full tool trace. Correlations from one run, n=1 per task, no control arm — associations, not causal claims.

| behaviour | n | solved | rate | vs complement | Fisher p |
|---|---|---|---|---|---|
| get_status called >=1 | 69 | 25 | 36% | 15% | 0.009 |
| first edit within 4 calls | 13 | 5 | 38% | 25% | 0.326 |
| exactly 1 edit_file | 49 | 17 | 35% | 21% | 0.103 |
| submitted exactly once | 101 | 32 | 32% | 7% | 0.008 |
| non-empty patch | 101 | 33 | 33% | 4% | 0.001 |
| did not hit call cap | 104 | 31 | 30% | 12% | 0.081 |

Rule-violation counts: get_status never called 60/129 (47%); >=3 calls 0/129; first edit after >4 calls 116/129 (90%); submit 0 times 21, >1 times 7 (max: requests_6757 x10); zero-patch 28/129 (22%).

## 6. Tool usage

| tool | calls | share | errors |
|---|---|---|---|
| run_command | 1455 | 52% | 203 |
| read_file | 867 | 31% | 0 |
| edit_file | 279 | 10% | 0 |
| submit_patch | 124 | 4% | 0 |
| get_status | 82 | 3% | 0 |
| write_file | 2 | 0% | 0 |
| get_code_neighbors | 2 | 0% | 0 |
| search_similar_code | 1 | 0% | 0 |

**Tool-level failures are essentially zero on 31B.** edit_file: 0 errors across 279 calls (strategies: exact 146, unescaped 38 — the A3 delimiter fix works completely at this scale; contrast E4B where 62% of edit_file calls error). Of the 203 run_command "errors", 202 are `error (exit 0)` with empty detail — benign harness flags (grep-no-match / empty output), 1 real. What remains after A3 is purely decision-level: wrong content, no patch, budget exhaustion.
Per-task medians: 21 tool calls, 5 read_file, 11 run_command, 1 edit_file, 1 get_status, 1 submit_patch, 20 k thinking chars.

## 7. Rich retention vs prior 31B runs

- Prior 31B-solved union (cover-rich, repeat-live, smoke): 16 tasks
- This run solved: 15 rich tasks
- Kept: rich_2725, rich_2943, rich_3006, rich_3043, rich_3067, rich_3278, rich_3454, rich_3518, rich_3718, rich_3777, rich_3882, rich_3894, rich_3905, rich_4077, rich_4079
- LOST: rich_3471
- NEW: none

rich_3471 death trace: 484 s, 20 calls, 0 edits, 0 submits. grep -> read text.py -> grep -> read text.py (returned file start again; agent noted the tool behaving oddly) -> 2 more reads -> 20 calls of locating. Violated A3's 3-4-call locate limit and its sed advice.

## 8. Time trend (deterioration check)

| block | tasks | solve% | median patch | median calls | NO_PATCH% |
|---|---|---|---|---|---|
| 1-21 | 21 | 10% | 1022 | 21 | 5% |
| 22-43 | 22 | 32% | 658 | 25 | 32% |
| 44-64 | 21 | 33% | 832 | 23 | 19% |
| 65-86 | 22 | 23% | 841 | 22 | 18% |
| 87-107 | 21 | 24% | 745 | 19 | 14% |
| 108-129 | 22 | 36% | 424 | 18 | 41% |

Patch size vs run position: Pearson r = -0.127 (no growth pathology). No OOM events, no compaction events, 2 token-limit truncations. Block 1's low rate is task-mix (fastapi+requests run first).

## 9. Budget fit

- 129 tasks x mean 302 s = 10.8 h total, inside the 12 h cap.
- Tasks hitting the 8-min wall: 24. Tasks hitting the 28-call cap: 25.
- The cap-arithmetic fear (129 x 8 min = 13 h) remains refuted by observed means.

## 10. Full per-task table

| # | task | repo | shape | result | mode | dur s | calls | patch | status | submits | edits | locate |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | fastapi_15661 | fastapi | add_raise/except | fail | WRONG_CONTENT | 320 | 23 | 2557 | 0 | 1 | 0 | 24 |
| 2 | fastapi_15588 | fastapi | multiline_logic_in_func | fail | WRONG_CONTENT | 263 | 13 | 1701 | 1 | 1 | 5 | 2 |
| 3 | fastapi_15589 | fastapi | add_other | fail | CALL_CAP | 434 | 28 | 1513 | 0 | 1 | 3 | 18 |
| 4 | fastapi_15030 | fastapi | add_raise/except | fail | WRONG_CONTENT | 226 | 9 | 1022 | 2 | 1 | 2 | 5 |
| 5 | fastapi_14962 | fastapi | add_return | fail | WRONG_CONTENT | 395 | 19 | 776 | 1 | 1 | 2 | 12 |
| 6 | fastapi_15280 | fastapi | add_raise/except | fail | CALL_CAP | 335 | 28 | 5374 | 0 | 1 | 4 | 21 |
| 7 | fastapi_14964 | fastapi | multiline_other | fail | WRONG_CONTENT | 107 | 15 | 1002 | 1 | 1 | 4 | 8 |
| 8 | fastapi_15023 | fastapi | multiline_logic_in_func | fail | NO_PATCH | 336 | 28 | 0 | 0 | 1 | 1 | 28 |
| 9 | fastapi_14986 | fastapi | multiline_other | fail | WRONG_CONTENT | 194 | 24 | 1191 | 0 | 1 | 5 | 13 |
| 10 | fastapi_14978 | fastapi | add_other | fail | WRONG_CONTENT | 204 | 27 | 3275 | 0 | 1 | 4 | 18 |
| 11 | requests_7505 | psf | add_return | fail | WRONG_CONTENT | 264 | 22 | 2603 | 0 | 1 | 6 | 7 |
| 12 | requests_7502 | psf | signature/arg_change | fail | WRONG_CONTENT | 328 | 18 | 1410 | 0 | 1 | 3 | 14 |
| 13 | requests_7433 | psf | multiline_other | fail | WRONG_CONTENT | 131 | 8 | 739 | 2 | 1 | 1 | 5 |
| 14 | requests_7427 | psf | add_condition_branch | fail | WRONG_CONTENT | 354 | 21 | 1034 | 0 | 1 | 1 | 16 |
| 15 | requests_7315 | psf | pure_deletion | fail | WRONG_CONTENT | 123 | 19 | 522 | 1 | 2 | 2 | 8 |
| 16 | requests_7328 | psf | single_token_change | fail | WRONG_CONTENT | 427 | 25 | 885 | 0 | 1 | 2 | 11 |
| 17 | requests_7309 | psf | multiline_other | fail | WRONG_CONTENT | 89 | 11 | 692 | 1 | 1 | 1 | 6 |
| 18 | requests_7205 | psf | single_line_other | fail | WRONG_CONTENT | 245 | 12 | 503 | 0 | 1 | 1 | 7 |
| 19 | rich_4070 | Textualize | multiline_other | fail | WRONG_CONTENT | 193 | 27 | 4324 | 1 | 1 | 11 | 2 |
| 20 | rich_4077 | Textualize | add_return | PASS | RESOLVED | 192 | 17 | 423 | 1 | 1 | 2 | 11 |
| 21 | rich_4079 | Textualize | multiline_other | PASS | RESOLVED | 456 | 27 | 562 | 0 | 1 | 1 | 22 |
| 22 | rich_4076 | Textualize | multiline_other | fail | NO_PATCH | 484 | 28 | 0 | 0 | 0 | 0 | 28 |
| 23 | rich_4075 | Textualize | multiline_logic_in_func | fail | NO_PATCH | 226 | 28 | 0 | 1 | 1 | 2 | 28 |
| 24 | rich_4006 | Textualize | multiline_other | fail | NO_PATCH | 484 | 4 | 0 | 1 | 0 | 0 | 5 |
| 25 | fastapi_14258 | fastapi | add_other | fail | NO_PATCH | 488 | 26 | 0 | 0 | 0 | 0 | 26 |
| 26 | fastapi_14851 | fastapi | add_condition_branch | PASS | RESOLVED | 380 | 25 | 0 | 0 | 1 | 0 | 26 |
| 27 | fastapi_14873 | fastapi | add_none_guard | PASS | RESOLVED | 272 | 20 | 1681 | 1 | 1 | 1 | 19 |
| 28 | fastapi_13920 | fastapi | add_condition_branch | fail | WRONG_CONTENT | 288 | 16 | 3667 | 0 | 1 | 9 | 4 |
| 29 | fastapi_14794 | fastapi | single_line_other | PASS | RESOLVED | 151 | 10 | 791 | 1 | 1 | 1 | 6 |
| 30 | fastapi_14786 | fastapi | single_token_change | PASS | RESOLVED | 58 | 4 | 404 | 2 | 1 | 1 | 3 |
| 31 | fastapi_14492 | fastapi | string/message_change | PASS | RESOLVED | 56 | 9 | 391 | 1 | 1 | 1 | 7 |
| 32 | fastapi_14479 | fastapi | add_other | fail | WRONG_CONTENT | 255 | 25 | 524 | 0 | 1 | 4 | 3 |
| 33 | fastapi_14463 | fastapi | single_token_change | PASS | RESOLVED | 99 | 17 | 832 | 1 | 1 | 2 | 7 |
| 34 | fastapi_12942 | fastapi | add_condition_branch | fail | WRONG_CONTENT | 362 | 25 | 1478 | 1 | 1 | 3 | 12 |
| 35 | fastapi_14099 | fastapi | multiline_other | fail | WRONG_CONTENT | 490 | 25 | 1382 | 0 | 0 | 1 | 24 |
| 36 | fastapi_14609 | fastapi | pure_deletion | fail | WRONG_CONTENT | 491 | 25 | 8027 | 0 | 0 | 9 | 10 |
| 37 | fastapi_14372 | fastapi | multiline_other | PASS | RESOLVED | 155 | 20 | 526 | 0 | 1 | 1 | 17 |
| 38 | fastapi_14349 | fastapi | multiline_other | fail | WRONG_CONTENT | 469 | 22 | 2157 | 1 | 1 | 2 | 19 |
| 39 | fastapi_14512 | fastapi | add_condition_branch | fail | NO_PATCH | 487 | 21 | 0 | 1 | 0 | 0 | 22 |
| 40 | fastapi_14487 | fastapi | multiline_logic_in_func | fail | WRONG_CONTENT | 221 | 27 | 4642 | 1 | 1 | 7 | 18 |
| 41 | fastapi_11355 | fastapi | multiline_other | fail | WRONG_CONTENT | 222 | 25 | 2087 | 1 | 1 | 3 | 20 |
| 42 | fastapi_14485 | fastapi | multiline_logic_in_func | fail | NO_PATCH | 264 | 28 | 0 | 1 | 1 | 1 | 28 |
| 43 | fastapi_14482 | fastapi | multiline_other | fail | CALL_CAP | 484 | 28 | 1711 | 0 | 1 | 4 | 6 |
| 44 | fastapi_14306 | fastapi | multiline_logic_in_func | fail | NO_PATCH | 191 | 28 | 0 | 1 | 1 | 1 | 29 |
| 45 | fastapi_14458 | fastapi | add_condition_branch | PASS | RESOLVED | 286 | 10 | 1502 | 1 | 1 | 3 | 5 |
| 46 | fastapi_14459 | fastapi | multiline_other | fail | WRONG_CONTENT | 490 | 26 | 498 | 1 | 0 | 1 | 24 |
| 47 | fastapi_14448 | fastapi | multiline_logic_in_func | fail | WRONG_CONTENT | 402 | 7 | 2573 | 1 | 1 | 1 | 5 |
| 48 | fastapi_14455 | fastapi | multiline_other | fail | WRONG_CONTENT | 250 | 24 | 1765 | 1 | 1 | 1 | 22 |
| 49 | fastapi_9753 | fastapi | multiline_other | PASS | RESOLVED | 290 | 27 | 694 | 1 | 1 | 2 | 24 |
| 50 | fastapi_14430 | fastapi | single_line_other | fail | NO_PATCH | 486 | 18 | 0 | 0 | 0 | 0 | 18 |
| 51 | fastapi_5077 | fastapi | multiline_other | PASS | RESOLVED | 296 | 14 | 887 | 1 | 1 | 2 | 9 |
| 52 | fastapi_9555 | fastapi | multiline_logic_in_func | PASS | RESOLVED | 362 | 27 | 2280 | 2 | 1 | 2 | 8 |
| 53 | fastapi_14361 | fastapi | single_line_other | fail | WRONG_CONTENT | 204 | 14 | 512 | 1 | 1 | 1 | 11 |
| 54 | fastapi_13207 | fastapi | multiline_other | fail | WRONG_CONTENT | 309 | 23 | 1280 | 0 | 1 | 1 | 9 |
| 55 | fastapi_14360 | fastapi | multiline_other | fail | WRONG_CONTENT | 339 | 15 | 649 | 1 | 1 | 1 | 12 |
| 56 | fastapi_14356 | fastapi | multiline_other | fail | WRONG_CONTENT | 249 | 22 | 746 | 0 | 1 | 1 | 16 |
| 57 | fastapi_5624 | fastapi | multiline_other | PASS | RESOLVED | 392 | 16 | 1197 | 2 | 1 | 2 | 14 |
| 58 | fastapi_14419 | fastapi | multiline_logic_in_func | fail | NO_PATCH | 487 | 27 | 0 | 0 | 0 | 0 | 27 |
| 59 | fastapi_14301 | fastapi | multiline_other | PASS | RESOLVED | 412 | 28 | 1702 | 1 | 1 | 5 | 7 |
| 60 | fastapi_14262 | fastapi | multiline_logic_in_func | fail | WRONG_CONTENT | 250 | 27 | 832 | 0 | 1 | 2 | 22 |
| 61 | fastapi_14266 | fastapi | pure_deletion | fail | NO_PATCH | 315 | 28 | 0 | 0 | 1 | 2 | 28 |
| 62 | fastapi_14246 | fastapi | multiline_other | fail | WRONG_CONTENT | 305 | 27 | 1084 | 1 | 1 | 1 | 25 |
| 63 | fastapi_14186 | fastapi | add_condition_branch | fail | WRONG_CONTENT | 355 | 12 | 1670 | 1 | 1 | 2 | 4 |
| 64 | fastapi_9425 | fastapi | add_condition_branch | PASS | RESOLVED | 206 | 21 | 544 | 2 | 1 | 1 | 19 |
| 65 | fastapi_13713 | fastapi | add_import | fail | CALL_CAP | 265 | 28 | 4166 | 1 | 1 | 1 | 24 |
| 66 | fastapi_14077 | fastapi | single_line_other | PASS | RESOLVED | 117 | 17 | 2443 | 2 | 2 | 6 | 5 |
| 67 | rich_3718 | Textualize | multiline_other | PASS | RESOLVED | 260 | 10 | 767 | 1 | 1 | 4 | 2 |
| 68 | rich_3934 | Textualize | add_condition_branch | fail | WRONG_CONTENT | 478 | 27 | 798 | 0 | 1 | 2 | 14 |
| 69 | rich_3953 | Textualize | multiline_other | fail | WRONG_CONTENT | 341 | 12 | 884 | 2 | 1 | 1 | 10 |
| 70 | rich_3944 | Textualize | off_by_one | fail | WRONG_CONTENT | 181 | 12 | 1077 | 1 | 1 | 3 | 7 |
| 71 | rich_3942 | Textualize | multiline_other | fail | NO_PATCH | 484 | 23 | 0 | 0 | 0 | 0 | 23 |
| 72 | rich_3938 | Textualize | add_condition_branch | fail | NO_PATCH | 282 | 28 | 0 | 0 | 2 | 1 | 28 |
| 73 | rich_3882 | Textualize | signature/arg_change | PASS | RESOLVED | 100 | 12 | 503 | 1 | 1 | 1 | 4 |
| 74 | rich_3894 | Textualize | add_condition_branch | PASS | RESOLVED | 220 | 21 | 587 | 0 | 3 | 1 | 7 |
| 75 | rich_3935 | Textualize | multiline_other | fail | NO_PATCH | 484 | 21 | 0 | 0 | 0 | 0 | 21 |
| 76 | rich_3905 | Textualize | multiline_other | PASS | RESOLVED | 88 | 11 | 627 | 1 | 1 | 3 | 6 |
| 77 | rich_3930 | Textualize | add_import | fail | WRONG_CONTENT | 486 | 20 | 6182 | 0 | 0 | 5 | 8 |
| 78 | httpx_3672 | encode | add_return | fail | WRONG_CONTENT | 252 | 25 | 1579 | 1 | 1 | 4 | 16 |
| 79 | fastapi_14791 | fastapi | add_other | fail | WRONG_CONTENT | 115 | 5 | 483 | 1 | 1 | 1 | 2 |
| 80 | fastapi_15800 | fastapi | add_raise/except | fail | CALL_CAP | 249 | 28 | 660 | 0 | 1 | 1 | 27 |
| 81 | fastapi_15785 | fastapi | add_condition_branch | fail | CALL_CAP | 216 | 28 | 1411 | 0 | 1 | 0 | 29 |
| 82 | fastapi_14371 | fastapi | add_condition_branch | fail | CALL_CAP | 419 | 28 | 6607 | 0 | 1 | 9 | 7 |
| 83 | fastapi_14605 | fastapi | add_def/class | fail | CALL_CAP | 179 | 28 | 7205 | 0 | 1 | 13 | 3 |
| 84 | fastapi_15763 | fastapi | multiline_other | fail | WRONG_CONTENT | 199 | 27 | 1180 | 0 | 1 | 4 | 6 |
| 85 | fastapi_14583 | fastapi | add_condition_branch | fail | NO_PATCH | 487 | 15 | 0 | 0 | 0 | 1 | 14 |
| 86 | fastapi_15745 | fastapi | multiline_logic_in_func | fail | CALL_CAP | 444 | 28 | 2014 | 0 | 1 | 2 | 20 |
| 87 | fastapi_14297 | fastapi | add_condition_branch | fail | WRONG_CONTENT | 232 | 12 | 931 | 1 | 1 | 1 | 5 |
| 88 | fastapi_14303 | fastapi | multiline_other | fail | WRONG_CONTENT | 150 | 11 | 745 | 1 | 1 | 1 | 7 |
| 89 | fastapi_13537 | fastapi | multiline_other | PASS | RESOLVED | 258 | 9 | 826 | 1 | 1 | 1 | 6 |
| 90 | fastapi_14953 | fastapi | add_return | fail | WRONG_CONTENT | 219 | 10 | 560 | 1 | 1 | 1 | 5 |
| 91 | fastapi_13786 | fastapi | multiline_logic_in_func | fail | WRONG_CONTENT | 491 | 24 | 4574 | 1 | 0 | 6 | 10 |
| 92 | fastapi_14616 | fastapi | multiline_logic_in_func | PASS | RESOLVED | 276 | 28 | 769 | 0 | 1 | 1 | 27 |
| 93 | fastapi_11194 | fastapi | multiline_other | PASS | RESOLVED | 178 | 10 | 1020 | 0 | 1 | 1 | 4 |
| 94 | requests_6757 | psf | add_import | fail | NO_PATCH | 288 | 24 | 0 | 2 | 10 | 4 | 9 |
| 95 | requests_6629 | psf | add_return | fail | WRONG_CONTENT | 321 | 25 | 524 | 1 | 1 | 1 | 21 |
| 96 | requests_6644 | psf | add_condition_branch | PASS | RESOLVED | 160 | 18 | 376 | 1 | 1 | 1 | 13 |
| 97 | requests_6589 | psf | add_condition_branch | fail | WRONG_CONTENT | 296 | 23 | 363 | 1 | 1 | 1 | 19 |
| 98 | requests_6592 | psf | signature/arg_change | fail | WRONG_CONTENT | 218 | 23 | 579 | 1 | 1 | 3 | 5 |
| 99 | rich_3180 | Textualize | multiline_logic_in_func | fail | NO_PATCH | 483 | 17 | 0 | 0 | 0 | 0 | 17 |
| 100 | rich_3486 | Textualize | add_condition_branch | fail | WRONG_CONTENT | 410 | 19 | 542 | 0 | 1 | 4 | 9 |
| 101 | rich_3777 | Textualize | add_condition_branch | PASS | RESOLVED | 227 | 28 | 976 | 1 | 1 | 2 | 27 |
| 102 | rich_3468 | Textualize | add_raise/except | fail | WRONG_CONTENT | 392 | 23 | 6966 | 2 | 1 | 0 | 26 |
| 103 | rich_3782 | Textualize | add_return | fail | NO_PATCH | 342 | 28 | 0 | 0 | 1 | 1 | 28 |
| 104 | rich_3772 | Textualize | multiline_other | fail | WRONG_CONTENT | 591 | 10 | 2221 | 2 | 1 | 2 | 5 |
| 105 | rich_3296 | Textualize | multiline_other | fail | WRONG_CONTENT | 260 | 27 | 905 | 1 | 1 | 2 | 10 |
| 106 | rich_3675 | Textualize | multiline_other | fail | WRONG_CONTENT | 258 | 18 | 702 | 0 | 2 | 3 | 11 |
| 107 | rich_3676 | Textualize | multiline_other | fail | WRONG_CONTENT | 201 | 18 | 1224 | 0 | 1 | 4 | 10 |
| 108 | rich_3518 | Textualize | signature/arg_change | PASS | RESOLVED | 97 | 13 | 529 | 2 | 1 | 1 | 10 |
| 109 | rich_3535 | Textualize | multiline_other | fail | WRONG_CONTENT | 242 | 12 | 465 | 1 | 1 | 1 | 9 |
| 110 | rich_3521 | Textualize | multiline_other | fail | NO_PATCH | 484 | 15 | 0 | 0 | 0 | 0 | 15 |
| 111 | rich_3506 | Textualize | multiline_other | fail | NO_PATCH | 484 | 7 | 0 | 0 | 0 | 0 | 7 |
| 112 | rich_3480 | Textualize | single_token_change | fail | NO_PATCH | 487 | 10 | 0 | 0 | 0 | 0 | 10 |
| 113 | rich_3472 | Textualize | multiline_other | fail | NO_PATCH | 348 | 28 | 0 | 0 | 1 | 0 | 29 |
| 114 | rich_3454 | Textualize | string/message_change | PASS | RESOLVED | 114 | 8 | 657 | 2 | 1 | 2 | 4 |
| 115 | rich_3471 | Textualize | add_other | fail | NO_PATCH | 484 | 20 | 0 | 0 | 0 | 0 | 20 |
| 116 | rich_3470 | Textualize | single_line_other | fail | NO_PATCH | 403 | 28 | 0 | 0 | 1 | 1 | 28 |
| 117 | rich_3469 | Textualize | single_line_other | fail | NO_PATCH | 323 | 28 | 0 | 0 | 2 | 1 | 29 |
| 118 | rich_3052 | Textualize | multiline_other | fail | WRONG_CONTENT | 200 | 10 | 3261 | 1 | 1 | 6 | 2 |
| 119 | rich_3278 | Textualize | add_other | PASS | RESOLVED | 437 | 17 | 322 | 1 | 1 | 2 | 8 |
| 120 | rich_2943 | Textualize | single_token_change | PASS | RESOLVED | 119 | 15 | 400 | 1 | 1 | 1 | 11 |
| 121 | rich_2725 | Textualize | multiline_other | PASS | RESOLVED | 202 | 19 | 1099 | 0 | 1 | 3 | 5 |
| 122 | rich_3105 | Textualize | single_line_other | fail | NO_PATCH | 483 | 23 | 0 | 0 | 0 | 0 | 23 |
| 123 | rich_3130 | Textualize | multiline_other | fail | WRONG_CONTENT | 223 | 25 | 828 | 1 | 1 | 1 | 23 |
| 124 | rich_3043 | Textualize | add_other | PASS | RESOLVED | 358 | 17 | 449 | 0 | 1 | 2 | 8 |
| 125 | rich_3067 | Textualize | string/message_change | PASS | RESOLVED | 213 | 18 | 655 | 0 | 1 | 1 | 10 |
| 126 | rich_3006 | Textualize | operator/comparison_change | PASS | RESOLVED | 77 | 18 | 558 | 1 | 1 | 1 | 10 |
| 127 | rich_3064 | Textualize | multiline_other | fail | CALL_CAP | 362 | 28 | 1529 | 0 | 1 | 5 | 17 |
| 128 | rich_3063 | Textualize | add_condition_branch | fail | NO_PATCH | 484 | 18 | 0 | 0 | 0 | 0 | 18 |
| 129 | rich_3061 | Textualize | multiline_other | fail | CALL_CAP | 419 | 28 | 1124 | 1 | 1 | 3 | 19 |
