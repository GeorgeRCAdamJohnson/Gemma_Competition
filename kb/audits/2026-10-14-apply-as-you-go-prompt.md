VERDICT: REJECT

# Audit — "apply-as-you-go" prompt for multi-item tasks (rich_4070)

- Proposal: `Gemma\kb\proposals\2026-10-11-apply-as-you-go-prompt.md` (read in full; not modified)
- Mode: AUDIT (step 2 of `gemma-audit`), date 2026-10-14, slug `apply-as-you-go-prompt`
- KB: `check-fresh` = FRESH (exit 0); `inputs_fingerprint` `645cfb03047649cea58aadfa9fedc71e53d634a417d34f69c4e6ca1807b447d4`;
  newest input `GEMMA_EXPERIMENT_LOG.md` @ 2026-10-15T03:58:38Z; engines fc-3 / nm-3 / cm-2 / rp-3 / cl-3
  (`Gemma\kb\build_meta.json`). No rebuild needed.
- Steering read in full: `.kiro\steering\reverse-engineering-accountability.md`,
  `.kiro\steering\gemma-submission-protocol.md`.

---

## 1. Suggestion restated

Add ONE generic instruction to the **v6b** system prompt: when the problem statement lists multiple items,
make each edit immediately after locating that item (bank partial progress) instead of tracing the whole plan
first. No other change, kept generic (no task ids / file names / problem fingerprints). Target: `rich_4070`,
described as a multi-file perf refactor where the agent "traced every symbol and hit the wall with 0 edits
banked". The proposal itself asks the audit to settle four things; all four are settled below, three against it.

Provenance: lever (a) under "IMPLICATION for v6bv2 (rich-only)" in the log entry
"v21 vs v6b — BUDGET A/B ON THE SAME HARD RICH TASKS" (`Gemma\GEMMA_EXPERIMENT_LOG.md:L6858-L6869`). MEASURED.

---

## 2. Prior art — **RE-RUN** (the instruction is already in the live-best prompt, verbatim)

**The proposed instruction already exists, shipped, as its own prompt section.** MEASURED:

| path | line | text |
|---|---|---|
| `Gemma\submit_v6w\out_v6w\submission\prompts\system.md` | 22 | `## BANK PROGRESS AS YOU GO (multi-item fixes)` |
| same | 23 | "If the problem needs several changes, apply EACH ONE the moment you locate it — do not trace the entire plan first and edit at the end. A partial fix that is submitted scores. A complete plan that never gets written scores nothing." |

`submit_v6w` is the **live-best baseline** (v6w @ 0.15, submission 57098497, COMPLETE —
`Gemma\kb\curated\submissions.csv` row 2; `Gemma\kb\curated\run_labels.json:baseline`). The same section is
present in `submit_v6c`, `submit_v6t`, `submit_v6v`, `submit_v6x`, `submit_v6y` and the staged
`submit_t4096\prompts\system.md` (all line 22, MEASURED by `Select-String`). It was introduced deliberately as
change-set item **3 "BANK AS YOU GO"** of v6c, whose log pre-registration says, verbatim: *"for multi-item
fixes, apply EACH item the moment it is located; do not trace the whole plan first. Directly targets
rich_4070's measured failure (10 symbols traced, 0 edits banked)"* (`GEMMA_EXPERIMENT_LOG.md:L6921-L6923`,
entry "v6c — THE BUDGET ORACLE", 2026-10-11). MEASURED.

The lever's semantic content is also present in the two v6z-family prompts that lack the heading:
`submit_v6z_on_v6w\hard\out\submission\prompts\system.md:46` — "A landed partial edit scores; a perfect
unapplied plan scores nothing." MEASURED.

Tags: `apply-as-you-go` = **RE-RUN** (shipped v6c → v6w, 2026-10-11, 10+ run dirs).
`apply-as-you-go on rich_4070 specifically` = **VARIANT** only in the sense that no *v6c-family gate ever
included rich_4070* (v6c excluded it on purpose, `GEMMA_EXPERIMENT_LOG.md:L6944-L6946`) — but the behaviour the
instruction is meant to cause has already been produced on rich_4070 repeatedly (§4, §7). The proposal states no
reason an earlier result does not apply, which a RE-RUN requires.

Second prior-art hit: the standing-truth block, bullet 5 — *"The prompt channel (v1–v20+v19v3) is EXHAUSTED for
commitment — budget tuning, edit-early, reserve-tail, anti-loop, commit-to-path-first were all tried …
Re-running a prompt commitment lever = a re-run."* (`GEMMA_EXPERIMENT_LOG.md:L8-L36`, bullet at L41-L45 of that
block). MEASURED (as a log claim; its own status is UNVERIFIED in `log_claims.md`, but it is on point).

Third: the base named in the proposal is wrong by the project's own correction. `GEMMA_EXPERIMENT_LOG.md:L9276`
(FORENSIC VERDICT, 2026-10-14) — *"CORRECTED: 'v6b was a lateral null' … v6 scored 2/6 on that exact sample …
so v6b (1/6) was a REGRESSION vs v6, not a lateral null."* Building on v6b would therefore change two things at
once (base downgrade + the already-present instruction) and would start below both v6 and v6w. MEASURED.

---

## 3. Ground truth per task — rich_4070 (the decisive section; this is NEW ground)

Source: `Gemma\comp_files\tasks.jsonl` (`instance_id == rich_4070`) and `Gemma\kb\tasks_gold.json:tasks.rich_4070`.

**Gold patch** (13,445 chars): 9 files, 33 hunks — `rich/_emoji_replace.py`, `rich/console.py`, `rich/emoji.py`,
`rich/logging.py`, `rich/protocol.py`, `rich/repr.py`, `rich/segment.py`, `rich/syntax.py`, `rich/theme.py`.
MEASURED.

**Problem statement**: 3,096 chars — *not* a terse PR title. It is "perf: reduce Console and RichHandler import
time by deferring unused imports" plus an explicit **per-file item table** that names every change, including
the line "`console.py` | Defer `getpass` to `Console.input()` (only when `password=True`) | ~2ms". So the
checklist is handed to the agent; nothing has to be guessed. MEASURED.

**Test patch** (875 chars) touches exactly two existing test files and adds **zero** new tests
(`tasks_gold.json` → `tests.added_tests = []`, `tests.assertions = []`):
- `tests/test_console.py` — the password test is rewritten to monkeypatch the attribute on the **`getpass`
  module** instead of on `rich.console`. That only takes effect if `console.py` resolves the symbol off the
  module at call time, i.e. only if the `getpass` import is deferred into `Console.input()`.
- `tests/test_syntax.py` — `Console` is re-sourced from `rich.console` instead of from `rich.syntax`. This
  change cannot fail before the patch (importing fewer names never fails), so it is a Pass-to-Pass
  accommodation, not the Fail-to-Pass. INFERRED (static reading).

**Corroborating measurement** — the KB's gold-first replay (`Gemma\kb\replays\gold\rich_4070.json`,
engine rp-3, base_commit `fc41075a…`): base = 106 passed / 7 failed; gold = 107 passed / 6 failed. **The gold
flips exactly ONE test**, and `test_input_password` is in `gold_pass_tests`. MEASURED.

### Consequence (answers the proposal's question 2, and corrects a standing label)

The hidden test **does** reward partial progress on rich_4070 — but only for one specific item. Of the ~14
listed items across 9 files, the Fail-to-Pass hinges on **2 hunks in 1 file**: drop the module-level `getpass`
binding in `rich/console.py` **and** re-bind it inside `Console.input()`. Everything else is Pass-to-Pass
surface. INFERRED from the test_patch, corroborated by the measured +1-test gold differential.

Two standing claims are therefore wrong in their basis:
- `Gemma\RICH_48_DIFFICULTY_MAP.md:91` and `:165` classify rich_4070 HARD / "GENUINE DIFFICULTY" off
  **gold-patch sprawl** (9 files / 128 lines). The document itself names edit mechanics as "the
  high-confidence, reliably-measured axis" (`:110-:114`). For this task that axis overstates the requirement by
  ~an order of magnitude: the test needs one file. MEASURED (patch vs test_patch).
- The same document's premise that rich problem statements are PR titles with median 138 chars
  (`RICH_48_DIFFICULTY_MAP.md:~100-108`) does not hold here: 3,096 chars with an itemised table. MEASURED.
- `GEMMA_EXPERIMENT_LOG.md:L1646,L1653` ("a 9-file/54-hunk refactor = out of scope for plastic surgery",
  "genuine large synthesis") and `:L6944` ("genuine difficulty … unwinnable task") rest on the same
  patch-size basis. Flagged as a finding, not adopted as a correction here (one audit, static basis).

Caveat carried forward, per the 2026-10-14 forensic entry: `gold_first = "INVALID"` for rich_4070 — 6 tests
still fail locally under gold, so the engine gives no replay verdict for this task. "A getpass-only partial
would resolve it" is **INFERRED**, not replay-MEASURED. See §6/§9.

---

## 4. Behaviour per task per run (rich_4070, all 13 rows)

`python kb\build_kb.py card --task rich_4070` → 13 rows, **0 resolved**. MEASURED.

| run | calls | chars | class / subclass |
|---|---|---|---|
| `Outputs/v14` | 33 | 5138 | — (no trace) |
| `Outputs/v15` | 12 | 1847 | — (no trace) |
| `Outputs/v18` | 15 | 3157 | WRONG-FIX |
| `Outputs/v19` | 15 | 1047 | WRONG-FIX |
| `Outputs/v19_lora` | 6 | 0 | FOUND-NOT-LANDED / ARG_REJECTED |
| `Outputs/v19v3` | 15 | 1428 | WRONG-FIX |
| `_v6out` | 22 | 2223 | WRONG-FIX |
| `submit_v21/out_v21` | 15 | 0 | FOUND-NOT-LANDED / REFUSED_CALLS |
| `submit_v6b/out_v6b` | 28 | 0 | FOUND-NOT-LANDED / REFUSED_CALLS |
| `submit_v6z_on_v6w/hard/out` | 26 | **3806** | WRONG-FIX |
| `v2_gate_out` | 12 | 514 | WRONG-FIX |
| `v2_gate_out2` | 0 | 0 | LOCATE / NO_GOLD_FILE |
| `v2_gate_s05c` | 8 | 1047 | WRONG-FIX |

### 4a. v6b — the proposal's lead claim is TRUE, and the refused edit was destructive

`Gemma\submit_v6b\out_v6b\results\traces\trace_rich_4070.json`, 35 steps. MEASURED:
- `step_id=30`: the model writes a 16-item checklist for `rich/console.py`; items **2 and 13 are exactly the
  getpass pair** ("Remove `from getpass import getpass`" / "Move `from getpass import getpass` into `input`").
  So it enumerated the F2P-critical item explicitly.
- `step_id=31`: `get_status` (free) → `tool_calls_used 28`, `remaining 0`, `patch_size 0`.
- `step_id=32`: a `run_command` python-replace on `rich/console.py` — **the proposal's lead is confirmed**; the
  harness refused it with `BudgetExceeded`. "0 edits attempted" is false; "0 successful edits" is true.
  (Matches claim A5 of `Gemma\kb\audits\2026-10-14-rich-near-miss-forensic*.md`, UPHELD by its refute pass.)
- **But read the refused payload.** It deletes `from getpass import getpass`, `from html import escape`,
  `import inspect`, `import zlib`, `from inspect import isclass` and two relative imports — and **never
  re-binds any of them inside the methods that use them**. It also contains the model's own inline admissions
  "`# Wait, this is wrong.`", "`# This is wrong syntax.`" and "`# I will just do the simple replacements and
  hope for the best.`", one of which splices an import into a `def` signature. Had that call been allowed, it
  would have left `rich/console.py` syntactically broken. MEASURED (step 32 `arguments.command`).
- `step_id=33`: empty `submit_patch` (`patch_size 0`). `step_id=35`: final text.

So the counterfactual "one more call and it would have banked progress" is false in substance. It was one call
away from banking a **module-breaking** patch.

### 4b. The hard arm — apply-as-you-go ALREADY happened on rich_4070, and the partial was net-destructive

`Gemma\submit_v6z_on_v6w\hard\out\results\traces\trace_rich_4070.json`, 26 calls, 3,806 chars, 2 files.
MEASURED, by step:
- `step_id=5,6,7`: three successful `edit_file` calls on `rich/logging.py` (status ok).
- `step_id=25`: successful `edit_file` on `rich/console.py` that **removes** the module-level
  `import inspect`, `import zlib`, `from getpass import getpass`, `from html import escape`,
  `from inspect import isclass` (harness diff echoed in the observation, strategy `exact`).
- `step_id=26`: `isclass(renderable)` → `isinstance(renderable, type)` (ok).
- `step_id=27,28`: `_caller_frame_info` default → `None`, and `import inspect` deferred into the stack fallback
  (ok).
- `step_id=29,30,31,32,33`: **five consecutive attempts** to add the deferred `getpass` import inside `input()`
  — all five rejected with *"mandatory input parameters are not present: old_string"*. The serialized arguments
  show the known argument-key collapse: the `new_string` value ends `…)`,old_string:` and the intended
  `old_string` has become a JSON **key**. At `step_id=33` the model prints the correct JSON in prose and still
  emits the malformed call ("I am literally typing the arguments wrong").
- `step_id=34`: `submit_patch` → `patch_size 3806`, `files_changed 2`.

**The banked partial deletes three module-level bindings (`getpass`, `escape`, `zlib`) that the file still
references and re-binds none of them.** `Console.input(password=True)`, `export_html`, `export_svg` would raise
`NameError`. Those paths are exercised by tests that **pass at base** (`test_input_password`, `test_export_html`,
`test_export_svg`, `test_save_html`, `test_save_svg` all appear in `replays\gold\rich_4070.json:gold_pass_tests`).
So this run's "banked progress" is a Pass-to-Pass regression, i.e. strictly worse than submitting nothing.
MEASURED from the trace's own edit diffs + the replay's pass list; the exact P2P delta is INFERRED (no replay
verdict available for this task).

### 4c. Partial banking on this task is routine, not absent

`Gemma\kb\near_miss.jsonl` (nm-3), rich_4070 rows. MEASURED:
- `WROTE_GOLD_CHANGE` reached in **8 of 11** traced runs, coverage 1.0 each.
- `APPLIED` reached in 6 runs, at call **5** (v19), **11** (v19v3), **13** (v18, v2_gate_out), **18**
  (v2_gate_s05c), **22** (`_v6out`), **26** (hard arm). Four of those are early-and-incremental by any
  definition.
- Furthest stage never reaches `RESOLVED` in any of the 13 rows.

The lever's intended behaviour (edit early, edit incrementally, bank before the wall) has been produced on this
exact task at least six times and has never resolved it.

---

## 5. Failure classification (§10 definitions, verbatim labels)

- `submit_v6b/out_v6b::rich_4070` — **FOUND-NOT-LANDED / REFUSED_CALLS**. Decided by the observation class
  `REFUSED_CALLS`: the only edit-bearing call (`step_id=32`) returned `error_type BudgetExceeded`;
  `post_submit_edits = 0`; scored state = the empty `submit_patch` at `step_id=33`. MEASURED.
- `submit_v6z_on_v6w/hard/out::rich_4070` — **WRONG-FIX / UNREPLAYED**, with `stopped_by = ARG_REJECTED`
  (near_miss). Five edit calls rejected for a missing mandatory parameter. Per §10 this is **tool-call
  malformation, NOT INFRA** — it comes from the submitted config, so the row stays stage-classified and carries
  the `~`-family marker. MEASURED.
- `submit_v21/out_v21::rich_4070` — FOUND-NOT-LANDED / REFUSED_CALLS; near_miss `where: "text"` only (the gold
  change appeared in prose, not in tool args) — a low-specificity heuristic hit, flagged as such.
- Remaining 8 rows: WRONG-FIX ×6 (UNREPLAYED), LOCATE/NO_GOLD_FILE ×1, no-trace ×2 (v14/v15).

Aggregate: 13 attempts, **0 RESOLVED**, 0 post-submit edits.

---

## 6. Replays / tests run (command + result)

| command | result |
|---|---|
| `python kb\build_kb.py check-fresh` | `FRESH` (exit 0) — no rebuild |
| `python kb\build_kb.py report-path --date 2026-10-14 --slug apply-as-you-go-prompt --kind audit` | this path (exit 0) |
| `python kb\build_kb.py card --task rich_4070` | 13 rows, 0 resolved (§4) |
| `python kb\build_kb.py leakcheck --scope config kb\proposals\2026-10-11-apply-as-you-go-prompt.md` | **exit 1** — `LEAK task_id: rich_4070`, `LEAK task_id: rich_4077` |
| `python kb\build_kb.py leakcheck --scope tooling kb\proposals\…` | `LEAKCHECK CLEAN` (exit 0) |
| `python kb\build_kb.py leakcheck --scope config submit_v6w\out_v6w\submission\prompts\system.md` | `LEAKCHECK CLEAN` (exit 0) — the already-shipped lever text is leak-free |
| read `kb\replays\gold\rich_4070.json` | `gold_first INVALID`; base 106P/7F, gold 107P/6F → gold flips exactly 1 test; `test_input_password` in `gold_pass_tests` |
| raw-trace reads (v6b steps 28-35; hard arm steps 5-7, 25-36) | §4a, §4b |
| `python kb\build_kb.py claims --task rich_4070` / `--text "as you go\|bank"` | **filters are no-ops in this build** — both returned the same unfiltered claim stream. Worked around with a raw `Select-String` grep of the log (the §2/§3 citations). Tooling gap, reported. |

**No replay was run, because this build has no `replay` subcommand** (`build_kb.py` accepts only
`build, check-fresh, report-path, preflight, verdict, leakcheck, card, claims, pull`). The agent brief's
`B replay --task … --candidate …` does not exist here, so the hand-built-candidate route is unavailable; and
rich_4070's `gold_first = INVALID` means the engine would return no verdict for it anyway. I did **not** create
a git worktree by hand (that writes refs into the shared clone and would trip CloneGuard). The missing datum is
named in §9.

No Kaggle push, no submit, no git write. Scratch files were written only under `%TEMP%` and removed.

---

## 7. Variance

Similar-config replicates on rich_4070 (same 0.18 family: 28 calls / 8 min / 80 turns / 240s, tool sets within
the v6 family): `submit_v6b/out_v6b` (28 calls, 0 chars, edit_file removed, thinking 4096) and
`submit_v6z_on_v6w/hard/out` (26 calls, 3806 chars, edit_file primary). Those differ in tool surface and
thinking, so they are **not** replicates; there are **no same-config replicates** of rich_4070 anywhere in
`runs.jsonl`. Flip rate across all 13 rows and all configs: **0/13**. At temperature 0.2, n=1 per config, no
single-run difference on this task is separable from noise — which also means the hard arm's 3,806 chars is one
observation, not a rate. MEASURED (absence of replicates), INFERRED (noise statement).

Cross-config consistency that is worth more than any single run: `ARG_REJECTED`/`REFUSED_CALLS` is the
`stopped_by` on 6 of the 11 traced rich_4070 rows (v19_lora, v19v3, v21, v6b, hard, v2_gate_out, v2_gate_s05c),
i.e. the malformed-argument / budget-wall family dominates this task's failure mode across six different
configs. MEASURED (`near_miss.jsonl`).

---

## 8. Rules check

| rule | status |
|---|---|
| Pre-register the bar (accountability #2; protocol "Pre-register before every gate run") | **FAIL as submitted** — the proposal states no threshold, no baseline it must beat, and no task set. |
| External judge only (#1) | n/a yet — nothing run. The intended judge (free rich gate) is correct in kind. |
| One change per submission (#7; protocol ablation discipline) | **FAIL** — applied to v6b it is *two* changes vs the live-best (base v6w→v6b plus the instruction), and vs v6w it is *zero* changes (already present, §2). |
| Floor-guaranteed composition (#15) | **FAIL in spirit** — basing on v6b starts below the known-good floor; the log's own correction puts v6b at 1/6 vs v6's 2/6 on the identical sample (`:L9276`). |
| Tune before concluding (#13) | n/a (nothing measured yet), but note the lever has never been swept — it exists at exactly one phrasing since v6c. |
| Novelty leads, rigor serves it (#10/#11/#18) | Honoured in the verdict: the *idea* "rich_4070 is winnable on partial progress" is **supported** by new ground truth (§3) and is NOT being sent back to the herd. What is rejected is the *specific change*, because it is already in the baseline and its behaviour has already been observed failing on the target (§4b/§4c). The debugging task it points at is the malformed-argument mechanism, named in §9/§10. |
| Honest nulls are results (#3) | Honoured — §4c is reported as a null for the lever. |
| Negative space (#19) | Applied: the *absence* of any resolve across 13 attempts **despite** 8/11 runs reaching WROTE_GOLD_CHANGE at coverage 1.0 is the signal. Opportunity was there; conversion never was. |
| Free gate first (protocol) | n/a yet; any revised change must still go to the free 5-task rich gate before the scored slot. |
| Rich-only / protocol 5-task gate | The proposal implies a single-task test on rich_4070; the standing rule is a 5-task rich gate (reiterated in `:L9286-L9291`). |
| Leakcheck on the proposed prompt text | **CANNOT BE SATISFIED** — no concrete prompt text was supplied, so there is nothing to check. The proposal *document* fails `--scope config` on its two bare task ids and is CLEAN under `--scope tooling`; that is expected for a proposal doc and is not itself a defect. |

### Live-best baseline reconciliation (required)

- `.kiro\steering\gemma-submission-protocol.md` now states **"v6w @ 0.15 is SACRED (live-best) — Kaggle
  submission 57098497"**. It **agrees** with `kb\curated\run_labels.json:baseline` and
  `kb\curated\submissions.csv` (57098497, COMPLETE, publicScore 0.15). The brief's note that steering still
  says "v6 @ 0.12 (STALE)" is itself out of date — steering has been corrected. **Reported, not adopted
  blindly:** I use **v6w @ 0.15**, cited to `submissions.csv`.
- The now-stale artefact is inside the log: `GEMMA_EXPERIMENT_LOG.md:L8` READ-THIS-FIRST bullet 4 still reads
  "LIVE-BEST = v6 @ 0.12 (SACRED)". `log_claims.md` marks that entry SUPPORTED only for the 0.12 figure.
  Finding, surfaced; the log is not mine to edit.
- `submit_branch_final` / submission 57146757 is **PENDING, no score** — any bar depending on it stays
  NEEDS-DATA. Note also that `submissions.csv` has no row for ref **57201051** ("B_temp1") which the log cites
  at `:L9205`; the curated history may trail the log by one or more submissions. A read-only
  `B pull` of submissions would close that gap. It does not affect this verdict (the baseline is confirmed by a
  COMPLETE row).

---

## 9. Cheapest falsifying test

The cheapest test that could have saved the proposal was **"has this text already shipped?"** — one
`Select-String` over `submit_*/**/prompts/system.md`. I ran it (§2): the instruction is present at line 22 of
the live-best prompt. That alone falsifies "add one generic instruction".

The cheapest test for the *underlying* question ("is rich_4070 winnable on partial progress?") is a gold-subset
replay: apply **only** the two `rich/console.py` getpass hunks to `base_commit fc41075a…` and run
`tests/test_console.py::test_input_password` plus the console/syntax P2P set. Expected if §3 is right: that one
test flips fail→pass and nothing else regresses. **This build cannot run it** — no `replay` subcommand, and
`gold_first` for rich_4070 is INVALID so the engine would withhold a verdict. The data to collect is named in
§10.

A second cheap test, already run as a by-product: if "bank partial progress" were the binding constraint, no run
should have banked much. `Outputs/v14` banked 5,138 chars and `hard` banked 3,806 — both WRONG-FIX. Falsified.

---

## 10. Verdict rationale — REJECT

Five independent grounds, each MEASURED:

1. **It is a disguised RE-RUN already in the baseline.** The exact instruction is section
   `## BANK PROGRESS AS YOU GO (multi-item fixes)` at line 22 of
   `submit_v6w\out_v6w\submission\prompts\system.md` (live-best, v6w @ 0.15) and of five other v6-family
   prompts, introduced as v6c change-set item 3 on 2026-10-11 explicitly to target rich_4070
   (`GEMMA_EXPERIMENT_LOG.md:L6921`). Against the current frozen base the proposed change is a **no-op**.
2. **Against v6b it is not one change, and it lowers the floor.** v6b is a measured regression
   (1/6 vs v6's 2/6 on the identical sample, `:L9276`), so "v6b + instruction" changes the base *and* the
   prompt, violating one-change discipline and the floor-guarantee rule.
3. **The behaviour it wants has already occurred on the target task, repeatedly, without resolving it.**
   `APPLIED` reached at calls 5/11/13/13/18/22/26 across six configs; `WROTE_GOLD_CHANGE` coverage 1.0 in 8 of
   11 traced runs; 0/13 resolved (`near_miss.jsonl`, `card --task rich_4070`).
4. **On this task, banking partials earlier is actively harmful, and that is measured, not theorised.** The
   hard arm's 3,806-char banked patch deletes the module-level `getpass`, `escape` and `zlib` bindings that
   `rich/console.py` still calls and re-binds none of them, because the five calls that would have re-bound
   `getpass` were destroyed by the argument-key collapse bug (steps 29-33). The v6b refused call at step 32 has
   the same defect plus self-admitted syntax errors. Instructing "edit sooner, edit more" multiplies partial,
   half-applied items of this shape.
5. **The real blocker is a different, already-pre-registered mechanism.** Six of eleven traced rich_4070 rows
   stop on `ARG_REJECTED`/`REFUSED_CALLS`. The malformed-argument-key family is exactly what the prior two-pass
   audit (`kb\audits\2026-10-14-rich-near-miss-forensic-final.md`, verdict REVISE,
   `GEMMA_EXPERIMENT_LOG.md:L9210`) identified and already has a revised, paired-gate plan for. Spending the
   next gate on a no-op prompt line would displace it.

No pre-registered bar is issued, because the verdict is not PROCEED.

### What the proposal got right, and the revised hypothesis worth taking forward (not gated here)

- Its **lead was correct**: v6b `rich_4070` step 32 *is* an edit-bearing `run_command` python-replace on
  `rich/console.py`, so "0 edits attempted" was false. Confirmed independently of the earlier audit.
- Its **question 2 was the right question, and the answer is a genuinely new finding**: the hidden test does
  reward partial progress here — the Fail-to-Pass is 2 hunks in 1 of the 9 files (the `getpass` deferral in
  `Console.input()`), and the gold flips exactly one local test. rich_4070's "HARD / genuine difficulty / out
  of scope" label is an artefact of gold-patch size, not of what the test requires (§3).
- The **revisable successor** (a different change, needing its own audit): an *atomicity* rule rather than an
  *earliness* rule — never let one item's "remove the binding" and "re-bind it" land in different tool calls;
  if the second half fails, revert the first half before submitting. Plus the malformed-argument fix already
  pre-registered. Both must be phrased generically (no task ids, no file names) and leakchecked as text.
- **Data to collect** before anyone re-opens rich_4070: (a) make the replay engine runnable for a hand-built
  candidate (`replay` subcommand absent in this build) and repair rich_4070's local gold so `gold_first`
  validates, then replay the getpass-only subset against `test_input_password`; (b) a read-only
  `python kb\build_kb.py pull` of submissions history to close the 57201051 gap in `curated\submissions.csv`.
  Neither is required for this REJECT.

---

## 11. What the suggestion missed

1. That the instruction it proposes **is already in the live-best prompt, verbatim, at line 22**, and has been
   since v6c on 2026-10-11 — written for this very task.
2. That its chosen base, **v6b, is a measured regression** (1/6 vs v6's 2/6), already corrected in the log.
3. That the refused v6b edit it cites as near-success **would have broken `rich/console.py`** (deletes bindings
   without re-binding; model's own "this is wrong syntax" / "hope for the best" comments inline).
4. That a run **has already banked 3,806 chars incrementally on rich_4070** (`submit_v6z_on_v6w/hard`) and the
   result was a Pass-to-Pass regression, not a partial win.
5. That the **Fail-to-Pass is a single item** — so "apply each item as you find it" without an ordering or
   atomicity rule is ~1-in-14 on the item that decides the task, and the destructive half of that item lands
   first.
6. That the measured blocker on that exact item is the **malformed `edit_file` argument-key bug** (5 straight
   refusals), not commit timing.
7. That **`rich_4070` has no same-config replicate anywhere**, so a one-task single-run gate could not
   distinguish a flip from noise even if it fired.
8. That the proposal supplies **no pre-registered bar, no task set, and no prompt text to leakcheck** — three
   preconditions a PROCEED requires.
9. That the standing **RICH_48 difficulty label for this task is derived from gold-patch sprawl**, which its
   own document calls the high-confidence axis — and which this test_patch contradicts.

---

## 12. Measured vs inferred

**MEASURED** (file + line/step cited above): the `BANK PROGRESS AS YOU GO` text and its presence in v6w/v6c/
v6t/v6v/v6x/v6y/t4096; the v6c pre-registration naming rich_4070; gold = 9 files / 33 hunks and the 3,096-char
itemised problem statement; the 875-char test_patch content and `added_tests = []`; the replay's 106P/7F →
107P/6F differential and `gold_first INVALID`; all 13 `card` rows and 0/13 resolved; the v6b steps 30/31/32/33
content and `BudgetExceeded`; the hard arm's steps 5-7 / 25-28 successful edits and 29-33 five rejections with
the collapsed argument key; `near_miss` stages and `stopped_by` values; the leakcheck exit codes; the baseline
rows in `submissions.csv` and `run_labels.json`; the absence of a `replay` subcommand and the non-functional
`claims` filters.

**INFERRED** (reasoned, not executed): that `test_input_password` specifically is the Fail-to-Pass (the
measured +1-test differential and the pass list are consistent with it, but no replay confirms it for this
task); that the `tests/test_syntax.py` edit is P2P-only; that the hard arm's submitted patch would fail
`test_export_html` / `test_export_svg` / `test_save_html` / `test_save_svg` / `test_input_password` by
`NameError` (follows from the deleted bindings, not replay-verified); the exact P2P delta of any partial;
the noise statement at temperature 0.2, n=1.

**UNVERIFIABLE here**: whether a getpass-only partial would actually resolve rich_4070 on the real harness
(blocked by the INVALID local gold and the missing replay command); the status of submission 57201051.

<!-- AUDIT-JSON
{"schema": "gemma-audit/1", "mode": "AUDIT", "verdict": "REJECT",
 "proposal": "c:\\Users\\Biges\\OneDrive\\Documents\\Desktop\\kAGGLE\\Gemma\\kb\\proposals\\2026-10-11-apply-as-you-go-prompt.md",
 "kb_inputs_fingerprint": "645cfb03047649cea58aadfa9fedc71e53d634a417d34f69c4e6ca1807b447d4",
 "targets": ["rich_4070"],
 "prior_art": [
  {"lever": "apply-as-you-go / BANK PROGRESS AS YOU GO (multi-item fixes)", "tag": "RE-RUN", "runs": ["submit_v6c/out_v6c", "submit_v6t/out_v6t", "submit_v6v/out_v6v", "submit_v6w/out_v6w", "submit_v6x/out_v6x", "submit_v6y/out_v6y"]},
  {"lever": "landed partial edit scores (same semantics, no heading)", "tag": "RE-RUN", "runs": ["submit_v6z_on_v6w/hard/out"]},
  {"lever": "prompt commitment channel declared exhausted (standing truth bullet 5)", "tag": "RE-RUN", "runs": ["Outputs/v19", "Outputs/v19v3", "submit_v21/out_v21"]},
  {"lever": "base = v6b (measured regression 1/6 vs v6 2/6)", "tag": "RE-RUN", "runs": ["submit_v6b/out_v6b", "_v6out"]}
 ],
 "per_task": [
  {"run_id": "submit_v6b/out_v6b", "task": "rich_4070", "failure_class": "FOUND-NOT-LANDED", "subclass": "REFUSED_CALLS", "evidence": ["Gemma/submit_v6b/out_v6b/results/traces/trace_rich_4070.json#step_id=30", "Gemma/submit_v6b/out_v6b/results/traces/trace_rich_4070.json#step_id=32", "Gemma/submit_v6b/out_v6b/results/traces/trace_rich_4070.json#step_id=33"]},
  {"run_id": "submit_v6z_on_v6w/hard/out", "task": "rich_4070", "failure_class": "WRONG-FIX", "subclass": "ARG_REJECTED", "evidence": ["Gemma/submit_v6z_on_v6w/hard/out/results/traces/trace_rich_4070.json#step_id=25", "Gemma/submit_v6z_on_v6w/hard/out/results/traces/trace_rich_4070.json#step_id=29", "Gemma/submit_v6z_on_v6w/hard/out/results/traces/trace_rich_4070.json#step_id=33", "Gemma/submit_v6z_on_v6w/hard/out/results/traces/trace_rich_4070.json#step_id=34"]},
  {"run_id": "submit_v21/out_v21", "task": "rich_4070", "failure_class": "FOUND-NOT-LANDED", "subclass": "REFUSED_CALLS", "evidence": ["Gemma/kb/near_miss.jsonl#run=submit_v21/out_v21,task=rich_4070,step_id=22"]},
  {"run_id": "Outputs/v19_lora", "task": "rich_4070", "failure_class": "FOUND-NOT-LANDED", "subclass": "ARG_REJECTED", "evidence": ["Gemma/kb/near_miss.jsonl#run=Outputs/v19_lora,task=rich_4070,step_id=26"]},
  {"run_id": "_v6out", "task": "rich_4070", "failure_class": "WRONG-FIX", "subclass": "UNREPLAYED", "evidence": ["Gemma/kb/near_miss.jsonl#run=_v6out,task=rich_4070,step_id=24"]}
 ],
 "claims": [
  {"id": "A1", "text": "The proposed instruction already exists verbatim as section 'BANK PROGRESS AS YOU GO (multi-item fixes)' at line 22 of the live-best v6w system prompt.", "basis": "MEASURED", "evidence": ["Gemma/submit_v6w/out_v6w/submission/prompts/system.md#L22-L23"]},
  {"id": "A2", "text": "That section was introduced as v6c change-set item 3 on 2026-10-11, explicitly to target rich_4070's '10 symbols traced, 0 edits banked' failure.", "basis": "MEASURED", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#L6921"]},
  {"id": "A3", "text": "rich_4070 has 13 runs in the KB and 0 resolved.", "basis": "MEASURED", "evidence": ["Gemma/kb/runs.jsonl#task=rich_4070"]},
  {"id": "A4", "text": "v6b rich_4070 step_id=32 is an edit-bearing run_command python-replace on rich/console.py refused with BudgetExceeded, so 'no edit attempted' is false.", "basis": "MEASURED", "evidence": ["Gemma/submit_v6b/out_v6b/results/traces/trace_rich_4070.json#step_id=32"]},
  {"id": "A5", "text": "That refused v6b payload deletes module-level bindings without re-binding them and contains the model's own 'this is wrong syntax' admissions, so it would have broken rich/console.py.", "basis": "MEASURED", "evidence": ["Gemma/submit_v6b/out_v6b/results/traces/trace_rich_4070.json#step_id=32"]},
  {"id": "A6", "text": "The hard arm already applied-as-it-went on rich_4070: 7 successful incremental edits across logging.py and console.py, 3806 chars submitted.", "basis": "MEASURED", "evidence": ["Gemma/submit_v6z_on_v6w/hard/out/results/traces/trace_rich_4070.json#step_id=5", "Gemma/submit_v6z_on_v6w/hard/out/results/traces/trace_rich_4070.json#step_id=25", "Gemma/submit_v6z_on_v6w/hard/out/results/traces/trace_rich_4070.json#step_id=34"]},
  {"id": "A7", "text": "Five consecutive attempts to add the deferred getpass import were rejected for a missing old_string because the argument key collapsed into the new_string value.", "basis": "MEASURED", "evidence": ["Gemma/submit_v6z_on_v6w/hard/out/results/traces/trace_rich_4070.json#step_id=29", "Gemma/submit_v6z_on_v6w/hard/out/results/traces/trace_rich_4070.json#step_id=33"]},
  {"id": "A8", "text": "The hard arm's banked patch removed the module-level getpass, escape and zlib bindings that console.py still references, so it is a Pass-to-Pass regression rather than partial progress.", "basis": "INFERRED", "evidence": ["Gemma/submit_v6z_on_v6w/hard/out/results/traces/trace_rich_4070.json#step_id=25", "Gemma/kb/replays/gold/rich_4070.json#gold_pass_tests"]},
  {"id": "A9", "text": "rich_4070's gold flips exactly one local test (base 106P/7F -> gold 107P/6F) and test_input_password is in gold_pass_tests.", "basis": "MEASURED", "evidence": ["Gemma/kb/replays/gold/rich_4070.json#base", "Gemma/kb/replays/gold/rich_4070.json#gold"]},
  {"id": "A10", "text": "The test_patch pins the Fail-to-Pass to the getpass deferral inside Console.input(): 2 hunks in 1 of the 9 gold files, with zero added tests.", "basis": "INFERRED", "evidence": ["Gemma/comp_files/tasks.jsonl#instance_id=rich_4070", "Gemma/kb/tasks_gold.json#tasks.rich_4070.tests"]},
  {"id": "A11", "text": "The problem statement is 3096 chars and names every item including the getpass deferral, so the RICH_48 premise of terse 138-char PR titles does not hold for this task.", "basis": "MEASURED", "evidence": ["Gemma/comp_files/tasks.jsonl#instance_id=rich_4070", "Gemma/RICH_48_DIFFICULTY_MAP.md#L100-L114"]},
  {"id": "A12", "text": "RICH_48_DIFFICULTY_MAP labels rich_4070 HARD / GENUINE DIFFICULTY off gold-patch sprawl (9 files, 128 lines), a basis the test_patch contradicts.", "basis": "MEASURED", "evidence": ["Gemma/RICH_48_DIFFICULTY_MAP.md#L91", "Gemma/RICH_48_DIFFICULTY_MAP.md#L165"]},
  {"id": "A13", "text": "near_miss shows APPLIED reached at calls 5,11,13,13,18,22,26 across six configs on rich_4070 with WROTE_GOLD_CHANGE coverage 1.0 in 8 of 11 traced rows, and never RESOLVED.", "basis": "MEASURED", "evidence": ["Gemma/kb/near_miss.jsonl#task=rich_4070"]},
  {"id": "A14", "text": "v6b is a measured regression versus v6 on the identical 6-task sample (1/6 vs 2/6), so basing the change on v6b lowers the floor.", "basis": "MEASURED", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#L9276"]},
  {"id": "A15", "text": "Baseline is v6w @ 0.15 (submission 57098497, COMPLETE); gemma-submission-protocol.md now agrees with run_labels.json, while the log's READ-THIS-FIRST bullet 4 still says v6 @ 0.12 and is the stale artefact.", "basis": "MEASURED", "evidence": ["Gemma/kb/curated/submissions.csv#ref=57098497", "Gemma/kb/curated/run_labels.json#baseline", "c:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE/.kiro/steering/gemma-submission-protocol.md", "Gemma/GEMMA_EXPERIMENT_LOG.md#L8"]},
  {"id": "A16", "text": "No same-config replicate of rich_4070 exists, so a single-task gate on it cannot separate a flip from noise.", "basis": "MEASURED", "evidence": ["Gemma/kb/runs.jsonl#task=rich_4070"]},
  {"id": "A17", "text": "This build has no replay subcommand and the claims --task/--text filters return the unfiltered stream, so a gold-subset replay and the lexicon claim queries were unavailable.", "basis": "MEASURED", "evidence": ["Gemma/kb/build_kb.py#argparse-cmd-choices"]}
 ],
 "tests_run": [
  {"cmd": "python kb\\build_kb.py check-fresh", "result": "FRESH (exit 0)"},
  {"cmd": "python kb\\build_kb.py report-path --date 2026-10-14 --slug apply-as-you-go-prompt --kind audit", "result": "exit 0, path printed, file did not exist"},
  {"cmd": "python kb\\build_kb.py card --task rich_4070", "result": "13 rows, 0 resolved; 2 rows no-trace"},
  {"cmd": "python kb\\build_kb.py leakcheck --scope config kb\\proposals\\2026-10-11-apply-as-you-go-prompt.md", "result": "exit 1 - LEAK task_id rich_4070, rich_4077 (bare ids in proposal prose)"},
  {"cmd": "python kb\\build_kb.py leakcheck --scope tooling kb\\proposals\\2026-10-11-apply-as-you-go-prompt.md", "result": "LEAKCHECK CLEAN (exit 0)"},
  {"cmd": "python kb\\build_kb.py leakcheck --scope config submit_v6w\\out_v6w\\submission\\prompts\\system.md", "result": "LEAKCHECK CLEAN (exit 0)"},
  {"cmd": "Select-String -Path submit_*/**/prompts/system.md -Pattern 'BANK|as you go'", "result": "hits in v6c, v6t, v6v, v6w, v6x, v6y, submit_t4096 (line 22); 0 hits in v6b, v21, v22, v6s, all v6z arms"},
  {"cmd": "read kb\\replays\\gold\\rich_4070.json", "result": "gold_first INVALID; base 106P/7F, gold 107P/6F; test_input_password in gold_pass_tests"},
  {"cmd": "python - trace dump submit_v6b/out_v6b steps 28-35", "result": "step30 16-item checklist incl. both getpass items; step31 get_status 0 remaining; step32 python-replace refused BudgetExceeded, payload deletes bindings without re-binding; step33 empty submit"},
  {"cmd": "python - trace dump submit_v6z_on_v6w/hard/out edit calls", "result": "steps 5,6,7,25,26,27,28 ok; steps 29-33 edit_file rejected 'old_string not present'; step34 submit_patch 3806 chars / 2 files"},
  {"cmd": "python - tasks.jsonl rich_4070 patch + test_patch + problem_statement", "result": "patch 13445 chars / 9 files / 33 hunks; test_patch 875 chars / 2 existing test files / 0 added tests; problem_statement 3096 chars naming the getpass item"},
  {"cmd": "python kb\\build_kb.py claims --task rich_4070", "result": "filter is a no-op in this build; fell back to raw Select-String grep of the log"}
 ],
 "missed": [
  "The instruction already ships verbatim at line 22 of the live-best v6w prompt (since v6c, 2026-10-11).",
  "v6b is a measured regression (1/6 vs v6 2/6) so basing on it is a second change and lowers the floor.",
  "The refused v6b edit would have broken rich/console.py (deletes bindings, no re-bind, self-admitted syntax errors).",
  "A run has already banked 3806 chars incrementally on rich_4070; the result was a Pass-to-Pass regression.",
  "The Fail-to-Pass is a single item of ~14, so 'apply each item as you find it' has no ordering or atomicity guarantee.",
  "The measured blocker on that item is the malformed edit_file argument-key bug (5 consecutive refusals), not commit timing.",
  "rich_4070 has no same-config replicate, so a single-task gate cannot separate a flip from noise.",
  "No pre-registered bar, no task set, and no prompt text to leakcheck were supplied.",
  "The RICH_48 HARD label for rich_4070 is derived from gold-patch sprawl, a basis the test_patch contradicts."
 ],
 "proposed_curations": [
  {"id": "rich_4070_f2p_scope", "kind": "ground_truth", "task": "rich_4070", "text": "Gold is 9 files / 33 hunks, but the hidden test adds no tests and the gold flips exactly one local test; the Fail-to-Pass is the getpass deferral into Console.input() in rich/console.py (2 hunks, 1 file). Treat the HARD/sprawl label as a gold-patch-size artefact, not a statement of what the test requires.", "status": "SUPPORTED", "basis": "comp_files/tasks.jsonl#rich_4070 test_patch; kb/replays/gold/rich_4070.json base 106P/7F vs gold 107P/6F", "confidence": "MEASURED differential, INFERRED test identity"},
  {"id": "apply_as_you_go_shipped_v6c", "kind": "lever", "lever": "apply-as-you-go / BANK PROGRESS AS YOU GO", "text": "Shipped as v6c change-set item 3 on 2026-10-11 and present at line 22 of every v6c-descendant prompt including the live-best v6w. Any new proposal to 'add' it is a RE-RUN against the current base.", "status": "SUPPORTED", "basis": "submit_v6w/out_v6w/submission/prompts/system.md#L22; GEMMA_EXPERIMENT_LOG.md#L6921"},
  {"id": "rich_4070_partial_is_destructive", "kind": "finding", "task": "rich_4070", "text": "Banking partial items on rich_4070 has been observed to regress Pass-to-Pass: submit_v6z_on_v6w/hard deleted the module-level getpass/escape/zlib bindings and never re-bound them because 5 consecutive edit_file calls died on the argument-key collapse. Earliness is not the lever; per-item atomicity plus the malformed-argument fix is.", "status": "SUPPORTED", "basis": "submit_v6z_on_v6w/hard/out/results/traces/trace_rich_4070.json#step_id=25,29..33,34"},
  {"id": "log_live_best_stale_L8", "kind": "log_correction", "text": "GEMMA_EXPERIMENT_LOG.md READ-THIS-FIRST bullet 4 still reads 'LIVE-BEST = v6 @ 0.12 (SACRED)'. submissions.csv (57098497, COMPLETE, 0.15), run_labels.json:baseline and the current gemma-submission-protocol.md all say v6w @ 0.15. The log line is the stale artefact.", "status": "CONTRADICTED", "basis": "kb/curated/submissions.csv; kb/curated/run_labels.json; .kiro/steering/gemma-submission-protocol.md"},
  {"id": "tooling_gap_replay_and_claims", "kind": "tooling", "text": "build_kb.py in this build exposes no 'replay' subcommand (so hand-built candidate replays per the auditor brief are impossible) and the 'claims --task/--text/--lever' filters return the unfiltered stream. Audits must fall back to raw greps, and rich_4070's gold_first is INVALID so no replay verdict exists for it regardless.", "status": "SUPPORTED", "basis": "python kb/build_kb.py replay --help -> invalid choice; kb/replays/gold/rich_4070.json#gold_first"},
  {"id": "submissions_csv_trails_log", "kind": "data_gap", "text": "The log cites submission ref 57201051 (B_temp1) but curated/submissions.csv has no such row; newest row is 57146757 PENDING. A read-only submissions pull would reconcile. Does not affect the v6w @ 0.15 baseline, which is confirmed COMPLETE.", "status": "UNVERIFIED", "basis": "GEMMA_EXPERIMENT_LOG.md#L9205; kb/curated/submissions.csv"}
 ]}
-->
