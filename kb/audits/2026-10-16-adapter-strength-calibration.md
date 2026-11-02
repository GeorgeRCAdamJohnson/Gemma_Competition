VERDICT: REVISE

# AUDIT — adapter strength/span calibration FREE gate (2026-10-16, slug `adapter-strength-calibration`)

Proposal: `Gemma\kb\proposals\2026-10-16-adapter-strength-calibration-gate.md` (read-only; unmodified).
KB: FRESH (`python kb\build_kb.py check-fresh` → `FRESH`, exit 0), `inputs_fingerprint=9f2e9311cea4`,
built 2026-10-16T07:16:10Z.
Steering read in full: `.kiro\steering\reverse-engineering-accountability.md`,
`.kiro\steering\gemma-submission-protocol.md`.

Short version: the DIRECTION is sound and genuinely unmeasured — no adapter has ever been served at the
v6w config, and no strength below α/r = 0.5 has ever been served at all. But three of the proposal's own
four open questions resolve against it on data already on disk: (1) its admissibility bar labels a
**no-adapter** run "not admissible / over-strong" on two independent exact-replicate pairs, so the bar is
noise-dominated; (2) its mid arm (α/r ≈ 0.5) has already been measured against a byte-identical
no-adapter control and already fails that bar, so one of two arms is a re-run with a known answer;
(3) the task set it names has never been run by any config, while a 5-run no-adapter band already exists
on the v6w set and a byte-identical no-adapter control already exists for the adapter set. Fixable
offline; nothing here needs new data.

---

## 1. Suggestion restated

Spend one FREE 5-task rich gate measuring adapter SERVE-STRENGTH (no training, no scored slot):
ARM 0 = no-adapter v6w (28/8/80/240, 9 tools, thinking 1024); ARM 1 = a known on-disk multi-layer adapter
at effective α/r ≈ 0.25; ARM 2 = the same weights at α/r ≈ 0.5. Preferred artifact: the 110-module r32
adapter in `submit_v6z_on_v6w\lora025` (175 MB), alternative the 410-module artifact in `v2_gate_out2`
(979 MB). Only `lora_alpha` varies across adapter arms (`train\make_variant.py`). Proposed set:
rich_4077 (control), rich_4079, rich_3469, rich_3675, rich_3934. Bar: strength `s` is ADMISSIBLE iff on
≥4/5 tasks its edit-attempt rate AND patch_chars are not below ARM 0 and it does not lose rich_4077;
OVER-STRONG iff it drops tool_calls / patch_chars / edit-attempts materially below ARM 0 on ≥2 tasks or
loses rich_4077. Outcome = the admissible band; an empty band is an accepted null. Four questions are
explicitly handed to this audit: NEW-vs-RE-RUN, can one gate serve ≥2 strengths, which artifact/scales,
is the bar measurable from gate output.

## 2. Prior art

| lever | tag | evidence |
|---|---|---|
| Multi-layer adapter served on the scored 31B stack | **RE-RUN** (4 prior runs) | `v2_gate_out2`, `v2_gate_s05c`, `Outputs\v19_lora`, `submit_v6z_on_v6w\lora025\out` — all served a multi-layer PEFT adapter on 4×L4 31B W4A16. [MEASURED: the four `submission\adapters\main_lora\adapter_config.json` files] |
| `make_variant.py` serve-scale (α rewrite, weights untouched) | **RE-RUN** | `adapter_v2_s05` + `v2_gate_s05/s05b/s05c` (410-mod, α64→16) and `adapter_dataset-r32-s0.25` + `lora025` (110-mod, α64→16) are both on disk as α-rewritten variants of shipped artifacts. [MEASURED] |
| Adapter at α/r = 0.5 | **RE-RUN, already judged against a matched control** | `v2_gate_s05c` (410-mod, r32/α16) and `lora025` (110-mod, r32/α16). §6 shows s05c already fails the proposal's own bar against a byte-identical no-adapter control. [MEASURED] |
| Adapter at α/r = 2.0 | **RE-RUN** | `v2_gate_out2` (410-mod α64) and `Outputs\v19_lora` (110-mod α64). [MEASURED] |
| Adapter at α/r **< 0.5** (the proposal's ARM 1) | **NEW** | no `adapter_config.json` anywhere under `Gemma\**` has α/r < 0.5 except the layer-0 sample stub (r4/α8 = 2.0). Nothing below 0.5 has ever been served. [MEASURED: full on-disk scan, §6 test T1] |
| Any adapter at the **v6w** config | **NEW** | every adapter arm ever run used 15 calls / 8 min / 24 turns / 120 s, 6144 out-tokens, `frequency_penalty 0.4`, thinking 256 and prompt sha `d7777085b575`. v6w is 28/8/80/240, 8192 out-tokens, no frequency penalty, thinking 1024, prompt sha `9c2fa3587f25`. [MEASURED: §6 test T2] |
| In-run no-adapter control arm next to adapter arms | **NEW as an in-run arm**, but a byte-identical **historical** control already exists | `Outputs\v19` is no-adapter with prompt sha `d7777085b575` and config 15/8/24/120/think-256 — identical to all four adapter arms on every KB config field, on the same 5-task set. [MEASURED] |

Net: the proposal is a VARIANT overall. Exactly two things in it are NEW — strength below 0.5, and any
adapter at the v6w config. Its ARM 2 is a RE-RUN whose answer is already on disk (§6).

## 3. Ground truth per task (gold + test_patch)

From `kb\tasks_gold.json` + `Gemma\comp_files\tasks.jsonl` [all MEASURED]; no gold text is reproduced.

| task | class | gold files | hunks | added/removed | F2P test file → added test |
|---|---|---|---|---|---|
| rich_4077 | EASY (`RICH_48_DIFFICULTY_MAP.md:94`, kb `EASY`) | `rich/file_proxy.py` | 1 | 3/0 (pure ADD) | `tests/test_file_proxy.py` → `test_isatty` |
| rich_4079 | EASY (`:95`) | `rich/markdown.py` | 1 | 4/3 | `tests/test_markdown.py` → `test_inline_code_in_table_cells` |
| rich_3469 | EASY (`:64`) | `rich/markdown.py` | 1 | 1/1 (one-line) | `tests/test_markdown.py` → `test_table_with_empty_cells` |
| rich_3675 | **HARD** (`:74`) | `rich/console.py`, `rich/diagnose.py` | 5 | 28/13 | `tests/test_console.py` → **82 added tests** in the test_patch |
| rich_3934 | **HARD** (`:84`) | `rich/live.py`, `rich/live_render.py` | 3 | 17/3 | `tests/test_live.py` → `test_live_empty` |
| rich_3278 | EASY (`:60`) | `rich/ansi.py` | 1 | 1/0 | `tests/test_ansi.py` → `test_strip_private_escape_sequences` |
| rich_3471 | EASY (`:66`) | `rich/text.py` | 1 | 1/0 | `tests/test_text.py` → `test_append_tokens` |
| rich_3882 | EASY (`:80`) | `rich/prompt.py` | 1 | 1/1 | `tests/test_prompt.py` → `test_prompt_confirm_markup` |
| rich_4076 | EASY (`:93`) | `rich/ansi.py` | 1 | 3/3 | `tests/test_ansi.py` → `test_decode_newlines` |
| rich_4070 | HARD (`:110`) | 9 files incl. `rich/console.py`, `rich/emoji.py` | 33 | 71/57 | `tests/test_console.py`, `tests/test_syntax.py`, 0 added tests |

Two notes that bear on the proposed set. rich_3675's test_patch rewrites `tests/test_console.py` with 82
added tests, so its resolve verdict rides on a very large Pass-to-Pass surface — a poor instrument for a
calibration read [MEASURED]. And local gold-first replay coverage is `kb\replays\gold\` = {rich_3469,
rich_4070, rich_4076, rich_4079} only: the proposal's control task **rich_4077 has no gold-valid local
replay**, so a disputed resolve on the control cannot be re-checked offline [MEASURED].

## 4. Behavior per task per run (the arms that already exist)

All four adapter arms share one config and one prompt sha; `Outputs\v19` is the byte-identical no-adapter
control. Task set {rich_3469, rich_4070, rich_4076, rich_4077, rich_4079} [MEASURED: `kb\runs.jsonl`,
`config.prompt_sha256`, `kb\build_kb.py card`].

| run | adapter served | α/r | per-task (res, calls, patch_chars, n_edit, malform share, end) |
|---|---|---|---|
| `Outputs/v19` | none | — | 3469 F/15/0/1/0.00/CALL_CAP · 4070 F/15/1047/5/0.10/CALL_CAP · 4076 F/15/0/3/0.053/CALL_CAP · **4077 R**/13/324/5/0.00/SUBMITTED · 4079 F/15/0/1/0.00/CALL_CAP |
| `v2_gate_out` | competition **sample layer-0 stub** r4/α8, 2 modules, 217,672 B | 2.0 | 3469 F/15/0/4/0.05 · 4070 F/12/514/12/**0.435**/TURN_CAP · 4076 F/14/473/1/0.177 · **4077 R**/5/396/3/0.00 · 4079 F/15/0/6/**0.458**/CALL_CAP |
| `v2_gate_out2` | 410-module r32/α64, 979,558,760 B | 2.0 | **all 5**: F / calls=0 / 0 chars / 0 edits / malform **1.00** / `NUDGE_EXHAUSTED` |
| `v2_gate_s05c` | same 410-module weights, α rewritten to 16 | 0.5 | 3469 F/15/0/0/0.105 · 4070 F/8/1047/16/**0.609**/TURN_CAP · 4076 F/15/0/0/0.00 · **4077 R**/15/324/5/0.00/CALL_CAP · 4079 F/15/0/0/0.00 |
| `Outputs/v19_lora` | 110-module r32/α64, 175,341,968 B | 2.0 | 3469 F/15/0/0/0.158 · 4070 F/6/0/18/**0.750** · 4076 F/**calls=0**/0/0/**1.00**/`NUDGE_EXHAUSTED` · **4077 R**/12/324/4/0.188 · 4079 F/15/0/6/**0.458** |

Raw-trace spot checks (KB rows are an index, not the evidence):
`Gemma\v2_gate_out2\results\traces\trace_rich_4077.json` — 12 steps, **no step carries a `tool_calls`
field**, `model_name='main_lora'` at step_id=3, `final_metrics.total_steps=12` → the adapter WAS served
and zero structured calls were emitted [MEASURED].
`Gemma\Outputs\v19_lora\results\traces\trace_rich_4076.json` — 11 steps, no `tool_calls` field on any
step, `model_name='main_lora'` step_id=3 [MEASURED].
`Gemma\Outputs\v19\results\traces\trace_rich_4070.json` — 25 steps, 20 carry `tool_calls`,
`model_name='/kaggle/input/models/google/gemma-4/other/gemma-4-31b-it-qat-w4a16-ct/2'` → no adapter
[MEASURED]. `Gemma\v2_gate_s05c\results\traces\trace_rich_4070.json` — 30 steps, 22 with `tool_calls`,
`model_name='main_lora'` [MEASURED]. `Gemma\submit_v6w\out_v6w\results\traces\trace_rich_4077.json` — 28
steps, 24 with `tool_calls`, base model id, system prompt step_id=1 states a 28-call budget [MEASURED].

Run-level aggregates (the numbers a calibration should actually read):

| run | adapter | resolves | Σ patch_chars | tasks with ≥1 edit attempt | Σ n_edit | mean malform | tasks with calls=0 |
|---|---|---|---|---|---|---|---|
| `Outputs/v19` | none | 1/5 | 1371 | 5/5 | 15 | 0.031 | 0 |
| `v2_gate_out` | layer-0 stub | 1/5 | 1383 | 5/5 | 26 | **0.224** | 0 |
| `v2_gate_s05c` | 410-mod α/r 0.5 | 1/5 | 1371 | **2/5** | 21 | **0.143** | 0 |
| `Outputs/v19_lora` | 110-mod α/r 2.0 | 1/5 | **324** | 3/5 | 28 | **0.511** | 1 |
| `v2_gate_out2` | 410-mod α/r 2.0 | 0/5 | **0** | **0/5** | 0 | **1.000** | **5** |

[MEASURED] Two things follow. The proposal's core premise — "lowering effective strength moved it from
paralyzed toward acting" — is **SUPPORTED** at the run level for the 410-module artifact (α/r 2.0 → 0.5
takes malform 1.000 → 0.143, Σ chars 0 → 1371, calls=0 tasks 5 → 0). And α/r = 0.5 is still 4.6× the
matched control's malformation and loses edit activity on 3 of 5 tasks, so the usable band, if any, lies
**below** 0.5 — exactly where nothing has ever been served.

## 5. Failure classification (§10 definitions, verbatim)

- `v2_gate_out2` × rich_3469/4070/4076/4077/4079 — **LOCATE / NO_GOLD_FILE**, decided by zero structured
  tool calls with `end_reason=NUDGE_EXHAUSTED` and malformation share 1.0. **Not INFRA**: the submitted
  config (the adapter) caused it, so it is stage-classified and carries `~` [MEASURED:
  `kb\runs.jsonl#row_id=v2_gate_out2::rich_*`, `kb\near_miss.jsonl` `furthest_stage=None`].
- `Outputs/v19_lora` × rich_4076 — **LOCATE / NO_GOLD_FILE** `~`, same deciding observation (calls=0,
  malformation 1.0, `NUDGE_EXHAUSTED`); × rich_4070 — **FOUND-NOT-LANDED** with malformation 0.750;
  × rich_4079 — **FOUND-NOT-LANDED**, malformation 0.458; × rich_4077 — **RESOLVED** [MEASURED].
- `v2_gate_s05c` × rich_3469, rich_4076, rich_4079 — **LOCATE**; × rich_4070 — **WRONG-FIX**, malformation
  share 0.609 (`ARG_REJECTED`-driven), carries `~`, not INFRA; × rich_4077 — **RESOLVED** [MEASURED].
- `v2_gate_out` × rich_4070, rich_4076 — **WRONG-FIX**; × rich_3469 — **LOCATE**; × rich_4079 —
  **FOUND-NOT-LANDED**; × rich_4077 — **RESOLVED** [MEASURED].
- `submit_v6w/out_v6w` (ARM 0 as proposed) — 4/6 RESOLVED (3278, 3471, 3882, 4077), rich_4076 **LOCATE**
  (`CALL_CAP`), rich_4079 **FOUND-NOT-LANDED** [MEASURED].

The measured overbake signature is therefore **categorical**, not a gentle slide: zero structured calls /
malformation share → 1.0 / `NUDGE_EXHAUSTED`. That matters for the bar (§6, §10).

## 6. Tests run (offline; no Kaggle push, no agent command executed)

**T0 — freshness + report path.** `python kb\build_kb.py check-fresh` → `FRESH` (exit 0);
`report-path --date 2026-10-16 --slug adapter-strength-calibration --kind audit` → this file (exit 0).

**T1 — on-disk scan of every `adapter_config.json` under `Gemma\**` with weight sizes.** 31 configs.
α/r values present: 2.0 (`adapter_dataset` 110-mod α64; `adapter_v2_dataset`/`v2_gate_out2` 410-mod α64;
`Outputs\v19_lora` 110-mod α64; `comp_files`/`v2_gate_out` r4/α8 2-module stub) and 0.5
(`adapter_dataset-r32-s0.25`, `adapter_v2_s05`, `v2_gate_s05`/`s05b`/`s05c`, `lora025`).
**Nothing below 0.5 exists.** `lora025`'s shipped config is r32/α16/110 modules/175,341,936 B — i.e. the
proposal's "preferred artifact at mid serve-scale" is byte-for-byte the artifact `lora025` already
shipped [MEASURED].

**T2 — config/prompt identity across arms** (`kb\runs.jsonl` `config.prompt_sha256` + each run's
`submission\eval_config.yaml` and `configs\sampling.yaml`). All adapter arms (`v2_gate_out`,
`v2_gate_out2`, `v2_gate_s05c`, `Outputs\v19_lora`, `lora025`): prompt sha `d7777085b575`, 15/8/24/120,
6144 out-tokens, `frequency_penalty 0.4`, thinking 256. `Outputs\v19`: identical on all of those, no
adapter. `submit_v6w\out_v6w`: prompt sha `9c2fa3587f25`, 28/8/80/240, 8192, no frequency penalty,
thinking 1024 [MEASURED]. Consequence: `lora025` lives under `submit_v6z_on_v6w\` but was **not** run at
the v6w config, and the log's lora025-vs-no-adapter comparison on the hard tasks (`GEMMA_EXPERIMENT_LOG.md`
~L9422/L9477 and the content-LoRA audit §4) is **confounded by a 15-vs-28 call budget and thinking
256-vs-1024**, not a clean adapter effect.

**T3 — THE CHEAPEST FALSIFYING TEST: apply the proposal's bar to no-adapter arms.** Two exact-replicate
pairs exist (same prompt sha `9c2fa3587f25`, same 28/8/80/240 + 8192 + 9 tools, same 6 tasks, no adapter
in either): (A) `submit_v6x/out_v6x` vs `submit_v6t/out_v6t` (both thinking 4096); (B)
`submit_v6w/out_v6w` vs `submit_v6y/out_v6y` (both thinking 1024). Scoring "not below on edit-attempts
AND patch_chars" exactly as written:

- Pair A: not-below on **2/6**; materially below on **2** tasks (rich_3471 707→0 chars with 5→0 edits;
  rich_4076 371→0 chars with 5→3 edits) → a **zero-adapter** arm is ruled NOT ADMISSIBLE **and
  OVER-STRONG**.
- Pair B: not-below on **2/6** → NOT ADMISSIBLE (materially-below count 0, so not flagged over-strong).
- For reference the same scoring against the matched control `Outputs/v19`: `v2_gate_out` (sample stub,
  the arm the proposal cites as "baseline-like") 2/5; `v2_gate_s05c` 2/5; `Outputs\v19_lora` 1/5;
  `v2_gate_out2` 0/5 with materially-below on 5/5.

[MEASURED, `%TEMP%` script over `kb\runs.jsonl`, removed.] So the ADMISSIBLE half of the bar fails on
2 of 2 no-adapter replicate pairs and on the stub arm the proposal treats as the baseline-like reference;
the OVER-STRONG half fires only on the already-known categorical collapse. The bar as written cannot
separate "mildly degraded" from run-to-run noise.

**T4 — no-adapter band at the v6w config** (5 runs, same prompt sha, 28 calls; thinking 1024–4096):
resolves 3–4/6; Σ patch_chars 1786–3604; tasks with ≥1 edit 5–6/6; Σ n_edit 21–35; **mean malformation
0.000–0.059**; tasks with calls=0 **always 0** [MEASURED]. Per-task malformation at this prompt never
exceeds 0.20 (`v6y`×rich_4079). This is the band a revised bar can be pre-registered against.

**T5 — harness mechanics for multi-arm serving** (static read).
`harness_src\x\adk_submission\server.py:397 create_model_registry` enumerates
`self.adapter_manifest.adapters.keys()` and registers **every** discovered adapter as its own model id
plus an `adapter:<name>` alias against the same vLLM server;
`harness_src\x\adk_submission\discovery.py:384 discover_adapters` catalogues every
`adapters/<name>/adapter_model.safetensors`. `comp_files\HARNESS_README.md` §3.4 L204 confirms all
discovered adapters are registered (`enable_lora`, `max_loras=8`, `max_lora_rank=128`), and L110 says
`agent.yaml`'s `adapter` is a single optional name. Crucially
`harness_src\x\swegemma\harness\agent_runner.py:616` calls `compile_submission(submission_dir=...)`
**inside** the per-task agent run, which `swegemma\evaluate.py:316` invokes per `evaluate_task`. So in a
free-gate notebook the `adapter:` line of `agent.yaml` can be rewritten between arms and the next task
picks it up, with ONE vLLM start and all strengths co-registered. The trace records the served id
(`model_name='main_lora'` vs the base model path, step_id=3 in the traces cited in §4), so arm identity is
auditable per task [MEASURED]. Size check: `adk_submission\limits.py:184` `max_total_size_bytes = 3 GiB`
including `adapters/` (README §2.4 L134/L179) → three copies of the 410-module artifact = 2.94 GB (at the
wall), three copies of the 110-module artifact = 526 MB (comfortable) [MEASURED arithmetic on measured
sizes].

**T6 — bar measurability from gate output.** `submit_v6w\out_v6w\gemma-sibling-conform-v6w.log` prints
only `id, repo, resolved, duration_s, tool_calls, patch_chars` and a RESOLVED tally; there is **no**
ATTRIBUTION table and no `first_edit_at` / `n_edit` / `edit_fail` / malformation in the v6w kernel output
(the ATTRIBUTION cell exists in `submit_v6z_on_v6w\lora025\notebook_src.py` L359-425, not in v6w). The
missing metrics are all derivable post-hoc from the pulled `results\traces\trace_<task>.json` via
`build_kb.py build` (`edit_attempts`, `tool_call_malformation.share`, `refused`, `arg_rejected`,
`end_reason` are KB trace fields) [MEASURED]. So the bar is measurable — but only after a KB rebuild, not
from the SUMMARY the gate prints. (Side note: that same log prints the header `===== v6c SUMMARY =====`
in the v6w run — a stale version token; read arms by directory + `model_name`, never by the SUMMARY label.)

**T7 — leakcheck.** `leakcheck --scope config` on the proposal **exits 1**: bare ids rich_3535, rich_3469,
rich_3934, rich_4070, rich_4077, rich_4079, rich_3675. `--scope tooling` → `LEAKCHECK CLEAN` (exit 0).
The v6w base artifacts are clean under the strict scope: `submit_v6w\out_v6w\submission\prompts\system.md`
and `agent.yaml` both `LEAKCHECK CLEAN` [MEASURED]. The proposal is a planning document, so this is not a
blocker, but the task ids must stay in the notebook's task-list cell (tooling scope) and never enter
`prompts\system.md` or any YAML.

**T8 — baseline reconciliation** (`curated\submissions.csv`, `curated\run_labels.json`). v6w @ **0.15**,
ref 57098497, COMPLETE, 2026-10-12 → the policy baseline, unchanged. Also in the CSV and **not** yet
reflected in the pointers: ref 57146757 (branch_final) is **COMPLETE at 0.12**, not PENDING as
`run_labels.json:pending`, `KB_SUMMARY §7` and `gemma-submission-protocol.md` all still state; and ref
57201051 "v6w + temperature 1.0 / top_k 64" is **COMPLETE at 0.13**. Separately, `KB_SUMMARY`'s BASELINE
banner says `gemma-submission-protocol.md` "still says v6 @ 0.12 and is STALE" — the steering file as read
today says *"v6w @ 0.15 is SACRED (live-best) — Kaggle submission 57098497"*, so the **banner's claim about
steering is itself stale**; steering and the CSV now agree [MEASURED].

**T9 — the 0.13 datum** (relevant to the originating question, and to any future one-change gate).
`submit_v7_temp1\out\submission\configs\sampling.yaml` = temperature 1.0, top_p 0.95, **top_k 64**, 8192
out-tokens, thinking 1024; `eval_config.yaml` = 28/8/80/240; `prompts\system.md` SHA-256 prefix
`9C2FA3587F25` — **byte-identical to v6w's prompt**. So "only change vs the 0.15 v6w baseline" is
SUPPORTED: the 0.13 run is v6w with temperature 0.2→1.0 plus top_k 64, i.e. **−0.02 LB for a
sampling-only change**. `submit_v7_temp1\` contains **no `results\`** directory — that submission was
never gated and has no traces, so "why 0.13" is answerable only as an LB delta, not from behavior
[MEASURED].

## 7. Variance

- Exact-replicate no-adapter pairs at the v6w config: 4/6 vs 4/6 (v6x/v6t) and 4/6 vs 3/6 (v6w/v6y);
  per-task patch_chars swings 0 ↔ 707 (rich_3471), 0 ↔ 1167 (rich_4076), 0 ↔ 632 (rich_4079) with the
  adapter held at none and the prompt byte-identical [MEASURED, §6 T3/T4]. A 5-task, n=1-per-arm gate
  therefore cannot resolve per-task differences of this size.
- rich_4077 as "always-solve control": resolved in 10 of 11 v6-family runs; the miss is
  `submit_v6s/out_v6s` (no adapter, thinking 4096, `CALL_CAP`, 1454 patch_chars, WRONG-FIX). At the exact
  v6w sampling (thinking 1024) it is 6/6. So "loses rich_4077 ⇒ over-strong" carries a ~9% false-positive
  rate across the family, ~0% within the thinking-1024 subfamily [MEASURED].
- Malformation share is the one metric that separates arms cleanly: ≤0.059 mean / ≤0.20 per task across 5
  no-adapter v6w-config runs, versus 0.143–1.000 mean across the four adapter arms [MEASURED]. But it is
  not adapter-exclusive — `submit_v6z_on_v6w/armA/out` (no adapter, prompt sha `b8b62ef95b0b`) shows 0.89
  and 0.91 on two tasks, so the threshold is only valid with the prompt held fixed [MEASURED].
- The proposed HARD tasks have never resolved: rich_3675 0/8 runs, rich_3934 0/6 runs; rich_3676 resolved
  once (`submit_v6z_on_v6w/branch/out`) [MEASURED].

## 8. Rules check

| rule | status |
|---|---|
| Free gate first, scored slot untouched (protocol) | **PASS** — explicit, and ARM 0 is v6w itself. |
| Live-best / baseline named correctly | **PASS with a finding** — v6w @ 0.15 (ref 57098497) is the baseline; §6 T8 records three stale PENDING statements and a stale KB banner. |
| Pre-register the bar (acct. 2) | **FAIL as written** — the bar is pre-registered but it is not discriminating: two no-adapter replicate pairs fail it (§6 T3). A bar a null arm fails is not a bar. |
| One change per gate (acct. 7 / protocol) | **FAIL as written** — adapter arms at the v6w config change adapter **and** (vs the only comparable adapter data) budget 15→28, turns 24→80, timeout 120→240, out-tokens 6144→8192, `frequency_penalty` 0.4→0, thinking 256→1024, prompt `d77770`→`9c2fa3`. Pick one regime and say which (§10). |
| No extrapolation (acct. 4) | **FAIL as written** — the proposal uses the s05c datum (15-call/think-256 regime) to predict behavior at the v6w regime, and sells the result as "a serve-strength prior for the content LoRA" although the band would be specific to this artifact's trained weights. Record the regime and the artifact as the validity range. |
| Tune before concluding (acct. 13) | **PARTIAL** — it does sweep a knob, which is right, but one of the two points is already measured (§6) so the realised sweep is n=1 new point. Sweep ≥2 **new** points. |
| Floor-guaranteed composition (acct. 15) | **N/A at serve, honoured in spirit** — there is no blend weight at serve; w=0 = ship no adapter, and ARM 0 *is* the live-best, so the floor is preserved by arm selection (same reading as the 2026-10-15 audit §8). |
| Novelty leads, tests decide (acct. 10, 11) | **PASS** — this audit does not recommend abandoning the weights lever. Two components are genuinely new (α/r < 0.5; any adapter at v6w), and the 410-module collapse is diagnosed as an execution/strength fault, not a refutation. |
| Honest nulls (acct. 3) | **PASS** — an empty admissible band is pre-accepted as a result. |
| Single flat agent, no sub-agents | **PASS** — stated; consistent with the curated `J-subagents-regress`. |
| No gold / no fingerprints in config (hard limit) | **PASS on gold**; see §6 T7 for the bare-task-id scope point. |
| Rich-only next gate | **PASS** — all five proposed tasks are rich. |

## 9. Cheapest falsifying test

Already run, offline, and it fired: §6 **T3** — score the proposal's admissibility rule on two
no-adapter exact-replicate pairs. Both land at 2/6 "not below" and pair A also trips "materially below on
≥2 tasks". A rule that calls a zero-adapter arm over-strong is measuring run-to-run variance, so the
gate as specified would spend GPU to produce an uninterpretable verdict. The next-cheapest unexecuted
test, which the revision needs anyway, is static: build the two α-variants with
`python train\make_variant.py --adapter adapter_dataset-r32-s0.25 --scale 0.5` and `--scale 0.25` and
assert the emitted `adapter_config.json` has `r=32` with `lora_alpha` 8 and 4 — because `--scale` is
**relative to the source artifact's own α/r** (`make_variant.py` L63-66: `eff_target = scale *
alpha0/r0`), and the preferred source is already at 0.5, so a naive `--scale 0.5`/`0.25` produces 0.25 and
0.125, not 0.5 and 0.25. Pin arms by integer `lora_alpha`, never by `--scale`.

## 10. Verdict rationale — REVISE

The direction survives and should be pursued: WRONG-FIX remains the largest traced-rich failure class, the
weights lever is not refuted, and two parts of this proposal have never been measured — strength below
α/r = 0.5, and any adapter at the v6w config. Nothing in this audit says retreat. What it says is that
the gate as written would burn its GPU on an unreadable answer. Four concrete defects, all fixable before
any push, all from data already on disk:

1. **The bar is noise-dominated (blocking).** Per-task "edit-attempts AND patch_chars not below ARM 0"
   fails on 2/2 no-adapter exact-replicate pairs and on the stub arm the proposal itself calls
   baseline-like (§6 T3). Replace with (a) a **categorical hard fail** matching the measured overbake
   signature — any task with 0 structured tool calls, or malformation share ≥ 0.35, or
   `end_reason=NUDGE_EXHAUSTED` (no-adapter v6w-config ceiling is 0.20 per task, 0.059 mean, 0 tasks with
   calls=0; §6 T4) — and (b) **run-level aggregates** against the measured no-adapter band (resolves 3–4/6,
   Σ patch_chars 1786–3604, tasks-with-≥1-edit 5–6/6, mean malformation ≤0.059). Keep "loses rich_4077"
   only as a secondary flag and state its measured ~9% family-level false-positive rate.
2. **Drop the α/r = 0.5 arm; sweep below it.** §4/§6 show 0.5 already measured against a byte-identical
   control (`v2_gate_s05c` vs `Outputs\v19`: malformation 4.6× the control, edit activity on 2/5 vs 5/5,
   and it already fails the proposal's own bar). Spend both adapter arms on the unmeasured band — α=8
   (α/r 0.25) and α=4 (α/r 0.125) on the 110-module r32 artifact — pinned by integer `lora_alpha` (§9).
3. **Fix the task set and the regime, and say which.** The proposed set {4077, 4079, 3469, 3675, 3934} has
   never been run as a set by any config, has no ARM 0 history, mixes in two never-resolved HARD tasks, and
   rich_3675 carries an 82-test Pass-to-Pass surface. Use the v6w 6-task set {3278, 3471, 3882, 4076, 4077,
   4079} — 6 EASY, 5 existing no-adapter runs for a variance band, and ARM 0 = v6w itself — **or**, if
   comparability to the s05c/out2 overbake datum is the priority, run the adapter arms at the v19 regime on
   {3469, 4070, 4076, 4077, 4079} where `Outputs\v19` is a byte-identical control. One or the other, stated
   before the push; not a blend.
4. **Artifact choice is settled by the size limit and honesty about what is being calibrated.** Use the
   110-module r32 artifact (175 MB; three co-registered strengths = 526 MB vs 2.94 GB for the 410-module at
   the 3 GiB wall; `limits.py:184`). And state plainly that its weights are the *trained v2 edit-discipline*
   adapter with a known tool-call serialization defect, not a benign random artifact — so the admissible
   band is a property of **this artifact at this regime**, an upper bound and a method check, not a
   transferable strength prior for a future content LoRA (acct. 4). If an artifact-agnostic band is the real
   goal, add a random-weight same-shape arm; that is a different, also-cheap experiment.

Answers to the proposal's four open questions, for the record. (a) NEW vs RE-RUN: VARIANT — new at α/r <
0.5 and at the v6w config; ARM 2 is a RE-RUN. (b) Multiple strengths in one gate: **yes** — co-register
each α variant as its own `adapters/<name>/` (all are registered as distinct model ids;
`server.py:397`, README §3.4) and rewrite `agent.yaml`'s `adapter:` between arms, since
`compile_submission` runs per task (`agent_runner.py:616` via `evaluate.py:316`); one kernel, one vLLM
start, arm verifiable per task from the trace's `model_name`. (c) Artifact/scales: 110-module r32, pinned
integer α. (d) Bar measurable: resolved / tool_calls / patch_chars yes from the printed SUMMARY;
n_edit / first-edit / edit_fail / malformation only via a trace pull + `build_kb.py build` — the v6w
kernel has no ATTRIBUTION cell.

**One execution blocker outside the design.** The most recent log entries state the Kaggle weekly GPU
quota is exhausted: `GEMMA_EXPERIMENT_LOG.md` L10090 (2026-10-15, "Maximum weekly GPU quota of 45.00 hours
reached", `submit_v6w_fastapi` push FAILED) and L10116 (2026-10-16, "Kaggle weekly GPU quota exhausted
(45.00 h)"). I cannot verify current quota — the Kaggle API exposes no quota endpoint and pushing is
outside my limits. Confirm quota before building, and note Colab is not a substitute judge: there is no
local 31B W4A16 vLLM stack (`eval_hf_adapter.py` is E2B 4-bit HF, `run_local.py` drives a 12B GGUF), so a
non-Kaggle run would not be the trustworthy judge this calibration needs. Budget estimate from
`submit_v6w\out_v6w\gemma-sibling-conform-v6w.log`: ~450 s vLLM start, first result at t=626 s, all 6
tasks done by t=1867 s → ~31 min for 6 tasks; three arms in one kernel ≈ 75–95 min, versus ~90–120 min as
three separate pushes.

## 11. What the suggestion missed

1. Its admissibility bar is failed by **no-adapter** arms — 2/6 on two exact-replicate pairs, and 2/5 for
   the sample-stub arm it cites as baseline-like (§6 T3).
2. α/r = 0.5 is not an untested "mid point": it has already been measured against a byte-identical
   no-adapter control and already fails (malformation 0.143 vs 0.031; edit activity 2/5 vs 5/5) (§4).
3. **No adapter has ever been served at the v6w config.** Every adapter arm ran 15/8/24/120, 6144
   out-tokens, `frequency_penalty 0.4`, thinking 256, prompt `d777708`. So "comparable to the s05c datum"
   and "ARM 0 = v6w" are mutually exclusive in one gate (§6 T2).
4. A byte-identical no-adapter control for the adapter set **already exists** (`Outputs\v19`), and a
   5-run no-adapter band already exists at the v6w config — the control arm is partly free either way (§4, T4).
5. `lora025` sits under `submit_v6z_on_v6w\` but ran at the v19 config, so the log's "lora025 banked 0
   chars where no-adapter banked 1187/465" is confounded by a 15-vs-28 call budget and thinking
   256-vs-1024, not an adapter effect (§6 T2).
6. `make_variant.py --scale` is relative to the source artifact's own α/r, and the preferred source is
   already at 0.5 — `--scale 0.5` yields 0.25, not 0.5. Arms must be pinned by integer `lora_alpha` (§9).
7. The 410-module alternative costs 979 MB per strength; three co-registered strengths = 2.94 GB against
   a 3 GiB hard limit (§6 T5).
8. Multiple strengths **can** share one kernel and one vLLM server (per-task `compile_submission` +
   all-adapters registration), which the proposal treats as unknown and which also holds the stack
   constant across arms (§6 T5).
9. The bar's behavioral metrics are **not** in the v6w kernel's printed output; they need a trace pull and
   a KB rebuild (§6 T6).
10. The proposed task set has no ARM 0 history, includes two never-resolved HARD tasks, and rich_3675's
    test_patch adds 82 tests (§3, §7).
11. rich_4077 is not an absolute control (lost once in-family, `v6s`), and it has **no gold-valid local
    replay**, so a disputed resolve on the control cannot be re-checked offline (§3, §7).
12. The artifact is the trained v2 edit-discipline adapter with a known serialization defect, not a benign
    one — the resulting band is artifact- and regime-specific, not the transferable "serve-strength prior"
    the proposal promises (§10 item 4).
13. GPU quota was reported exhausted as recently as today's log entry; the gate may not be pushable (§10).
14. Three pointers still call submission 57146757 PENDING when `curated\submissions.csv` has it COMPLETE at
    0.12, and `KB_SUMMARY`'s claim that steering is stale on the baseline is itself now stale (§6 T8).

## 12. Measured vs inferred

**MEASURED** (raw files, traces, on-disk configs, curated submissions): every `adapter_config.json` under
`Gemma\**` with r / α / module count / weight bytes, and that nothing below α/r = 0.5 exists; `lora025`'s
shipped config being byte-equal in shape to the proposal's preferred ARM 2; prompt-sha and
eval_config/sampling identity across all adapter arms and `Outputs\v19`, and their difference from v6w;
all per-task outcomes, edit-attempt counts, malformation shares, end reasons and failure classes quoted in
§4/§5; the five raw-trace spot checks incl. zero `tool_calls` fields and `model_name='main_lora'` in
`v2_gate_out2`/`v19_lora`; the T3 bar scoring on two no-adapter replicate pairs; the T4 no-adapter band;
`create_model_registry` / `discover_adapters` / per-task `compile_submission` behavior and the 3 GiB limit;
the v6w kernel log's printed columns, its ~31-min 6-task wall time and its stale `v6c SUMMARY` header;
both leakcheck results; `make_variant.py`'s relative-scale arithmetic; all gold metadata in §3 and the
4-task `replays\gold\` coverage; `submissions.csv` rows incl. v6w 0.15, branch_final COMPLETE 0.12 and
57201051 COMPLETE 0.13; the 0.13 submission's sampling/eval/prompt-hash identity to v6w and its absent
`results\` dir.

**INFERRED**: that three co-registered 110-module strengths total ~526 MB (arithmetic on measured sizes);
that a 3-arm single-kernel gate runs ~75–95 min (scaling the measured 6-task 31-min run); that an α/r <
0.5 arm will behave between the measured 0.5 point and no-adapter (a bounded expectation, not a
prediction — it is exactly what the gate must measure); that GPU quota is still exhausted (the newest log
entry says so; I could not verify it, and the API exposes no quota endpoint); that the revised
malformation threshold 0.35 sits above no-adapter noise (derived from a 5-run band at one prompt, n=5).

<!-- AUDIT-JSON
{"schema": "gemma-audit/1", "mode": "AUDIT", "verdict": "REVISE",
 "proposal": "c:\\Users\\Biges\\OneDrive\\Documents\\Desktop\\kAGGLE\\Gemma\\kb\\proposals\\2026-10-16-adapter-strength-calibration-gate.md",
 "kb_inputs_fingerprint": "9f2e9311cea4",
 "targets": ["rich_4077", "rich_4079", "rich_3469", "rich_3675", "rich_3934", "rich_3278", "rich_3471", "rich_3882", "rich_4076", "rich_4070"],
 "prior_art": [
  {"lever": "multi-layer adapter served on the scored 31B stack", "tag": "RE-RUN", "runs": ["v2_gate_out2", "v2_gate_s05c", "Outputs/v19_lora", "submit_v6z_on_v6w/lora025/out"]},
  {"lever": "make_variant.py serve-scale alpha rewrite (weights untouched)", "tag": "RE-RUN", "runs": ["v2_gate_s05c", "submit_v6z_on_v6w/lora025/out"]},
  {"lever": "adapter at alpha/r = 0.5", "tag": "RE-RUN", "runs": ["v2_gate_s05c", "submit_v6z_on_v6w/lora025/out"]},
  {"lever": "adapter at alpha/r = 2.0", "tag": "RE-RUN", "runs": ["v2_gate_out2", "Outputs/v19_lora"]},
  {"lever": "adapter at alpha/r < 0.5", "tag": "NEW", "runs": []},
  {"lever": "any adapter served at the v6w config (28/8/80/240, think 1024, 8192 out-tokens)", "tag": "NEW", "runs": []},
  {"lever": "no-adapter control arm matched byte-for-byte to the adapter arms", "tag": "VARIANT", "runs": ["Outputs/v19", "submit_v6w/out_v6w"]}],
 "per_task": [
  {"run_id": "v2_gate_out2", "task": "rich_4077", "failure_class": "LOCATE", "subclass": "NO_GOLD_FILE~",
   "evidence": ["Gemma/v2_gate_out2/results/traces/trace_rich_4077.json#step_id=3", "Gemma/kb/runs.jsonl#row_id=v2_gate_out2::rich_4077", "Gemma/kb/near_miss.jsonl#run_id=v2_gate_out2 furthest_stage=None"]},
  {"run_id": "Outputs/v19_lora", "task": "rich_4076", "failure_class": "LOCATE", "subclass": "NO_GOLD_FILE~",
   "evidence": ["Gemma/Outputs/v19_lora/results/traces/trace_rich_4076.json#step_id=3", "Gemma/kb/runs.jsonl#row_id=Outputs/v19_lora::rich_4076"]},
  {"run_id": "v2_gate_s05c", "task": "rich_4070", "failure_class": "WRONG-FIX", "subclass": "ARG_REJECTED~",
   "evidence": ["Gemma/v2_gate_s05c/results/traces/trace_rich_4070.json#step_id=3", "Gemma/kb/runs.jsonl#row_id=v2_gate_s05c::rich_4070 malform=0.609"]},
  {"run_id": "v2_gate_out", "task": "rich_4077", "failure_class": "RESOLVED", "subclass": null,
   "evidence": ["Gemma/kb/runs.jsonl#row_id=v2_gate_out::rich_4077", "Gemma/v2_gate_out/submission/adapters/main_lora/adapter_config.json", "Gemma/comp_files/adapter_config.json"]},
  {"run_id": "Outputs/v19", "task": "rich_4070", "failure_class": "WRONG-FIX", "subclass": null,
   "evidence": ["Gemma/Outputs/v19/results/traces/trace_rich_4070.json#step_id=3", "Gemma/kb/runs.jsonl#row_id=Outputs/v19::rich_4070"]},
  {"run_id": "submit_v6w/out_v6w", "task": "rich_4079", "failure_class": "FOUND-NOT-LANDED", "subclass": null,
   "evidence": ["Gemma/kb/runs.jsonl#row_id=submit_v6w/out_v6w::rich_4079", "Gemma/submit_v6w/out_v6w/gemma-sibling-conform-v6w.log#line=89"]},
  {"run_id": "submit_v6x/out_v6x", "task": "rich_3471", "failure_class": "RESOLVED", "subclass": null,
   "evidence": ["Gemma/kb/runs.jsonl#row_id=submit_v6x/out_v6x::rich_3471"]},
  {"run_id": "submit_v6t/out_v6t", "task": "rich_3471", "failure_class": "LOCATE", "subclass": null,
   "evidence": ["Gemma/kb/runs.jsonl#row_id=submit_v6t/out_v6t::rich_3471"]}],
 "claims": [
  {"id": "A1", "text": "Nothing below alpha/r = 0.5 has ever been served: all 31 on-disk adapter_config.json files are at alpha/r 2.0 or 0.5.", "basis": "MEASURED", "evidence": ["Gemma/adapter_dataset-r32-s0.25/adapter_config.json", "Gemma/adapter_v2_s05/adapter_config.json", "Gemma/adapter_dataset/adapter_config.json"]},
  {"id": "A2", "text": "No adapter has ever run at the v6w config: all adapter arms used 15/8/24/120, 6144 tokens, freq_penalty 0.4, think 256, prompt sha d7777085b575.", "basis": "MEASURED", "evidence": ["Gemma/v2_gate_s05c/submission/eval_config.yaml", "Gemma/submit_v6z_on_v6w/lora025/out/submission/eval_config.yaml", "Gemma/kb/runs.jsonl#config.prompt_sha256"]},
  {"id": "A3", "text": "The proposal's admissibility bar fails on no-adapter exact-replicate pairs: v6x-vs-v6t 2/6 not-below with 2 materially-below; v6w-vs-v6y 2/6.", "basis": "MEASURED", "evidence": ["Gemma/kb/runs.jsonl#row_id=submit_v6x/out_v6x::rich_3471", "Gemma/kb/runs.jsonl#row_id=submit_v6t/out_v6t::rich_4076", "Gemma/kb/runs.jsonl#row_id=submit_v6y/out_v6y::rich_3278"]},
  {"id": "A4", "text": "alpha/r = 0.5 is already measured against a byte-identical no-adapter control and already fails the bar: s05c 2/5 not-below, mean malform 0.143 vs 0.031, edit activity 2/5 vs 5/5.", "basis": "MEASURED", "evidence": ["Gemma/kb/runs.jsonl#row_id=v2_gate_s05c::rich_4076", "Gemma/kb/runs.jsonl#row_id=Outputs/v19::rich_4076"]},
  {"id": "A5", "text": "Multiple strengths can share one kernel: create_model_registry registers every discovered adapter as its own model id and compile_submission runs per task, so agent.yaml's adapter can be rewritten between arms.", "basis": "MEASURED", "evidence": ["Gemma/harness_src/x/adk_submission/server.py#L397", "Gemma/harness_src/x/adk_submission/discovery.py#L384", "Gemma/harness_src/x/swegemma/harness/agent_runner.py#L616", "Gemma/harness_src/x/swegemma/evaluate.py#L316"]},
  {"id": "A6", "text": "Three co-registered 410-module strengths = 2.94 GB against the 3 GiB max_total_size_bytes; the 110-module artifact (175 MB) is the only safe choice for a 3-arm gate.", "basis": "MEASURED", "evidence": ["Gemma/harness_src/x/adk_submission/limits.py#L184", "Gemma/comp_files/HARNESS_README.md#L134", "Gemma/v2_gate_out2/submission/adapters/main_lora/adapter_config.json"]},
  {"id": "A7", "text": "The v6w kernel prints only resolved/duration/tool_calls/patch_chars; n_edit, first_edit_at, edit_fail and malformation require a trace pull plus build_kb.py build.", "basis": "MEASURED", "evidence": ["Gemma/submit_v6w/out_v6w/gemma-sibling-conform-v6w.log#line=79", "Gemma/submit_v6z_on_v6w/lora025/notebook_src.py#L359"]},
  {"id": "A8", "text": "make_variant.py --scale is relative to the source artifact's own alpha/r, so --scale 0.5 on the already-0.5 preferred artifact yields 0.25; arms must be pinned by integer lora_alpha.", "basis": "MEASURED", "evidence": ["Gemma/train/make_variant.py#L63"]},
  {"id": "A9", "text": "Baseline is v6w @ 0.15 (ref 57098497 COMPLETE). branch_final ref 57146757 is COMPLETE at 0.12, not PENDING as steering, run_labels.json and KB_SUMMARY still state; KB_SUMMARY's claim that steering is stale on the baseline is itself stale.", "basis": "MEASURED", "evidence": ["Gemma/kb/curated/submissions.csv", "Gemma/kb/curated/run_labels.json", "Gemma/kb/KB_SUMMARY.md", ".kiro/steering/gemma-submission-protocol.md"]},
  {"id": "A10", "text": "The 0.13 run (ref 57201051) is v6w with temperature 1.0 + top_k 64 only: prompt sha prefix 9C2FA3587F25 and eval_config match v6w byte-for-byte; it has no results/ dir, so no traces exist.", "basis": "MEASURED", "evidence": ["Gemma/submit_v7_temp1/out/submission/configs/sampling.yaml", "Gemma/submit_v7_temp1/out/submission/prompts/system.md", "Gemma/kb/curated/submissions.csv"]},
  {"id": "A11", "text": "Kaggle weekly GPU quota was reported exhausted (45.00 h) in the log on 2026-10-15 and again on 2026-10-16; current quota is unverifiable from here.", "basis": "INFERRED", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#L10090", "Gemma/GEMMA_EXPERIMENT_LOG.md#L10116"]},
  {"id": "A12", "text": "Lowering the 410-module artifact from alpha/r 2.0 to 0.5 did move it from paralysis toward acting (malform 1.000->0.143, sum patch_chars 0->1371, calls=0 tasks 5->0), so the proposal's premise holds at run level.", "basis": "MEASURED", "evidence": ["Gemma/kb/runs.jsonl#row_id=v2_gate_out2::rich_4070", "Gemma/kb/runs.jsonl#row_id=v2_gate_s05c::rich_4070"]}],
 "tests_run": [
  {"cmd": "python kb/build_kb.py check-fresh", "result": "FRESH (exit 0); inputs_fingerprint 9f2e9311cea4"},
  {"cmd": "python kb/build_kb.py report-path --date 2026-10-16 --slug adapter-strength-calibration --kind audit", "result": "exit 0; kb/audits/2026-10-16-adapter-strength-calibration.md (new file)"},
  {"cmd": "on-disk scan of every adapter_config.json under Gemma/** with weight sizes", "result": "31 configs; alpha/r only 2.0 or 0.5; lora025 = r32/alpha16/110 modules/175,341,936 B; 410-module = 979,558,760 B"},
  {"cmd": "prompt_sha256 + eval_config/sampling comparison across all runs (kb/runs.jsonl + submission yamls)", "result": "all 4 adapter arms and Outputs/v19 share prompt d7777085b575 + 15/8/24/120/6144/freq0.4/think256; v6w = 9c2fa3587f25 + 28/8/80/240/8192/think1024"},
  {"cmd": "apply the proposal's admissibility bar to Outputs/v19 vs each adapter arm and to two no-adapter exact-replicate pairs", "result": "no-adapter v6x-vs-v6t 2/6 not-below + 2 materially-below (ruled over-strong); v6w-vs-v6y 2/6; stub 2/5; s05c 2/5; v19_lora 1/5; out2 0/5 with 5 materially-below"},
  {"cmd": "run-level aggregates over the 5 no-adapter v6w-config runs", "result": "resolves 3-4/6; sum chars 1786-3604; tasks>=1edit 5-6/6; sum n_edit 21-35; mean malform 0.000-0.059; tasks with calls=0 always 0"},
  {"cmd": "raw-trace reads of trace_rich_4077 (out2), trace_rich_4076 (v19_lora), trace_rich_4070 (v19, s05c), trace_rich_4077 (v6w)", "result": "out2 and v19_lora: zero steps carrying tool_calls, model_name=main_lora; v19/s05c/v6w: 20/22/24 steps with tool_calls"},
  {"cmd": "static read of server.py create_model_registry, discovery.py discover_adapters, agent_runner.py compile_submission, limits.py", "result": "all adapters registered as distinct model ids; compile_submission is per task; max_total_size_bytes = 3 GiB incl. adapters"},
  {"cmd": "python kb/build_kb.py leakcheck --scope config kb/proposals/2026-10-16-adapter-strength-calibration-gate.md", "result": "exit 1: bare ids rich_3535/3469/3934/4070/4077/4079/3675; --scope tooling CLEAN; v6w system.md + agent.yaml CLEAN under --scope config"},
  {"cmd": "Get-FileHash on submit_v7_temp1 vs submit_v6w system.md + read of both sampling/eval configs", "result": "identical prompt SHA 9C2FA3587F25; 0.13 run differs only by temperature 1.0 + top_k 64; no results/ dir in submit_v7_temp1"}],
 "missed": [
  "The admissibility bar is failed by no-adapter arms (2/6 on two exact-replicate pairs; 2/5 for the sample-stub arm it calls baseline-like).",
  "alpha/r = 0.5 is already measured against a byte-identical control and already fails the bar, so one of two adapter arms is a re-run.",
  "No adapter has ever been served at the v6w config, so 'ARM 0 = v6w' and 'comparable to the s05c datum' are mutually exclusive in one gate.",
  "A byte-identical no-adapter control (Outputs/v19) and a 5-run no-adapter band at the v6w config already exist.",
  "lora025 ran at the v19 config despite living under submit_v6z_on_v6w, so the logged lora025-vs-no-adapter chars comparison is budget-confounded.",
  "make_variant.py --scale is relative to the source artifact's own alpha/r; arms must be pinned by integer lora_alpha.",
  "Three co-registered 410-module strengths = 2.94 GB against a 3 GiB hard limit.",
  "Multiple strengths can share one kernel and one vLLM server (all adapters registered; compile_submission per task).",
  "n_edit / first_edit_at / edit_fail / malformation are not in the v6w kernel output; they need a trace pull + KB rebuild.",
  "The proposed task set has no ARM 0 history, has two never-resolved HARD tasks, and rich_3675's test_patch adds 82 tests.",
  "rich_4077 is not an absolute control (lost once in-family under v6s) and has no gold-valid local replay.",
  "The artifact is the trained v2 edit-discipline adapter with a known serialization defect, so the band is artifact- and regime-specific, not a transferable strength prior.",
  "GPU quota was reported exhausted as recently as the 2026-10-16 log entry; the gate may not be pushable.",
  "Three pointers still call submission 57146757 PENDING when submissions.csv has it COMPLETE at 0.12, and KB_SUMMARY's 'steering is stale' banner is itself stale."],
 "proposed_curations": [
  {"id": "J-no-adapter-arm-at-v6w-config", "kind": "judgment", "status": "SUPPORTED", "text": "No LoRA adapter has EVER been served at the v6w config. All five adapter-bearing runs (v2_gate_out, v2_gate_out2, v2_gate_s05c, Outputs/v19_lora, submit_v6z_on_v6w/lora025/out) ran max_tool_calls 15 / 8 min / 24 turns / 120 s timeout, max_output_tokens 6144, frequency_penalty 0.4, thinking_budget 256 and prompt sha256 d7777085b575. v6w is 28/8/80/240, 8192 out-tokens, no frequency penalty, thinking 1024, prompt sha256 9c2fa3587f25. CONSEQUENCES: (1) any adapter-vs-v6w comparison changes 6+ variables at once; (2) the correct matched control for every existing adapter arm is Outputs/v19, which is byte-identical on prompt and config with no adapter; (3) the log's lora025-vs-no-adapter patch_chars comparison on the hard tasks is budget-confounded, not an adapter effect.", "evidence": ["Gemma/v2_gate_s05c/submission/eval_config.yaml", "Gemma/v2_gate_s05c/submission/configs/sampling.yaml", "Gemma/submit_v6z_on_v6w/lora025/out/submission/eval_config.yaml", "Gemma/submit_v6w/out_v6w/submission/eval_config.yaml", "Gemma/kb/runs.jsonl#config.prompt_sha256"], "author": "gemma-auditor 2026-10-16 (adapter-strength-calibration audit)"},
  {"id": "J-pertask-edit-bar-is-noise", "kind": "judgment", "status": "SUPPORTED", "text": "A per-task 'edit-attempts AND patch_chars not below the control' bar cannot be used on a 5-6 task rich gate at n=1 per arm: scored on two NO-ADAPTER exact-replicate pairs (same prompt sha 9c2fa3587f25, same 28/8/80/240 config, same 6 tasks) it returns 2/6 not-below for both, and the v6x-vs-v6t pair also trips 'materially below on >=2 tasks', i.e. it labels a zero-adapter arm OVER-STRONG. The measured overbake signature is categorical instead: 0 structured tool calls, malformation share -> 1.0, end_reason NUDGE_EXHAUSTED. The no-adapter band at the v6w config (n=5 runs) is resolves 3-4/6, sum patch_chars 1786-3604, tasks-with->=1-edit 5-6/6, mean malformation 0.000-0.059 (per-task max 0.20), tasks with calls=0 always 0.", "evidence": ["Gemma/kb/runs.jsonl#row_id=submit_v6x/out_v6x::rich_3471", "Gemma/kb/runs.jsonl#row_id=submit_v6t/out_v6t::rich_3471", "Gemma/kb/runs.jsonl#row_id=submit_v6w/out_v6w::rich_4079", "Gemma/kb/runs.jsonl#row_id=submit_v6y/out_v6y::rich_4079"], "author": "gemma-auditor 2026-10-16 (adapter-strength-calibration audit)"},
  {"id": "J-multi-arm-one-kernel", "kind": "judgment", "status": "SUPPORTED", "text": "A free gate CAN run several adapter strengths plus a no-adapter control in ONE kernel on one vLLM server. discover_adapters catalogues every adapters/<name>/adapter_model.safetensors and create_model_registry registers each as its own model id (plus an adapter:<name> alias); compile_submission(submission_dir=...) is called inside the per-task agent run, so rewriting agent.yaml's 'adapter:' line between arms takes effect on the next task. The served id is recorded per step in the trace as model_name (e.g. 'main_lora' vs the base model path), so arm identity is auditable. Size limit: max_total_size_bytes = 3 GiB including adapters/, so three copies of the 410-module artifact (979 MB each) = 2.94 GB is at the wall while three copies of the 110-module artifact (175 MB) = 526 MB is safe.", "evidence": ["Gemma/harness_src/x/adk_submission/server.py#L397", "Gemma/harness_src/x/adk_submission/discovery.py#L384", "Gemma/harness_src/x/swegemma/harness/agent_runner.py#L616", "Gemma/harness_src/x/swegemma/evaluate.py#L316", "Gemma/harness_src/x/adk_submission/limits.py#L184", "Gemma/v2_gate_out2/results/traces/trace_rich_4077.json#step_id=3"], "author": "gemma-auditor 2026-10-16 (adapter-strength-calibration audit)"},
  {"id": "J-0.13-is-sampling-only", "kind": "judgment", "status": "SUPPORTED", "text": "The scored 0.13 run (submission 57201051, 2026-10-15) is v6w with a SAMPLING-ONLY change: submit_v7_temp1/out/submission/prompts/system.md has SHA-256 prefix 9C2FA3587F25, byte-identical to submit_v6w/out_v6w's prompt, and its eval_config.yaml is the same 28/8/80/240; sampling.yaml differs only by temperature 0.2 -> 1.0 and the addition of top_k 64 (top_p 0.95, 8192 out-tokens, thinking 1024 unchanged). So temperature 1.0 + top_k 64 cost -0.02 LB versus v6w @ 0.15. submit_v7_temp1 contains no results/ directory, so there are no dev traces for that run: the 0.13 datum is an LB delta only and cannot be diagnosed behaviorally.", "evidence": ["Gemma/submit_v7_temp1/out/submission/configs/sampling.yaml", "Gemma/submit_v7_temp1/out/submission/eval_config.yaml", "Gemma/submit_v7_temp1/out/submission/prompts/system.md", "Gemma/submit_v6w/out_v6w/submission/prompts/system.md", "Gemma/kb/curated/submissions.csv"], "author": "gemma-auditor 2026-10-16 (adapter-strength-calibration audit)"},
  {"id": "J-branch-final-scored-0.12", "kind": "judgment", "status": "SUPPORTED", "text": "Submission 57146757 (branch_final, PER-TASK BRANCHING) is COMPLETE at publicScore 0.12 in curated/submissions.csv, BELOW the v6w baseline of 0.15. The PENDING statements in .kiro/steering/gemma-submission-protocol.md, kb/curated/run_labels.json:pending and KB_SUMMARY section 7 are stale, and verdicts previously held at NEEDS-DATA pending that score can now be decided. Separately, KB_SUMMARY's BASELINE banner asserts that gemma-submission-protocol.md 'still says v6 @ 0.12 and is STALE'; the steering file as of 2026-10-16 names v6w @ 0.15 (submission 57098497) as live-best, so the banner's claim about steering is itself stale. Baseline unchanged: v6w @ 0.15.", "evidence": ["Gemma/kb/curated/submissions.csv", "Gemma/kb/curated/run_labels.json", "Gemma/kb/KB_SUMMARY.md", ".kiro/steering/gemma-submission-protocol.md"], "author": "gemma-auditor 2026-10-16 (adapter-strength-calibration audit)"}]}
-->
