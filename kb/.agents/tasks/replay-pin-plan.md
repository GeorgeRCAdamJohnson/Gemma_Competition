# Implementation Plan — per-task dependency pinning for the gold-first replay engine

Scope: a bounded bugfix inside `Gemma\kb\kblib\replay.py` (+ a small call-site touch in
`Gemma\kb\build_kb.py`) so each replayed task runs its tests against the `pygments` version its own
`poetry.lock` pins, with `markdown-it-py` importable, WITHOUT mutating the shared `.venv` and WITHOUT
touching any scorer-judging logic. Grounded in the root-cause audit
(`Gemma\kb\audits\2026-10-15-hard-rich-gold-local-failure.md`), the curated claim
`J-local-gold-pygments-drift`, and the engine source read in full.

## Design decisions (made here; one-two sentences each)

- **Isolation mechanism: `pip install --target <tmp>` + `PYTHONPATH` prepend, NOT a per-task venv.**
  `_run_pytest` already launches tests as a subprocess with a fully-controlled `env` dict and already
  sets `env["PYTHONPATH"] = str(wt)`. Prepending an isolated `--target` dir to that one subprocess's
  `PYTHONPATH` is a two-line change at the exact existing injection point, needs no venv bootstrap
  (`ensurepip`/interpreter copy — slow and brittle on OneDrive/Windows), and leaves
  `sys.executable`/`.venv` byte-for-byte unchanged (MEASURED constraint from the task brief). The
  interpreter still runs from the shared env, so the `rich.__file__`-under-worktree assertion keeps
  working: the pin dir only supplies `pygments`/`markdown_it`, and `wt` stays first on `PYTHONPATH`
  so the worktree `rich` is imported first. Justification over a venv: smaller blast radius, faster,
  no mutation of the base env, trivially removable scratch under `$env:TEMP`.
- **Pin source: parse the task's own `poetry.lock` at `base_commit` in the throwaway worktree, with a
  hardcoded fallback.** The worktree is already checked out at `base_commit`, so `poetry.lock` is on
  disk there (the audit MEASURED the lock pins by `git show`). Parsing the worktree copy keeps the pin
  derived from the task's commit, not a static table. A tiny stdlib TOML-ish line scanner (not a new
  dependency) extracts `pygments` and `markdown-it-py`. Fallback map
  (`rich_3469->pygments==2.17.2`, `rich_4070->2.19.2`, `rich_4079->2.19.2`) is used ONLY when the lock
  is absent/unparseable, and is recorded with `provenance="fallback"` plus a warning in the record.
- **No-pin / offline failure policy: record INFRA/UNVERIFIED, never a wrong-version pass.** If a pin
  cannot be installed (offline, no cache, version yanked), the replay result is marked INFRA with the
  reason and `verdict_valid=False`; gold is NOT marked VALID on a mismatched env (hard constraint 2).
- **Cache-key change: fold the applied pins into the `env` block the cache already validates.** `read_cache`
  already invalidates when `env.python`/`env.pytest` change. Adding `env["pins"]` (sorted
  `pkg==ver` list + provenance) makes a re-pin invalidate stale cache entries with zero new key
  plumbing. This is the minimal correct change.
- **Pins apply to `rich` tasks only.** Only `Textualize/rich` tests hard-code pygments/markdown_it byte
  output (MEASURED: fastapi path untouched by the audit). The resolver returns an empty pin set for
  non-rich repos, so fastapi replays are byte-identical to today (idempotence for them is preserved).
- **Note on the referenced spec:** the task brief cites `.kiro\specs\gemma-auditor\design.md §13`;
  that file does not exist (ASSUMED moved). The §13 "rp-3" contract is carried inline in
  `replay.py`'s module docstring and `RP_VERSION`; this plan honors that inline contract. The engine
  version is bumped to `rp-4` so pinned results never collide with pre-fix cache entries.

## Hard constraints encoded in every step
- Writes ONLY under `Gemma\kb\` (code in `kblib\`, generated KB outputs, the verify doc) and `$env:TEMP`
  scratch (removed after). NEVER edit `Gemma\submit_*`, `Gemma\GEMMA_EXPERIMENT_LOG.md`,
  `.kiro\steering\*`, or curated inputs (`claims.jsonl`, `run_labels.json`, `submissions.csv`,
  `replay_set.json`).
- Scorer-judging logic (`_required_pass`, `harness_like`, `gold_relative`, JUnit parse, the
  `rich.__file__` exit-97 assertion, the required-node set) is UNTOUCHED. Only which library versions
  are present changes.
- No git commits, no Kaggle, no training, no network beyond pip's local cache (offline-friendly).
- Clones (`Gemma\local_eval\repos\rich`, `\fastapi`) stay read-only; CloneGuard must still verify CLEAN.

---

# Implementation Plan

- [ ] 1. Add a `poetry.lock` pin parser + fallback map + resolver in `kblib\replay.py`.
      Add module-level `_PIN_FALLBACK = {"rich_3469": {"pygments": "2.17.2"}, "rich_4070": {"pygments": "2.19.2"}, "rich_4079": {"pygments": "2.19.2"}}` and `_PIN_PKGS = ("pygments", "markdown-it-py")`.
      Add `def _parse_lock_pins(worktree) -> dict`: read `<worktree>/poetry.lock` (UTF-8, errors="replace");
      scan `[[package]]` blocks for `name = "..."`/`version = "..."` pairs; return `{normalized_name: version}`
      for the names in `_PIN_PKGS` (normalize case/`-`vs`_` so `Pygments`/`markdown-it-py` match). Return `{}` if the file is missing/unparseable.
      Add `def _resolve_pins(repo, task, worktree) -> (pins: dict, provenance: str, warnings: list)`:
      for non-rich repos return `({}, "none", [])`; else parse the lock, and if `pygments` is missing from
      the parsed pins fall back to `_PIN_FALLBACK.get(task, {})` with `provenance="fallback"` and a warning string, else `provenance="lockfile"`.
      Files: `Gemma\kb\kblib\replay.py`
      Verify: `python Gemma\kb\kblib\_selftest_pins.py` (added in step 6) prints the three rich pins from the real worktrees; before that unit exists, interim check is step 7's full build.

- [ ] 2. Add an isolated pin-install helper in `kblib\replay.py` that installs into a scratch `--target` dir, never the base env.
      Add `def _ensure_pins(pins: dict) -> (target_dir: pathlib.Path | None, install_log: list, infra_reason: str | None)`:
      compute a deterministic scratch dir under `self.build_root / "pins" / <sha12 of sorted pkg==ver>` (reused across tasks sharing identical pins so pygments 2.19.2 installs once);
      if already populated, return it; else run `[sys.executable, "-m", "pip", "install", "--no-input", "--disable-pip-version-check", "--target", str(target), "<pkg>==<ver>", ...]`
      with `--no-index`-free but cache-friendly flags (allow pip's local cache; do NOT pass `--index-url`); on non-zero return code return `(None, log, "pin install failed: <tail>")`.
      Keep the base interpreter untouched — install only into `--target`. The dir lives under `self.build_root` (already `$env:TEMP`, torn down in `__exit__`).
      Files: `Gemma\kb\kblib\replay.py`
      Verify: covered by step 6 unit (`_ensure_pins` with an already-present version is a no-op returning a dir) and step 7 build.

- [ ] 3. Thread pins through `run_candidate` -> `_run_pytest` and prepend the pin target to the test subprocess `PYTHONPATH` ONLY.
      In `_run_pytest`, after computing `env["PYTHONPATH"] = str(wt)`, if a resolved pin target dir is passed in, set
      `env["PYTHONPATH"] = os.pathsep.join([str(wt), str(pin_target)])` so the worktree `rich` still imports first (keeps the exit-97 `rich.__file__` assertion valid) while `pygments`/`markdown_it` resolve from the pin dir.
      Change `_run_pytest` signature to accept `pin_target=None`; in `run_candidate`, before step 6 (`self._run_pytest(...)`), call `_resolve_pins` + `_ensure_pins` for `(repo, task, wt)`; on an `infra_reason` return
      `{"result": "INFRA", "reason": <reason>, "verdict_valid": False, ...}` WITHOUT running tests (hard constraint 2 — never run on a wrong env). Record `pins`, `pin_provenance`, `pin_warnings` on the result dict.
      Do NOT change the bootstrap string, the pytest args, the JUnit path, or any pass/fail computation.
      Files: `Gemma\kb\kblib\replay.py`
      Verify: step 7 build — the three hard-rich golds flip to `harness_like: True` in `Gemma\kb\replays\gold\rich_3469.json`, `rich_4070.json`, `rich_4079.json`; `rich_4076.json` stays VALID.

- [ ] 4. Fold the applied pins into the result `env` block (cache-key) and bump `RP_VERSION`.
      In `run_candidate`, extend the existing `res["env"] = {...}` to include `"pins": sorted(f"{k}=={v}" for k,v in pins.items())` and `"pin_provenance": provenance`.
      Change `RP_VERSION = "rp-3"` to `"rp-4"` so pre-fix cached results (no pins) are invalidated by the existing `engine_version` check in `read_cache`.
      No change needed to `read_cache`/`write_cache` logic — the `env` dict is already stored and compared via `engine_version`; adding `pins` to `env` means a different pin set yields a different stored `env`, and future hardening can compare it directly. Update `ENGINE_VERSIONS["rp"]` consumer in `build_kb.py` automatically picks up `replay.RP_VERSION` (it references the attribute, no literal to edit).
      Files: `Gemma\kb\kblib\replay.py`
      Verify: step 7 build; then re-run build with no new candidates (step 8) re-runs zero replays (cache hit on rp-4 entries).

- [ ] 5. Surface pin provenance + warnings in the gold-first record and the replay record, and record INFRA on pin failure.
      In `gold_first`, carry `pins`, `pin_provenance`, and `pin_warnings` from the gold result into `rec` (so `kb\replays\gold\<task>.json` records which pins were applied and whether from lockfile or fallback).
      In `build_kb.py :: _replay_candidate`, copy `res.get("pins")`/`pin_provenance`/`pin_warnings` into the `rec` dict and append a short `notes` suffix when `pin_provenance == "fallback"` (so the replay table flags backstop use). When `res["result"] == "INFRA"` with a pin reason, keep `agent_passed = "INFRA"` (existing branch already maps INFRA) and ensure the reason text is preserved in `notes`.
      Files: `Gemma\kb\kblib\replay.py`, `Gemma\kb\build_kb.py`
      Verify: step 7 build — `Gemma\kb\replays\gold\rich_4070.json` shows `"pin_provenance": "lockfile"` and `"pins": ["pygments==2.19.2"]` (lockfile wins over the fallback map).

- [ ] 6. Add a tiny self-test for the pin parser/resolver/installer (new file under kblib, stdlib only).
      Create `Gemma\kb\kblib\_selftest_pins.py`: imports `replay`, builds a throwaway worktree-less check for `_parse_lock_pins` against a small inline `poetry.lock` fixture string (asserts it extracts `pygments`/`markdown-it-py`), asserts `_resolve_pins("psf/requests", ...)` returns `({}, "none", [])`, and asserts the fallback fires with `provenance="fallback"` for a fake task when given an empty worktree. Keep it runnable as `python Gemma\kb\kblib\_selftest_pins.py` returning exit 0.
      Files: `Gemma\kb\kblib\_selftest_pins.py`
      Verify: `python Gemma\kb\kblib\_selftest_pins.py` exits 0 and prints `PIN SELFTEST OK`.

- [ ] 7. Full replay rebuild to confirm all three hard-rich golds flip to VALID and the clones stay clean.
      Run the real engine over the curated replay set with `--replay` and a generous deadline, forcing a re-run so rp-4 pins are applied fresh.
      Files: none (generates `Gemma\kb\replays\*`, `Gemma\kb\KB_SUMMARY.md`, `Gemma\kb\build_meta.json`)
      Verify: `python Gemma\kb\build_kb.py build --replay --force-replay --deadline-s 1500` prints `BUILD OK`; then
      inspect `Gemma\kb\replays\gold\rich_3469.json` / `rich_4070.json` / `rich_4079.json` each show `"gold_first": "VALID-HARNESS-LIKE"` (3469 may be VALID-HARNESS-LIKE under its 2.17.2 pin), `rich_4076.json` stays VALID, and `Gemma\kb\replays\clone_state.json` shows `"verdict": "CLEAN (no builder-attributable change)"` with `module_file_checks_ok: true`.

- [ ] 8. Confirm idempotence + caching: a second cached build re-runs nothing and the base env is unchanged.
      Capture the shared-env package versions before/after to prove no global mutation, then re-run build without `--force-replay`.
      Files: none
      Verify: `python -m pip freeze > %TEMP%\gkb_env_before.txt` ; `python Gemma\kb\build_kb.py build --replay --deadline-s 1500` (no `--force-replay`) prints `BUILD OK` with `replays_run_this_build=0` in `Gemma\kb\build_stamp.json` (cache hit on rp-4); `python -m pip freeze > %TEMP%\gkb_env_after.txt` ; `fc %TEMP%\gkb_env_before.txt %TEMP%\gkb_env_after.txt` reports no differences (pygments/markdown-it-py in the base env unchanged). Also confirm `git -C Gemma\local_eval\repos\rich status --porcelain` is empty.

- [ ] 9. Write the verification doc recording MEASURED pass/fail per task, pin provenance, and env-unchanged proof.
      Create `Gemma\kb\audits\2026-10-15-replay-pin-verification.md` (new audit doc, NOT a curated input) summarizing: the three golds' before/after `gold_first` verdicts, the applied pins + provenance (lockfile vs fallback), the CloneGuard CLEAN verdict, and the `pip freeze` diff showing the base env is byte-identical. Tag each line MEASURED vs ASSUMED. Note explicitly that the scorer logic was not changed (reference the untouched `_required_pass`/`harness_like`).
      Files: `Gemma\kb\audits\2026-10-15-replay-pin-verification.md`
      Verify: file exists and lists all four rich tasks with their post-fix verdicts; cross-check its numbers against the regenerated `Gemma\kb\replays\gold\*.json`.

## Notes / assumptions (stated per accountability rules)
- MEASURED (from the audit, re-running the real engine): 3469 passes clean under pygments 2.17.2;
  4070 and 4079 pass clean under 2.19.2; 4076 passes under all three. No single global pygments
  satisfies all three — per-task pinning is required.
- ASSUMED: pip's local cache contains (or can fetch, if the environment is briefly online) pygments
  2.17.2 and 2.19.2 and a compatible markdown-it-py. If offline with an empty cache, step 7 will
  legitimately record the un-installable task(s) as INFRA/UNVERIFIED rather than a false pass — that
  is the correct, honest outcome under hard constraint 2, not a plan failure.
- ASSUMED: `.kiro\specs\gemma-auditor\design.md` is absent; the rp-3/rp-4 §13 contract is honored via
  `replay.py`'s inline docstring and `RP_VERSION`. If that spec file is later located, re-check its
  §13 wording against this plan before merging.
- The optional "derive required nodes from test_patch when `added_tests == []`" hardening from the
  audit is explicitly NOT in scope: the pygments pin alone resolves rich_4070, and that refinement
  would touch required-node derivation (scorer-adjacent). Left out to respect the one-change discipline
  and the "scorer untouched" hard constraint.
