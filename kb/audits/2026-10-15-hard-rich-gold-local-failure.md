# Hard-rich gold-first local failure — root-cause audit (2026-10-15)

Scope: why the gold patch fails its own `test_patch` locally for `rich_3469`, `rich_4070`,
`rich_4079` while `rich_4076` passes, and whether it is fixable without weakening the scorer.
Read-only investigation. Nothing in the engine, clones, or KB was modified. All env changes made
to reproduce were reverted (final env: pygments 2.21.0, markdown-it-py 4.2.0 — the state found).

Every claim is tagged **MEASURED** (reproduced from a file or a throwaway re-run of the real
`kblib.replay` engine) or **INFERRED**.

---

## Summary answer

**It is OUR harness, not the tasks, and all three are cheaply fixable.** None of the three golds
fails to apply, needs the network, needs a C extension, or is otherwise inherently un-runnable
offline. Every failure is **test-environment dependency version drift** in the single shared
`.venv` the replay engine runs tests with (`sys.executable`): a missing/younger `markdown-it-py`
plus a `pygments` that is newer than the version each task's own `poetry.lock` pins. The rich
tests hard-code exact ANSI/pygments byte output, so a different pygments version makes unrelated
(and, for rich_4079, the target) tests fail even though the gold code change is correct.

Proof it is drift and not the tasks (all **MEASURED** by re-running `kblib.replay.ReplayEngine`
against the four golds):

| pygments in `.venv` | rich_3469 | rich_4070 | rich_4079 | rich_4076 |
|---|---|---|---|---|
| 2.21.0 (found) + markdown_it present | required_pass ✔, harness_like ✘ (1 unrelated fail) | ✘ 6 fail | ✘ target fails | ✔ |
| **2.19.2** (4070/4079 lock pin) | required_pass ✔, 1 unrelated fail | **✔ harness_like** | **✔ harness_like** | ✔ |
| **2.17.2** (3469 lock pin) | **✔ harness_like** | ✘ 2 fail | ✘ 1 fail | ✔ |

Each task passes cleanly (exit 0, 0 failures, 0 errors, required tests pass) **when the test env
matches the pygments version that task's `poetry.lock` pins.** No single global pygments satisfies
all three, so the fix is **per-task dependency pinning** (install the task's locked
pygments + markdown-it-py into the checkout env before running its tests) — the standard
SWE-bench per-instance-environment practice. This changes nothing in the scorer logic: the same
FAIL_TO_PASS/PASS_TO_PASS required-node set, the same JUnit validation, the same zero-failure bar.
We are only giving the tests the library versions they were authored against.

Cheapest fixes, highest value first: **(1)** pin `pygments` (and ensure `markdown-it-py`) per-task
from the task's `poetry.lock` — fixes 4070, 4079, and 3469; **(2)** the engine already requires
`markdown_it` to be importable (it is now, 4.2.0) — keep it installed. One mechanism (per-task
pin) resolves all three failing golds.

---

## How the engine judges (so the fix is scoped correctly)

- `kblib/replay.py :: ReplayEngine._run_pytest` runs tests with **`sys.executable`** (the same
  interpreter that launched the KB build) via an inline bootstrap that does
  `importlib.import_module("rich")`, asserts `rich.__file__` is under the worktree (exit 97 if
  not), then `import pytest; pytest.main(...)`. There is **no per-task virtualenv and no
  dependency install** — whatever `pygments`/`markdown-it-py` happens to be in that one `.venv`
  is what every task sees. (MEASURED: the bootstrap string and `cmd = [sys.executable, "-c",
  bootstrap] + args` in `_run_pytest`.)
- `harness_like` (the VALID-HARNESS-LIKE criterion) requires `exit_code == 0` **and** `failed == 0`
  **and** `errors == 0` **and** `required_pass`. This matches `HARNESS_README.md` §6 step 5
  (`resolved = True` iff pytest exit 0, JUnit `failures == 0, errors == 0, passed > 0`, and every
  required node passed). So an unrelated failing test in the same file breaks the gate exactly as
  it would break the real scorer **in the same env**. (MEASURED: `_run_pytest`/`gold_first` and
  grep of HARNESS_README §6.)
- `required_tests` come from `gt["tests"]["added_tests"]` = the `def test_*` **added** by the
  task's `test_patch`. The task JSON has **no** explicit `FAIL_TO_PASS`/`PASS_TO_PASS` fields
  (MEASURED: `tasks.jsonl` row for rich_4070 keys = base_commit, patch, test_patch,
  problem_statement, hints_text, created_at, repo, instance_id). When `test_patch` only *edits*
  existing tests (adds no new `def test_`), `added_tests == []` and `_required_pass` falls back to
  "passed ≥ 1 and failed == 0 and errors == 0" — i.e. the whole-file zero-failure bar. This is why
  pygments noise in unrelated tests invalidates gold.

---

## Per-task findings

### rich_3469 — FAILING (control-adjacent: required test actually passes)
- **Difficulty label:** `kb_mech_class = EASY`. Gold touches `rich/markdown.py`; test file
  `tests/test_markdown.py`; required test `test_table_with_empty_cells`.
- **Failure signature (as recorded in `kb/replays/gold/rich_3469.json`):** `exit_code 2,
  errors 1, passed 0, gold_first INVALID, error_names ["test_markdown"]`. (MEASURED, file.)
- **Root cause #1 (collection error):** `ModuleNotFoundError: No module named 'markdown_it'` while
  collecting `tests/test_markdown.py` (import chain `tests/test_markdown.py` → `rich.markdown` →
  `from markdown_it import MarkdownIt`). The gold patch and test_patch BOTH apply cleanly
  (`apply … rc 0` for candidate and test_patch). (MEASURED: throwaway re-run of
  `ReplayEngine.run_candidate`, stdout tail `ModuleNotFoundError: No module named 'markdown_it'`;
  import list of `rich/markdown.py` at base shows `markdown_it` is the only external import.)
- **Root cause #2 (version drift, surfaces once markdown_it present):** with `markdown_it`
  importable and pygments 2.21.0, collection succeeds and `required_pass` becomes **True**
  (`test_table_with_empty_cells` passes), but `harness_like` is still False because the sibling
  test `test_inline_code` fails on pygments color-code output. (MEASURED.) With pygments pinned to
  **2.17.2** — the version this base's `poetry.lock` pins — the whole file passes:
  `exit_code 0, passed 7, failed 0, required_pass True, harness_like True`. (MEASURED.)
- **Evidence citation:** `kb/replays/gold/rich_3469.json` (`error_names`, `exit_code`);
  `poetry.lock @ c478588f` → `pygments 2.17.2`, `markdown-it-py 2.2.0` (MEASURED, git show);
  `replay.py :: _run_pytest` (interpreter = `sys.executable`, no per-task install).
- **Cheapest fix:** before running this task's tests, install into the test env the versions from
  the task's `poetry.lock` (`pygments==2.17.2`, `markdown-it-py>=2.2.0`). **Risk:** low; it only
  aligns library versions with the authored baseline. Does not touch tests or the scorer.

### rich_4070 — FAILING (the empty-`added_tests` case + pygments drift)
- **Difficulty label:** `kb_mech_class = HARD`. Gold touches 9 `rich/*.py` files; test files
  `tests/test_console.py`, `tests/test_syntax.py`; **`added_tests == []`** (the test_patch only
  edits import lines in the two test files — changes a `getpass` monkeypatch target and moves a
  `Console` import — it adds no new `def test_`). (MEASURED: `tasks_gold.json` tests block;
  test_patch diff.)
- **Failure signature (`kb/replays/gold/rich_4070.json`):** `exit_code 1, failed 6, passed 107,
  gold_first INVALID`, reason "gold does not pass required tests locally". (MEASURED, file.)
- **Root cause:** pygments **version drift only.** Gold applies cleanly and runs. Of the failures,
  gold **fixes exactly `test_input_password`** (the real target: base fails it, gold passes it) and
  introduces **zero regressions**; the 6 that remain are all `tests/test_syntax.py` pygments
  rendering tests (`test_python_render*`, `test_option_no_wrap`, `test_syntax_highlight_ranges`),
  **identical in base and gold** — i.e. pre-existing env noise unrelated to the code change.
  (MEASURED: base vs gold `failed_names` diff — `fixed by gold = ["test_input_password"]`,
  `regressions = []`, the 6 syntax tests present in both.) Because `added_tests == []`, the
  fallback required-pass counts those 6 against gold. With pygments pinned to **2.19.2** (this
  base's `poetry.lock` pin) all syntax tests pass: `exit_code 0, passed 113, failed 0,
  required_pass True, harness_like True`. (MEASURED.)
- **Evidence citation:** `kb/replays/gold/rich_4070.json`; `poetry.lock @ fc41075a` →
  `pygments 2.19.2`, `markdown-it-py 3.0.0` (MEASURED, git show); the 6 names are all under
  `tests/test_syntax.py` (MEASURED, stdout tail).
- **Cheapest fix:** per-task pin `pygments==2.19.2` into the test env (markdown-it-py already fine).
  Fully resolves this gold. **Risk:** low. **Secondary hardening (optional, do NOT rely on it as
  the fix):** when `added_tests == []`, derive the required-node set the way the real scorer does
  (test functions referenced/edited in `test_patch`, i.e. `test_input_password` here) rather than
  the whole-file zero-failure fallback — this would make the gate robust to residual env noise
  without relaxing any test. This mirrors HARNESS_README §6 ("test functions extracted from
  test_patch"). It is a *defense-in-depth* refinement; the pygments pin alone already passes.

### rich_4079 — FAILING (target test itself is pygments-sensitive)
- **Difficulty label:** `kb_mech_class = EASY`. Gold touches `rich/markdown.py`; test file
  `tests/test_markdown.py`; required test `test_inline_code_in_table_cells` (a NEW test the
  test_patch adds, with a hard-coded monokai-pygments ANSI `expected`).
- **Failure signature (`kb/replays/gold/rich_4079.json`):** `exit_code 2, errors 1, passed 0,
  gold_first INVALID, error_names ["test_markdown"]`. (MEASURED, file.)
- **Root cause #1 (collection error):** same `ModuleNotFoundError: No module named 'markdown_it'`
  as 3469 — the whole file failed to collect. Gold + test_patch apply cleanly. (MEASURED.)
- **Root cause #2 (target test is version-sensitive):** once `markdown_it` is importable, the file
  collects and the **required test itself fails** under pygments 2.21.0 because its `expected`
  string is the exact `monokai`/`python` lexer byte output from an older pygments. Pinning
  pygments to **2.19.2** (this base's lock) makes it pass: `exit_code 0, passed 8, failed 0,
  required_pass True, harness_like True`. (MEASURED.) (Under 2.17.2 it fails again — the pin must
  be the task's own, 2.19.2.)
- **Evidence citation:** `kb/replays/gold/rich_4079.json`; test_patch adds
  `test_inline_code_in_table_cells` with `inline_code_theme="monokai", inline_code_lexer="python"`
  and a byte-exact `expected` (MEASURED, test_patch diff); `poetry.lock @ 19c67b9a` →
  `pygments 2.19.2`, `markdown-it-py 3.0.0` (MEASURED).
- **Cheapest fix:** per-task pin `pygments==2.19.2` + ensure `markdown-it-py` importable.
  Fully resolves. **Risk:** low.

### rich_4076 — PASSING control (why it is different)
- Gold touches `rich/ansi.py`; test file `tests/test_ansi.py`; required test `test_decode_newlines`.
- **Observed:** `gold_first VALID-HARNESS-LIKE`, `exit_code 0, passed 24, failed 0` under every
  pygments version tried (2.17.2 / 2.19.2 / 2.21.0). (MEASURED, file + all three re-runs.)
- **Why it passes where the others fail:** `tests/test_ansi.py` imports only `rich.ansi` /
  `rich.text` — it has **no `markdown_it` import** (so no collection error) and **no pygments /
  syntax-highlighting assertion** (so it is immune to the pygments drift). It is the one hard-rich
  gold whose correctness does not depend on an external library's exact output. This is precisely
  the DIFFERENCE: 4076 touches no drifting dependency; 3469/4079 depend on markdown_it + a
  pinned pygments; 4070 depends on a pinned pygments. (MEASURED/INFERRED from the import lists.)

---

## Does not weaken the scorer

Every proposed fix is an **environment** change, not a scorer change:

- **Per-task dependency pin** installs the `pygments` / `markdown-it-py` versions the task's own
  `poetry.lock` specifies into the test checkout. It does not edit, skip, xfail, or relax any test;
  it does not alter FAIL_TO_PASS/PASS_TO_PASS, the JUnit validation, the `python_classes=Test* *Test`
  selection, the `exit_code == 0 ∧ failures == 0 ∧ errors == 0` bar, or the required-node set. It
  only makes the local test env match the version baseline the tests were authored against — the
  same thing a SWE-bench per-instance image does. A test that passes afterward passes because the
  library produces its authored output, not because a check was loosened. (The real Kaggle scorer
  runs in the task's pinned environment, so this is a parity fix, not a leniency.)
- **The optional 4070 required-node refinement** (derive required nodes from `test_patch` when
  `added_tests == []`, instead of whole-file zero-failure) would make the gate *stricter and more
  precise* — it would still demand the targeted test(s) pass and still demand zero errors; it would
  only stop counting demonstrably-unrelated, env-noise failures as gold failures. It is explicitly
  the HARNESS_README §6 behavior ("test functions extracted from test_patch"). It is NOT required
  for the fix (the pygments pin alone passes) and is offered as defense-in-depth only.

Nothing here makes a failing test pass by changing the test.

---

## Recommendations (implement nothing here — these are the fixes)

1. **Highest value — per-task dependency pinning in the replay env.** Before running a task's
   tests, read the task's `poetry.lock` (present in each rich base commit) and install the pinned
   `pygments` (and confirm `markdown-it-py`) into the interpreter the engine uses. Mechanically:
   either (a) build a per-task throwaway venv seeded from `poetry.lock`, or (b) `pip install
   pygments==<lock> markdown-it-py==<lock>` into a scratch target and prepend it so the worktree
   import check still points `rich.__file__` at the worktree. This one change flips all three
   hard-rich golds to VALID (3469 needs 2.17.2; 4070 and 4079 need 2.19.2 — MEASURED).
2. **Keep `markdown-it-py` importable** in the base env (it is now, 4.2.0). The recorded
   `ModuleNotFoundError` reflects an earlier env state; the current on-disk package imports fine.
   The per-task pin in (1) should still install the lock version to avoid 4.x-vs-2.x output drift.
3. **Optional (4070 only, defense-in-depth):** when `added_tests == []`, derive the required-node
   set from the `test_patch`-referenced test functions (HARNESS_README §6), not the whole-file
   fallback. Do not ship this as the fix; the pin in (1) already resolves 4070.

### Caveat / uncertainty (stated per rule 9)
- The gold records in `kb/replays/gold/*.json` were produced in a prior env state (markdown_it
  not importable). The current re-runs are the authoritative measurement; the stored JSON should
  be regenerated after fix (1) lands. (MEASURED that current engine behavior differs from the
  stored records.)
- All pass/fail results above are from this Windows `.venv` (pytest 9.1.1, python 3.13.14). The
  pygments-version mechanism is library-level and env-independent, but the exact remaining-failure
  *names* under each pygments version are specific to this interpreter. The leaderboard remains the
  only external judge; this audit makes the **local** gold-first gate trustworthy for the three
  hard-rich tasks, which is its stated purpose.
