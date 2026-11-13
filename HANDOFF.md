# AI Handoff: Gemma 4 Developer Agent competition (as of 2026-11-13 03:30 UTC)

Read this first, then `GEMMA_EXPERIMENT_LOG.md` (the source of truth; newest entries at the bottom; the "standing truth"
block at the top). Repo `c:\Users\biges\Gemma\Gemma_Competition`, Windows + PowerShell, WSL Ubuntu available. GitHub
`GeorgeRCAdamJohnson/Gemma_Competition`, push to `main` (user's convention). Update the log BEFORE every push.

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
- `_locate_ceiling.py`: 73% of failures edit the RIGHT file first -> the wall is in-file logic/contract.
- `_statement_accuracy.py` / `_statement_contract.py`: 71% of statements name neither gold file nor symbol; 61% contain none
  of the hidden test's strings; E4B solves 30% when the gold file is named vs ~6% otherwise; PR-style 17% vs issue 2%.
- `_multifile_solves.py`: only fastapi_14077 of 38 multi-file tasks ever solved (87%, usually 1-file patches).
- `_near_miss.py` / `_near_miss_detail.py`: 21 rarely-solved tasks are strict near misses (best failing run misses one
  edge-case test, e.g. rich_3782, fastapi_14794, fastapi_15763, rich_4075, rich_3052). Pack 1 has ~1 run on each:
  **pack 1 is unmeasured on 103 of 129 tasks.**
- Inconsistency found, untested: pack 1's `fixer.md` says "~28 tool calls and 8 minutes" but runs at 80 calls / 30 min.

**Recommended next experiments (in order):**
1. Fix Colab reliability (section 2) — nothing else runs without it.
2. Near-miss sweep: pack 1 on the 21 near-miss + 13 "effectively single-file" multi-file tasks, 5 passes each
   (~1-1.5 h L4, ~2-3 CU). Goal: measure pack 1 where it was never measured; grow the A/B set; read contract misses.
3. Batch 6 rerun only if still wanted (prediction is null). Single-change arm: fix the 28/8 budget text to 80/30.

## 2. Colab: how it works here
**Accounts/balance:** Colab Pro+, 362.69 CU, nothing billing. L4 ≈ 1.94 CU/h (G4 ≈ 10, CPU 0.08). Never use G4.

**Two control paths:**
- API wrapper (Windows): `python colab_fasteval/colab_mcp.py exec "runtimes/<id>" <file.py>` runs a file in a FRESH kernel.
  Get the exact runtime name (ends in `........`) with `python colab_fasteval/_runtimes.py`. Auth = ADC with colaboratory
  scope, quota project `htmlhub-dev-20260703174246`. Each exec stream is cut server-side after ~4-5 min -> keep calls short.
- Official CLI in WSL via `~/colabw` (= `colab --auth=adc`), currently PINNED to 0.7.5 (`colab_fasteval/wsl_pin_cli.sh`).
  `wsl -d Ubuntu -- bash -c "~/colabw new -s NAME --gpu L4"`, `upload -s`, `exec -s -f`, `status -s`, `sessions`, `usage`,
  `stop -s`. On 0.7.5 `exec --timeout` is a HARD cap (0.8.0: idle seconds). `colab sessions` can falsely report "gone".
- WSL commands with nested quotes/`$` are rejected by the tool parser: put logic in a script file and run it.

**Drive mount (needs the user):** `bash ~/drivemount.sh <session> <auto_release_s>` (in WSL). It prints a consent URL; the
browser auto-open fails, so paste the URL to the user. If the first try fails, rerunning right away usually mounts without
a new link. Verify with `_probe_mount.py` via the API ("drive mounted: True").

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
