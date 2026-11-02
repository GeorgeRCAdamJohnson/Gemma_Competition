# V2 Adapter Forensics — edit-discipline QLoRA, FREE 5-task gate (v2_gate_s05c)

Read-only forensic analysis of the v19-LoRA-v2 "edit-discipline" adapter (all-linear, r=32,
lora_alpha=16, effective alpha/r=0.5) on the FREE 5-task rich gate. Compared against the
live-best no-adapter v6 run on the same tasks. No code was changed and nothing was rerun.

Sources:
- Adapter traces: `Gemma/v2_gate_s05c/results/traces/trace_rich_{4077,4079,4076,3469,4070}.json`
- v6 no-adapter traces: `Gemma/_v6out/results/traces/trace_rich_{4077,4079,4076,4070}.json`
  (NOTE: `trace_rich_3469.json` does **not** exist in `_v6out` — that comparison is unavailable.)
- Resolved status is taken from the user-provided run summary (message #11) and corroborated by
  `submit_patch` `patch_size` in each trace (only rich_4077 submitted a non-zero patch).

---

## 1. Summary answer (bottom line first)

**The adapter is doing BOTH failure modes, and neither is the skill we trained for.**

1. **The dominant observed failure is NOT anchor-mismatch.** Across all five tasks there are **zero
   ANCHOR-MISMATCH failures that actually blocked a resolve** attributable to the trained skill. The
   one real anchor error (rich_4070 step 5) was self-corrected on the very next call. The edit tool
   also auto-unescapes `\n`, so the specific "literal `\n` instead of real newline" failure the
   adapter was trained to prevent is **silently tolerated by the harness** (strategy `"unescaped"`).

2. **The two things that actually sank the run are (a) SEARCH-DEATH and (b) a MALFORMED-TOOLCALL
   decoding corruption specific to `edit_file`.**
   - **3 of 5 tasks (rich_4079, rich_4076, rich_3469) never attempted a single `edit_file`** and
     submitted empty patches (patch_size 0). They burned the 15-call budget on `grep`/`pytest`/
     `read_file` and never converged. This is the `first_edit_at=None` "search-death" the user flagged.
   - **rich_4070 made 16 `edit_file` calls, 11+ of them identically MALFORMED**: the adapter
     serialized the call so that `new_string` ends with the literal text `` `,old_string: `` and the
     entire intended `old_string` became a **JSON key** with value `` ` ``. The tool rejected every one
     of these with `"mandatory input parameters are not present: old_string"`. That is a REPEAT-LOOP
     of a format-corruption bug.

3. **rich_4077 resolved in spite of the adapter, not because of it.** v6 (no adapter) resolves the
   same task the same easy way (add `isatty` to `rich/file_proxy.py`). The adapter's edit even emitted
   literal `\n`; it only landed because the tool auto-unescaped it.

4. **Every measured delta vs v6 is neutral or negative.** v6 scored 2/5 on these tasks
   (4077 + 4079); the adapter scored 1/5 (4077 only). There is **no task the adapter resolved that v6
   did not**, and **no sub-step where the adapter is observably better**. On rich_4079 and rich_4076
   the adapter is strictly worse (0 edit attempts vs v6 landing a correct edit on 4079).

**Verdict:** The edit-anchor skill is not the bottleneck in this run. The adapter is (a) **corrupting
`edit_file` tool-call serialization** (a decoding/format problem, visible as the `` `,old_string: ``
key-collapse on rich_4070) and (b) **degrading the agent's convergence** so it dies in search without
ever reaching an edit on 3/5 tasks. This points at a training-data-shape / format problem and a
capability regression, not at a skill that "just needs more training."

---

## 2. Per-task table

| task      | attempted_edit | n_edit_calls | n_anchor_mismatch | n_malformed | resolved | vs v6 |
|-----------|:--------------:|:------------:|:-----------------:|:-----------:|:--------:|-------|
| rich_4077 | yes (step 17)  | 1            | 0                 | 0           | **True** | tie — both resolve, same fix (add `isatty`) |
| rich_4079 | **no**         | 0            | 0                 | 0 (SEARCH-DEATH) | False | **worse** — v6 lands correct edit & resolves |
| rich_4076 | **no**         | 0            | 0                 | 0 (SEARCH-DEATH) | False | tie-bad — both fail, v6 also 0 edits (24 calls) |
| rich_3469 | **no**         | 0            | 0                 | 0 (SEARCH-DEATH) | False | n/a — no v6 trace exists |
| rich_4070 | yes (step 5)   | 16           | 1 (self-fixed)    | **11+**     | False | **worse** — v6 lands 4 clean edits, resolves import fix path |

### Failure-class counts (across all 5 adapter tasks)

| class | count (tasks) | count (edit calls) |
|-------|:---:|:---:|
| ANCHOR-MISMATCH (trained skill, old_string not byte-matching) | 1 task | 1 call (rich_4070 step 5, self-corrected next call) |
| MALFORMED-TOOLCALL (old_string jammed into new_string / missing param) | 1 task | 11+ calls (rich_4070 steps 14–29) |
| SEARCH-DEATH (never attempted an edit) | **3 tasks** (4079, 4076, 3469) | — |
| REPEAT-LOOP (same malformed call re-emitted) | 1 task (rich_4070) | 11+ calls |
| OTHER (minor arg typo, non-fatal: `start_line"` key) | 1 call (rich_3469 step 21) | 1 |

Measured fact: **of 17 total `edit_file` calls across all adapter tasks, exactly 1 was a true
anchor-mismatch (and it was recovered); 11+ were malformed-toolcall corruption; 2 were clean
successes (rich_4077 step 17, rich_4070 steps 6 & 26).**

---

## 3. Evidence (direct quotes from traces)

### 3a. rich_4077 (the ONE resolve) — resolved IN SPITE of the adapter

Adapter `edit_file` at step 17 (`rich/file_proxy.py`), raw args contain **literal `\n`**:

```
old_string = '    def fileno(self) -> int:\n        return self.__file.fileno()'      # literal backslash-n
new_string = '    def fileno(self) -> int:\n        return self.__file.fileno()\n\n    def isatty(self) -> bool:\n        return self.__file.isatty()'
```

Observation shows the tool rescued it via unescaping:

```
{"status": "ok", ..., "occurrences": 1, "strategy": "unescaped",
 "diff": "... def fileno(self) -> int:\n         return self.__file.fileno()\n+\n+    def isatty(self) -> bool:\n+        return self.__file.isatty()\n"}
```

The file bytes read at step 16 use **real** newlines, so the adapter's literal-`\n` old_string would
NOT byte-match — this is exactly the ANCHOR-MISMATCH we trained to prevent — but the harness tool has
an `"unescaped"` fallback strategy that silently fixes it. v6 (no adapter) resolves the identical task
at its step 16 with a correctly-newlined edit adding `isatty`. **Conclusion: not an adapter win.**

### 3b. rich_4070 — MALFORMED-TOOLCALL corruption (the clearest adapter defect)

Raw `arguments` JSON object, adapter step 14 (verbatim from the trace):

```json
{"filepath": "rich/logging.py",
 "new_string": "from . import get_console\nfrom ._log_render import LogRender\nfrom .highlighter import ReprHighlighter\nfrom .text import Text\n\n\nclass RichHandler(Handler):`,old_string:",
 "from . import get_console\nfrom ._log_render import LogRender\nfrom .highlighter import ReprHighlighter\nfrom .text import Text\nfrom .traceback import Traceback\n\n\nclass RichHandler(Handler)": "`"}
```

Note the structure: `new_string`'s value **ends with the literal characters `` `,old_string: ``**, and
the string that should have been the `old_string` **value became a JSON key** whose value is a lone
backtick `` ` ``. The tool's response is explicit:

```
{"error": "Invoking `edit_file()` failed as the following mandatory input parameters are not present:\nold_string ..."}
```

This exact corruption repeats at steps 14, 15, 16, 17, 18, 19, 20, 21, 23, 24, 27, 28, 29 — a
**REPEAT-LOOP of a malformed call**. The agent recognizes it needs `old_string` and keeps re-emitting
the same broken serialization. The two edits that *did* apply (steps 6 and 26) used the normal
`{filepath, old_string, new_string}` shape — showing the adapter can produce valid calls but
intermittently collapses the two string params together with a stray backtick.

The stray backtick + `,old_string:` key-collapse is a **serialization/decoding artifact**, consistent
with the training data shaping the model to emit a run-on string instead of two cleanly separated JSON
fields. This is a format problem, not an anchor-matching skill gap.

### 3c. rich_4079, rich_4076, rich_3469 — SEARCH-DEATH (0 edits)

All three burned the budget on well-formed exploration and never reached an edit:

- rich_4079: 8 `run_command` (all clean `grep`/`find`, e.g. `grep -n "class Table" rich/table.py`),
  several `read_file`, then `get_status` shows `tool_calls_remaining: 0` and `patch_submitted: false`,
  followed by two empty `submit_patch` (`patch_size: 0`). **It identified `rich/markdown.py` as
  relevant (same file v6 edits) but never edited it.**
- rich_4076: clean `grep` + a sequence of `python3 -c` repro probes, then BudgetExceeded, empty patch.
- rich_3469: repeated `pytest` + `grep`, BudgetExceeded, empty patch. (One minor arg typo: step 21
  `read_file` emitted a key `start_line"` with a trailing quote — non-fatal.)

Measured fact: the SEARCH-DEATH tasks' `run_command` strings are **not** corrupted — the format
corruption is specific to `edit_file`'s dual-string payload. These tasks fail by **non-convergence
within 15 calls**, not by format.

### 3d. v6 comparison, step by step

- **rich_4079 (v6 resolves, adapter 0 edits):** v6 explores (steps 3–20), then at step 21 attempts an
  edit on `rich/markdown.py` `on_text` that fails with `"old_string and new_string are identical"`,
  immediately corrects it at step 22 (changes the conditional so `stylize` only runs for str input),
  runs tests, submits. The adapter reached the same file in exploration but **never attempted any
  edit** — pure search-death. **Clear regression.**
- **rich_4076 (both fail):** v6 also lands 0 successful edits and hits BudgetExceeded (24 calls); it
  spends calls on a `code_analyzer_agent` and many `run_command`. Neither resolves; not an adapter
  regression on *outcome*, but the adapter still never edits either.
- **rich_4070 (v6 resolves path, adapter corrupts):** v6 makes 4 clean `edit_file` calls (steps 5, 6,
  7, 24) with correctly-separated `old_string`/`new_string`, including the `Path(record.pathname).name`
  → `os.path.basename(...)` fix, and submits. The adapter attempts the same import/`RichHandler` region
  but collapses into the `` `,old_string: `` malformed loop and never produces a coherent patch set.
  **Clear regression caused by format corruption.**
- **rich_4077 (tie):** covered in 3a — both resolve the same easy way.

---

## 4. Cross-cutting answers

**(a) Dominant failure: ANCHOR-MISMATCH or MALFORMED-TOOLCALL?**
Measured: of 17 `edit_file` calls, 1 anchor-mismatch (self-corrected), 11+ malformed-toolcall, 2 clean.
But the *run-level* dominant failure is **SEARCH-DEATH (3/5 tasks never edit)**, with
MALFORMED-TOOLCALL the dominant *edit-level* failure (1 task, 11+ calls). ANCHOR-MISMATCH — the trained
skill — is essentially a non-factor here, and where it occurred it was tolerated/recovered.

**(b) rich_4079 & rich_4076 vs v6:** On rich_4079 the adapter is strictly worse — v6 lands a correct
edit and resolves; the adapter reaches the right file but emits **zero** edits (search-death). On
rich_4076 both fail with 0 landed edits, so no outcome delta, but the adapter still never edits.

**(c) rich_4077 — because of or in spite of the adapter?** **In spite of.** v6 resolves it the same
easy way, and the adapter's edit only applied because the tool auto-unescaped a literal-`\n` old_string
that would otherwise have been an anchor-mismatch.

**(d) Any evidence the adapter helped anything?** **No.** No task resolved by the adapter that v6
missed; no sub-step observably better; v6 is 2/5 vs adapter 1/5 on these tasks. Every delta is neutral
(4076, 4077) or negative (4079, 4070).

---

## 5. Conclusions (measured vs inferred)

**Measured facts:**
- 3/5 adapter tasks made 0 `edit_file` attempts (search-death). (trace step counts, empty patches)
- rich_4070 emitted 11+ structurally malformed `edit_file` calls with `old_string` collapsed into a
  JSON key and a stray `` `,old_string: `` suffix, each rejected for missing `old_string`. (raw args JSON)
- The one clean resolve (rich_4077) used literal-`\n` escaping that the tool auto-unescaped; v6
  resolves it identically. (observation `"strategy": "unescaped"`, v6 trace)
- Adapter 1/5 vs v6 2/5 on the shared tasks; no adapter-only resolve. (user summary + patch_size)
- `run_command` serialization is NOT corrupted; corruption is specific to the two-string `edit_file`
  payload. (SEARCH-DEATH command strings)

**Inferences (clearly labeled as such):**
- The `` `,old_string: `` key-collapse looks like the model emitting the two edit strings as one
  run-on token sequence instead of two separate JSON fields — most plausibly a **training-data-shape
  artifact** (how the edit examples were serialized/templated), amplified at alpha/r=0.5. This is an
  inference from the serialization pattern, not directly measured against the training set.
- The search-death on 3/5 tasks suggests the adapter also **degraded general agent convergence**
  (it over-explores and under-commits), not just edit formatting. Inferred from behavior; the cause
  (over-fit to edit emission at the expense of planning) is not directly verifiable from these traces.

---

## 6. Recommendations (only what the evidence supports)

1. **Do not conclude "the anchor skill needs more/different training" from this run** — anchor-mismatch
   is not the failure mode here (1 occurrence, recovered; harness auto-unescapes it anyway).
2. **Fix the `edit_file` serialization first.** The `` `,old_string: `` key-collapse is the single
   clearest, most repeated defect (rich_4070). Inspect the training data's tool-call template: confirm
   `old_string` and `new_string` are emitted as two cleanly delimited JSON fields with no trailing
   backtick/joiner, and check whether the chat template / stop tokens let the two strings run together.
3. **Investigate the convergence regression (search-death) separately** before another gate — 3/5
   tasks never editing is a bigger run-killer than any formatting issue. Compare call-budget usage
   adapter vs v6; the adapter burns 15 calls without committing while v6 commits by ~call 16–21.
4. **Before trusting a gate verdict, note the harness leniency:** the `"unescaped"` edit strategy
   masks the exact byte-faithfulness failure the adapter targets, so a FREE gate can neither credit nor
   penalize that skill cleanly. Any future test of the anchor skill needs a path that observes the
   raw old_string match, not just final resolve.
5. **rich_3469 has no v6 baseline** in `_v6out`; if that comparison matters, locate/regenerate the v6
   trace before drawing conclusions on it.

---

*Analysis was done with throwaway read-only Python scripts (deleted after use) that parsed each
trace's `steps[].tool_calls[]` and `observation.content`. No trace or source file was modified.*
