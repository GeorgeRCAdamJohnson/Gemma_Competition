# Implementation Plan — Gemma KB / auditor toolkit REVISION 5 (task kb-rev5)

Abbreviations (absolute paths; relative paths land in the wrong place):
- ROOT = `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE`
- G    = `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma`
- K    = `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb`
- T    = `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\.agents\tasks\kb-rev5`
- B    = `python c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\build_kb.py`
- Kaggle CLI = `C:\Users\Biges\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\local-packages\Python313\Scripts\kaggle.exe`

Interpreter (MEASURED 2026-10-31): `python` = `ROOT\.venv\Scripts\python.exe`, CPython 3.13.14, pytest 9.1.1, the
same env the rp-4 cache keys were written with. Never drive replays with `G\.train_env\Scripts\python.exe`
(it has no pytest, so every task comes back INVALID; log 2026-10-16 "INTERPRETER TRAP").
PowerShell swallows child stdout: always run `B ... *> $env:TEMP\x.txt` and read the file.

FEAT files (the per-feature execution units) are in `T\features\FEAT-00{1..5}.json`; `T\context.json` holds the
project context. This file is the full plan; the FEATs restate its items as steps.

---------------------------------------------------------------------------------------------------------------

## 0. What exploration found (inventory since the last build stamp 2026-10-16T07:16:10Z)  [MEASURED unless tagged]

Freshness: `B check-fresh` → exit 3 `STALE`. Tests: `python -m pytest tests -q` (cwd K) → `47 passed`.
The last build covered 31 run dirs, 165 traces, 242 rows, log 10,108 lines. Today (2026-10-31):

- **Log** `G\GEMMA_EXPERIMENT_LOG.md`: 14,554 lines (+4,446). The new `##` entries run L10115–L14548 (fastapi routing
  probe; B_temp1 0.13; all-task gold gate; gate-noise math; budget raise 57276407 threw; cover-rich; size ladder
  (later VOIDED, five variables moved); arch-remap; local E4B parity rig; A1–A25 arms; A3 delimiter fix = LB 0.18
  (2026-10-20); Colab 31B harness; HARNESS BUG: 91/124 sweep patches corrupted (2026-10-20); D-arms RETRACTED;
  129-task 31B A3 run 34/129; LB denominator = 58 tasks; A25 router 0.13; ca5 = **0.20** (ref 57760641,
  2026-10-30, "new personal best"); E4B crown 57807043 = 0.03; small-model $10K track; official-12B local
  62/91; scorer-blocker audit 7/129; Kaggle 31B full-129 v7 = 35/129 + two retractions; phantom-budget claim
  RETRACTED; "E4B was really 12B" claim later RETRACTED as UNVERIFIED; 3 code-intelligence tools DEAD; ca5
  resubmitted 57847285 (2026-10-31); locate-numeral arms). Many entries carry `CORRECTION`/`RETRACTION`/
  `[RETRACTED …]` markers.
- **New Kaggle run outputs** (JSON kernel logs with `-> resolved=` lines, ATIF-v1.7 traces): `submit_cover_rich\out_v5`
  (31), `submit_repeat_live\out_v1` (10), `submit_size_{e2b,e4b,12b}\out_v*`, `submit_remap_{e2b,e4b}\out_v1`,
  `submit_v7_{e2b,e4b}\out_v2`, `out_k_e4ba3`, `out_k_e4ba5` (44 each), `out_repeat_v2` (10),
  `local_eval\pull_31ba3hard_out` (129), `local_eval\pull_31ba3hard_v11_out`, `local_eval\pull_a2{1,2}_out`.
- **New Kaggle runs WITHOUT `resolved=` lines** but with `results\task_results.jsonl` (+ JSON log, traces):
  `kaggle_pkg\out_{v6,v7,e4b,e4b_v3}` (129 traces each). Their config lives in `out_v7\agent_ca5\` (not
  `submission\`). `out_v7\summary.json` says 5/9 while 129 traces exist (partial summary; `recovered_full129.json`
  beside it) → outcome source must be `task_results.jsonl`, not `summary.json`. The current rule would file these
  as `run-dir-failed` (0 result rows) — wrong.
- **Local rig runs** (`G\local_eval\parity_rig\**\r<N>\` and `m1_full129\<arm>\`, `m1_locate\<arm>\`): layout
  `traces\trace_<task>.json` (ATIF-v1.7, NOT under `results\`), `task_results.jsonl`, `summary.json`, `logs\`,
  `patches\`, `test_outputs\`. ~170 rN dirs, ~1,180 traces. Arm config = `parity_rig\agent_<arm>\` or
  `agent_ctrl_<arm>\` (agent.yaml / eval_config.yaml / configs\sampling.yaml / prompts\system.md). Traces carry
  no model name (`agent = {name: adk-eval-core}`); the served model is not recorded (log 2026-10-31 shows the
  declared/served model was disputed) → served model is UNVERIFIED for rig rows. `summary.json` can disagree with
  `task_results.jsonl` (ca5\r1: summary 4 tasks, 7 traces).
- **Local sweep runs** `G\local_eval\runs\` (3,059 files): `<tag>.results.jsonl` (748), `.pinned.jsonl` (631, pinned
  rescore), `.guard.jsonl` (638; `cmd` has `--model`, `--isolate`), `.trace.jsonl` (custom per-turn format, NOT
  ATIF), `*.patches\` dirs, 8 `*.sweep.jsonl`. Patches from runs without `--isolate` are UNTRUSTED (log
  2026-10-20 HARNESS BUG: concurrent gate_run processes shared one worktree).
- **Kernel dirs**: 115 `kernel-metadata.json` (list in §0 of `T\context.json` notes). New families not matched by the
  current `"gemma-sibling-conform-" in id` rule: `comfyops/gemma-submission-packager[-a25|-ca5|-ca5v2]` (these
  produced the scored zips), `comfyops/ca5-{31b,e4b}-full129-eval`, `comfyops/ci-tools-probe`, `probe-*`.
  Dozens of `push_*` dirs (2026-10-18) hold only `kernel-metadata.json` + notebook (outputs not local; `pull_*`
  dirs hold ≤1 file).
- **Scored-zip evidence on disk**: `local_eval\pull_packager_ca5_out\submission\` + `submission.zip` (the 0.20 pack,
  prompt sha256[:12] `b9aeaa9a53ce`, caps 28/8/120/300), `local_eval\pull_submissions\<ref>_<desc>.zip` (5 submission
  zips: 57424022, 57470483, 57530249, 57551592, 57582998), `local_eval\leaderboard\lb.csv` (public LB snapshot).
- **Legacy manual pull** `K\pulled\v6w_temp1_probe\` (no `_pull_meta.json`): its `submission\configs\sampling.yaml` is
  **temperature 0.2** — this is the exact trap the brief names (submission 57201051 was temp 1.0 / top_k 64).
- **Gold-first coverage already measured** by the user's driver `G\local_eval\gold_gate_all.py` (imports
  `kblib.replay` rp-4) into `K\replays\goldgate_all.json`: 48 rich tasks = 43 VALID-HARNESS-LIKE, 1 VALID-GOLD-RELATIVE
  (rich_3472), 4 INVALID (rich_3468, rich_3486, rich_3675, rich_3782 — log L10242ff: required nodes SKIPPED on
  Windows by rich's own skip markers; exit 0 / failed 0 / errors 0). Records lack `gold_pass_tests` and
  `engine_version`; total secs 2,994 (max 905). `K\replays\gold\` holds full records for only 4 tasks;
  `K\audits\_decode_sweep_cache\gold_gate.json` holds 12. Fastapi: never gold-gated.
- **Clones** (read-only check): `repos\rich` HEAD 58ac1512 clean, `repos\fastapi` 0bdc3ca37 clean. Rich has a
  user-created extra worktree `repos\_wt_capconv_ctrl_A3_r0_rich_3772` (external; never touch). New clones
  `repos\requests`, `repos\httpx`, `repos\rich_b/_c/_v` exist (not wired into replay this revision).
- **Dev harness**: every Gemma eval notebook (`*.ipynb`, `probe_lora_load\notebook_src.py`, `colab_fasteval\
  fast_eval_reps_v2.ipynb`) constructs `EventsCompactionConfig(compaction_interval=15, overlap_size=2,
  token_threshold=14336, event_retention_size=5)` and `ContextCacheConfig(min_tokens=2048, ttl_seconds=1800,
  cache_intervals=10)`; HARNESS_README L556 says the scorer uses `compaction_interval = 5`. So nearly all dev gates
  ran a different compaction interval from the scorer.
- **CLI/contract gaps found in the current code** (these are blocking-class "recipe contradicts CLI" defects):
  `build_kb.py` has NO `replay` subcommand although the agent file and recipe call `B replay ...`; `claims` ignores
  `--task/--version/--lever/--text` (only `--status` filters); `pull` is a stub; `_baseline_banner()` hardcodes
  "gemma-submission-protocol.md still says v6 @ 0.12 and is STALE" (steering now says v6w @ 0.15);
  `_lever_lines()` is a stub; `curated\lever_lexicon.json` does NOT exist (the brief assumed it does).
- **Foreign tooling** (the user's, read-only to us): `G\build_kb.py` (rebuilds `G\EXPERIMENT_KB.sqlite` — NEVER run
  it, it writes outside our allowed set), `G\kb_query.py` (read-only SQLite FTS over the log: `search`,
  `section`, `experiments`), `ROOT\.github\agents\gemma-experiment-reviewer.agent.md`, `G\.git` (user repo — never
  commit). `ROOT\gemma_push\GEMMA_EXPERIMENT_LOG.md` is an older copy outside G (not an input).
- **Current submissions baseline** (curated `submissions.csv`, pulled 2026-10-15): newest row 57201051 = 0.13. The
  log (unverified until a pull) names ca5-31B 0.20 (57760641), A3 0.18 x2, A23 0.15, A25 0.13, E4B 0.03
  (57807043), resubmit 57847285 (pending). So a fresh pull will almost certainly show a live-best ≠ v6w @ 0.15
  → **BASELINE CONFLICT** to report, never adopt.

---------------------------------------------------------------------------------------------------------------

## 1. Design decisions (each with rationale)  — recorded in REVISION 5 (§3 of this plan)

D5-1 **Stack + track on every row.** Each row gets `stack = {platform: kaggle|local-rig|local-sweep|colab|unknown,
  scorer: harness|rig-local|sweep-pinned|sweep-raw, model_declared, model_served_verified: bool}` and `track =
  main (31B) | small-model (E2B/E4B) | dev-proxy (12B, others)`. Replaces the binary `out_of_scope`. Rationale: the
  KB now mixes four stacks and two prize tracks; a matrix that pools them would mis-state every lever.
  `model_served_verified` is true only for Kaggle runs whose kernel log names the served model; rig/sweep = false.
D5-2 **Outcome sources, in priority:** (1) kernel-log `-> resolved=` lines; (2) `results\task_results.jsonl` or
  `task_results.jsonl` beside `traces\`; (3) sweep `.pinned.jsonl` (pinned rescore) else `.results.jsonl`.
  `summary.json` is read only to emit a `summary_disagrees` warning. Rationale: kaggle_pkg logs have no
  `resolved=` lines and rig summaries are partial.
D5-3 **Config sources, in priority:** `submission\` → a single `agent_*\` child dir with `agent.yaml` (kaggle_pkg) →
  rig arm map `parity_rig\agent_<arm>` then `agent_ctrl_<arm>` → sweep guard `cmd` flags (`--model`,
  `--temp`, `--max-tool-calls`, `--prompt-file`, `--isolate`) → none. `config_confidence` names which one.
D5-4 **Sweep rows are summary-only.** `.trace.jsonl` is not ATIF and is not modelled; rows carry outcome + config +
  `patch_trusted` (true iff the guard cmd has `--isolate`). Untrusted patches are never replayed. Rationale: honest
  scope; the 2026-10-20 corruption is MEASURED.
D5-5 **Submit-dir rule** = any dir with `kernel-metadata.json` whose id starts `comfyops/`, carrying
  `kernel_family` (sibling-conform | packager | full129-eval | probe | train | other). Foreign kernels
  (`comp_other\`, `competitor_probe`, `getting_started`) are `reference-kernel`. Labels: slug minus
  `comfyops/gemma-sibling-conform-` (e.g. `31b-a3-hard`, `cover-rich`), packager → `packager-<suffix>`.
D5-6 **Coverage accounts for everything.** KB_SUMMARY §2 gets a "since last build" table: every new/changed run dir,
  kernel log, trace dir, submit/push/staged dir, sweep tag and log `##` entry (by line range) with `parsed: yes/no`
  and the reason. The previous stamp is read from the PREVIOUS `build_meta.json` (`newest_input.mtime_utc`
  2026-10-16T05:05:06Z) and frozen into a builder constant `REV5_PRIOR_BUILD_UTC` so output stays idempotent.
D5-7 **Staged submissions (D3-4).** Dirs with agent.yaml+eval_config.yaml and no kernel-metadata.json at top level
  (`submit_t4096`, `submit_branch_final`) get config extraction via `configs.extract_config(dir)` and
  `zip_drift` = per-file sha256 compare of the dir's agent package vs the sibling `submission.zip` (stdlib
  `zipfile`, read-only): `MATCH | DRIFT(<files>) | NO_ZIP`. Same zip-drift check runs for `pull_packager_*_out`.
D5-8 **Dev-harness AST pass (D3-5).** New `kblib\devharness.py`: for each submit/push/pulled dir, parse
  `notebook_src.py` and every `*.ipynb` code cell (cell source joined; lines starting `!`/`%` blanked) with
  `ast.parse`; record keyword args of `EventsCompactionConfig(...)` / `ContextCacheConfig(...)` calls (constants
  only via `ast.literal_eval`; never comments, never regex). Scorer values from HARNESS_README (`compaction_interval
  = 5`, `overlap_size = 2`, `token_threshold = 14,336` read by regex on the README's bullet lines). Per run
  `dev_harness = {compaction_interval, …, source, matches_scorer: bool|null}`. Each mismatching field is a lever
  instance `dev-harness:<field>=<value>` in the lever matrix. No code is executed.
D5-9 **Pull (§14 as amended by the brief).** `kblib\kaggle.py`; argv allowlist exactly: `competitions submissions
  gemma-4-developer-agent --csv`, `kernels list --mine --csv --page-size 200`, `kernels output comfyops/<slug> -p
  <dir>` (+ `--file-pattern <regex>` iff `kernels output --help` lists it), `kernels pull comfyops/<slug> -p <dir>
  -m`, and `kernels output --help`. subprocess.run(argv list, stdout=file, stderr=STDOUT), never PowerShell, never
  `push`. Layout `K\pulled\<slug>\<pull-utc>.partial\` → renamed to `<pull-utc>\` after `_pull_meta.json` is
  written. Submissions snapshots → `K\pulled\submissions\<pull-utc>.csv` (+ `.meta.json`). Post-download sweep
  deletes `.safetensors` > 50 MB and every `.bin/.gguf/.pt/.pth`, recorded in `_pull_meta.json.deleted`.
  `--dry-run` prints targets/argv only; `--max N` (default 12) bounds a run; `--slug` repeatable; `--submissions`;
  `--targets` (auto). Network only here; `build` never imports `kaggle.py`'s runner.
D5-10 **Pull attribution + mismatch flag.** `kernels output` returns only the LATEST version, so every pulled run is
  `attribution.kind = latest-at-pull`. The builder compares the pulled `submission\` (or `agent_*\`) config with
  every submission whose description maps to the pulled label (or explicit `--for-ref`), using the description's
  stated config facts (F4 patterns: `temperature X`, `top_k N`, `thinking N`, budget quad `a/b/c/d`, `max_tool_calls
  N`, model token) and, when a local submission zip for that ref exists, the zip's file hashes. Any stated fact that
  differs → `ATTRIBUTION-MISMATCH: pulled output does not explain ref <R> (<field>: pulled <x> vs submission <y>)`;
  equal hashes → `ATTRIBUTION-CONFIRMED`; else `ATTRIBUTION-UNVERIFIED`. The legacy `pulled\v6w_temp1_probe` gets the
  same check (label from its log name → v6w → refs 57098497 and 57201051) and MUST come out MISMATCH vs 57201051.
  A mismatching pull is never used as evidence for that ref (rows keep `explains_refs: []`).
D5-11 **Pull targets** (auto): (a) every COMPLETE/ERROR submission ref in the newest snapshot whose producing kernel
  has no local output, where producing kernel = description `Notebook <Title> | Version N` / `<Title> - Version N`
  slugified and confirmed in `kernels list --mine`; (b) log version tokens whose submit/push dir has a kernel id
  but no local run dir; minus slugs already in `K\pulled\<slug>\` unless `--force`. Scored refs first, newest first.
D5-12 **Submissions source selection.** The builder uses the newest `K\pulled\submissions\*.csv` whose pull time is
  newer than `curated\submissions.csv` mtime, else curated; KB_SUMMARY §7 names the file used and both dates.
  Curated files are never rewritten.
D5-13 **Baselines per track + conflict.** Policy baseline = `curated\run_labels.json:baseline` (main track). The
  banner is computed from the steering file's ACTUAL text: parse `G\..\.kiro\steering\gemma-submission-protocol.md`
  for `\*\*(\S+) @ (0\.\d+) is SACRED` and the `submission (\d+)`; banner states `steering says X @ s (ref r)`,
  `curated baseline Y @ t`, `LB best on main track (from <csv>) Z @ u (ref q)`. Any disagreement →
  `BASELINE CONFLICT: …` (never adopted). Same for small-model track (best COMPLETE E2B/E4B-described submission vs
  curated, which has no small-model baseline → conflict "no curated small-model baseline"). The steering file is
  added to the input fingerprint (banner depends on it).
D5-14 **Stale curated artifacts → proposals, generated.** The build writes `K\curated\_proposed_updates.md` (the ONE
  allowed path under `curated\`, added to `io.safe_write`'s allowlist as an exact file) listing each detected
  curated staleness as a proposed JSON patch: `run_labels.json.pending[branch_final]` → status COMPLETE 0.12 (ref
  57146757); baseline conflict(s); missing `lever_lexicon.json` (proposed content = the builtin default); missing
  small-model baseline; `submissions.csv` refresh from the newest snapshot; `replay_set.json` additions only if a
  min-set run id no longer exists. KB_SUMMARY §7 renders branch_final from the submissions data (COMPLETE 0.12), and
  labels the curated `pending` entry "stale (see _proposed_updates.md)".
D5-15 **Claims cl-4 (§12.4 for real).** Rewrite `kblib\claims.py` per design §12.1–12.7 with the REV5 extensions:
  version tokens extended (`v\d+\w*`, `A\d{1,2}`, `ca\d+(?:-\w+)?`, `D\d`, `E\d`, `P\d`, `off12`, `b12`, `branch_final`,
  model tokens `31B/12B/E4B/E2B`) via a builtin alias table + curated `run_labels.json` labels; F1/F1v/F2/F2b/F3/F4/F5
  (incl. `<version> @ 0.NN`, `scored 0.NN`, `= 0.NN (k/58)`)/F6/F9/F10 (`live-best`, `NEW PERSONAL BEST`, `BOARD
  BEST`); table types A/B/C incl. TOTAL rows; bar/unit/keyed classifier; ref binding (`ref \d{8}` on the same
  sentence binds an F5 to that exact submission — strongest evidence). Supersession: (1) cited `L\d+`/`line ~\d+`
  → containing unit; (2) heading `[RETRACTED …]`/`[CLAIM … WRONG, corrected …]` marks that unit superseded and links
  to the next unit whose heading has a correction stem and shares a version token or a ≥2-word heading phrase; (3)
  `CORRECTION/RETRACTION … ABOVE` → nearest earlier unit sharing a version token. Each claim records `chain`
  [unit ids, oldest→newest] and `superseded_by`. Status set: SUPPORTED / CONTRADICTED / UNVERIFIED / SUPERSEDED.
  Curated claims (`curated\claims.jsonl`) merge into `log_claims.md` §curated with their `status` and evidence.
D5-16 **Claims CLI filters work.** `claims --task/--version/--lever/--text/--status/--limit` filter for real, newest
  unit first, superseded marked.
D5-17 **Lever matrix (lv-1).** New `kblib\levers.py`; lexicon = `curated\lever_lexicon.json` if present else builtin
  `kblib\lever_lexicon_default.json` (code-owned; KB_SUMMARY names which). A lever instance = a config-field diff vs
  the run's parent (same kernel family/label lineage, previous run by date) or vs the track baseline config, plus
  lexicon hits in the log claims. KB_SUMMARY §6: one row per lever: versions/arms, stack+track, n runs, n distinct
  tasks, per-task outcome string, LB refs if any, latest log verdict (with supersession applied). n is always
  reported as `rows / distinct tasks` (anti n-inflation).
D5-18 **STANDING_TRUTHS.md (generated, idempotent).** ≤ 80 lines: Baselines & LB (from the submissions snapshot +
  banner), stack facts, closed/open lever axes, corrections (latest in each chain), each line `- [id] text —
  evidence: <path>:L<n> (<status>)`. Sources only: curated SUPPORTED claims, SUPPORTED non-superseded log claims of
  kinds verdict/standing-truth, the latest unit of each correction chain, builder-measured facts (gold coverage,
  dev-harness mismatch counts, pull attribution flags). Nothing invented.
D5-19 **Replay rp-5.** (a) gold-first records cached in `K\replays\gold\<task>.json` keyed by (engine_version, pins,
  required_mode, task_fingerprint, env) and REUSED on later `--replay` builds (fixes "cached --replay re-runs
  nothing"); (b) when gold has exit 0 / failed 0 / errors 0 but required nodes are SKIPPED, gold_first = `INFRA` with
  reason `required nodes skipped on this platform: <junit skip messages>` (was INVALID; both are excluded from
  counted replays, so no bar is weakened); JUnit skip messages are parsed into `skipped_names`/`skip_reasons`;
  (c) `--required-nodes added|hunk` flag (default `added` = current behaviour, byte-identical results): `hunk` adds the
  enclosing `def test_*` of every modified test_patch hunk (AST of the post-test_patch file in the worktree, line
  ranges from the hunk headers) — closer to HARNESS_README L609 "test functions extracted from test_patch"; it is
  stricter-or-equal (adds nodes, never removes any), recorded in the cache key; (d) NITs: `_run_git_env` routed
  through a new `gitio.git(..., extra_env=...)` so `add -N`/`diff` are allowlisted; dead `if False` branch deleted;
  `_PIN_FALLBACK` kept, now emits a `PIN-FALLBACK` warning into `build_log.txt`; (e) base-env evidence artifact:
  every replay/gold-gate session writes `K\replays\env_freeze_before.txt`, `env_freeze_after.txt` (`python -m pip
  freeze --all`, sorted) and `env_freeze_check.json {identical, n_before, n_after, python}` and fails the build
  (exit 4) if not identical.
D5-20 **Replay subcommands.** `B replay --task T (--run R | --candidate PATH | --gold) [--kind ...] [--force]
  [--required-nodes ...] [--deadline-s D] [--lock-wait-s W]` (design §15.1) and `B gold-gate --repo rich|fastapi
  [--tasks ...] [--deadline-s D] [--required-nodes ...]` (resumable; writes `replays\gold\<task>.json`; reuses
  goldgate_all.json only for the concordance report, never as a counted gold record).
D5-21 **Replay scope tiers** for `build --replay` (default scope `rich`): tier 0 curated min_set + all_runs rules;
  tier 1 Kaggle main-track rows with a trace; tier 2 Kaggle other tracks; tier 3 local-rig rows; sweep rows never.
  Within a tier: run_id sort. Only tasks whose gold_first is VALID-* get agent candidates; others record
  `gold_local=N/INFRA` without running. Bounded by `--deadline-s`; `replays_pending` reported; resumable via cache.
  `--replay-scope all` adds fastapi rows.
D5-22 **Gold coverage table.** Generated `K\replays\gold_coverage.json` + KB_SUMMARY §13a: one row per rich task (48)
  and each fastapi task attempted: rp-5 verdict, reason, pins+provenance, gold pass n, and concordance with
  `goldgate_all.json` and `_decode_sweep_cache\gold_gate.json` (agree/disagree/absent).
D5-23 **Required-node gap documentation.** KB_SUMMARY §13b lists every task whose `added_tests` is empty (whole-file
  fallback) with its test files and the count of test functions in modified hunks (from tasks.jsonl test_patch,
  static) — "the local bar differs from the harness for these tasks"; plus the `hunk`-mode result for the rich ones
  where it was run.
D5-24 **Scale guard.** Cross-task near-miss FP control uses a deterministic cap: for each trace, the other tasks are
  the 40 with the smallest sha256(task_id + other_id) among same-repo tasks (all if fewer). Recorded as
  `near_miss_fp.sampling = "hash-cap-40"`; bar unchanged (≤ 1 %). Rationale: ~2,200 traces × 129 tasks would cost
  minutes for a precision metric; the cap is deterministic so idempotence holds.
D5-25 **card is cost-aware.** `card --task T` prints a one-line summary per (stack, track, label) group (n rows,
  resolved, classes) then rows, with `--limit N` (default 40) and `--stack S`; `card RUN TASK` unchanged.
D5-26 **Gate builder** (`gemma-gate-builder` agent + `B gate-build` / `B gate-check`, new `kblib\gatebuild.py`):
  `gate-build --audit <final.md> --base <G-rel dir> --name <name> --change-spec <json>`: refuses unless the final
  report line 1 is `VERDICT: PROCEED`; refuses if `G\submit_<name>` exists; copies the base dir (shutil.copytree,
  excluding `out*`, `results`, `*.zip`, `__pycache__`, large binaries) into `G\submit_<name>`; writes
  `GATE_MANIFEST.json` (base path, base file hashes, created_utc, audit path, change-spec); applies the change-spec
  (a list of `{file, old, new}` exact single-occurrence replacements or `{file, replace_with_path}`) to files inside
  the NEW dir only; sets `kernel-metadata.json` id to `comfyops/gemma-gate-<name>` and refuses if that id equals any
  local kernel id; `gate-check --dir <new>` verifies: dir is in its own manifest, every changed file is declared in
  the change-spec (single-variable = exactly one logical change; >1 file only if the spec lists them under one
  `variable`), `_assemble.py` runs exit 0 (subprocess, cwd = new dir), `B leakcheck --scope config` clean on every
  changed text file + prompts, no base dir file mtime changed. It writes `GATE_PREREG.md` (change, bar, task set with
  difficulty classes from `G\RICH_48_DIFFICULTY_MAP.md`/tasks_gold mechanical difficulty, judge = FREE Kaggle gate)
  and prints the push command for the USER (`& "<kaggle.exe>" kernels push -p "G\submit_<name>"`) — it never runs
  it. `gatebuild.py` has its own write guard: writes only under the new dir it created. No code in kblib invokes
  `kernels push` (test-enforced).

---------------------------------------------------------------------------------------------------------------

## 2. Assumptions (recorded; challenge any of them)

- AS-1 "Last ~10 days" = everything newer than build stamp 2026-10-16T07:16:10Z (it is actually ~15 days to 2026-10-31).
- AS-2 `curated\lever_lexicon.json` is absent (MEASURED). A code-owned default lexicon is used and proposed for curation.
- AS-3 "No LOCAL 31B evaluation stack" means this PC. `colab_fasteval` (Colab, real 31B, dev harness with
  compaction 15) and `kaggle_pkg` full-129 kernels are separate stacks; the agent must label them, and treat Colab
  as a dev-internal hypothesis, never a judge. The coder verifies this wording against log L11961–L11997 and
  L12435–L12514 before writing the agent rule (targeted reads only).
- AS-4 Small-model (E2B/E4B) is a second prize track (log L13460ff, MEASURED text) → second baseline track.
- AS-5 Sweep patches without `--isolate` are untrusted; with it, trusted (log L12124ff).
- AS-6 requests/httpx clones exist but are NOT wired into replay this revision (scope; rich+fastapi only).
- AS-7 `goldgate_all.json` was produced by rp-4 via `local_eval\gold_gate_all.py`; it is reused for the coverage
  concordance; rp-5 re-runs gold-first per task (≈ 50 min total for 48 rich, MEASURED secs) because counted replays
  need `gold_pass_tests`, which goldgate_all lacks. Fastapi gold-gate is attempted bounded by one `--deadline-s 1800`
  run; unfinished tasks are reported "not run (deadline)".
- AS-8 `kernels output --file-pattern` existence is checked at runtime (`kernels output --help` to a file); deletion
  sweep runs regardless.
- AS-9 Pull is capped at `--max 12` slugs per invocation; scored-ref producers first. More slugs → report the rest
  as "pull targets not fetched (cap)".
- AS-10 The log's 0.20 live-best is UNVERIFIED until the pulled snapshot; never adopted; reported as BASELINE CONFLICT
  if confirmed.
- AS-11 `G\kb_query.py` is read-only (MEASURED: SELECT-only over `EXPERIMENT_KB.sqlite`); agents may use
  `python G\kb_query.py search "<terms>"` as a cheap log index but must verify any hit against the log text. `G\build_kb.py`
  (the user's) must NEVER be run by agents (writes `G\EXPERIMENT_KB.sqlite`).
- AS-12 A full `build --replay` over ~2,000 new rich rows may take several hours; it is run as repeated bounded
  builds (`--deadline-s 1700`) in the background until `replays_pending=0`, or the remaining pending count is
  reported as a gap. Each bounded run is resumable through the cache.
- AS-13 Gate-builder needs shell (to run `_assemble.py` and `leakcheck`); Kiro frontmatter has no per-command
  allowlist (design §17: only name/description/tools/welcomeMessage). The push prohibition is enforced by the agent
  text, by `gate-build`/`gate-check` never invoking kaggle, and by a static test. Residual risk: an LLM with shell
  could still type a push; stated in the agent file and in the final report.
- AS-14 The frozen base for a gate is the dir named in the PROCEED bar (`bar.base_dir`), else
  `run_labels.json:baseline.gate_base_dir` (proposed new curated field), else the gate-builder refuses (NEEDS-BASE);
  it never guesses. For the 0.20 ca5 pack the scored files are in `local_eval\pull_packager_ca5_out\submission\`;
  `gate-check` compares the clone's agent package hashes to the baseline package when one is named.
- AS-15 KB size: runs.jsonl may grow to ~8–10 MB (≈ 3,000 rows). Acceptable (single file, skip-identical writes).

---------------------------------------------------------------------------------------------------------------

## 3. REVISION 5 section — the coder appends this text VERBATIM to the end of
## `ROOT\.kiro\specs\gemma-auditor\design.md` (FEAT-001 step 1). Do not edit anything above it.

```markdown

---

## REVISION 5 (2026-10-31) — absorb 15 days of new work; finish the deferred pieces; agents v2

Status: approved by the kb-rev5 planning step. REVISION 4 stays in force except where this section amends it.
Engines after this revision: fc-3 (unchanged), nm-3 (+ hash-cap FP sampling), cm-2, rp-5, cl-4, lv-1, dh-1.

### R5.1 Why
Between the 2026-10-16 build and 2026-10-31 the log grew 10,108 → 14,554 lines and four new run stacks appeared
(Kaggle full-129 eval kernels, the local parity rig, local sweeps, Colab). The scored baseline moved on the board
(per the log, unverified until pulled). The REV4 builder would mis-file the new runs (kaggle_pkg logs carry no
`resolved=` lines; rig traces are not under `results\`), pool stacks and tracks, and its recipe calls a `replay`
subcommand that does not exist.

### R5.2 Row identity: stack and track (replaces `out_of_scope`)
Every `runs.jsonl` row gains `stack {platform, scorer, model_declared, model_served_verified}`, `track
(main|small-model|dev-proxy)`, `run_kind (kaggle-kernel|kaggle-pulled|kaggle-pulled-legacy|local-rig|local-sweep|
pasted-log)`, `arm`, `rep`, `config_confidence`, `dev_harness`, `patch_trusted`. Matrices, levers and variance are
computed per track; KB_SUMMARY never pools tracks. `model_served_verified` is false for rig and sweep rows.

### R5.3 Discovery kinds (amends §5)
New kinds: `rig-run` (dir with `traces\` + `task_results.jsonl`), `kaggle-eval-run` (JSON kernel log +
`results\task_results.jsonl`, no `resolved=` lines), `sweep-tag` (one per `<tag>` in `local_eval\runs`), `pulled-run`
(`kb\pulled\<slug>\<utc>\`), `pulled-legacy` (a `kb\pulled\` run dir without `_pull_meta.json`), `staged-submission`
(D3-4, with config + zip drift), `scored-zip` (a `submission.zip` with `submission\` beside it, e.g.
`pull_packager_*_out`), `submission-zip-archive` (`local_eval\pull_submissions\*.zip`), `lb-snapshot`
(`local_eval\leaderboard\lb.csv`), `foreign-tool` (`G\build_kb.py`, `G\kb_query.py`, `G\EXPERIMENT_KB.sqlite`),
`reference-kernel` (non-comfyops kernel dirs), `partial` (`*.partial`). Submit-dir = any `comfyops/` kernel dir, with
`kernel_family`. Outcome priority: kernel-log `resolved=` → `task_results.jsonl` → sweep pinned → sweep raw;
`summary.json` only raises `summary_disagrees`. KB_SUMMARY §2 adds "Since the previous build (2026-10-16T07:16Z)"
listing every new/changed source with parsed yes/no and the reason, and the log's new `##` units by line range.

### R5.4 Configs (amends §6.3; closes D3-4 and D3-5)
Config priority: `submission\` → single `agent_*\` child → rig `parity_rig\agent_<arm>`/`agent_ctrl_<arm>` → sweep
guard cmd flags → none. Staged submissions get `zip_drift MATCH|DRIFT(files)|NO_ZIP` vs the sibling
`submission.zip` (read with `zipfile`, never extracted to disk). Dev-harness pass `kblib\devharness.py` (dh-1):
`ast.parse` of `notebook_src.py` and every `.ipynb` code cell (IPython magics blanked), keyword constants of
`EventsCompactionConfig(...)` and `ContextCacheConfig(...)` via `ast.literal_eval`; comments and strings are never
read as config. Scorer reference: HARNESS_README §"Events Compaction" (`compaction_interval = 5`, `overlap_size =
2`, `token_threshold = 14,336`). Per run `dev_harness.matches_scorer`. Each differing field is a lever instance.

### R5.5 Kaggle pulls (replaces §14 layout; §14 rules otherwise stand)
`kblib\kaggle.py`, invoked only by `build_kb.py pull`. Allowed argv: `competitions submissions
gemma-4-developer-agent --csv`; `kernels list --mine --csv --page-size 200`; `kernels output --help`; `kernels
output comfyops/<slug> -p <dir> [--file-pattern <re>]`; `kernels pull comfyops/<slug> -p <dir> -m`. Never `push`.
Layout: `kb\pulled\<slug>\<pull-utc>[.partial]\` with `_pull_meta.json {slug, pull_utc, argv, exit, output_text,
files, deleted, latest_only: true, submission_config, attribution}`; submissions → `kb\pulled\submissions\
<pull-utc>.csv` (+`.meta.json`). Large binaries (`.safetensors` > 50 MB, `.bin`, `.gguf`, `.pt`, `.pth`) are deleted
after download and listed. Attribution: every output pull is `latest-at-pull`; the build compares the pulled config
with each submission mapped to the pulled label (and the local submission zip when present):
`ATTRIBUTION-CONFIRMED` (hash-equal), `ATTRIBUTION-MISMATCH` (any stated config fact differs; e.g. the legacy
`v6w_temp1_probe` output is temperature 0.2 vs ref 57201051's temperature 1.0), else `ATTRIBUTION-UNVERIFIED`. A
mismatching pull never explains that ref. Targets: producers of scored refs without local output, then log versions
with a kernel id but no local run; `--max` bounds a run (default 12).

### R5.6 LB source, baselines, banner (amends §12.4 "External LB source", D3-3)
The builder uses the newest `kb\pulled\submissions\*.csv` newer than `curated\submissions.csv`, else curated, and
names it. Baselines per track: main = `curated\run_labels.json:baseline`; small-model = none curated yet. The banner
is computed from the steering file's own text (`**<label> @ <score> is SACRED` + ref) compared with the curated
baseline and with the best COMPLETE main-track / small-model score in the LB source. Any disagreement prints
`BASELINE CONFLICT: steering=<..> curated=<..> lb_best=<..> (source <csv>)`; nothing is adopted. Stale curated
entries (e.g. `run_labels.json.pending[branch_final]` while the LB source shows ref 57146757 COMPLETE 0.12) are
rendered as stale and proposed in `kb\curated\_proposed_updates.md`, the only builder-written path under `curated\`.
The steering file joins the input fingerprint.

### R5.7 Claims cl-4 (implements §12.1–12.7; extends tokens and supersession)
Implements the full column mapping, table types A/B/C (incl. TOTAL rows), the bar/unit/keyed F1 classifier and
F1–F10 as specified in §12.4, plus: extended version tokens (`A\d{1,2}`, `ca\d+`, `D\d`, `E\d`, `P\d`, `off12`, `b12`,
model tokens) with a builtin alias table; `ref \d{8}` binds an F5 to that exact submission; F5 also reads `=
0.NN (k/58)` and `scored 0.NN`; F10 also reads `NEW PERSONAL BEST` / `BOARD BEST`. Supersession: cited lines;
heading tags `[RETRACTED …]` / `[CLAIM … WRONG, corrected …]`; `CORRECTION … ABOVE` → nearest earlier unit sharing a
version token. Each claim carries `chain` and `superseded_by`; status adds `SUPERSEDED`. Curated claims merge into
`log_claims.md`. `claims` CLI filters (`--task --version --lever --text --status --limit`) are implemented.

### R5.8 Levers lv-1 (implements §12.8)
`kblib\levers.py`; lexicon = curated `lever_lexicon.json` if present, else code-owned
`kblib\lever_lexicon_default.json` (named in KB_SUMMARY; proposed for curation). Instances = config diffs vs the
run's lineage parent or the track baseline, dev-harness diffs, and lexicon hits in claims. KB_SUMMARY §6 per lever:
labels/arms, track, stack, rows/distinct-tasks, per-task outcomes, LB refs, latest non-superseded log verdict.

### R5.9 Replay rp-5 (amends §13)
Gold-first records are cached and reused (key: engine, pins, required_mode, task fingerprint, env). Gold with exit 0
/ 0 failed / 0 errors whose required nodes are skipped → `INFRA (required nodes skipped on this platform: …)`.
`--required-nodes added|hunk` (default `added`, byte-identical to rp-4 judging); `hunk` adds enclosing test
functions of modified test_patch hunks (never removes a node). All git calls go through `gitio.git` (incl. `add
-N`/`diff` with excludes env). Every replay session writes `replays\env_freeze_{before,after}.txt` +
`env_freeze_check.json`; a difference fails the command (exit 4). New subcommands `replay` (§15.1 contract) and
`gold-gate`. `build --replay` scope tiers: min-set → Kaggle main → Kaggle other → local-rig; sweep never; `--replay-scope
all` adds fastapi. `replays\gold_coverage.json` + KB_SUMMARY §13a (all 48 rich + attempted fastapi, with
concordance against `goldgate_all.json` and the decode-sweep cache) and §13b (tasks on the whole-file fallback).

### R5.10 STANDING_TRUTHS.md (new generated file)
≤ 80 lines, each `- [id] statement — evidence: <path>:L<n> (<status>)`, sections Baselines/LB, Stacks, Closed axes,
Open axes, Corrections. Sources: curated SUPPORTED claims, SUPPORTED non-superseded log verdicts, the newest unit of
each correction chain, builder-measured facts. Idempotent; part of `generated_files`.

### R5.11 Agents and recipe
`gemma-auditor.md` v2 (same name/frontmatter/tools) adds the hard-won rules (no local 31B stack; identify the config
behind every LB number; reject true-by-construction signals and n-inflation; standing facts; cost discipline: load
STANDING_TRUTHS.md + KB_SUMMARY.md first, use `card`/`claims`/`kb_query.py search`/offset reads, never whole traces
or the whole log). `gemma-gate-builder.md` (new) turns a PROCEED final report into a ready-to-push FREE gate dir via
`B gate-build`/`B gate-check`; it may CREATE `G\submit_<name>\` only, never modifies an existing `submit_*`, never
runs kaggle. The recipe keeps its four steps, inputs, refute-on-other-family and mechanical stricter-of-two final;
prompts reference STANDING_TRUTHS.md and cost discipline; rebuild step effort low.

### R5.12 Acceptance (REV5)
Two plain builds byte-identical except the stamp; a second cached `build --replay` runs 0 candidates and 0 gold
controls; clones clean; base env freeze identical; `python -m pytest tests -q` green (old + new); `B check-fresh`
exit 0 after build; recipe + both agents statically valid; no `kernels push` string reachable in kblib code paths.
```

---------------------------------------------------------------------------------------------------------------

## 4. Ordered implementation items

Order is by dependency: FEAT-001 (items 1–6) → FEAT-002 (items 7–10) → FEAT-003 (items 11–14) → FEAT-004
(items 15–20) → FEAT-005 (items 21–26). Every item leaves the builder runnable. Verify with the project's real
commands: `python -m pytest tests -q` (cwd K), `B build`, `B check-fresh`, `python K\tests\idempotence_check.py`.

### FEAT-001 — Discovery, ingestion of the new stacks, D3-4, D3-5, coverage-since-last-build

- [ ] 1. Append the REVISION 5 section (§3 above) verbatim to the end of `ROOT\.kiro\specs\gemma-auditor\design.md`.
      Files: `ROOT\.kiro\specs\gemma-auditor\design.md` (append only).
      Verify: `python -c "t=open(r'c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\.kiro\specs\gemma-auditor\design.md',encoding='utf-8').read();assert t.count('## REVISION 5')==1 and 'REVISION 4' in t"` exits 0.

- [ ] 2. Extend discovery (D5-3, D5-5, R5.3): new kinds `rig-run`, `kaggle-eval-run`, `sweep-tag`, `pulled-run`,
      `pulled-legacy`, `scored-zip`, `submission-zip-archive`, `lb-snapshot`, `foreign-tool`, `reference-kernel`,
      `partial`; submit-dir = any `comfyops/` kernel id with `kernel_family`; `local_eval\runs\` grouped per tag (not
      per file); skip `*.partial` dirs; `discover()` returns new lists `rig_runs`, `eval_runs`, `sweep_tags`,
      `pulled_runs`, `scored_zips`. Keep the `_skip_dir` rules (still skip `local_eval\repos`, `.git`, `kb\` except
      `kb\pulled` and `kb\replays\manual`). Add `.kiro\steering\gemma-submission-protocol.md` and all new outcome/
      config files to `input_fingerprint` extra files.
      Files: `K\kblib\discover.py`, `K\kblib\paths.py` (add `STEERING_PROTOCOL`, `RIG_ROOT`, `SWEEP_ROOT` constants),
      `K\tests\test_unit.py` (synthetic tmp G trees: a rig rN dir, a kaggle-eval dir with task_results.jsonl and a
      JSON log lacking `resolved=`, a sweep tag with guard/results/pinned, a `.partial` dir, a packager kernel dir).
      Verify: `python -m pytest tests -q -k discover` passes; existing 47 still pass.

- [ ] 3. Row production for the new kinds (D5-1, D5-2, D5-3, D5-4): in `build_kb.py cmd_build`, generalise the per-run
      loop to a source adapter per kind (kaggle-kernel, kaggle-eval-run, rig-run, sweep-tag, pulled-run/legacy,
      pasted-log). New module `K\kblib\sources.py` with `outcomes_from_task_results(path)`,
      `sweep_rows(tag_files)` (pinned > raw; `patch_trusted` from guard `--isolate`; config from guard flags),
      `rig_arm_config(g, arm)`, `agent_dir_config(run_dir)` (single `agent_*\` child), `stack_and_track(...)`.
      `_run_dir_trace_map` must accept `traces\` directly under the run dir. Rows gain `stack`, `track`, `run_kind`,
      `arm`, `rep`, `config_confidence`, `patch_trusted`, `summary_disagrees`. `configs.extract_config` gains the
      `agent_*` and arm-dir sources (no behaviour change for `submission\`). Classify still runs (fc-3 unchanged).
      Files: `K\kblib\sources.py` (new), `K\build_kb.py` (cmd_build loop, `_run_dir_trace_map`, `_submission_dir`,
      `_label_for` for new families per D5-5), `K\kblib\configs.py`, `K\tests\test_unit.py`.
      Verify: `B build *> $env:TEMP\b1.txt` exits 0 and prints `BUILD OK`; `python -c` over `K\runs.jsonl` shows rows
      for `kaggle_pkg/out_v7` (129, outcome from task_results), `local_eval/parity_rig/m1_full129/ca5` (129,
      run_kind local-rig, track per declared model, model_served_verified false), and sweep tags with
      `patch_trusted` set; `python -m pytest tests -q` passes.

- [ ] 4. Staged submissions + zip drift (D5-7, D3-4): config fields for `staged_submissions` and `scored_zips`;
      `zip_drift` via stdlib `zipfile` (read members in memory; never extract). Render under KB_SUMMARY §2.
      Files: `K\kblib\configs.py` (`zip_drift(dir)`), `K\build_kb.py` (`_coverage_lines`), `K\tests\test_unit.py`
      (tmp dir + zip with one drifted file → `DRIFT(['prompts/system.md'])`).
      Verify: `python -m pytest tests -q -k zip_drift` passes; after `B build`, KB_SUMMARY §2 shows
      `submit_t4096` and `submit_branch_final` with a zip_drift value and config one-liner.

- [ ] 5. Dev-harness AST pass (D5-8, D3-5): new `K\kblib\devharness.py` (`scan_dir(dir) -> dict|None`,
      `scorer_reference(readme_path) -> dict`); never `exec`/`eval`/`compile(...,'exec')`, only `ast.parse` +
      `ast.literal_eval` on keyword values. Attach `dev_harness` to every row whose run dir (or nearest ancestor
      submit/push dir, or the kernel dir that owns the pulled slug) has a notebook. KB_SUMMARY §9 adds the scorer
      value (5) and counts of runs matching / not matching / unknown.
      Files: `K\kblib\devharness.py` (new), `K\build_kb.py` (`_harness_lines`), `K\tests\test_unit.py`
      (a notebook JSON with `EventsCompactionConfig(compaction_interval=15, ...)` in a cell and a comment
      `# compaction_interval=5` → 15 read, comment ignored; source scan asserts no exec/eval).
      Verify: `python -m pytest tests -q -k devharness` passes; after `B build`, `runs.jsonl` rows for
      `submit_v6w/out_v6w` carry `dev_harness.compaction_interval == 15` and `matches_scorer == false`.

- [ ] 6. Coverage-since-last-build + scale guard + cost-aware card (D5-6, D5-24, D5-25): constant
      `REV5_PRIOR_BUILD_UTC = "2026-10-16T07:16:10Z"` in `build_kb.py`; KB_SUMMARY §2 "Since the previous build"
      table (sources with mtime > constant: kind, path, parsed, reason) + the log's `##` units with first line >
      10108 (count + first/last line); near-miss FP hash-cap-40 in `nearmiss.cross_task_fp` (record `sampling`);
      `card --task T [--limit N] [--stack S]` group summary.
      Files: `K\build_kb.py`, `K\kblib\nearmiss.py`, `K\tests\test_unit.py` (FP sampler deterministic; card
      grouping on a 3-row synthetic runs file).
      Verify: two consecutive `B build` + `python K\tests\idempotence_check.py snapshot $env:TEMP\i1.json` /
      `... i2.json` / `compare` → `IDENTICAL`; `B check-fresh` exit 0; build duration recorded in
      `build_stamp.json` (target < 900 s without replay); `python -m pytest tests -q` passes.

### FEAT-002 — Real `pull`, submissions snapshots, baselines per track, banner, curated proposals

- [ ] 7. Implement `K\kblib\kaggle.py` (D5-9): `KAGGLE_EXE` constant, `_ALLOWED` argv validator (exact patterns;
      slug `^comfyops/[a-z0-9][a-z0-9-]*$`, no `/N`), `run(argv, out_file)` via `subprocess.run(list, stdout=fh,
      stderr=STDOUT, env=os.environ|{PYTHONUTF8:1,PYTHONIOENCODING:utf-8})`, `pull_submissions()`, `list_mine()`,
      `pull_output(slug)` (.partial → rename; `kernels pull -m` into `source\`; delete-large sweep;
      `_pull_meta.json`), `has_file_pattern()` (reads `kernels output --help` output). Writes go through
      `io.safe_write` (pulled/ prefix) or `pathlib` inside the `.partial` dir created by this process only.
      `cmd_pull` in build_kb.py: `--slug` (repeatable), `--submissions`, `--targets`, `--max 12`, `--force`,
      `--dry-run`, `--for-ref R`; exit 0 ok / 6 CLI failure / 1 bad args.
      Files: `K\kblib\kaggle.py` (new), `K\build_kb.py` (`cmd_pull`, parser), `K\tests\test_unit.py`
      (validator rejects `kernels push ...`, `/3` suffix, foreign owner; `--dry-run` prints argv without running;
      source scan: the string `push` never appears in an allowed argv template).
      Verify: `python -m pytest tests -q -k kaggle` passes; `B pull --submissions --dry-run *> $env:TEMP\p.txt` prints
      the exact argv and exits 0 with no network.

- [ ] 8. Attribution + mismatch flag + pull targets (D5-10, D5-11): `kblib\attribution.py`:
      `description_facts(desc)` (F4 patterns), `zip_hashes(path)`, `attribute(pulled_cfg, refs, local_zips)`;
      `pull_targets(g, snapshot_rows, kernels_list)`. The build attaches `attribution` to `pulled-run` and
      `pulled-legacy` rows and renders KB_SUMMARY §7 "Pulled outputs vs submissions".
      Files: `K\kblib\attribution.py` (new), `K\build_kb.py`, `K\tests\test_unit.py` (unit: pulled temp 0.2 vs
      desc "temperature 1.0 / top_k 64" → MISMATCH on temperature).
      Verify: `python -m pytest tests -q -k attribution` passes; after `B build`, the `K\pulled\v6w_temp1_probe`
      rows show `ATTRIBUTION-MISMATCH` for ref 57201051 (slow test `test_rev5_legacy_pull_mismatch` in
      `K\tests\test_slow_facts.py`).

- [ ] 9. Submissions source selection + baselines per track + banner from steering text + proposals (D5-12, D5-13,
      D5-14): replace `_baseline_banner` with `kblib\baseline.py` (`steering_baseline(path)`, `lb_source(kb)`,
      `track_best(rows)`, `banner(...)`, `proposed_updates(...) -> markdown`). Add exact path
      `curated/_proposed_updates.md` to `io._ALLOWED_GENERATED` and make `_check_allowed` accept that exact file
      before the protected-dir check (and ONLY that file — unit test proves `curated/claims.jsonl` still raises).
      `_lb_lines` renders refs, status, scores, branch_final from the LB source (COMPLETE 0.12), and the curated
      `pending` entry as stale.
      Files: `K\kblib\baseline.py` (new), `K\kblib\io.py`, `K\build_kb.py` (`_baseline_banner`, `_lb_lines`,
      generated_files), `K\tests\test_unit.py` (banner with steering text "v6w @ 0.15 is SACRED" + curated v6w + LB
      best 0.20 → contains `BASELINE CONFLICT` and never the word STALE about steering; safe_write allows only the
      one curated file).
      Verify: `python -m pytest tests -q` passes; `B build`; KB_SUMMARY line 3 is computed (no hardcoded "v6 @
      0.12 … STALE"); `K\curated\_proposed_updates.md` exists and proposes the branch_final correction.

- [ ] 10. Run the real pull (network, read-only): `B pull --submissions *> $env:TEMP\ps.txt`; `B pull --targets --dry-run`
      (record targets); `B pull --targets --max 12 *> $env:TEMP\pt.txt` (background process, poll the file; timeout
      per slug 600 s). Then `B build`. Record in `T\features\FEAT-002.json.findings`: snapshot path, newest refs and
      scores, live-best per track, conflicts, slugs pulled, attribution flags, deleted binaries, targets not
      fetched. Never `kernels push`, never submit.
      Files: generated only (`K\pulled\...`, KB outputs).
      Verify: `K\pulled\submissions\<utc>.csv` exists; `B build` exit 0; KB_SUMMARY §7 names that csv as the LB
      source; `B check-fresh` exit 0.

### FEAT-003 — Claims cl-4, claims CLI, lever matrix lv-1, STANDING_TRUTHS.md

- [ ] 11. Rewrite `K\kblib\claims.py` to cl-4 (D5-15, §12.1–12.7): segmentation (`##` units + `###` heading blocks),
      version tokens + builtin aliases (+ labels from runs), table types A/B/C + TOTAL rows + cell grammar,
      F1/F1v/F2/F2b/F3/F3t/F4/F5/F6/F9/F10 with the bar/unit/keyed classifier, ref binding, attribution + run binding
      (by `version_label`, `arm`, kernel label; per track), statuses incl. SUPERSEDED, supersession chains, curated
      merge. Keep `extract(...)` signature but pass the LB source rows from item 9 and the runs rows.
      Files: `K\kblib\claims.py`, `K\build_kb.py` (`_claims_summary`, `_log_claims_md`), `K\tests\test_claims.py`
      (new; content-anchored real-log tests per §12.4 list, each locating its line by content, plus REV5 cases:
      `ca5-31B scored 0.20` → F5 0.20 bound to ca5 SUPPORTED iff the LB source has it; the B_temp1 entry `ref 57201051
      … = 0.13` → F5 bound to ref; `Bar for v4: >=2/6` → bar, not outcome; `0/6 resolved but 6/6 BANKED` → only 0/6;
      the `[RETRACTED same day …]` D-ARMS heading → SUPERSEDED with a chain to the 2026-10-21 CORRECTION unit).
      Verify: `python -m pytest tests -q -k claims` passes; after `B build`, `log_claims.jsonl` has > 78 claims and
      a non-zero count of auto-checked facts; KB_SUMMARY §8 shows counts by status.

- [ ] 12. Implement the `claims` CLI filters (D5-16): `--task`, `--version`, `--lever` (lexicon id or text), `--text`
      (regex over heading+facts), `--status`, `--limit` (default 50); newest unit first; superseded marked.
      Files: `K\build_kb.py` (`cmd_claims`), `K\tests\test_unit.py` (synthetic log_claims.jsonl).
      Verify: `python -m pytest tests -q -k cmd_claims` passes; `B claims --version ca5 --limit 5 *> $env:TEMP\c.txt`
      prints only ca5-bound claims.

- [ ] 13. Lever matrix lv-1 (D5-17, D5-8 lever instances): `K\kblib\levers.py`, `K\kblib\lever_lexicon_default.json`
      (ids + regexes + config field mapping for: max_tool_calls, max_time_minutes, max_turns, timeout_seconds,
      thinking_budget, temperature, top_k, top_p, max_output_tokens, frequency_penalty, tools surface, sub-agents/
      router, adapter/LoRA, prompt rules (anchor-grep, delimiter fix, apply-as-you-go, locate numeral, verify rule,
      compliance salience, patch_size), model size, dev-harness compaction_interval). `_lever_lines` renders §6 per
      track with rows/distinct-tasks. Propose the default lexicon in `_proposed_updates.md` (item 9 helper).
      Files: `K\kblib\levers.py` (new), `K\kblib\lever_lexicon_default.json` (new), `K\build_kb.py`
      (`_lever_lines`), `K\tests\test_unit.py` (two synthetic runs differing only in temperature → one lever
      instance `temperature`, n rows/distinct tasks correct).
      Verify: `python -m pytest tests -q -k lever` passes; after `B build`, KB_SUMMARY §6 lists ≥ 10 levers, each with
      a `rows/distinct` figure.

- [ ] 14. STANDING_TRUTHS.md (D5-18): `K\kblib\standing.py` `render(curated, claims, baseline_info, gold_cov,
      devharness_counts, attributions) -> str`; register in `io._ALLOWED_GENERATED` and `generated_files`.
      Files: `K\kblib\standing.py` (new), `K\kblib\io.py`, `K\build_kb.py`, `K\tests\test_unit.py` (every line has
      `evidence:`; ≤ 80 lines; deterministic).
      Verify: `B build` twice + idempotence compare `IDENTICAL` (now including STANDING_TRUTHS.md);
      `python -m pytest tests -q` passes.

### FEAT-004 — Replay rp-5, `replay` + `gold-gate` subcommands, gold coverage, scorer-parity gap, NITs, run it

- [ ] 15. NITs + git routing (D5-19d): add `extra_env` param to `gitio.git`; replace `_run_git_env` calls in
      `replay._candidate_diff` with `gitio.git(wt, "add", "-N", ".", scope="worktree", eol=True, odb=..., alt=...,
      extra_env=env_excl)` and the same for `diff --binary` (bytes: add `binary=True` option returning bytes); delete
      `_run_git_env` and the dead `if False` statement; `_PIN_FALLBACK` path appends a `PIN-FALLBACK <task>` warning
      that `build_kb.py` writes into `build_log.txt` (sorted). Bump `RP_VERSION = "rp-5"`.
      Files: `K\kblib\gitio.py`, `K\kblib\replay.py`, `K\tests\test_unit.py` (`test_gitio_allowlist_exact_set`
      updated only if the set changes — it must not; `test_replay_no_mutating_git_verbs_in_source` still passes; new
      test: `replay.py` source has no `subprocess.run(` with `"git"` outside gitio and no `if False`).
      Verify: `python -m pytest tests -q` passes; `python K\kblib\_selftest_pins.py` prints `PIN SELFTEST OK`.

- [ ] 16. rp-5 judging extensions (D5-19a,b,c): gold-first cache read/write in `replays\gold\<task>.json` with key
      fields; skip-reason parse in `_parse_junit` (`skipped_names`, `skip_reasons` from `<skipped message=...>`);
      INFRA-for-platform-skip rule in `gold_first`; `required_mode` param threaded through `run_candidate` →
      `_required_tests(gt, wt, mode)` (`added` = current; `hunk` = added ∪ enclosing `def test_*` of modified hunks,
      via `unidiff` hunk ranges + `ast.parse` of the post-test_patch file in the worktree); cache key includes
      required_mode; base-env freeze artifacts written at engine enter/exit (`python -m pip freeze --all` to the two
      files via `io.safe_write`; `env_freeze_check.json`); mismatch → raise → exit 4.
      Files: `K\kblib\replay.py`, `K\kblib\unidiff.py` (expose hunk new-side ranges if missing), `K\build_kb.py`
      (`_run_replays` uses cached gold; exit 4 on freeze mismatch), `K\tests\test_unit.py` (junit with a skipped
      required node → INFRA reason contains the skip message; `hunk` mode on a synthetic test_patch modifying the body
      of `test_b` adds `test_b`, never drops an `added` node; `added` mode returns exactly the rp-4 list).
      Verify: `python -m pytest tests -q` passes; `python K\kblib\_selftest_pins.py` OK.

- [ ] 17. `replay` and `gold-gate` subcommands + scope tiers (D5-20, D5-21): `cmd_replay` per design §15.1 (takes the
      lock; gold/base controls first if not cached; prints result lines; updates `replays.jsonl`); `cmd_gold_gate
      --repo rich|fastapi [--tasks ...] [--deadline-s D] [--required-nodes ...]` (resumable through the gold cache;
      CloneGuard around it; prints one line per task); `build --replay-scope min|rich|all` (default rich) with tier
      ordering; non-VALID gold → no agent candidate run.
      Files: `K\build_kb.py` (`cmd_replay`, `cmd_gold_gate`, `_run_replays` tiers, parser), `K\tests\test_unit.py`
      (parser accepts the §15.1 options; tier ordering on synthetic rows; `--replay-scope min` = min set only).
      Verify: `python -m pytest tests -q` passes; `B replay --task rich_4079 --gold *> $env:TEMP\r.txt` exits 0 and
      reports `VALID-HARNESS-LIKE` (cached rp-5 record written).

- [ ] 18. Gold coverage + required-node gap docs (D5-22, D5-23): `kblib\goldcov.py` builds
      `replays\gold_coverage.json` from `replays\gold\*.json` + concordance with `replays\goldgate_all.json` and
      `audits\_decode_sweep_cache\gold_gate.json` (read-only); KB_SUMMARY §13a/§13b.
      Files: `K\kblib\goldcov.py` (new), `K\build_kb.py` (`_replay_lines`), `K\tests\test_unit.py`.
      Verify: `python -m pytest tests -q` passes; `B build`; KB_SUMMARY §13a lists 48 rich rows.

- [ ] 19. Run gold-first for real (base env untouched): `B gold-gate --repo rich --deadline-s 1750 *> $env:TEMP\gg.txt`
      as a background process, polling the file, re-launching until all 48 rich tasks have an rp-5 record (≈ 50 min
      MEASURED in rp-4); then `B gold-gate --repo rich --tasks <the whole-file-fallback rich tasks> --required-nodes
      hunk` (records the hunk-mode verdicts separately; default stays `added`); then `B gold-gate --repo fastapi
      --deadline-s 1800` once (AS-7). Expected for the 4 Windows-skip tasks: INFRA with the skip messages (the log's
      L10242ff explanation, now MEASURED by the engine). Record per-task results in FEAT-004 findings.
      Verify: `K\replays\gold_coverage.json` has 48 rich rows with rp-5 verdicts; `env_freeze_check.json.identical ==
      true`; `git -C G\local_eval\repos\rich status --porcelain` and `...\fastapi status --porcelain` empty (write
      them to `K\replays\clone_status_final.txt`).

- [ ] 20. Replay all new rows' candidates gold-first: `B build --replay --deadline-s 1700 --lock-wait-s 120
      *> $env:TEMP\br.txt` repeatedly (background; poll) until `replays_pending=0` or a stated stop (report the
      pending count and tiers left). Then a second cached `B build --replay` must report `replays_run_this_build=0`
      and 0 gold controls run; then two plain builds + idempotence compare.
      Verify: `build_stamp.json.replays_run_this_build == 0` on the cached rerun; idempotence `IDENTICAL`;
      `clone_state.json.verdict == "CLEAN (no builder-attributable change)"`; `B check-fresh` exit 0;
      `python -m pytest tests -q` passes.

### FEAT-005 — Agents, recipe, gate builder, tests, verification record

- [ ] 21. Gate-builder tooling (D5-26): `K\kblib\gatebuild.py` (`build_gate(audit, base, name, spec)`,
      `check_gate(dir)`, own write guard: only inside the dir it created; refuses existing targets; never imports
      kaggle.py; prints but never runs the push command); `cmd_gate_build`, `cmd_gate_check` in build_kb.py.
      Files: `K\kblib\gatebuild.py` (new), `K\build_kb.py`, `K\tests\test_gatebuild.py` (new; uses `GKB_GEMMA_ROOT`
      tmp tree: refuses non-PROCEED audit; refuses existing `submit_<name>`; refuses kernel id collision; refuses a
      spec touching an undeclared file; creates a dir with GATE_MANIFEST.json + GATE_PREREG.md; base dir files'
      mtimes unchanged; source has no `subprocess` call whose argv contains `kaggle`).
      Verify: `python -m pytest tests -q -k gatebuild` passes.

- [ ] 22. Rewrite `ROOT\.kiro\agents\gemma-auditor.md` (keep `name: gemma-auditor`, the 4 frontmatter keys, `tools:
      [read, write, shell]`). Update KB layout/CLI to exactly what is built (new files: STANDING_TRUTHS.md,
      gold_coverage.json, pulled\, _proposed_updates.md; new CLI: replay, gold-gate, pull options, claims filters,
      card --limit/--stack, gate-build/gate-check (auditor never uses gate-*)). Add sections: "Standing rules (hard
      checks)" with each brief bullet as a numbered rule (no local 31B stack → NEEDS-DATA for bars needing a local
      31B agent run; FREE Kaggle rich gate is the first trustworthy judge; Colab/rig/sweep are dev-internal; identify
      the config behind every LB number from the submission description + pulled `submission\` + attribution flag
      — the 0.13 = temp 1.0/top_k 64 lesson; reject true-by-construction signals; report rows/distinct tasks (34 rows =
      10 tasks lesson); standing facts list incl. J-subagents-regress, v2_gate_out vs v2_gate_out2 410-module A/B,
      v2 over-strong not inert, WRONG-FIX is fix-content, reviewer/critic ~0.7 % addressable, LB facts only from
      submissions, `kernels output` latest-only, leakcheck clean with no bare task ids in config/prompt text,
      `train_lora.py --maxlen` ≥ 8192; track awareness main vs small-model; never run `G\build_kb.py`); "Cost
      discipline" (load `K\STANDING_TRUTHS.md` then `K\KB_SUMMARY.md` first; `B card --task T --limit`, `B claims
      ...`, `python G\kb_query.py search "<terms>"` then targeted `Select-String`/offset reads of the log; open raw
      traces only for the step_ids that decide a claim; never read a whole multi-MB trace or the whole log; report
      evidence-dense, ≤ ~400 lines). Verify each standing fact against its source before writing it (curated
      claims.jsonl ids; log lines via targeted grep) and cite the source inline.
      Files: `ROOT\.kiro\agents\gemma-auditor.md`.
      Verify: `B leakcheck --scope tooling ROOT\.kiro\agents\gemma-auditor.md` exit 0; `python -m pytest tests -q -k
      recipe` passes (item 25 tests).

- [ ] 23. Create `ROOT\.kiro\agents\gemma-gate-builder.md`: frontmatter keys `name: gemma-gate-builder`,
      `description`, `tools: [read, write, shell]`, `welcomeMessage`. Body: purpose; inputs (final audit path, gate
      name); refusal rules (final VERDICT ≠ PROCEED; change not single-variable; no base dir named → NEEDS-BASE);
      procedure = `B gate-build ...` → edit only inside the new dir if the spec needs a hand edit → `B gate-check
      --dir ...` → hand back GATE_PREREG.md path + the push command for the USER; the boundary paragraph ("the one
      exception to never-write-submit_*: may CREATE one new `G\submit_<name>\`; must never modify, rename or delete an
      existing `submit_*` dir; never runs the Kaggle CLI, never pushes, never submits, never commits"); residual-risk
      note (AS-13); leakcheck and gold/task-id rules.
      Files: `ROOT\.kiro\agents\gemma-gate-builder.md` (new).
      Verify: `B leakcheck --scope tooling ROOT\.kiro\agents\gemma-gate-builder.md` exit 0; tests from item 25 pass.

- [ ] 24. Update `ROOT\.kiro\workflows\gemma-audit.workflow.json`: keep name, inputs `{proposal_path: file, slug:
      string}`, step ids `rebuild-kb, audit, refute, final`, agents (wf-coder, gemma-auditor ×2, wf-coder), modelIds
      (`claude-opus-5` audit, `gpt-5.6-sol` refute — different families), artifacts keys, the mechanical `B verdict`
      final, rebuild `effortLevel: "low"`. Prompt edits: audit/refute KB lines list STANDING_TRUTHS.md first, the
      corrected LB wording (LB source = newest pulled snapshot or curated; never "v6w=0.15 live-best" hardcoded; the
      banner states conflicts), the real CLI (replay, gold-gate, claims filters, card --limit), and a "Cost
      discipline" paragraph matching the agent file; remove the stale "v6 @ 0.12 in steering is STALE" and "branch_final
      PENDING" strings.
      Files: `ROOT\.kiro\workflows\gemma-audit.workflow.json`.
      Verify: `python -m pytest tests -q -k recipe` passes; `B leakcheck --scope tooling <recipe>` exit 0.

- [ ] 25. Static validation tests: extend `K\tests\test_recipe.py` — every `B <cmd>` mentioned in the recipe and in
      both agent files is a real subparser of `build_kb.build_parser()` (parse the names); every `K\...` file path
      named in them exists after a build (STANDING_TRUTHS.md, KB_SUMMARY.md, log_claims.md, runs.jsonl,
      replays\gold_coverage.json); recipe prompts contain `STANDING_TRUTHS.md` and `Cost discipline`; no recipe/agent
      text contains `v6 @ 0.12 in steering is STALE` or `branch_final PENDING`; gate-builder frontmatter has exactly
      the 4 keys and name `gemma-gate-builder`; gate-builder text contains "never modify" + "existing" + "submit_" and
      "never" + "push"; no agent text instructs running `G\build_kb.py`.
      Files: `K\tests\test_recipe.py`.
      Verify: `python -m pytest tests -q` → all pass (old + new; record the count).

- [ ] 26. Verification record + final consistency: append "REVISION 5 — verification (2026-10-31)" to
      `K\build_verification.md` with MEASURED/ASSUMED tags: coverage counts by kind; new runs; LB snapshot facts and
      conflicts; attribution flags; gold coverage table (48 rich + fastapi attempted); hunk-mode results; claims
      status counts and the list of CONTRADICTED claims (id, line, fact, evidence); lever count; idempotence result;
      cached-replay 0 result; env freeze identical; clone status; test count; remaining gaps; curated proposals.
      Final run: `B build` (plain) → `B check-fresh` exit 0 → idempotence IDENTICAL → pytest green.
      Files: `K\build_verification.md`.
      Verify: commands above; `git -C G\local_eval\repos\rich status --porcelain` empty, same for fastapi; no
      `$env:TEMP\gkb_*` or `kbrev5*` scratch left.

---------------------------------------------------------------------------------------------------------------

## 5. Hard constraints (every FEAT; the reviewer blocks on these)
- Never `kaggle kernels push`, never submit, never `git commit`/push, no training, no edits to existing
  `G\submit_*` dirs, `G\GEMMA_EXPERIMENT_LOG.md`, `ROOT\.kiro\steering\*`, curated inputs (only the generated
  `K\curated\_proposed_updates.md`). Never run `G\build_kb.py` (user tool; writes `G\EXPERIMENT_KB.sqlite`).
- Allowed writes: `K\` (code, generated outputs, pulled\, replays\, docs, tests), the REV5 append to design.md, the
  two agent files, the recipe, `$env:TEMP` scratch removed after. Tests that need a G tree use `GKB_GEMMA_ROOT` +
  `tmp_path`.
- Builder offline by default (only `pull` touches the network); idempotent; cached `--replay` re-runs nothing;
  base interpreter never mutated (pins in isolated `--target` dirs; freeze artifact proves it); gold-first before any
  counted replay; static reconstruction only; clones left clean; gold patches / problem-statement fingerprints / task
  ids never in any agent config or gate config (leakcheck --scope config).
- MEASURED vs ASSUMED labels in every record; a missed bar is reported as missed.

## Digest

Build/test commands (MEASURED today): `python -m pytest tests -q` with cwd `K` → `47 passed in 0.40s`.
`B check-fresh` → exit 3 `STALE` (inputs changed since 2026-10-16). Interpreter `ROOT\.venv\Scripts\python.exe`
3.13.14, pytest 9.1.1. PowerShell swallows stdout: redirect `*> file`. Idempotence: `python K\tests\idempotence_check.py
snapshot <a.json>` / `compare <a.json> <b.json>` (uses `build_meta.json.generated_files`, strips the two stamp
prefixes). Pin self-test: `python K\kblib\_selftest_pins.py` → `PIN SELFTEST OK`.

Per file (what to change, what I read):
- `K\build_kb.py` (1,104 lines). `cmd_build(args)` L82–286: discover → per-run loop over `disc["run_dirs"] +
  disc["pasted_logs"]` (L110–175: `kernellog.parse_log`, `_run_dir_trace_map`, `configs.extract_config(_submission_dir)`,
  `traces.parse_trace`, `nearmiss.compute`, `classify.classify`, row dict with `run_kind`
  "pasted-log"/"kaggle-kernel" and `config` subset incl. `out_of_scope`) → `nearmiss.cross_task_fp` → `_run_replays`
  or `_read_cached_replays` → `claims.extract(log_text, curated/submissions.csv, curated/claims.jsonl, baseline)` →
  render via `render.kb_summary(stamp, banner, None, coverage, matrix, harness, levers, lb, claims_summary, nearmiss,
  replay, limitations)` → `_write` outputs → `build_meta` (schema build_meta/3, `generated_files` hard-listed L235–239)
  → `build_stamp.json` → `build_log.txt`. `_run_dir_trace_map` L59 only looks at `results\traces`. `_submission_dir`
  L77 only `submission\`. `_baseline_banner` L339–346 hardcodes the stale steering sentence. `_lever_lines` L415 stub.
  `_run_replays` L594–713 (targets = min_set + all_runs_rules; per task `eng.gold_first` every build, saved via
  `_save_gold`; as_run + counterfactual candidates; CloneGuard). `cmd_card` L993, `cmd_claims` L1011 (only `--status`
  filters), `cmd_pull` L1021 stub (returns 1). `build_parser` L1029–1087: subcommands build/check-fresh/report-path/
  preflight/verdict/leakcheck/card/claims/pull — NO `replay`. `cmd_leakcheck` returns 1 on hits (agent file matches).
  Covered by: `tests\test_slow_facts.py` (reads runs.jsonl), `tests\test_recipe.py`, `tests\idempotence_check.py`.
- `K\kblib\discover.py` (`discover(g)` → dict of run_dirs/failed/empty/pasted/reference/submit_dirs/
  staged_submissions/items/read_files/beyond_depth; run dir = has `results\traces` or a JSON kernel log; failed = JSON
  log without `resolved=`; submit-dir = kernel id contains `gemma-sibling-conform-`; staged = top-level `submit_*`
  with agent.yaml+eval_config.yaml and no kernel-metadata; `input_fingerprint(g, extra_files)` hashes 5 curated files
  + log + tasks.jsonl + HARNESS_README + 2 maps + extra). Note: `lever_lexicon.json` is listed but absent on disk.
  Covered by: no direct unit test today (add in item 2).
- `K\kblib\paths.py`: `gemma_root()` honours `GKB_GEMMA_ROOT`; `SKIP_DIRS={.git,.train_env,__pycache__}`,
  `SKIP_DIR_PREFIXES=(adapter_dataset, adapter_v2_)`, `MAX_WALK_DEPTH=8`, `LARGE_FILE_BYTES=50MB`.
- `K\kblib\configs.py`: `extract_config(submission_dir)` reads agent.yaml/eval_config.yaml (strict YAML subset with
  `!include`), `generate_content_config` sampling fields, tools, prompt sha256/chars, `out_of_scope` when model ≠
  31B; contains a dead `if False` at the list-mapping branch (harmless; leave or clean). Covered by
  `test_yaml_subset_nested_and_scalars`.
- `K\kblib\claims.py` (cl-3, 118 lines): `segment()` at `## ` only; facts = heading `N/M` (6/10/22 only), `_LB`,
  `_VER_AT`, live-best heading flag; status SUPPORTED iff a score equals any COMPLETE submission score; curated
  claims loaded but not merged into statuses. Whole module is replaced in item 11. No unit tests today.
- `K\kblib\replay.py` (rp-4): `RP_VERSION="rp-4"` L37; `_PIN_FALLBACK` L54; `run_candidate` L~300–445 (apply
  ladder, protected reset, test_patch, pins → `_run_pytest`, `required = sorted(set(gt["tests"]["added_tests"]))`
  L426, `_required_pass` L547 (no required → passed≥1 ∧ failed==0 ∧ errors==0; else each required node must be in
  passed/failed names, skipped ⇒ missing ⇒ False), `harness_like` L429, `gold_relative` L437); `_candidate_diff`
  L461–471 (dead `if False` gitio call, then `_run_git_env` add -N / diff --binary outside the allowlist);
  `gold_first` L563–611 (INFRA/INVALID/VALID-HARNESS-LIKE/VALID-GOLD-RELATIVE); cache helpers `read_cache`/
  `write_cache` keyed on engine/task_fingerprint/python/pytest; `_parse_junit` L696 counts skipped without names/
  messages; `_run_git_env` L728. Covered by `test_replay_*`, `test_gitio_*`, `_selftest_pins.py`.
- `K\kblib\gitio.py`: `git(repo, *args, scope, eol, odb, alt, timeout)`; allowlists `_MAIN_RO`, `_MAIN_WORKTREE`,
  `_WT_SCOPE` (worktree scope already allows `add` and `diff`) — only `extra_env` + bytes mode are needed. Covered by
  `test_gitio_allowlist_blocks_commit_push_config`, `test_gitio_allowlist_exact_set`.
- `K\kblib\io.py`: `safe_write` allowlist `_ALLOWED_GENERATED` (9 files) + dirs `replays/`, `nearmiss_cache/`,
  `pulled/`; protected `curated/`, `proposals/`, `audits/`, `replays/manual/` checked FIRST. Add `STANDING_TRUTHS.md`
  and the exact `curated/_proposed_updates.md` exception. Covered by `test_safe_write_*`.
- `K\kblib\render.py`: `kb_summary(...)` fixed section order (2, 3, 7, 8, 9, 10, 13, 6, 11). Extend its signature
  (add since-last-build, levers per track, §13a/§13b, pulled-vs-submissions) — keep stamp-line rules.
- `K\kblib\kernellog.py`: `P1R` matches `-> resolved=`; JSON kernel logs are arrays of `{stream_name,time,data}`.
  Unchanged except it is no longer the only outcome source.
- `K\kblib\traces.py`: `parse_trace(path, harness_tool_calls)` requires `schema_version` starting `ATIF-`; rig,
  kaggle_pkg and cover-rich traces are all `ATIF-v1.7` with keys `schema_version, agent, steps, final_metrics`
  (MEASURED) → reusable as is.
- `K\curated\*` (read-only): `claims.jsonl` 6 rows (`J-subagents-regress`, `J-local-gold-pygments-drift`,
  `J-reviewer-critic-dead`, `J-wrongfix-is-content-not-ask`, `J-adapter-loads-in-scoring-host-confirmed`,
  `J-multilayer-adapter-takes-effect-ondisk`; keys id/kind/status/text/evidence/author); `run_labels.json` baseline
  v6w @ 0.15 (57098497), `pending[branch_final]` status PENDING (stale), no small-model baseline;
  `submissions.csv` newest 57201051 0.13 (2026-10-15); `replay_set.json` 8 min_set + rich_4079 all_runs.
- `ROOT\.kiro\workflows\gemma-audit.workflow.json`: 4 steps (rebuild-kb wf-coder effort low; audit gemma-auditor
  claude-opus-5 artifact audit_report; refute gemma-auditor gpt-5.6-sol artifact refute_report; final wf-coder effort
  medium artifact final_report, runs `B verdict`). Prompts hardcode "v6w=0.15 live-best … branch_final PENDING … v6 @
  0.12 in steering is STALE" and call `B replay` (non-existent). Covered by `tests\test_recipe.py` (6 tests: keys,
  ids, agents/models/families, template refs, P1 flags + unwrap, artifact keys).
- `ROOT\.kiro\agents\gemma-auditor.md` (187 lines; frontmatter name/description/tools [read, write, shell]/
  welcomeMessage; sections Role, Absolute paths, KB layout, Matrix letters, CLI, Read before judging, Evaluate,
  Verdict rules, Report format, AUDIT-JSON, REFUTE mode, Hard limits, Final chat message). Its KB/LB lines are stale
  (v6w live-best, steering v6 STALE). `test_recipe.py::test_agents_and_models` asserts `write` or `shell` in its
  frontmatter.
- `ROOT\.kiro\steering\gemma-submission-protocol.md` L23: `**v6w @ 0.15 is SACRED (live-best)** — Kaggle submission
  57098497` (read-only; banner parses it).
- `G\comp_files\HARNESS_README.md` L556 `compaction_interval = 5`, L558 `overlap_size = 2`, L559 `token_threshold =
  14,336`; L609 required nodes = FAIL_TO_PASS / PASS_TO_PASS / "test functions extracted from test_patch", explicitly
  passed, not skipped.
- `G\local_eval\gold_gate_all.py` (user script; read-only reference): drives `ReplayEngine.gold_first` per task and
  writes `K\replays\goldgate_all.json` records `{gold_first, reason, result_criterion, pins, pin_provenance,
  pin_warnings, gold_pass_n, repo, included, secs}`.
