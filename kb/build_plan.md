# Implementation Plan — Gemma Auditor deliverables 1–3

Source of truth: `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\.kiro\specs\gemma-auditor\design.md`
(**REVISION 4**, APPROVED by `Gemma\kb\curated\_build_reviews\design-review-r4.json`). This plan sequences the
design's own ordered task list (§22, tasks T1–T16) into independently verifiable steps for deliverables 1–3:

1. the KB built by one idempotent `Gemma\kb\build_kb.py` (+ `Gemma\kb\kblib\` helpers) producing `runs.jsonl`,
   `tasks_gold.json` (129 tasks), `near_miss.jsonl`, `log_claims.md`/`.jsonl`, `KB_SUMMARY.md` (with the
   BASELINE banner and the dev-harness-vs-scorer row), failure classes, and gold-first cached replays under
   `%TEMP%` worktrees;
2. the agent file `ROOT\.kiro\agents\gemma-auditor.md`;
3. the workflow recipe `ROOT\.kiro\workflows\gemma-audit.workflow.json`.

Do not re-decide the architecture. Every design decision is already made in `design.md`; this plan only orders the
build and names, per step, exactly which design sections and which §19.2 acceptance facts (the external judge for
each step) govern it. The 14 applied findings D3-1..D3-14 are each encoded in a design section; the governing
section/fact is named inline per step so none is dropped.

## Verified ground truth (read-only probe at planning time)

- Data is live and still growing (confirms the design's "assert ≥" discipline): **159** `trace_*.json` under
  `**\results\traces\` (design snapshot said 155), **30** run dirs with a `results\traces` folder,
  `GEMMA_EXPERIMENT_LOG.md` = **8799** lines (snapshot said 8750, append-only below L8552).
- `Gemma\comp_files\tasks.jsonl` = **129** lines (the 129-task gold target), `HARNESS_README.md` and
  `_whl_inspect\` present.
- `Gemma\submit_t4096\agent.yaml` and `Gemma\submit_branch_final\agent.yaml` both present (the D3-4
  staged-submission dirs).
- `Gemma\kb\curated\run_labels.json` already holds `baseline`/`prior_baseline`/`pending` (**never overwrite**;
  T1 only adds `aliases`/`pasted_logs`/`runs`). `Gemma\kb\curated\submissions.csv` (1782 B) already present
  (**read-only**, T1 does not rewrite it).
- `ROOT\.kiro\agents\gemma-auditor.md` **exists** as a draft (T14 rewrites it in place).
  `ROOT\.kiro\workflows\gemma-audit.workflow.json` **does not exist** (T15 creates it).
- Hand-maintained inputs that must never be deleted/overwritten: `Gemma\kb\curated\` (incl. `_build_reviews\`,
  `run_labels.json`, `submissions.csv`), `Gemma\kb\proposals\`, `Gemma\kb\audits\`, `Gemma\kb\replays\manual\`,
  all `Gemma\submit_*`, `GEMMA_EXPERIMENT_LOG.md`, `ROOT\.kiro\steering\*`.

## Conventions for every step

- Runtime: the `python` on PATH (CPython 3.13.14), **stdlib only at runtime** (design §3). Network only in `pull`.
- Build/test harness lives under `Gemma\kb\`. Standard commands:
  - unit tests: `python -m pytest c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\tests -q -m "not slow"`
    with env `PYTHONDONTWRITEBYTECODE=1` (design §19.1);
  - slow/integration tests on real data: same path with `-m slow` (design §19.2);
  - a build: `python c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\build_kb.py build` (+ `--replay …`
    for replay phases). Long commands (full builds, replays) run in the background with explicit timeouts
    ≤ 1,800,000 ms and are polled (design §22 preamble).
- Guards that every build step prompt must keep (never remove any of these): **gold-first replays**,
  **static edit reconstruction only — never execute agent-authored commands**, the **write-boundary allowlist**
  (`safe_write` only; never touch `submit_*`, the log, `.kiro\steering\*`, `curated\`, `proposals\`), and the
  **scorer-gaming guards** (gold patches and problem fingerprints never enter any config; `leakcheck`).
- Each step must leave the tree buildable and its named tests green before the next step starts. A missed
  pre-registered bar is reported as missed in `Gemma\kb\curated\build_verification.md`, never reframed
  (accountability rule 2).

---

# Deliverable 1 — the knowledge base and its builder

- [ ] 1. **T1 — Scaffold, seeds, fixtures.** Create `Gemma\kb\build_kb.py` as an argparse skeleton for the 10
      commands (`build, check-fresh, pull, replay, card, claims, preflight, report-path, verdict, leakcheck`) with
      `-h` per command and `GKB_GEMMA_ROOT` honoured (design §15.1). Create `kblib\paths.py`, `kblib\io.py`
      (`safe_write` with the §4 write-boundary allowlist, atomic replace, retry, skip-identical, deterministic
      JSON dumps `sort_keys=True, ensure_ascii=False`), `kblib\lock.py` (§15.3, `O_CREAT|O_EXCL`, Windows
      `ctypes` liveness, never `os.kill`), plus `Gemma\kb\pytest.ini` (`-p no:cacheprovider`; `slow` marker) and
      `Gemma\kb\tests\`. Augment the curated seeds per §7.8 **without overwriting** the on-disk
      `baseline`/`prior_baseline`/`pending`: add `aliases`/`pasted_logs`/`runs` (incl. arm aliases with
      `scope: heading` for `branch`/`hard gate`, extended to `serA/serB/lora025/branch2/maxout16k/compact5/m12`
      with `alias_sources`) to `run_labels.json`; create `lever_lexicon.json`, `replay_set.json`, and an empty
      `claims.jsonl` only if absent; **do not rewrite** `submissions.csv`. Make the log fixture copies under
      `tests\fixtures\log\`, each recording its source line and the log sha256 at copy time (D3-6).
      Files: `Gemma\kb\build_kb.py`, `Gemma\kb\kblib\__init__.py`, `kblib\paths.py`, `kblib\io.py`,
      `kblib\lock.py`, `Gemma\kb\pytest.ini`, `Gemma\kb\tests\` (+ `tests\fixtures\log\`),
      `Gemma\kb\curated\run_labels.json` (augment), `curated\lever_lexicon.json`, `curated\replay_set.json`,
      `curated\claims.jsonl` (if absent).
      Verify: `python -m pytest Gemma\kb\tests -q -m "not slow"` (io + lock tests pass, incl. `safe_write` rejects
      protected paths via exit-5 path, skips identical bytes, lock exclusivity + stale-by-age + no `os.kill` in
      source); `python Gemma\kb\build_kb.py -h` and each `<cmd> -h` exit 0; confirm the on-disk `baseline` block in
      `run_labels.json` is byte-unchanged and `submissions.csv` untouched.

- [ ] 2. **T2 — Discovery and coverage** (`kblib\discover.py`, design §5). Implement the first-match-wins kinds
      table incl. `staged-submission` (D3-4: requires NO `kernel-metadata.json`; `submit_t4096`/`submit_branch_final`),
      `reference-log` (`G\compeition\getting started`), the pasted-log location+extension rule, the
      directory-depth-8 walk with `beyond-walk-depth` listing, the >50 MB large-file rule (adapter-fingerprint
      exception reads only first+last 1 MiB), BOM-aware text decoding, the input and discovery fingerprints taken
      at discovery time (five curated inputs incl. `submissions.csv`), and `check-fresh`.
      Files: `kblib\discover.py` (+ tests under `Gemma\kb\tests\`).
      Verify: `python -m pytest Gemma\kb\tests -q -m "not slow"` (discover tests pass); then
      `python -m pytest Gemma\kb\tests -q -m slow` for acceptance **fact 21** (`compeition/getting started` →
      `reference-log`, 0 rows) and **fact 26** (`submit_t4096`/`submit_branch_final` → `staged-submission`); plus
      the coverage bar: every discovered run-ish item is classified.

- [ ] 3. **T3 — Kernel and pasted logs** (`kblib\kernellog.py`, `kblib\events.py`, design §6.1). Pass
      segmentation (label lines never start a pass; a pass opens only after ≥1 result row; empty passes dropped;
      single pass → `pass=null`), line rules P1h–P7 incl. P2h and the tolerant `(?:Evaluating )?` forms for
      PASS_START/P1h/P1r (D3-9), H1–H4/A1 run-level lines, and harness logger events L1 with the dedupe (each
      per-task event appears twice).
      Files: `kblib\kernellog.py`, `kblib\events.py` (+ tests).
      Verify: `python -m pytest Gemma\kb\tests -q -m "not slow"` (kernellog + events, incl. S12 BOM/`Evaluating`
      and D3-9 PASS_START); then `-m slow` for acceptance **facts 5, 10, 14** and the event part of **fact 9**
      (`_v10_kaggle_pull::requests_7315` has exactly one deduplicated `VERIFY_TEST_PATCH_FAIL`), plus **fact 29**
      (multi-pass `Evaluating` log keeps passes separate).

- [ ] 4. **T4 — Configs and labels** (`kblib\configs.py`, `kblib\labels.py`, design §6.3–§6.4). Field paths, the
      strict in-house YAML subset parser (with `!include`), notebook `write_text` extraction (rightmost-constant,
      `dynamic`), the dev-harness AST pass reading `EventsCompactionConfig`/`ContextCacheConfig` Call keyword args
      into `config.dev_harness` with `source` line and `dev_harness_matches_scorer` vs `HARNESS_README.md:L556`
      (D3-5; comments never read), `stop_sequences`/`sampling_extra` (D3-8), adapter fingerprint + sample
      detection, label precedence (curated > local-dir > slug-from-log-name > pulled-slug > pasted tokens),
      prompt twins, submit-dir mapping, `m12` → `out_of_scope: non-31B` (D3-7), run dates.
      Files: `kblib\configs.py`, `kblib\labels.py` (+ tests).
      Verify: `python -m pytest Gemma\kb\tests -q -m "not slow"` (configs vs PyYAML oracle where available; labels
      precedence/twins/`slug_reused`); then `-m slow` for acceptance **fact 11** (the §6.4 label table holds),
      **fact 27** (compact5→5 via AST, submit_v15→15 not its comment, `matches_scorer` flags), **fact 28** (m12
      out-of-scope).

- [ ] 5. **T5 — Traces** (`kblib\traces.py`, design §6.2). Observation classes incl. `ARG_REJECTED`/`REFUSED_TIME`,
      malformed rules incl. swallowed-sibling values (S14), argument salvage, text-call parsing with the
      backtick-skip + identical-`(fn,args_raw)` dedupe `quoted_repeat` (D3-10), `tool_call_malformation.share`,
      returned read ranges (python-script prints are NOT read events, D3-11), submits with
      `scored_state_basis`/`submit_consistency`/`post_submit_edits`, nudge counting with the any-call reset primary
      + valid-call-reset variant (D3-14), count model cm-2 with β fit, end-reason precedence (event > trace >
      heuristic), and lexical edit-attempt detection.
      Files: `kblib\traces.py` (+ tests).
      Verify: `python -m pytest Gemma\kb\tests -q -m "not slow"` (every obs class; cm-2 arithmetic; D3-10/D3-11/
      D3-14 cases); then `-m slow` for acceptance **facts 1, 2, 4, 6, 8, 15, 17 (submit part), 19, 20**
      (fact 6: `v2_gate_out2` is a stage class with a `~` suffix, never INFRA; fact 19: nudge count = 9).

- [ ] 6. **T6 — Gold** (`kblib\unidiff.py`, `kblib\gitio.py`, `kblib\gold.py`, design §6/§7.2/§8). `unidiff.py`
      (strict in-memory apply, `--- /dev/null` new files, reject `..`/absolute paths); `gitio.py` with the §13.2
      verb allowlist (a test asserts `commit`/`push`/`config`/`stash` cannot be issued), `cat-file --batch`,
      worktree-only EOL flags, object-dir env helper; `gold.py` writes `tasks_gold.json` (schema `tasks_gold/2`)
      for all **129** tasks with `specificity`, `parametrized`, `new_files`, AST `functions_source=ast@base_commit`,
      and the F13 multi-line `assert`/`with pytest.raises` capture.
      Files: `kblib\unidiff.py`, `kblib\gitio.py`, `kblib\gold.py` (+ tests).
      Verify: `python -m pytest Gemma\kb\tests -q -m "not slow"` (unidiff; gitio allowlist = exactly §13.2;
      gold F13); then `-m slow` for acceptance **fact 7** (129 tasks; every rich task has ≥1 hunk with
      `functions_source = ast@base_commit`).

- [ ] 7. **T7 — Static reconstruction** (`kblib\bashpy.py`, `kblib\harness_edit.py`, `kblib\reconstruct.py`,
      design §8). Bash front-end feeding a restricted Python-AST symbolic interpreter (module source contains no
      `exec`/`eval`/`compile(...,"exec")`/`subprocess`/`os.system` — a test greps for this); `harness_edit.py`
      emulates `edit_file` via the on-disk wheel's `apply_replacement` with `sys.modules` stub registration;
      the VFS timeline with scored state + `post_submit_edits`; the four candidate kinds (`as_run`, `final`,
      `counterfactual`, `intent`); repairs R1–R5 with `intent_discarded`; cache keys (§13.6); fidelity incl. the
      `NO_SUBMIT_EMPTY_TREE` cross-check. **Agent-authored commands are never executed.**
      Files: `kblib\bashpy.py`, `kblib\harness_edit.py`, `kblib\reconstruct.py` (+ tests).
      Verify: `python -m pytest Gemma\kb\tests -q -m "not slow"` (bashpy/reconstruct fixtures incl. the no-exec
      source grep; harness_edit strategies + stub registration); then `-m slow` for acceptance
      **facts 3, 16, 17, 20** (fact 16: R1 on v6b rich_4079 step 31 → 359-char OLD occurs once at base).

- [ ] 8. **T8 — Near-miss and classification** (`kblib\nearmiss.py` `nm-3`, `kblib\classify.py` `fc-3`, design
      §9–§10). Exact-line + identifier inverted indexes with the fixed fuzzy order; SAW rules (a)/(b) with
      coordinate mapping and the off-path cross-task control; the revised classes (INFRA narrowed,
      `EDIT_AFTER_SUBMIT`/`REVERTED`/`RECON_MISMATCH`, `SAW_ONLY`, `KERNEL_FAILED`, `~`/`^` suffixes). Writes
      `near_miss.jsonl` and `failure_class`/`failure_subclass` into `runs.jsonl`.
      Files: `kblib\nearmiss.py`, `kblib\classify.py` (+ tests), and the first write of
      `Gemma\kb\near_miss.jsonl` + `Gemma\kb\runs.jsonl`.
      Verify: `python -m pytest Gemma\kb\tests -q -m "not slow"` incl. the brute-force equivalence test; then
      `-m slow` for acceptance **fact 12** (`v2_gate_out`→INFRA/RUN_INVALID SAMPLE_ADAPTER). Run a non-replay
      `build` once (background, timeout ≤ 1,800,000 ms) and **measure non-replay build time vs the ≤300 s bar**
      (§9.4/§19.2); if missed, implement the pre-declared near-miss cache and record the miss in
      `build_verification.md`.

- [ ] 9. **T9 — Replays** (`kblib\replay.py` `rp-3`, design §13). `CloneGuard` (clone's own config,
      `GIT_OPTIONAL_LOCKS=0`, refs/config/index/`count-objects`, post-image provenance), `%TEMP%` worktrees with
      object isolation + LF-forced inside the worktree only, **gold-first + base control run first**,
      required-test matching, both result criteria, the worktree-free cache, replay budget + whole-command
      deadline, ordering, protected reset, manual candidates. Then run
      `build --replay --replay-budget-s 1200 --deadline-s 1500` repeatedly (background, command timeout
      1,800,000 ms) until `replays_pending=0`, then a plain `build`.
      Files: `kblib\replay.py` (+ no-git tests), and `Gemma\kb\replays\replays.jsonl`,
      `replays\clone_state.json`, `replays\gold\<task>.json`, `replays\cache\**`.
      Verify: `python -m pytest Gemma\kb\tests -q -m "not slow"` (replay no-git tests: JUnit matching, gold-first
      validity table, CRLF-insensitive cache key, deadline/`NOT_RUN` accounting, provenance equal/unequal); then
      the §19.3 bars — gold-first VALID for every minimum-set task, `clone_state.json` `identical: true` for both
      clones (identity, not "clean"), no `%TEMP%\gkb_*` left, import-check line points inside its worktree, rich
      clone plain diff stat recorded (never the EOL-override figure).

- [ ] 10. **T10 — Claims and levers** (`kblib\claims.py` `cl-3`, `kblib\levers.py`, design §12). Heading blocks;
       the two correction-stem lexicon regexes with `correction_unit`; date sanity (L8094 `date_suspect`); the
       rule-5 **fact-line** extractor (any line/row yielding a fact binds regardless of lexicon, D3-1); the F1
       **bar/unit/keyed** classifier (D3-2); case-insensitive F5 + the `<v> @ 0.NN` idiom and type-C LB-history
       tables + TOTAL-row per-version F1 + F10 `live_best` with the v6↔v6w contradiction pair (D3-1); auto-checks
       against `curated\submissions.csv` (COMPLETE-only scores; PENDING has none) and the `run_labels.json:baseline`
       pointer (D3-3); claim-id collision suffixes; unit-based supersession/contradictions; the >12-line paragraph
       `chunk k/n` split (D3-12); alias-first tokenization incl. heading-scoped aliases. Writes `log_claims.jsonl`
       and `log_claims.md`. The curated file is still empty here (merged, never written).
       Files: `kblib\claims.py`, `kblib\levers.py` (+ tests), and `Gemma\kb\log_claims.jsonl` +
       `Gemma\kb\log_claims.md`.
       Verify: `python -m pytest Gemma\kb\tests -q -m "not slow"` (claims D3-1/D3-2/D3-3/D3-12 cases); then
       `-m slow` for acceptance **facts 13, 18, 22, 23, 24, 25** (fact 23: fact-line LB claims extract on the live
       log, content-anchored; fact 24: v6↔v6w live-best pair + BASELINE status vs `submissions.csv`; fact 25: F1
       bar/unit/keyed; no manufactured CONTRADICTED from a bar).

- [ ] 11. **T11 — Render and query commands** (`kblib\render.py`, `kblib\verdict.py`, `kblib\leak.py`,
       `kblib\paths_cli.py`, design §7.5/§15/§18.3). `KB_SUMMARY.md` with all §7.5 sections in order, incl. the
       two build-stamp lines, the **BASELINE banner** right after them (D3-1/D3-3: stale-steering wording when
       curated+submissions.csv confirm v6w @ 0.15 while steering says v6 @ 0.12; `BASELINE CONFLICT`/NEEDS-DATA
       when unmapped), the outcome matrix with `S`/`~`/`^`, section 9 **Harness semantics** incl. the row "Does
       the dev harness match the scorer?" (D3-5), and `build_stamp.json`/`build_meta.json`/`build_log.txt`.
       Commands: `card`, `claims` (validated `--text`), `preflight` (slug-suffix rule N26), `report-path`,
       `verdict` (fingerprint-diff N23), `leakcheck` (both scopes).
       Files: `kblib\render.py`, `kblib\verdict.py`, `kblib\leak.py`, `kblib\paths_cli.py` (+ tests), and
       `Gemma\kb\KB_SUMMARY.md`, `build_meta.json`, `build_stamp.json`, `build_log.txt`.
       Verify: `python -m pytest Gemma\kb\tests -q -m "not slow"` (render/verdict/leak/paths_cli); then run two
       builds and the **idempotence check** (`tests\idempotence_check.py` snapshot/compare → IDENTICAL excluding
       the build stamp), the **protected-trees** manifest check (submit_*, log, steering, curated, proposals,
       replays\manual unchanged before/after `build --replay`), and `check-fresh` → 0 right after a build.
       **Re-measure the ≤300 s non-replay build-time bar.**

- [ ] 12. **T12 — Kaggle pulls (read-only)** (`kblib\kaggle.py`, `build_kb.py pull`, design §14). A `/N` slug
       suffix rejected (F9: `kernels output` always returns latest), `--source-version`, a source pull with every
       output pull, `LIKELY-LATER-VERSION` unless the twin matches. `submissions.csv` is already seeded, so a
       scored-history pull is optional (`pull --submissions` refreshes into `pulled\_submissions\`; newest of
       curated/pulled wins). Run `pull --dry-run`, then `pull` for versions with no local output, optionally
       `pull --submissions`, then rebuild. **Never `kernels push`, never submit, never commit** — a unit test
       asserts no other Kaggle verb string exists in the module.
       Files: `kblib\kaggle.py` (+ tests), and `Gemma\kb\pulled\**` (add-only).
       Verify: `python -m pytest Gemma\kb\tests -q -m "not slow"` (F9: `/N`→exit 1 with the L6691 message;
       `--source-version` builds only `kernels pull …/N -m`; the no-other-verb assertion); then `pull --dry-run`
       exits 0 and prints only `kernels output`/`kernels pull -m`/`competitions submissions` argv; a rebuild stays
       green and records pulled slugs/attributions/flags.

- [ ] 13. **T13 — Minimum curation.** Using `card`, `claims`, replays and the raw files, author the minimum rows
       in `Gemma\kb\curated\claims.jsonl` (§12.6), each with paths, step_ids and lines and a status decided from
       the data. Rebuild and confirm they merge (none orphaned) and appear in `log_claims.md` and KB_SUMMARY §8.
       Files: `Gemma\kb\curated\claims.jsonl` (append hand-authored rows; never overwrite existing rows).
       Verify: `python Gemma\kb\build_kb.py build` exits 0; `python Gemma\kb\build_kb.py claims --status curated`
       lists the new rows; grep `log_claims.md` / KB_SUMMARY §8 shows them with no orphan warning in
       `build_log.txt`.

---

# Deliverable 2 — the auditor agent file

- [ ] 14. **T14 — Agent file.** Rewrite `ROOT\.kiro\agents\gemma-auditor.md` per design §17 (keep `name:
       gemma-auditor`, `tools: [read, write, shell]`, frontmatter only engine-known keys). Body: role/context
       (runs inside `gemma-audit`, AUDIT vs REFUTE, never launches workflows, exempt-self "Audit first" note, the
       wrapped-date instruction); absolute `ROOT`/`G`/`KB` block; the KB layout + CLI exactly as built in T1–T13
       (every generated file one-liner, every command + exit codes, the key fields incl.
       `scored_state_basis`/`post_submit_edits`/`near_miss.stages`, matrix letters `S`/`~`/`^`, the query
       recipes); the mandatory read-before-judging order; the §10 failure-class evaluation; the verdict rules
       (PROCEED/REVISE/REJECT/NEEDS-DATA); the exact report format with line-1 `VERDICT:` and the §17.1 AUDIT-JSON
       block using `<task_id>` placeholders; REFUTE mode phases A/B; the hard limits (write only its report +
       optional manual candidates; never edit submit_*/log/steering/curated/proposals; never push/submit/commit;
       `leakcheck` on any proposed config). The D3-3 live-best rule: policy baseline = steering reconciled with
       `curated\run_labels.json:baseline`; steering `v6 @ 0.12` reported **stale**, use `v6w @ 0.15` citing
       `submissions.csv`; baseline-dependent bar on an unscored submission stays NEEDS-DATA. Examples use
       placeholders, never real gold text.
       Files: `ROOT\.kiro\agents\gemma-auditor.md` (rewrite in place).
       Verify (§19.4, static only): frontmatter parses and `tools` contains `read` plus `write`-or-`shell`;
       a scripted check that every `build_kb.py` command named in the file runs `<cmd> -h` exit 0;
       `python Gemma\kb\build_kb.py leakcheck --scope tooling ROOT\.kiro\agents\gemma-auditor.md` exits 0 (clean).

---

# Deliverable 3 — the workflow recipe

- [ ] 15. **T15 — Workflow recipe.** Write `ROOT\.kiro\workflows\gemma-audit.workflow.json` per design §18:
       top-level keys exactly `name, description, inputs, steps` with `inputs == {"proposal_path": "file",
       "slug": "string"}`; the 4 flat sequential steps `rebuild-kb` (wf-coder, effortLevel `low`,
       captureOutput true) → `audit` (gemma-auditor, modelId `claude-opus-5`, artifact `audit_report`) →
       `refute` (gemma-auditor, modelId `gpt-5.6-sol`, artifact `refute_report`) → `final` (wf-coder, effortLevel
       `medium`, artifact `final_report`); prompts P1–P4 copied **verbatim** with backslashes escaped (P1 includes
       `--deadline-s 1500 --lock-wait-s 120`), BLOCK-K expanded into P2/P3, `K`/`B` spelled out; the hyphenated id
       `rebuild-kb` and the artifact keys `audit_report`/`refute_report`/`final_report`; no step-level `input`
       key; no prompt references its own step's artifact; P2 keeps the explicit unwrap instruction next to
       `{{rebuild-kb.output}}`. **Static validation only; do not launch** (§18.6).
       Files: `ROOT\.kiro\workflows\gemma-audit.workflow.json` (create), `Gemma\kb\tests\test_recipe.py`.
       Verify: `python -m pytest Gemma\kb\tests\test_recipe.py -q` passes (JSON parses; keys/inputs exact; step
       ids unique; template-reference rules per §2.16; modelIds ⊆ {claude-opus-5, gpt-5.6-sol, claude-fable-5}
       and steps 2/3 differ in family; P1 has the two flags; agents are `gemma-auditor`/`wf-coder`); then
       `python -c "import json; json.load(open(r'ROOT\.kiro\workflows\gemma-audit.workflow.json', encoding='utf-8'))"`
       succeeds and `python Gemma\kb\build_kb.py leakcheck --scope tooling <recipe>` exits 0.

---

# Final verification and hand-off

- [ ] 16. **T16 — Final verification and hand-off.** Run a fresh `build --replay` to `replays_pending=0` and
       confirm `check-fresh` = 0. Confirm all unit + slow tests green, the idempotence and protected-trees checks
       pass, both clone states identical, and no `%TEMP%\gkb_*` remains. Write
       `Gemma\kb\curated\build_verification.md` with the commands and results for every build-loop item (two
       builds + idempotence compare; coverage of every run dir and log; the matrix holding every rich gate task
       per run; near-miss step_ids; `tasks_gold.json` count = 129; gold-first per replayed task + minimum-set
       status; the Harness-semantics answers with citations incl. the call-count puzzle and the dev-harness-vs-
       scorer row; the final `git status` of both clones read the clone's own way + the rich clone's provenance +
       the offered-but-not-run restore command; the ≤300 s build-time bar result and both near-miss FP bars;
       agent/recipe consistency; the §18.6 launch hand-off with inputs
       `proposal_path = Gemma\kb\proposals\2026-10-11-max-tool-calls-28-to-50.md`,
       `slug = max-tool-calls-28-to-50`). Summarize to the user: what was built, bars met/missed, counts, and what
       is left for the top-level session (the launch, promotion of `proposed_curations`, the forensic as first
       use, the clone-restore decision).
       Files: `Gemma\kb\curated\build_verification.md`.
       Verify: `python -m pytest Gemma\kb\tests -q` (full suite, unit + slow) all green;
       `python Gemma\kb\build_kb.py check-fresh` exits 0; `build_verification.md` records every §19 bar result
       (met or missed, no reframing).

---

## Notes / assumptions

- This plan deliberately mirrors the design's §22 task order because each design task already ends with its tests
  green and leaves the tree buildable; re-decomposing would risk dropping one of the D3-1..D3-14 fixes, which are
  distributed across §5/§6.1/§6.2/§6.3/§7.5/§12/§15/§20.
- The build-review GATE and the convergence loop are provided by the surrounding workflow (`build-loop`); this
  file is the plan that loop consumes. The gate contract (semantic_reviewer writing `Gemma\kb\build-review.json`
  with `verdict: APPROVED`, `onMaxIterations: abort`, `maxIterations <= 5`) is left unchanged.
- Every "fact N" named per step is the design's §19.2 acceptance fact measured on the **real** Gemma data — the
  external judge for that step. Because the data grows during the session, those facts assert "≥" on counts
  (design §0/§2.1), so the live counts observed at planning time (159 traces, 8799 log lines) do not invalidate
  them.
- If a step hits a bar it cannot meet (e.g. the ≤300 s build time), report it as missed in
  `build_verification.md` and apply the pre-declared fallback (the §9.4 near-miss cache), rather than reframing
  the bar.
