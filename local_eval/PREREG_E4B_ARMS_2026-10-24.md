# PRE-REGISTRATION — E4B prompt arm sweep, 2026-10-24

Written and timestamped BEFORE the first run is launched. Nothing below may be edited
after the sweep starts; any change goes in a new dated section.

## Question
Does any prompt arm beat A3 on E4B's dominant, measurable failure mode?

## Why these arms (evidence, all measured from the local trace corpus this session)
Corpus: 194 trace files, 16,650 tool calls, 2,540 errors, 1,059 (tag,task) run pairs.

1. **edit_file is the failure centre.** 2,990 calls, 1,849 errors (62%).
   Signatures: anchor-not-found 1,604 (65% of all errors); missing-mandatory-param
   (the delimiter class A3 fixed) 170; empty error text 309 (run_command).
2. **Anchor length predicts failure WITHIN task**, so it is not a task-difficulty
   confound. Pooled: single-line anchors 572/1,090 = 52.5% succeed;
   multi-line 548/1,591 = 34.4%. Within rich_3043, successful anchors have median
   11 chars vs 326 for failures.
3. **Half of post-failure edit_file calls re-send the identical anchor** (790 retry
   vs 786 fresh). A retried anchor succeeds 11.5%; a fresh one 61.3%.
4. A3 already tells the model twice never to re-send an identical failing call
   (lines 46 and 55) and the behaviour persists, so a third exhortation is not
   the test — a hard format constraint is.

## Arms (all SUBSTITUTIONS into A3, never appends; verified byte-identical elsewhere)
| Arm | Prompt file | sha256[:12] | Changed axis |
|---|---|---|---|
| A3  | prompts/e4b_A3_delim.md       | 178bc00db239 | control (untouched) |
| D2  | prompts/e4b_D2_checklist.md   | e59df9475766 | structure / STOP gates (11 lines differ) |
| A19 | prompts/e4b_A19_shortanchor.md | ea421252960c | "kept SHORT and UNIQUE" -> hard ONE-line, <=80-char constraint (+174 chars) |

A19 is NOT a repeat of A18. A18 tested copy-fidelity (a worked example teaching
copy-don't-retype) and NULL'd on resolves at n=8. A19 tests anchor LENGTH, which
A18 never isolated and which the corpus shows predicts failure within task.

## Design
- Cohort: **rich_2725 + rich_2943** — the two tasks the log identifies as carrying
  the signal (L12342: "rich_2725 and rich_2943 carry the signal").
- n: **18 reps per arm** (the n the log pre-registered for the D2 replication, L12348).
- 3 arms x 18 reps x 2 tasks = 108 runs. Arms interleaved by rep by sweep.py, so
  wall-clock drift is balanced across arms rather than confounded with them.
- Serial (`--conc 1`) and `--isolate` (per-run git worktree) — both on by default.
- Budgets match the shipped config: max_tool_calls 28, max_time 480s, thinking on,
  temp 0.2, 9-tool surface.

## PRIMARY metric (decided in advance)
**Per-run edit_file failure rate** = edit_file errors / edit_file calls, computed per
run from the trace, then compared arm-vs-A3 with a **run-level permutation test**
(two-sided, alpha 0.05, 20,000 shuffles). Run-level, not per-call: errors cluster
inside looping runs, which is exactly the mistake that produced the retracted
D-arm p-values.

## GUARDS (must all hold, or the arm is rejected regardless of the primary)
1. Corruption rate (missing-mandatory-param class) must not rise above A3's.
   A3 drove it to ~0.006; a rise means the arm displaced A3's win, as A4 did.
2. Landed edits per run must not decline.
3. Fresh-anchor success rate must not decline (an arm must not "improve" the rate
   merely by making fewer attempts).
4. Resolve rate is REPORTED, never the decision metric — E4B resolves ~3/44 and
   cannot resolve a one-task delta at this n.

## Known measurement hazards (handled, not ignored)
- **gate_run has silent false positives.** Its shared-env verifier can fail to apply
  the test patch, pass 91 unrelated tests, and report resolved=True (rich_3777 was
  exactly this). Every resolve number below is therefore PROVISIONAL until
  re-scored with `rescore_pinned.py`. The primary metric is computed from traces
  and is unaffected.
- **Infra deaths.** 17.7% of runs in an earlier cohort died at call 0-1 with
  chat_error and error=None. Those are excluded from the primary and COUNTED, not
  silently dropped.
- **Diff cap.** gate_run stores diff[:8000]; patches above that are truncated on
  disk. Patch-size claims are capped accordingly.
- **Local != Kaggle.** The arch remap is required locally; out_k_e4ba3's 2/44 had no
  remap and is a serving-degraded number, not clean E4B+A3.

## What a win would and would not mean
A primary win + all guards = adopt the arm for the E4B submission and re-validate on
a wider cohort. It would NOT establish a board score: local E4B serving differs from
Kaggle, and the $10k small-model prize is decided on the private test set.

---

## ADDENDUM, 2026-10-24 (after the sweep started — new section, nothing above edited)

**1. A tag collision nearly destroyed the control baseline. Caught before any loss.**
`sweep.py` built its per-run tag as `f"{arm}_r{rep}_{task}"`, with no sweep name. A new
sweep therefore writes the same filenames as any earlier sweep sharing an arm name, and
`run_one` unlinks the previous results/guard files at the start of each run. The new
sweep had begun overwriting `A3_r*_rich_2725` — the 23-run pooled-A3 control baseline
that the D-arm retraction rests on. Stopped after 2 files; verified the baseline is
INTACT (23 distinct (task,rep) pairs, D2's 27 files untouched, the r0 stall snapshot
surviving). Fixed by prefixing the tag with `--name`; backup at `sweep.py.bak-2026-10-24`.
Lesson: the earlier tag-uniqueness fix (L195-197) made the tag unique per task but not
per sweep.

**2. `driver_exception:RuntimeError` is now the majority label, not 17.7%.**
5 of the first 6 runs carry it. It is NOT an infra death and it does NOT truncate the
run: the traces are complete (e.g. D2 r0 rich_2943 has 59 records, an `end` record with
`end_reason=call_cap`, 29 turns, 28 calls) and the diffs are saved. The exception is
thrown by the post-run verification step — the known gate_run shared-env verifier
problem the log already flags as making every resolve number provisional. So:
  * the PRIMARY metric (computed from traces) is unaffected;
  * the resolve flag is unusable until `rescore_pinned.py` re-scores the saved diffs;
  * the jump from 17.7% to ~83% is most likely because the arch remap makes E4B attempt
    far more edits, giving the verifier more chances to fail. UNVERIFIED.

**3. Early numbers are NOT a result.** n=2-3 per arm. A3's 0.0% edit_file failure rate
rests on 1-2 edit_file calls total. No conclusion until n=18/arm.
