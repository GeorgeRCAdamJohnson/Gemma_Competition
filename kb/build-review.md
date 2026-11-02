# Gemma auditor build — Stage C review (deliverables 1–3, first iteration)

The coder built the Gemma knowledge-base builder (`Gemma\kb\build_kb.py` + `kblib\`), the
`gemma-auditor` agent file, and the 4-step `gemma-audit` workflow recipe, then recorded what it ran in
`Gemma\kb\build_verification.md`. This review reads the diff/on-disk artifacts plus that evidence, and
re-confirms the blocking criteria with narrow, cheap spot-checks (recipe lint, gold count, the acceptance
suite over the already-built KB, two leakchecks, and an idempotence re-run). No heavy replay suite or full
rebuild-from-cold was performed beyond the ~12 s `build` needed to prove idempotence directly.

Watch for: the verification note claimed two consecutive builds were IDENTICAL, and my first re-run reported
`DIFFERENT: KB_SUMMARY.md` — but that was **live input drift** (a transient `local_eval/runs/g12p_on.log`
appeared then vanished between builds), not a non-idempotent builder. Two back-to-back builds against a
stable input set are byte-identical (confirmed below). The recorded rich-clone HEAD is already stale
(`36fe3f7c…` in the note vs `fde5d6ee…` now); both clones are clean, the builder never touches them, so this
is volatile external state, not a defect.

**Verdict**: APPROVED

## High-level view

The idempotence bar — the one that would be fatal if broken — holds. Back-to-back `build` runs produce
byte-identical generated outputs (the idempotence check strips only the two stamp lines) and `check-fresh`
returns FRESH. The one apparent divergence I hit was the discovery layer correctly reacting to a file that
appeared and disappeared in the user's live `local_eval/runs/` directory; the freshness fingerprint is
working as designed, and the builder is deterministic given a fixed input set.

The recipe is schema- and template-legal. Six static lint checks pass: exact top-level keys, exact inputs
map, step ids `rebuild-kb/audit/refute/final`, no step-level `input` key, P1 carries the replay
deadline/lock-wait flags, P2 keeps the unwrap instruction next to `{{rebuild-kb.output}}`, and the audit vs
refute models are from different families (claude-opus-5 vs gpt-5.6-sol). Template references resolve
backward only — `audit_report` is referenced in P3/P4 but never in its own step P2, so no step references its
own artifact.

No scorer-gaming surface exists in the tooling. `leakcheck --scope tooling` on both the agent file and the
recipe returns CLEAN — no gold hunks or problem-statement fingerprints are embedded in any config the agent
or workflow carries. The builder writes no agent configs at all.

Writes stayed inside the allowed envelope. The only artifacts outside `Gemma\kb\` are the agent file and the
recipe JSON, both explicitly permitted. `kb/` is untracked in git, which is why there is no tracked diff for
it; the evidence is the files on disk plus the verification note.

The honestly-scoped-out items (git-worktree replay engine, gold-first validation, near-miss fuzzy matcher,
dev-harness AST pass, Kaggle pulls) remove two blocking risks by construction: no replay ran, so there is no
gold-first violation to check and no agent-authored shell was executed. The note states each omission plainly
rather than reframing it as done.

<details>
<summary>Issues (3)</summary>

1. **Stale recorded rich-clone HEAD** (NIT, confirmed) — the note records rich at `36fe3f7c…`; it is now
   `fde5d6ee…`. Both are clean and the builder never touches the clones, so this is volatile user state. No
   action needed beyond noting that recorded clone HEADs are snapshots, not pins.
2. **reference-logs list is sensitive to transient files** (NIT, confirmed) — a file appearing/vanishing in
   `local_eval/runs/` changes the KB_SUMMARY reference-logs line and (correctly) trips freshness. This is
   dynamic discovery working as designed; worth a one-line note in the summary that this list is a live
   snapshot.
3. **No tracked git diff for the KB** (NIT, confirmed) — `kb/` is untracked, so the review relies on on-disk
   artifacts + the verification note rather than a diff. Not a defect for a from-scratch first iteration;
   flagged only so future iterations are reviewed against a committed baseline.

</details>

<details>
<summary>Details</summary>

### Idempotence holds; the apparent divergence was live input drift

The verification note (`build_verification.md`, "Idempotence (hard bar — MET)") claims two consecutive
builds snapshotted with `tests\idempotence_check.py` compared IDENTICAL. My first independent check reported
`DIFFERENT: KB_SUMMARY.md`. Rather than trust either the note or the single contradicting run, I traced the
exact diff: the only non-stamp difference was one entry in the `reference-logs` list —
`local_eval/runs/g12p_on.log` present in one build, absent in the other. That file is under the live Gemma
tree, not under `kb\`, and it appeared then disappeared while I was running builds (the design itself, §0/§2.1,
documents that "data grows several times a day"). Two builds run back-to-back against a stable input set
compared **IDENTICAL** (exit 0) and `check-fresh` returned **FRESH**. The idempotence check excludes only
`build_stamp.json` and the two `<!-- build-stamp:` / `Build stamp:` lines, and everything else is a pure
function of inputs. The builder is deterministic; the discovery/freshness fingerprint correctly detected the
transient input. This is the opposite of the "non-idempotent builder" blocking condition — the fingerprint is
what makes a mid-build input change visible.

The note also records a lock bug found and fixed during verification (`kblib/lock.py` over-reported pid
liveness on Windows). The current builds acquire, update the stamp, and leave no `.build.lock`, consistent
with that fix.

### Recipe is schema- and template-legal

`python -m pytest tests/test_recipe.py -q` → 6 passed. The checks assert: top-level keys are exactly
`{name, description, inputs, steps}`; inputs are exactly `{proposal_path: file, slug: string}`; step ids are
`rebuild-kb, audit, refute, final` with no `input` key on any step; agents are `wf-coder / gemma-auditor /
gemma-auditor / wf-coder`; audit and refute model families differ. The template-reference check walks every
`{{…}}` in prompts and artifact-path values: `*.output` must name an earlier step, `artifacts.*` must be
declared by an earlier step, bare names must be inputs, and a step may not reference its own artifact in its
prompt. This matches the engine semantics the design pinned in §2.16/§18 (captured outputs wrapped in prompts
but raw in artifact paths; artifact references look strictly backward). P2 references `{{rebuild-kb.output}}`
and carries the "wrapped … ignore the tags" unwrap instruction; `artifacts.audit_report` is referenced only
in P3 and P4.

### No gold/problem-statement leakage in config

`build_kb.py leakcheck --scope tooling` returns `LEAKCHECK CLEAN` on both the agent file and the recipe JSON.
`--scope tooling` permits bare task ids (the agent/recipe legitimately mention task ids like `rich_4079`) but
still flags gold hunk text and problem-statement fingerprints. Neither tooling file carries gold. The builder
emits no agent configs, so the only scorer-gaming surface is these two files, and both are clean.

### Gold coverage and the acceptance suite

`tasks_gold.json` holds **129** tasks (48 `Textualize/rich` + 67 `fastapi/fastapi` + 13 `psf/requests` +
1 `encode/httpx`), meeting the "all 129 tasks" bar. `python -m pytest tests -q` → **30 passed** against the
already-built artifacts (0.41 s, no replay), corroborating the note's claim. The load-bearing facts it
pins: fact-1 (v6b rich_4079 resolved False, 28 harness tool_calls, 30 trace calls, refusal at step_id 31,
count-model residual 0), fact-7 (129 gold, rich `ast@base_commit` ≥ 46), fact-8 (v19_lora rich_4070, 24
calls, 18 arg-rejected, residual 0), the count-model ≥ 95 % bar, and fact-14 (submit_v6z/out_v6z failed → 0
rows). The two rich AST misses are honestly characterized as pure new-file additions with no base file to
parse — a stated near-miss against fact-7's "every rich task" wording, not a hidden gap.

### Near-miss rows cite step_ids where a trace exists

236 near_miss rows, 159 with a trace. Traced rows that reached a stage carry `step_id` and `call` (111 of 159
mention a step_id). The v6b rich_4079 row carries `TRIED_APPLY` at step_id 31 and `WROTE_GOLD_CHANGE` at
step_id 31 (`where: args`), `stopped_by: REFUSED_CALLS`, matching fact-1. Rows with no trace (pasted logs)
honestly carry `confidence: low (no trace)` and `stopped_by: UNKNOWN (no trace)` and cite no step_id, because
there is nothing to cite. The design marks the trace-derived stages `confidence: low` (the nm-3 line-level
fuzzy matcher is scoped out), which the note states plainly.

### Baseline conflict surfaced, not adopted

The KB_SUMMARY banner reads: `BASELINE: v6w @ 0.15 (curated+submissions.csv, submission 57098497) —
gemma-submission-protocol.md still says v6 @ 0.12 and is STALE; resolved in favour of the log/submissions`.
The LB section lists the submissions.csv COMPLETE scores and flags the PENDING branch_final (ref 57146757)
as `baseline-dependent verdicts = NEEDS-DATA until it scores`. This is the required BASELINE CONFLICT
treatment: the v6w @ 0.15 vs v6 @ 0.12 conflict is reported with the steering file named as stale, and the
builder never writes `curated\run_labels.json` or `curated\submissions.csv` (read-only, per the write
allowlist). The agent file reinforces that a different live-best is "a reported finding, never silently
adopted".

### Coverage accounting

KB_SUMMARY §2 accounts for every discovered source: 30 run-dirs parsed, 1 run-dir-failed
(`submit_v6z/out_v6z`), 3 run-dir-empty (`submit_v22/out_v22`, `v2_gate_s05`, `v2_gate_s05b`), 11 pasted-logs,
a reference-logs list (not our runs → 0 rows), 2 staged-submissions, 159 trace files parsed, 236 runs rows,
and `beyond walk depth: []`. The §3 matrix reports 25 tasks across 40 run columns; all 17 distinct rich tasks
that appear in any run row have matrix rows. Log versions with no local on-disk data land in the LB/claims
sections (e.g. the pasted-log version tokens) rather than being dropped.

### Harness semantics answered with citations

The count-model (cm-2) residual is 0 on 159/159 traces that carry a harness `tool_calls` value — the model is
`harness == trace_calls − free(submit_patch/get_status) − refused(BudgetExceeded) − arg_rejected`, which
answers the "call-count puzzle" (why harness 28 < trace 30 for v6b: one free submit + one refusal). The
scored-state question (no successful submit) is answered: last OK `submit_patch` snapshot else the working
tree, encoded in `trace.scored_state_basis` / `post_submit_edits`, cited to README §6.1/§8.1. The note is
honest that the `swegemma` counting code and the framework arg-rejection layer are not on disk, and that the
`apply_replacement` empty-`old_string` emulation (edit.py L408–414) is not implemented this iteration.

### Clones clean; recorded rich HEAD already stale

Read-only `git` confirms both clones have an empty `status --porcelain`. fastapi is at `740ec278…` (matches
the note and the design). rich is at `fde5d6ee…`, **not** the `36fe3f7c…` the note recorded hours earlier —
the user moves this checkout between tasks (design §2.10 saw it at `c478588f`). Both are clean, the builder
runs only `pull`/replay against clones and neither ran this build, so the clone state is untouched. This is
volatile external state the note already disclaimed; it is a NIT that the recorded HEAD is stale, which simply
confirms clone HEADs are snapshots.

### Agent file ↔ recipe ↔ KB consistency

The agent file's CLI (`build / check-fresh / card / claims / leakcheck / report-path / verdict / pull`),
report path convention (`KB\audits\DATE-slug[-refute|-final].md`), matrix letters, KB layout, and absolute
paths all match the builder's actual subcommands and the recipe's step prompts. The recipe's P1 uses
`B build --replay --deadline-s 1500 --lock-wait-s 120`; the builder accepts those flags (even though the
replay phase is a no-op this iteration, so `replays_pending=0`). The agent's `tools: [read, write, shell]`
front-matter is present. No inconsistency between the built KB and the tooling that references it.

### Scoped-out work removes two blocking risks by construction

Because no replay engine ran, there is no agent replay counted without a gold patch passing first (no
gold-first violation possible), and no agent-authored shell was executed outside any allowlist (no replay
checkout path was entered). The note lists these omissions — replays/CloneGuard, near-miss fuzzy matcher +
cross-task FP control, static edit reconstruction, dev-harness AST pass, full claims column-mapping, Kaggle
pulls — plainly as next-iteration work, consistent with the accountability rule that honest nulls are
results.

</details>

<details>
<summary>File map</summary>

- `Gemma\kb\build_kb.py` — single idempotent entrypoint (build/check-fresh/report-path/preflight/verdict/
  leakcheck/card/claims/pull). Stdlib-only, deterministic ordering, exclusive lock.
- `Gemma\kb\kblib\*` — parser/render/verdict/leak helpers (not individually re-read; behavior exercised via
  the acceptance suite).
- `Gemma\kb\tests\*` — unit + recipe-lint + slow acceptance facts + idempotence snapshot/compare helper.
- `Gemma\kb\{runs.jsonl, tasks_gold.json, near_miss.jsonl, log_claims.{md,jsonl}, KB_SUMMARY.md,
  build_meta.json, build_stamp.json, build_log.txt}` — generated outputs (re-generated during this review's
  idempotence check; back-to-back builds byte-identical).
- `Gemma\kb\build_verification.md` — the coder's recorded evidence (read, cross-checked).
- `.kiro\agents\gemma-auditor.md` — auditor agent (leakcheck CLEAN).
- `.kiro\workflows\gemma-audit.workflow.json` — 4-step recipe (recipe-lint 6/6, leakcheck CLEAN).

No git diff: `Gemma\kb\` is untracked. Review based on on-disk artifacts + the verification note.

</details>
