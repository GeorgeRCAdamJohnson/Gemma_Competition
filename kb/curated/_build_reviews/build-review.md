# Build review — Gemma Auditor iteration 2 (static edit reconstruction §8, near-miss nm-3 §9.2/§9.4, gold-first replay rp-3 §13)

**Verdict**: APPROVED

This iteration delivers the three capabilities iteration 1 deferred, against the approved design
(REVISION 4): static edit reconstruction (§8), the line-level near-miss matcher nm-3 with a measured
cross-task false-positive control (§9.2/§9.4), and the gold-first git-worktree replay engine rp-3 (§13).
I judged from recorded evidence — the on-disk `kblib/` sources, the generated KB artifacts, the replay
cache/gold records, `clone_state.json`, `build_meta.json`, and `build_verification.md` — plus the design
sections §8, §9.2, §9.4, §13. I spot-read two replay cache `result.json` files (one passing agent
candidate, one failing) to confirm the replay table's claims are backed by real JUnit evidence; I did not
re-run the replay suite or the test suite, per the gate instruction. No blocking finding holds.

Watch for: (1) `clone_state.json` on disk records 8 module-file checks and ZERO external drift, while
`build_verification.md` narrates "29 checks" and "external drift on rich" from an earlier run — a stale
narrative, not a code defect, since the current artifact is the clean one (NIT). (2) `replay._run_git_env`
runs `git add -N .` / `git diff --binary` directly, bypassing the `gitio` allowlist entry point; the two
verbs are read/stage-only in the throwaway worktree with objects redirected to the scratch store, so no
clone mutation is possible, but it is an un-allowlisted git path (NIT). (3) The tracked files
`GEMMA_EXPERIMENT_LOG.md`, `submit_v19_lora_v2/kernel-metadata.json`, `local_eval/run_local.py`,
`PAPER_FINDING1_DRAFT.md` show as modified in `git status`, but none are builder-attributable (see below).

## Why no blocking finding holds

The eight blocking conditions were each checked against evidence:

- **Gold-first violations.** None. Every one of the 44 `replays.jsonl` rows carries `gold_local: "Y"` and
  `gold_first` in {VALID-HARNESS-LIKE, VALID-GOLD-RELATIVE}. Every `agent_passed` of `Y`/`N` carries a real
  `candidate_sha` + `result: "RAN"` and a matching cache dir. No agent candidate is counted as a pass/fail
  for a task whose gold did not pass locally. (§13.5)
- **Agent code executed outside the allowlisted %TEMP% worktree, or with no allowlist check.** None. Static
  reconstruction (`reconstruct.py`, `bashpy.py`) is pure symbolic evaluation over a VFS: `ast.parse` + a
  hand-rolled interpreter, no `exec`/`eval`, no subprocess/os process API (AST-enforced by
  `test_reconstruct_no_exec_apis_in_source`). The replay engine executes only inside detached worktrees
  under `%TEMP%/gkb_<pid>_<hex>/wt_<task>`, with `GIT_OBJECT_DIRECTORY` redirected to a throwaway store,
  teardown in `finally`. `gitio.git()` enforces a verb allowlist that makes commit/push/fetch/config/stash/
  gc and main-clone reset/checkout impossible (`test_gitio_allowlist_*`). (§8, §13.2)
- **Near-miss matcher with no stated/measured FP control.** Present and measured. `nearmiss.cross_task_fp`
  evaluates WROTE_GOLD_CHANGE on 6,361 (trace, other-task) pairs; 39 fire = 0.613 %, against a
  pre-registered bar ≤ 1 % → PASS. Recorded in `build_meta.json:near_miss_fp` and KB_SUMMARY §10. (§9.4)
- **Writes outside allowed locations.** None builder-attributable. `safe_write` is the sole write path and
  rejects `curated/`, `proposals/`, `audits/`, `replays/manual/`, the log, and `.kiro/steering/*`; it allows
  only the nine generated files + the `replays/`/`nearmiss_cache/` prefixes. The modified tracked files are
  not builder outputs: `kernel-metadata.json` (10/11) and `PAPER_FINDING1_DRAFT.md` (10/11) predate the
  10/15 build; `GEMMA_EXPERIMENT_LOG.md` and `run_local.py` were last written before the build stamp and the
  log is a read-only input (documented live drift). The builder's generated artifacts all live under the
  untracked `kb/`.
- **Non-idempotent builder.** `build_verification.md` records two plain builds byte-identical (idempotence
  check excludes only the stamp lines + `build_stamp.json`), and two `build --replay --deadline-s 1500`
  runs against a stable log byte-identical. The replay cache is add-only, keyed by (task, candidate sha256);
  `replays_pending: 0`. Determinism fixes (inverted index frozen to sorted tuples, sorted hit iteration,
  volatile `from_cache` dropped) are in `nearmiss.py`/`replay.py` as described.
- **Clones left dirty / builder-attributable change.** `clone_state.json`: `builder_safe: true`,
  `verdict: "CLEAN (no builder-attributable change)"`, empty `builder_diffs` for both rich and fastapi,
  `external_drift_present: false`, all 8 module-file checks `under_worktree: true`. CloneGuard compares
  builder-controllable fields (refs/config/count-objects) only; external HEAD drift (the user moves the
  checkout) is classified EXTERNAL per §13.3, and here even that is absent.
- **Replay table claiming passes it cannot show evidence for.** Every `agent_passed: Y` maps to a cache
  `result.json` with a JUnit-backed PASS. Spot-checked `rich_4079/_v6out` (`a645917018d5`): 8 passed,
  `required_pass: true`, `harness_like: true`, import under worktree. Spot-checked `rich_4070/_v6out`
  (`84d665bf`): 2 collection errors → `required_pass: false` → table shows agent N (honest). Non-resolvers
  and bash/syntax-error counterfactuals are reported as nulls, not forced into passes.
- **Regression of iteration-1 guarantees.** None observed. `build_meta.json`: tasks_gold 129, traces 159,
  engine versions cm-2/fc-3/nm-3/rp-3/cl-3. cm-2 residual 0 on 159/159 and the 47/47 test pass are recorded
  in `build_verification.md` (30 original + 17 new). Baseline conflict (v6w @ 0.15 vs stale protocol v6 @
  0.12) is surfaced in the KB_SUMMARY banner. Write-boundary enforcement intact.

<details>
<summary>Issues (3)</summary>

1. **Stale verification narrative** — `build_verification.md` says "29 module-file checks" and "external
   drift on rich," but the on-disk `clone_state.json` records 8 checks and zero drift. NIT: reconcile the
   note to the current artifact; no code change needed.
2. **Un-allowlisted git path in replay** — `replay._run_git_env` issues `git add -N .` / `diff --binary`
   outside the `gitio` allowlist. NIT: route these through `gitio.git()` (add an `add`-with-excludes verb)
   so every git call shares one audited entry point. Harmless today (worktree-scoped, objects redirected).
3. **Dead `if False` branch in `_candidate_diff`** — a `... if False else None` line is a leftover scaffold.
   NIT: delete it.

</details>

<details>
<summary>Details</summary>

### Static edit reconstruction (§8) — static-only, test-enforced

`reconstruct.py::PyEval` parses each `run_command` python payload with `ast.parse` and walks a restricted
statement/expression subset (Assign/AugAssign/If/For/With/Assert/Expr; str.replace, re.sub, open().write,
Path.write_text, f-strings, `in`/`len`) over a copy-on-write `VFS`. Anything outside the subset becomes
`UNPARSED(<node> at line N)` with the snippet retained — never executed to disambiguate. The R1
escaped-quote span decoder (`extract_escaped_quote_spans`) repairs `-c '...'` payloads before parse and
preserves inner `\"` (so `Text(\"\", justify` stays intact), matching the design's MEASURED claim on v6b
rich_4079 step 31. The bash front-end (`bashpy.py`) extracts heredocs first (junk terminator like `PY'`
lands inside the body → SyntaxError, as bash behaves), tokenizes with shlex, classifies simple commands,
and flags mutations (`mv`/`cp`/`rm`/`git checkout|apply|stash|reset`, redirects to workspace paths) as
`unmodeled` rather than modelling them. `harness_edit.py` emulates `edit_file` with the competition
wheel's OWN `apply_replacement` (loaded via `zipfile`, four stub modules registered in `sys.modules`
before exec, wheel sha256 recorded) — harness source, not agent code; agent old/new strings are passed as
data. The AST guard `test_reconstruct_no_exec_apis_in_source` asserts no `exec`/`eval` and no
`subprocess`/`os.{system,popen,exec,spawn}` in `bashpy`/`reconstruct`.

### Near-miss nm-3 (§9.2) + cross-task FP control (§9.4) — measured, calibrated

`GoldIndex` builds an exact normalized-added-line map and an identifier inverted index, both frozen to
sorted tuples for determinism. `candidate_hits` matches exact first, then fuzzy only against gold lines
sharing ≥ 1 identifier, with the §9.2 ladder (length filter → identifier Jaccard ≥ 0.70 → real_quick/quick
→ `ratio() ≥ 0.90`). G2 (NEW side only) is honored: `_new_side_text` takes `new_payload` or statically
reconstructs NEW-side literals from the raw command. All 159 traced rows now carry
`confidence: "measured (nm-3 line-level)"` (verified: 0 traced rows are `low`; the 77 `low (no trace)` rows
genuinely have no trace). The cross-task control measures 0.613 % FP against the pre-registered ≤ 1 % bar
(PASS), with the unit guard `test_nearmiss_cross_task_fp_bar` asserting distinct-gold tasks yield 0 FP.

### Gold-first replay engine rp-3 (§13) — gold runs first, clones provably clean

`ReplayEngine.gold_first()` runs the gold (patch + test_patch) and base (test_patch only) controls before
any agent candidate; `run_candidate` writes reconstructed candidates by VFS content or patches via the
apply ladder, applies the protected reset + test_patch, and runs pytest through a bootstrap that exits 97
unless the imported package `__file__` is inside the worktree. Validity is assigned exactly per §13.5:
rich_4079 → VALID-HARNESS-LIKE (gold 8/0, base fails 1 required), rich_3469 → VALID-GOLD-RELATIVE (gold
passes required tests, one unrelated Windows failure → env_noise). INVALID/INFRA tasks carry
`verdict_valid: false` and their agent candidates are never counted as verdicts. The cache is add-only,
keyed by (task, candidate sha256), reused unless engine/env/fingerprint changes. CloneGuard snapshots
HEAD/status/diff/refs/config/index/count-objects before and after and fails only on builder-attributable
drift; the recorded verdict is CLEAN with no drift of any kind this run.

### Deferred items (honest nulls, not blocking)

`build_verification.md` and KB_SUMMARY §11 state the deferrals plainly: dev-harness AST pass (D3-5),
staged-submission config fields (D3-4), full claims column-mapping (§12.4), Kaggle live pulls (§14, stub),
and the R2–R5 `intent` repair ladder (only `as_run` + `counterfactual` + R1 ship this iteration;
counterfactuals needing R2–R5 are reported as BASH_ERROR/SYNTAX_ERROR nulls rather than guessed). These
are acceptable deferrals under the gate rubric.

</details>

<details>
<summary>Files reviewed</summary>

- `kblib/bashpy.py` — bash front-end (heredoc extraction, shlex tokenize, simple-command classify).
- `kblib/reconstruct.py` — static Python symbolic interpreter + R1 span decode; no exec/eval.
- `kblib/harness_edit.py` — wheel `apply_replacement` emulation of `edit_file` (harness source).
- `kblib/nearmiss.py` — nm-3 GoldIndex + stage ladder + cross-task FP control.
- `kblib/replay.py` — rp-3 ReplayEngine + CloneGuard; gold-first; worktree isolation; cache.
- `kblib/gitio.py` — single git entry point with verb allowlist.
- `kblib/io.py` — safe_write write-boundary enforcement.
- `KB_SUMMARY.md` — §10 near-miss/FP, §13 replay table (44 rows, all gold_local Y).
- `replays/replays.jsonl`, `replays/gold/*.json`, `replays/clone_state.json`, `replays/cache/**/result.json`.
- `build_meta.json`, `build_verification.md`.
- design.md §8, §9.2, §9.4, §13 and the tests `tests/test_unit.py`.

</details>
