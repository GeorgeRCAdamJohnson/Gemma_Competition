# Per-task dependency pinning for the gold-first replay engine (rp-4)

The replay engine previously ran every rich task's tests against the single shared `.venv`
(`sys.executable`), with no per-task dependency install. rich's tests hard-code exact ANSI/pygments
byte output, so a pygments newer than each task's own `poetry.lock` pin made unrelated tests (and, for
rich_4079, the target test) fail even when the gold code was correct — leaving three of the four
hard-rich golds (rich_3469, rich_4070, rich_4079) INVALID while rich_4076 stayed VALID. rp-4 resolves
each task's `pygments`/`markdown-it-py` version from its `poetry.lock` at `base_commit`, installs them
into an isolated `%TEMP%` `--target` directory, and prepends that directory to the test subprocess's
`PYTHONPATH` *after* the worktree. The base interpreter env is never touched and no scorer-judging logic
changes.

Watch for: nothing blocking. The isolation mechanism, the untouched base env, the unchanged pass/judge
criteria, the INFRA-on-pin-failure policy, and all four golds reaching VALID-HARNESS-LIKE with
lockfile provenance are each backed by MEASURED evidence in `build_verification.md` and confirmed by
reading the engine source. One NIT on the hardcoded fallback map; one NIT on evidence that lives in prose
rather than a committed artifact.

**Verdict**: APPROVED

## High-level view

The fix is scoped to *environment provisioning*, which is exactly where the root-cause audit placed the
defect. `_resolve_pins` reads the task's `poetry.lock` (lockfile provenance), `_ensure_pins` installs
the pins into `build_root/pins/<sha12>` via `pip install --target` (no `--index-url`, local cache
allowed), and `_run_pytest` threads that directory onto `PYTHONPATH` behind the worktree. The worktree
staying first is what keeps the exit-97 `rich.__file__`-under-worktree assertion valid — only
`pygments`/`markdown_it` resolve from the pin dir.

Base-env integrity is the central safety claim and it is directly measured: `pip freeze` before and
after the replay build is identical, and `import pygments`/`import markdown_it` report 2.21.0/4.2.0 both
before and after. The pins live only in the throwaway target dir, torn down with `build_root` in
`__exit__`.

The scorer was not weakened. `_required_pass` (same required-node set with the `added_tests`-else-
whole-file-zero-failure fallback), `harness_like` (`exit_code==0 ∧ junit_present ∧ passed≥1 ∧ failed==0
∧ errors==0 ∧ required_pass`), `gold_relative`, the JUnit parse, the pytest arg set, and the exit-97
assertion are all byte-unchanged — verified by reading the source, not just the doc.

The failure policy is fail-closed: an un-installable pin returns `result=INFRA` and the task is never
judged on a mismatched env, so a wrong-version silent pass is structurally impossible. All four golds
reach VALID-HARNESS-LIKE with `provenance=lockfile` (the hardcoded fallback never fired), the control
rich_4076 did not regress, and the clones end clean with no leftover `%TEMP%\gkb_*`.

<details>
<summary>Issues (2)</summary>

1. **Hardcoded fallback pin map (NIT)** — `_PIN_FALLBACK` embeds pygments pins for three tasks as a
   last resort when `poetry.lock` can't be parsed. It never fired this run (all four used lockfile
   provenance) and firing it is recorded with a warning + `provenance=fallback`, so it does not fake
   green. Consider dropping it or converting a fallback hit to INFRA, so the engine can only ever pin
   from a task's real lock.
2. **Key evidence lives in prose (NIT)** — the base-env `pip freeze` before/after comparison and the
   gold `exit/pass/fail` numbers are reported in `build_verification.md`, not emitted as a committed
   artifact under `kb/replays/`. The `gold/<task>.json` + `clone_state.json` records cover provenance,
   pins, and the module-file checks; a persisted freeze-diff would make the base-env claim independently
   re-checkable without re-running.

</details>

<details>
<summary>Details</summary>

## Isolation: pins never reach the base env

`_ensure_pins` installs into `build_root / "pins" / <sha12>` keyed on the sorted `pkg==ver` set, so the
pygments 2.19.2 shared by rich_4070/4079/4076 installs once and is reused. The install command is
`[sys.executable, "-m", "pip", "install", "--no-input", "--disable-pip-version-check", "--target",
<target>] + spec` — crucially no `-m pip install` into site-packages and no `--index-url` pin, so it
honors the local pip cache and stays offline-friendly. The target dir sits under `build_root` (a
`%TEMP%\gkb_*` mkdtemp) and is removed in `__exit__` along with the worktrees.

The ordering in `_run_pytest` is what makes this safe:

```python
if pin_target is not None:
    env["PYTHONPATH"] = os.pathsep.join([str(wt), str(pin_target)])
else:
    env["PYTHONPATH"] = str(wt)
```

Worktree first means the under-test `rich` still imports from the worktree, so the bootstrap's exit-97
`rich.__file__`-under-worktree guard keeps firing (the doc records all 30 checks `under_worktree: True`).
Only `pygments`/`markdown_it`, which are absent from the worktree, resolve from the pin dir. The doc's
measured `pip freeze` before/after identical, and 2.21.0/4.2.0 unchanged in the base interpreter, is the
direct confirmation that the shared `.venv` is not mutated — satisfying the first BLOCKING criterion.

## Scorer judging logic is unchanged

Reading the source rather than trusting the doc: `_required_pass` keeps the same two-branch contract —
when `added_tests` is non-empty each required node must be present and passing; when it's empty it falls
back to "passed≥1 ∧ failed==0 ∧ errors==0". `harness_like` is still
`exit_code==0 ∧ junit_present ∧ passed≥1 ∧ failed==0 ∧ errors==0 ∧ required_pass`. `gold_relative`,
`_parse_junit`, the pytest args (`python_classes=Test* *Test`, `--junitxml`), and the exit-97 bootstrap
assertion are untouched by the pin threading. No test is relaxed, skipped, xfailed, or deselected. The
only behavioral change is which library versions are importable — satisfying the second and fifth
BLOCKING criteria. This matches the audit's framing: aligning the env to the version baseline the tests
were authored against is a parity fix, not leniency, and is the standard SWE-bench per-instance-env
practice. The curated claim J-local-gold-pygments-drift states the same contract.

## Fail-closed on an un-installable pin

```python
pin_target, pin_log, pin_infra = self._ensure_pins(pins)
if pin_infra is not None:
    return {"result": "INFRA", "reason": f"pin unavailable: {pin_infra}", ...}
```

A pin that fails to install (offline, uncached, yanked) returns `INFRA` *before any test runs*, carrying
the attempted pins, provenance, and log. Because `gold_first` maps `result == "INFRA"` to
`gold_first = "INFRA"` rather than VALID, a gold can never be marked VALID on a mismatched or wrong-
version env. There is no silent wrong-version fallback — satisfying the third and fourth BLOCKING
criteria. This path did not trigger this run (all pins installed from the local cache/index), which the
doc states honestly as a code path exercised by the self-test rather than the live build.

## All four golds VALID-HARNESS-LIKE with lockfile provenance

The verification table records, after `build --replay --force-replay`, read back from
`replays/gold/<task>.json`:

```
rich_3469  VALID-HARNESS-LIKE  harness_like  markdown-it-py==2.2.0, pygments==2.17.2  lockfile  0/7/0/0/True/True
rich_4070  VALID-HARNESS-LIKE  harness_like  markdown-it-py==3.0.0, pygments==2.19.2  lockfile  0/113/0/0/True/True
rich_4079  VALID-HARNESS-LIKE  harness_like  markdown-it-py==3.0.0, pygments==2.19.2  lockfile  0/8/0/0/True/True
rich_4076  VALID-HARNESS-LIKE  harness_like  markdown-it-py==3.0.0, pygments==2.19.2  lockfile  0/24/0/0/True/True
```

The three formerly-INVALID golds flipped; the control rich_4076 did not regress; every pin came from the
task's own `poetry.lock` (`provenance=lockfile`, 0 warnings) with the lock versions cross-checked by
`git show <base_commit>:poetry.lock` against the audit table. The hardcoded `_PIN_FALLBACK` map never
fired. This satisfies the done-condition BLOCKING criterion (all four VALID with pins + provenance
recorded), and the pins/provenance are surfaced through `build_kb.py:_replay_candidate` onto the replay
records (confirmed: `pin_provenance`, `pin_warnings`, and a `pins=FALLBACK` note when provenance is
fallback).

## Write boundary and clone cleanliness

All generated outputs land under `kb/replays/`; the engine's git access goes through `gitio` with a verb
allowlist, worktrees are detached under `%TEMP%\gkb_*`, and objects are redirected to a throwaway store.
The doc records `clone_state.json` verdict `CLEAN (no builder-attributable change)`, both clones'
`git status --porcelain` empty at the end, and zero `gkb_*` left under `%TEMP%`. Idempotence is
re-confirmed: two plain builds byte-identical bar the stamp lines; `RP_VERSION` bumped rp-3→rp-4 so pre-
fix no-pin cache entries are invalidated, and the pins are folded into the result `env` block for a
cache-key change. No edits to `submit_*`, `GEMMA_EXPERIMENT_LOG.md`, `.kiro/steering/*`, or the curated
inputs are evident. This satisfies the remaining BLOCKING criteria.

</details>

<details>
<summary>Files changed</summary>

- `Gemma/kb/kblib/replay.py` — `_parse_lock_pins`, `_resolve_pins`, `_ensure_pins`, pin threading through
  `run_candidate`/`_run_pytest`/`gold_first`; `RP_VERSION` rp-3→rp-4; `_PIN_PKGS`/`_PIN_FALLBACK`.
- `Gemma/kb/build_kb.py` — `_replay_candidate` surfaces `pins`/`pin_provenance`/`pin_warnings` and a
  `pins=FALLBACK` note.
- `Gemma/kb/kblib/_selftest_pins.py` — pin resolver self-test.
- Evidence: `Gemma/kb/build_verification.md` (rp-4 section); regenerated `Gemma/kb/replays/gold/*.json`,
  `clone_state.json`, `KB_SUMMARY.md` §13.

Full root-cause context: `Gemma/kb/audits/2026-10-15-hard-rich-gold-local-failure.md`.

</details>
