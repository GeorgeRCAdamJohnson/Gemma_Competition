# Implementation Plan — decode-toward-COMMITMENT sweep on the FIXED local gold-first scorer

> Scope: build an in-repo, idempotent sweep RUNNER that drives the existing local agent loop
> (`local_eval/run_local.py`) across a set of decode configs x rich tasks, scores every agent
> attempt through the FIXED per-task-pinned gold-first replay engine (`kb/kblib/replay.py` rp-4),
> and emits a pre-registered sweep report + raw JSONL. NO training, NO Kaggle, NO scored slot,
> NO git commits, NO worktree. Writes land ONLY under `Gemma/kb/` and `Gemma/local_eval/`
> (+ `%TEMP%` scratch that the replay engine already tears down).
>
> ROOT = `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE`.
> Gemma = `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma`.
> Windows / PowerShell / `python` on PATH. Absolute paths throughout.

---

## Design decisions (made here, grounded in the code that was read)

- **Scorer reuse, not re-implementation.** The runner imports `kb/kblib/replay.py` directly and reuses
  its public gold-first path: `rp.load_raw_tasks(tasks.jsonl)`, `gold.build_tasks_gold(tasks.jsonl)`,
  then `ReplayEngine(tasks_gold)` with (a) one `eng.gold_first(repo, task, base_commit)` per task as the
  VALIDITY GATE and (b) one `eng.run_candidate(repo, task, base_commit, kind="patch",
  patch_text=agent_diff, gold_pass_tests=<from gold_first>)` per agent attempt to SCORE it. This is the
  identical per-task-pinned, worktree-isolated, APPROVED rp-4 path the KB uses; the runner does NOT
  call `verify()` in `run_local.py` (that path is NOT the fixed scorer and is not per-task pinned).
  Rationale: the hard constraint is "reuse the FIXED gold-first scorer (per-task pinning)", and `replay.py`
  is exactly that engine. `run_local.py`'s own `verify()` and `batch.py`'s scoring are the OLD path and
  are explicitly avoided for scoring (they may still be used for the agent LOOP, see below).

- **Agent loop reuse.** The runner imports `run_local as R` and calls `R.run_agent(task, model,
  max_tool_calls, system_prompt=..., max_time_s=..., use_compaction=...)` to produce the agent's diff
  and the per-run stats. `run_agent` already resets the clone to `base_commit`, loads the per-task graph,
  runs the loop, and returns `(diff, calls, dur, submitted)`; `R.LAST_RUN` then exposes
  `first_edit_call`, `edit_ok`, `edit_err`, `tool_counts`, `end_reason`, `patch_chars`, `nudges`. The
  diff `run_agent` returns is fed verbatim as the `patch_text` candidate to the replay engine.

- **Decode injection = module globals + ONE additive edit to `chat()`.** `TEMPERATURE`, `TOP_P`, `TOP_K`
  are already `run_local` module globals read by `chat()`; the runner sets them per config before each
  `run_agent`. `frequency_penalty`/`presence_penalty` are NOT currently forwarded by `chat()`, so one
  additive, backward-compatible edit to `run_local.py` adds two module globals (`FREQUENCY_PENALTY=0.0`,
  `PRESENCE_PENALTY=0.0`) and forwards them only when non-zero (penalty 0 == exact current behavior).
  The reserve-tail / commit-by-remaining nudge reuses the EXISTING `KAGGLE_NUDGE_TEXT` / `NUDGE_MODE` /
  `KAGGLE_MAX_NUDGES` mechanism (the v19v3 reserve-tail family) — no new mechanism invented.
  Rationale: `local_eval/` is writable; the task explicitly permits the `chat()` edit there and requires
  it stay additive.

- **Baseline is the LOCAL baseline, never the 0.15 board number.** The local backend is a local
  `llama-server` at `http://127.0.0.1:8081` (confirmed `OLLAMA = ".../v1/chat/completions"` in
  `run_local.py`), NOT the competition 31B. So the comparator is the baseline ARM run FIRST locally
  through the same fixed scorer. The 0.15 (v6w, submission 57098497) and 0.13 (v6w+temp1.0/topk64,
  submission 57201051) board numbers are context only and are quoted as such in the report.

- **No workflow restructuring.** This is one coherent deliverable (a single coupled runner + its one
  additive injection edit + the pre-registered run that writes the report). It does not decompose into
  independent features, so the plan is written as a single ordered list for the existing
  implement-and-review loop; the loop's stop contract (`kb/audits/build-review.json` verdict==APPROVED,
  reviewer last) is preserved untouched.

---

# Implementation Plan

- [ ] 1. Add additive frequency/presence-penalty forwarding to the local agent's `chat()`.
      In `local_eval/run_local.py`: add two module globals near the other sampling globals
      (`TEMPERATURE`, `TOP_P`, `TOP_K`) — `FREQUENCY_PENALTY = 0.0` and `PRESENCE_PENALTY = 0.0` —
      and in `chat()` append `payload["frequency_penalty"] = FREQUENCY_PENALTY` only when it is
      non-zero, and `payload["presence_penalty"] = PRESENCE_PENALTY` only when non-zero (mirror the
      existing `if TOP_P is not None:` guard style). Also expose `--freq-penalty` / `--presence-penalty`
      argparse flags in `main()` wired to those globals, defaulting to 0.0, so the CLI stays usable.
      Keep it strictly backward compatible: with both at 0.0 the payload is byte-identical to today.
      Files: `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval\run_local.py`
      Verify: `cd c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval; python -c "import run_local as R; assert R.FREQUENCY_PENALTY==0.0 and R.PRESENCE_PENALTY==0.0; import inspect,json; src=inspect.getsource(R.chat); assert 'frequency_penalty' in src and 'presence_penalty' in src; print('OK additive')"`
      — prints `OK additive` and the import does not error (confirms the module still loads and the
      defaults are the no-op values).

- [ ] 2. Create the sweep RUNNER `local_eval/decode_sweep.py` that defines the arms and the task split,
      but does NOT yet score — a dry structure that imports both engines and resolves paths.
      It must: `import run_local as R`; add `Gemma/kb` to `sys.path` and
      `from kblib import replay as rp, gold, paths`; define `TASKS_JSONL = Gemma/comp_files/tasks.jsonl`;
      define the PRE-REGISTERED arm table (see item 6) as a list of dicts
      `{"name","temperature","top_p","top_k","freq_penalty","presence_penalty","nudge_mode","nudge_max"}`
      with a stable `config_hash` = sha256 of the sorted-json of the decode fields (12 hex chars);
      define the EXACT rich task set and its EASY/HARD labels and the DISCOVER/CONFIRM (held-out) split
      (see item 5). No network, no model calls in this item.
      Files: `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval\decode_sweep.py`
      Verify: `cd c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval; python decode_sweep.py --list` — prints the arm table (with config hashes), the task set with EASY/HARD labels,
      and the discover/confirm split, then exits 0 WITHOUT contacting the model or the scorer.

- [ ] 3. Implement the gold-validity gate in `decode_sweep.py`: for each task in the set, run the fixed
      scorer's gold-first control ONCE and cache the verdict.
      Add `gold_gate(task_id) -> dict` that loads the task record from `tasks.jsonl`, calls
      `rp.load_raw_tasks(TASKS_JSONL)` (once per process) and builds `tasks_gold` via
      `gold.build_tasks_gold(TASKS_JSONL)` (once), then inside a `with rp.ReplayEngine(tasks_gold) as eng:`
      block calls `eng.gold_first(task["repo"], task_id, task["base_commit"])`. A task is INCLUDED only if
      the returned record's `gold_first` is `VALID-HARNESS-LIKE` or `VALID-GOLD-RELATIVE`; any `INFRA` /
      `INVALID` task is EXCLUDED with the record's `reason` recorded (hard constraint: never score an
      agent attempt against invalid gold). Persist the gate verdicts to
      `kb/audits/_decode_sweep_cache/gold_gate.json` so reruns skip re-validating.
      Files: `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval\decode_sweep.py`
      Verify: `cd c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval; python decode_sweep.py --gold-gate` — prints a per-task line `task <id>: gold_first=<verdict> (reason)` for the
      full task set, writes `kb/audits/_decode_sweep_cache/gold_gate.json`, and if the backend/clones
      allow it, every EASY anchor task (rich_4077, rich_4079) reports a VALID verdict. If a clone or the
      replay env is unavailable, each affected task is reported INFRA with its reason and EXCLUDED — not
      faked. (This item needs the local git clones under `local_eval/repos/`; it does NOT need the model
      server.)

- [ ] 4. Implement the per-(config, task) agent run + score + cache in `decode_sweep.py`.
      Add `run_cell(arm, task_id, gold_rec) -> row`: set `R.TEMPERATURE`, `R.TOP_P`, `R.TOP_K`,
      `R.FREQUENCY_PENALTY`, `R.PRESENCE_PENALTY`, `R.NUDGE_MODE`, `R.KAGGLE_MAX_NUDGES` from the arm;
      set `R.FIRST_MSG`/`R.set_tools_mode` consistent with the v6w-equivalent config (document which: use
      the kaggle tool surface + kaggle first message so the loop matches the board agent, since the
      baseline arm is "v6w-equivalent sampling"); call `R.set_repo(repo)` then
      `diff, calls, dur, submitted = R.run_agent(task, model, max_tool_calls, max_time_s=..., use_compaction=...)`;
      read `st = R.LAST_RUN` for `first_edit_call`, `edit_ok`, `edit_err`, `tool_counts`, `end_reason`,
      `nudges`. Then SCORE the diff through the fixed engine: inside a `with rp.ReplayEngine(tasks_gold)
      as eng:` call `eng.run_candidate(repo, task_id, base_commit, kind="patch", patch_text=diff,
      gold_pass_tests=gold_rec["gold_pass_tests"], timeout_s=...)`; `resolved = bool(res.get("gold_relative"))`
      (or `harness_like` when gold was harness-like — mirror whichever criterion `gold_first` used).
      Record the row: `{config_name, config_hash, task, easy_hard, split, resolved, tool_calls=calls,
      first_edit_at=st.get("first_edit_call") (JSON null if None), no_edit=(st.get("first_edit_call") is None),
      patch_chars=len(diff), submitted, end_reason, edit_ok, edit_err, nudges, scorer_result=res.get("result"),
      required_pass=res.get("required_pass"), gold_relative=res.get("gold_relative")}`. Cache each row by
      `(config_hash, task)` at `kb/audits/_decode_sweep_cache/<config_hash>/<task>.json`; on rerun, a cached
      row is loaded instead of re-running the model. If the model server at `http://127.0.0.1:8081` is not
      up, the cell is recorded `status="NOT-RUN"` with reason `"backend down: <error>"` and `resolved=None`
      — never faked.
      Files: `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval\decode_sweep.py`
      Verify: `cd c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval; python decode_sweep.py --arm baseline --task rich_4077` — runs ONE cell; if the backend is up it prints a row
      with `resolved=`, `first_edit_at=`, `tool_calls=`, writes the cache file, and a second invocation of
      the same command prints `[cache hit]` and does not call the model again; if the backend is down it
      prints `NOT-RUN (backend down ...)` and exits 0 without fabricating a result.

- [ ] 5. Pre-register and freeze the EXACT rich task set, EASY/HARD labels, and the held-out split in
      `decode_sweep.py` (constants, consumed by items 2-4 and 7). Source the labels from
      `Gemma/RICH_48_DIFFICULTY_MAP.md` §1-§2. Use this fixed set (all single-file, gold-verifiable, with
      traces):
      EASY (10): rich_4077, rich_4079, rich_4076, rich_3469, rich_3471, rich_3278, rich_2943, rich_3470,
      rich_3882, rich_3518.
      HARD (2, as difficulty controls): rich_3935 (single-file HARD), rich_3772 (single-file HARD) — kept
      single-file so gold stays locally verifiable; genuine multi-file giants (rich_3930, rich_4070) are
      EXCLUDED up front as out of a 15/28-call agent's reach and recorded as such.
      Held-out split (fixed, seedless, by task id so a winner is never chosen on the tasks it was tuned on):
      DISCOVER = rich_4077, rich_4079, rich_3471, rich_2943, rich_3882, rich_3935 (tune/choose arms here);
      CONFIRM (held-out) = rich_4076, rich_3469, rich_3278, rich_3470, rich_3518, rich_3772 (the SUCCESS
      bar is judged ONLY on CONFIRM). Record the split and the exclusion reasons as module constants and
      echo them in the report header.
      Files: `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval\decode_sweep.py`
      Verify: covered by item 2's `--list` (the split and labels print and the EASY/HARD/excluded counts
      sum to the declared set); additionally
      `python -c "import decode_sweep as d; assert set(d.DISCOVER)&set(d.CONFIRM)==set(); print('disjoint OK')"`
      prints `disjoint OK`.

- [ ] 6. Pre-register the arm table and the SUCCESS bar as module constants in `decode_sweep.py`.
      Arms (baseline FIRST, then ONE axis varied at a time; combinations only in a labeled SECOND pass):
      - `baseline`: temperature 0.2, top_p 0.95, top_k 64, freq 0.0, presence 0.0 (v6w-equivalent). RUN FIRST.
      - axis (a) temperature DOWN: `temp_00` (0.0 greedy), `temp_01` (0.1) — top_p/top_k/penalties at baseline.
      - axis (b) penalties UP: `freq_02` (freq 0.2), `freq_04` (freq 0.4 — the value the log says killed the
        repeat-loop), `pres_02` (presence 0.2), `pres_04` (presence 0.4) — temperature at baseline.
      - axis (c) reserve-tail: `reserve_tail` — baseline sampling + the v19v3 commit-by-remaining nudge via
        `NUDGE_MODE="kaggle"` + `KAGGLE_NUDGE_TEXT` reserve-tail; one `nudge_max` value.
      - SECOND pass (only after single-axis, only combining axes that each won on CONFIRM): e.g.
        `combo_temp01_freq04`, `combo_temp01_reserve`.
      PRE-REGISTERED BAR (verbatim text the report MUST carry at the top):
      "Baseline arm = v6w-equivalent sampling (temperature 0.2, top_p 0.95, top_k 64, NO penalty), run
      FIRST locally through the FIXED per-task-pinned gold-first scorer, establishing the LOCAL resolve
      count and the commit-timing proxy for THIS backend. The local backend is a local llama-server at
      127.0.0.1:8081, NOT the competition 31B, so the LOCAL baseline is the only comparator — never the
      0.15 board number. An arm WINS on the held-out CONFIRM split only if it either (i) resolves at least
      as many CONFIRM tasks as baseline AND strictly improves the commit-timing proxy (strictly earlier
      median first_edit_at OR strictly fewer no-edit runs), OR (ii) resolves strictly more CONFIRM tasks.
      A tie on resolves with equal-or-worse commit-timing is a FAILURE. One axis changes per arm; the
      baseline is a hard floor. A null (no arm beats baseline on CONFIRM) is a valid reported result."
      Files: `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval\decode_sweep.py`
      Verify: `python decode_sweep.py --list` prints every arm with exactly ONE axis differing from
      baseline (except the explicitly labeled SECOND-pass combos), and prints the pre-registered BAR text
      block; `python -c "import decode_sweep as d; print(len(d.ARMS))"` runs clean.

- [ ] 7. Implement `--run-all` orchestration + the report/JSONL writers in `decode_sweep.py`.
      `--run-all` runs the gold gate (item 3), then runs baseline across the full set FIRST, then each
      single-axis arm, then (optionally, behind `--second-pass`) the combos; every cell goes through
      `run_cell` with caching. It appends every per-(config,task) row to
      `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\audits\2026-10-15-decode-commitment-sweep.jsonl`
      (one JSON object per line; rerun truncates-then-rewrites from cache so it is idempotent). It then
      writes the report
      `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\audits\2026-10-15-decode-commitment-sweep.md`
      containing, in order: (1) the pre-registered BAR text (item 6) at the very top; (2) the frozen task
      set with EASY/HARD labels, the DISCOVER/CONFIRM split, and the excluded tasks + reasons; (3) a
      per-arm-vs-baseline table with columns `arm | CONFIRM resolves (n/N) | DISCOVER resolves | median
      first_edit_at | no-edit runs | mean tool_calls | VERDICT(win/tie/FAIL)`; (4) a VERDICT line that
      names the winning arm or states the honest NULL, with EVERY number tagged MEASURED (tied to a JSONL
      row / cache file) vs INFERRED; (5) a caveat block: "LOCAL-ONLY, FREE-GATE-CANDIDATE — a win here is a
      hypothesis for the FREE Kaggle gate per gemma-submission-protocol.md, NOT a scored-slot change; the
      backend is not the 31B." Any NOT-RUN cell is listed with its reason in a dedicated subsection.
      Files: `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval\decode_sweep.py`,
      `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\audits\2026-10-15-decode-commitment-sweep.md`,
      `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\audits\2026-10-15-decode-commitment-sweep.jsonl`
      Verify: `cd c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval; python decode_sweep.py --run-all` — exits 0; the `.jsonl` has one row per (arm,task) that ran; the `.md`
      opens with the verbatim BAR text, has the per-arm table, a VERDICT line, and the LOCAL-ONLY caveat.
      If the backend is down, the report is still written with every cell NOT-RUN and the VERDICT line
      states "NOT MEASURED — backend was down" (never a fabricated win). Re-running `--run-all` a second
      time is idempotent (serves from cache, same files).

- [ ] 8. Prove the HARD CONSTRAINTS hold and leave the clones clean.
      Confirm the only files created/modified are under `Gemma/kb/` and `Gemma/local_eval/`; confirm NO
      edits to `Gemma/submit_*`, `Gemma/GEMMA_EXPERIMENT_LOG.md`, `.kiro/steering/*`, or
      `Gemma/comp_files/*` (curated inputs); confirm no git commit was made and the rich/fastapi clones
      under `Gemma/local_eval/repos/` are clean (the replay engine's CloneGuard already asserts this, but
      record `git status` for each clone in the report's provenance footer). Remove any `%TEMP%` scratch
      the engine did not auto-clean (it tears down `gkb_*` on exit; verify none linger).
      Files: (verification only — no new files beyond the sweep artifacts)
      Verify: run
      `git -C c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval\repos\rich status --porcelain`
      and the fastapi equivalent — both print NOTHING (clean); run
      `git -C c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE status --porcelain` and confirm the only
      changed/added paths are `Gemma/local_eval/run_local.py`, `Gemma/local_eval/decode_sweep.py`,
      and files under `Gemma/kb/audits/` (report, jsonl, `_decode_sweep_cache/`) plus `Gemma/kb/replays/`
      cache the engine writes — and NOTHING under `Gemma/submit_*`, the experiment log, steering, or
      `Gemma/comp_files/`. Record both outputs in the report provenance footer.

---

## Notes / assumptions (flagged, not blocking)

- **Backend availability is the one external dependency.** The agent LOOP needs the local llama-server
  on `127.0.0.1:8081`; the gold GATE and the SCORER need only the local git clones + a Python with
  `pytest`+`rich` (`run_local.pytest_python()` / `GATE_PYTHON` already handle interpreter selection, and
  the replay engine installs per-task pins into an isolated `%TEMP%` target). If the server is down the
  runner records NOT-RUN rows and the report says so — this satisfies the "never fake numbers" constraint
  and still verifies the plumbing (items 1-3 and the cache/report writers run without the model).
- **Which `resolved` criterion.** `gold_first` returns either `VALID-HARNESS-LIKE` (use
  `res["harness_like"]`) or `VALID-GOLD-RELATIVE` (use `res["gold_relative"]`); `run_cell` mirrors the
  per-task criterion the gate chose so the agent attempt is judged by the same yardstick as gold. This is
  the APPROVED rp-4 contract, not a new rule.
- **Tool surface / first message.** The baseline arm must mirror v6w, which runs the kaggle 9-tool
  surface + kaggle first message (`R.set_tools_mode("kaggle")`, `R.FIRST_MSG="kaggle"`,
  `R.NUDGE_MODE="kaggle"`). The runner sets these for all arms so the ONLY thing varying across arms is
  the decode axis under test (ablation discipline).
- **Idempotency.** All model-expensive work is cached by `(config_hash, task)` under
  `Gemma/kb/audits/_decode_sweep_cache/`; the gold gate is cached under the same root; the replay engine
  additionally caches by candidate sha under `Gemma/kb/replays/cache/`. Reruns redo nothing and rewrite
  the report/JSONL deterministically from cache.
