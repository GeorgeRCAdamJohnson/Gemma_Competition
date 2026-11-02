# RICH 48 Difficulty Map — can a rich-only strategy realistically reach #1?

Read-only investigation. Zero GPU. No code changed, nothing submitted. Source of truth:
`Gemma/comp_files/tasks.jsonl` (129 records, 48 with repo `Textualize/rich`), the gold `patch`
of each rich task, plus local-eval ground-truth logs and `GEMMA_EXPERIMENT_LOG.md`.

---

## 0. SUMMARY ANSWER (read this first)

**The rich-only path to #1 is NOT realistically supported by the current agent, and the dominant
failure mode is COMMITMENT/EDIT-MECHANICS, not task difficulty.**

Two findings, kept strictly separate because they have different confidence levels:

1. **MEASURED (high confidence, from gold patches):** The gold fixes are mechanically small. Of 48
   rich tasks, **20 are EASY** (single file, single hunk, ≤~10 net lines — the "rich_4077 profile"),
   **12 are MEDIUM**, **16 are HARD** (multi-file / sprawling / large). So the *fix itself* is tiny
   for ~42% of rich tasks. The winnable slice, judged only by patch size, looks large.

2. **MEASURED (high confidence, from local-eval logs + experiment log):** The agent does **not**
   convert that slice. Across every logged local run, **confirmed distinct rich resolves EVER = 2**
   (`rich_4077`, `rich_4079`), and **zero fastapi ever** (`GEMMA_EXPERIMENT_LOG.md:27-28`). Even on the
   EASIEST tasks the agent fails — and the logged tool traces show *why*: it either loops on
   `search_code` and never commits an edit ("explore death" / `no_patch`), or it commits a patch that
   fails pytest (`test_fail`), often re-emitting the identical broken edit 8–10 times.

**So the strategy's core assumption — "rich is the winnable slice beyond the 2 easy ones" — is HALF
true and that half is the wrong half.** The tasks are winnable *on paper* (small fixes). The agent is
not currently *capable of winning them* for behavioral reasons that have nothing to do with how hard
the task is. A `rich_4077`-profile task (3-line add, exact-named symbol) is the easiest thing in the
set and the agent *still* only lands it intermittently (`GEMMA_EXPERIMENT_LOG.md:160-163, 764-772`).

**Honest bottom line:** the ceiling of a rich-only strategy is gated by the agent's commit-and-edit
reliability, not by a shortage of easy rich tasks. Fix the behavior (force an early commit; make
multi-line edits byte-faithful) and ~20 rich tasks come into range. Leave the behavior as-is and the
realistic count is ~2, which is where it has sat across all runs.

---

## 1. FULL 48-ROW DIFFICULTY TABLE

Columns: `files` = source files in gold patch (test_patch excluded); `net` = added+removed lines
(`+`/`-` split); `shape`; `localization` (see §1a caveat); `class`.

| instance_id | files | net (+/-) | shape | localization | class | file(s) |
|---|---|---|---|---|---|---|
| rich_2725 | 1 | 10 (5/5) | MODIFY-SMALL | EASY | **EASY** | rich/table.py |
| rich_2943 | 1 | 2 (1/1) | ONE-LINE | MEDIUM | **EASY** | rich/style.py |
| rich_3006 | 1 | 2 (1/1) | ONE-LINE | MEDIUM | **EASY** | rich/repr.py |
| rich_3043 | 1 | 2 (1/1) | ONE-LINE | MEDIUM | MEDIUM | rich/_export_format.py |
| rich_3052 | 1 | 34 (29/5) | MULTI/SPRAWLING | EASY | HARD | rich/prompt.py |
| rich_3061 | 1 | 91 (67/24) | MULTI/SPRAWLING | MEDIUM | HARD | rich/text.py |
| rich_3063 | 1 | 4 (3/1) | MODIFY-SMALL | MEDIUM | MEDIUM | rich/markup.py |
| rich_3064 | 1 | 17 (8/9) | MODIFY-SMALL | EASY | MEDIUM | rich/markdown.py |
| rich_3067 | 1 | 2 (1/1) | ONE-LINE | MEDIUM | **EASY** | rich/highlighter.py |
| rich_3105 | 1 | 2 (1/1) | ONE-LINE | MEDIUM | **EASY** | rich/_export_format.py |
| rich_3130 | 1 | 12 (5/7) | MODIFY-SMALL | EASY | MEDIUM | rich/markdown.py |
| rich_3180 | 2 | 127 (89/38) | MULTI/SPRAWLING | MEDIUM | HARD | rich/_wrap.py; rich/cells.py |
| rich_3278 | 1 | 1 (1/0) | ADD | MEDIUM | **EASY** | rich/ansi.py |
| rich_3296 | 1 | 4 (1/3) | MODIFY-SMALL | EASY | **EASY** | rich/syntax.py |
| rich_3454 | 1 | 2 (1/1) | ONE-LINE | MEDIUM | **EASY** | rich/highlighter.py |
| rich_3468 | 1 | 42 (36/6) | MULTI/SPRAWLING | MEDIUM | MEDIUM | rich/console.py |
| rich_3469 | 1 | 2 (1/1) | ONE-LINE | MEDIUM | **EASY** | rich/markdown.py |
| rich_3470 | 1 | 2 (1/1) | ONE-LINE | MEDIUM | **EASY** | rich/console.py |
| rich_3471 | 1 | 1 (1/0) | ADD | MEDIUM | **EASY** | rich/text.py |
| rich_3472 | 1 | 4 (3/1) | MODIFY-SMALL | MEDIUM | **EASY** | rich/pretty.py |
| rich_3480 | 1 | 4 (2/2) | MODIFY-SMALL | MEDIUM | MEDIUM | rich/text.py |
| rich_3486 | 3 | 98 (74/24) | MULTI/SPRAWLING | MEDIUM | HARD | 3 files (traceback etc.) |
| rich_3506 | 1 | 17 (15/2) | MODIFY-SMALL | MEDIUM | MEDIUM | rich/segment.py |
| rich_3518 | 1 | 2 (1/1) | ONE-LINE | EASY | **EASY** | rich/table.py |
| rich_3521 | 1 | 35 (16/19) | MULTI/SPRAWLING | EASY | MEDIUM | rich/segment.py |
| rich_3535 | 2 | 8 (7/1) | MULTI/SPRAWLING | MEDIUM | HARD | rich/cells.py; rich/segment.py |
| rich_3675 | 2 | 41 (28/13) | MULTI/SPRAWLING | MEDIUM | HARD | rich/console.py; rich/diagnose.py |
| rich_3676 | 2 | 13 (12/1) | MULTI/SPRAWLING | MEDIUM | HARD | rich/default_styles.py; rich/traceback.py |
| rich_3718 | 1 | 7 (3/4) | MODIFY-SMALL | EASY | MEDIUM | rich/panel.py |
| rich_3772 | 1 | 45 (29/16) | MULTI/SPRAWLING | EASY | HARD | rich/traceback.py |
| rich_3777 | 2 | 13 (12/1) | MULTI/SPRAWLING | MEDIUM | HARD | rich/console.py; rich/diagnose.py |
| rich_3782 | 1 | 29 (24/5) | MULTI/SPRAWLING | EASY | HARD | rich/syntax.py |
| rich_3882 | 1 | 2 (1/1) | ONE-LINE | EASY | **EASY** | rich/prompt.py |
| rich_3894 | 1 | 4 (4/0) | ADD | MEDIUM | **EASY** | rich/_inspect.py |
| rich_3905 | 1 | 7 (4/3) | MODIFY-SMALL | EASY | **EASY** | rich/progress.py |
| rich_3930 | 26 | 12714 (12170/544) | MULTI/SPRAWLING | MEDIUM | HARD | 26 files (grapheme rewrite) |
| rich_3934 | 2 | 20 (17/3) | MULTI/SPRAWLING | EASY | HARD | rich/live.py; rich/live_render.py |
| rich_3935 | 1 | 16 (13/3) | MULTI/SPRAWLING | MEDIUM | HARD | rich/table.py |
| rich_3938 | 2 | 45 (40/5) | MULTI/SPRAWLING | MEDIUM | HARD | rich/console.py; rich/segment.py |
| rich_3942 | 2 | 70 (43/27) | MULTI/SPRAWLING | EASY | HARD | rich/default_styles.py; rich/markdown.py |
| rich_3944 | 1 | 2 (1/1) | ONE-LINE | MEDIUM | **EASY** | rich/cells.py |
| rich_3953 | 1 | 26 (16/10) | MULTI/SPRAWLING | MEDIUM | MEDIUM | rich/cells.py |
| rich_4006 | 1 | 45 (33/12) | MULTI/SPRAWLING | MEDIUM | MEDIUM | rich/cells.py |
| rich_4070 | 9 | 128 (71/57) | MULTI/SPRAWLING | EASY | HARD | 9 files (import-defer perf) |
| rich_4075 | 1 | 15 (12/3) | MULTI/SPRAWLING | MEDIUM | MEDIUM | rich/console.py |
| rich_4076 | 1 | 6 (3/3) | MODIFY-SMALL | MEDIUM | **EASY** | rich/ansi.py |
| rich_4077 | 1 | 3 (3/0) | ADD | MEDIUM | **EASY** | rich/file_proxy.py |
| rich_4079 | 1 | 7 (4/3) | MODIFY-SMALL | MEDIUM | **EASY** | rich/markdown.py |

### 1a. Measurement caveat on the "localization" column (IMPORTANT — pressure-tested)

The brief asked for localization difficulty from the `problem_statement`. **I pressure-tested this
before trusting it and it fails as an independent axis.** The rich problem statements are **GitHub PR
titles + an issue link** (median length 138 chars; 22/48 under 120 chars; `hints_text` is empty for
all 48). They are not SWE-bench-style verbose bug reports. Example: `rich_4077`'s entire statement is
"proxy isatty — Fixes .../issues/4041".

My first automated pass scored terse titles as "HARD to localize" and consequently misclassified
`rich_4077` (the one task we *know* the agent can solve) as HARD. That is the exact "name it before
pressure-testing" failure this project was burned by twice, so I discarded that pass. The corrected
heuristic treats a title that names the subsystem/symbol ("proxy isatty", "Segment.split_cells fix",
"fix for markdown table") as a localization *pointer*. Under the corrected pass the known anchors
(`rich_4077/4079/4076/3469`) all land EASY and the 9-file perf refactor `rich_4070` lands HARD, which
matches reality.

**Stated uncertainty:** localization is the *low-confidence* axis — it is inferred from PR-title
wording, and the agent at task time does not receive the gold patch, only this title + the repo. The
**high-confidence, reliably-measured axis is edit mechanics** (file count, hunks, net lines), which is
also precisely the agent's proven failure surface. The `class` column is therefore driven primarily by
edit mechanics, with localization as a secondary modifier only.

---

## 2. COUNTS

Measured from gold patches (reliable):

- **EASY: 20 / 48** (single file, 1 hunk, ≤~10 net lines, or a small ADD — the rich_4077 profile)
- **MEDIUM: 12 / 48** (one file, a few hunks, some tracing)
- **HARD: 16 / 48** (multi-file, sprawling, or large single-file rewrites)

Shape histogram: ADD 4, ONE-LINE 11, MODIFY-SMALL 12, MULTI/SPRAWLING 21. File-count: 37/48 are
single-file; the extreme is `rich_3930` (26 files / 12.7k lines — a full grapheme-handling rewrite,
uncatchable by a 15-call agent).

---

## 3. IMPLIED WINNABLE-SLICE SIZE → ROUGH PUBLIC-LB CEILING

Scoring is resolves / 129 total tasks. These are **rough upper bounds** (they assume the agent
converts every task in a class, which §4 shows it does not):

- EASY only: **20 / 129 ≈ 0.155** (rough ceiling)
- EASY + MEDIUM: **32 / 129 ≈ 0.248** (rough ceiling)

**Label these as paper ceilings, not projections.** They describe how many rich fixes are *small
enough* to be winnable, not how many the agent *will* win. The live-best score across all runs is
**0.12 with 2/6 resolves** (`GEMMA_EXPERIMENT_LOG.md:27, 163`), i.e. the realized rate is far below
even the EASY-only paper ceiling. The gap between 0.155 and the realized ~0.02 (2/129) is the
commitment/edit problem, quantified.

---

## 4. CROSS-REFERENCE VERDICT: commitment vs difficulty (the key disambiguation)

For the rich tasks with agent traces, I compared the **gold-patch class** against the
**externally-judged outcome** (hermetic pytest `test_fail` / `no_patch` / resolved, from
`Gemma/local_eval/_batch_*.txt` and `GEMMA_EXPERIMENT_LOG.md`). `no_patch` = agent never committed an
edit (search-death). `test_fail` = agent committed a patch that failed pytest (edit-fidelity /
correctness). These are the two distinct non-difficulty failure modes.

| task | gold class | gold fix | observed outcome | failure type |
|---|---|---|---|---|
| rich_4077 | **EASY** | 3-line ADD (`isatty` method on FileProxy) | resolves under v1/v3/v6, breaks under v2/v4; often `test_fail` or `no_patch` | **COMMITMENT / variance** — fix is trivial, agent just doesn't reliably commit the right edit |
| rich_4079 | **EASY** | 7-line markdown edit | resolved only under v6 prompt; else fails on multi-line edit | **EDIT-FIDELITY** — byte-faithful multi-line edit |
| rich_4076 | **EASY** | 6-line ansi rstrip/newline fix | never resolved in logs; candidate | **EDIT-FIDELITY** (gold is easy) |
| rich_3469 | **EASY** | 2-line markdown space fix | never resolved in logs | **COMMITMENT** (gold is trivial) |
| rich_4070 | **HARD** | 9 files / 128 lines import-defer perf refactor | never resolved; burns all calls exploring | **GENUINE DIFFICULTY** (also commitment-tax) |

Additional direct evidence from the local-eval tool traces (`_batch_all.txt`, `_batch_baseline.txt`),
all on tasks whose gold fix is EASY (1–2 net lines):

- **rich_3278** (gold = 1-line ADD): agent spends all 15 calls issuing escalating `search_code` regex
  (`\x1b\[\d*` variations), never edits → `no_patch`. Pure search-death on a one-line fix.
- **rich_2943** (gold = 1-line cache clear): agent finds the line, then emits the *identical*
  `edit_file(style._hash=None)` **10 times in a row** and still `test_fail`. The edit tool call is not
  taking effect / not byte-faithful; the agent cannot tell and loops.
- **rich_3470** (gold = 1-line): loops `search_code('record_capture')` 15× → `no_patch`.
- **rich_3471** (gold = 1-line ADD): repeats a `for content, style in tokens:` edit with escaped-vs-raw
  `\n` confusion, never lands → `no_patch` / `err`.

**Verdict:** For every rich task the agent attempted-and-failed where the gold fix is EASY, the
failure is **behavioral (won't-commit or bad-edit), not difficulty.** The only genuine-difficulty
failure among the traced set is `rich_4070`, which is correctly a HARD multi-file refactor. This is
the disambiguation the brief asked for, and it lands firmly on: **rich is failing from won't-commit /
can't-edit-faithfully, not from real hardness.**

---

## 5. RANKED TARGET LIST — top 15 easiest rich tasks to point the agent at

Ranked by edit mechanics (single file, single hunk, smallest net edit = least room for the agent's
search-death and multi-line-edit failures). Each is the `rich_4077` profile or tighter.

| # | task | file | fix | why it's easy |
|---|---|---|---|---|
| 1 | rich_3471 | rich/text.py | +1 (ADD) | one added line, exception guard in `append_tokens`; title names the method |
| 2 | rich_3278 | rich/ansi.py | +1 (ADD) | single added strip line; subsystem named |
| 3 | rich_3944 | rich/cells.py | 1/1 | one-line cell-width fix |
| 4 | rich_3882 | rich/prompt.py | 1/1 | one-line prompt-markup escape; title + body point to prompt |
| 5 | rich_3518 | rich/table.py | 1/1 | one-line add_row column highlight; `fix(table):` scoped title |
| 6 | rich_3454 | rich/highlighter.py | 1/1 | one-line hyperlink highlighter regex fix; issue # in title |
| 7 | rich_3470 | rich/console.py | 1/1 | one-line record/capture fix (currently search-deaths — pure commitment) |
| 8 | rich_3469 | rich/markdown.py | 1/1 | one-line superfluous-space fix |
| 9 | rich_2943 | rich/style.py | 1/1 | one-line cache clear (currently emits right edit but it won't land — edit-tool fidelity) |
| 10 | rich_3105 | rich/_export_format.py | 1/1 | one-line export-template fix; has a structured bug-fix body |
| 11 | rich_3067 | rich/highlighter.py | 1/1 | one-line URL-tilde regex fix; issue # named |
| 12 | rich_3006 | rich/repr.py | 1/1 | one-line repr fix for custom classes; issue # named |
| 13 | rich_4077 | rich/file_proxy.py | +3 (ADD) | the proven anchor; add `isatty` delegate — resolve it *reliably* first |
| 14 | rich_3894 | rich/_inspect.py | +4 (ADD) | small added guard for unusual `__qualname__` |
| 15 | rich_3296 | rich/syntax.py | 4 (1/3) | small single-hunk syntax padding fix; `fix(syntax):` scoped title |

(Next tier, still EASY: rich_3905 panel/progress blank-line, rich_3472 pretty dataclass field,
rich_4076 ansi newlines, rich_4079 markdown inline table, rich_2725 table box order.)

---

## 6. BOTTOM LINE

**Is the rich-only path to #1 realistic?** Not with the current agent. The number of *clearly
mechanically-winnable* rich tasks is ~20 (paper ceiling ≈ 0.155 LB), and a further ~12 are plausible
(≈ 0.248). But the realized count across every logged run is **2** (rich_4077, rich_4079), and the
live-best is **0.12**. The slice exists; the agent does not harvest it.

**Is the dominant rich failure mode difficulty or commitment?** **Commitment / edit-mechanics, decisively.**
The externally-judged traces show the agent search-deathing (`no_patch`) or emitting non-landing /
non-byte-faithful edits (`test_fail`) on tasks whose gold fix is literally one line. Genuine difficulty
only explains the HARD tasks (multi-file refactors like rich_4070, rich_3930), which no 15-call agent
should be expected to clear anyway.

**What this means for strategy (recommendation, not implemented):**

1. The lever is **not** finding more rich tasks — it is making the agent **commit an edit early and
   emit it byte-faithfully.** The §4 traces are the proof: fix the loop where the agent re-issues the
   same `edit_file` 8–10 times without it taking effect, and where it escalates `search_code` instead
   of editing. (Note `GEMMA_EXPERIMENT_LOG.md:694, 712-723` already identifies "compulsive
   reproduction" and explore-death as root causes; this map corroborates it against gold-patch size.)
2. The user's instinct — "we've tried the commit rule before and it ignored" — is consistent with the
   evidence: a prompt rule alone did not fix it (v4 regressed, broke rich_4077). The traces suggest the
   failure is partly in the **edit tool mechanics** (identical edit emitted repeatedly with no effect),
   not only in the model's willingness. That is a harness bug to debug, per the accountability rule
   that a gate/execution failure on a sound idea is a debugging task, not a verdict on the idea.
3. Target the §5 list in order. Bank `rich_4077` as a **reliable** (not flaky) resolve first; it is the
   cleanest test of whether the commit-and-edit fix actually works, at zero risk to live-best.

**Measured vs inferred, stated plainly:**
- MEASURED: patch sizes, class counts (20/12/16), the 2-ever-resolved fact, and the per-task
  `no_patch`/`test_fail` outcomes with their tool traces.
- INFERRED: the localization column (from PR-title wording), the "what the agent *could* resolve if the
  commit/edit bug were fixed" slice size, and the paper LB ceilings. These are hypotheses about
  capability, not leaderboard-confirmed results.

---

### Appendix — provenance / read-only scripts used (safe to delete)
`Gemma/_rich_difficulty_probe.py`, `_rich_localize_probe.py`, `_rich_reclass.py`, `_rich_ps_audit.py`,
`_trace_outcomes.py`, `_trace_outcomes2.py`, `_rich_report_data.py` and their JSON outputs
(`_rich_probe_out.json`, `_rich_classified.json`, `_rich_classified2.json`). None modified
`tasks.jsonl` or any competition artifact. Ground-truth outcome evidence read from
`Gemma/local_eval/_batch_all.txt`, `_batch_baseline.txt`, `_batch_summary.txt`, and
`Gemma/GEMMA_EXPERIMENT_LOG.md`.
