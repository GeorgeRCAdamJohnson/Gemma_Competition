VERDICT: REJECT

Mode: AUDIT · slug `max-tool-calls-28-to-50` · date 2026-10-14
Proposal: `Gemma\kb\proposals\2026-10-11-max-tool-calls-28-to-50.md`
KB: FRESH (`python Gemma\kb\build_kb.py check-fresh` → `FRESH`, exit 0); inputs_fingerprint
`bf50f179e4c1d50ff385d887120e89843a9a963c61d85a0130c8384424859959`; newest input
`GEMMA_EXPERIMENT_LOG.md` @ 2026-10-15T02:33:19Z.

---

## 1. Suggestion restated

On the v6b config (`Gemma\submit_v6b`: 28 calls / 8 min / 240 s timeout / thinking 4096 / no `edit_file`,
edits via `run_command` python-replace), change **only** `max_tool_calls` 28 → 50. Rationale: v6b's two hard
rich nulls (rich_4070, rich_4079) ended at the call wall, rich_4079 having reached `rich/markdown.py` around
call 24. The proposal asks the audit to settle four things: (a) did those two runs end with an edit the harness
refused at the wall, and would it have passed; (b) is two budget points on two tasks at n=1 enough to call the
lever dead; (c) does 50 calls fit inside `max_time_minutes: 8` / 240 s per-call; (d) prior art for every version
that moved `max_tool_calls` / `max_turns` / `max_time_minutes`, plus the risk to the always-solved rich_4077.

The proposal is right about one thing and I confirm it up front: the A/B that killed this idea
(`GEMMA_EXPERIMENT_LOG.md:L6817` "v21 vs v6b — BUDGET A/B … 'more budget' is FALSIFIED") is **not** a
one-variable A/B, and the log itself already carries that correction (`GEMMA_EXPERIMENT_LOG.md:L9287-9290`,
"v21-vs-v6b changed ≥5 variables at once … it is not a one-change budget A/B"). The verdict below does not
rest on that entry. It rests on an earlier, cleaner experiment the proposal never cites, on the gold patches,
and on the two refused calls themselves.

---

## 2. Prior art — tag: **RE-RUN (of the >28-call regime), already measured as a regression**

| ver | call/time budget | result | source |
|---|---|---|---|
| v1 | 25 calls / 5 min | 0/6, rich_4077 = 0 patch | `GEMMA_EXPERIMENT_LOG.md:L520-524` MEASURED |
| **v2** | **25→40 calls + max_turns 50**, 5 min | **1/6 → 0/6 REGRESSION; rich_4079 TIMEOUT @40 calls/309 s; rich_4076 TIMEOUT @34 calls/303 s, no submit; fastapi_15661 TIMEOUT, no submit** | `GEMMA_EXPERIMENT_LOG.md:L596-612` MEASURED |
| v3/v5 | 15 → 22 calls | 1/6; "15-call ceiling confirmed" | `GEMMA_EXPERIMENT_LOG.md:L151-170` (version table) MEASURED |
| v10-v14 | **40 calls / turns 60** | v10 "2/10" **RETRACTED**; committed kernel = **0/10** on the same code + same 10 tasks + same eval_config | `GEMMA_EXPERIMENT_LOG.md:L4742-4775` MEASURED |
| v15/v16 | 12 / 15 calls | 1/5 each; "budget/prompt tuning EXHAUSTED as a lever" | `GEMMA_EXPERIMENT_LOG.md:L151-170` MEASURED |
| v6b / v6w / v21 | 28 / 28 / 15 | v6b 1/6, v6w 4/6 + LB 0.15, v21 2/5 | `Gemma\kb\runs.jsonl`; `Gemma\kb\curated\submissions.csv` MEASURED |

Two findings dominate the prior art:

- **A2 (MEASURED).** The v2 experiment is exactly this lever and it regressed: "Raising max_tool_calls 25->40 +
  max_turns 50 let the agent THINK/EXPLORE longer, which pushed nearly every task INTO the 5-min timeout. A
  timeout = no clean submit = 0 resolves." (`GEMMA_EXPERIMENT_LOG.md:L604-607`). Per-task, **rich_4079 and
  rich_4076 — two of the proposal's own targets — are the tasks that timed out** at 40 and 34 calls. It also
  moved `max_turns`, so it is not single-variable either; but its *mechanism* (call cap removed → run drifts
  into the time wall → no clean submit) is the mechanism this proposal would re-create.
- **A3 (MEASURED).** The only pro-budget datum in the project is retracted. `GEMMA_EXPERIMENT_LOG.md:L4742`:
  "CRITICAL — v10 '2/10' IS NOT REPRODUCIBLE … SAME eval_config (max_tool_calls 40, turns 60) — verified …
  RETRACT 'budget 22->40 is the confirmed lever / mechanism-confirmed'." Same entry records a
  **measurement-validity defect that bites this proposal directly**: the committed/batch scoring environment is
  systematically slower per step than the interactive draft environment, so every per-task duration we reason
  about is optimistic (`L4766-4772`).

A RE-RUN needs a stated reason the earlier result does not apply. The proposal gives none for v2 or for the
v10 retraction, because it does not cite them.

---

## 3. Ground truth per task (gold patch + test_patch; diagnosis only)

- **rich_4070** — `Gemma\kb\tasks_gold.json` (tasks.rich_4070), base `fc41075a`: title *"perf: reduce Console
  and RichHandler import time by deferring unused imports"*. **9 files, 33 hunks, +71/−57 lines**,
  `difficulty.kb_mech_class = HARD`. Tests: `tests/test_console.py`, `tests/test_syntax.py`. The gold does not
  merely delete imports — it *defers* them, e.g. it adds a nested wrapper
  `def is_expandable(obj) -> bool:` inside `console.py` that lazily imports from `.pretty`, and rewrites
  `isclass(renderable)` → `isinstance(renderable, type)` at the single call site (hunks 2-5). MEASURED.
- **rich_4079** — `Gemma\kb\tasks_gold.json` (tasks.rich_4079), base `19c67b9a`: title *"Inline table code"*.
  **1 file, 1 hunk, +4/−3** in `rich/markdown.py`, `kb_mech_class = EASY`. The gold replaces three lines of
  `on_text` with an `isinstance(text, str)` branch: `self.content.append(text, context.current_style)` else
  `self.content.append_text(text)`. The test_patch adds `test_inline_code_in_table_cells`, which asserts an
  exact ANSI string. MEASURED.
- **rich_4077** — the always-solve: 26/32 attempts resolved (`GEMMA_EXPERIMENT_LOG.md:L9245` recount; my own
  count from `B card --task rich_4077` agrees on the resolve pattern). MEASURED.

---

## 4. Behavior per task per run (the two refused calls the proposal hangs on)

**rich_4070, run `submit_v6b/out_v6b`** (`Gemma\submit_v6b\out_v6b\results\traces\trace_rich_4070.json`):

- `step_id=31` — `get_status` returns, verbatim: `tool_calls_used: 28, tool_calls_remaining: 0,`
  **`time_seconds_remaining: 250.74`**, `agent_elapsed_seconds: 229.26`. MEASURED.
  → **A1: the call wall did bind first on this task, with 52 % of the 480 s time budget unused.** The
  proposal's factual premise here is correct and I confirm it.
- `step_id=30` — the model writes a **16-item** edit plan covering `rich/console.py` only (1 of the gold's 9
  files). MEASURED.
- `step_id=32` — a `run_command` python-replace **was** issued and refused:
  `{"status":"error","error_type":"BudgetExceeded","error_message":"Tool call budget exhausted (28 calls)"}`.
  MEASURED. So "made no edit attempt" is false (agrees with the prior refute A5,
  `GEMMA_EXPERIMENT_LOG.md:L9239-9242`).
- **A4 (MEASURED, from the call's own argument text):** that refused command would have *corrupted* the file.
  It contains the model's own in-line admissions — `# Wait, this is wrong. is_expandable is a function.` and
  `# This is wrong syntax.` and `# I will just do the simple replacements and hope for the best.` — and it
  inserts `from .pretty import Pretty, is_expandable` **immediately after `def _collect_renderables(`**, i.e.
  inside the parameter list, then calls `p.write_text(s)`. It also blind-replaces
  `is_expandable(renderable)` → `isinstance(renderable, type)`. Granting call 29 writes a syntactically invalid
  `rich/console.py`.
- Near-miss (`Gemma\kb\near_miss.jsonl`, row `submit_v6b/out_v6b::rich_4070`): `TRIED_APPLY` call 30 /
  step_id 32; `APPLIED` false; `stopped_by` REFUSED_CALLS; `WROTE_GOLD_CHANGE` reached at call 28 / step_id 30
  **with `where: "text"` and `hunk: 26`** — a prose-channel match on **1 of 33 hunks**. Per my own heuristic
  caution, a `where: text` hit is not an edit and 1/33 hunks is not a fix. MEASURED value, INFERRED weight.

**rich_4079, run `submit_v6b/out_v6b`** (`...\traces\trace_rich_4079.json`):

- `step_id=29` observation carries `budget_warning: "Only 1 tool call(s) remaining (27/28 used)"`; `step_id=30`
  is a ranged `read_file` on `rich/markdown.py` 640-670; `step_id=31` is an edit-bearing `run_command` refused
  with `BudgetExceeded`; `step_id=32` is an empty `submit_patch` (`patch_size: 0`). MEASURED.
- Near-miss row: `READ_GOLD_FILE` call 24 / step_id 26, `SAW_GOLD_HUNK` call 25 / step_id 27, `TRIED_APPLY`
  call 29 / step_id 31, **`WROTE_GOLD_CHANGE` NOT reached**, `stopped_by` REFUSED_CALLS. MEASURED.
- **A5 (MEASURED, gold-vs-call comparison):** the refused call's NEW text sets
  `self.content = Renderables()` in `__init__` and `self.content.append(text)` in `on_text`. The gold keeps the
  `Text` content and adds the `isinstance(text, str)` branch with `append(text, context.current_style)`. The
  refused edit is **in the right file and the right function but is not the gold change**, which is why nm-3
  scores `WROTE_GOLD_CHANGE = false` while still crediting SAW_GOLD_HUNK.
- **A6 (MEASURED static + authored control):** as issued, that command is also Python-invalid. Its argument
  contains 0 raw newlines and 6 `\"` sequences inside `python3 -c '…'`, so the interpreter would see
  `OLD = \"    def __init__…`. I compiled my own synthetic control (not trace content):
  `compile('OLD = \\"abc\\"')` → `SyntaxError: unexpected character after line continuation character`, while
  `OLD = "abc"` compiles. So granting call 29 here most likely yields a shell/Python error, not a patch.
  (`Gemma\kb\KB_SUMMARY.md` §13 shows the KB's *static* reconstruction "applied" — the reconstruction bypasses
  the shell, so it does not contradict this.)

---

## 5. Failure classification (§10 definitions)

- `submit_v6b/out_v6b::rich_4070` → **FOUND-NOT-LANDED / REFUSED_CALLS** (`Gemma\kb\runs.jsonl`). Decided by
  the refused structured call at step 32 (`BudgetExceeded`) plus the empty submit at step 33. MEASURED.
- `submit_v6b/out_v6b::rich_4079` → **FOUND-NOT-LANDED / REFUSED_CALLS** (same basis, step 31 refusal, empty
  submit at step 32). MEASURED.
- `submit_v6b/out_v6b::rich_4077` → **RESOLVED**, 13 calls / 168 s — i.e. the always-solve finishes at less
  than half the current cap, so it gains nothing from a larger cap and can only lose. MEASURED.
- `Outputs/v11::rich_4077` → 40 calls, **0 patch chars**, 304.8 s, unresolved (`Gemma\kb\runs.jsonl`) — the
  always-solve breaking inside the 40-call regime. MEASURED (log-pasted row, no trace → no subclass).
- `Outputs/v14::rich_4070` → 33 calls, 5 138 chars, unresolved; `submit_v6z_on_v6w/hard/out::rich_4070` → 26
  calls, 3 806 chars, **WRONG-FIX**. rich_4070 is 0/13 across every config in the KB. MEASURED.

---

## 6. Replays / tests run (command + result)

| command | result |
|---|---|
| `python Gemma\kb\build_kb.py check-fresh` | `FRESH`, exit 0 |
| `python Gemma\kb\build_kb.py report-path --date 2026-10-14 --slug max-tool-calls-28-to-50 --kind audit` | this path, exit 0 |
| `python Gemma\kb\build_kb.py card --task rich_4070 / rich_4079 / rich_4077` | full run histories; 4070 = 0/13, 4079 = 6/32, 4077 = 26/32 |
| `python Gemma\kb\build_kb.py claims --text "budget\|tool_calls\|calls"` | 66 rows; the budget-lever entries are `C76ad8eeec402` (v2 regression, SUPPORTED), `C1d064447c797` (v10 non-reproducible, UNVERIFIED), `C5c2daceb4bfa` (the v21-vs-v6b "falsified" verdict, UNVERIFIED) |
| per-call timing scan over `Gemma\kb\runs.jsonl` (227 rows with both duration and tool_calls) | rows with ≥20 calls: **median 10.2 s/call, mean 10.9, p90 13.9, max 24.3**. All-row durations: median 216.8 s, **max 485.2 s; 7 rows ≥480 s** |
| static argument analysis of trace steps 4070#32 and 4079#31 (no execution) | 4070#32: 35 raw newlines, valid shell quoting, self-admitted wrong Python; 4079#31: 0 raw newlines, 6 `\"` → invalid Python |
| authored control `compile('OLD = \\"abc\\"')` | `SyntaxError: unexpected character after line continuation character` |
| `leakcheck --scope config <proposal>` | **exit 1** — 3 bare task-id hits (rich_4077/4079/4070) in the proposal prose |
| `leakcheck --scope tooling <proposal>` | `LEAKCHECK CLEAN`, exit 0 |
| KB replay table (`KB_SUMMARY.md` §13) for the two counterfactuals | rich_4070 v6b counterfactual: "no reconstructable change (python-replace@step32:BASH_ERROR)"; rich_4079 v6b counterfactual: "applied; **gold not valid locally (INVALID)**" → **no replay verdict is available for either task**; `replays_pending=0` |

No new replay was run: §13 records gold-first = N (INVALID) for both rich_4070 and rich_4079, so a replay
cannot adjudicate "would it have passed". The gold-vs-argument comparison in §4 is the available evidence.

---

## 7. Variance

- **The only same-config replicate pair in the KB flips 20 % of its tasks.** `Outputs/v10` vs
  `_v10_kaggle_pull` — same code, same 10 tasks, same `eval_config` (40 calls / 60 turns), verified in
  `GEMMA_EXPERIMENT_LOG.md:L4744-4746`: rich_4077 `True 287.8 s 29c` → `False 302.3 s 35c 0ch`; rich_4079
  `True 277.1 s 33c` → `False 305.3 s 33c 1847ch`. MEASURED.
- rich_4079 at n=1 per config resolves 6/32 overall and at call counts 21, 26, 26, 28, 33, 38 while failing at
  24, 25, 26, 28, 28, 28 — **resolution is not ordered by call count** (`B card --task rich_4079`). MEASURED.
- rich_4070: 0/13, across 6-33 calls and 34-354 s. MEASURED.
- Consequence (INFERRED): a 5-task, n=1 free gate cannot distinguish a budget effect from this noise floor.
  The proposal names no replicate count and no null to beat.

---

## 8. Rules check

- **Baseline / live-best.** `.kiro\steering\gemma-submission-protocol.md` now states **v6w @ 0.15 (submission
  57098497)**, matching `Gemma\kb\curated\submissions.csv` and `curated\run_labels.json:baseline`. Two
  **stale-baseline findings to surface, not adopt**: (i) `Gemma\kb\KB_SUMMARY.md`'s BASELINE banner still says
  "gemma-submission-protocol.md still says v6 @ 0.12 and is STALE" — the steering file has since been updated,
  so the banner's claim is itself out of date; (ii) the log's standing-truth block
  (`GEMMA_EXPERIMENT_LOG.md:L25`, bullet 4) still says "LIVE-BEST = v6 @ 0.12 (SACRED)". The external fact is
  v6w @ 0.15. MEASURED.
- **Rule 15, floor-guaranteed composition — VIOLATED.** The proposal builds on v6b. v6b is a measured
  **regression**: 1/6 against v6's 2/6 on the identical 6-task sample, per the log's own correction
  (`GEMMA_EXPERIMENT_LOG.md:L9280-9282`, "v6b (1/6) was a REGRESSION vs v6, not a lateral null"). And v6b is
  not one change from the live-best: `Gemma\submit_v6b\out_v6b\submission\agent.yaml` exposes **7 tools, no
  `edit_file`/`write_file`**, while `Gemma\submit_v6w\out_v6w\submission\agent.yaml` exposes **9 with
  `edit_file` + `write_file`**; thinking budget also differs (4096 vs 1024). Both `eval_config.yaml` files are
  byte-equal (28 / 8 / 80 / 240), so the call cap is the *only* budget field that differs — which means
  "28→50 on v6b" is a 3-delta change versus the thing that actually scored 0.15. MEASURED.
- **One change per gate — VIOLATED as written** (see above). It would be one change if applied to v6w.
- **Rule 13, tune before concluding — the proposal is right to raise it, and it cuts both ways.** The lever has
  now been sampled at 12, 15, 18, 22, 25, 28 and 40 calls across v15/v16/v21/v3/v1/v6*/v2/v10-v14 with no
  monotone relationship to resolves, and the one apparent win at 40 is retracted. That is a swept knob, not a
  single point. MEASURED.
- **Rule 11 / 10, a gate failure is a debugging task, not a verdict on the idea.** Honoured here: I did not
  dismiss the idea on the discredited v21-vs-v6b entry. I went to the two refused calls to look for the
  execution bug blocking transfer — and found that the blocker is **not** the budget. On rich_4079 the model
  had the right file and function at call 24-25 and still composed a non-gold edit in a shell-invalid command;
  on rich_4070 the model composed a self-admittedly broken edit covering 1 of 9 files. Those are synthesis and
  serialization defects, and both are reachable with 28 calls. MEASURED.
- **Free gate first.** Not at issue — the proposal does not ask for the scored slot. But note the asymmetry in
  §9: the per-task risk this change creates is invisible on a 5-task gate and only materialises on the 129-task
  scored run.
- **Leakcheck.** `--scope config` trips on three bare task ids in the proposal's prose (exit 1);
  `--scope tooling` is clean. The shipped artifact for this change is a single integer in `eval_config.yaml`,
  so there is no leak vector in the submission itself — but no proposal prose may be copied into a prompt.
  MEASURED.

---

## 9. The cheapest falsifying test (run, offline)

The question "would the refused edits have landed the gold if granted?" is decidable offline by comparing the
refused calls' arguments to the gold hunks, without any Kaggle push. I ran it (§4, A4/A5/A6). It falsifies the
proposal's rationale on both targets:

- rich_4079: the refused edit is **not the gold change** (nm-3 agrees: `WROTE_GOLD_CHANGE` false) **and** is
  Python-invalid as issued.
- rich_4070: the refused edit is self-admittedly wrong and syntax-breaking, and addresses 1 of 9 gold files
  against 33 hunks.

Second test, on the proposal's question (c) — does 50 calls fit in 8 minutes? **Mixed, and it is the wrong
question.** For the two targeted tasks the call wall binds first (4070 had 250.7 s left at the wall; 4079 ran
8.8 s/call ⇒ ~440 s for 50 calls). For the population it does not: median 10.2 s/call at ≥20 calls ⇒ ~510 s for
50 calls against a 480 s cap, p90 13.9 s/call ⇒ the wall at ~34 calls, and 7 of 227 rows already terminate at
480-485 s. MEASURED. The structural consequence (INFERRED, and the thing the proposal misses entirely):
**`max_tool_calls: 28` is currently the de facto governor of per-task wall-clock**, and the fastapi half of the
scored set is the slowest per call measured (13.8 s/call on fastapi_15661, 30.4 s/call on fastapi_15588). The
log records the host's statement that the 12 h global budget currently **errors the whole submission**
(`GEMMA_EXPERIMENT_LOG.md:L196-206`, second-hand from a forum thread, host "planning a fix", unconfirmed). Also
unresolved per `L4766-4772`: the committed scoring environment is slower per step than the dev environment we
measure in. Raising the cap to 50 therefore trades a bounded per-task loss for an unbounded whole-run risk
against a live-best of 0.15.

---

## 10. Verdict rationale — REJECT

Three independent grounds, any one of which is sufficient:

1. **The counterfactual it is built on is false.** The two refused calls were not "a good edit one call short".
   rich_4079's was in the right function with non-gold content and shell-invalid escaping; rich_4070's was
   self-admittedly wrong, syntax-breaking, and 1 of 9 files. Granting call 29 produces a wrong or broken patch,
   not a resolve. That is the same "no commit → wrong commit" lateral the log already recorded for rich_4076
   (`L6830`) and that rich_4070 reproduces at 26 and 33 calls (3 806 and 5 138 chars, both unresolved).
2. **It is a RE-RUN of a measured regression with no stated reason the earlier result does not apply.** v2
   raised the same field (25→40) and went 1/6 → 0/6 by pushing tasks into the time wall, with rich_4079 and
   rich_4076 among the timeouts (`L596-612`); the one apparent win at 40 calls (v10) is retracted as
   non-reproducible under the same eval_config (`L4742-4760`).
3. **It is not one change from the live-best, and its base is a known regression.** v6b = 1/6 vs v6 = 2/6 on the
   identical sample, 7 tools without `edit_file`, thinking 4096. The live-best is v6w @ 0.15. Rule 15 forbids
   layering onto a regressed base; rule "one change per submission" forbids the 3-delta bundle.

No pre-registered bar is issued (bars accompany PROCEED only).

For the record, what a non-rerun version of this question would look like, if the user wants to pursue it: it
is **not** a global cap raise. The data points at a *conditional* extension — the signal the log already
identified (`L6855-6861`, `first_edit_at`) plus the free `get_status` the agent already calls: extend only when
the agent has banked a non-empty patch and the remaining time can pay for the extra calls, so the always-solve
and the fastapi sink are untouched and the per-task wall-clock stays bounded. That is a different proposal,
with a different mechanism, and it needs its own audit. It also inherits the §7 problem: with rich_4079 at
6/32 and the one replicate pair flipping 2 of 10, any such gate needs a replicate plan, not n=1.

---

## 11. What the suggestion missed

1. **The v2 experiment** (`L596-612`) — the same field, the same direction, a measured 1/6 → 0/6, with
   rich_4079 and rich_4076 timing out at 40 and 34 calls. The proposal cites only the discredited v21-vs-v6b
   entry and concludes the lever is therefore open.
2. **The v10 retraction** (`L4742-4775`) — "budget 22→40 is the confirmed lever" is explicitly retracted, and
   the same entry records that our dev durations are optimistic relative to the scoring environment.
3. **The content of the refused calls.** The proposal asks whether they would have passed but reads them as
   "an edit the harness refused". Both carry their own defeat: a non-gold replacement plus invalid escaping
   (4079), and self-admitted wrong logic that writes an unparsable file (4070).
4. **rich_4070's gold shape.** 9 files, 33 hunks, +71/−57, HARD, and a *deferral* pattern (nested lazy-import
   wrapper), not the import deletions the model planned. 22 extra calls do not close that, and the model's own
   plan covered 1 file.
5. **The 129-task consequence.** `max_tool_calls` is also the per-task wall-clock governor. 7 of 227 recorded
   rows already end at the 480-485 s time wall; fastapi is 13.8-30.4 s/call; the 12 h global cap reportedly
   errors the whole submission. The free gate cannot see this risk.
6. **rich_4077's exposure.** It resolves at 13 calls under v6b and 21 under v6w, so it cannot gain from a
   higher cap; and it has already broken inside the 40-call regime once (`Outputs/v11::rich_4077`: 40 calls,
   0 chars) and once in the v10 replicate (35 calls, 0 chars, 302 s).
7. **The baseline.** The proposal targets v6b, a 1/6 regression, as if it were the current base; the live-best
   is v6w @ 0.15 (`curated\submissions.csv`, submission 57098497).

---

## 12. Measured vs inferred

**MEASURED** — every table and quote above with a path: the two refused calls and their arguments and
observations (trace step_ids 30/31/32/33 for rich_4070, 29/30/31/32 for rich_4079); `time_seconds_remaining
250.74` at the rich_4070 call wall; near-miss stages and `stopped_by` for both; both gold entries
(file/hunk/difficulty/test) from `tasks_gold.json`; the per-call timing distribution over 227 `runs.jsonl`
rows; the v2 and v10 log entries and their per-task tables; the v6b/v6w `agent.yaml` and `eval_config.yaml`
contents; the KB §13 replay rows showing gold INVALID locally; the leakcheck exit codes; the
`submissions.csv` scores.

**INFERRED** — (a) that granting call 29 on rich_4079 would have errored in the shell (static escaping analysis
plus an authored `compile()` control; not executed against the trace, per the hard limit); (b) that granting
call 29 on rich_4070 would have written an unparsable `console.py` (static reading of the command's own
replacements); (c) the 129-task wall-clock extrapolation and the 12 h error risk (built on a 6-task gate
sample, a second-hand host statement, and a dev-vs-scoring latency gap the log itself flags as unquantified);
(d) that a 5-task n=1 gate cannot resolve a budget effect at this noise floor.

**UNVERIFIABLE** — "would the refused edit have passed the hidden tests?" cannot be settled by replay: gold-first
fails locally for both rich_4070 and rich_4079 (`KB_SUMMARY.md` §13). My answer rests on the gold-vs-argument
comparison, not on a replay, and I do not claim a replay verdict.

<!-- AUDIT-JSON
{"schema": "gemma-audit/1", "mode": "AUDIT", "verdict": "REJECT",
 "proposal": "c:\\Users\\Biges\\OneDrive\\Documents\\Desktop\\kAGGLE\\Gemma\\kb\\proposals\\2026-10-11-max-tool-calls-28-to-50.md",
 "kb_inputs_fingerprint": "bf50f179e4c1d50ff385d887120e89843a9a963c61d85a0130c8384424859959",
 "targets": ["rich_4070", "rich_4079", "rich_4077"],
 "prior_art": [{"lever": "max_tool_calls raise (25->40) + max_turns 50 (v2)", "tag": "RE-RUN", "runs": ["Outputs/v15", "Outputs/v14"]},
               {"lever": "40-call regime v10-v14 (retracted 2/10; committed 0/10)", "tag": "RE-RUN", "runs": ["Outputs/v10", "_v10_kaggle_pull", "Outputs/v11", "Outputs/v12_v2", "Outputs/v14"]},
               {"lever": "28-call regime (v6b/v6w/v6c/v6t)", "tag": "VARIANT", "runs": ["submit_v6b/out_v6b", "submit_v6w/out_v6w", "submit_v6c/out_v6c", "submit_v6t/out_v6t"]},
               {"lever": "15-call regime (v21)", "tag": "VARIANT", "runs": ["submit_v21/out_v21"]}],
 "per_task": [{"run_id": "submit_v6b/out_v6b", "task": "rich_4070", "failure_class": "FOUND-NOT-LANDED", "subclass": "REFUSED_CALLS",
                "evidence": ["Gemma\\submit_v6b\\out_v6b\\results\\traces\\trace_rich_4070.json#step_id=31", "Gemma\\submit_v6b\\out_v6b\\results\\traces\\trace_rich_4070.json#step_id=32", "Gemma\\kb\\near_miss.jsonl#row_id=submit_v6b/out_v6b::rich_4070"]},
              {"run_id": "submit_v6b/out_v6b", "task": "rich_4079", "failure_class": "FOUND-NOT-LANDED", "subclass": "REFUSED_CALLS",
                "evidence": ["Gemma\\submit_v6b\\out_v6b\\results\\traces\\trace_rich_4079.json#step_id=31", "Gemma\\kb\\near_miss.jsonl#row_id=submit_v6b/out_v6b::rich_4079"]},
              {"run_id": "submit_v6b/out_v6b", "task": "rich_4077", "failure_class": "RESOLVED", "subclass": null,
                "evidence": ["Gemma\\kb\\runs.jsonl#row_id=submit_v6b/out_v6b::rich_4077"]},
              {"run_id": "Outputs/v11", "task": "rich_4077", "failure_class": "FOUND-NOT-LANDED", "subclass": "NO_TRACE",
                "evidence": ["Gemma\\kb\\runs.jsonl#row_id=Outputs/v11::rich_4077"]}],
 "claims": [{"id": "A1", "text": "v6b rich_4070 died on the CALL wall with 250.74s of 480s time remaining (get_status at step 31) - the proposal's premise on this point is correct.", "basis": "MEASURED", "evidence": ["Gemma\\submit_v6b\\out_v6b\\results\\traces\\trace_rich_4070.json#step_id=31"]},
            {"id": "A2", "text": "v2 raised max_tool_calls 25->40 and regressed 1/6 -> 0/6 by pushing tasks into the time wall; rich_4079 (40 calls) and rich_4076 (34 calls) both TIMEOUT.", "basis": "MEASURED", "evidence": ["Gemma\\GEMMA_EXPERIMENT_LOG.md#L596-612"]},
            {"id": "A3", "text": "The only pro-budget result (v10 2/10 at 40 calls) is RETRACTED: the committed kernel run of the same code/tasks/eval_config scored 0/10.", "basis": "MEASURED", "evidence": ["Gemma\\GEMMA_EXPERIMENT_LOG.md#L4742-4760"]},
            {"id": "A4", "text": "The refused rich_4070 edit would corrupt console.py: it inserts an import inside 'def _collect_renderables(' and carries the model's own 'this is wrong syntax' comments.", "basis": "MEASURED", "evidence": ["Gemma\\submit_v6b\\out_v6b\\results\\traces\\trace_rich_4070.json#step_id=32"]},
            {"id": "A5", "text": "The refused rich_4079 edit is in the gold file+function but is NOT the gold change (Renderables()/append vs gold's isinstance branch); nm-3 WROTE_GOLD_CHANGE=false.", "basis": "MEASURED", "evidence": ["Gemma\\submit_v6b\\out_v6b\\results\\traces\\trace_rich_4079.json#step_id=31", "Gemma\\kb\\tasks_gold.json#tasks.rich_4079", "Gemma\\kb\\near_miss.jsonl#row_id=submit_v6b/out_v6b::rich_4079"]},
            {"id": "A6", "text": "That same command is Python-invalid as issued (6 backslash-quote sequences, 0 raw newlines); an authored compile() control shows the pattern is a SyntaxError.", "basis": "INFERRED", "evidence": ["Gemma\\submit_v6b\\out_v6b\\results\\traces\\trace_rich_4079.json#step_id=31"]},
            {"id": "A7", "text": "50 calls does not fit the 480s cap at the population median: 10.2 s/call at >=20 calls (p90 13.9) implies ~510s; 7 of 227 rows already end at 480-485s.", "basis": "MEASURED", "evidence": ["Gemma\\kb\\runs.jsonl"]},
            {"id": "A8", "text": "rich_4070 gold is HARD: 9 files, 33 hunks, +71/-57, a lazy-import deferral pattern; the v6b plan covered console.py only.", "basis": "MEASURED", "evidence": ["Gemma\\kb\\tasks_gold.json#tasks.rich_4070", "Gemma\\submit_v6b\\out_v6b\\results\\traces\\trace_rich_4070.json#step_id=30"]},
            {"id": "A9", "text": "v6b is a regression base (1/6 vs v6 2/6 on the same sample) and differs from the 0.15 live-best v6w by tool surface (7 vs 9, no edit_file) and thinking budget, not only by the call cap.", "basis": "MEASURED", "evidence": ["Gemma\\GEMMA_EXPERIMENT_LOG.md#L9280-9282", "Gemma\\submit_v6b\\out_v6b\\submission\\agent.yaml", "Gemma\\submit_v6w\\out_v6w\\submission\\agent.yaml", "Gemma\\submit_v6w\\out_v6w\\submission\\eval_config.yaml"]},
            {"id": "A10", "text": "The only same-config replicate pair in the KB (Outputs/v10 vs _v10_kaggle_pull, 40 calls) flips rich_4077 and rich_4079, so a 5-task n=1 gate cannot resolve a budget effect.", "basis": "MEASURED", "evidence": ["Gemma\\GEMMA_EXPERIMENT_LOG.md#L4744-4746", "Gemma\\kb\\runs.jsonl#row_id=_v10_kaggle_pull::rich_4079"]},
            {"id": "A11", "text": "Stale-baseline findings: KB_SUMMARY's banner calls the steering file stale but steering now says v6w @ 0.15; the log's READ-THIS-FIRST bullet 4 still says v6 @ 0.12.", "basis": "MEASURED", "evidence": ["Gemma\\kb\\KB_SUMMARY.md#L3", ".kiro\\steering\\gemma-submission-protocol.md", "Gemma\\GEMMA_EXPERIMENT_LOG.md#L25"]},
            {"id": "A12", "text": "No replay can decide 'would it have passed': gold-first is INVALID locally for both rich_4070 and rich_4079.", "basis": "MEASURED", "evidence": ["Gemma\\kb\\KB_SUMMARY.md#section-13"]}],
 "tests_run": [{"cmd": "python Gemma\\kb\\build_kb.py check-fresh", "result": "FRESH (exit 0)"},
               {"cmd": "python Gemma\\kb\\build_kb.py card --task rich_4070 | rich_4079 | rich_4077", "result": "rich_4070 0/13, rich_4079 6/32 (resolves at 21/26/26/28/33/38 calls, fails at 24/25/26/28), rich_4077 26/32"},
               {"cmd": "python Gemma\\kb\\build_kb.py claims --text \"budget|tool_calls|calls\"", "result": "66 rows; v2-regression claim SUPPORTED, v10-non-reproducible and v21-vs-v6b verdicts UNVERIFIED"},
               {"cmd": "per-call timing scan over Gemma\\kb\\runs.jsonl (227 rows)", "result": ">=20 calls: median 10.2 s/call, p90 13.9, max 24.3; durations max 485.2s, 7 rows >=480s"},
               {"cmd": "static argument analysis of trace_rich_4070.json#32 and trace_rich_4079.json#31 (no execution)", "result": "4070: 35 raw newlines, self-admitted wrong Python, import inserted inside a def signature. 4079: 0 raw newlines, 6 backslash-quote -> invalid Python"},
               {"cmd": "authored control: compile() of an assignment whose string literal is prefixed by a backslash-quote escape (synthetic, not trace content)", "result": "SyntaxError: unexpected character after line continuation character; the unescaped form compiles"},
               {"cmd": "python Gemma\\kb\\build_kb.py leakcheck --scope config Gemma\\kb\\proposals\\2026-10-11-max-tool-calls-28-to-50.md", "result": "exit 1: 3 bare task-id hits (prose only; the shipped change is one integer in eval_config.yaml)"},
               {"cmd": "python Gemma\\kb\\build_kb.py leakcheck --scope tooling Gemma\\kb\\proposals\\2026-10-11-max-tool-calls-28-to-50.md", "result": "LEAKCHECK CLEAN (exit 0)"}],
 "missed": ["The v2 experiment (L596-612): same field, 25->40, measured 1/6 -> 0/6 with rich_4079 and rich_4076 timing out at 40 and 34 calls.",
            "The v10 retraction (L4742-4775): 'budget 22->40 is the confirmed lever' is retracted; committed env is slower per step than our dev measurements.",
            "The content of the two refused calls: non-gold replacement + invalid escaping (4079), self-admitted wrong logic writing an unparsable file (4070).",
            "rich_4070's gold shape: 9 files, 33 hunks, +71/-57, a lazy-import deferral; the model's plan covered 1 file.",
            "max_tool_calls is also the per-task wall-clock governor for the 129-task scored run; 7/227 rows already hit the 480s wall and fastapi runs 13.8-30.4 s/call; the 12h global cap reportedly errors the whole submission.",
            "rich_4077 cannot gain from a higher cap (13-21 calls) and has already broken inside the 40-call regime (Outputs/v11: 40 calls, 0 chars).",
            "The baseline is v6w @ 0.15, not v6b (1/6 regression)."],
 "proposed_curations": [{"id": "CUR-budget-lever-v2", "kind": "judgment", "lever": "max_tool_calls", "text": "Raising max_tool_calls against a fixed max_time_minutes is a measured regression on this agent family: v2 (25->40 + turns 50) went 1/6 -> 0/6 with rich_4079/rich_4076 timing out; the only pro-budget result (v10 2/10 at 40 calls) is retracted as non-reproducible (committed 0/10, same eval_config).", "status": "SUPPORTED", "evidence": ["GEMMA_EXPERIMENT_LOG.md#L596-612", "GEMMA_EXPERIMENT_LOG.md#L4742-4760"]},
                        {"id": "CUR-v6b-refused-edits", "kind": "judgment", "lever": "budget-wall counterfactual", "text": "The v6b edit-bearing calls refused at the 28-call wall would not have landed gold: rich_4079 step 31 carries a non-gold replacement in a Python-invalid command; rich_4070 step 32 carries self-admitted wrong logic that inserts an import inside a def signature. 'One more call' is not the blocker.", "status": "SUPPORTED", "evidence": ["submit_v6b/out_v6b/results/traces/trace_rich_4079.json#step_id=31", "submit_v6b/out_v6b/results/traces/trace_rich_4070.json#step_id=32", "kb/tasks_gold.json#tasks.rich_4079"]},
                        {"id": "CUR-log-live-best-stale", "kind": "contradiction", "lever": "baseline", "text": "GEMMA_EXPERIMENT_LOG.md READ-THIS-FIRST bullet 4 ('LIVE-BEST = v6 @ 0.12') is stale; curated/submissions.csv confirms v6w @ 0.15 (57098497 COMPLETE). KB_SUMMARY's banner calling the steering file stale is also now out of date - steering says v6w @ 0.15.", "status": "SUPPORTED", "evidence": ["GEMMA_EXPERIMENT_LOG.md#L25", "kb/curated/submissions.csv", ".kiro/steering/gemma-submission-protocol.md"]}]}
-->
