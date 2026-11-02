VERDICT: REVISE

# Audit — commitment behavior-clone LoRA recipe (decoder-first, LoRA as sequenced fallback)

- Proposal: `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\proposals\2026-10-14-commitment-lora-recipe.md`
- Mode: AUDIT (step 2 of `gemma-audit`), date 2026-10-15, slug `commitment-lora-recipe`
- KB: `check-fresh` = FRESH; `build_meta.json` inputs_fingerprint `80f7600f925f`; build stamp 2026-10-15T14:20:58Z
- Baseline used: **v6w @ 0.15** (`Gemma\kb\curated\submissions.csv` ref 57098497, COMPLETE; `curated\run_labels.json:baseline`). `.kiro\steering\gemma-submission-protocol.md` has been updated and now names v6w @ 0.15 itself — the `KB_SUMMARY.md` banner still calls that steering file stale, and **that banner is the out-of-date artifact**, not the steering file. The stale live-best claim now lives in `Gemma\GEMMA_EXPERIMENT_LOG.md` READ-THIS-FIRST item 4 ("v6 @ 0.12 SACRED", L27-29). [MEASURED]

Every claim below is tagged MEASURED or INFERRED and cites a path. No gold text or problem-statement text is reproduced.

---

## 1. Suggestion restated

Two gated stages against the fixed `gemma-4-31b-it-qat-w4a16-ct`, aimed at the skill "once the fault is localized, emit `edit_file` instead of another grep/read/pytest":

- **Stage A (first, zero-GPU):** sweep decode/budget dials one at a time — `frequency_penalty` (around 0.4), `presence_penalty`, `temperature`/`top_p`, and the `get_status` reserve-tail / edit-shape knob — judged offline via `Gemma\train\eval_hf_adapter.py` on a "by-task holdout".
- **Stage B (only if A misses):** a commitment behavior-clone LoRA on self-distilled, two-key-filtered passing trajectories from public GitHub issues; dict-structured `arguments` + `apply_chat_template`, round-trip parser validation, assistant-only loss masking, r=16 / alpha=32 (alpha=2r), all-linear text-decoder, LR 1e-4, 1 epoch, packing off, replay/anchor mix.
- **Shared pre-registered bar:** a lever "moves commitment" iff edit-attempt rate rises from "3/5 made 0 edits → 2/5" to **≥4/5**, AND resolves do not drop below **2/5**; null = the no-change v6 decode config at the same budget; targets named as rich_4079, rich_4076, rich_3469.
- Explicit scorer-gaming guard (no gold patches, no problem-statement fingerprints, no task-id conditioning), citing `Gemma\VULN_PUBLIC_TASK_PATCH_STAGING.md`.

The proposal asks the audit to settle six items; sections 5–9 below answer all six.

---

## 2. Prior art

| Lever in the proposal | Tag | Evidence |
|---|---|---|
| `frequency_penalty` ≈ 0.4 to break repeat loops | **RE-RUN** | Run in v19 (`Gemma\GEMMA_EXPERIMENT_LOG.md` L5718-5727) and again in the shipped lineage as v6x/v6y, where the log records the repetition-penalty variants as **negative** (L8878-8879). [MEASURED] |
| `get_status` reserve-tail + edit-shape | **RE-RUN** | v19 lever #2, "KILLED search-death: every task now REACHES an edit" (L5725-5727); it is a prompt/agent-yaml lever, and READ-THIS-FIRST item 5 (L30-32) names reserve-tail among the exhausted prompt levers. [MEASURED] |
| `presence_penalty` | NEW (never run) | Only appears as a candidate in the lever list at L5060-5065; no run carries it. [MEASURED] |
| `temperature` / `top_p` / `top_k` sweep | **NEW on the board** | "no Kaggle submission has used temp 1.0 or top_k (all temp 0.2)" (L8881-8882); every shipped `configs\sampling.yaml` is temp 0.2 / top_p 0.95 (`Gemma\submit_v6w\out_v6w\submission\configs\sampling.yaml`). A local oracle probe exists: temp 0.2 ×1 = 5/12, temp 1.0/top_k 64 ×3 = 14/36 on the same tasks, "task-determined, not sampling noise" (L8858-8866). [MEASURED] |
| Action/tool-call-shaped trajectory SFT with assistant-only loss masking and template-rendered args | **VARIANT (large overlap)** | `Gemma\train\build_stage2_transitions.py` already emits a `call:...{...}` tool-call trajectory as structured `{"messages":[user,assistant]}` for template render + assistant-turn loss mask; the log's CORRECTION #2 (L2492-2505) retracts "taught content not action" and states the target FORM was already correct. [MEASURED] |
| Low-rank / low-strength ablation (r8, alpha 16) + arg-length lever | **RE-RUN of a killed methodology** | Pre-registered at L2535-2560, run and **KILLED** at L2613-2625: local 12B base produced 0/10 on the rich held-out, so the bar lost discriminating power; the log's own prescription was to move the validation to fastapi held-out where the baseline is non-zero. [MEASURED] |
| Serve-scale dose sweep 0.5 / 0.75 / 1.0 | **RE-RUN on confounded ground** | The dose-response was measured through GGUF-over-Ollama-blob and is explicitly listed as confounded/retracted, root-caused to base mismatch (L2672-2696, L2720-2726). A 31B serve-scale arm was then run for real: lora025 at effective 0.5 = **0/3**, with 2 of 3 tasks banking nothing where the no-adapter arm banked 1187/465 chars (L8273-8290). [MEASURED] |
| Adapter path at all | External judge already spoke | LB 0.05 (`curated\submissions.csv` ref 57054171) vs v6w 0.15 (57098497); the log calls it "the worst number we have ever recorded" (L8294-8296). [MEASURED] |

Config diff vs the baseline: Stage A changes sampling only; Stage B adds one adapter. Both are single-variable in the gate sense. The sequencing discipline (zero-GPU falsifier first) is sound and matches the log's own L5104-5107 reasoning.

---

## 3. Ground truth per task (from `Gemma\kb\tasks_gold.json`, mechanical class only — no gold text)

| task | class | gold files | hunks | added test |
|---|---|---|---|---|
| rich_3469 | EASY | `rich/markdown.py` | 1 | `tests/test_markdown.py::test_table_with_empty_cells` |
| rich_4076 | EASY | `rich/ansi.py` | 1 | `tests/test_ansi.py::test_decode_newlines` |
| rich_4077 | EASY | `rich/file_proxy.py` | 1 | `tests/test_file_proxy.py::test_isatty` |
| rich_4079 | EASY | `rich/markdown.py` | 1 | `tests/test_markdown.py::test_inline_code_in_table_cells` |
| rich_4070 | **HARD** | 9 files (`rich/console.py`, `rich/segment.py`, `rich/syntax.py`, …) | **33** | none added; `tests/test_console.py`, `tests/test_syntax.py` |

[MEASURED] The judging set the bar names is 4 EASY single-hunk tasks plus one 33-hunk, 9-file release-batch diff (rich_4070) that no single commit-fast edit can produce. rich_4070 is 0/13 across all runs (`B card --task rich_4070`).

---

## 4. Behavior per task per run (the runs the proposal's C-series rests on)

From `Gemma\kb\runs.jsonl`, `Gemma\kb\near_miss.jsonl`, and the raw trace `Gemma\v2_gate_s05c\results\traces\trace_rich_4070.json`.

**The adapter arms are three different objects, and the proposal treats them as one.** [MEASURED]

| run | packaged adapter (`submission\adapters\main_lora\adapter_config.json`) | per-task outcome |
|---|---|---|
| `v2_gate_out2` | **r=32, alpha=64, 410 modules** (the trained v2 adapter, α/r = 2.0) | all 5 tasks: `tool_calls=0`, `patch_chars=0`, `end_reason=NUDGE_EXHAUSTED`, `furthest_stage=None`, `stopped_by=NEVER_ATTEMPTED` |
| `v2_gate_s05c` | **r=32, alpha=16, 410 modules** (a `make_variant.py --scale 0.5` derivative) | 3469 edits=0 (furthest=None) · 4076 edits=0 (furthest=None) · 4079 edits=0 (furthest=READ_GOLD_FILE) · 4070 edits=16, 13 malformed, argrej=13, WRONG-FIX · 4077 RESOLVED |
| `v2_gate_out` | **r=4, alpha=8, 2 modules** — does not match the trained v2 adapter at all | 3469 edits=4 · 4070 edits=12 (10 malformed) · 4076 edits=1 · 4077 RESOLVED · 4079 edits=6 (11 malformed) → **edits on 5/5** |

`Gemma\train\make_variant.py` L5-6 and L53-54 document that the strength dial works *by rewriting `lora_alpha`* to set effective scale α/r, with scale 0 = no-op. So **α/r = 0.5 is the serve-scale setting of the s05c arm, not a training hyperparameter mistake.** The training record (log L5853-5860) and `Gemma\adapter_v2_dataset\adapter_config.json` both read r=32 / alpha=64 / 410 all-linear modules. [MEASURED]

Baseline arms on the same tasks:

| run | 3469 | 4070 | 4076 | 4077 | 4079 | edits ≥1 | resolves |
|---|---|---|---|---|---|---|---|
| `_v6out` (v6, LB 0.12) | *not in run* | 4 edits, WRONG-FIX | 0 edits, LOCATE/NO_GOLD_FILE | RESOLVED | RESOLVED | 3/4 | **2/4** |
| `submit_v6w/out_v6w` (live-best) | *not in run* | *not in run* | 2 edits, LOCATE/NO_GOLD_FILE | RESOLVED | **0 edits**, furthest=SAW_GOLD_HUNK, stopped_by=NEVER_ATTEMPTED | 2/3 | 1/3 |
| `Outputs/v19` (freq_penalty 0.4 + reserve-tail) | 1 | 5 | 3 | 5 | 1 | **5/5** | 1/5 |
| `Outputs/v19v3` | 0 | 7 | 10 → WRONG-FIX | 3 | 0 | 3/5 | 1/5 |
| `submit_v21/out_v21` | 1 | 0 | 2 | 5 | 1 | 4/5 | 1/5 |

[MEASURED] Two things fall out. First, `_v6out` has **no rich_3469 row** — the "v6 = 2/5" figure the bar uses as its floor was measured on a 4-task set, and no run in the KB has ever scored 2 resolves on the 5-task set the bar names. Second, **v6w (the live-best) does not resolve rich_4079** and `submit_v6w/out_v6w` rich_4079 is the one clean commitment failure in the shipped lineage: it reached `SAW_GOLD_HUNK` and never attempted an edit.

---

## 5. Failure classification (§10 definitions)

- `v2_gate_out2` × all 5: **INFRA-shaped**, 0 tool calls on every task, `end_reason=NUDGE_EXHAUSTED`, `stopped_by=NEVER_ATTEMPTED`. KB stage-classifies them LOCATE/NO_GOLD_FILE; the log's own ledger labels this arm "0/5 OVERBAKED" (L8300-8302). [MEASURED]
- `v2_gate_s05c` × rich_3469, rich_4076: **LOCATE / NO_GOLD_FILE** — `furthest_stage=None`, the gold file is never read. These are *not* commitment failures. [MEASURED]
- `v2_gate_s05c` × rich_4079: **LOCATE / FILE_NOT_HUNK**, `furthest_stage=READ_GOLD_FILE` — strictly *worse localization* than v6w's `SAW_GOLD_HUNK` on the same task. [MEASURED]
- `v2_gate_s05c` × rich_4070: **WRONG-FIX** with a malformation share of 0.59 (13 of 22 structured calls), decided by `ARG_REJECTED` ×13; the raw trace carries 13 "mandatory input parameters are not present:" observations beginning at step_id 14. Tool-call malformation is config-attributable, so this row carries `~`, not INFRA. [MEASURED]
- `submit_v6w/out_v6w` × rich_4079: **FOUND-NOT-LANDED / SAW_ONLY**, `stopped_by=NEVER_ATTEMPTED`, 0 edit calls, no submit. This is the genuine instance of the skill the proposal targets. [MEASURED]

**Consequence for the proposal's premise.** Of the three tasks it names as commitment-death, two (rich_3469, rich_4076) never opened the gold file in that run, and the third (rich_4079) stopped one stage short of v6w. And in the regime we actually ship, the log's own trace recount finds **only 2 of 34 runs (28-call regime: v6w/x/y/c/t/b) made no edit attempt at all** (L8880-8884) — an edit-attempt rate near 94%. The "2/5" search-death baseline belongs to the 15-call v19/v2-gate regime, not to the 0.18 lineage the bar's null names. [MEASURED]

---

## 6. Replays / tests run

| command | result |
|---|---|
| `python Gemma\kb\build_kb.py check-fresh` | FRESH (exit 0) |
| `python Gemma\kb\build_kb.py report-path --date 2026-10-15 --slug commitment-lora-recipe --kind audit` | this path (exit 0) |
| `python Gemma\kb\build_kb.py card --task rich_{3469,4070,4076,4077,4079}` | full run histories; used for §4 and the resolve counts |
| `python Gemma\kb\build_kb.py leakcheck --scope config <proposal>` | **exit 1 — LEAK task_id: rich_3469, rich_4076, rich_4079** (bare dev task ids; no gold text, no problem-statement text) |
| `python Gemma\kb\build_kb.py leakcheck --scope tooling <proposal>` | CLEAN (exit 0) |
| `python Gemma\kb\build_kb.py pull --submissions` | **not implemented in this build** ("pull is read-only and not executed in this build iteration"), exit 1 — so the branch_final score stays UNVERIFIABLE |
| gold-first replay status read from `Gemma\kb\replays\gold\*.json` | **rich_3469 INVALID · rich_4070 INVALID · rich_4079 INVALID · rich_4076 VALID-HARNESS-LIKE**; `replays.jsonl` has **0 rows for rich_4077** |
| raw-trace scan of `Gemma\v2_gate_s05c\results\traces\trace_rich_4070.json` | 30 steps, 13 × "mandatory input parameters are not present:" from step_id 14 — C3's signature confirmed against the raw file |
| on-disk adapter config scan (`Gemma\*\adapter_config.json`, `*\submission\adapters\main_lora\adapter_config.json`) | trained v2 = r32/α64/410 all-linear; `adapter_v2_s05` = r32/α16/410; `v2_gate_out` packaged = r4/α8/2 modules |
| static read of `Gemma\train\eval_hf_adapter.py` | `BASE = "google/gemma-4-E2B-it"` hardcoded; single `--task`; `generate()` passes only `do_sample`/`temperature`/`top_p`/`pad_token_id` — no frequency or presence penalty |

No agent commands were re-run; no Kaggle push; no manual replay candidates were needed because the deciding facts were already on disk. Scratch files under `%TEMP%` were removed.

---

## 7. Variance

- **rich_4079 is a coin flip.** 6 resolves in 32 attempts (log L9246-9247, corrected refute recount; consistent with the card: resolved under `_v6out`, `v6c`, `v6t`, `v6z-armA`, `Outputs/v10`, `Outputs/v12_v2`; not under v6b/v6s/v6v/v6w/v6x/v6y/armB/armC/v6z_on_v6w/v7_d/v21/v19/v19v3). Several of those arms are near-identical configs (same 28/8/80/240 budget family), so this is within-config variance, not a lever difference. [MEASURED]
- **rich_4077 is near-deterministic:** 26/32. **rich_3469 0/18, rich_4076 0/32, rich_4070 0/13.** [MEASURED]
- Therefore "resolves ≥ 2/5" on this set ≈ "rich_4079 must land", a Bernoulli with p ≈ 0.19 at n = 1. A single run of *any* change fails that clause ~81% of the time and passes it ~19% of the time for reasons unrelated to the change. [INFERRED from the measured 6/32]
- **No config has a replicate anywhere in the project** (log L8869-8872: "No replicate of ANY config exists… Run-to-run noise is still unquantified"), and the harness runs at temp 0.2, n=1. [MEASURED]

---

## 8. Rules check

| rule | status |
|---|---|
| Pre-register the bar (acct. 2) | Partially met: a bar exists, but its floor (2/5) was measured on a different 4-task set and has never been achieved on the 5-task judging set. **FAIL as written.** |
| External judge only (acct. 1) | **FAIL:** the stated judge is `eval_hf_adapter.py` on an E2B base — the same local-on-rich methodology already killed as non-discriminating (log L2613-2625), and the resolve clause is unmeasurable there (gold INVALID for 3469/4070/4079, no replay row for 4077). |
| Adversarial / dev-vs-eval separation (acct. 5) | **FAIL:** the "by-task holdout that shares NO tasks with any tuning split" is contradicted two paragraphs later by a bar naming the five rich tasks that ~20 configs have been tuned on. |
| No extrapolation (acct. 4) | **FAIL:** the 2/5 edit-attempt baseline (15-call regime, half-strength adapter) is applied to the 28-call shipped regime, where the measured rate is 32/34. |
| Tune before concluding (acct. 13) | Honoured in spirit (Stage A is a sweep), but the Stage A mechanism diagnostic was already run in v19 and must be re-read, not re-assumed. |
| Floor-guaranteed composition (acct. 15) | Partially met: Stage B keeps a resolve floor, but the adapter lever has no w=0-allowed blend at serve; the only strength dial is `make_variant.py`, and its 0.5 arm measured 0/3 (log L8277-8285). |
| Novelty leads / gate failure is a debugging task (acct. 10, 11) | Honoured — this audit does **not** recommend abandoning the weights lever. The defects named here are in the bar, the judge, and the v2 diagnosis, not in the idea. |
| One change per gate (protocol) | Met for Stage A; met for Stage B provided the data recipe and hyperparameters ship as one adapter against an unchanged prompt. |
| Free gate before scored slot (protocol) | Met and explicitly stated. |
| Leakcheck (protocol / forbidden list E) | **config scope FAILS** on 3 bare task ids; tooling scope CLEAN. No gold or problem-statement content present. Must not carry task ids into any prompt/config text. |
| Live-best baseline named correctly | Partially: the proposal's resolve floor is v6's dev 2/5, not the policy baseline v6w. Steering now agrees with `submissions.csv` on v6w @ 0.15; the log's READ-THIS-FIRST item 4 is the stale artifact. `branch_final` (57146757) is PENDING in `submissions.csv` while log §E reports 0.12 for it — reported, not adopted; `B pull --submissions` is unimplemented, so it is UNVERIFIABLE. |

---

## 9. Cheapest falsifying test (run, offline)

The bar's own premise was falsifiable from data already on disk, and it falsifies:

1. **Edit-attempt rate in the shipped regime** — 2 of 34 runs made no edit attempt (log L8880-8884). A bar that asks a change to raise edit-attempt rate to ≥4/5 is asking the baseline to beat itself; it cannot discriminate. [MEASURED]
2. **Stage A's lever already cleared the commitment clause and did not move resolves** — v19 reached edits on 5/5 with resolve 1/5 (log L5723-5727; `Outputs/v19` rows). [MEASURED]
3. **The resolve clause is unmeasurable on the stated judge** — gold-first is INVALID for rich_3469/4070/4079 and there is no replay row for rich_4077. [MEASURED]
4. **The alpha prescription targets a non-defect** — `adapter_v2_dataset` is α/r = 2.0; α/r = 0.5 is the `make_variant.py` scale dial, and the α/r = 0.5 arm was the *better* of the two (1/5 vs 0/5 "OVERBAKED", log L8300-8302). [MEASURED]

The remaining zero-GPU falsifier the proposal itself names — the loss-mask inspection (assert mean_loss > 0, masked-token count == assistant-turn count, tool-result tokens masked) plus a round-trip parse of every candidate row — is correct and still unrun. It should run before any GPU cycle, and it should be paired with the `--maxlen` check below.

---

## 10. Verdict rationale — REVISE

The direction survives: training/nudging *behavior* rather than content, sequencing the zero-GPU falsifier first, and refusing to treat edit-anchors as the target are all consistent with the measured record, and the weights lever is not disproven by a mis-executed gate. What cannot ship as written is the evidence base and the bar.

Six things must change before this is a recommendation:

1. **Re-anchor the premise to the shipped regime.** "Commitment" as a *population* failure is a 15-call-regime artifact: 2/34 in the 0.18 lineage. The one real instance is `v6w` × rich_4079 (`SAW_GOLD_HUNK`, `NEVER_ATTEMPTED`). Either target that specific mechanism (reached the hunk, spent the call budget re-reading, never attempted) with a bar measured on ranged-read/commit opportunities, or adopt the target the latest measured entry names: **WRONG-FIX / wrong_content, 34 of 56** (log L9455-9470).
2. **Fix the bar.** Drop the 2/5 edit-attempt floor (pre-passed). Drop rich_4070 (HARD, 33 hunks, 0/13) from the judging set. State the resolve floor against a **paired baseline arm run byte-identically on the same task set** — no such v6w arm exists across rich_3469/4076/4079, so the baseline arm must run first. Condition the mechanism clause on *opportunities* (a commit-sooner bar passes vacuously where the gold file is never opened).
3. **Fix the judge.** `eval_hf_adapter.py` is an E2B single-task plumbing script that cannot vary `frequency_penalty`/`presence_penalty` at all, cannot score resolve where gold is locally invalid, and produces an adapter object that **cannot serve on the 31B** (dim mismatch, log L9490-9492). The same local-on-rich comparison was already killed for zero baseline. Either repair the local rig to the parity level described at log L8820-8840 (real edit engine, bash, uncut results, 80-turn cap) and judge on a set with non-zero baseline, or make the FREE Kaggle 5-task rich gate the first judge and say so.
4. **Correct the v2 facts and re-derive the hyperparameters from them.** v2 trained at r=32 / α=64 / 410 all-linear modules. The full-strength arm made **zero tool calls on 5/5**; the α/r = 0.5 arm is the one that scored 1/5. So "alpha = 2r fixes v2" is backwards, and the log's own measured recommendation is the opposite: **q/v only, r = 8-16, α/r ≤ 1, 1 epoch, capacity matched to ~45-100 examples, NOT 410 modules, early-stop on a behavioral metric** (log L9487-9494). Also resolve which adapter `v2_gate_out` actually served — its packaged config is r=4/α=8/2 modules, so every C-series claim sourced from that run is UNVERIFIED until that is settled.
5. **Drop serialization as a training target.** Malformed-`edit_file` share by shipped prompt: candidate D 0/8, v6w 2/15 (13%), vs v19v3 8/14 (57%), the v2-adapter-gate prompt 31/39 (79%), `v2_gate_s05c` 13/16 (81%), lora025 6/6 (100%) — the log's conclusion is that the serialization catastrophe belongs to the v19 prompt family and to the adapters, and "a LoRA trained to fix serialization would train against a distribution we do not ship" (L9470-9480). Keep the dict-`arguments` / round-trip / template-parity hygiene as *data hygiene* (it is correct and cheap); do not keep it as the *objective*. Likewise, the mandated 0.5/0.75/1.0 dose sweep rests on a measurement retracted as an Ollama-base-mismatch artifact (L2672-2696, L2720-2726) and on a 31B 0.5 arm that already measured 0/3.
6. **Keep task ids out of any config or prompt text.** `leakcheck --scope config` on the proposal exits 1 on rich_3469 / rich_4076 / rich_4079. The proposal's own forbidden-list discipline is otherwise correct — no gold, no fingerprints, no task-id conditioning — and the "public tasks are fuel, not answers" framing is consistent with `Gemma\VULN_PUBLIC_TASK_PATCH_STAGING.md`.

Answers to the six questions the proposal asked the audit to settle:

- *Is decoder-first right?* Yes as sequencing, but the specific dials are mostly spent: `frequency_penalty` 0.4 ran in v19 (and negative in v6x/v6y) and the reserve-tail is a prompt lever already in the exhausted set. The genuinely untried dial is **temperature / top_k / min_p** — never used on the board, with a local oracle lead. Make that the Stage A change.
- *Does the loss-mask inspection confirm C3 first?* It is the right zero-GPU falsifier and is still unrun; run it with the round-trip parse. Add the trainer constraint the log found: `train_lora.py` defaults `--maxlen 768` while the current trajectories run median ~3600 tokens, so any run must pass `--maxlen >= 8192` or it silently reproduces the already-fixed truncation null (L9483-9486).
- *Can the stack reproduce W4A16 for quant-matched training?* Already determined: **no** — "quantization-matched training | impossible on 31B: w4a16 is serving-only, no grad path" (L8300-8306). bf16-twin → INT4-serve is the only path; this is a closed question, not an open one.
- *Is ≥4/5 on five tasks meaningful?* No. 3 of the 5 have never resolved (0/18, 0/32, 0/13) and the fourth is 6/32, so the resolve clause reduces to one p≈0.19 coin at n=1, with no replicates anywhere in the project to bound noise.
- *Round-trip validation of every row?* Correct and required; unrun.
- *Prior art per lever?* Section 2. Two RE-RUNs, one re-run on confounded ground, one large VARIANT, one genuinely NEW dial.

---

## 11. What the suggestion missed

1. The v2 adapter's actual training hyperparameters (r32/α64/410 all-linear) and the fact that α/r = 0.5 is a deliberate serve-scale dial, not a defect — so the headline hyperparameter "fix" is a no-op aimed backwards.
2. That the full-strength v2 arm (`v2_gate_out2`) made **zero tool calls on all five tasks**, and that C1/C2/C3 therefore describe the half-strength arm plus a run whose packaged adapter is a 2-module r4/α8 object.
3. That in the shipped 28-call regime only 2 of 34 runs made no edit attempt — the premise's search-death rate is regime-specific.
4. That v19 already cleared the edit-attempt clause at 5/5 without moving resolves, and that `frequency_penalty` 0.4 was negative in the shipped lineage (v6x/v6y).
5. That rich_3469 and rich_4076 are LOCATE-stage in the very run cited (gold file never read, 0/18 and 0/32 lifetime), so a commit-sooner lever cannot resolve them — and when later configs did raise their edit count, the outcome was WRONG-FIX.
6. That the live-best v6w does **not** resolve rich_4079 and that `_v6out` never ran rich_3469, so the "v6 = 2/5" floor was never measured on the judging set.
7. That gold-first replay is INVALID for rich_3469/4070/4079 and absent for rich_4077, making the offline resolve clause unmeasurable.
8. That `eval_hf_adapter.py` is E2B-only, single-task, cannot set frequency/presence penalties, and yields an adapter that cannot serve on the 31B — and that the local-on-rich comparison was already killed for a floored baseline.
9. That the log's latest measured recommendation points at WRONG-FIX/wrong_content with q/v-only, α/r ≤ 1, ≤100 examples — the opposite of all-linear / α=2r.
10. That serialization was explicitly dropped as a LoRA target because it is off the shipped prompt's distribution.
11. The `--maxlen 768` trainer default, which would silently reproduce the known mean_loss≈0 truncation null.
12. That quant-matched 31B training is already settled impossible, and that the adapter lever has an external-judge datum: LB 0.05 vs v6w 0.15.

---

## 12. Measured vs inferred

**MEASURED** (raw files, traces, on-disk configs, curated submissions): all adapter configs and module counts; `v2_gate_out2` 0-tool-call outcome; `v2_gate_s05c` per-task edit counts, malformation shares and the 13 raw argument-rejection observations; `_v6out` / `v6w` / `v19` / `v19v3` / `v21` per-task edit counts and resolves; near-miss furthest stages and stop reasons; per-task lifetime resolve counts (3469 0/18, 4070 0/13, 4076 0/32, 4077 26/32, 4079 6/32); gold file/hunk/test metadata and mechanical classes; gold-first replay validity; `eval_hf_adapter.py` base and sampling surface; `make_variant.py` alpha-rewrite semantics; the 2-of-34 no-edit-attempt recount; the malformed-`edit_file` share by prompt; the lora025 0/3 result; LB scores; both leakcheck results; the unimplemented `pull --submissions`.

**INFERRED** (labelled, not verdicts): that the resolve clause reduces to a p≈0.19 single-Bernoulli at n=1 (arithmetic on the measured 6/32); that an E2B-based offline arm will floor at least as hard as the measured 12B 0/10 on rich; that raising edit-attempt rate on a task whose gold file is never opened produces wrong-fix rather than resolve (supported by `v19v3` rich_4076 = 10 edit calls → WRONG-FIX, but not a randomised test); that Stage A's remaining power sits in temperature/top_k (a local-oracle lead at n=3, explicitly "a lead, not a finding" in the log).

**UNVERIFIABLE here:** `branch_final` (ref 57146757) — PENDING in `curated\submissions.csv`, reported as 0.12 in log §E; `pull --submissions` is not implemented in this build, so the conflict stands unresolved and the baseline remains v6w @ 0.15. Which adapter `v2_gate_out` actually served at runtime (the packaged config contradicts the trained artifact).

<!-- AUDIT-JSON
{"schema": "gemma-audit/1", "mode": "AUDIT", "verdict": "REVISE",
 "proposal": "c:\\Users\\Biges\\OneDrive\\Documents\\Desktop\\kAGGLE\\Gemma\\kb\\proposals\\2026-10-14-commitment-lora-recipe.md",
 "kb_inputs_fingerprint": "80f7600f925f",
 "targets": ["rich_3469", "rich_4070", "rich_4076", "rich_4077", "rich_4079"],
 "prior_art": [
  {"lever": "frequency_penalty ~0.4 to break repeat loops", "tag": "RE-RUN", "runs": ["Outputs/v19", "submit_v6x/out_v6x", "submit_v6y/out_v6y"]},
  {"lever": "get_status reserve-tail + edit-shape (commit sooner)", "tag": "RE-RUN", "runs": ["Outputs/v19"]},
  {"lever": "presence_penalty", "tag": "NEW", "runs": []},
  {"lever": "temperature/top_p/top_k sweep on the board", "tag": "NEW", "runs": []},
  {"lever": "action-shaped tool-call trajectory SFT, assistant-only loss mask, template-rendered args", "tag": "VARIANT", "runs": ["v2_gate_out2", "v2_gate_s05c", "Outputs/v19_lora"]},
  {"lever": "low-rank/low-strength adapter ablation judged on local rich held-out", "tag": "RE-RUN", "runs": ["train/adapters/fastapi_spec12b_r8"]},
  {"lever": "serve-scale dose sweep 0.5/0.75/1.0", "tag": "RE-RUN", "runs": ["v2_gate_s05c", "submit_v6z_on_v6w/lora025/out"]},
  {"lever": "alpha=2r as a fix for v2", "tag": "RE-RUN", "runs": ["v2_gate_out2"]}
 ],
 "per_task": [
  {"run_id": "v2_gate_out2", "task": "rich_4079", "failure_class": "INFRA-shaped (0 tool calls)", "subclass": "NEVER_ATTEMPTED",
   "evidence": ["Gemma/kb/runs.jsonl#row_id=v2_gate_out2::rich_4079", "Gemma/kb/near_miss.jsonl#run_id=v2_gate_out2", "Gemma/v2_gate_out2/submission/adapters/main_lora/adapter_config.json"]},
  {"run_id": "v2_gate_s05c", "task": "rich_3469", "failure_class": "LOCATE", "subclass": "NO_GOLD_FILE",
   "evidence": ["Gemma/kb/runs.jsonl#row_id=v2_gate_s05c::rich_3469", "Gemma/kb/near_miss.jsonl#run_id=v2_gate_s05c furthest_stage=None"]},
  {"run_id": "v2_gate_s05c", "task": "rich_4076", "failure_class": "LOCATE", "subclass": "NO_GOLD_FILE",
   "evidence": ["Gemma/kb/runs.jsonl#row_id=v2_gate_s05c::rich_4076"]},
  {"run_id": "v2_gate_s05c", "task": "rich_4079", "failure_class": "LOCATE", "subclass": "FILE_NOT_HUNK",
   "evidence": ["Gemma/kb/runs.jsonl#row_id=v2_gate_s05c::rich_4079", "Gemma/kb/near_miss.jsonl#furthest_stage=READ_GOLD_FILE"]},
  {"run_id": "v2_gate_s05c", "task": "rich_4070", "failure_class": "WRONG-FIX", "subclass": "ARG_REJECTED~",
   "evidence": ["Gemma/v2_gate_s05c/results/traces/trace_rich_4070.json#step_id=14", "Gemma/kb/runs.jsonl#row_id=v2_gate_s05c::rich_4070 malform=13/22"]},
  {"run_id": "submit_v6w/out_v6w", "task": "rich_4079", "failure_class": "FOUND-NOT-LANDED", "subclass": "SAW_ONLY",
   "evidence": ["Gemma/kb/runs.jsonl#row_id=submit_v6w/out_v6w::rich_4079", "Gemma/kb/near_miss.jsonl#furthest_stage=SAW_GOLD_HUNK stopped_by=NEVER_ATTEMPTED"]},
  {"run_id": "Outputs/v19", "task": "rich_4076", "failure_class": "LOCATE", "subclass": "NO_GOLD_FILE",
   "evidence": ["Gemma/kb/runs.jsonl#row_id=Outputs/v19::rich_4076 editcalls=3", "Gemma/GEMMA_EXPERIMENT_LOG.md#L5723"]},
  {"run_id": "_v6out", "task": "rich_4079", "failure_class": "RESOLVED", "subclass": null,
   "evidence": ["Gemma/kb/runs.jsonl#row_id=_v6out::rich_4079"]}
 ],
 "claims": [
  {"id": "A1", "text": "The trained v2 adapter is r=32/alpha=64 (alpha/r=2.0), 410 all-linear modules; alpha/r=0.5 is a make_variant.py serve-scale dial, not a training error.", "basis": "MEASURED", "evidence": ["Gemma/adapter_v2_dataset/adapter_config.json", "Gemma/train/make_variant.py#L5", "Gemma/GEMMA_EXPERIMENT_LOG.md#L5857"]},
  {"id": "A2", "text": "The full-strength v2 arm (v2_gate_out2) made 0 tool calls on all 5 tasks; the log ledger records all-linear r32 as 0/5 OVERBAKED and 1/5 at alpha 0.5 - inverting the proposal's alpha=2r prescription.", "basis": "MEASURED", "evidence": ["Gemma/kb/runs.jsonl#v2_gate_out2", "Gemma/GEMMA_EXPERIMENT_LOG.md#L8300"]},
  {"id": "A3", "text": "v2_gate_out's packaged adapter is r=4/alpha=8/2 modules, which does not match the trained v2 adapter; C-series claims sourced from that run are unverified.", "basis": "MEASURED", "evidence": ["Gemma/v2_gate_out/submission/adapters/main_lora/adapter_config.json"]},
  {"id": "A4", "text": "In the shipped 28-call regime only 2 of 34 runs made no edit attempt, so the proposal's 2/5 search-death baseline is regime-specific and the >=4/5 edit-attempt bar is pre-passed by the null.", "basis": "MEASURED", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#L8880"]},
  {"id": "A5", "text": "v19 already ran freq_penalty 0.4 + reserve-tail: edits on 5/5 tasks, resolve 1/5; repetition-penalty variants v6x/v6y were negative in the shipped lineage.", "basis": "MEASURED", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#L5723", "Gemma/GEMMA_EXPERIMENT_LOG.md#L8878", "Gemma/kb/runs.jsonl#Outputs/v19"]},
  {"id": "A6", "text": "Lifetime resolves on the judging set: rich_3469 0/18, rich_4070 0/13, rich_4076 0/32, rich_4077 26/32, rich_4079 6/32; no run has ever scored 2/5 on this 5-task set and _v6out never ran rich_3469.", "basis": "MEASURED", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#L9246", "Gemma/kb/runs.jsonl#card--task"]},
  {"id": "A7", "text": "The resolve clause reduces to one p~0.19 Bernoulli (rich_4079) at n=1 with no config replicates anywhere in the project.", "basis": "INFERRED", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#L9246", "Gemma/GEMMA_EXPERIMENT_LOG.md#L8869"]},
  {"id": "A8", "text": "Two of the three named commitment-death tasks (rich_3469, rich_4076) never read the gold file in that run (furthest_stage=None) - they are LOCATE-stage, not commitment.", "basis": "MEASURED", "evidence": ["Gemma/kb/near_miss.jsonl#run_id=v2_gate_s05c", "Gemma/kb/runs.jsonl#v2_gate_s05c"]},
  {"id": "A9", "text": "Gold-first replay is INVALID for rich_3469/4070/4079 and absent for rich_4077, so the offline resolve clause is unmeasurable on the stated judge.", "basis": "MEASURED", "evidence": ["Gemma/kb/replays/gold/rich_4079.json", "Gemma/kb/replays/replays.jsonl", "Gemma/kb/KB_SUMMARY.md#13"]},
  {"id": "A10", "text": "eval_hf_adapter.py is hardcoded to gemma-4-E2B-it, is single-task, and exposes only temperature/top_p - it cannot sweep frequency or presence penalty, and a 12B/E2B adapter cannot serve on the 31B.", "basis": "MEASURED", "evidence": ["Gemma/train/eval_hf_adapter.py", "Gemma/GEMMA_EXPERIMENT_LOG.md#L9490"]},
  {"id": "A11", "text": "The same local-on-rich adapter methodology was already run and killed: local 12B base produced 0/10 on the rich holdout, so the bar lost discriminating power.", "basis": "MEASURED", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#L2613"]},
  {"id": "A12", "text": "Serialization was dropped as a LoRA target: malformed edit_file share is 0/8 for candidate D and 2/15 for v6w vs 31/39 for the v2-gate prompt and 13/16 for v2_gate_s05c, so it belongs to the v19/adapter distribution we do not ship.", "basis": "MEASURED", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#L9470"]},
  {"id": "A13", "text": "The dose-dependent argument collapse cited as C4 was retracted as an Ollama base-mismatch artifact, and the real 31B scale-0.5 arm (lora025) measured 0/3 with 2 of 3 tasks banking nothing.", "basis": "MEASURED", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#L2672", "Gemma/GEMMA_EXPERIMENT_LOG.md#L8277"]},
  {"id": "A14", "text": "Quantization-matched 31B training is already determined impossible (w4a16 is serving-only, no grad path), so the proposal's open question 3 is closed.", "basis": "MEASURED", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#L8300"]},
  {"id": "A15", "text": "train_lora.py defaults to --maxlen 768 while current trajectories run median ~3600 tokens; any run must pass --maxlen >= 8192 or it reproduces the known mean_loss~0 truncation null.", "basis": "MEASURED", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#L9483"]},
  {"id": "A16", "text": "The one genuine commitment instance in the shipped lineage is v6w x rich_4079: furthest_stage=SAW_GOLD_HUNK, stopped_by=NEVER_ATTEMPTED, 0 edit calls, no submit.", "basis": "MEASURED", "evidence": ["Gemma/kb/near_miss.jsonl#submit_v6w/out_v6w rich_4079", "Gemma/GEMMA_EXPERIMENT_LOG.md#L8884"]},
  {"id": "A17", "text": "leakcheck --scope config on the proposal exits 1 on three bare dev task ids (rich_3469, rich_4076, rich_4079); --scope tooling is CLEAN and no gold or problem-statement text is present.", "basis": "MEASURED", "evidence": ["Gemma/kb/build_kb.py#leakcheck", "Gemma/kb/proposals/2026-10-14-commitment-lora-recipe.md"]},
  {"id": "A18", "text": "Baseline is v6w @ 0.15 (57098497 COMPLETE); steering now agrees and the KB_SUMMARY banner calling it stale is itself outdated; branch_final 57146757 is PENDING in submissions.csv while log section E reports 0.12, and pull --submissions is unimplemented so the conflict is unresolved.", "basis": "MEASURED", "evidence": ["Gemma/kb/curated/submissions.csv", "Gemma/kb/curated/run_labels.json", "Gemma/kb/KB_SUMMARY.md#baseline-banner", "Gemma/GEMMA_EXPERIMENT_LOG.md#L8862"]},
  {"id": "A19", "text": "The external judge has already spoken on the adapter lever: the LoRA submission scored 0.05 (57054171) against v6w 0.15.", "basis": "MEASURED", "evidence": ["Gemma/kb/curated/submissions.csv", "Gemma/GEMMA_EXPERIMENT_LOG.md#L8294"]},
  {"id": "A20", "text": "The judging set is 4 EASY single-hunk tasks plus rich_4070, a 33-hunk 9-file HARD diff that no single commit-fast edit can produce.", "basis": "MEASURED", "evidence": ["Gemma/kb/tasks_gold.json#rich_4070"]}
 ],
 "tests_run": [
  {"cmd": "python Gemma/kb/build_kb.py check-fresh", "result": "FRESH (exit 0)"},
  {"cmd": "python Gemma/kb/build_kb.py report-path --date 2026-10-15 --slug commitment-lora-recipe --kind audit", "result": "printed this report path (exit 0)"},
  {"cmd": "python Gemma/kb/build_kb.py card --task rich_3469|rich_4070|rich_4076|rich_4077|rich_4079", "result": "full run histories; rich_3469 0/18, rich_4070 0/13, rich_4076 0/32 never resolved; rich_4079 resolves in 6 runs"},
  {"cmd": "python Gemma/kb/build_kb.py leakcheck --scope config <proposal>", "result": "exit 1 - LEAK task_id rich_3469, rich_4076, rich_4079 (no gold/problem-statement text)"},
  {"cmd": "python Gemma/kb/build_kb.py leakcheck --scope tooling <proposal>", "result": "LEAKCHECK CLEAN (exit 0)"},
  {"cmd": "python Gemma/kb/build_kb.py pull --submissions", "result": "not implemented in this build (exit 1); branch_final score stays UNVERIFIABLE"},
  {"cmd": "runs.jsonl scan of edit_attempts/malformation/resolve for the 5 gate tasks across v2_gate_*, _v6out, v6w, v6t, v19*, v21, v6z arms", "result": "v2_gate_s05c 2/5 tasks emitted an edit; v2_gate_out 5/5; v19 5/5 with resolve 1/5; _v6out 3/4 with resolve 2/4; v6w rich_4079 0 edit calls"},
  {"cmd": "near_miss.jsonl furthest_stage/stopped_by scan for the same rows", "result": "v2_gate_out2 all None/NEVER_ATTEMPTED; v2_gate_s05c 3469 & 4076 None, 4079 READ_GOLD_FILE; v6w 4079 SAW_GOLD_HUNK/NEVER_ATTEMPTED"},
  {"cmd": "raw read of Gemma/v2_gate_s05c/results/traces/trace_rich_4070.json", "result": "30 steps, 13 'mandatory input parameters are not present:' observations from step_id 14 - C3 signature confirmed"},
  {"cmd": "adapter_config.json scan across Gemma/** and */submission/adapters/main_lora", "result": "trained v2 = r32/alpha64/410 all-linear; adapter_v2_s05 = r32/alpha16/410; v2_gate_out packaged = r4/alpha8/2 modules"},
  {"cmd": "static read of Gemma/train/eval_hf_adapter.py and Gemma/train/make_variant.py", "result": "E2B hardcoded, single --task, no frequency/presence penalty in generate(); make_variant sets effective scale by rewriting lora_alpha"},
  {"cmd": "read of Gemma/kb/replays/gold/*.json", "result": "rich_3469/4070/4079 gold_first=INVALID; rich_4076 VALID-HARNESS-LIKE; no replay row for rich_4077"}
 ],
 "missed": [
  "v2 trained at alpha/r=2.0, not 0.5 - the headline hyperparameter fix is aimed at a dial setting, not a defect",
  "the full-strength v2 arm made 0 tool calls on 5/5 tasks; C1-C3 describe the half-strength arm",
  "v2_gate_out's packaged adapter (r4/alpha8/2 modules) does not match the trained v2 adapter",
  "only 2 of 34 runs in the shipped 28-call regime made no edit attempt, so the >=4/5 edit-attempt bar is pre-passed",
  "v19 already cleared the edit-attempt clause at 5/5 without moving resolves; freq_penalty was negative in v6x/v6y",
  "rich_3469 and rich_4076 are LOCATE-stage (gold file never read) and 0/18 and 0/32 lifetime - a commit-sooner lever cannot resolve them",
  "v6w does not resolve rich_4079 and _v6out never ran rich_3469, so the 2/5 floor was never measured on the judging set",
  "gold-first replay is INVALID for 3 of the 5 tasks and absent for rich_4077, making the offline resolve clause unmeasurable",
  "eval_hf_adapter.py is E2B/single-task, cannot set frequency or presence penalty, and yields an adapter that cannot serve on the 31B",
  "the local-on-rich adapter comparison was already killed for a floored baseline (12B base 0/10)",
  "the log's latest measured recipe points at WRONG-FIX/wrong_content with q/v-only and alpha/r <= 1, not all-linear with alpha=2r",
  "serialization was explicitly dropped as a LoRA target because it is off the shipped prompt's distribution",
  "train_lora.py --maxlen 768 default would silently reproduce the known truncation null",
  "quant-matched 31B training is already settled impossible; the adapter lever already has an LB datum of 0.05 vs v6w 0.15",
  "rich_4070 is a 33-hunk 9-file HARD task and does not belong in a commit-timing judging set",
  "bare dev task ids in the proposal text fail leakcheck --scope config"
 ],
 "proposed_curations": [
  {"id": "J-v2-alpha", "kind": "judgment", "status": "SUPPORTED", "text": "The v2 edit-discipline adapter was TRAINED at r=32/lora_alpha=64 (alpha/r=2.0), 410 all-linear modules. The alpha=16 configs on disk (adapter_v2_s05, adapter_dataset-r32-s0.25, submit_v6z_on_v6w/lora025) are make_variant.py serve-scale derivatives. Any claim that v2 was 'under-driven at alpha/r=0.5' is false.", "evidence": ["Gemma/adapter_v2_dataset/adapter_config.json", "Gemma/adapter_v2_s05/adapter_config.json", "Gemma/train/make_variant.py", "Gemma/GEMMA_EXPERIMENT_LOG.md#L5857"]},
  {"id": "J-v2-arms", "kind": "judgment", "status": "SUPPORTED", "text": "The three v2 gate arms served different adapters: v2_gate_out2 = r32/alpha64/410 (full strength, 0 tool calls on 5/5); v2_gate_s05c = r32/alpha16/410 (half strength, 1/5, the forensic's source); v2_gate_out = r4/alpha8/2 modules (adapter identity unverified). C1-C4 must name the arm.", "evidence": ["Gemma/v2_gate_out2/submission/adapters/main_lora/adapter_config.json", "Gemma/v2_gate_s05c/submission/adapters/main_lora/adapter_config.json", "Gemma/v2_gate_out/submission/adapters/main_lora/adapter_config.json"]},
  {"id": "J-commit-regime", "kind": "judgment", "status": "SUPPORTED", "text": "Zero-edit 'search-death' is a 15-call-regime property. In the shipped 28-call regime 2 of 34 runs made no edit attempt; the one clean instance is v6w x rich_4079 (SAW_GOLD_HUNK / NEVER_ATTEMPTED). Any commitment bar must be measured in the shipped regime and conditioned on opportunity.", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#L8880", "Gemma/kb/near_miss.jsonl#submit_v6w/out_v6w rich_4079"]},
  {"id": "J-local-judge", "kind": "judgment", "status": "SUPPORTED", "text": "eval_hf_adapter.py cannot serve as the judge for a decode sweep or a resolve floor: E2B base, single task, no frequency/presence penalty, gold locally INVALID for rich_3469/4070/4079 and absent for rich_4077, and the local-on-rich baseline already floored at 0/10.", "evidence": ["Gemma/train/eval_hf_adapter.py", "Gemma/kb/replays/gold/rich_4079.json", "Gemma/GEMMA_EXPERIMENT_LOG.md#L2613"]}
 ]}
-->
