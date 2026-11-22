# AI Handoff: Gemma 4 Developer Agent competition

Read this first, then `GEMMA_EXPERIMENT_LOG.md` (the source of truth; newest entries at the bottom; the "standing truth"
block at the top). Repo `c:\Users\biges\Gemma\Gemma_Competition`, Windows + PowerShell, WSL Ubuntu available. GitHub
`GeorgeRCAdamJohnson/Gemma_Competition`, push to `main` (user's convention). Update the log BEFORE every push.

**Don't reconstruct procedures from this history.** Start with the
[Kaggle](docs/KAGGLE_BEST_PRACTICES.md), [Colab](docs/COLAB_BEST_PRACTICES.md),
and [LoRA](docs/LORA_BEST_PRACTICES.md) runbooks and the
[notebook index](README.md#running-experiments-start-here). For ongoing jobs
carry forward the registration/receipt path, exact slug/version or runtime,
last verified progress, budget/cleanup status, and the next authorized action.

## Update 2026-11-22: intel DB, slots validation, swing dossier

- Per-attempt intel DB: `kb/attemptdb/` (see its README). Rebuild `python kb/attemptdb/build.py`, check
  `python kb/attemptdb/verify.py` (27 checks), query `python kb/attemptdb/q.py`. The `.sqlite` is gitignored; rebuild it.
- GPU rules: `.kiro/steering/gpu-usage.md`. 12 slots per L4 lane VALIDATED by `comfyops/e4b-slots-per-lane-8v12-r4` v1
  (x1.295 attempts per lane-hour, solves -1.92 points vs a -2.0 line).
- Findings paper: `Write-up/FINDINGS_E4B_INTEL_DB_20261121.md`. Discovery + swing dossier: log entries of 2026-11-22,
  `Outputs/SWING_DOSSIER.md` (local, Outputs/ is gitignored; scripts `Outputs/_disc_*.py`, `_swing_dossier.py` force-added).
- Next (needs user approval): pre-register the restart-at-call-12 A/B on the 17 swing tasks (12 slots, >= 20 rounds);
  pull missing test outputs; audit gold labels (fastapi_14851 is suspect); build the reusable experiment queue.

## Current handoff: 2026-11-18

### Latest evaluation and scored submission (2026-11-19 UTC)

- Evidence-first fixer prompt: `comfyops/e4b-seed39-evidence-first` v1
  was accepted and queued. Five candidate-only Seed39 rounds, no fresh
  control or competition submission. Only the fixer prompt changed in the
  package. The frozen scheduler passed a 32-task overlap test, eight slots
  on each of four lanes. Live GPU dispatch is still to be confirmed.
  Receipt and frozen registration: `Outputs/kaggle_e4b_seed39_evidence_first`.
  Cap: 12 GPU-hours; 28.40 included GPU-hours at preflight. Compare against
  the ten saved rounds; resume read-only rather than relaunching.
- Repair-decisions Seed39 rounds 1-5 ran as
  `comfyops/e4b-repair-decisions-seed39-rounds-1-to-5` v2. The runtime
  reported 195 attempts, 60 verified solves, 25 overflows and no recorded
  routing violations; `complete=false` because of abnormal/ungraded results.
  The separate rounds 6-10 notebook
  `comfyops/e4b-repair-decisions-seed39-rounds-6-to-10` v1 completed with
  10, 11, 13, 11, and 14 verified solves. Receipts and collected results live under
  `Outputs/kaggle_e4b_repair_decisions_seed39_r1_r5_v2` and
  `Outputs/kaggle_e4b_repair_decisions_seed39_r6_r10`.
- The user authorized a scored competition notebook. Private CPU packager
  `comfyops/gemma-submit-e4b-repair-decisions-v1` v1 completed, and its
  `submission.zip` was verified against the evaluated policy and adapter.
  Competition submission **58547656** was accepted and was `PENDING` on
  2026-11-19 07:10 UTC; zero submissions remained that day. Receipt:
  `Outputs/competition_repair_decisions_v1/submission_receipt.json`. Do not
  resubmit; check the existing reference. Diagnostic scores are not a
  leaderboard prediction.

This section supersedes older status and balance statements below. Keep the
history: the chronological source of truth is
[GEMMA_EXPERIMENT_LOG.md](GEMMA_EXPERIMENT_LOG.md), especially its newest
entries. The worktree contains extensive existing modified and untracked work;
do not reset, clean, overwrite, or edit the user's read-only attachments.

### Goal and standing constraints

Improve E4B repair performance and reliability, with a working target of
15-16 verified resolves per 39-task practice round. Study actual 31B, E4B,
LoRA and non-LoRA traces to guide training; do not assume practice scores
predict the public leaderboard.

- Current public baselines supplied by the user: **31B ca5 0.20**, **E4B
  pack 1 0.06**. The E4B repro-gate experiment is **closed**, not pending.
- Pack 1 had one run on each of 90 runtime tasks and 20 runs on each of 39
  score tasks. The 90 are under-tested, not unmeasured. The historical 73%
  right-file figure excludes failures without a parsed edit and covers only
  mixed-outcome tasks. Check near-miss selection against raw test output.
- Preregister experiments, inputs, win/failure rules and budgets before
  launch; verify actual hardware, quota and costs; preserve artifacts; report
  failures and incomplete coverage. Ask the user **"ready"** before
  triggering fresh Drive consent, and let them approve it in a visible
  notebook or interactive terminal. Do not download models from Hugging Face.
- A local verified solve requires a completed, error-free attempt, nonempty
  real test output, exit 0 and the correct observed route. Gate acceptance or
  a nonempty patch alone is not a solve. Separate ungraded, timeout, overflow,
  missing and routing failures.

### What was learned and completed

- The raw-near-miss pilot returned **0/5 on each of three tasks**; the
  startup-gate A/B returned **10.75 vs 11.25/26** over eight paired rounds.
  Neither result supports promotion. Memory V9 was incomplete: 17/45 memory
  versus 19/48 control graded, with **no same-round graded pairs**; this is
  not a valid paired comparison. One trace showed a promising intermediate
  patch later damaged by repeated edits, motivating tool-state training.
- The p5 tool-state adapter completed 32 training updates. Its completed
  39-task x 16-round paired evaluation recorded **178 p5 vs 189 base verified
  solves in 624 pairs**, net -11; the registered gain criterion was not met.
  There were 80 p5 and 73 base overflow attempts. The frozen p5 curriculum
  contained edits in some input histories but **zero final supervised edit
  targets** in its 2,048 training rows.
- At 32,768 context with a 5,000-token output reserve, 27,768 input tokens
  fit. The error's "at least 27,769" is a lower bound, not an exact prompt
  length; per-turn prompt tokens, not cumulative totals, measure the context.
  Prior 64K and 131K recovery diagnostics had zero verified solves and
  incomplete coverage, so wider context is not an established fix.
- On the same 39 task IDs, an archived 31B ca5 single pass solved **30/39**;
  that and E4B runs differ in configuration and repeat count, so they are not
  a clean model-size A/B. Trace examples suggest learning shared contract
  preservation across parallel paths, maintaining composed behavior, checking
  rendered output and editing the owning definition. In particular,
  `fastapi_5077` and `rich_3718` were 0/32 across p5/base despite patches
  touching the relevant file; finding the file did not ensure a correct fix.
- The first evidence-to-edit engineering seed solved **13/39** in its first
  diagnostic round. Nine additional rounds completed: the ten round totals
  were **13, 12, 9, 11, 12, 10, 12, 10, 12, 13** (mean 11.4/39).
  They were adapter-only diagnostics, not paired against a contemporaneous
  base. The seed submission scored **0.05** publicly; pack 1's 0.06 remains
  ahead. Pack 1 also drew 0.01 on another submission, so one draw does not
  establish a causal regression.
- **Intel database BUILT (2026-11-21):** `kb/attempts.sqlite`, code and
  README in `kb/attemptdb/`. 13,697 unique attempts (incl. 31B archive
  traces) decomposed into 93,011 steps and 67,874 tool calls with full
  observations; per-attempt behaviour features; vLLM server config, load and
  errors joined to attempts by lane and time; 4,472 crawled documents with
  full-text search; experiment-log sections linked to experiments, slugs,
  tasks and submissions; experiment catalog with repeat signatures.
  `verify.py` passes 16/16. Rebuild after pulling results:
  `python kb/attemptdb/build.py; python kb/attemptdb/verify.py`. Use
  `attempts_unique` for rates; `verified IS NULL` means not on disk.
- Drive `ab_runs` is now local (`Outputs/drive_ab_runs`, 10 Colab tags,
  3,432 traces); DB totals 14,739 unique attempts, 7,807 traces, verify 27/27.
  To refresh: `robocopy "G:\My Drive\gemma_fasteval\ab_runs" Outputs\drive_ab_runs /E /MT:32`
  (run outside the Kiro sandbox), then rebuild.
- **Batch 6 resolved:** attempt 1 ran 10 rounds but every L_loc pass hit the
  YAML bug; attempt 4 ran 2 rounds with the fixed skill (L_loc 8, 7 vs pack 1
  9, 6; locate called in 6/24 attempts). Too few rounds for the prereg rule;
  no sign of a gain.
- **Breakthrough scan (2026-11-21, log entry of the same date, scripts
  `Outputs/_bt_*.py`):** lead 1 = incomplete multi-site fixes (multi-hunk
  tasks: some gold hunks covered 20.1% solved vs all 52.5%; 81% of missed
  hunks share an identifier with the agent's own edit); lead 2 = read waste
  causing fixer overflow (17% of failures, ~+5% relative recoverable; read
  limits were only ever prompt rules). The "old_string not found" lead is
  DOWNGRADED to a symptom. **AUDITED the same day (log entry "AUDIT of the
  breakthrough scan"):** lead 1 is mostly between-task (within-task: 5-7
  tasks, thin) and its identifier signal is 83% vs a 58% null; lead 2's loss
  is ~75 solves (+2.9%, upper bound), not 120. Expected effects are +0.2..+0.65
  tasks per 39-task round; 5-round A/Bs cannot detect that. Test mechanisms
  on intermediate outcomes and targeted cohorts first.
- Evidence-first Seed39 (`comfyops/e4b-seed39-evidence-first`) results are on
  disk complete: 54/195 verified, 13, 9, 12, 9, 11 per round (descriptive; no
  sign of a gain over the 11.2-11.8/round earlier Seed39 runs).
- `Outputs/_submissions.json` is stale (last 58263186); refresh needs Kaggle
  credentials, which the Kiro OS sandbox currently blocks, as it blocks git.

### Latest dataset, training and upload

- Built an original development corpus with **24 train and 8 validation
  families** from one authoring lineage. Baseline, positive and same-anchor
  hard negative were replayed twice, totaling 384 behavioral subprocesses;
  32 accepted, zero rejected. Native token/prefix checks passed with a maximum
  of 526 tokens. It is **not** the independent full corpus or full
  serving-parity dataset; `training_ready=false`, `serving_parity=false`,
  and there are no sealed decisions. The full-corpus and promotion gates are
  in [LORA_EVIDENCE_TO_EDIT_SPEC.md](LORA_EVIDENCE_TO_EDIT_SPEC.md).
- The user authorized and ran a preregistered **three-update engineering
  pilot**, not the proposed 64-update substantive run. It used the E4B QAT
  base, rank 8/alpha 4, q42/v24, BF16 and accumulation 4. All four numerical
  and export gates passed; 3 checkpoints and a 132-tensor adapter were
  saved. Outcome is `development_pilot_trained_requires_serving_probe`.
  Development validation NLL changed **0.27265343 -> 0.27124039** on eight
  families; this is not evidence of repair improvement.
- Colab receipt elapsed 851.05 seconds, estimated job cost 0.459 CU at
  1.94 CU/hour. The wider displayed balance fell 2.10 CU, not an itemized
  bill. The runtime was terminated with user approval; last observed state
  was zero active sessions and 0.00 CU/hour. Pip reported unrelated dependency
  conflicts, documented in the experiment log; do not describe the whole
  environment as clean.
- The visible notebook
  [colab_repair_decisions_v1_visible.ipynb](train/colab_repair_decisions_v1_visible.ipynb)
  reuses the underlying notebook builder and Colab environment-staging helper
  but was built separately, not by the standard template command. Corpus
  registration and inputs are under
  [repair-decisions-v1](train/data/repair-decisions-v1/); keep the
  [replay-audit ZIP](train/data/repair-decisions-v1/replay-audit-v1.zip)
  separate from training inputs because it contains oracles and wrong edits.
  The Drive run is
  `G:\My Drive\gemma_fasteval\lora_runs\e4b-repair-decisions-v1-colab-pilot`.
- The user authorized **private upload only**. Dataset
  [comfyops/e4b-repair-decisions-v1-pilot](https://www.kaggle.com/datasets/comfyops/e4b-repair-decisions-v1-pilot)
  was verified private, version 1, ready, dataset ID 13475589. It contains
  only the mapped adapter and config; downloaded copies matched:
  - adapter SHA256 `9f6b42913234eb5b9ff27a9c686bb68348c29403ca0ba9c761c8d6538827cc85`
  - config SHA256 `a0d3ea9560655956305345562eeb7985a49f3622eff8e3539bf665343baa53cf`
  Serving compatibility and repair improvement are not yet established.

### Next requested experiment: not yet built or launched

The user approved **five rounds over the same 39 Seed39 tasks**: 195 attempts,
the new repair-decisions adapter on the fixer and the base model on the
verifier. The proposed private, Internet-off notebook uses four L4s and a
maximum 10,800-second wall time, equivalent to **12 device-hours**. This is
a ceiling, not a predicted charge. The latest prior quota snapshot was about
31.85 GPU-hours, but it is stale; recheck included quota and active jobs, and
avoid paid scale-up. No five-round package or preregistration was completed,
no such GPU job was launched, and no new competition submission was made.
The assistant's latest responses said it could not upload notebook code to
Kaggle; a subagent was not launched to do so.

For whoever continues this work:

1. Inspect [tool_lora_runner.py](kaggle_pkg/tool_lora_runner.py),
   [_build_seed39_repeats.py](kaggle_pkg/_build_seed39_repeats.py),
   [run_experiment.py](kaggle_pkg/run_experiment.py), the
   [previous registration](kaggle_pkg/push_e4b_evidence_seed39_r2_r10/registration.json),
   and [focused tests](colab_fasteval/tests/test_tool_lora_kaggle.py).
   The existing evidence-seed runner allows one or nine rounds, with the
   latter labeled 2-10. Support five rounds labeled 1-5 without changing
   prior modes; test 195 unique task/round attempts and partial summaries.
2. Freeze the exact cohort, policy, mounted inputs, adapter hashes, settings,
   unique output directory and title-derived private slug. Preregister
   before launch. The previous diagnostic used 32K context, four TP1 L4 lanes
   and eight slots per lane; the competition scorer's four L4s use TP4, so
   this is not exact scorer parity.
3. Before dispatch require verified GPUs, pinned hashes, advertised context,
   repeatable nonzero adapter effect, native tool-call parser checks on all
   four lanes and compiled role routing. Audit observed routing in traces.
   Verify quota durations with `.total_seconds()`; account for other jobs.
   A successful push followed by a slug-related 403 requires read-only
   verification of the actual private version, not a blind repush.
4. Collect raw outputs and report actual per-round solves, all failures and
   partial coverage. Compare historical Seed39 descriptively, not as a
   contemporaneous paired A/B. Do not submit to the competition without
   separate authorization.

### Evidence and operational entry points

- Paired p5 report and traces:
  [result report](Outputs/kaggle_tool_lora_p5_repeat39/result_report.json),
  [raw progress](Outputs/kaggle_tool_lora_p5_repeat39/results/lora_progress.json).
- Seed39:
  [round 1](Outputs/kaggle_e4b_evidence_seed39/result_report.json),
  [rounds 2-10](Outputs/kaggle_e4b_evidence_seed39_r2_r10/result_report.json).
- 31B comparison:
  [raw archive](Outputs/ca5_31b_presubmit_85/results.tar.gz),
  [pass summary](Outputs/ca5_31b_presubmit_85/presubmit_ab.json).
- [Kaggle runbook](docs/KAGGLE_BEST_PRACTICES.md),
  [Colab runbook](docs/COLAB_BEST_PRACTICES.md),
  [LoRA runbook](docs/LORA_BEST_PRACTICES.md), and
  [template preparation](notebooks/prepare.py) capture the working setup and
  recovery lessons. Use them rather than rediscovering procedures.
- The previous chat checkpoints are in
  `C:\Users\biges\.copilot\session-state\b7d91ba8-5635-49cf-8008-7c44a69a2525\checkpoints`;
  checkpoints 030-034 contain the recent evaluation, trace, dataset and
  pilot details. These session files supplement, but do not replace, the
  persistent repository log and saved result artifacts.

## Earlier handoff history (status as of 2026-11-13)

## User working rules (do not break)
- Ask the user "ready" BEFORE triggering any Drive consent link. Links live ~2 min; the user walks away otherwise.
- Never download models from Hugging Face. Use Kaggle's `google/gemma-4/.../gemma-4-e4b-it-qat-w4a16-ct/2` (a byte-identical
  copy is on Drive).
- Kaggle credentials stored as Colab Secrets are NOT readable headlessly (tested). The local token is
  `C:\Users\biges\.kaggle\access_token`; uploading it to a VM was proposed, never approved. Do not do it without an OK.
- "Our only gauge is the public score." Only run tasks that could plausibly land (no full 129-task sweeps for A/Bs).
- Pre-register every A/B (arms + hashes, tasks, win rule) in the log before launching. Report misses as misses.
- The user is expert and direct; give numbers, admit wrong hypotheses plainly (several were wrong this session).

## 1. Latest state
**Finals (unchanged):**
- 31B: ca5 = 0.20 (ref 57760641).
- E4B: pack 1, kernel `gemma-submit-e4b-retry-fresh`, bundle `84f904c63afd` = 0.06.
- ACTION FOR USER: select BOTH explicitly on the Kaggle Submissions page; auto-select may choose two 31B rows (0.20 + 0.17).

**Closed this session:** 31B B+C (`gemma-submit-ca5-bc-time10-cmd60`): draws 0.15 / 0.17 / 0.13 (ref 58263186), mean 0.15,
below the 0.18 switch rule.

**Repro-first / repro-gate E4B (`comfyops/e4b-repro-ab`) is CLOSED, not pending.** `colab_fasteval/Chat_History` (file saved
11-12) records the build session BEFORE results. Result (log ~L18176-18237): F fresh retry 11.50 vs control 9.82 (t 3.18) ->
F became pack 1; R repro gate 8.88 (32% context overflow, 2x time). Gold check: only 18% of E4B repro tests are
gold-consistent and 57% of base-reproducing tests also fail on gold -> "Do NOT re-run it on E4B" (31B tester only, gold
check first). Treat chat logs as history; the experiment log is the source of truth.

**E4B levers already closed (pooled A/Bs, all within ±1 task/pass of pack 1):** H_hygiene, R_reads, T5 (temp 0.5, worse),
L_lean, HG4, HT5, HR, HR4, V_vote (+0.5 but +57% time). LoRA is "closed unless new mechanism" in the standing truth.

**Batch 6 (`locate` skill as second opinion) has NO result after 4 VMs:**
| attempt | Drive tag | what happened |
|---|---|---|
| 1 | `e4b_ab6_locate_20261112` | L_loc broken: SKILL.md YAML (inline JSON in description). C: 8/12, 10/12 |
| 2 | `e4b_ab6b_locate_20261113` | fixed skill (L_loc sha `a60585682580`); VM reclaimed during L_loc r1. C r1 8/12 |
| 3 | (e4bloc4) | VM reclaimed during prep |
| 4 | `e4b_ab6c_locate_20261113` | C r1 finished ~01:31; VM reclaimed ~02:00 |
Unread: `ab_runs/e4b_ab6c_locate_20261113/progress.json` may contain an L_loc entry (proves whether the skill loads).
Offline prediction (`Outputs/_locate_rules_sim.py`): batch 6 null or negative; every locate rule loses files on anchor tasks.

**Offline findings this session (all CPU, scripts in `Outputs/`):**
- `_pass_conditions.py`: 14-15/26 passes are NOT GPU speed, warm-up, cache or cold start; consistent with independent sampling.
- `_seed_check.py`: a shared vLLM seed does not correlate passes (concurrency 8 breaks reproducibility).
- `_locate_ceiling.py`: 73.2% of failures WITH a parsed first edit, on mixed-outcome tasks, first edit the gold file.
  Failures without a parsed edit and all-or-nothing task groups are excluded; do not generalize this to all failures.
- `_statement_accuracy.py` / `_statement_contract.py`: 71% of statements name neither gold file nor symbol; 61% contain none
  of the hidden test's strings; E4B solves 30% when the gold file is named vs ~6% otherwise; PR-style 17% vs issue 2%.
- `_multifile_solves.py`: only fastapi_14077 of 38 multi-file tasks ever solved (87%, usually 1-file patches).
- Pack 1 has **one run on each of 90 runtime tasks** and **20 runs on each of 39 score tasks**. The runtime set is
  under-tested, not unmeasured.
- `_near_miss.py` / `_near_miss_detail.py` nominate candidates but their inference must be checked against raw test output.
  A raw-output audit narrowed the runtime pilot to rich_3052, rich_3675, and rich_4075; see the pre-registration at the
  bottom of `GEMMA_EXPERIMENT_LOG.md`. Do not reuse the original 21-task set without rechecking.
- Pack 1's `fixer.md` says "~28 tool calls and 8 minutes" while the actual limits are 80 calls / 30 min, but no runs were
  budget-bound; treat a text change as a behavior experiment, not an assumed fix.

**Pre-registered E4B experiment COMPLETED:** `rich_3052`, `rich_3675`, `rich_4075` each resolved 0/5; the local
diagnostic missed. One `rich_4075` run exceeded the context window. Results and durations are in the newest log entry
and Drive `gemma_fasteval/ab_runs/e4b_pack1_rawnear_20261113`; no leaderboard inference.

**Post-run diagnosis:** All 15 saved patches and evaluation outputs were inspected. `rich_3052` reached the prompt file
but missed the case-insensitive return/validation contract; `rich_3675` missed TTY autodetection semantics in four runs
and broke imports in one; `rich_4075` missed the print fix in all five, with traces focused on the Python 3.8 clause.
The gate accepted the broken-import patch and also accepted unrelated existing tests; details and parser caveat are in
the newest log entry. The user-supplied results archive is in `results/`.

**Recommended next experiments (in order):**
1. A local startup-error gate fix is ready at `colab_fasteval/arms_gate_fix/G_startup` (SHA-1 `05af53c15525`);
   original `C_pack1` remains `84f904c63afd`. Five local regression tests passed; the inherited three-attempt policy
   can still submit a rejected patch. An eight-round, 416-execution comparison is pre-registered in the latest log entry,
   completed eight paired rounds: control 11.25/26 versus treatment 10.75/26, paired t -0.52; the positive rule
   was not met. All 416 task rows are recorded in Drive progress, including 42 context-window errors. The local
   monitor stopped logging before completion and the runtime termination cause is unknown. See the latest log entry.
   Round-four trace follow-up found one G-side win with a gate-rejected first attempt that retried into the expected
   source file (`fastapi_14492`); the other five G-only wins were correctly targeted before the gate. The `rich_4077`
   control trace shows a wrong-file edit accepted by its existing tests; it is the only matched C trace reviewed.
   Control traces for the other five G-only wins remain unavailable, so their causes are not established. The
   aggregate A/B remains negative.
2. Use short periodic API requests if investigating Colab reliability; a long stalled CLI exec is not a keep-alive.

## 2. Colab: how it works here
**Accounts/balance:** Colab Pro+, 329.72 CU after the A/B run; 0.00 CU/h, no active assignments or sessions.
L4 ≈ 1.94 CU/h (G4 ≈ 10, CPU 0.08). Never use G4.

**Two control paths:**
- API wrapper (Windows): `python colab_fasteval/colab_mcp.py exec "runtimes/<id>" <file.py>` runs a file in a FRESH kernel.
  Get the exact runtime name (ends in `........`) with `python colab_fasteval/_runtimes.py`. Auth = ADC with colaboratory
  scope, quota project `htmlhub-dev-20260703174246`. Each exec stream is cut server-side after ~4-5 min -> keep calls short.
- Official CLI in WSL via `~/colabw` (= `colab --auth=adc`), currently PINNED to 0.7.5 (`colab_fasteval/wsl_pin_cli.sh`).
  `wsl -d Ubuntu -- bash -c "~/colabw new -s NAME --gpu L4"`, `upload -s`, `exec -s -f`, `status -s`, `sessions`, `usage`,
  `stop -s`. On 0.7.5 `exec --timeout` is a HARD cap (0.8.0: idle seconds). `colab sessions` can falsely report "gone".
- WSL commands with nested quotes/`$` are rejected by the tool parser: put logic in a script file and run it.

**Drive mount (needs the user):** The pilot succeeded with `colab drivemount -s <session>` in the VS Code integrated
terminal: the user opened the displayed link, approved access, and pressed Enter at the prompt. Earlier automatic
attempts did not produce a verified mount. Verify with `_probe_mount.py` via the API ("drive mounted: True").

**Bring-up sequence (A/B batch):**
1. `new` L4 -> upload `colab_fasteval/_abL_inputs.tar` -> `/content/ab_inputs.tar`, the launch json -> `/content/launch.json`,
   `_gpu_prep_ab.py` -> `/content/gpu_prep_ab.py`, `_launch_if_ready.py` -> `/content/launch_if_ready.py`.
2. Drive mount (ask "ready" first).
3. Prep via API: `_prep_guarded.py` (refuses without Drive). Restores the env tar (19.2 GB), copies the model and snapshots,
   installs `python3.12-venv` (REQUIRED). ~7-8 min. Ends with "PREP DONE" + "IMPORTS" in `/content/prep.log`.
4. Launch: `_launch_if_ready.py` (detached driver `gpu_ab_run.py`; config from `/content/launch.json`).
5. Status: `_ab6_check.py`, `_ab6_intel.py` (per-trace locate/first-edit stats), `_ab_status.py`, `_intel.py`.
Results go to Drive `gemma_fasteval/ab_runs/<tag>/<arm>/round_N` + `progress.json` after EVERY pass, so VM loss costs at
most one pass. The driver writes `ALL_DONE`, stops vLLM and exits.
Chained scripts exist: `_ab_chain.sh` (whole bring-up), `_ab_attach.sh` (keep-alive re-attach), `_keepalive_auto.py`
(keeps the VM, launches the driver after prep, stops by rule). They did NOT keep VMs alive (see below).

**THE OPEN PROBLEM: VMs get reclaimed.** 5 of the last 5 VMs died 20-40 min after my last client request:
- A long CLI exec (keep-alive) stalls silently or drops after 6-40 min on both 0.8.0 and 0.7.5; a VM outlives a drop by
  ~20 min, then dies. Kernel activity alone does not keep it.
- VMs that survived for hours (e4bab 11-10, e4bvote 11-11; see `colab_fasteval/_cli_history.py`) had NO long CLI exec;
  they were API-driven with regular polling.
- Current hypothesis (unproven, 3rd one): Colab needs periodic client REQUESTS. Planned fix, not built: a local poller doing
  a short API exec every ~4 min for the whole run, plus VM-side auto-launch after prep. Alternative: attach the Colab web UI
  (`colab url -s <name>`) and have the user keep the tab open.
- Always end idle VMs: `~/colabw stop -s <name>`; check `~/colabw usage` (Usage rate should be 0.00 when nothing runs).

## 3. Kaggle submissions
- Limit: 1 submission/day, resets 00:00 UTC. Deadline Dec 2; team merge deadline Nov 25. Finals = 2 selections.
- Kaggle GPU quota: under 2 h left this week -> no Kaggle A/B batches.
- Submit a kernel: `python kaggle_pkg/_submit_debug.py <kernel> "<message>"`; at reset with polling/landed-check:
  `python kaggle_pkg/_submit_at_reset.py`.
- After a score lands: `python kaggle_pkg/_refresh_submissions.py` (merges into `Outputs/_submissions.json`), then
  `python Write-up/_rebuild_score_svg.py` and `python Write-up/_check_score_record.py` (all checks must pass).
  `Outputs/` is gitignored: `git add -f` scripts and `_submissions.json`.
- Kaggle model variations (no HF): `python kaggle_pkg/_list_g4_variations.py`. Unquantized E4B for any LoRA:
  `gemma-4-e4b-it-qat-q4_0-unquantized` v2 (15.91 GB).
- Kaggle A/B builder (if quota returns): `kaggle_pkg/_build_e4b_batch3_kaggle.py <hours> <batch>`.

## 4. Key files
- `colab_fasteval/arms/C_pack1` = pack 1 (LoopAgent fixer -> verifier, 80 calls / 30 min, skill `submit-gate`).
- `colab_fasteval/arms6/` = batch 6 arms (build: `_build_arms6.py`; check skills: `_skill_yaml_check.py`).
- `colab_fasteval/skill_locate/` = locate v3 (offline: top1 41%, top5 74%).
- `colab_fasteval/ab_tasks_swing.json` = 12 batch-6 tasks; 26-task landable set from `_ab_tasks.py`.
- `Outputs/ab_logs/` = 2,487 Colab run logs; Drive `ab_runs` holds 2,389 full ATIF traces (1,076 solved).
- `Outputs/e4b_variance3/tasks.jsonl` = 129 tasks with gold `patch` + `test_patch`.

## In-progress E4B context-history A/B (pre-registered 2026-11-14)
- Tests pack 1's `include_contents: none` against an otherwise identical `include_contents: default` fixer, on the 26-task landable set for five paired rounds. Arm hashes, task manifest, paired-win rule, retry-specific measure, 20-CU cap, and unique Drive tag are registered in the newest `GEMMA_EXPERIMENT_LOG.md` entry.
- Pre-registration live check: Pro Plus, 329.72 CU, 0.00 CU/h, no active runtimes/assignments; L4 was eligible. Historical L4 rate was ~1.94 CU/h, not a guaranteed quote. The cumulative stop balance remains 309.72 CU.
- **Recovered round 1:** Drive `progress.json` contains both arms, each `rc=0`, 10/26 resolved: `H_default` in 1,022 seconds and `N_none` in 1,024 seconds. Seven tasks resolved in both arms, three only in H_default, three only in N_none, and 13 in neither. Both arms had context-window errors on `fastapi_14873` and `fastapi_11194`; N_none also had one on `rich_2725`.
- **Current resume (2026-11-14):** the user completed the VS Code terminal commands and Drive is mounted in active L4 assignment `e4b-ctx-history-r3-20261114` (host `gpu-l4-s-ass1a1-1e2h1fcw9ld0z`). The registered bundle was re-uploaded with the same SHA-256; cached model and 129 snapshots were verified. Prep completed in 470 seconds with matching arm fingerprints, task hash, imports, and L4 details.
- Seeded the saved Drive progress into the new runtime's `/content/ab/progress.json` without overwriting the Drive copy. The launch guard started PID 8118 with the registered five rounds, concurrency 8, tag, and eight-hour deadline. vLLM became ready after 4.8 minutes and round 1 `N_none` started. It was still running at the last successful progress check; completion after that is unverified.
- **Status:** only round 1 of 5 is present. The registered positive-signal rule (H_default wins at least 4/5 rounds and gains at least 5 total resolves) is not met; no experiment conclusion or leaderboard prediction is justified. The inspected r3 runtime has since disappeared: 0 active assignments and 0.00 CU/h. Latest balance is 325.11 CU, leaving 15.39 CU before the registered 309.72-CU stop balance. Do not resume without fresh user authorization; ask for readiness again before any new Drive consent.

## Parallel replication staged (2026-11-14)
- The user subsequently launched `e4b-ctx-history-r4-20261114-1429` through the visible WSL launcher and completed Drive consent. Driver PID 28112 was reported launched; synced tag `e4b_context_history_20261114_r4_1429` records H_default round 1 at 11/26 in 1,172 seconds, exit code 0, one context-window error. No paired conclusion yet; the older partial cohort remains separate.
- Latest live usage: 324.00 CU, 1.94 CU/hour, ONE active assignment. This confirms allocation/billing, not task progress.
- User approved trying ONE additional L4 for an independent five-round replication. Pre-registered in the newest experiment-log entry: session `e4b-ctx-history-parallel-20261114`, tag `e4b_context_history_20261114_parallel`, same verified input tar, arms/tasks, five paired rounds, concurrency 8, utilization 0.85, eight-hour driver deadline. Analyze separately; leave the active run untouched.
- Second runtime NOT launched at staging. Ask "ready" before new Drive consent. The WSL template now accepts environment overrides for SESSION_NAME and RUN_TAG so a second visible terminal can launch the replication without editing/restarting the first.
- The cumulative 309.72-CU stop balance still applies to BOTH runtimes; no budget reset. Two L4s would be about 3.88 CU/hour at the observed rate, allocation permitting. CU enforcement remains manual; the driver deadline is checked between passes.
- **Later live check (~15:21 Pacific):** user allocated the parallel L4 and completed visible Drive consent, but the next CLI exec lost connection before output-tag preflight/prep. A subsequent read-only mount probe succeeded on that same runtime; no repeat consent needed while it survives. Latest usage: 323.65 CU, 1.94 CU/hour, ONE active assignment. Parallel session is IDLE; original r4 returns "not found". Parallel execution was NOT verified; disappearance cause is unknown. Only r4 H_default round 1 is locally synced, no replication progress. Recovery choice pending: preserve existing outputs and use the surviving runtime, not another allocation.
- **Recovery supersedes staging:** user selected recovering r4, not launching the replication. CLI websocket errors persisted; Windows `colab_mcp.py` API execution worked on `runtimes/6dbe41e7_4f0f_487a_b706_1de6a3d2aa38........`. Validated saved r4 checkpoint against raw results and task IDs, left Drive artifacts untouched, seeded local progress, and switched the surviving parallel-named session to r4's output tag. Prep passed arm/task hashes and import checks; driver PID 21883 launched, skipping H_default round 1. Original driver cutoff remains 2026-11-15 06:43:35 UTC; latest log says vLLM booting, with no resumed task pass yet verified.
- **Monitoring is NOT continuous:** recovery prep polling ended after launch. A visible VS Code monitoring-task launch was cancelled; no ongoing watchdog or automatic budget guard was established. Latest confirmed balance 323.17 CU, one L4 at 1.94 CU/hour. Shared 309.72-CU floor remains manual. Do not confuse the surviving session name (`e4b-ctx-history-parallel-20261114`) with its current experiment tag (`e4b_context_history_20261114_r4_1429`).
- **~15:40 Pacific API check:** driver PID 21883 exists; log confirms vLLM ready and round 1 N_none started at elapsed 4.9 minutes. CLI IDLE/old mount-probe timestamp does not reflect this detached driver. No resumed pass completion verified yet; monitoring remains on-demand.

## After computer crash / Kaggle fallback (2026-11-14)
- User requested all commands in a file, completion check, and four-GPU Kaggle execution if incomplete. Commands are now in `colab_fasteval/RUN_COMMANDS.md`, including WSL recovery, Colab launch/status/stop/Drive checkpoints, and Kaggle build/push/status/logs/output.
- Colab survived the crash. Drive and live API confirm r4 round 1 H_default 11/26 (1,172s), round 1 N_none 9/26 (1,177s), round 2 N_none 12/26 (951s), all rc=0 and n=26. Live driver log says round 2 H_default started. Only 3/10 passes are saved; do not claim five rounds finished. Original r4 artifacts/run left untouched.
- Latest Colab usage during staging: 321.71 CU, 1.94 CU/hour, one L4. No continuous monitor; original 309.72-CU floor still manual.
- A separate five-pair Kaggle replication was pre-registered before push in the newest experiment-log section. Builder `kaggle_pkg/_build_context_history_kaggle.py` reuses exact registered bundle/tasks/arms and existing competition image/wheelhouse/server setup. Four L4s required at execution; one server/GPU, conc 8/GPU. GPU0 rounds 1 and 5, GPUs 1-3 rounds 2-4, each pair's arms sequential on the same GPU. No cross-platform score pooling.
- Built notebook cells compile; mocked tests verify exact five-pair schedule/checkpoints and explicit incomplete-pass failure. One CLI push succeeded: `comfyops/e4b-context-history-20261114`, version 1, 7,200-second notebook limit, 90-minute eval limit. Immediate status QUEUED, logs empty; actual four-GPU allocation/quota remains unverified. Kaggle CLI is installed/authenticated; browser is not logged in. No leaderboard submission was made. Do not push another version while queued/running.

## Memory/variance pressure test (2026-11-14; later evidence supersedes staging)
- Kaggle final saved checkpoint confirms all ten passes: H 50/130, N 58/130; neither meets the preregistered directional rule. Raw output download remains partial.
- CPU audit checked 416 gate outcomes, 416 trace paths and 401 patches. The 36 repeated nonempty task/patch groups (163 rows, 22 tasks) have no conflicting resolved labels. This does not validate gate feedback or workspace isolation.
- Strong memory-related case: `G_startup/round_8/fastapi_14492` made the correct tutorial edit, had it undone because an existing test expects the old identifier, then wandered into LICENSE/CITATION. Saved-attempt restoration recovered the correct edit and task tests passed. This is external saved-state rescue, not proven compaction loss.
- Gate rollback/restoration affects Python non-test source only. The final round-8 patch retains unrelated non-source edits as well as the restored correct edit; do not assume retries reset the entire workspace.
- Keep pattern memory, retry-state retention, misleading gate feedback, and final task-test flakiness separate. No new GPU experiment or gate fix was launched during this audit. See newest experiment-log section for exact evidence and limitations.
- Subsequent online research is documented in the newest experiment-log section with primary sources: SWE-Exp, REM (solve-rate gain p=0.22, not significant), The Complexity Trap, Reflexion's incorrect-test analysis, context-engineering guidance, and batch-dependent inference nondeterminism. Evidence supports testing short structured pattern/task-state memory, not raw trace dumping; no new run is registered or launched.

## Task-memory implementation (2026-11-14; CPU build, no new GPU launch)
- User authorized building skills/LoRA, then emphasized time. Start with the smallest within-task memory treatment; do not start an expensive training sweep.
- Canonical skill: `colab_fasteval/skill_task_memory/`; non-overwriting builder: `_build_memory_arm.py`. Generated isolated control/treatment live under `colab_fasteval/arms_memory_v1/`. Control bytes match `arms_context_ab/N_none`; baseline files were not edited.
- Memory checkpoints full non-harness tracked/intent-to-add diffs before the existing gate rolls source back, records gate observations and post-gate workspace fingerprints, and requires first-tool recall on each fixer invocation. It does NOT repair/re-rank gate decisions or change the three-attempt policy. Recall is bounded, notes explicitly unverified, patch hashes checked; state lives in per-task Git metadata.
- ADK 1.36.1 wheel inspection confirms `include_contents: none` retains current-turn tool responses. Actual generated model payload/recall compliance remains untested. Official harness compilation is also pending; local CLI Python has no `google.adk`/`adk_submission`.
- Focused Windows and WSL tests cover retention after rollback, source-only best-attempt restoration, corrupted/stale state refusal, bounded recall, copied-skill execution and baseline preservation. See newest log for final counts. Existing gate ResourceWarnings were observed, not changed.
- `train/memory_lora_smoke.py`: CPU preflight by default; opt-in rank-8, max-three-step synthetic compatibility smoke, default 600-second worker cutoff. Local bases only; rejects the compressed serving checkpoint. Known Drive cache path contains only the W4A16 E4B artifact; an authorized unquantized QAT twin is NOT verified available.
- This is NOT a real training dataset, long-term pattern bank, trained adapter or measured score improvement. Next: verify the official compiler and real recall payload, obtain/verify training twin provenance, pre-register a tiny timed smoke with runtime/cost check. Ask "ready" before visible Drive consent. Do not run the old context-history launcher as though it launches memory.

## Kaggle memory launch (2026-11-14; supersedes CPU-only staging)
- User explicitly requested Kaggle execution. One private version was pushed to `comfyops/e4b-task-memory-20261114`; immediate status QUEUED, logs empty. No allocation, remote compilation, smoke or scores verified yet. Do not repush while queued/running.
- Pre-registration is in the newest experiment-log section, including exact arm/bundle/notebook/task hashes and outcome rules. The old context-history notebook is COMPLETE and untouched.
- Canonical skill was tightened to <=4,000-character recall and <=3,000-character paged patch reads to fit the 5,000-character harness output cap. Newly frozen `colab_fasteval/arms_memory_kaggle_v1` differs from the original CPU arm; its manifest is bundled by `kaggle_pkg/_build_memory_kaggle.py`.
- Run: four paired rounds on the same 26 familiar development tasks, one pair/L4, alternating arm order. 104 main outcomes/arm. One separate reduced-budget memory smoke must show initial/retry recall calls and responses before full evaluation. No LoRA, pattern bank or leaderboard submission.
- Notebook cap 3,600s, main eval deadline 2,700s, single 480s boot attempt. Requested four L4s must be confirmed by logs. Remaining Kaggle GPU quota/accounting was not verified from CLI.
- Monitor with `kaggle kernels status comfyops/e4b-task-memory-20261114` and `kaggle kernels logs comfyops/e4b-task-memory-20261114`. Outputs: `memory_progress.json`, `memory_summary.json`, and raw `memory_results/` in notebook output. A failed/incomplete smoke aborts the main experiment and preserves stderr/traces.

## Kaggle memory v1 failure diagnosed; revision 2 staged, not pushed
- v1 ended ERROR after 615s wall time. Both arms compiled and all four L4 servers were healthy. Smoke completed (160s, rc=0, 0/1 resolved) but failed strict recall compliance; NO main paired rounds ran.
- Full source/outputs are downloaded under `Outputs/e4b_task_memory_kaggle_20261114_v1_source` and `Outputs/e4b_task_memory_kaggle_20261114_v1`. Extracted skill/arm hashes match frozen v1 exactly.
- Actual trace: first fixer used run_command to run a nonexistent repository scripts/memory.py; second started get_status and skipped recall; third correctly used run_skill_script and successfully recalled TWO saved candidates. Audit: 3 invocations, 1 first recall, 1 payload. This is policy compliance failure, not broken packaging or a ledger failure. Do not loosen the audit or infer score degradation.
- Revision 2 builder moves the explicit tool-call protocol to the start, forbids shell execution of the skill resource, removes conflicting budget-first wording and fixes the retry rule. Generated `colab_fasteval/arms_memory_kaggle_v2` preserves control bytes; v1 untouched. Actual model compliance remains untested.
- Runner diagnostics now print invocation/recall counts and precise failure reasons. Windows 9 tests pass + 1 POSIX skip; WSL 10 pass; real trace audit reproduced and downloaded file hashes verified.
- No new Kaggle push/allocation occurred after the failure. Obtain approval before another GPU run; freeze/register the revised notebook first. Existing Kaggle builder still targets v1, so it must NOT simply be repushed as the corrected run.

## Corrected Kaggle version 2 approved and submitted (latest)
- User explicitly approved "Launch corrected Kaggle run" after being told it allocates four L4s again. Fresh v2 hashes, unchanged design/criteria and caps were registered BEFORE push in the newest experiment-log section.
- `kaggle_pkg/_build_memory_kaggle.py` now targets `arms_memory_kaggle_v2` and a new `push_memory_v2` directory; v1 files/results are untouched. Notebook SHA `334c4a0769ddd017e8a710d2a0e7ce96ace352b64af7ea319946c5e40d9e0d68`; bundle SHA `b51ab39769eaab52da83a3d23ab1b6e2269b6123ec4db8e0abb2e55c034f7486`.
- Exactly one push succeeded as version 2 at the same Kaggle URL. Immediate status QUEUED, logs empty; v2 GPU allocation, compiler pass, smoke compliance and scores remain unverified. Do not repush/retry while queued/running.
- Strict first-tool recall/response checks are unchanged. Same separate smoke and four main pairs, same task/model/budgets, 60-minute notebook cap. No LoRA or Colab allocation. Download future outputs to a separate `_v2` folder, not the preserved `_v1` directory.

## Public LoRA investigation (2026-11-14; research only)
- Inspected Ayush Barai's pinned submission v9 (`366835192`) and upstream `lora-step-2` trainer. Latest/pinned submission source hashes match. The 32-second run packages an existing adapter; public trainer logs show about four hours of optimization plus setup, on four L4s.
- Actual training used BF16, NOT NF4: logs say 4-bit OFF, context reduced to 8,192, 52 examples (49 Gemma / 3 Qwen), only 6,790 unique supervised edit-call tokens. Rank/alpha 16/16, q/o/down on layers 30-59, 90 modules; 217 example presentations and 54 updates. Native completion IDs and action-span masking are the useful lessons, not a demonstrated memory mechanism.
- Public 0.22 is not an isolated adapter gain: the author's stated prior range already includes 0.22. Compare its 31B model to our 31B 0.20, not E4B 0.06. Small held-out loss and nonzero adapter tensors do not establish agent-score benefit.
- Important correction to earlier blocker framing: the upstream verification kit includes an E4B packed-checkpoint -> differentiable BF16 text-stack loader, preserving tied embeddings and all 42 layer-scalar buffers. A separate unquantized twin may therefore be unnecessary. Our current NF4 smoke does not implement this alternate path; it was not run here.
- Author receipts report a one-L4 E4B pilot: 37 updates in 35.59 minutes, 19.02 GiB peak allocated / 21.76 GiB reserved. Our cached small config agrees on 42 layers, tied embeddings and one quantization group; exact checkpoint hash, numerical fidelity, dependencies and serving export remain unverified locally. Do not equate compatible-looking config with identical weights.
- That kit's E4B results are weak: exposed 40-task panel base 5, higher-LR adapter 7, lower-LR 4; higher LR has 3 paired wins / 1 loss, nominal p=0.625. Exact training histories/tokenized files are missing. Reuse engineering gates, not claims of proven gains.
- Next candidate: retain external candidate-state memory; teach correct native recall actions and evidence-based retry behavior with a small, issue-disjoint LoRA pilot. First verify base fidelity, gradients and served adapter effect; do not copy the 31B layer range onto E4B or change the running memory A/B.
- Sources and limitations are in the newest experiment-log entry. Public code/data were downloaded and inspected, not executed. No training, model download, new runtime or Drive consent; memory v2 status has not been refreshed during this investigation.

## Memory v2 failure recovered; v3 candidate staged, NOT launched (latest)
- The requested `kaggle kernels pull` succeeded, as did output download. Current remote status is ERROR. Source/output are preserved separately in `Outputs/e4b_task_memory_kaggle_20261114_v2_source` and `Outputs/e4b_task_memory_kaggle_20261114_v2`; v1 untouched. Downloaded arm bytes exactly match frozen v2.
- Four L4s allocated; both arms compiled; registered bundle matched; all four servers healthy. Smoke completed rc=0 in 165 seconds; no main paired rounds ran.
- Crucial distinction: `fastapi_14492` resolved true, with the intended one-line tutorial edit and two official tests passing. All THREE fixer invocations called recall FIRST. The third response was blocked by the artificial 12-call smoke budget: 3 invocations / 3 first recalls / 2 payloads. Strict audit correctly failed; this is not evidence that the revised invocation prompt failed.
- Trace shows the correct first edit undone by the existing-test gate, followed by successful recall of saved candidate metadata and reapplication of the correct edit. This supports further testing of candidate-state memory, NOT a causal memory gain or leaderboard prediction.
- Fixed only smoke task limits: now the same 80 calls / 30 minutes / 200 turns as main, still concurrency 1 and a HARD 240-second smoke process cap. No weaker recall audit; main design, prompts, gate and arm bundle unchanged.
- Frozen `kaggle_pkg/push_memory_v3` candidate: notebook SHA `73e3824674195286ed5c353833027c5d0c010936d2732041e45cd406c2ec6b07`, bundle SHA unchanged `b51ab39769eaab52da83a3d23ab1b6e2269b6123ec4db8e0abb2e55c034f7486`. Registration now includes smoke/task limits. No push or allocation authorized/performed for v3.

## Memory version 3 approved and submitted (latest)
- User explicitly instructed "rUN IT" at 2026-11-14 21:33 PST. Verified frozen v3 hashes/limits and prior run ERROR, then recorded approval before ONE successful push as Kaggle version 3.
- Immediate status QUEUED, logs empty. Four L4s requested, not yet observed; compilation, smoke and A/B results unverified. Same strict audit, 240-second smoke process cap, 45-minute main deadline and 60-minute notebook cap. No automatic retry.
- Download into separate `Outputs/e4b_task_memory_kaggle_20261114_v3` and `_v3_source` folders. Preserve v1/v2 and all registrations.

## Parallel CPU finding: recall can omit the actual edit
- Actual v2 trace (same arm bytes used in v3) confirms a 393-character correct patch becomes a 67-character header-only preview: no old/new identifier or hunk. Gate excerpt also drops the failing test name. `excerpt` divides the over-budget prefix allowance by six, even for ASCII; diff headers consume the remaining prefix.
- Full patch is still accessible via `show`, but successful recall delivery alone does not establish that the useful edit was shown. Next proposed refinement is change-first, evidence-preserving cards tested under the same 4,000-character limit, before another GPU allocation.
- Research/replay only: no code or current-run change. Keep reporting v3's actual paired results; this representation finding is not evidence that a refined arm would win.

## CPU change-first cards implemented (not launched)
- Frozen `colab_fasteval/arms_memory_cpu_cards_v1`; canonical renderer now retains changed lines instead of diff/index prefixes, summarizes named test/assertion evidence, and clips by real JSON-escaped size. Full saved patches and `show` paging are unchanged; previews are not apply-ready.
- Checksum-matched actual v2 candidate replay: old/new identifier, hunk and failing test absent from legacy default recall, present in the new card. Reconstructed recall: 1,049 JSON characters, under the same 4,000 cap. This proves retention, not model benefit.
- Windows targeted tests: 10 pass + 1 POSIX skip. WSL: 11 pass, including real rollback/best restoration. Renderer/test Pylance syntax checks passed; existing gate ResourceWarnings untouched.
- Verified NO prompt/work loss: frozen v3 arm hashes still match registration; new CPU pair changes ONLY two `memory.py` copies and skill documentation relative to that memory arm. Prompt, gate script, agent graph, sampling and control remain byte-identical. No GPU push.
- Latest source pull succeeded into `Outputs/e4b_task_memory_kaggle_20261114_v3_source`; status COMPLETE. Final outputs downloading separately into `_v3`; wait for actual summary before recording final scores.

## Memory v3 final receipts verified (latest)
- COMPLETE; downloaded notebook cell sources exactly match registered v3. Full trace download continues; small final summary/progress already retrieved separately and independently reconciled against all eight complete 26-task passes.
- Control 47/104 (45.2%); memory 40/104 (38.5%). Round control/memory: 13/10, 11/9, 10/10, 13/11. Memory wins 0/4: three losses and one tie. No promotion; pre-registered score criterion failed.
- Memory delivery audit: 104/104 task-runs, 158/158 first recalls and structured responses. Matched task-runs: memory-only 8, control-only 15, both 32, neither 49; repeated familiar tasks, not independent hidden performance.
- Main error maps: 8 control / 11 memory context overflows, all 27,769 input + 5,000 requested output against 32,768 context, retried five times. Preserve these as actual failures; no other recorded error types. Trace-level interpretation pending full artifacts.
- CPU change-first card variant remains unlaunched. No further GPU push or LoRA training. Its improved information retention does not establish a performance gain or erase v3's negative result.
- Full v3 download is now complete and verified: 208 main traces/results, all 104 memory audits independently reproduced. Actual memory use: 54 nonempty recalls / 158 total, zero `show`, zero `note`; no agent requested a full saved patch through the memory API. Final scores unchanged.

## Deep audit supersedes the earlier shallow memory interpretation
- Full findings in newest experiment-log section; CPU scripts/derived trajectories in session files. No GPU launch or code/prompt change during the audit.
- Baseline ALREADY saves/restores best source candidate diffs. The arm adds model-visible metadata, not new protected persistence; no cross-task memory or trained transfer exists. All 104 initial recalls empty, only 35 runs reach retry memory.
- Verified official ADK/compiler source: only skill name/description injected until load_skill. ZERO runtime load_skill calls; show/note instructions were in the unread body, not the fixer prefix. Zero show calls is therefore not evidence of a deliberate informed choice.
- Of 64 nonempty candidate appearances, only 1 exposes an edited line/hunk; 0 gate excerpts retain a test node. New cards fix this channel only; CPU test confirms empty first-recall response remains identical.
- Six of eight memory-only wins occur before nonempty recall. Both retry-exposed wins are fastapi_14492; one benefits from baseline auto-restoration, the other includes a forbidden test edit persisting into gate validation. Neither cleanly identifies a memory-information gain.
- Memory final-gate ACCEPTED: 39/79 solve, 40 fail grading; 29 failures finish after one fixer invocation with gate acceptance. Concrete fastapi_9425: None vs type(None), unrelated multipart test passes, actual 204 test fails. Card-only changes cannot directly fix first-pass false acceptance.
- rich_2943: model "repairs" discarded candidate's syntax error in an already rolled-back clean baseline. rich_3882: invents Console.supports_markup, retries don't learn markup=True, tie-break restores first bad candidate. Need explicit feedback/code-version binding and contract grounding, not just storage.
- Error-free-pair sensitivity: memory 38 vs control 45 on 86 pairs; full -7 remains. Identical nonempty patches: 19 repeated groups / 69 runs / 15 tasks, zero mixed final labels. This sample does not support random final grading as the main explanation.
- Memory recorded prompt tokens +9%; first-request paired median +1,081 tokens. Policy/prompt/tool overhead differs even with empty recall, so current A/B does not isolate information from protocol effects. Do not infer token cost caused the losses.
- Next proposed experiment requires visible retrieval affordances, correct applied/discarded feedback binding and an identical-protocol sham-memory control; gate/context fixes must be symmetric and re-baselined. CPU cards remain unlaunched and not established beneficial. Do not train LoRA merely to repeat an already compliant recall call.

## Corrected v4 approved, tested and PRE-REGISTERED (not yet pushed)
- User requested fixing issues and resubmitting. One four-L4 private Kaggle notebook run authorized; no Colab/Drive consent or leaderboard submission.
- Frozen final arms: `colab_fasteval/arms_memory_kaggle_v4`; package: `kaggle_pkg/push_memory_v4`. Earlier v4 preflight snapshots preserved separately. ALL old frozen bundles/results untouched.
- Both arms now have identical visible show/note instructions, focused contract-check workflow, code-version binding, shared protected-test/all-production rollback gate, explicit operational failures and global three-candidate cap. Only saved evidence is withheld in control (two EVIDENCE_ENABLED constants). Both arms audited.
- Sampling include_thoughts=false removes accumulated reasoning with pinned compiler support; same thinking/output budgets and sampling otherwise. This is mitigation, not a guarantee of zero context errors. No hard magic-print reproduction gate.
- Validation: 17/17 Windows +17/17 WSL, real Linux pytest comparison/rollback/acceptance integration, pinned reasoning-strip helper checks and syntax validation pass. Missing local pytest restored only in a session-specific dependency directory.
- Registered notebook SHA `457d8b3d42af68d22d84771b727ec2015e0a2e14db18604c2c35948ad014150a`; bundle SHA `b5733cafde088a88876bff6ac675db60b8abe5760c15fbeb2768ac7585c66200`. Complete maps/criteria in registration.json and newest log entry, written BEFORE push.
- Same familiar 26 tasks x4 pairs, concurrency8/GPU, one 240-second memory smoke, 45-minute main deadline, actual push --timeout3600. Score signal >=3 round wins and >=4 extra solves; delivery >=99 tasks EACH arm, zero nonempty control recalls.
- Existing remote v3 COMPLETE; next action is hash/invariant verification then ONE `kaggle kernels push -p kaggle_pkg\push_memory_v4 --timeout 3600 --accelerator NvidiaL4`. No auto retry; pull/status new v4 and record actual launch receipt.

## Corrected v4 SUBMITTED and remote source verified (latest)
- Exactly one push succeeded as Kaggle version 4 with --timeout3600 and NvidiaL4, after verifying v3 COMPLETE. Remote status RUNNING at 2026-11-14 23:57 PST. Do NOT push again.
- Actual uploaded notebook cell sources all match pre-registration; source/metadata are in `Outputs/e4b_task_memory_kaggle_20261114_v4_source`.
- Requested four L4s; actual device guard/compile/server/smoke results not yet observed because version-specific log retrieval returns no log files. Keep this distinction; no scores yet.
- Quota read-only receipt: 5.18h GPU used, 54.82h remaining of60h (account-wide, not measured v4 cost). Platform run cap 3,600 seconds.
- Final validation:17/17 Windows +17/17 WSL, real Linux pytest path and isolated pinned context-strip helpers pass. Temporary pytest dependencies cleaned; no shared environment change.
- Continue with status and actual v4 artifacts; preserve all failures and compare NEW identical-protocol evidence/control arms, not old baseline as if unchanged.

## V4 FAILED at smoke timeout (latest; 2026-11-15)
- Remote ERROR, available artifacts fully downloaded into the separate v4 directory; both downloaded arms exactly match frozen v4. Source pull also succeeded.
- Four L4s confirmed, both arms compiled, registered bundle matched, all four servers healthy. Smoke started at492s and hit its240s process cap, rc124/n0. NO main rounds or task grade.
- Partial task log shows successful FIRST recall at7.6/7.9s, then scope drift: CITATION.cff/README edits and translated-doc reads rather than the requested documentation-example identifier. No logged focused check, gate or submission before timeout.
- Zero recall counts in progress mean no completed structured trace, NOT proven skipped recall. Do not report a scored smoke0/1 or a main-memory loss.
- Local gate regressions passed, but the GPU smoke never reached the new gate. Cause of policy drift not isolated; do not claim include_thoughts=false caused it or that new checks used the budget.
- Notebook wall time ~12.5min; four-device equivalent ~0.83 L4 device-hours, not billing. No automatic re-push. Preserve cap/audit; next design should separate short wiring conformance from open-ended real-task solving and improve missing-trace diagnostics before another registration/approval.

## V5 PRE-REGISTERED after "Fix and submit" (not yet pushed)
- One v5 push authorized. V4 ERROR confirmed; account quota5.54h used/54.46h remaining. No Drive consent, increased cap or automatic re-push.
- Package `kaggle_pkg/push_memory_v5`; MAIN arms remain byte-identical frozen `colab_fasteval/arms_memory_kaggle_v4`. No main prompt/gate/sampling/cohort changes.
- Separate short synthetic wiring fixture borrows only fastapi_14492's snapshot identity, replaces question/reference/test patch and uses its own workspace. One LICENSE-line marker; independent whole-file oracle. This is wiring conformance, not a real benchmark smoke or main-policy localization test.
- Main starts only after ordered native recall/edit/check/note/ACCEPTED gate/submit, complete trace and successful fixture grading. Round0 excluded from all main totals. Missing traces/scores now explicitly unavailable/None, not zero; strict main audits retained.
- Validation21/21 Windows +21/21 WSL; actual scripts and oracle negative/positive cases pass. Pylance/generated syntax checks and embedded-payload hashes pass. V1-v4 packages preserved; wiring arm differs only in fixer prompt.
- Notebook SHA `8dc7f05a2e12ce8092efae4870d76a52d5c07c056c0524dd8e9394f67aa2d90a`; bundle SHA `a25a93f2d60b094669ae7d41114438b0bee6d7d175d4296295fa1681ad5cf26b`. Full maps/criteria in registration.json and newest experiment-log entry, written BEFORE push.
- Same240s smoke/2700s main/3600s platform caps, four paired rounds x26 familiar tasks; original score/delivery criteria unchanged. No leaderboard prediction.
- Official grader protects entire pyproject.toml and runner configs despite local gate allowing some metadata edits; do not assume these survive grading. Separate limitation, not changed in v5. LICENSE fixture is permitted.
- Next: single authorized push, NEW `_20261115_v5_source`/`_20261115_v5` output directories, remote source/status verification. Actual GPU allocation/wiring/main results still pending.

## V7 ran: smoke fixed, main TIMED OUT; V8 lean protocol PRE-REGISTERED (user chose B)
- V7 cleared WIRING_SMOKE_OK and the memory NOTE channel was finally active in main (18-33 saves/pass vs zero before). Audit fix held.
- All first-wave main passes hit the 1800s cap at 15-21/26 tasks -> run aborted. The incomplete results do not establish task throughput, the cause of the stalls, an arm speed difference, or feasibility of the full schedule.
- Partial, truncated, confounded signal (NOT a verdict): shared-task memory 6/19 vs control 9/19; observed shows=0 and control nonempty recalls=0. These incomplete subsets cannot establish which arm is faster or better.
- User chose B: keep full 104/arm, remove the per-task focused pytest check from BOTH arms in an attempt to improve speed. V8 also timed out on every first-wave pass, so a throughput recovery is not established. The verifier gate still runs a regression check. protocol_revision6, experiment_revision8; eval deadline 2700->2850.
- New frozen arms `colab_fasteval/arms_memory_kaggle_v8` differ from v6 ONLY in fixer.md; arms differ only by EVIDENCE_ENABLED. Package `kaggle_pkg/push_memory_v8`.
- Validation23/23 Windows +23/23 WSL; embedded payload/hashes verified; lean prompt + dispatch/audit fixes + deadline2850 embedded; v1-v7 preserved.
- Notebook SHA `b0a0fc3cb869eae17271c1000d1daa597c07dcffce64dd0ed6e54e61cb28457d`; bundle SHA `376f84322f5ac284600d0763ea65302ad8196daf3e0e80360eebb3f355e943d1`. Memory map `1923cd081bd4f3717097acc29276d5177cb0838497e3331c68a2a8ce0399ca6a`; control map `e577088a1c12570cf97e3aa5d5971087ff7dbc10195e51fda56fc306916a26db`.
- V8 synthetic smoke passed, but all four first-wave main passes timed out at 1800s with unequal partial subsets; the partial scores are not a paired comparison. No LoRA, leaderboard prediction, or Drive consent.

## V6 ERROR (audit missed saved note); V7 PRE-REGISTERED (audit fix, resubmit)
- V6 proved the dispatch fix works: the real smoke trace shows recall/edit/check/note(saved marker)/gate/submit and fixture solved=1 in83s. The note call again omitted `"action":"note"` but `memory.py` SAVED it this time.
- Remaining failure was in `audit_wiring`: it required `action=="note"` in the call ARGS, so it ignored a genuinely-saved note when action was omitted -> missing=[note], notebook ERROR.
- Fix (runner only): detect the note stage by the saved-note stdout marker (`TASK_MEMORY: saved unverified agent note`), which only the note branch prints; a guard test ensures a non-saving call (recall JSON) still counts as missing. Main `audit_trace` note/show counters now also recognize inferred calls.
- Verified on the REAL v6 trace: audit_wiring now valid=true, observed=[edit,check,note,gate,submit], ordered, submit_calls=1.
- ONLY the runner/notebook changed. Main arms unchanged: v7 embedded bundle SHA byte-identical to v6 (`9fd2f74d318f...`) and arm maps equal v6. protocol_revision5, experiment_revision7. Reuses frozen `arms_memory_kaggle_v6`; package `kaggle_pkg/push_memory_v7`.
- Validation23/23 Windows +23/23 WSL incl. the action-omitted note audit test; embedded payload/hashes verified; v1-v6 preserved.
- Notebook SHA `5e92a83c3f7f3088bb05e7aa3dd772722cb3a1db8c0cc0723cb6295a69bf6fe7`; bundle SHA `9fd2f74d318f39f535c34d901536163d5453f17fc8d0b596123f103233bba345`.
- Approval "Fix and submit"; one push authorized. Same240s/2700s/3600s caps and criteria. No LoRA/leaderboard/Drive consent/auto re-push. GPU allocation, live gate, WIRING_SMOKE_OK and main outcomes pending remote receipts.

## V5 ERRORED on a real note-dispatch bug; V6 PRE-REGISTERED (fix, resubmit)
- V5 reached GPU: four healthy L4s, fixture graded solved=1 in79s, but notebook ERRORED before any main round. The strong smoke audit correctly failed it: the fixer's note call omitted `"action":"note"`, so `memory.py` (default `--action recall`) silently recalled and saved nothing; audit saw missing=[note].
- The omitted-action behavior is reproduced for V5, but its role in the V3 zero-note/zero-show observations is unproven: the audited V3 traces contained no note/show calls. Do not attribute those V3 observations to this bug.
- Fix: `memory.py` infers the action when `--action` is omitted (note if `--note`, show if `--candidate`, else recall); explicit `--action` still wins. Only new behavior: a note/show call can no longer fall back to recall. This is a protocol change -> protocol_revision5, experiment_revision6.
- New frozen arms `colab_fasteval/arms_memory_kaggle_v6` differ from frozen v4 ONLY in the two `memory.py` copies; N_none vs M_memory still differ only by `EVIDENCE_ENABLED`. Separate synthetic wiring fixture, prompts, gate, sampling, cohort, caps and criteria unchanged from v5.
- Validation22/22 Windows +22/22 WSL incl. a new note-without-action regression; embedded payload/hashes verified; embedded memory.py carries the fix; v1-v5 packages preserved.
- Package `kaggle_pkg/push_memory_v6`. Notebook SHA `b44c371374bafd83da483c60b1aba8d2ac7e20200b51dbaa1805bb472287b38f`; bundle SHA `9fd2f74d318f39f535c34d901536163d5453f17fc8d0b596123f103233bba345`. Memory map `adee79dc72f7cdfb15e72ea20ef1e490a5e1b45d01329587bca8b167cccedc13`; control map `7b6667fbca3634b39394f8e08a2355e35bc20c6afe009cdfbf06026eb6eadee9`.
- Approval "Fix and submit"; one push authorized. Same240s/2700s/3600s caps and criteria. No LoRA/leaderboard/Drive consent/auto re-push. GPU allocation, live gate, WIRING_SMOKE_OK and main outcomes pending remote receipts.

## V9 finished: partial resolves, no completed paired comparison
- Latest21:30PST Kaggle status **COMPLETE**, but experiment summary `complete=false`. Saved grades: **M_memory17/45 (37.8%) versus N_none19/48 (39.6%)**. These unequal incomplete cohorts do not show improvement or support a causal/leaderboard claim. Per rounds: M1=8/23,N2=12/24,M3=9/22,N4=7/24.
- All104 opposite-arm task-runs never started: zero same-round task pairs have both arms graded. Global deadline stopped7M/4N tasks; zero per-task timeouts and zero process errors. Arm-level scheduling barrier prevented crossover, so registered paired success criteria cannot be evaluated.
- Saved summary/progress/log are in `Outputs/e4b_task_memory_kaggle_20261115_v9_review`. Graded-run recall audits:45/45 memory valid,47/48 control valid. Earlier launch/live observations below are historical.
- **Raw forensic completed for all93 graded traces/grade rows**, with detailed case studies and selected actual test logs. Census and intermediate-span receipt saved alongside raw outputs. Report's new "V9 raw-trace forensic" section contains sources and limitations; the11globally stopped tasks have no saved traces.
- M57recalls/11nonempty across9runs/61verified note saves/0show; N62recalls/0nonempty/75note saves/2show requests rejected as withheld. Notes work now. Candidate exposure remains sparse; only one of9exposedM runs resolves, a post-rejection-selected cohort, not evidence of harm. Invalid N4fastapi14077 audit comes from BudgetExceeded, not broken dispatch.
- **New preservation evidence:** M3fastapi14463 net successful changes through step11 exactly match passing N4 changed spans; later stale edit loops damage imports and task collection fails. This is changed-span equality, NOT independently regraded intermediate workspace. Gate-only snapshots never capture that state because the fixer never reaches the gate.
- M1rich3454 recalls rollback evidence, reapplies correct source, then survives35failed edits and resolves83tests without native submit. Rich3882and3518 show true failure evidence delivered but wrong edit boundaries persist. Rich4077repeats priorfile_proxy-versusconsole mechanism. All3memory-only solve issues have0nonempty recall; do not attribute their wins to retrieved candidates.
- Next supported target is protected working-state plus verified already-applied awareness and exact evidence use, not another generic recall ritual. Full detail and reproducibility helper hash in experiment log. No new run or policy implementation from this analysis.
- User selected a 2000s **per-task wall** limit: stop only that evaluator and its descendants; other tasks continue. This is separate from the existing 30-minute agent budget and includes evaluator setup and grading, so do not claim it exactly reproduces the competition's timeout semantics.
- `kaggle_pkg/memory_isolated_runner.py` runs one evaluator process per task, up to 8 per GPU. It freezes and kills the specific process tree, including sandbox commands that created new sessions; each task's outputs and progress are retained. Completed persisted grades remain available; absent grades are ungraded, not failed. Global-cap and not-started statuses are distinct.
- The existing 2850s overall evaluation cap remains a separate constraint; 2000s per task does NOT guarantee all 208 tasks finish. The 3600s notebook cap requires a platform launch limit; the notebook alone does not enforce it. Four-L4 allocation, quota, process-per-task memory pressure, and real throughput are not verified for V9.
- `kaggle_pkg/push_memory_v9` reuses V8's exact arm and input hashes. Registered 4 paired rounds, same 26 tasks and success criteria. Notebook SHA `5d7901137beb40e10c61900a780b4788b194be400948b0dcea064ea45863e54b`; bundle SHA `376f84322f5ac284600d0763ea65302ad8196daf3e0e80360eebb3f355e943d1`.
- Linux/WSL tests exercise an actual detached child and verify a simultaneous task continues, plus persisted-grade and deadline handling. The real Kaggle evaluator, server load and timeout cleanup remain untested. Latest remote notebook status checked read-only: ERROR from the prior run.
- User authorized "launch it" on 2026-11-15 20:11 PST. Exactly one push accepted as version 9 with `--timeout 3600 --accelerator NvidiaL4`; latest read-only status **RUNNING**. All six remote cell source texts match preregistration; receipt in `Outputs/e4b_task_memory_kaggle_20261115_v9_source`. Current quota was not independently refreshed. User's20:56PST log confirms four L4s, healthy servers and synthetic wiring success. At notebook2401.5s it records64 main evaluations graded (M31/N33), not solve counts; no result/trace errors in those64. No second arm or timeout yet shown. Do NOT push again while queued/running.
- First task2000s expiry is around notebook2528.3s, not notebook2000s: main started528.3s. Global evaluation expiry is around3378.3s. Each GPU waits for all26 first-arm tasks before its second arm, so task isolation does not remove this arm barrier or guarantee208-task coverage. Main scores and recall audits must come from saved results, not TASK_END completion messages. Full receipt/counts are appended to the experiment log.

## Parallel LoRA pilot: interrupted during staging, no active Colab allocation
- User requested parallel LoRA work and answered "ready" for one L4, two-hour monitor limit and 271.09-CU stop balance. Visible terminal completed Drive consent and started PID 1779 in `e4b-memory-lora-20261115-p1`.
- `train/packed_memory_lora.py` reconstructs the BF16 text stack from the exact cached packed E4B source; no new model download. Rank8/alpha4 q/v, LR1e-5, 20 updates on 24 original recall/show scenarios (20 train/four wording holdouts). This is protocol/gradient/export engineering, NOT substantive repair training or a solve-rate result.
- Preparation restored the environment and was copying weights. The original monitor then hit a transient WSL usage/DNS failure and safely stopped the runtime. No checkpoint hash success, model load, gradients, updates or adapter export was observed. Latest independent usage: **276.82 CU, 0.00/hr, zero assignments**; displayed decrease 0.27 CU. Old runtime entity no longer exists.
- Added three-attempt read-only monitoring retries with failed partial output excluded, deadline checks, and persistent-failure shutdown. Five focused WSL tests and Bash syntax pass. No automatic restart. Use a newly registered tag for a newly authorized run; do not overwrite `e4b_memory_lora_20261115_p1`.
- Revised trainer SHA `7dfa477e02a1ad1756eb4cf16841f85892768a7011297d01da95b628d73234ea`; revised launcher SHA `0ced0a707f1c96650997c3f964ff8bf80bfe0596090c54ea3339635a2b04f494`. Initial hashes, recipe, caveats and interruption receipts are in the experiment log. The repository-wide `train/` ignore applies to these new local files; they are not automatically tracked.

## Paper Track research: evidence delivery, not headline gains
- Six-source review added to the corrected section of `MEMORY_RESEARCH_PRESSURE_TEST.md`, above the archived unreliable draft. It links context admission/symbol representations and independently guarded diagnostics to our actual grep, wrong-edit-target and lost-candidate cases.
- Largest graph/LoRA headline is not substantiated by its attached reproduction: the patch tool returns success without applying or testing a patch. Do not copy its claimed 46% result into our forecasts.
- The graph audit concerns swegemma0.2.7; current extracted helpers already resolve fallback names and normalize edge types. Tool/graph version must be checked, not assumed.
- Cached external LoRA corpus: 14 issues/14 other repos, but zero native edit steps within4096 cached context tokens, two within8192. Actual E4B serialization, evidence-preserving representation, provenance, leakage filtering and outcome verification are still prerequisites for a meaningful repair-data lane. Do not treat the synthetic controller pilot as that lane.

## Tool-use LoRA spec and one-command Kaggle workflow (2026-11-17)
- User requested a concrete LoRA specification and fewer approval prompts through
  consolidated scripts; explicitly selected **private notebook experiments only**,
  not leaderboard submissions.
- `LORA_TOOL_USE_SPEC.md` specifies 480 original tool-state decision examples
  (320/80/80 by scenario family), native E4B serialization, role-correct
  actions, stale-edit/rollback/error counterfactuals, assistant-only loss,
  rank8/alpha4 q/v training, compatibility/serving gates, sealed behavior tests
  and a separately registered interleaved adapter-on/off repair evaluation.
  These are proposed gates/recipes, not measured training results.
- `python -m kaggle_pkg.run_experiment launch --package <new-frozen-package>
  --output <unused-run-folder> --expected-version <N> --accelerator NvidiaL4`
  validates/snapshots a registered private notebook, appends preregistration
  before a single push, requests its registered platform cap, pins source/status/
  paginated output collection to the actual version, and appends actual results
  to the log. It never submits to the leaderboard or retries a push.
- `check --package kaggle_pkg\push_memory_v9` is offline only.
  `resume --output <run-folder>` never pushes. A lost push response requires
  explicit `--recover-version <N>` and remote source/privacy verification.
  Do not relaunch V9 or overwrite its frozen artifacts.
- All16 focused launcher tests passed, covering ambiguous push, receipt preservation, resource/version/
  privacy/hash guards, paging/path checks, partial grades, failure evidence,
  monitoring deadlines and read-only resume. Live read-only V9 source/status/
  first-page API smoke passed: exact cell source match, COMPLETE, 100 files on
  page one with more pages. This did not launch a new notebook.
- No new dataset, trainer extension, fresh Colab launcher, GPU run or adapter
  was produced by this specification task. Original p1 remains interrupted;
  no new Colab balance/assignment claim. Ask **ready** before any new Drive
  consent, use a visible terminal, and preregister/authorize a fresh job tag.

## V10 completed and CPU LoRA implemented (2026-11-17; latest)
- User is handling today's leaderboard submission personally. They authorized
  private E4B tests, but explicitly left Colab **CPU-only/pending**. Do not
  allocate Colab or trigger Drive consent based on the old p1 authorization.
- Exactly one new private Kaggle push: version10 of
  `comfyops/e4b-task-memory-20261114`. No leaderboard submission by the assistant.
  V10 uses unchanged V9 policy bytes on eight development-selected tasks,
  both arms/two rounds:32 runs. All eight jobs/GPU started together, removing
  the arm barrier; actual allocation four NVIDIA L4s.
- Saved results: **M6/16, N6/16**, all16 pairs graded. Round1 M2/N4; round2
  M4/N2. No outer task/global timeouts, missing starts or process errors.
  Registered exploratory score rule missed; recall-delivery bar passed.
  This selected diagnostic is not held-out generalization or a leaderboard forecast.
- Outputs in `Outputs/e4b_task_memory_kaggle_20261117_v10_run`;191 downloaded
  JSON/JSONL/log/patch artifacts. All32 raw grades/audits independently verified.
  Actual main started notebook573.8s; ended2431.4s. Kernel completed; no rerun.
- Trace census: M140 edits/110 failed/10 stale reissues of successful calls;
  81 repeated failed-argument calls and10 failed reissues of previously
  successful arguments. N236 edits/200 failed/151 repeated failed arguments/
  6 failed reissues of successes. These raw event totals have different edit
  denominators; do not infer a treatment efficiency gain. M made21 recalls,
  5 nonempty across4 runs, zero show; N22 recalls/no nonempty/show.
  A fixer in M1rich4077 calls unavailable submit_patch, receives a ValueError
  and does not resolve.
  Grade errors include7M/6N context overflows and1M/2N native30-minute timeouts;
  outer scheduling success does not mean clean agent behavior.
- `train/tool_state_data.py` and the extended packed trainer implement the CPU
  engineering path. Twelve original executable source families, eight states
  each:96 examples split64/16/16. Native core edit engine and real Git/task-memory
  used; workspace/gate envelopes are constructed and explicitly labeled.
- First CPU attempt retained with8 over-cap rows. Corrected p4 isolates its
  historical-error ledger rather than truncating evidence. All96 exact template
  prefixes/masks now pass <=2048 tokens (max1851), using an explicitly recorded
  local legacy-tokenizer metadata override. Serving equivalence is NOT proven.
- Data/manifest/oracle/tokenization receipts:
  `train/data/e4b_tool_state_pilot` (also retained in Outputs for raw-run
  traceability). Dataset SHA256
  `e7cdf73a3a2d05ebc14c3a8fdc66a651ceba52ee8cead54da2a23f309e4db223`,
  schema SHA256
  `33c2f5ea377992d7f01740c7d7684461dc341d45071afc64947a94855bdf9d5f`.
  This is96 engineering examples, NOT the specified480-family-expanded
  capability corpus. Manifest remains `training_ready=false`.
- Trainer adds dataset/schema/manifest validation, per-row native tools,
  max-length/accumulation arguments, assistant-token-normalized loss and a
  three-update engineering override. Default original p1 dataset remains intact.
  Native call IDs/responses validated. Ten focused trainer tests pass, including
  a CPU autograd test for assistant-token-weighted accumulation. Twenty-eight
  focused combined tests and all8 WSL process/schedule tests pass. No
  packed-base GPU load, LoRA gradients,
  optimizer updates, exported adapter or new Colab consent has occurred.
- Local trainer diagnostics still reflect pre-existing absent compressed-tensors
  and older Transformers lacking Gemma4 classes. New data generator/build
  diagnostics clear; do not claim a clean full GPU environment/type-check.
- The existing broad `train/` ignore remains for bulk artifacts. Narrow
  exceptions allowlist only this trainer, generator, requirements, focused
  tests and this dataset. No Git
  staging/commit/push or automatic fresh Colab launcher was made.

# 2026-11-18 update: p5 full129 Kaggle diagnostic launched

- User selected **G_startup with the adapter on fixer only**; verifier, prompts,
  tools, sampling and gate remain unchanged. The only baseline policy-file
  difference is the fixer YAML adapter declaration.
- p5 is uploaded to private dataset `comfyops/e4b-tool-state-lora-p5`
  (13430618), processing ready. Server privacy and downloaded config/weight
  hashes verified. Mapped adapter SHA256:
  `9aa8cbb60795b137f061c4f887f50b2f1118c975d9ef41b1e083c209379b4a92`.
- Private notebook `comfyops/e4b-tool-lora-p5-129` **v2 COMPLETE**;
  exact remote source and private visibility verified. Frozen package:
  `kaggle_pkg/push_tool_lora_p5_v2`; active receipt:
  `Outputs/kaggle_tool_lora_p5_129_v2/receipt.json`.
- Reuses LoRA discovery/registry from the historical load probe, pinned working
  E4B image/wheelhouse, four independent tp1 serving lanes, and the existing
  per-task isolated evaluator. Requires exactly four L4s; eight tasks/lane;
  2,000s outer task wall; 12,000s eval cap; 14,400s platform cap.
  GPU quota before launch:47.96399 hours remaining, no reserved time.
- Saved native parser and repeatable base/adapter logprob-effect gates
  **passed on all four lanes**. Priority receipts are downloaded under
  `Outputs/kaggle_tool_lora_p5_129_v2/priority`. All129 tasks have records;
  adapter routing is observed on129 tasks, with no recorded routing violations.
  The pulled notebook's cell sources match the frozen v2 package.
- User runtime logs confirmed **four NVIDIA L4s** and installed
  `adk_submission0.2.13` / `swegemma0.2.11`. The final summary has **80 real
  grades:13 solves and67 test failures (exit code1)**. Another49 records have abnormal
  test exits:35 code2,11 code-1,3 code124. The registered129-real-grade
  requirement is unmet (`complete=false`); platform completion is not clean
  validation or evidence of improvement.
- Inspected code2 logs include missing `scripts.prepare_release` on
  `fastapi_15661` and missing `is_typealiastype` import on `fastapi_13920`.
  `rich_3518` aborted on context overflow (27769 input +5000 requested output
  exceeds32768). Collection errors may be patch-induced; do not assume all49
  abnormal records are infrastructure failures.
- Complete pasted-log/progress cross-check finds **22 context-overflow tasks**,
  not just the11 code-1 aborts:11 code-1,7 code2,4 code1. All report the same
  lower-bound overflow message and five retries. Four are inside the80 real grades
  (`rich_4070`, `fastapi_11194`, `rich_3130`, `fastapi_15800`), so real-grade
  coverage does not mean error-free agent execution. **Correction: this is not
  proof of an exact one-token overflow.** Deployed vLLM0.19.1 deliberately
  tokenizes only to allowed input +1 for rejection and reports "at least".
  Increasing the budget by one token is not an established fix.
- Full129 bulk collection has finished:
  `Outputs/kaggle_tool_lora_p5_129_v2/result_report.json`. Collector code2
  reflects the unmet clean-grade requirement, not a missing download.
- User requested a much smaller follow-up on known E4B-solvable tasks. Prepared
  `kaggle_pkg/push_tool_lora_p5_controls_v2`: `rich_3006`, `rich_3454`,
  `rich_3905`, each16/16 prior E4B ARM_F successes and a checked raw
  resolved=True/test_exit_code=0/error=None grade. Two G_startup arms (adapter
  off/on) x two rounds =12 executions. Selection predates this full129 result;
  these are biased positive controls, not a held-out benchmark. Historical
  ARM_F is not identical to G_startup, so current base solves are measured.
- The full129 frozen source is unchanged. Follow-up notebook SHA256:
  `e08e31212ab570f8c1fbf4e46a13d61057caf31f2c4ec4980828a3188fbadb43`.
  Follow-up requires current run terminal plus saved passing serving gates,
  fresh quota >=5.34 device-hours, and a single new private push. Platform
  cap4800s; per-task wall2000s; eval cap2400s; three jobs/GPU, counterbalanced
  arms/rounds. Do not start it alongside the full129 allocation.
- Smaller private notebook `comfyops/e4b-tool-lora-p5-controls` **v1 COMPLETE**.
  Exact private source verified. Receipt:
  `Outputs/kaggle_tool_lora_p5_controls/receipt.json`. Full129 was COMPLETE and
  its saved gates passed before this single push; fresh quota was46.36677
  device-hours remaining. No simultaneous GPU allocation or automatic retry.
- All12 control executions graded and solved: **base6/6, adapter6/6**, all six
  pairs graded, routing verified, no recorded errors. On these selected tasks
  base used37 tools/62 LLM calls versus adapter53/80; no demonstrated solve or
  efficiency improvement. This cannot establish behavior on the22 long-context
  failures. Pulled control notebook sources match the frozen package.
- Old sequential collector PID5408 was explicitly stopped because downloading
  every full-run artifact delayed the requested control. Its historical log
  remains preserved. Replacement detached Python PID34448 finished collecting
  both versions; final state is `collected_both` (full collector2, controls0). State:
  `Outputs/kaggle_tool_lora_control_queue.json`; transcript:
  `Outputs/kaggle_tool_lora_both_collectors.log`. Check current receipts/state
  before resuming; do not launch either notebook again.
- Deeper trace audit: overflow tasks have median30 tool calls/35.5 LLM calls,
  versus11/15 among the other107 tasks. `rich_3518` has13 edit attempts with
  12 FileEditErrors; `fastapi_13713` has31 edit attempts, all failed. Repeated
  edits/rereads consume context. Historical pre-LoRA repro artifacts contain
  62 context errors in312 available rows across different ARM_F/ARM_R policies;
  this proves the failure predates p5, not a paired rate comparison.
- The runner explicitly sets32768 context and sampling reserves5000 output
  tokens. User-provided model configuration declares text context131072.
  Larger-window L4 runtime performance remains unvalidated here; existing
  server logs show7.8 GiB KV cache, not a64k runtime validation. Do not fetch
  replacement weights or mutate frozen runs.
- **Reuse prior context/memory evidence before proposing more experiments.**
  The log already records the260-execution E4B history-toggle A/B (H50/130,
  N58/130; formally inconclusive),31B compaction analysis (repeat reads4% to13%
  but no detectable within-task solve effect), scorer/CLI compaction mismatch,
  and correct patches undone/rescued by gate rollback and saved-attempt
  restoration. These are not new discoveries from p5. History inclusion was
  tested at32768, not a context-capacity sweep. The historical65536 llama.cpp
  setting was a12B shared pool with two32768-token slots. Do not mistake it
  for an E4B64k per-request evaluation, or treat a failed history toggle as
  disproving structured solution memory. No matched E4B64k/128k sweep was
  found in this log review; this is a search result, not proof none exists.
- The historical probe slug was unavailable. The first new-kernel push returned
  HTTP400; preserved its receipt under `Outputs/kaggle_tool_lora_p5_129`.
  After matching title/slug and compressing the embedded source, a non-executing
  private quick-save created v1 successfully; the registered execution is v2.
  Do not blindly retry/relaunch either receipt. Twenty-one local LoRA/launcher tests
  passed; generated code and changed Python files passed syntax checks.
- The full-pool diagnostic has no adapter-off arm; the smaller positive-control
  diagnostic is paired. Neither is the spec's staged repair promotion gate.
  No sealed behavioral evaluation, leaderboard submission or improvement claim.
- Existing collector supports read-only resumption:
  `python -m kaggle_pkg.run_experiment resume --output Outputs/kaggle_tool_lora_p5_129_v2`.
  Collect all raw grades, traces, patches and logs; require129 real grades and
  inspect fixer/verifier model receipts. Keep abnormal exits distinct rather
  than inventing grades or assuming an infrastructure root cause.

# 2026-11-18 update: overflow-only 64K follow-up completed at cutoff

- User explicitly approved **all22** prior p5 context-overflow tasks at65536
  tokens, including the four with real grades, not an arbitrary18-task subset.
  Selection preserves original task-file order and comes only from saved
  full129 v2 errors; original task definitions, all G_startup policy bytes and
  the p5 adapter are pinned against that execution's registration.
- Frozen package: `kaggle_pkg/push_tool_lora_p5_overflow64k`; new private target:
  `comfyops/e4b-tool-lora-p5-overflow64k` v1.   notebook SHA256:
  `9eedfcafacb6fd30c566250b8aff3bf0168e1c65297bb0130c46bc044326aa1d`.
  **v1 COMPLETE**, exact private remote source verified. Receipt:
  `Outputs/kaggle_tool_lora_p5_overflow64k/receipt.json`. Collector finished
  with exit2 because the diagnostic was incomplete at its registered cutoff,
  not because the result download failed. No repush.
- Four independent tp1 L4 lanes, **one task/GPU**, at most four in flight.
  Ten consecutive finalized results that are **not verified solves** trigger
  stop: ordinary unresolved results, errors and timeouts all count. A verified
  solve resets the streak. Completion order is the saved shared-lock receipt,
  not notebook output ordering. Stop cancels active evaluator descendants,
  prevents further dispatch, saves partial results and stops serving processes.
  Late/cancelled completions cannot reset the frozen stop state; never-started
  deadline tasks do not inflate the streak. Early stop remains incomplete.
- Each lane must retain native parser/repeatable adapter-effect gates and
  additionally advertise65536 and complete an adapter request with65528 input
  tokens plus8 output allowance before any task starts. Fixer p5/base verifier,
  prompts, sampling, gate and per-task caps remain unchanged. No HF downloads,
  new Colab allocation, Drive consent or leaderboard submission.
- Evaluation deadline3600s; platform cap4800s; at most5.34 device-hours.
  Fresh04:25 UTC quota receipt:45.84085 device-hours available, none reserved;
  both earlier kernels COMPLETE, target absent. Use SDK `total_seconds()`:
  its duration string drops days. Pay-to-scale is enabled; no independent
  dollar tariff is claimed. Receipt:
  `Outputs/kaggle_tool_lora_p5_overflow64k_preflight.json`.
- Validation:33 Windows tests ran (26 passed,7 Linux-only skips);15 Linux tests
  passed, including real detached-descendant   cancellation and isolation, preserved grades and explicit partial-trace errors.
  Frozen bundle/cohort/hash checks, generated invocation binding and Python
  syntax passed. Pylance's optional-stop error is fixed; only known absent
  local GPU SDK imports remain. Lower concurrency is intentional for the stop
  rule and prevents interpreting this single-arm recovery as a pure context
  effect or causal evidence against the LoRA.
- Actual result: all four L4s passed the full-window probe (65,528 input tokens,
  8 generated). Tenth non-solve, `fastapi_14356`, triggered the cutoff about
  28m42s into the run; 3 active tasks were cancelled and 9 never started.
  Zero verified solves; 2 exit1 grades and 8 exit2 collection errors.
  See `Outputs/kaggle_tool_lora_p5_overflow64k/result_report.json`.
- Same ten completed task IDs at 32K vs 64K: recorded overflows 10 to 0;
  nonempty test logs 4 to 10; nonempty patches 4 to 9; valid grades 1 to 2;
  solves 0 to 0. Five 64K traces record prompt counts above the old 27,768-token
  input allowance; the other five could have fit at 32K on their observed
  trajectories. These are descriptive differences, not causal estimates.
- Raw 64K pytest evidence: 5 of 8 collection-error logs show missing
  `inline_snapshot` or `dirty_equals` (one also shows an import error); the
  other three show syntax/name errors. `fastapi_14258` moved from a syntax
  error to a failing behavior assertion. `rich_4070` moved from an indentation
  error to 123 passing tests plus one TTY/stdin failure, still not solved.
  Clean-snapshot vs saved-patch replay can separate environment failures from
  patch regressions without another GPU allocation.

# 2026-11-18 update: native131072-token follow-up submitted

- User requested "Once we submit the 64k submit 131k";64K is already submitted.
  Private `comfyops/e4b-tool-lora-p5-overflow131k` **v1 COMPLETE**, exact private
  remote source verified. The follow-up uses
  **131072 tokens** (native128K), using exactly the same22 task definitions,
  policy/adapter hashes, task limits, deadlines, four lanes and ten-consecutive-
  non-solve cutoff. Submission may overlap64K; do not replace/restart64K.
- Frozen package: `kaggle_pkg/push_tool_lora_p5_overflow131k`; notebook SHA256
  `7cbd54c2b03af4e245d0e416724e344c52162eb7b53360202b7fe9265878b49d`.
  Receipt: `Outputs/kaggle_tool_lora_p5_overflow131k/receipt.json`. Detached
  collector `kaggle-overflow131k-collector` waits up to4h for this version and
  collects independently without pushing. Check its receipt before any
  recovery. Original64K frozen notebook is unchanged.
- Each serving lane must advertise131072 and complete a native adapter probe
  with131064 input tokens plus8 output allowance, in addition to the parser/
  effect gates. Actual agent output reserve stays5000, allowing126072 input
  tokens. No changed gate/prompt, checkpoint replacement or HF download.
- Fresh04:41 UTC quota:45.41855 unreserved device-hours available,0 reserved.
  Additional cap5.34 device-hours; both runs combined at most10.67.
  At the single131K push, quota was rechecked:45.33829 device-hours available;
  64K still RUNNING. Launcher appended preregistration before the push.
  Pay-to-scale enabled; dollar tariff not independently quoted. Resource
  receipt: `Outputs/kaggle_tool_lora_p5_overflow131k_preflight.json`.
- Validation:34 Windows tests ran (27 passed,7 Linux-only skipped);16 Linux
  tests passed. Exact full-window probes reject truncation/no completion/
  wrong advertised capacity. Generated131K invocation, embedded syntax,
  input equality and both frozen-package preflights passed. Local GPU SDK
  imports remain unavailable, not installed for editor-only validation.
- Runtime verified 131,064 input tokens and 8 generated on all four L4s.
  Stopped at the tenth non-solve, `fastapi_14873`, at about 34m11s:
  no verified resolves, one failing real grade (`rich_4070`, also hit the
  80-tool cap), nine ungraded completions, three cancelled, nine never
  started. No reported overflow in the ten completions. Both context
  follow-ups are closed as solve-improvement levers for this selected cohort.
  The pulled v1 notebook cell sources match the frozen registration.

# 2026-11-18 update: p5 repeat39 at 32K launched

- User selected **all 39 historical score tasks, 16 paired rounds**:
  624 task-round pairs / 1,248 total attempts. The original 39-ID manifest
  matches all sixteen saved ARM_F passes. The old 15/26 and 16/26 were
  single-pass highs on a different 26-task cohort; fresh retry on this 39
  averaged 11.50/39, and historical pack 1 averaged 12.00/39. Neither
  replaces the live control.
- Compare `G_startup` base against the same `G_startup` with p5 on the
  fixer only; the base verifier, sampling, prompts, tests, and task caps
  are unchanged. Reuse mounted Kaggle model/adapter and 32,768 context.
  Four L4s, eight evaluator slots per GPU, and both arms of each pair
  dispatched together to the same GPU. No non-solve cutoff in this A/B.
- Preregistered signal: all pairs attempted, no global-deadline interruptions
  or observed routing violations, at least 16 net additional verified
  solves, and one-sided task-cluster sign-flip p <= 0.05. Report per-task
  and per-round outcomes, clean-grade discordance, regressions and abnormal
  outcomes separately. No leaderboard, holdout, or equivalence claim.
- Frozen `kaggle_pkg/push_tool_lora_p5_repeat39`, notebook SHA256
  `a490a2dcb65ac59aa11958443146c9b25da5aa15039f414b61758f4b0d468e17`.
  Private `comfyops/e4b-tool-lora-p5-repeat39` **v1 RUNNING**; exact private
  source verified. Receipt `Outputs/kaggle_tool_lora_p5_repeat39/receipt.json`.
  Detached collector `kaggle-p5-repeat39-collector` is responsive and saves
  results without pushing. Notebook cap five hours/20 device-hours, evaluation
  deadline 16,800s. Both overflow runs were COMPLETE; 43.72594 unreserved
  GPU-hours were available immediately before launch. Timings-based estimate was
  4.07h median and 4.16h p95 evaluation, not a completion guarantee.
- Targeted validation: Windows 29 passed and seven Linux-only skips;
  Linux 18 passed. Full mocked schedule covered all 624 pairs, both arms
  together on the same GPU. Source preflight and arm/task byte checks
  passed. Check the launch receipt before any recovery; never repush.

# 2026-11-18 update: evidence-to-edit seed39 diagnostic submitted

- The Colab evidence-to-edit seed completed three optimizer updates; the
  mapped export and all three checkpoints were verified on Drive. Colab showed
  zero active sessions at closeout. This is not the larger training corpus.
- The user selected one adapter-only pass on the same 39 historical score
  tasks at 32K, using the base verifier and unchanged G_startup policy.
  Notebook startup checks the mounted task and adapter hashes, then checks
  native serving and fixer/verifier routing on four L4s before tasks start.
- Private `comfyops/e4b-evidence-to-edit-seed39` v1 was QUEUED at launch;
  adapter dataset `comfyops/e4b-evidence-to-edit-seed-pilot` was ready.
  The launch receipt is `Outputs/kaggle_e4b_evidence_seed39/receipt.json`;
  collector `kaggle-evidence-seed39-collector` is version-pinned. Do not retry
  a push. Platform cap 4,800s / 5.34 GPU-hours; 40.10 GPU-hours remained
  before launch. The ongoing p5 repeat39 notebook was not changed.
- Compare verified solve IDs and per-task outcomes descriptively against
  completed p5/base rounds; report grade, routing and runtime failures
  separately. There is no live control or leaderboard claim.
- The original pass recorded 13 verified solves, 20 clean failures, five
  overflows and one grader timeout. For nine additional passes, the
  hash-pinned `comfyops/e4b-evidence-to-edit-seed39-rounds-2-to-10` v1 preserves
  Seed39's inputs and four-L4 serving gates; run labels are 2-10, without
  rerunning round 1. Its receipt and results are written under
  `Outputs/kaggle_e4b_evidence_seed39_r2_r10`. The limits are 9,600 seconds
  for evaluation and 10,800 seconds platform wall (12 GPU-hours maximum);
  the prelaunch check found 37.72 included GPU-hours left and zero reserved.
  Compare the distribution of completed rounds, including counts below 12
  solves; the comparison to p5/base is descriptive, not a new paired arm.
  Kaggle created the notebook under its title-derived slug. Its private v1
  source matched the frozen package; the receipt records both slugs. Resume
  read-only with the actual slug from the receipt, never repush.

# 2026-11-17 update: p3/p4 outcomes; p5 IDE notebook completed

- **p3 actual result:**96/96 native tokenizer preflight accepted, checkpoint
  SHA256 verified, official Transformers reference model loaded/decompressed;
  then failed before any forward comparison or training because reference
  prompt0 had only13 tokens against the16-token requirement. The specific p3
  session was stopped;0 active assignments,0/hr. p3 balance275.86 ->275.58 CU
  (displayed delta0.28 CU); p2+p3 displayed total1.24 CU. Copied actual logs and
  status under `Outputs/e4b_tool_lora_20261117_p3/drive_receipts`.
- Fixed all short prompts and moved their token-length check ahead of the
  reference model load. Exact E4B tokenizer/Transformers5.13.1 lengths are
  19,16,16,16,16,17,18,17. Tests prove a short prompt fails at preflight.
- **p4 actual result:** the 3072-row tokenizer preflight, checkpoint hash, and
  independent reference-fidelity gate passed (128 positions, top-1=1.0,
  mean KL=0). It then failed before the first optimizer update: the trainer
  expected q/v projections in all42 layers, but E4B shares K/V across18
  layers, so actual coverage is q=42, v=24, total66 rather than84. No adapter
  was exported. The trainer now derives expected coverage from the model
  configuration; p5 subsequently passed this check on GPU.
- p4's worker ran711.5 seconds on one L4 at1.94 CU/hour. Balance275.58 ->
  275.11 CU (displayed delta0.47 CU); it stopped with0 active assignments and
  0 CU/hour. Several CLI status reads lost connection, but the bounded launcher
  collected the actual failure receipt and shut down the runtime. Cumulative
  displayed p2-p4 cost is1.71 CU. Full result:
  `Outputs/e4b_tool_lora_20261117_p4/outcome.json`; Drive receipts remain
  under `Outputs/e4b_tool_lora_20261117_p4/drive_receipts`.
- The focused Windows suite now reports22 tests run:17 passed and5 WSL-only
  launcher tests skipped on Windows. The separate WSL launcher suite previously
  passed5 cases. The passing reference-fidelity gate is a model-reconstruction
  check only, not a repair or capability result.
- p5 is frozen and preregistered at
  `Outputs/e4b_tool_lora_20261117_p5/registration.json`; bundle SHA256
  `2c8611974bc0bb711494e05bffeba72f124b271e89880cab8cab344e3c862cbc`.
  It uses the same exploratory data,32 intended updates, accumulation4,
  validation sample32, and checkpoints after every update. Its ceiling is
  3900 seconds or2.1 CU (whichever comes first), with a2.0 CU/hour rate cap.
  The prepared bundle is staged at
  `G:\My Drive\gemma_fasteval\ide_lora_bundle_e4b_tool_state_p5`.
- **p5 actual result:** the user authorized unattended notebook execution,
  pinned dependency setup and Drive access. Reconnected their existing
  `L4P5111626` session; no additional runtime was allocated.
  `train/colab_tool_lora_ide.ipynb` now restores the cached tested environment
  and runs the frozen trainer as a foreground child with live output, instead
  of replacing Torch in the Python3.13 notebook kernel.
- Corrected a notebook-only preflight bug: the frozen tokenizer receipt uses
  an empty `rejected` list, not numeric0. Reused the extracted staging inputs
  only after checking every registered member hash; no frozen bundle/source/
  data or training setting changed. Focused receipt/tamper/deadline regressions
  pass. Setup/correction consumed the same original budget clock.
- Completed32 finite, nonzero-gradient updates and saved32 native PEFT Drive
  checkpoints. Confirmed q=42/v=24/total66 target modules,132 adapter tensors.
  Reference fidelity passed128 positions (top-1=1.0, KL=0); zero-adapter and
  native-reload max logit deltas=0; adapter on/off max logit delta=1.25.
- Validation NLL on32 held-out examples:0.91485078 ->0.91271102. This small
  sampled-loss movement is not a tool-use/repair capability result. No sealed
  test or serving compatibility result is established. Keep
  `training_ready=false`; no capability or leaderboard prediction is authorized.
- Results, logs and native adapter persisted in Drive:
  `G:\My Drive\gemma_fasteval\lora_runs\e4b_tool_lora_20261117_p5`.
  Total notebook budget clock1822.2s, including1414.5s before the trainer;
  effective cap3780s (registered3900s/2.1 CU/max2.0 CU/hour).
  Observed balance275.06 ->274.10 CU, displayed delta0.96 CU.
  The notebook called `runtime.unassign()` after saving results; verified
  **0 active sessions and0.00 CU/hour**. Do not relaunch automatically.
- All32 saved checkpoint hashes were independently verified against their
  receipts. Final exports and reports are copied locally under
  `Outputs/e4b_tool_lora_20261117_p5/drive_receipts`; the native export is9,094,104
  bytes,132 tensors, and matches checkpoint32. See
  [p5 outcome](Outputs/e4b_tool_lora_20261117_p5/outcome.json).

- User explicitly authorized **one L4, at most2h or4CU** and completed Drive
  consent in the visible VS Code terminal.
- Fresh session: `e4b-tool-lora-20261117-p2`; verified one NVIDIA L4,
  rate1.94 CU/hour, starting276.82 CU, stop floor272.82 CU.
- Preregistered frozen payload:
  `Outputs/e4b_tool_lora_20261117_p2/registration.json`.
  Bundle SHA256:
  `52077e737cdfd64b58371ab3cc71b6cf0b590437a92e29c51cfd252d2b4411e5`.
- Build used the original96-row engineering input and at most3 intended updates.
  Adds independent supported-reference fidelity, zero-adapter equality,
  nonzero adapter effect and native export/reload checks. No gate success or
  trained adapter verified. It failed before model loading, with0 optimizer
  updates and no adapter. Competition serving remains unverified.
- Actual failure: Transformers5.13.1 defaults `apply_chat_template` to
  `return_dict=True`, giving `BatchEncoding` where `encode` expected token IDs.
  Fixed both calls with explicit `return_dict=False`; independently reproduced
  v5 return type and verified all96 original rows at max1851 tokens using the
  exact v5 version, without legacy metadata overrides.
- Terminal also reported `RuntimeError: Connection was lost`; copied actual
  failure/environment/log receipts from Drive, explicitly stopped the specific
  failed session and verified0 active assignments,0/hr. Ending275.86 CU;
  displayed balance delta0.96 CU. Outcome:
  `Outputs/e4b_tool_lora_20261117_p2/outcome.json`.
  No automatic fresh allocation/relaunch. Use terminal/Drive receipts, not
  concurrent independent CLI exec calls into the monitor's kernel.
- New launcher `colab_fasteval/colab_tool_lora.sh` owns visible consent,
  hard7200s watchdog, CU/rate checks, read-only retries, failed-state handling,
  result download and specific-session shutdown. Future attempts now bound each
  read-only command to65s, suppress bare-runpy globals, reserve cleanup time
  inside the total deadline, and run a native-tokenizer preflight BEFORE
  staging checkpoint weights. Never rerun p1 or the closed p2.
- User emphasized generating thousands of original code/example sets.
  `train/tool_state_cases.py` + `--variants-per-family 32` now produces
  384 original buggy/fixed program cases and3072 decision rows; full native
  edit/Git/memory generation completed in `Outputs/tool_state_synthetic_3072`.
  Exact v5 native prefix/length audit:3072 accepted,0 rejected,max1879 tokens.
  Split2048 train/512 validation/512 test. Dataset SHA256:
  `cf79d697c37fd0d2e1005a481ba232e4306f58da151f90458e7d0ce3f1773df9`.
  This is12 underlying mechanism families, not384 independent families.
  Initial corpus execution caught an invalid iterator counterfactual; fixed the
  source fixture and added its regression before successful generation.
  Token gate passed; serving-schema/full-sandbox equivalence and broader family
  diversity remain unverified. Keep `training_ready=false`.
- Thirteen Windows numerical/program/data tests and five WSL real-launcher
  success/failure/network/cost tests passed. New Python syntax checks passed.
  No leaderboard submission, no Git commit or push.
