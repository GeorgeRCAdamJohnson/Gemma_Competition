VERDICT: REVISE

# AUDIT — rich near-miss forensic (proposal 2026-10-11), audited 2026-10-14

- Proposal: `Gemma\kb\proposals\2026-10-11-rich-near-miss-forensic.md` (read, not modified)
- KB: `inputs_fingerprint` d31fed8cc9c648e7347e85a895e3122dd4459553fe32aa172cfcadd9c137131f, built 2026-10-15T01:21:38Z, `check-fresh` = FRESH (exit 0)
- Mode: AUDIT. Every claim below is tagged MEASURED (read out of a raw artifact) or INFERRED.

---

## 1. Suggestion restated

A forensic, not a config change: for every rich task ever attempted, per run, report the furthest
near-miss stage reached, what stopped it, the trace step_ids, and **whether the attempted change would
have passed the tests locally**; mark six named leads SUPPORTED/CONTRADICTED/UNVERIFIED; list every
READ-THIS-FIRST standing truth and log verdict the raw data contradicts; rank "what we've been missing";
and end with exactly **one** next rich-only free-gate change plus its pre-registered bar. Stated
constraints: "v6 @ 0.12 is live-best and sacred", "12B is parked", "the next gate is rich-only".

**Verdict in one line:** the forensic is worth running and I ran it — but the proposal must be REVISED
before it drives anything, because (a) all three of its stated constraints are stale, (b) its headline
required output (local replay of the attempted change) is **impossible** for 3 of its 4 targeted tasks,
and (c) two of the "mechanism findings" it asks me to build on are **arithmetic artifacts** that the raw
traces contradict. The one next change I propose is different from anything the proposal anticipated and
comes out of a defect I found in the raw traces (§10).

---

## 2. Prior art

| lever / question in the proposal | tag | basis |
|---|---|---|
| "per-rich-task near-miss forensic with step_ids" | **RE-RUN (now mechanised)** | the KB's `nm-3` near-miss engine + `fc-3` classifier already emit exactly this for 149 traced rich rows (`Gemma\kb\near_miss.jsonl`, `runs.jsonl`). MEASURED. |
| "would the attempted change have passed?" | **BLOCKED** | `rp-3` replay engine exists, but gold is locally INVALID on rich_4079 / rich_4070 / rich_3469 (§6). MEASURED. |
| "budget 28→50 on hard rich" | **RE-RUN, already killed** | log L6834-6838 (v21/v6b A/B) and §7 below. |
| "apply-as-you-go / edit-early prompt" | **RE-RUN** | shipped in the v6t/armC/hard prompt family (`submit_v6z_on_v6w\hard\out\...\trace_rich_3934.json` step 1 system text: "EDIT NOW", "Edit first. Verify after, if at all."). MEASURED. |
| "treat rich_4070/4079 as structurally out of reach" | **REJECTED by data** | rich_4079 has resolved 6 times (§4). MEASURED. |
| "sed-read fix / read_file ranges are broken" (log L7619, L7991, L8021) | **REJECTED by data** | the tool works; the model's *argument key* is malformed (§5, §9). MEASURED — this is the new finding. |
| "name the exact malformed argument in the prompt" | **VARIANT (new target)** | armC did this for `old_string` and measurably killed the loop (log L7741-7743, 52→1 markers). It has never been done for `read_file` keys. MEASURED precedent, NEW target. |

Config diffs that matter for the baseline question: v6 = 22/5/40/120, thinking 512, edit_file present;
v6b = 28/8/80/240, thinking 4096, **edit_file and write_file dropped**; v6w = 28/8/80/240, thinking 1024,
9-tool surface with **edit_file primary** (log L6729-6740, L8389-8402). MEASURED from the log; the staged
config fields are a declared KB gap (`KB_SUMMARY.md` §11), so the config columns in `runs.jsonl` are null.

---

## 3. Ground truth per task (gold patch + test_patch, from `comp_files\tasks.jsonl` + `tasks_gold.json`)

All MEASURED. Difficulty = KB `mech-1` class.

| task | class | gold file(s) | what the gold does | what the test asserts |
|---|---|---|---|---|
| rich_4077 "proxy isatty" | EASY (1 file, 1 hunk, +3/-0) | `rich/file_proxy.py` | adds `isatty()` delegating to the wrapped file | `assert file_proxy.isatty()` |
| rich_4079 "Inline table code" | EASY (1 file, 1 hunk, +4/-3) | `rich/markdown.py` | `TextElement.on_text`: when `text` is a `str`, `self.content.append(text, context.current_style)` instead of building a `Text` and stylizing it | exact-ANSI equality on a rendered markdown table (`test_inline_code_in_table_cells`) |
| rich_4076 "preserve newlines" | EASY (1 file, 1 hunk, +3/-3) | `rich/ansi.py` | `decode()`: `re.split(r"(?<=\n)", terminal_text)` + `decode_line(line.rstrip("\n"))` (plus a docstring arg rename) | `test_decode_newlines` + 4 `Text.from_ansi` newline assertions |
| rich_3469 "fix superfluous space" | EASY (1 file, 1 hunk, +1/-1) | `rich/markdown.py` | `__rich_console__`: `if new_line and node_type != "inline":` | `test_table_with_empty_cells`, exact box-drawing output |
| rich_4070 "perf: reduce import time" | HARD (9 files, 33 hunks, +71/-57) | `_emoji_replace, console, emoji, logging, protocol, repr, segment, syntax, theme` | defers imports / `TYPE_CHECKING` restructuring across 9 modules | no added tests; existing `test_console.py` + `test_syntax.py` must stay green |

Gate-set context (same MEASURED source): rich_3278 EASY (+1/-0), rich_3471 EASY (+1/-0), rich_3882 EASY
(+1/-1). The hard set: rich_3535 HARD (+7/-1), rich_3676 HARD (+12/-1), rich_3675 HARD (+28/-13),
rich_3486 HARD (+74/-24), rich_3934 HARD (+17/-3).

**Lead 5 is answered and it is the opposite of the proposal's worry:** the 6-task rich gate
(3278/3471/3882/4076/4077/4079) is **6/6 mechanically EASY**, not mostly HARD. MEASURED.

---

## 4. Behaviour per task per run (the forensic the proposal asked for)

Full table is reproducible from `Gemma\kb\runs.jsonl` + `near_miss.jsonl` (195 rich rows, 149 with a
trace). Resolve counts over all runs on disk, MEASURED:

| task | resolved / attempted | furthest stage when it failed | note |
|---|---|---|---|
| rich_4077 | **24 / 32** | RESOLVED or LOCATE | the anchor |
| rich_3882 | 10 / 11 | — | near-deterministic pass |
| rich_3278 | 8 / 11 | TRIED_APPLY (armA, ARG_REJECTED @step n/a) | near-deterministic pass |
| rich_4079 | **6 / 31** | SAW_GOLD_HUNK or TRIED_APPLY | coin flip |
| rich_3471 | 4 / 11 | READ_GOLD_FILE | coin flip |
| rich_3676 | 1 / 8 | SCORED_NONEMPTY | first-ever hard resolve (branch arm) |
| rich_3718 | 1 / 1 | — | MEDIUM, one run |
| rich_4076 | **0 / 26** | SCORED_NONEMPTY (wrong file) | localisation null |
| rich_3469 | **0 / 15** | READ_GOLD_FILE at best | localisation null |
| rich_4070 | **0 / 13** | WROTE_GOLD_CHANGE (v21) / SCORED_NONEMPTY 3806ch (hard) | never resolved |
| rich_3535 / 3675 / 3934 / 3486 | 0 / 8, 0 / 8, 0 / 6, 0 / 1 | SCORED_NONEMPTY | hard set, patches banked |

Aggregate failure classes over the 149 **traced** rich rows (MEASURED, `fc-3`):
**WRONG-FIX 56 (37.6%), RESOLVED 45 (30.2%), LOCATE 29 (19.5%), FOUND-NOT-LANDED 19 (12.8%).**
Rows with **zero** edit attempt: 24/149 (16.1%), and 6 of those are infra-zero runs (`v2_gate_out2` 0
calls; `serA` 0 calls). `post_submit_edits`: **0 rows** — no EDIT_AFTER_SUBMIT losses anywhere in rich.
`scored_state_basis`: `last-ok-submit` 120, `final-state (no submit; harness recovery)` 29.

### The proposal's lead 1 (the two v6b hard-rich failures), MEASURED per trace

- `submit_v6b\out_v6b\results\traces\trace_rich_4079.json`: read gold file `rich/markdown.py` at call 24 /
  **step_id 26**, SAW_GOLD_HUNK at call 25 / **step_id 27**, then a `run_command` python-replace at call 29
  / **step_id 31** observed **REFUSED_CALLS** (budget already spent), then `submit_patch` at step_id 33 with
  `patch_size 0`. Class FOUND-NOT-LANDED / REFUSED_CALLS. So: *yes*, it ended on an edit the harness never
  applied, and the cause is the **call cap**, not a tool defect. **SUPPORTED.**
- `submit_v6b\out_v6b\results\traces\trace_rich_4070.json`: python-replace on `rich/console.py` at call 30 /
  **step_id 32**, observed **REFUSED_CALLS**; `submit_patch` step_id 33, `patch_size 0`. **SUPPORTED.**
- Would either have passed? For rich_4079 the refused edit replaced `self.content: Text = Text("", ...)`
  with `self.content = Renderables()` and rewrote `on_text` wholesale — the gold touches **only** `on_text`
  and keeps `self.content` as-is, and the test is an exact-ANSI comparison. **INFERRED (static gold diff):
  it would not have passed.** No replay verdict is available (§6). The refused rich_4070 command's own text
  contains `"# Replace isclass ... # Wait, this is wrong."` — MEASURED from the trace argument.

### Lead 2 (edit mechanics on the python-replace path) — SUPPORTED with a correction

`submit_v21\out_v21\results\traces\trace_rich_4076.json`: a python-replace at call 17 / step_id 19 observed
**REFUSED_CALLS**, with refusals also at calls 16 and 19 (step_ids 18, 21) and `obs_by_class`
`{OK:10, REFUSED_CALLS:3, TOOL_ERROR:6}` — 6 tool errors out of 19 calls. MEASURED. So the python-replace
path does cost calls to quoting/anchor errors, and standing truth #2 ("the edit-ANCHOR skill is NOT the
bottleneck") was indeed measured on `edit_file`, not on this path. **But** the project's own later
measurement points the other way for the *choice* of path: runs that edited through `run_command` resolved
0.61 vs 0.25 for runs that did not (log §H, L8952-8966). Correction, not refutation.

### Lead 3 (the "5,228-char unsubmitted patch") — **CONTRADICTED / artifact absent**

- The string `5228` appears **only** in the log's own prose (L6735, L6795). It appears in **no** run output,
  trace, or pasted log anywhere under `Gemma\` (searched `*.log,*.txt,*.json,*.md`). MEASURED.
- The one v6 artifact on disk says the opposite. `_v6out\gemma-sibling-conform-v6.log` L33/L77:
  `rich_4070 ... resolved=False duration=197.2s tool_calls=22 patch_chars=2223`, and the trace shows
  `submit_calls:[{call 23, obs_class OK, patch_size 2223, step_id 25}]`, `end_reason SUBMITTED`,
  `scored_state_basis last-ok-submit`. **It submitted 2,223 chars in 197s. It did not time out.** MEASURED.
- Consequence: the premise used in the v6b pre-registration to justify **dropping edit_file**
  ("live v6 trace rich_4070 proved edit_file death-spirals at thinking 4096 → timeout w/ unsubmitted
  5228-char patch", L6735) is not supported by any artifact in the workspace. The closest real number is
  `Outputs\v14::rich_4070` = 5,138 chars at 33 calls (a different version, no trace). INFERRED: the claim
  came from a pasted chat trace that was never saved.
- What the harness scores when a run ends with no successful submit: the **working tree**
  (`final-state (no submit; harness recovery)`, 29 rich rows). MEASURED, and it means an unsubmitted patch
  is **not** automatically lost — which also undercuts the urgency framing around that claim.

### Lead 4 (v6 = 1/6 or 2/6?) — **SETTLED: 2/6. The v6b pre-registration's baseline was wrong.**

`_v6out\gemma-sibling-conform-v6.log` **L84: `RESOLVED: 2/6`**, with `rich_4077` (15 calls, 396 ch) and
`rich_4079` (21 calls, 562 ch) resolved on **exactly the v6b 6-task sample** (fastapi_15588, fastapi_15661,
rich_4070, rich_4076, rich_4077, rich_4079). MEASURED. The v6b entry at **L6742** states
"**Baseline:** v6 scored 1/6 on this sample" — **CONTRADICTED**. READ-THIS-FIRST #4 ("2/6, rich_4077 +
rich_4079") is **SUPPORTED**.
Consequence: v6b at 1/6 was a **regression against a 2/6 baseline**, not the "lateral null" the log records
(L6768) — it lost rich_4079. INFERRED from the two MEASURED numbers.

### Lead 6 (the v1 "Column docstring deviation") — **CONTRADICTED**

Log **L485**: "rich_4079: the code_analyzer sub-agent correctly found the Column-docstring deviation vs its
Row/_Cell siblings — the SIBLING-CONFORMANCE mechanism FIRED exactly as designed and produced a clean
patch." The rich_4079 gold is `rich/markdown.py :: TextElement.on_text`; `Column`/`Row`/`_Cell` live in
`rich/table.py`; no docstring is involved. MEASURED. So a **wrong-file** patch was logged as the mechanism
"firing exactly as designed", and L493 then carried it forward as something that "may actually resolve".

### The v21 entry's load-bearing sentence — **CONTRADICTED**

Log **L6834**: "Verified from traces: v6b rich_4070 made 31 calls, **ALL grep/read symbol-tracing, not ONE
python-replace edit**". The trace says `calls_by_fn = {get_status 1, read_file 11, run_command 18,
submit_patch 1}` and carries an `edit_attempts` entry: a python-replace on `rich/console.py` at call 30 /
step_id 32, REFUSED. MEASURED. It made exactly one, and the harness refused it for budget. The adjacent
claim "0 real edits in BOTH" is also wrong for v21: `near_miss` reaches **WROTE_GOLD_CHANGE at step_id 22
(call 17)** — the gold change was written into a `run_command` that was refused. Low-specificity heuristic
flag: that stage came from the nm-3 line matcher, not from an applied diff; cross-task FP rate for
WROTE_GOLD_CHANGE is 0.613% (`build_meta.json`), so it is a real hit but it is a *text* hit, not an edit.

---

## 5. Failure classification (§10 definitions, verbatim classes)

- `submit_v6b/out_v6b::rich_4079` — **FOUND-NOT-LANDED / REFUSED_CALLS.** Decided by `REFUSED_CALLS` (1) at
  step_id 31 with `submit_calls patch_size 0`. Harness event: none; `end_reason CALL_CAP`. MEASURED.
- `submit_v6b/out_v6b::rich_4070` — **FOUND-NOT-LANDED / REFUSED_CALLS.** Same shape, step_id 32. MEASURED.
- `submit_v21/out_v21::rich_4070` — **FOUND-NOT-LANDED / REFUSED_CALLS** (`REFUSED_CALLS` ×2, step_ids 21,
  22; `end_reason CALL_CAP`). MEASURED.
- `submit_v21/out_v21::rich_4076` and `::rich_3469` — **LOCATE / NO_GOLD_FILE** (`REFUSED_CALLS` ×3,
  `TOOL_ERROR` ×6 on 4076). MEASURED.
- `submit_v6w/out_v6w::rich_4079` — **FOUND-NOT-LANDED / SAW_ONLY**, `scored_state_basis = final-state (no
  submit)`, 28 calls, 0 chars. The **live-best config fails this task**. MEASURED.
- `submit_v6z_on_v6w/hard/out::rich_4070` — **WRONG-FIX / UNREPLAYED**, 3,806 chars submitted, with
  `ARG_REJECTED` ×5 on `edit_file` (`missing_params: ["old_string"]`, step_ids 29-33) and malformation
  share 0.156. Per §10 this is stage-classified with a `~`-family marker, **not** INFRA — it comes from the
  submitted config. MEASURED.
- Aggregate: WRONG-FIX dominates (56/149). **Standing truth #1 ("the model explores until the budget dies
  without ever calling edit_file … the single recurring failure") is CONTRADICTED as the dominant mode**:
  the dominant mode is landing a patch that does not resolve. MEASURED, and consistent with the project's
  own later §J count (log L8968-8975: "only 2 of 34 runs … made no edit attempt at all").

---

## 6. Replays / tests run

| command | result |
|---|---|
| `python kb\build_kb.py check-fresh` | **FRESH** (exit 0) — no rebuild needed |
| `python kb\build_kb.py report-path --date 2026-10-14 --slug rich-near-miss-forensic --kind audit` | this path (exit 0) |
| read `kb\replays\gold\rich_4079.json` | `gold_first: INVALID`, reason "gold does not pass required tests locally", gold run `exit_code 2, errors 1, passed 0` |
| read `kb\replays\gold\rich_3469.json` | `gold_first: INVALID`, same shape (`exit_code 2, errors 1, passed 0`) |
| read `kb\replays\gold\rich_4070.json` | `gold_first: INVALID`, gold leaves **6 failures** (`exit_code 1`) |
| read `kb\replays\gold\rich_4076.json` | `gold_first: VALID-HARNESS-LIKE`, `result_criterion: harness_like`, gold 24 passed / 0 failed, base 20/4 |
| `kb\replays\replays.jsonl` (44 rows) | every rich_4079/4070/3469 row is `gold_local: N` → **no replay verdict possible**; every rich_4076 row is `no reconstructable change` |
| `python kb\build_kb.py leakcheck --scope config <proposed prompt text>` | **CLEAN** (exit 0) |
| trace-level recount of `read_file` arguments across all 149 rich traces | see §9 — 44/928 calls carry a malformed argument key |
| `python kb\build_kb.py claims --task rich_4079` | returns the whole claims table unfiltered — the `--task` filter does not narrow (consistent with the declared §11 gap "full claims column-mapping deferred"). I used raw `Select-String` on the log for every task/version/lever instead. |

**This is the hard blocker on the proposal's required output #1.** "Would the attempted change have passed
the tests?" is answerable **only for rich_4076** (and there, no attempted change is statically
reconstructable). For rich_4079, rich_4070 and rich_3469 the gold itself does not pass locally, so per the
engine's own rule a replay yields **no verdict** — the proposal cannot require that column for them.
Measured cause is not recorded beyond `errors: 1 / exit_code 2` (a collection-time error on the
`tests/test_markdown.py` module for 4079/3469); the replay rows carry no stderr. That is the one piece of
this proposal that is genuinely NEEDS-DATA.

---

## 7. Variance

Same 6-task EASY gate, 28-call regime, configs differing in thinking budget / frequency penalty / prompt
(v6c, v6s, v6t, v6v, v6w, v6x, v6y, v6z, armA, armB, armC — MEASURED from `runs.jsonl`):

- rich_4077 **24/32 overall**, rich_3882 **10/11**, rich_3278 **8/11** → deterministic core.
- rich_4076 **0/26** → never flips.
- rich_4079 **3/11 in this regime (6/31 overall)**, rich_3471 **4/11** → coin flips.
- Scores observed: 4, 4, 4, 3, 3, 3, 2, 2 out of 6.

So a config move of ±1 task on this gate is **inside noise**, and the log already says so twice
(L7491-7510 "the gate's limits are now fully characterised… stop gating on these 6 tasks"; L7744-7765
"the gate is dead… it is a 5-sided die"). Any bar that pre-registers "+1 resolve on these 6" is
unreadable. The hard set is no better as a *resolution* instrument: rich_3676 is T in `branch` and F in
`hard`/`compact5`/`m12`/`maxout16k`/`serB` → **1/8**, which the log itself calls a coin flip (L8674-8676).

Budget as a lever: the v21↔v6b A/B that "falsified" it changed **≥5 variables at once** (15→28 calls,
120→240 s, thinking 256→4096, frequency_penalty 0.4→0, and the tool surface: edit_file/write_file dropped).
MEASURED from L6821-6826. Its conclusion is sound **only** for 4070/4079; the same 28-call budget family
later produced 4/6 on the EASY gate and the 0.15 board score. The log's wording "a dead lever … at both
ends of the range" over-generalises a confounded n=2-task comparison.

---

## 8. Rules check

- **Pre-register the bar** — the v6b gate did pre-register (L6741-6747), but against a **wrong baseline**
  (1/6 vs the measured 2/6). A bar is only as good as its baseline; this one inverted the sign of the
  result. The v21 entry pre-registered nothing — it is a post-hoc read of two runs.
- **External judge only** — respected for the board; but "edit_file death-spirals / 5228-char timeout"
  entered the log as a verdict from a **chat-pasted trace with no artifact** and then justified a
  change-set. That is a dev-internal claim promoted to a verdict.
- **One change per gate** — violated by construction in v6b (eight coupled changes, acknowledged in the
  entry itself) and in the v21↔v6b comparison.
- **Tune before concluding (13)** — "budget is dead" and "read_file ranges are broken" are both
  single-point conclusions; the second is contradicted by the traces (§9).
- **Novelty leads / gate failure is a debugging task (10, 11)** — the correct application here: the
  "serialization wall" was **not** a model-capability dead end; §5.3 of the real harness names it and the
  raw traces show a *mechanical* argument-key defect. Debug, don't retreat. The proposal's offer to
  "treat rich_4070/4079 as structurally out of reach" is the retreat move, and rich_4079's 6 resolves
  refute it.
- **Negative space (19)** — under-used, and it is the right lens for rich_4076 (0/26) and rich_3469 (0/15):
  the tell is that `rich/ansi.py` was touched in **1 of 12** runs (log §I) — an absence relative to
  opportunity, not a presence.
- **Free gate first / live-best** — **the proposal's constraint block is stale on all three counts:**
  1. Live-best is **v6w @ 0.15** (`kb\curated\submissions.csv` ref **57098497**, COMPLETE, 2026-10-12), not
     v6 @ 0.12 (ref 56806249). `gemma-submission-protocol.md` has been updated and now agrees; the
     **log's READ-THIS-FIRST #4 (L27) and CONSOLIDATED VERSION HISTORY (L154) are the stale ones.** MEASURED.
  2. 12B is **not** parked — it serves (log L8509-8558, "12B SERVES. Viability PASS, quality NEGATIVE").
  3. The scored slot for the current day is **already spent**: log L9059-9075 records submission ref
     **57201051** ("v6w + temperature 1.0 / top_k 64") pushed 2026-10-15 01:15 UTC, with the receipt "0
     submissions remaining today". MEASURED from the log; **not yet in `submissions.csv`** (so the CSV is
     one-to-two submissions behind).
  4. Conflict to surface, not to adopt: the log states ref **57146757** ("PER-TASK BRANCHING") scored
     **0.12** (L9050), while `submissions.csv` still shows it `PENDING` with no score. Either way v6w @
     0.15 stays the baseline, so no verdict here depends on it — but `B pull --submissions` is the required
     read-only step to reconcile, and any bar that *does* depend on 57146757 or 57201051 is **NEEDS-DATA**
     until those scores land.

---

## 9. Cheapest falsifying test — run, and it overturned two standing findings

I re-counted `read_file` arguments directly out of all 149 raw rich traces
(`<run>\results\traces\trace_rich_*.json`, `steps[].tool_calls[].{function_name,arguments}` + the sibling
`observation.content`). Three MEASURED results:

**(a) "rich_3934 spent 60 read_file calls on a 41-line gold" (log L7986-7989) is an arithmetic artifact.**
`submit_v6z_on_v6w\hard\out\results\traces\trace_rich_3934.json` contains **20 tool calls total: read_file
8, run_command 6, edit_file 5, submit_patch 1** — it cannot contain 60 reads (`final_metrics.total_steps`
= 24). The number 60 is approximately the **hard-arm total across all six tasks (58)**. The task that
actually dominates reads on that arm is **rich_3486: 20 read_file of 29 calls.** So "that single task
burned more budget than the other five combined" is false, and the log's §7973 per-task table
(`rich_3934 | read_file 60 | run_cmd 3 | edit_file 3`) disagrees with its own trace on all three columns.

**(b) "`read_file` line-ranges are BROKEN / it returns the top of the file / we CANNOT fix the tool"
(log L7619-7625, repeated at L7991 and L8021) is WRONG — and the real cause is fixable.**
Across the range calls I inspected, `read_file` with `start_line`/`end_line` returns **exactly the
requested region**, `status: ok`:
- `submit_v6z_on_v6w\hard\...\trace_rich_3676.json` step 11 `{start_line 190, end_line 210}` → 345 chars
  beginning at `filename: str` (line ~190); step 17 `{1,150}` → begins at `import inspect`; 13 range calls,
  **zero** non-ok observations.
- `...\trace_rich_3486.json` steps 4, 6, 7, 8, 15, 19-21, 23-24, 27-29 → every one returns its region.

What actually happens when the model "keeps reading the beginning of the file" is that **the argument KEY
is malformed** — the model emits `"start_line\""` (a trailing quote baked into the key name), so the
harness sees no `start_line` and serves the file from line 1:
- `submit_v6y\out_v6y\...\trace_rich_4079.json` steps 19, 20, 21, 25, 27, 28 use key `start_line"` →
  each returns **4,024 chars starting at `from __future__ import annotations`** (line 1). The model then
  says at step 21 "I keep reading the beginning of the file", at step 26 again, and at step 29 "I will use
  `sed`". **Step 22 re-emits the same read with the bare key `start_line: 308` → 1,429 chars starting at
  `class TableDataElement`** — correct. Same pattern at step 25 (bad) → step 26 (good).
- `submit_v6t\out_v6t\...\trace_rich_3471.json` step 6 (`start_line"`, `end_line"`) → top of file, model
  complains at step 7, step 7 with correct keys → the requested `append_tokens` region.
- `submit_v6z_on_v6w\hard\...\trace_rich_3486.json` step 5 (`start_line"`) → complaint at step 6; step 13
  shows the collapsed shape `filepath: "rich/syntax.py`,start_line=500,end_line=600"`.

**Quantified baseline (MEASURED, all 149 rich traces): 928 `read_file` calls, 44 of them (4.7%) carry a
malformed argument key or a collapsed `filepath`; 19 of 149 rows (12.8%) are affected.** Bad keys:
`start_line"` ×41, `end_line"` ×7, `"end_line"` ×6. Worst rows: `v6y::rich_4079` 6 of 15 reads,
`v2_gate_out::rich_4079` 6 of 12, `lora025::rich_3676` 7 of 13, `hard::rich_3675` 3 of 5. The affected rows
concentrate on exactly the stuck tasks: **rich_4076 (7 rows), rich_4079 (4), rich_3469 (3), rich_3675 (3)**.

**(c) This unifies the project's three "walls" into one defect family.** `edit_file` ARG_REJECTED
(`missing_params: ["old_string"]`, 5 calls on `hard::rich_4070`), the "valid JSON as prose" observation
(log L7920-7937), and this `start_line"` key corruption are the same thing: **the model cannot reliably
serialise tool-call arguments**, and it shows up in the *keys*, not only the values. The harness §5.3 nudge
machinery (log L8566-8584) addresses the unclosed-tag variant only. armC proved the prompt can fix one
instance of this family by **naming the exact malformation** (`old_string` missing → 52 markers to 1,
log L7741-7743). That lever has never been pointed at `read_file` keys.

---

## 10. Verdict rationale — REVISE, and the one next change

**Why not PROCEED:** the proposal's constraint block is stale on three facts (live-best, 12B, slot), its
required output #1 cannot be produced for 3 of its 4 targeted tasks, and two of the findings it tells me to
build on (rich_3934's 60 reads; read_file ranges broken) do not survive the raw traces. Acting on it as
written would re-import the errors it was written to catch.

**Why not NEEDS-DATA overall:** everything else in it *was* answerable offline and is answered above. Only
the local gold-validity defect is a data gap, and it blocks one column, not the forensic.

**Why not REJECT:** the forensic produced real, new, actionable signal (§9).

### Revisions required

1. Replace the constraint block with: live-best **v6w @ 0.15** (`submissions.csv` 57098497); 12B serves;
   the scored slot is spent until the next UTC day; two submissions (57146757, 57201051) are unreconciled
   between the log and `submissions.csv` → `B pull --submissions` first.
2. Narrow required output #1: the replay column applies to **rich_4076 only** (the single targeted task
   with `gold_first = VALID-HARNESS-LIKE`). For rich_4079 / rich_4070 / rich_3469 the honest output is
   "no replay verdict — gold INVALID locally", plus a static gold-vs-attempt diff (as in §4).
3. Append these CORRECTED entries to the log (the top-level session writes them, not me): READ-THIS-FIRST
   #1 (WRONG-FIX dominates, not exploration death), #4 (live-best is v6w @ 0.15), L6742 (v6 baseline on the
   v6b sample is **2/6**), L6735/L6795 (the 5228-char timeout has no artifact and the v6 artifact says
   2,223 chars submitted in 197 s), L6834 (v6b rich_4070 made one python-replace, refused for budget), L485
   (rich_4079 "Column-docstring" is the wrong file), L7619/L7986/L7991/L8021 (read_file ranges work; the
   defect is a malformed argument key; the sed remedy targets a non-defect).
4. Drop "treat rich_4070/4079 as structurally out of reach" — rich_4079 resolves 6/31.

### The ONE next rich-only free-gate change (pre-register exactly this; it is not PROCEED-approved until the revisions above are made)

**The change (one change-set, prompt-only, vs the v6w / branch base):** add a short block naming the
`read_file` argument-key malformation and the recovery, mirroring armC's `old_string` fix. Proposed text
(leakcheck `--scope config`: **CLEAN**; no gold, no problem-statement fingerprints):

> READING FILE REGIONS — the exact argument keys matter. The keys are `filepath`, `start_line`, `end_line`
> and nothing else. A key with a trailing quote (`start_line"`) is ignored by the harness and you get the
> TOP of the file back. If a read returns the top of the file when you asked for a region, your key was
> malformed: re-emit the same read once with the bare key `start_line`. Never put a line range inside
> `filepath`. Do not re-read a region you have already seen.

**The task set (rich-only, 6 tasks, chosen so the instrument is not saturated — classes stated):**
rich_4076 (EASY, 0/26, the localisation null, 7 malformed-key rows), rich_3469 (EASY, 0/15, 3 malformed-key
rows), plus four never-gated EASY rich tasks with no prior Kaggle or local exposure: rich_3067, rich_3472,
rich_3894, rich_2725 (each 1 file / 1 hunk per `tasks_gold.json`). **No task in this set has ever resolved
on any run**, so there is no deterministic core to mask a move — unlike the retired 3278/3882/4077 gate.

**Pre-registered bar — mechanism primary, resolution recorded only:**
- **PASS requires all three.** (i) *Mechanism:* malformed `read_file` argument keys = **0** across the six
  traces (baseline: 44 of 928 calls, 19 of 149 rows; on these tasks specifically, 4076 and 3469 show
  1-3 per affected run). (ii) *Waste:* no run contains ≥2 consecutive `read_file` calls returning content
  that begins at line 1 of a file over 150 lines. (iii) *No regression:* ≥5 of 6 tasks bank a non-empty
  patch (baseline on the 4 fresh tasks is unknown, so this clause is a floor, not a comparison).
- **FAIL:** malformed keys persist (prompt not followed → the lever is dead and the finding stands as a
  measurement, not a fix), **or** banking drops below 5/6 (the block displaced something that was working).
- **Resolution is recorded, not a criterion.** n=6 with four unknown-difficulty-in-practice tasks has no
  power, and rich_4079/3676 are measured coin flips. A resolve on a never-resolved task is a bonus to be
  re-run, never a promotion on its own.
- **Mechanism re-check (rule 13):** re-run the §9 counter on the new traces and compare the per-task
  malformed-key counts against the baselines listed above. Sweep nothing else; this is one block of text.
- **Judge:** the FREE Kaggle rich gate. The scored slot stays untouched; by the protocol it cannot be used
  until the free gate passes this bar **and** 57201051 has scored.

---

## 11. What the suggestion missed

1. **The live-best, the parked-12B and the free-slot constraints are all stale** — the proposal would have
   been pre-registered against v6 @ 0.12 while the board already has v6w @ 0.15 and a submission in flight.
2. **Its own required output #1 is unobtainable for 3 of its 4 targeted tasks** (gold INVALID locally). The
   proposal asserts "gold must pass its test_patch locally before any agent replay counts" without checking
   that gold *does* pass — it does not for rich_4079, rich_4070 or rich_3469.
3. **It treats the last session's two "fixable mechanism" findings as a foundation.** Both are artifacts:
   rich_3934's "60 reads" is the 6-task arm total (its trace has 8), and "read_file ranges are broken" is a
   malformed argument **key**. The sed-routing remedy the log pre-registers (L8021) would have been a gate
   spent on a defect that does not exist.
4. **The gate-makeup worry is inverted.** The 6-task rich gate is 6/6 mechanically EASY; the problem is not
   that it is too hard but that it is **saturated** (3 near-deterministic passes + 1 never-passes + 2 dice),
   which the log had already measured twice before this proposal was written.
5. **The v6b baseline error flips the sign of a logged verdict.** v6b was a regression (1/6 vs 2/6), and the
   change-set that caused it (dropping edit_file) was justified by a trace that is not on disk — then
   reversed later, with edit_file primary in the config that scored 0.15.
6. **Negative space is the right lens for the two stuck EASY tasks and was not used.** rich_4076 touched
   `rich/ansi.py` in 1 of 12 runs; rich_3469 reached its gold file in 2 of 15. Normalised by opportunity,
   those holes are the signal, and both tasks also carry malformed-key reads.
7. **No EDIT_AFTER_SUBMIT losses exist in rich** (0 rows with `post_submit_edits`), so the "edit the harness
   didn't apply" framing of lead 1 is specifically a **call-cap refusal**, not a scored-state subtlety.

---

## 12. Measured vs inferred

**MEASURED:** every per-task resolve count and failure class (`runs.jsonl`, `near_miss.jsonl`, 149 traces);
the step_ids in §4-5; `_v6out\gemma-sibling-conform-v6.log` L84 `RESOLVED: 2/6` and L77 `rich_4070 … 2223`;
the absence of `5228` anywhere outside the log prose; the gold patches and difficulty classes; the
`gold_first` validity of all four targeted tasks; the 44/928 malformed `read_file` keys and the step-level
before/after pairs proving the ranges work; `submissions.csv` refs and scores; the leakcheck result.

**INFERRED:** that the v6b rich_4079 refused edit would have failed its test (static gold diff, no replay);
that the 5228-char claim came from an unsaved chat trace; that fixing the malformed keys recovers budget on
4076/3469 specifically (the 4.7%/12.8% rates are measured, the *outcome* effect is not); that the four
fresh tasks behave like the other EASY tasks (never run on Kaggle); that `errors: 1 / exit_code 2` on the
4079/3469 gold replays is a test-module collection error (no stderr was captured).

**NOT VERIFIED:** whether 57146757 scored 0.12 (log says yes, `submissions.csv` says PENDING); whether
57201051 has scored; the cause of the local gold-validity failures; anything about fastapi (out of scope).

Scratch files were written under `%TEMP%` only and removed.

<!-- AUDIT-JSON
{"schema": "gemma-audit/1", "mode": "AUDIT", "verdict": "REVISE",
 "proposal": "c:\\Users\\Biges\\OneDrive\\Documents\\Desktop\\kAGGLE\\Gemma\\kb\\proposals\\2026-10-11-rich-near-miss-forensic.md",
 "kb_inputs_fingerprint": "d31fed8cc9c648e7347e85a895e3122dd4459553fe32aa172cfcadd9c137131f",
 "targets": ["rich_4070", "rich_4076", "rich_4077", "rich_4079", "rich_3469"],
 "prior_art": [
  {"lever": "per-rich-task near-miss forensic with step_ids", "tag": "RE-RUN", "runs": ["submit_v6b/out_v6b", "submit_v21/out_v21", "_v6out"]},
  {"lever": "budget 28->50 on hard rich", "tag": "RE-RUN", "runs": ["submit_v21/out_v21", "submit_v6b/out_v6b"]},
  {"lever": "apply-as-you-go / edit-first prompt", "tag": "RE-RUN", "runs": ["submit_v6z_on_v6w/hard/out", "submit_v6z_on_v6w/armC/out"]},
  {"lever": "sed-routing to fix read_file ranges", "tag": "RE-RUN", "runs": ["submit_v6z_on_v6w/hard/out"]},
  {"lever": "name the exact malformed tool-call argument in the prompt (read_file keys)", "tag": "VARIANT", "runs": ["submit_v6z_on_v6w/armC/out"]}
 ],
 "per_task": [
  {"run_id": "submit_v6b/out_v6b", "task": "rich_4079", "failure_class": "FOUND-NOT-LANDED", "subclass": "REFUSED_CALLS", "evidence": ["Gemma/submit_v6b/out_v6b/results/traces/trace_rich_4079.json#step_id=31", "Gemma/submit_v6b/out_v6b/results/traces/trace_rich_4079.json#step_id=32", "Gemma/kb/near_miss.jsonl#row_id=submit_v6b/out_v6b::rich_4079"]},
  {"run_id": "submit_v6b/out_v6b", "task": "rich_4070", "failure_class": "FOUND-NOT-LANDED", "subclass": "REFUSED_CALLS", "evidence": ["Gemma/submit_v6b/out_v6b/results/traces/trace_rich_4070.json#step_id=32", "Gemma/submit_v6b/out_v6b/results/traces/trace_rich_4070.json#step_id=33"]},
  {"run_id": "submit_v21/out_v21", "task": "rich_4070", "failure_class": "FOUND-NOT-LANDED", "subclass": "REFUSED_CALLS", "evidence": ["Gemma/submit_v21/out_v21/results/traces/trace_rich_4070.json#step_id=22", "Gemma/kb/near_miss.jsonl#row_id=submit_v21/out_v21::rich_4070"]},
  {"run_id": "submit_v21/out_v21", "task": "rich_4076", "failure_class": "LOCATE", "subclass": "NO_GOLD_FILE", "evidence": ["Gemma/submit_v21/out_v21/results/traces/trace_rich_4076.json#step_id=19"]},
  {"run_id": "submit_v6w/out_v6w", "task": "rich_4079", "failure_class": "FOUND-NOT-LANDED", "subclass": "SAW_ONLY", "evidence": ["Gemma/submit_v6w/out_v6w/results/traces/trace_rich_4079.json#step_id=13", "Gemma/kb/runs.jsonl#row_id=submit_v6w/out_v6w::rich_4079"]},
  {"run_id": "submit_v6z_on_v6w/hard/out", "task": "rich_4070", "failure_class": "WRONG-FIX", "subclass": "UNREPLAYED", "evidence": ["Gemma/submit_v6z_on_v6w/hard/out/results/traces/trace_rich_4070.json#step_id=29", "Gemma/submit_v6z_on_v6w/hard/out/results/traces/trace_rich_4070.json#step_id=34"]},
  {"run_id": "_v6out", "task": "rich_4079", "failure_class": "RESOLVED", "subclass": null, "evidence": ["Gemma/_v6out/gemma-sibling-conform-v6.log#line=84", "Gemma/_v6out/results/traces/trace_rich_4079.json#step_id=24"]},
  {"run_id": "_v6out", "task": "rich_4070", "failure_class": "WRONG-FIX", "subclass": "UNREPLAYED", "evidence": ["Gemma/_v6out/gemma-sibling-conform-v6.log#line=77", "Gemma/_v6out/results/traces/trace_rich_4070.json#step_id=25"]}
 ],
 "claims": [
  {"id": "A1", "text": "v6 scored 2/6 on the exact v6b 6-task sample (rich_4077 + rich_4079); the v6b pre-registration's '1/6 baseline' (log L6742) is wrong, so v6b at 1/6 was a regression.", "basis": "MEASURED", "evidence": ["Gemma/_v6out/gemma-sibling-conform-v6.log#line=84", "Gemma/GEMMA_EXPERIMENT_LOG.md#line=6742"]},
  {"id": "A2", "text": "read_file line-ranges are NOT broken; the model emits a malformed argument key (start_line\") so the harness ignores it and serves line 1. Re-emitting with the bare key returns the correct region.", "basis": "MEASURED", "evidence": ["Gemma/submit_v6y/out_v6y/results/traces/trace_rich_4079.json#step_id=21", "Gemma/submit_v6y/out_v6y/results/traces/trace_rich_4079.json#step_id=22", "Gemma/submit_v6t/out_v6t/results/traces/trace_rich_3471.json#step_id=6", "Gemma/GEMMA_EXPERIMENT_LOG.md#line=7619"]},
  {"id": "A3", "text": "Malformed read_file argument keys occur in 44 of 928 rich read_file calls (4.7%) across 19 of 149 rows, concentrated on rich_4076/4079/3469/3675.", "basis": "MEASURED", "evidence": ["Gemma/submit_v6y/out_v6y/results/traces/trace_rich_4079.json", "Gemma/v2_gate_out/results/traces/trace_rich_4079.json", "Gemma/submit_v6z_on_v6w/lora025/out/results/traces/trace_rich_3676.json"]},
  {"id": "A4", "text": "'rich_3934 spent 60 read_file calls' is the 6-task hard-arm total (58); its own trace has 8 read_file of 20 calls, and rich_3486 is the read-heavy task (20 of 29).", "basis": "MEASURED", "evidence": ["Gemma/submit_v6z_on_v6w/hard/out/results/traces/trace_rich_3934.json", "Gemma/submit_v6z_on_v6w/hard/out/results/traces/trace_rich_3486.json", "Gemma/GEMMA_EXPERIMENT_LOG.md#line=7986"]},
  {"id": "A5", "text": "'v6b rich_4070 made 31 calls, ALL grep/read, not ONE python-replace edit' (log L6834) is contradicted: one python-replace at call 30 / step_id 32, refused for budget.", "basis": "MEASURED", "evidence": ["Gemma/submit_v6b/out_v6b/results/traces/trace_rich_4070.json#step_id=32", "Gemma/GEMMA_EXPERIMENT_LOG.md#line=6834"]},
  {"id": "A6", "text": "The '5228-char unsubmitted patch / timeout' premise for dropping edit_file has no artifact anywhere under Gemma\\; the only v6 rich_4070 artifact submitted 2223 chars in 197s.", "basis": "MEASURED", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#line=6735", "Gemma/_v6out/gemma-sibling-conform-v6.log#line=77"]},
  {"id": "A7", "text": "The 6-task rich gate is 6/6 mechanically EASY and saturated (3 near-deterministic passes, rich_4076 0/26, rich_4079 and rich_3471 coin flips); no +-1 move on it is readable.", "basis": "MEASURED", "evidence": ["Gemma/kb/tasks_gold.json", "Gemma/kb/runs.jsonl", "Gemma/GEMMA_EXPERIMENT_LOG.md#line=7491"]},
  {"id": "A8", "text": "Gold does not pass locally for rich_4079, rich_4070 and rich_3469, so the proposal's 'would the attempted change have passed' column is unobtainable for them; rich_4076 is the only targeted task with valid local gold.", "basis": "MEASURED", "evidence": ["Gemma/kb/replays/gold/rich_4079.json", "Gemma/kb/replays/gold/rich_4070.json", "Gemma/kb/replays/gold/rich_3469.json", "Gemma/kb/replays/gold/rich_4076.json"]},
  {"id": "A9", "text": "Dominant rich failure class is WRONG-FIX (56 of 149 traced rows, 37.6%), not exploration death; 24 rows made no edit attempt and 6 of those are zero-call infra runs. Standing truth #1 is stale.", "basis": "MEASURED", "evidence": ["Gemma/kb/runs.jsonl", "Gemma/GEMMA_EXPERIMENT_LOG.md#line=8968"]},
  {"id": "A10", "text": "The proposal's constraints are stale: live-best is v6w @ 0.15 (ref 57098497), 12B serves, and the scored slot was spent on ref 57201051 at 2026-10-15 01:15 UTC; submissions.csv lags the log on 57146757 and 57201051.", "basis": "MEASURED", "evidence": ["Gemma/kb/curated/submissions.csv", "Gemma/GEMMA_EXPERIMENT_LOG.md#line=9059", "Gemma/GEMMA_EXPERIMENT_LOG.md#line=8509"]},
  {"id": "A11", "text": "The v6b rich_4079 refused edit replaced self.content with Renderables() and rewrote on_text, while the gold only changes on_text and keeps self.content; it would not have passed.", "basis": "INFERRED", "evidence": ["Gemma/submit_v6b/out_v6b/results/traces/trace_rich_4079.json#step_id=31", "Gemma/comp_files/tasks.jsonl#rich_4079"]},
  {"id": "A12", "text": "The v1 'rich_4079 Column-docstring deviation, mechanism fired exactly as designed' (log L485) is a wrong-file false positive: the gold is markdown.py::TextElement.on_text.", "basis": "MEASURED", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#line=485", "Gemma/comp_files/tasks.jsonl#rich_4079"]}
 ],
 "tests_run": [
  {"cmd": "python kb/build_kb.py check-fresh", "result": "FRESH (exit 0)"},
  {"cmd": "python kb/build_kb.py report-path --date 2026-10-14 --slug rich-near-miss-forensic --kind audit", "result": "kb/audits/2026-10-14-rich-near-miss-forensic.md (exit 0)"},
  {"cmd": "python kb/build_kb.py leakcheck --scope config %TEMP%/aud_proposed_change.txt", "result": "LEAKCHECK CLEAN (exit 0)"},
  {"cmd": "python kb/build_kb.py claims --task rich_4079", "result": "returns the full unfiltered claims table; the --task filter does not narrow (matches the declared claims column-mapping gap)"},
  {"cmd": "read kb/replays/gold/{rich_4079,rich_4070,rich_3469,rich_4076}.json", "result": "gold_first INVALID / INVALID / INVALID / VALID-HARNESS-LIKE"},
  {"cmd": "recount steps[].tool_calls[].arguments for read_file across all 149 rich traces", "result": "928 calls; 44 (4.7%) malformed keys (start_line\" x41, end_line\" x7, \"end_line\" x6) or collapsed filepath (2); 19/149 rows affected"},
  {"cmd": "compare read_file range-call observations against requested regions (trace_rich_3676, 3486, 3471, 4079)", "result": "every well-formed range call returned the requested region, status ok; every top-of-file return had a malformed key"},
  {"cmd": "grep '5228' across Gemma/**/*.{log,txt,json,md}", "result": "only GEMMA_EXPERIMENT_LOG.md lines 6735 and 6795; no run artifact"},
  {"cmd": "Select-String 'RESOLVED:' _v6out/gemma-sibling-conform-v6.log", "result": "line 84: RESOLVED: 2/6 (rich_4077, rich_4079)"}
 ],
 "missed": [
  "Live-best is v6w @ 0.15, not v6 @ 0.12; 12B is no longer parked; today's scored slot is already spent (ref 57201051).",
  "Required output #1 is unobtainable for rich_4079/4070/3469 - gold does not pass locally, so no replay verdict exists.",
  "Two findings the proposal builds on are artifacts: rich_3934's '60 read_file calls' (arm total; its trace has 8) and 'read_file ranges are broken' (the argument KEY is malformed).",
  "The gate-makeup worry is inverted: the 6-task rich gate is 6/6 EASY and saturated, already measured dead twice in the log.",
  "The v6b baseline error flips the sign of its verdict: 1/6 against a measured 2/6 is a regression, and the change-set was justified by a trace with no artifact.",
  "Negative space (rich_4076 touched ansi.py in 1 of 12 runs; rich_3469 reached its gold file in 2 of 15) is the right lens for the two stuck EASY tasks and was unused.",
  "No EDIT_AFTER_SUBMIT losses exist in rich (0 rows with post_submit_edits); lead 1's 'edit the harness didn't apply' is specifically a call-cap refusal."
 ],
 "proposed_curations": [
  {"id": "J-v6-baseline-2of6", "kind": "judgment", "status": "SUPPORTED", "text": "v6 resolved 2/6 on the v6b 6-task sample (rich_4077 + rich_4079); log L6742's '1/6 baseline' is CONTRADICTED, making v6b (1/6) a regression.", "evidence": ["Gemma/_v6out/gemma-sibling-conform-v6.log#line=84"], "supersedes": "GEMMA_EXPERIMENT_LOG.md#line=6742"},
  {"id": "J-readfile-range-keys", "kind": "judgment", "status": "SUPPORTED", "text": "read_file line-ranges work; the 'returns the top of the file' defect is a malformed argument key (start_line\"), measured in 44 of 928 rich read_file calls. The sed-routing remedy (L7991/L8021) targets a non-defect.", "evidence": ["Gemma/submit_v6y/out_v6y/results/traces/trace_rich_4079.json#step_id=21", "Gemma/submit_v6y/out_v6y/results/traces/trace_rich_4079.json#step_id=22"], "supersedes": "GEMMA_EXPERIMENT_LOG.md#line=7619"},
  {"id": "J-3934-read-count", "kind": "judgment", "status": "SUPPORTED", "text": "rich_3934 made 8 read_file calls of 20 total, not 60; 58 is the hard-arm 6-task total and rich_3486 is the read-heavy task (20 of 29).", "evidence": ["Gemma/submit_v6z_on_v6w/hard/out/results/traces/trace_rich_3934.json"], "supersedes": "GEMMA_EXPERIMENT_LOG.md#line=7986"},
  {"id": "J-v6b-4070-one-edit", "kind": "judgment", "status": "SUPPORTED", "text": "v6b rich_4070 attempted exactly one python-replace (call 30 / step_id 32), refused for budget; 'not ONE python-replace edit' is CONTRADICTED.", "evidence": ["Gemma/submit_v6b/out_v6b/results/traces/trace_rich_4070.json#step_id=32"], "supersedes": "GEMMA_EXPERIMENT_LOG.md#line=6834"},
  {"id": "J-dominant-failure-wrongfix", "kind": "judgment", "status": "SUPPORTED", "text": "Across 149 traced rich rows the dominant failure class is WRONG-FIX (56, 37.6%); FOUND-NOT-LANDED is 19. READ-THIS-FIRST #1's 'never calls edit_file' framing is stale.", "evidence": ["Gemma/kb/runs.jsonl"], "supersedes": "GEMMA_EXPERIMENT_LOG.md#line=11"},
  {"id": "J-gold-local-invalid", "kind": "limitation", "status": "SUPPORTED", "text": "gold_first is INVALID locally for rich_4079, rich_4070 and rich_3469 (collection error / residual failures), so agent-candidate replays on those tasks yield no verdict. rich_4076 is VALID-HARNESS-LIKE.", "evidence": ["Gemma/kb/replays/gold/rich_4079.json", "Gemma/kb/replays/gold/rich_4076.json"]}
 ]}
-->
