VERDICT: NEEDS-DATA

# Audit — content-correctness LoRA (multi-layer), re-derived

- Proposal: `c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\proposals\2026-10-15-content-correctness-lora-recipe.md`
- Mode: AUDIT (step 2 of `gemma-audit`), date 2026-10-15, slug `content-correctness-lora`
- KB: `check-fresh` = **FRESH** (exit 0); `build_meta.json` inputs_fingerprint `57064d63f76df320073eb995b3fc592d64fe0773d2e481648c69cf2b055b4705`; build stamp 2026-10-16T04:14:14Z; engines `fc-3 / nm-3 / cm-2 / rp-4 / cl-3`. [MEASURED]
- Baseline used: **v6w @ 0.15** (`Gemma\kb\curated\submissions.csv` ref 57098497, COMPLETE; `curated\run_labels.json:baseline`). `.kiro\steering\gemma-submission-protocol.md` itself now names v6w @ 0.15 — the `KB_SUMMARY.md` BASELINE banner calling that steering file "STALE" is the out-of-date artifact. [MEASURED]
- **Baseline-adjacent correction (reported, not adopted):** steering, `run_labels.json:pending` and `KB_SUMMARY.md` §7 all say branch_final (ref 57146757) is PENDING with no score. `curated\submissions.csv` now carries it as `SubmissionStatus.COMPLETE, publicScore 0.12`. It scored **below** v6w, so the baseline is unchanged and no verdict here depends on it; the three PENDING statements are stale. [MEASURED]

Every claim is tagged MEASURED or INFERRED and cites a path. No gold patch text or problem-statement text is reproduced.

---

## 1. Suggestion restated

Train **one** QLoRA adapter on the frozen `gemma-4-31b-it-qat-w4a16-ct` to improve the **content correctness** of the edit the agent writes once it is already at the right file/symbol. Everything else stays at the v6w baseline (prompt, 9-tool surface, 0.18 budget, single flat agent).

- **Target span:** all 60 layers / a broad span, `q,k,v,o` (+ maybe MLP), **not** layer 0 (host design rule); low rank (start r=16) with correctly-shaped scaling (alpha=2r or rsLoRA), explicitly dropping the prior recipe's inverted "raise alpha" fix.
- **Data:** self-distilled **passing** trajectories from public GitHub issues (keep only pytest-pass), filtered for correct minimal edits. No gold patches, no problem-statement fingerprints, no task-id conditioning. A few hundred rows, each round-tripped through Gemma's own tool-call parser.
- **Hygiene:** structured `arguments` dict + `apply_chat_template(..., tools=...)`; assistant/tool-call-only loss mask asserted nonzero and aligned; 1 epoch, cosine LR ~1e-4, packing off, trajectory held whole, replay/anchor rows mixed in.
- **Bar:** a v6w-equivalent **LOCAL** no-adapter baseline run first through the rp-4 gold-first scorer on a held-out EASY+HARD rich set; WIN = adapter resolves strictly more held-out tasks with no PASS_TO_PASS regression; tie or regression = FAILURE. Only then a FREE 5-task rich gate, only then the scored slot.
- **Self-imposed gate:** the proposal declares itself NEEDS-DATA until (a) an adapter-effect probe confirms a multi-layer adapter visibly changes 31B output on the wheelhouse, and (b) the fixed scorer produces a trustworthy no-adapter baseline on the held-out rich set.

It asks the audit to settle five things (fix-CONTENT framing, prior art, behavior-vs-capability, feasibility, scorer parity). Sections 2–9 answer all five.

---

## 2. Prior art

| Element of the proposal | Tag | Evidence |
|---|---|---|
| Multi-layer (non-layer-0) adapter served on the scored 31B stack | **RE-RUN of the serving configuration** (new objective) | `Gemma\adapter_v2_dataset\adapter_config.json` = r32/α64/**410 target modules** spanning many layers incl. `layers.41.mlp.gate_proj`, `layers.13.self_attn.q_proj`, `layers.17.self_attn.o_proj`; shipped byte-identically in `Gemma\v2_gate_out2\submission\adapters\main_lora\` (979,558,760 B). `Outputs\v19_lora` / `submit_v6z_on_v6w\lora025` shipped a **110-module** r32 adapter (175,341,9xx B) across layers 6/16/31/54… Multi-layer is not new; only the *objective* is. [MEASURED] |
| Low rank r=16 + α=2r | **RE-RUN of a measured-negative scaling** | `probe_lora_load\_adapter_dataset\localizer_v1` and `train\adapters\fastapi_specialist*` are already r16/α32 (α/r = 2.0); the 410-module r32/α64 arm (also α/r = 2.0) is the ledger's "0/5 OVERBAKED" (`Gemma\GEMMA_EXPERIMENT_LOG.md` "LoRA DECISION" ledger). The log's own measured prescription is the opposite: **q/v only, r 8–16, α/r ≤ 1, capacity matched to ~45–100 examples, NOT 410 modules**. [MEASURED] |
| Content-correctness (wrong_content) as the training objective | **NEW** (never trained) | The target is named for the first time in the 2026-10-14 "RECOMMENDED RECIPE IF WE TRAIN" entry; no run has trained it. Every prior adapter trained edit-anchor discipline, localization, or fastapi idioms. [MEASURED] |
| Self-distilled **passing** trajectories as the data source | **NEW** (and unbuilt) | No such dataset exists under `Gemma\train\data\`. What exists is gold-derived: `rich_gold_trajectories.jsonl` (45 rows) and `wrongfix_contrastive_rich.jsonl` (56 rows). [MEASURED] |
| dict-`arguments` + `apply_chat_template` + assistant-only loss mask + round-trip parse | **VARIANT (large overlap)** | `Gemma\train\build_stage2_transitions.py` already emits structured `{"messages":[…]}` for template render + assistant-turn masking; the log's CORRECTION #2 retracts "taught content not action" and states the target FORM was already correct. [MEASURED] |
| Single flat agent, no sub-agents | **Constraint honoured** | `curated\claims.jsonl` `J-subagents-regress` (SUPPORTED). [MEASURED] |
| "Offline-first, free gate second, scored slot last" sequencing | **Correct and required** | `.kiro\steering\gemma-submission-protocol.md`. [MEASURED] |

Config diff vs baseline: one added adapter, prompt/tools/budget unchanged — single-variable in the gate sense, which is correct.

**Two prior-art errors carried into this revision.**

1. *"v2 was near-inert partly for this reason [layer 0]"* is **FALSE**. v2 was never layer-0 (410 modules across many layers) and was never inert — it was violently over-strong: `v2_gate_out2` produced `tool_calls=0, patch_chars=0, end_reason=NUDGE_EXHAUSTED` on **5/5** tasks. [MEASURED: `Gemma\kb\runs.jsonl` rows `v2_gate_out2::rich_*`; `Gemma\kb\near_miss.jsonl` `furthest_stage=None, stopped_by=NEVER_ATTEMPTED`]
2. The host's layer-0 explanation applies to the **sample stub**, and one of our own runs served exactly that stub: `Gemma\v2_gate_out\submission\adapters\main_lora\adapter_config.json` is byte-equivalent to the competition sample `Gemma\comp_files\adapter_config.json` (r=4, α=8, `layers_to_transform:[0]`, `target_modules:[q_proj,o_proj]`), and its weights file is 217,672 B — the same size as `Gemma\comp_files\adapter_model.safetensors`. This **closes the prior audit's UNVERIFIED item #4** ("which adapter did `v2_gate_out` actually serve?"): it served the sample layer-0 stub, not the trained v2 adapter. [MEASURED]

---

## 3. Ground truth per task (mechanical only, from `Gemma\kb\tasks_gold.json`; no gold text)

The proposal names no judging set; it names rich_3535 and rich_4079 in its premise and points at "an EASY+HARD mix from `RICH_48_DIFFICULTY_MAP.md`". The tasks that actually carry the measured `wrong_content` mass are these ten:

| task | kb_mech_class | gold files | hunks | added/removed | added test(s) |
|---|---|---|---|---|---|
| rich_3471 | EASY | `rich/text.py` | 1 | 1/0 | `test_append_tokens` |
| rich_3469 | EASY | `rich/markdown.py` | 1 | 1/1 | `test_table_with_empty_cells` |
| rich_4076 | EASY | `rich/ansi.py` | 1 | 3/3 | `test_decode_newlines` |
| rich_4077 | EASY | `rich/file_proxy.py` | 1 | 3/0 | `test_isatty` |
| rich_4079 | EASY | `rich/markdown.py` | 1 | 4/3 | `test_inline_code_in_table_cells` |
| rich_3535 | **HARD** | `rich/cells.py`, `rich/segment.py` | 2 | 7/1 | `test_is_single_cell_widths` |
| rich_3676 | **HARD** | `rich/default_styles.py`, `rich/traceback.py` | 8 | 12/1 | `test_notes` |
| rich_3934 | **HARD** | `rich/live.py`, `rich/live_render.py` | 3 | 17/3 | `test_live_empty` |
| rich_3675 | **HARD** | `rich/console.py`, `rich/diagnose.py` | 5 | 28/13 | 82 test nodes in `tests/test_console.py` |
| rich_4070 | **HARD** | 9 files | 33 | 71/57 | none added |
| rich_3486 | **HARD** | 3 files | 12 | 74/24 | 2 nodes |

[MEASURED] Note rich_3675: its `test_patch` touches 82 test nodes, so under our local whole-file fallback bar it is scored far more strictly than a single-node task. Six of the eleven are HARD, and rich_4070/3486/3675 are release-batch-shaped diffs no single commit-fast edit produces.

---

## 4. Behavior per task per run (what the content-correctness premise actually rests on)

From `Gemma\train\data\wrongfix_contrastive_rich.jsonl` (56 rows, one per measured WRONG-FIX rich row), `Gemma\kb\runs.jsonl`, `Gemma\kb\near_miss.jsonl` and `Gemma\train\data\reviewer_catchability.json`.

**Defect split (re-tallied from the raw file, not from the log's prose):** `wrong_content=34, serialization=10, no_edit=6, wrong_place=6`. [MEASURED]

**The 34 `wrong_content` rows cover only 10 distinct tasks over 16 run_ids:** rich_3675 ×6, rich_4079 ×5, rich_3471 ×5, rich_3535 ×5, rich_3676 ×5, rich_3934 ×4, and rich_4070 / rich_4077 / rich_3486 / rich_4076 ×1 each. Every row has a distinct edit payload (34 distinct payloads), so they are not duplicate rows — but they are **10 independent problems sampled repeatedly**, not 34. [MEASURED]

**`same_file_as_gold` is True on 34/34 — and that is TRUE BY CONSTRUCTION.** `Gemma\train\build_rich_sft_data.py` L375-377 defines `wrong_content` as `model_files & gold_files` non-empty. So the proposal's sentence "33 edit gold's **symbols in gold's files** and are STILL wrong" mixes one tautology (the files part restates the label) with one real measurement (the symbol part). This is the same vacuity the log itself flagged as methodology warning #1 ("100% was VACUOUS … they restate the label"). [MEASURED]

**The real, non-circular measurement** is `train\test_reviewer_catchability.py` S1: of 34 rows, exactly 1 omits a code symbol that the issue names and gold changed (`rich_4070`, `size_ratio 0.18`); S1b (material-size diffs) = 0/34; the control fired 1/1, n=1, uninformative. [MEASURED: `Gemma\train\data\reviewer_catchability.json` summary block] That is a **negative** result — "no omitted issue-named symbol" — which supports "not an ask-comprehension failure". It does not positively establish "edits gold's symbols", and the report should not be cited as if it did.

Per-task behavior on the premise's named task:

- **rich_3535** (8 rows, `B card --task rich_3535`): WRONG-FIX ×5 (`branch` 465 chars/14 calls, `compact5` 479/22, `hard` 479/21, `maxout16k` 465/12, `serB` 465/15), FOUND-NOT-LANDED ×2 (`lora025` REFUSED_CALLS, 0 chars; `m12` SAW_ONLY, 0 chars), LOCATE ×1 (`serA`, 0 tool calls). So on this task the model lands a well-formed, same-file, ~465–479-char patch repeatedly and fails — and both zero-patch rows come from an **adapter** arm and a budget arm. [MEASURED]
- **rich_4079** (5 `wrong_content` rows): including `_v10_kaggle_pull` at `size_ratio 5.53` with coverage 0.29 — a diff 5.5× gold's size that still fails. Size/effort is not the lack. [MEASURED: `reviewer_catchability.json` detail row]

**Adapter arms, for the effect question:**

| run | packaged adapter | span | per-task behavior |
|---|---|---|---|
| `v2_gate_out` | r4/α8, `layers_to_transform:[0]`, 217,672 B = the **sample stub** | layer 0 only | edits attempted on **5/5**, rich_4077 RESOLVED |
| `v2_gate_out2` | r32/α64, 410 modules, 979,558,760 B | many layers + MLP | `tool_calls=0` on **5/5**, NUDGE_EXHAUSTED |
| `v2_gate_s05c` | same weights, α rewritten to 16 (serve-scale 0.5) | many layers + MLP | 3469/4076 never read the gold file; 4079 READ_GOLD_FILE only; 4070 WRONG-FIX with 13/22 malformed calls; 4077 RESOLVED |
| `submit_v6z_on_v6w\lora025` | r32/α16, 110 modules | layers 6/16/31/54… | rich_3535 FOUND-NOT-LANDED/REFUSED_CALLS, 0 patch chars; log records 0/3 with 2 of 3 banking nothing where no-adapter banked 1187/465 chars |

[MEASURED: the four `adapter_config.json` + `adapter_model.safetensors` paths above; `Gemma\kb\runs.jsonl`; `Gemma\kb\near_miss.jsonl`]

---

## 5. Failure classification (§10 definitions)

- `v2_gate_out2` × all 5 — stage-classified **LOCATE / NO_GOLD_FILE** (`furthest_stage=None`); the deciding observation is zero structured tool calls with `end_reason=NUDGE_EXHAUSTED`. **Not INFRA**: the submitted config (the adapter) caused it, so it stays stage-classified per §10. [MEASURED]
- `v2_gate_s05c` × rich_3469, rich_4076 — **LOCATE / NO_GOLD_FILE**. × rich_4079 — **LOCATE / FILE_NOT_HUNK**. × rich_4070 — **WRONG-FIX** with malformation share 0.59 (13 of 22), decided by `ARG_REJECTED ×13`; carries `~`, not INFRA. [MEASURED]
- `submit_v6z_on_v6w\lora025` × rich_3535 — **FOUND-NOT-LANDED / REFUSED_CALLS**, `patch_chars=0`. [MEASURED]
- The 34 `wrong_content` rows — **WRONG-FIX**, subclass `UNREPLAYED` in `runs.jsonl` (no per-row replay verdict exists yet for any of them). The content-correctness thesis is therefore built on a *diff-vs-gold* comparison, not on a replayed pass/fail of each model patch. [MEASURED]
- KB-wide re-tally: rich rows 201, **rich rows with a trace 155**, of which `WRONG-FIX 57 / RESOLVED 48 / LOCATE 30 / FOUND-NOT-LANDED 20`. The proposal's "56/149" is slightly stale (the dataset was built at an earlier fingerprint); direction unchanged — WRONG-FIX is the single largest traced-rich class at 37%. [MEASURED]
- Distinct rich tasks **ever** resolved in the whole record: **7** (rich_3278, 3471, 3676, 3718, 3882, 4077, 4079). The log's "6" is one short. [MEASURED]

---

## 6. Replays / tests run

| command | result |
|---|---|
| `python Gemma\kb\build_kb.py check-fresh` | FRESH (exit 0) |
| `python Gemma\kb\build_kb.py report-path --date 2026-10-15 --slug content-correctness-lora --kind audit` | this path (exit 0) |
| `python Gemma\kb\build_kb.py leakcheck --scope config <proposal>` | **exit 1 — LEAK task_id: rich_4079, rich_3535** (bare dev task ids; no gold text, no problem-statement text) |
| `python Gemma\kb\build_kb.py leakcheck --scope tooling <proposal>` | CLEAN (exit 0) |
| `python Gemma\kb\build_kb.py card --task rich_3535` | 8 rows; the table in §4 |
| raw tally of `Gemma\train\data\wrongfix_contrastive_rich.jsonl` | 56 rows; `wrong_content=34` over **10 distinct tasks**, `same_file_as_gold=34/34`, 34 distinct edit payloads, 16 distinct run_ids |
| raw read of `Gemma\train\build_rich_sft_data.py` L375-377 | `wrong_content` ⇔ `model_files & gold_files` — the same-file property is definitional |
| raw read of `Gemma\train\data\reviewer_catchability.json` | `total 34, S1 1, S1b 0, no_signal 33, ctrl_n 1, ctrl_hits 1` |
| on-disk scan of every `adapter_config.json` under `Gemma\**` + weight-file sizes | table in §4; `v2_gate_out` == competition sample stub (config byte-equivalent, weights 217,672 B) |
| raw read of `Gemma\kb\replays\gold\rich_4079.json` | `engine_version rp-4`, `gold_first VALID-HARNESS-LIKE`, `pin_provenance lockfile`, pins `markdown-it-py==3.0.0 / pygments==2.19.2`, gold exit 0 / 0 failed / required_pass true; base arm exit 1 / 1 failed |
| directory scan of `Gemma\kb\replays\gold\` | **only 4 files**: rich_3469, rich_4070, rich_4076, rich_4079 |
| static read of `Gemma\train\eval_hf_adapter.py` | `BASE = "google/gemma-4-E2B-it"`, 4-bit bitsandbytes HF `from_pretrained`, in-process `generate()`, single `--task`; **no vLLM, no wheelhouse, not the 31B** |
| static read of `Gemma\local_eval\run_local.py` | the local agent rig posts to `http://127.0.0.1:8081/v1/chat/completions` (llama-server `--jinja`), docstring: "local ollama Gemma (gemma4:26b) as a cooperating stand-in for the comp's 31B"; log records the actual served blob as 12B dense |
| static read of `Gemma\train\train_lora.py` | `--maxlen` default still **768** (L22, L122) |
| static read of `Gemma\comp_files\HARNESS_README.md` §2.4/§3.4 | < 3 GiB unpacked incl. adapters; `max_lora_rank 128`, `max_loras 8`; r=16 sizing guide "~110–220 MB" |

No agent commands were re-run, no Kaggle push, no submission. Three scratch scripts under `%TEMP%` were created and deleted. No manual replay candidates were needed — every deciding fact was already on disk.

---

## 7. Variance

- `rich_3535`: 8 runs, **0 resolves**, 5 of 8 land a 465–479-char same-file patch. The three non-WRONG-FIX rows are two adapter/budget arms with 0 patch chars and one 0-tool-call row. [MEASURED]
- `rich_4079`: 6 resolves in 32 attempts across near-identical 28/8/80/240-family configs — within-config variance, not a lever signal. `rich_4077`: 26/32. `rich_3469` 0/18, `rich_4076` 0/32, `rich_4070` 0/13. [MEASURED, prior-audit recount reconfirmed against `B card`]
- **No config in this project has a replicate** (log: "No replicate of ANY config exists… Run-to-run noise is still unquantified"); the harness runs temp 0.2, n=1. [MEASURED]
- Consequence for a "resolves strictly more" bar: on any judging set drawn from these tasks, most of the set is 0-for-everything and the one movable task is a p≈0.19 coin. A single-run strict-improvement bar on such a set is dominated by that coin unless the set is enlarged or replicated. [INFERRED arithmetic on the measured counts]

---

## 8. Rules check

| rule | status |
|---|---|
| Pre-register the bar (acct. 2) | **Partially met.** A direction and a comparator exist, but the bar names no task list, no n, no replication, and no decision rule for the 0-for-everything tasks. Not yet checkable. |
| External judge only (acct. 1) | **FAIL as written.** The named first judge is a *local* no-adapter agent baseline, but the only local agent rig serves a 12B GGUF stand-in (`run_local.py`), not the scored 31B W4A16 vLLM stack — and a 31B adapter cannot be applied to a 12B base at all. The rp-4 scorer judges **patches**; it cannot generate the adapter arm's patches. The first trustworthy judge available is the **FREE Kaggle rich gate**. |
| Adversarial / dev-vs-eval separation (acct. 5) | Honoured in intent (split so the adapter is not judged on tasks it was distilled from) and automatic if the data really is non-129 public issues. |
| No extrapolation (acct. 4) | **Watch item.** "34 measured wrong_content cases" is 10 distinct tasks × repeated runs; treating 34 as the sample size overstates the evidence by ~3×. |
| Honest nulls (acct. 3) | Honoured — the proposal pre-commits to REVISE/REJECT if content-correctness is capability-not-behavior. |
| Tune before concluding (acct. 13) | **Not yet satisfied.** r=16 / α=2r / 1 epoch / LR 1e-4 is a single point, and α/r = 2.0 is precisely the ratio the 410-module arm ran at when it went 0/5. A strength sweep (or rsLoRA) must be planned, not assumed. |
| Floor-guaranteed composition (acct. 15) | **Structurally unavailable, and the proposal does not say so.** At serve there is no tunable blend weight: vLLM applies the adapter as packaged, and the only strength dial is `make_variant.py` rewriting `lora_alpha` into a new artifact. "w=0 allowed" therefore means "ship the no-adapter submission", i.e. the floor is kept by *arm selection*, not by a blend. |
| Novelty leads / gate failure is a debugging task (acct. 10, 11) | Honoured. This audit does **not** recommend abandoning the weights lever; the adapter path has one genuinely new objective and the prior failures are diagnosed as execution faults (over-strength, wrong target, sample-stub mix-up), not as a refutation of the idea. |
| One change per gate (protocol) | Met, provided data recipe + hyperparameters ship as one adapter against an unchanged v6w prompt. |
| Free gate before scored slot (protocol) | Met and explicitly stated. |
| Leakcheck (protocol / forbidden list E) | **config scope FAILS** on `rich_4079`, `rich_3535`; tooling scope CLEAN. No gold or problem-statement content present. These ids must not travel into any prompt/config text. |
| Live-best baseline named correctly | Yes — v6w @ 0.15, and the proposal explicitly keeps it as live-best. The stale PENDING statements about branch_final are reported in the header. |
| Negative space (acct. 19) | **Unused opportunity.** The proposal's whole signal is "presence": the diff the model wrote. The 10-task `wrong_content` set also contains the hole — rows where the model had many edit opportunities on gold's file and never touched the one construct the added test exercises. That expected-minus-observed framing is not in the data plan. |

---

## 9. Cheapest falsifying test (run, offline) — and what it falsified

1. **The proposal's NEEDS-DATA gate (a) is already answered YES by our own runs, and answered better than the planned probe could.** `v2_gate_out` served the layer-0 **sample stub** and behaved baseline-like (edits on 5/5, one resolve); `v2_gate_out2` served the 410-module multi-layer adapter on the same stack and produced **zero tool calls on 5/5**. That is a natural A/B on the real scoring stack showing a multi-layer adapter has a very large effect. The open question is therefore **not** "does a multi-layer adapter take effect" — it is "at what span/rank/strength does it help instead of overbake". [MEASURED]
2. **The probe tool the proposal and the log name cannot test the claim.** `eval_hf_adapter.py` hardcodes `BASE = "google/gemma-4-E2B-it"` and loads a 4-bit HF model in-process — no vLLM, no wheelhouse, not the 31B. A green result there says nothing about the W4A16 serve path. The log's "confirm LOCALLY via `eval_hf_adapter` on the same wheelhouse" is internally inconsistent. [MEASURED]
3. **The offline comparator is unexecutable.** `run_local.py` drives a local llama-server GGUF stand-in (12B dense); the retracted dose-response was exactly this class of base-mismatch artifact. rp-4 scores patches, it does not run agents. So "LOCAL no-adapter baseline vs LOCAL adapter arm" has no stack to run on. [MEASURED]
4. **rp-4 gold-first validity covers 4 rich tasks, not 48.** `Gemma\kb\replays\gold\` holds rich_3469, rich_4070, rich_4076, rich_4079 only. A held-out EASY+HARD set cannot be scored until each of its tasks has a VALID-HARNESS-LIKE gold. [MEASURED]
5. **The data plan is circular for this target.** Self-distilling the agent's **passing** trajectories captures content the model already writes correctly. The failure class is one-character-wrong content on the right line (rich_3535) and 5.5×-oversized-but-wrong diffs (rich_4079) — none of which appears in a passing trajectory. Supervised imitation of successes cannot carry the discriminative signal that separates the wrong content from the right content; that signal lives in gold, or in execution feedback / preference data. The dossier's own R1 section says fine-tuning reliably teaches format/style and "deploy existing ability sooner", while LoRA **substantially underperforms full FT on programming at low rank** (Biderman arXiv:2405.09673) and SFT memorizes where RL generalizes (Chu arXiv:2501.17161). Applied squarely, **fix-content correctness sits on the capability side of that line, and the self-distillation-on-successes data plan is its weakest possible instantiation.** [MEASURED literature + MEASURED resolve counts; the mapping is INFERRED]
6. **Yield arithmetic.** Measured throughput: a 6-task rich gate on L4×4 took ~35 min including startup; distinct rich tasks ever resolved = 7 of 48; shipped LB resolve rate 0.12–0.15. Harvesting "a few hundred clean passing rows" at that rate needs ~1.5–2k agent task-runs ≈ 150–200 L4×4 hours against a 30 GPU-hr/week Kaggle quota. [INFERRED arithmetic on MEASURED inputs]
7. **The proposal discards the only assets built for this exact target, and never says so.** `rich_gold_trajectories.jsonl` (45 rows, every one of 257 tool calls and 122 `edit_file` calls independently re-parsed and re-applied against real repo bytes, 0 failures) and `wrongfix_contrastive_rich.jsonl` (56 rows) are **gold-derived**, so the proposal's own "no gold patches" rule bans them. That rule conflates two different things: staging gold diffs for **inference-time answer lookup** (the integrity issue in `Gemma\VULN_PUBLIC_TASK_PATCH_STAGING.md`, which is about matching a problem statement to a pre-staged diff) versus using public gold patches as **training** data. The proposal needs to pick one position explicitly; as written it bans its only usable correctness signal without argument. [MEASURED that the assets exist and are gold-derived; the distinction is INFERRED and is a rules question, not something this audit rules on]
8. **`--maxlen` is still 768.** `train_lora.py` L22/L122 default 768 against trajectories of median ~3600 tokens. "Trajectory held whole" is stated as an intent, not as the flag. Any run must pass `--maxlen >= 8192` or it silently reproduces the already-fixed mean-loss≈0 truncation null. [MEASURED]
9. **Capacity is fine.** 60 layers × {q,k,v,o} ≈ 240 modules at r=16 scales from the measured 410-module/r32 = 979 MB artifact to roughly 280–300 MB, inside the < 3 GiB / rank ≤ 128 / ≤ 8-adapter limits and consistent with the README's "r=16 → ~110–220 MB" guide. Adding MLP would multiply this materially. [INFERRED arithmetic on MEASURED sizes]

---

## 10. Verdict rationale — NEEDS-DATA

The direction is not refuted and should not be abandoned: WRONG-FIX is the largest traced-rich failure class (57/155 = 37%), it is genuinely a fix-correctness failure rather than an ask-comprehension or localization failure, multi-layer adapters demonstrably take effect on the scored stack, and the adapter path's three prior failures all have concrete execution explanations. The proposal also correctly removes both errors the previous audit caught (the inverted alpha fix, the vacuous edit-attempt bar).

It is NEEDS-DATA because **both of its own gates are unmet, and the mechanism it would use to meet them does not work as described**:

- Gate (a) is mis-specified. The yes/no is already answered by `v2_gate_out` (sample layer-0 stub, baseline-like) vs `v2_gate_out2` (410-module multi-layer, 0 tool calls on 5/5). The probe tool named (`eval_hf_adapter.py`, E2B 4-bit HF) cannot test the wheelhouse claim. What is actually missing is a **strength/span calibration** on the scored stack, not an existence proof.
- Gate (b) is unexecutable. There is no local 31B agent; the local rig is a 12B GGUF stand-in and a 31B adapter cannot be served on it. rp-4 scores patches, not agents. And gold-first validity exists for 4 of 48 rich tasks, so the held-out set the bar names cannot be scored yet.
- The data plan has no correctness signal. Self-distillation on passing trajectories reinforces what already works; the failing class (one-char-wrong content, oversized-but-wrong diffs) is absent from successes by construction. Meanwhile the proposal's "no gold" rule bans the two verified gold-derived assets without resolving the training-vs-inference distinction.

### Exactly what to collect, before any training spend

1. **Strength/span calibration on the scored stack (free, no scored slot).** Build a FREE 5-task rich gate kernel that serves a *known-shape* multi-layer adapter at ≥2 strengths (e.g. the existing 110-module artifact at two `make_variant.py` scales) alongside the no-adapter v6w arm, and read `tool_calls`, `patch_chars`, malformation share and resolve per task. Pre-register: "an adapter at strength s is admissible iff edit-attempt rate and patch_chars are not below the no-adapter arm on ≥4/5 tasks". This is the measurement the overbake history demands and that no probe can substitute.
2. **Extend rp-4 gold-first to the exact judging set.** `python Gemma\kb\build_kb.py build --replay --deadline-s 1500 --lock-wait-s 120` with the judging tasks added to `curated\replay_set.json`, then confirm `gold_first = VALID-HARNESS-LIKE` in `Gemma\kb\replays\gold\<task>.json` for every one. Any task whose gold is INVALID locally is removed from the bar. Report the list.
3. **A paired no-adapter arm on that same set, on the scored stack** (free gate, byte-identical v6w config, ideally ×2 for a first noise estimate). No such arm exists for an EASY+HARD held-out mix; without it "resolves strictly more" has no floor.
4. **A decision on the correctness signal**, stated before any data build: gold-derived training rows (the 45 + 34 already verified on disk) with an explicit rules position on training-vs-inference use of public gold, **or** execution-feedback / preference data (pass-vs-fail pairs on the same task, which the now-working rp-4 scorer can label offline). Self-distilled successes alone are not a content-correctness signal.
5. **Carry forward, unchanged:** `--maxlen >= 8192`; no bare task ids in any config/prompt text (`leakcheck --scope config` currently exits 1); loss-mask assertion + round-trip parse as data hygiene; single flat agent.

When 1–4 land, this becomes a PROCEED candidate with a bar of the form: one adapter, named task list with each task's mech class, pass = strictly more resolves than the paired no-adapter arm with zero regression on tasks the baseline resolved, mechanism check = the malformation share and patch_chars did not fall (i.e. the adapter is not overbaking), fail = tie or any regression.

---

## 11. What the suggestion missed

1. v2 was never layer-0 (410 modules across many layers) and was never inert — it was over-strong, 0 tool calls on 5/5. The host's layer-0 rule explains the **sample stub**, not v2.
2. `v2_gate_out` shipped that sample stub byte-for-byte (config identical to `comp_files\adapter_config.json`; weights 217,672 B), which both closes the prior audit's open question and supplies a free natural A/B proving multi-layer adapters take effect on the scored stack.
3. Therefore its own gate (a) is redundant as an existence question, and the tool it names (`eval_hf_adapter.py`, E2B 4-bit HF, no vLLM) could not answer it anyway.
4. There is no local 31B agent: `run_local.py` serves a 12B GGUF stand-in, and a 31B adapter cannot be applied to it. The "LOCAL baseline vs LOCAL adapter arm" comparison has no stack.
5. rp-4 scores **patches**, not agent runs — it cannot produce either arm's patches.
6. rp-4 gold-first validity exists for 4 rich tasks (3469, 4070, 4076, 4079), not for the EASY+HARD held-out set the bar names.
7. "33/34 edit gold's symbols in gold's files" is half tautology: `same_file_as_gold` is the definition of the `wrong_content` label (`build_rich_sft_data.py` L375-377). The non-circular part is a *negative* (S1 = 1/34), which supports "not an ask failure" but does not establish "edits gold's symbols".
8. The 34 `wrong_content` rows are 10 distinct tasks (rich_3675 ×6, 4079 ×5, 3471 ×5, 3535 ×5, 3676 ×5, 3934 ×4, plus four singletons) across 16 runs — ~3× less independent evidence than "34 cases" implies. All 34 are subclass `UNREPLAYED`.
9. Self-distillation on **passing** trajectories cannot carry the content-correctness signal; the failing content is absent from successes by construction. The dossier's R1 line (behavior teachable, programming capability weakly LoRA-shaped at low rank) lands on the capability side for this target — which is the question the proposal itself said must be answered squarely.
10. Yield: ~150–200 L4×4 hours to harvest a few hundred passing rows at the measured 6-tasks/35-min and 0.12–0.15 resolve rate, against 30 GPU-hr/week.
11. Its "no gold patches" rule bans the only verified assets for this target (45 gold trajectories, 34 contrastive pairs) and conflates inference-time gold staging with gold-derived training data.
12. `train_lora.py --maxlen` is still 768; "held whole" is not a flag.
13. No serve-time blend weight exists, so acct. 15's "w=0 allowed" is satisfied only by arm selection (ship no adapter), not by a tunable weight — worth stating so the floor discipline is explicit.
14. α/r = 2.0 is exactly the ratio the 410-module arm ran at when it scored 0/5; r=16/α=32 is a single untuned point, not a correction.
15. `leakcheck --scope config` exits 1 on rich_4079 / rich_3535.
16. The negative-space angle (expected-minus-observed: gold's file opened many times, the construct the added test exercises never touched) is unused in the data plan.
17. rich_3675's `test_patch` touches 82 test nodes; under our whole-file fallback bar it is scored far more strictly than the real harness would, so a local tie on sets containing it is not neutral evidence.
18. Three KB/steering artifacts still call branch_final PENDING; `submissions.csv` has it COMPLETE at 0.12 (below baseline).

---

## 12. Measured vs inferred

**MEASURED** (raw files, traces, on-disk configs, curated submissions): every adapter config, module count, span and weight-file size, including the byte-size identity of `v2_gate_out`'s adapter with the competition sample; `v2_gate_out2` 0-tool-call/NUDGE_EXHAUSTED on 5/5; `v2_gate_s05c` per-task stages and 13/22 malformation; `lora025` rich_3535 REFUSED_CALLS at 0 patch chars; the 56-row contrastive defect split (34/10/6/6) and its 10-task, 16-run, 34-distinct-payload composition; `same_file_as_gold` as a definitional consequence of the builder's L375-377 branch; `reviewer_catchability.json` S1 = 1/34, S1b = 0/34, ctrl n=1; rich-row tallies (201 rows, 155 traced, WRONG-FIX 57, RESOLVED 48, LOCATE 30, FOUND-NOT-LANDED 20) and 7 distinct rich tasks ever resolved; all gold mechanical metadata in §3; rp-4 `rich_4079` gold VALID-HARNESS-LIKE with lockfile pins; the 4-file contents of `replays\gold\`; `eval_hf_adapter.py` E2B/HF-only surface; `run_local.py`'s llama-server stand-in; `train_lora.py --maxlen` default 768; HARNESS_README size/rank limits; both leakcheck results; LB scores incl. branch_final = 0.12 COMPLETE and the 0.13 temp-1.0/top_k-64 run (ref 57201051).

**INFERRED** (labelled, not verdicts): that content-correctness sits on the capability side of the dossier's behavior/capability line (mapping of Biderman 2405.09673 + Chu 2501.17161 onto this setting); that self-distillation on successes cannot carry the discriminative signal (logical argument from the measured failure shapes, not a trained counterexample); the ~150–200 GPU-hour harvest estimate; the ~280–300 MB size estimate for a 240-module r16 adapter; that a single-run strict-improvement bar on these tasks is dominated by rich_4079's p≈0.19 coin.

**UNVERIFIABLE here:** whether gold-derived training data is permitted by competition rules (a rules question for the organizers, not decidable from the workspace); whether the adapter-effect "probe running separately" has produced anything (no artifact on disk, no log entry); run-to-run noise for any config (no replicates exist anywhere in the project).

<!-- AUDIT-JSON
{"schema": "gemma-audit/1", "mode": "AUDIT", "verdict": "NEEDS-DATA",
 "proposal": "c:\\Users\\Biges\\OneDrive\\Documents\\Desktop\\kAGGLE\\Gemma\\kb\\proposals\\2026-10-15-content-correctness-lora-recipe.md",
 "kb_inputs_fingerprint": "57064d63f76df320073eb995b3fc592d64fe0773d2e481648c69cf2b055b4705",
 "targets": ["rich_3535", "rich_4079", "rich_3675", "rich_3676", "rich_3471", "rich_3934", "rich_3469", "rich_4070", "rich_4076", "rich_4077", "rich_3486"],
 "prior_art": [
  {"lever": "multi-layer (non-layer-0) adapter served on the scored 31B", "tag": "RE-RUN", "runs": ["v2_gate_out2", "v2_gate_s05c", "submit_v6z_on_v6w/lora025/out", "Outputs/v19_lora"]},
  {"lever": "low-rank r16 with alpha/r = 2.0", "tag": "RE-RUN", "runs": ["v2_gate_out2", "train/adapters/fastapi_specialist", "probe_lora_load/_adapter_dataset/localizer_v1"]},
  {"lever": "content-correctness (wrong_content) as the training objective", "tag": "NEW", "runs": []},
  {"lever": "self-distilled passing-trajectory dataset", "tag": "NEW", "runs": []},
  {"lever": "dict-arguments + apply_chat_template + assistant-only loss mask + round-trip parse", "tag": "VARIANT", "runs": ["v2_gate_out2", "v2_gate_s05c", "Outputs/v19_lora"]},
  {"lever": "single flat agent, no sub-agents", "tag": "RE-RUN", "runs": ["_v6out", "submit_v6w/out_v6w"]}
 ],
 "per_task": [
  {"run_id": "v2_gate_out2", "task": "rich_4079", "failure_class": "LOCATE", "subclass": "NO_GOLD_FILE",
   "evidence": ["Gemma/kb/runs.jsonl#row_id=v2_gate_out2::rich_4079", "Gemma/kb/near_miss.jsonl#run_id=v2_gate_out2 furthest_stage=None", "Gemma/v2_gate_out2/submission/adapters/main_lora/adapter_config.json"]},
  {"run_id": "v2_gate_out", "task": "rich_4077", "failure_class": "RESOLVED", "subclass": null,
   "evidence": ["Gemma/kb/runs.jsonl#row_id=v2_gate_out::rich_4077", "Gemma/v2_gate_out/submission/adapters/main_lora/adapter_config.json", "Gemma/comp_files/adapter_config.json"]},
  {"run_id": "v2_gate_s05c", "task": "rich_4070", "failure_class": "WRONG-FIX", "subclass": "ARG_REJECTED~",
   "evidence": ["Gemma/kb/runs.jsonl#row_id=v2_gate_s05c::rich_4070 malform=13/22", "Gemma/v2_gate_s05c/results/traces/trace_rich_4070.json#step_id=14"]},
  {"run_id": "submit_v6z_on_v6w/lora025/out", "task": "rich_3535", "failure_class": "FOUND-NOT-LANDED", "subclass": "REFUSED_CALLS",
   "evidence": ["Gemma/kb/runs.jsonl#row_id=submit_v6z_on_v6w/lora025/out::rich_3535 patch_chars=0", "Gemma/submit_v6z_on_v6w/lora025/out/submission/adapters/main_lora/adapter_config.json"]},
  {"run_id": "submit_v6z_on_v6w/branch/out", "task": "rich_3535", "failure_class": "WRONG-FIX", "subclass": "UNREPLAYED",
   "evidence": ["Gemma/kb/runs.jsonl#row_id=submit_v6z_on_v6w/branch/out::rich_3535 patch_chars=465", "Gemma/train/data/wrongfix_contrastive_rich.jsonl#instance_id=rich_3535"]},
  {"run_id": "_v10_kaggle_pull", "task": "rich_4079", "failure_class": "WRONG-FIX", "subclass": "UNREPLAYED",
   "evidence": ["Gemma/train/data/reviewer_catchability.json#detail[instance_id=rich_4079,run_id=_v10_kaggle_pull] size_ratio=5.53"]},
  {"run_id": "submit_v6w/out_v6w", "task": "rich_4079", "failure_class": "FOUND-NOT-LANDED", "subclass": "SAW_ONLY",
   "evidence": ["Gemma/kb/runs.jsonl#row_id=submit_v6w/out_v6w::rich_4079", "Gemma/kb/near_miss.jsonl#furthest_stage=SAW_GOLD_HUNK stopped_by=NEVER_ATTEMPTED"]}
 ],
 "claims": [
  {"id": "A1", "text": "v2 was NOT layer-0 and NOT inert: 410 modules across many layers incl. MLP; v2_gate_out2 produced 0 tool calls on 5/5.", "basis": "MEASURED", "evidence": ["Gemma/adapter_v2_dataset/adapter_config.json", "Gemma/v2_gate_out2/submission/adapters/main_lora/adapter_model.safetensors", "Gemma/kb/runs.jsonl#row_id=v2_gate_out2::rich_4079"]},
  {"id": "A2", "text": "v2_gate_out shipped the competition SAMPLE layer-0 stub (config byte-equivalent to comp_files; weights 217,672 B), closing the prior audit's UNVERIFIED #4.", "basis": "MEASURED", "evidence": ["Gemma/v2_gate_out/submission/adapters/main_lora/adapter_config.json", "Gemma/comp_files/adapter_config.json", "Gemma/comp_files/adapter_model.safetensors"]},
  {"id": "A3", "text": "The sample-stub arm vs the 410-module arm is a natural A/B proving multi-layer adapters take large effect on the scored 31B stack; gate (a) is therefore mis-specified as an existence question.", "basis": "MEASURED", "evidence": ["Gemma/kb/runs.jsonl#row_id=v2_gate_out::rich_4077", "Gemma/kb/runs.jsonl#row_id=v2_gate_out2::rich_4079"]},
  {"id": "A4", "text": "eval_hf_adapter.py hardcodes BASE=google/gemma-4-E2B-it and loads 4-bit HF in-process; it cannot test the 31B W4A16 vLLM wheelhouse.", "basis": "MEASURED", "evidence": ["Gemma/train/eval_hf_adapter.py#L21", "Gemma/train/eval_hf_adapter.py#L24-L33"]},
  {"id": "A5", "text": "The offline comparator is unexecutable: run_local.py serves a 12B GGUF stand-in via llama-server, and rp-4 scores patches rather than running agents.", "basis": "MEASURED", "evidence": ["Gemma/local_eval/run_local.py#L2-L20", "Gemma/kb/kblib/replay.py"]},
  {"id": "A6", "text": "rp-4 gold-first validity exists for only 4 rich tasks (3469, 4070, 4076, 4079); rich_4079 is VALID-HARNESS-LIKE with lockfile pins.", "basis": "MEASURED", "evidence": ["Gemma/kb/replays/gold/rich_4079.json", "Gemma/kb/replays/gold/"]},
  {"id": "A7", "text": "wrong_content = 34 rows over only 10 distinct tasks and 16 runs; same_file_as_gold is 34/34 by definition of the label.", "basis": "MEASURED", "evidence": ["Gemma/train/data/wrongfix_contrastive_rich.jsonl", "Gemma/train/build_rich_sft_data.py#L375-L377"]},
  {"id": "A8", "text": "The non-circular reviewer measurement is a negative: S1 = 1/34, S1b = 0/34, control n=1.", "basis": "MEASURED", "evidence": ["Gemma/train/data/reviewer_catchability.json#summary"]},
  {"id": "A9", "text": "KB re-tally: 155 traced rich rows, WRONG-FIX 57 (37%); the proposal's 56/149 is stale but directionally right. 7 distinct rich tasks ever resolved, not 6.", "basis": "MEASURED", "evidence": ["Gemma/kb/runs.jsonl", "Gemma/kb/KB_SUMMARY.md#section-3"]},
  {"id": "A10", "text": "Self-distillation on passing trajectories cannot carry the content-correctness signal; the dossier's R1 places low-rank LoRA on programming capability as weak (Biderman 2405.09673, Chu 2501.17161).", "basis": "INFERRED", "evidence": ["Gemma/kb/research/2026-10-14-lora-what-to-train-dossier.md#section-2", "Gemma/train/data/reviewer_catchability.json#summary"]},
  {"id": "A11", "text": "Harvesting a few hundred passing trajectories needs ~150-200 L4x4 hours vs a 30 GPU-hr/week quota (6 tasks/35 min, 0.12-0.15 resolve rate).", "basis": "INFERRED", "evidence": ["Gemma/GEMMA_EXPERIMENT_LOG.md#L4x4-gate-35-minutes", "Gemma/kb/curated/submissions.csv"]},
  {"id": "A12", "text": "The 'no gold patches' rule bans the only verified assets for this target (45 gold trajectories, 34 contrastive pairs) and conflates inference-time gold staging with gold-derived training data.", "basis": "MEASURED", "evidence": ["Gemma/train/data/rich_gold_trajectories.jsonl", "Gemma/train/data/wrongfix_contrastive_rich.jsonl", "Gemma/VULN_PUBLIC_TASK_PATCH_STAGING.md#section-2"]},
  {"id": "A13", "text": "train_lora.py --maxlen default is still 768 against median ~3600-token trajectories.", "basis": "MEASURED", "evidence": ["Gemma/train/train_lora.py#L22", "Gemma/train/train_lora.py#L122"]},
  {"id": "A14", "text": "leakcheck --scope config exits 1 on rich_4079 and rich_3535; tooling scope is clean.", "basis": "MEASURED", "evidence": ["Gemma/kb/proposals/2026-10-15-content-correctness-lora-recipe.md"]},
  {"id": "A15", "text": "branch_final (57146757) is COMPLETE at 0.12 in submissions.csv while steering, run_labels.json and KB_SUMMARY still call it PENDING; baseline stays v6w @ 0.15.", "basis": "MEASURED", "evidence": ["Gemma/kb/curated/submissions.csv", "Gemma/kb/curated/run_labels.json", "Gemma/kb/KB_SUMMARY.md#section-7"]}
 ],
 "tests_run": [
  {"cmd": "python Gemma/kb/build_kb.py check-fresh", "result": "FRESH (exit 0)"},
  {"cmd": "python Gemma/kb/build_kb.py report-path --date 2026-10-15 --slug content-correctness-lora --kind audit", "result": "report path printed, exit 0"},
  {"cmd": "python Gemma/kb/build_kb.py leakcheck --scope config <proposal>", "result": "exit 1 - LEAK task_id rich_4079, rich_3535"},
  {"cmd": "python Gemma/kb/build_kb.py leakcheck --scope tooling <proposal>", "result": "CLEAN, exit 0"},
  {"cmd": "python Gemma/kb/build_kb.py card --task rich_3535", "result": "8 rows: WRONG-FIX x5, FOUND-NOT-LANDED x2, LOCATE x1; 0 resolves"},
  {"cmd": "raw tally of Gemma/train/data/wrongfix_contrastive_rich.jsonl", "result": "wrong_content=34 over 10 distinct tasks / 16 runs; same_file_as_gold 34/34"},
  {"cmd": "adapter_config.json + weight-size scan over Gemma/**", "result": "v2_gate_out == competition sample stub (217,672 B, layers_to_transform [0]); v2_gate_out2 == 410-module 979,558,760 B"},
  {"cmd": "read Gemma/kb/replays/gold/ (4 files) + rich_4079.json", "result": "rp-4 VALID-HARNESS-LIKE with lockfile pins; only 4 rich tasks covered"},
  {"cmd": "static read of eval_hf_adapter.py / run_local.py / train_lora.py", "result": "E2B HF base; 12B GGUF llama-server stand-in; --maxlen default 768"}
 ],
 "missed": [
  "v2 was never layer-0 and never inert (410 modules, 0 tool calls on 5/5) - the host's layer-0 rule explains the sample stub, not v2",
  "v2_gate_out shipped the competition sample stub byte-for-byte, which closes the prior audit's open adapter-identity question and supplies a free multi-layer-effect A/B",
  "the named probe tool (eval_hf_adapter.py, E2B 4-bit HF) cannot test the 31B W4A16 vLLM wheelhouse",
  "there is no local 31B agent: run_local.py serves a 12B GGUF stand-in and rp-4 scores patches, not agent runs",
  "rp-4 gold-first validity covers 4 of 48 rich tasks, so the held-out bar is unscorable today",
  "'33/34 edit gold's symbols in gold's files' is half tautology (same_file_as_gold defines the wrong_content label) and the real signal is a negative, S1=1/34",
  "the 34 wrong_content rows are 10 distinct tasks across 16 runs, all subclass UNREPLAYED",
  "self-distillation on passing trajectories contains no content-correctness signal by construction; the dossier's R1 line puts this target on the capability side",
  "yield: ~150-200 L4x4 hours to harvest a few hundred passing rows against 30 GPU-hr/week",
  "the 'no gold' rule bans the only verified assets for this target and conflates inference-time staging with gold-derived training data",
  "train_lora.py --maxlen is still 768",
  "no serve-time blend weight exists, so acct. 15's w=0 floor is kept by arm selection, not a tunable weight",
  "alpha/r = 2.0 is exactly the ratio the 0/5 OVERBAKED arm ran at; r16/alpha32 is one untuned point",
  "leakcheck --scope config exits 1 on two bare task ids",
  "the negative-space (expected-minus-observed) framing is unused in the data plan",
  "rich_3675's test_patch touches 82 nodes, so the local whole-file fallback bar is far stricter than the real harness there",
  "branch_final is COMPLETE at 0.12 in submissions.csv while three artifacts still call it PENDING"
 ],
 "proposed_curations": [
  {"id": "J-v2-gate-out-served-sample-stub", "kind": "judgment", "status": "SUPPORTED", "text": "The run v2_gate_out did NOT serve the trained v2 adapter: its packaged adapters/main_lora/adapter_config.json is byte-equivalent to the competition SAMPLE stub (r=4, lora_alpha=8, layers_to_transform:[0], target_modules:[q_proj,o_proj]) and its adapter_model.safetensors is 217,672 bytes, the same size as comp_files/adapter_model.safetensors. v2_gate_out2/s05/s05b/s05c served the real 410-module artifact (979,558,760 bytes). CONSEQUENCE: (1) every C-series claim sourced from v2_gate_out describes the SAMPLE layer-0 stub, not v2 (closes the UNVERIFIED item in 2026-10-15-commitment-lora-recipe.md section 11 #2); (2) the pair gives a free natural A/B on the SCORED stack - layer-0 stub = edits on 5/5 with rich_4077 resolved (baseline-like), 410-module multi-layer = tool_calls 0 on 5/5 - i.e. multi-layer adapters DO take large effect on the 31B W4A16 vLLM path, so an adapter-effect existence probe is redundant; the open question is strength/span calibration, not existence.", "evidence": ["Gemma/v2_gate_out/submission/adapters/main_lora/adapter_config.json", "Gemma/comp_files/adapter_config.json", "Gemma/comp_files/adapter_model.safetensors (217,672 B)", "Gemma/v2_gate_out2/submission/adapters/main_lora/adapter_model.safetensors (979,558,760 B)", "Gemma/kb/runs.jsonl#row_id=v2_gate_out::rich_4077", "Gemma/kb/runs.jsonl#row_id=v2_gate_out2::rich_4079"], "author": "gemma-auditor 2026-10-15 (content-correctness-lora audit)"},
  {"id": "J-wrongcontent-samefile-is-definitional", "kind": "judgment", "status": "SUPPORTED", "text": "The claim '33/34 wrong_content cases edit gold's symbols in gold's FILES' is half tautological: build_rich_sft_data.py L375-377 DEFINES defect_class=wrong_content as model_files & gold_files being non-empty, so same_file_as_gold=34/34 restates the label and measures nothing (the same vacuity the log recorded as reviewer-test methodology warning #1). The non-circular measurement is a NEGATIVE: reviewer_catchability.json S1 = 1/34 (only rich_4070 omits an issue-named, gold-changed code symbol) and S1b = 0/34. That supports 'WRONG-FIX is not an ask-comprehension failure' but does NOT establish 'the model edits gold's symbols'. Additional sample-size caveat: the 34 rows are only 10 DISTINCT tasks (rich_3675 x6, 4079 x5, 3471 x5, 3535 x5, 3676 x5, 3934 x4, plus 4 singletons) across 16 runs, and all are failure_subclass UNREPLAYED - no per-row replay verdict exists. Cite the content-correctness thesis as ~10 independent problems, not 34.", "evidence": ["Gemma/train/build_rich_sft_data.py#L375-L377", "Gemma/train/data/wrongfix_contrastive_rich.jsonl", "Gemma/train/data/reviewer_catchability.json#summary", "Gemma/kb/runs.jsonl"], "author": "gemma-auditor 2026-10-15 (content-correctness-lora audit)"},
  {"id": "J-no-local-31b-agent-arm", "kind": "judgment", "status": "SUPPORTED", "text": "There is NO offline stack that can run an adapter arm of our agent. local_eval/run_local.py posts to a local llama-server (127.0.0.1:8081) serving a 12B-dense GGUF stand-in for the competition 31B, and a 31B-shaped LoRA cannot be applied to a 12B base (the dim-mismatch finding; the earlier Ollama-blob dose-response was retracted as exactly this base-mismatch class). The rp-4 KB replay engine scores PATCHES (gold-first + candidate) and does not run the agent at all. eval_hf_adapter.py hardcodes BASE=google/gemma-4-E2B-it on a 4-bit HF in-process path with no vLLM, so it cannot speak to the W4A16 wheelhouse either. CONSEQUENCE: any bar of the form 'local no-adapter baseline vs local adapter arm' is unexecutable; the first trustworthy judge for an adapter is the FREE Kaggle rich gate, with rp-4 used afterwards to score the resulting patches offline.", "evidence": ["Gemma/local_eval/run_local.py#L2-L20", "Gemma/train/eval_hf_adapter.py#L21", "Gemma/kb/kblib/replay.py", "Gemma/GEMMA_EXPERIMENT_LOG.md#12B-adapter-cannot-serve-on-31B"], "author": "gemma-auditor 2026-10-15 (content-correctness-lora audit)"},
  {"id": "F-branch-final-scored-012", "kind": "fact", "status": "SUPPORTED", "text": "branch_final (submission ref 57146757, PER-TASK BRANCHING, 2026-10-13) is no longer PENDING: curated/submissions.csv records SubmissionStatus.COMPLETE with publicScore 0.12, below the v6w @ 0.15 live-best. The live-best is UNCHANGED. Three artifacts still describe it as PENDING and are stale on this point: .kiro/steering/gemma-submission-protocol.md, curated/run_labels.json:pending, and KB_SUMMARY.md section 7. Verdicts previously parked as NEEDS-DATA solely because branch_final was unscored can now be decided.", "evidence": ["Gemma/kb/curated/submissions.csv#ref=57146757", "Gemma/kb/curated/run_labels.json#pending", "Gemma/kb/KB_SUMMARY.md#section-7"], "author": "gemma-auditor 2026-10-15 (content-correctness-lora audit)"}
 ]}
-->
