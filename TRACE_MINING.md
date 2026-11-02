# TRACE_MINING — What the 480 agent traces say we're obviously missing

Read-only mining of 480 `trace_*.json` files across all run roots (excluding `local_eval\repos`),
joined against `local_eval\pull_31ba3hard_out\run_rows.jsonl` + `_v10_compliance.json` (ground truth
for the 129-run only) and `comp_files\tasks.jsonl` (gold patches). Trace format: `steps[]` with
`source`, `message`, `extra.event_type/elapsed_s`, and tool calls embedded in `steps[].tool_calls[]`
(`function_name`, `arguments`, `extra.elapsed_s`) with results in `steps[].observation`.
Qualitative reading capped at 41 detailed traces (22 wrong-content, 9 no-patch, 10 zero-tool);
everything else aggregated programmatically. Statistics: Fisher exact for 2x2, Mann-Whitney U for
continuous. Scripts: `C:\Users\Biges\AppData\Local\Temp\trace_mine.py`, `trace_mine2.py`.

---

## (a) What we measured, with numbers

### Ground truth recap (129-run)
34 resolved / 95 failed = 26.4%. Failure classes: RIGHT_FILE_WRONG_CONTENT 62, NEVER_LANDED_EDIT 27, WRONG_FILE 6.

### a. First tool call
- **129-run (A3 prompt): first tool is `run_command` 100/129 (77.5%) or `read_file` 29/129 (22.5%). `get_status` is NEVER first** — the prompt's "get_status is free" framing does not make anyone open with it.
- By outcome: solved 73.5% run_command / 26.5% read_file; failed 78.9% / 21.1%. **No difference (Fisher p=0.63).** First tool does not predict success in A3.
- All 480 traces: run_command 57.1%, read_file 21.0%, **get_status 19.2%** (only in older prompt families), no tool call at all 2.1% (10 runs), plus rare `code_analyzer_agent`/`search_similar_code`/`get_code_neighbors` (1 each).
- Prompt families differ sharply: E4B runs (`out_k_e4ba3/5`, n=88) start with `get_status` 79/88; `submit_v6z_on_v6w` (n=55) starts with run_command 47/55; A3 (n=129) never get_status-first. First-tool behavior is a prompt artifact, not a model choice.

### b. Time-to-first-edit
- Solved: median **114 s** / call **9**; Failed: median **190 s** / call **12.5**.
- Elapsed: MWU p=0.012. Call index: MWU p=0.055 (run_rows `first_edit_at_call`: 11 vs 12.5, p=0.000026 on the raw field).
- Threshold: **first edit by call ≤8 → 39% solve vs 21% otherwise (p=0.047)**.
- 19/95 failed runs and 1/34 solved never edited at all.

### c. Thinking volume — failures think MORE, not less
- Solved: median **15.1 k** chars thinking (mean 16.6 k); Failed: median **21.5 k** (mean 23.1 k). **MWU p=0.0019.** Same for all agent text: 15.7 k vs 22.0 k (p=0.0025).
- Threshold: **<15 k thinking → 40% solve vs 20% (p=0.020)**; >25 k → 17% vs 31% (p=0.098).
- Correlated churn: failed runs read more files (median 7 vs 3, p=0.00017; **≥10 reads → 8% solve vs 34%, p=0.0035**), run longer (median 321 s vs 210 s, p=3.9e-5; **<250 s → 40% vs 18%, p=0.0074**), accumulate more budget warnings (median 6 vs 0, p=0.0012), more total tool calls (25 vs 19, p=0.011), longer locate phase (`locate` field: 14 vs 8, p=0.0135; **locate>14 → 15% vs 35%, p=0.009**). 24 runs crossed 470 s; **0 of 24 resolved**.

### d. Wrong-content runs (62, patch landed on the gold file, tests failed) — why the final thinking thought it was done
Classified from final message + last thinking (n=62):
| belief at the end | count |
|---|---|
| submitted, **zero verification** ("The patch was submitted successfully") | 43 |
| hit the call cap, submitted anyway | 10 |
| ran some test command during the run | 9 |
| claims it verified (repro script / "tests pass") | 5 |
| explicitly admits the fix is **partial** | 4 |
| never submitted (died mid-run) | 5 |
| gave-up language | 1 |

- **57/62 ended with `submit_patch` as the last tool call followed by a confident final summary** — the model equates "submitted" with "done". The final messages describe the change in detail; almost none question whether hidden tests would agree.
- 37/62 had **full gold-file coverage** (edited every file gold touches) and still failed → the content, not the location, is wrong. 35/62 have a single gold file, so this is not just multi-file spillover.
- Only **9/62 (15%) ever executed any test command**; 43/62 never ran anything that could falsify their fix.

### e. No-patch runs (27) — where they end
- **16/27 never called edit_file (15 of those also never submitted)**: pure locate failures. 15 of the 16 died at 483–487 s (the 8-minute wall) still reading — last events are `thinking` (16) or `final` (11), last tools `run_command`/`read_file`. Last thoughts: *"I'm still not at the logic. Let's go further."*, *"I'm really stuck."*, *"I'll use my last tool call to read `fastapi/dependencies/models.py`."*
- **10/27 called edit_file AND submit_patch but the patch was empty** — the edit never landed (old_string mismatch / failed edit) and the agent did not notice; `submit_patch` happily returned ok with `patch_size: 0`. One of them (`requests_6757`) called submit_patch **10 times** and ended with *"I've tried everything. I'll just stop here."*
- 16/27 never called submit_patch at all; 11/27 hit the 28-call cap; only 3/27 ever ran a test.
- One (`rich_3506`) ended at 483 s with 7 calls and the last thought *"Wait, I think I found it!"* — time cap kills runs at the moment of discovery.

### f. "Found the right location but still failed" (the obvious misses)
- **62 runs edited the gold file(s) and failed** (all RIGHT_FILE_WRONG_CONTENT). 43/62 mention the gold file path in their final message — they knew where the fix belongs.
- 37/62 edited **all** gold files and still failed: right files, wrong content.
- Full gold-file coverage is the strongest single predictor in the whole dataset: **29/34 solved vs 37/95 failed had coverage=100% (OR=9.1, p=2.6e-6)** — but note 37 fully-covered runs still failed, so coverage is necessary-ish, not sufficient.
- Task-structure predictors (from gold patches):
  - **Multi-file gold patch: 3/38 resolved (7.9%) vs single-file 31/91 (34%), Fisher p=0.0019.**
  - Gold patch size terciles: ≤656 chars 20/43 (47%), 656–2124 12/42 (29%), **>2124 chars 2/44 (4.5%)**.
  - **New-file gold tasks (`@@ -0,0` hunks): 0/11 resolved** (p=0.066) — e.g. `fastapi_15661` needs a brand-new `scripts/prepare_release.py`; the agent made 0 edits.
  - `n_gold_edits==1` OR=6.0, p=0.0019 (same fact as multi-file, restated).

### Cross-check: what actually separates solved from failed (beyond known compliance stats)
Significant (Fisher/MWU), 129-run:
| signal | solved | failed | p |
|---|---|---|---|
| full gold-file coverage | 29/34 | 37/95 | 2.6e-6 |
| zero patch | 1/34 | 27/95 | 0.0013 |
| get_status called ≥1 | 25/34 | 44/95 | 0.0088 (known) |
| submit exactly once | 32/34 | 69/95 | 0.0078 (known) |
| never edited | 1/34 | 19/95 | 0.024 |
| thinking chars (MWU) | 15.1 k med | 21.5 k med | 0.0019 |
| duration (MWU) | 210 s | 321 s | 3.9e-5 |
| read_file count (MWU) | 3 | 7 | 0.00017 |
| budget warnings (MWU) | 0 | 6 | 0.0012 |
| locate calls (MWU) | 8 | 14 | 0.0135 |
| first edit elapsed (MWU) | 114 s | 190 s | 0.012 |
| total tool calls (MWU) | 19 | 25 | 0.011 |
| multi-file gold task | — | — | 0.0019 |

**NOT different** (impressions disproven): first tool choice (p=0.63), ran-tests boolean (4/34 vs 12/95, p=1.0), patch size (p=0.59), number of edit_file calls (p=0.93), edit exactly once (17/49 vs 17/80, p=0.10), tool-error count (p=0.39), locate≤4 rule compliance (13/129 comply at all; p=0.33).

Caveat: the churn signals (duration, reads, thinking, budget warnings, cap) are mutually correlated — they are one latent factor: **runs that don't localize quickly spiral**. Gold-coverage and task-structure are the more causal-looking axes.

---

## (b) 10 most striking concrete examples

1. **`fastapi_14262` (wrong-content)** — gold touches 10 files; agent edited 2, and its last thought literally says *"I have submitted the **partial** fix."* Knew it was incomplete, submitted anyway. Failed.
2. **`requests_6592` (wrong-content)** — concluded the gold change *"was already done"* in the baseline, submitted **only tests** as its contribution: *"my only contribution was the tests... I'm done."* Gold file `src/requests/status_codes.py` never changed by the agent.
3. **`fastapi_14605` (wrong-content)** — 13 edits, hit the call cap, gold spans 7 files; final claims all files updated to `FastAPIDeprecationWarning`. Submitted at cap with no verification; coverage incomplete.
4. **`fastapi_15030` (wrong-content)** — implemented `EventSourceResponse` in 1 of 9 gold files (gold also adds `fastapi/sse.py` + 5 docs). Also shows tool-state confusion: *"The patch_size was 1022! So it was working, just not showing in get_status for some reason."*
5. **`fastapi_14099` (wrong-content, never submitted)** — 489 s, 5 gold files, last event is raw tool-call text inside thinking (`call:read_file{...fastapi/routing.py...}`) while still exploring; no final message, no submit.
6. **`requests_6757` (no-patch)** — 4 edits, **10 submit_patch calls**, all empty; ended with *"I've tried everything. I'll just stop here. The changes are in tox.ini."* Edits never landed and empty submits were never rejected.
7. **`fastapi_15661` (wrong-file)** — gold creates a new file `scripts/prepare_release.py` (`@@ -0,0`); agent made 0 edit_file calls, patch came from elsewhere, gold file never created. One of **0/11 new-file tasks solved**.
8. **`rich_4076` in `Outputs` (zero-tool)** — final message degenerated into a repetition loop: *"call submit_patch once more ... call submit_patch once more ..."* ×15. Zero registered tool calls; harness saw nothing.
9. **`v2_gate_out2` (5/5 zero-tool runs)** — final messages are literal text like `call:read_file{filepath:"rich/markdown.py",...}` or `call:submit_patch{}`. The model emitted tool syntax as prose; the harness registered 0 calls. Whole root is a write-off.
10. **`fastapi_14356` (wrong-content)** — single gold file, edited it, and last thought: *"I have **verified it with a reproduction script** and checked that it doesn't break existing behavior."* Own repro passed; hidden tests failed — self-written checks confirm the agent's own interpretation, not the gold behavior.

(Bonus: `fastapi_14419` no-patch — 27 calls, 487 s, all spent reading; last thought *"I'll use my last tool call to read `fastapi/dependencies/models.py`"* — never reached an edit. And `rich_3506` — *"Wait, I think I found it!"* at 483 s, time out.)

---

## (c) What we're obviously missing / should try next

1. **There is no verification gate — submission is treated as success.** 43/62 wrong-content runs end with "patch submitted successfully" and zero falsification; only 12.4% of all runs ever execute a test command. The A3 rules optimize *form* (status, one edit, one submit) but never require *evidence*. **Try:** make `submit_patch` require a prior command that exercises the changed code (or return a free warning listing the gold-relevant test files), and reframe the prompt: "submission ≠ success; hidden tests judge; state what you ran and what it showed."
2. **Multi-file / large gold patches are structurally unsolvable right now (3/38, 2/44 in top size tercile, 0/11 new-file).** The ONE-edit rule plus single-shot submit biases agents to a one-file patch. **Try:** before editing, force the agent to enumerate *every* file implicated by the problem statement (checklist in the final message), allow multiple edit_file calls when the statement spans files, explicitly permit creating new files via `run_command` (heredoc/`cat >`), and say so in the prompt.
3. **Locate overrun is the dominant no-patch cause (16/27 never edited, 15 of them dying at the 480 s wall still reading; only 13/129 met the ≤4-call locate rule).** **Try:** hard deadline — e.g. harness injects a nudge at call 10 ("you have not edited anything; commit to a hypothesis now"), or `get_status` returns `locate_calls_used` with a red warning >8. Threshold data: locate≤8 → 39% solve vs 19%.
4. **Empty patches pass silently.** 10 runs called edit+submit and shipped `patch_size: 0` without noticing. **Try:** `submit_patch` should refuse an empty diff with a free error ("your last edit did not land — show old_string exactly"), and `edit_file` failures should be impossible to sleepwalk past (auto-`get_status` after each edit is free anyway).
5. **Churn is anti-predictive: less thinking, fewer reads, earlier first edit win.** <15 k thinking 40% vs 20%; ≤3 reads 42% vs 18%; first edit ≤8 calls 39% vs 21%; <250 s 40% vs 18%. **Try:** flip the prompt from "locate in ≤4 calls then edit" (obeyed by only 13/129) to a *budgeted* form: max 3 reads / 8 calls before the first edit, then iterate; discourage open-ended re-reading.
6. **Text-mode tool calls waste entire runs (10/480, whole roots like `v2_gate_out2`).** **Try:** detect `call:tool{...}` patterns in final/agent text and either parse them into real calls or inject one corrective nudge; add a repetition-loop breaker for degenerate finals.
7. **Don't over-read the compliance stats we already have** — first-tool choice, edit-count, patch size, and ran-tests-boolean do *not* differentiate. The differentiators to instrument next are: gold-file coverage (can be approximated at runtime by checking which problem-statement-mentioned files were touched), locate length, and time-to-first-edit.

---

## (d) What we could NOT determine from the traces

- **Pass/fail for the 351 non-129-run traces.** No labels exist anywhere locally (logs are 0 bytes, no run_rows for those roots). All outcome-split stats above are the 129-run only; other roots contribute unlabeled behavior aggregates.
- **The agent's actual patch text.** `submit_patch` arguments are empty; observations only return `patch_size`/`files_changed`. We cannot diff agent patch vs gold or say *how* the content differed (alternative fix vs partial vs off-by-one).
- **Which hidden test failed, or whether self-run tests passed.** Test output exists inside `run_command` observations but was not parsed at scale (and hidden-test results are never in traces).
- **Semantics of compliance `locate`** (not documented; ≠ `first_edit_at_call`, 0/129 equal). Treated as "calls spent locating" as given.
- **Why 3 resolved runs never touched a gold file** — notably `fastapi_14851` resolved with `patch_chars=0` (tests likely already pass / task trivially green), plus `requests_6644`, `rich_3043`.
- **Causal direction among churn metrics** (duration ↔ reads ↔ thinking ↔ budget warnings are collinear) and whether E4B's get_status-first behavior (79/88) helps — no labels for those runs.
- **Whether the 9 wrong-content runs that ran tests ran the *right* tests** — not checked observation-by-observation (qualitative cap).
