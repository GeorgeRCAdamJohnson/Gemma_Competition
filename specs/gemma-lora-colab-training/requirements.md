# Requirements — Gemma-4-31B Edit-Discipline LoRA, trained on Colab

## Context
The Gemma-4 Developer Agent competition uses a fixed `gemma-4-31b-it-qat-w4a16-ct` model. ~20 prompt-only
configs (v1–v20 + v19v3) produced exactly one durable rich resolve (rich_4077). Two walls are now measured as
**weights-level**, not prompt-fixable:
1. **Edit-anchor reproduction**: the model cannot emit an `old_string` that byte-matches the file — 12 of 14
   edit attempts across rich_4076/4070 failed to apply in v19v3 EVEN WHEN explicitly told to copy verbatim.
2. **Instruction-load ceiling**: adding or removing prompt text past v19's load regresses the model (v20 cut →
   broke the win + turn-budget death; v19v3 added → 2 tasks fell back into search-death/repeat-loop).

A LoRA is the remaining lever. This spec covers training it on Colab, with post-training configurability and
resume, feeding the existing submit pipeline. v6/0.12 is the SACRED live-best; the LoRA must beat v19's 1/5 on
a free run before it ever touches the scored slot.

## Glossary
- **Adapter**: PEFT LoRA weights (`adapter_model.safetensors` + `adapter_config.json`).
- **Scale / effective-α**: LoRA contribution `(lora_alpha / r) · BA`; editable post-hoc via `adapter_config.json`.
- **Trajectory**: one training example = a terse `localize → edit → submit` multi-turn conversation.
- **Resume**: continue training from a saved checkpoint without redoing completed epochs.

## Requirements

### R1 — Train a loop/edit-discipline LoRA on Colab
WHEN a Colab A100/H100 (80GB-class) session is available, the system SHALL QLoRA-fine-tune
`gemma-4-31b-it-qat-w4a16-ct` (or the agreed base) on edit-discipline trajectories, producing a PEFT adapter
≤ rank 128 and total submission footprint < 3 GiB (competition limits).

### R2 — Teach byte-faithful edit anchors (primary target)
The training data SHALL consist of trajectories whose edit step emits an `old_string` that is a SHORT, EXACT
span copied from the immediately preceding `read_file` output, so the adapter learns to reproduce source bytes
faithfully. This directly targets the measured 12/14 edit-apply failures.

### R3 — Teach stop-after-submit and no repeated-call tails
Trajectories SHALL end at `submit_patch` with no trailing content, and the training objective SHALL discourage
emitting a tool call identical to the immediately preceding one (the repeat-loop that returns under instruction load).

### R4 — Loss masking and short trajectories
The trainer SHALL compute loss ONLY on assistant action tokens (chat-template rendered, prompt tokens masked
to -100), and trajectories SHALL be kept short (the model degrades past v19's instruction load).

### R5 — Resume & extend (no retrain-from-scratch)
The trainer SHALL checkpoint the adapter + optimizer state + a progress record after every epoch, and a re-run
with the same output dir SHALL resume from the last completed epoch. Raising a stage's target epoch count SHALL
train only the not-yet-done epochs. A killed run SHALL lose at most the in-progress epoch.
(Note: `train/train_lora.py` already implements this; the spec reuses it, does not rebuild it.)

### R6 — Post-training configurability WITHOUT retraining
From a single trained adapter, the system SHALL produce submit-ready variants by config-only / cheap-offline
operations (no GPU retrain):
- R6.1 Adapter STRENGTH dial: emit variants with different effective-α by editing `lora_alpha`.
- R6.2 Rank TRUNCATION: if trained at r=R, emit r=K<R variants by slicing the A/B matrices.
- R6.3 These SHALL compose with the existing generation knobs (temperature, top_p, frequency_penalty,
  thinking_budget, stop_sequences) and the frozen v19 prompt, with no retraining.

### R7 — Adapter loads in the scoring harness
Each emitted variant SHALL pass a load-probe that attaches it to the base under vLLM exactly as the scoring
notebook does (reuse the proven `probe_lora_load` path), BEFORE any GPU eval run.

### R8 — External-judge gate before any scored submission
A LoRA variant SHALL be evaluated on the real 31B via a FREE Kaggle run on the fixed 5-task rich sample, with
the attribution table (resolved, edit_fail, first_edit_at, max_repeat). The pre-registered bar: resolved > v19's
1/5 AND edit_fail drops. Only a variant that clears the bar on the free run MAY use the daily scored slot.
v6/0.12 SHALL NOT be overwritten by anything that has not beaten it on a trustworthy judge.

### R9 — Reproducibility & artifact hygiene
The Colab notebook SHALL pin dependency versions, set a fixed seed, log per-epoch loss, and write adapters to a
mounted Google Drive path so a disconnect does not lose checkpoints. Training data and adapters SHALL be
versioned (committed metadata/hashes to the repo; large weights git-ignored).

### R10 — Drift / honesty guards
The spec SHALL record, per experiment, the pre-registered bar, the held-out judge, and the verdict. A null
result (adapter does not beat v19) SHALL be reported as a null, not reframed. No scored submission on a config
that only looks good on a dev-internal metric.

## Non-goals
- Not training a general code-fixer (fix-CONTENT quality is a later, separate target).
- Not touching fastapi tasks (rich-only until the rich path is solid).
- Not changing v19's prompt (frozen base; prompt channel is exhausted).
- Not full fine-tuning (QLoRA adapter only; base weights frozen).

## Open decisions (to confirm before Task 1)
- D1 Train rank: **r=32** (recommended, room to slice to 16/8) vs r=16.
- D2 Trajectory source: **rich-only gold diffs** (focused) vs rich + a few fastapi.
- D3 Base for training: **a bf16 sibling, NOT the W4A16 model** — you cannot QLoRA-finetune an already-W4A16-
  quantized checkpoint; `smoke_qlora.py` confirms the recipe trains a bf16 Gemma-4 base. The adapter is then
  loaded onto W4A16 at scoring (adapter-load-in-scoring already verified). CONFIRM which bf16 31B sibling id and
  that it fits the chosen GPU in NF4 4-bit.
- D4 Colab tier: 31B QLoRA (NF4) needs ~A100 40GB MIN (80GB comfortable); T4 16GB will NOT fit. CONFIRM what the
  Colab account can actually allocate per session (free=T4 won't work; Pro/Pro+ A100 not guaranteed per session).

## Colab environment facts to COLLECT (currently UNKNOWN — close before Task 3; honesty: do not assume)
- E1 GPU model + VRAM actually granted this session (print `nvidia-smi`); assert ≥40GB or stop (D4).
- E2 bf16 31B sibling HF model id + gated-access status; confirm the HF token (handle `bigesta`) can download it
  on Colab and the license is accepted (D3).
- E3 Measured 4-bit weight footprint of the chosen base on the granted GPU (free VRAM after load) — proves it fits.
- E4 Pinned dependency set that works with Gemma-4 on Colab's CUDA: exact versions of
  transformers / peft / bitsandbytes / accelerate / torch (record the working combo; Gemma-4 needs recent transformers).
- E5 Measured per-epoch wall time for the full trajectory set on the granted GPU → does 3 epochs fit one Colab
  session before disconnect? (If not, rely on Drive checkpoint + resume across sessions — R5.)
- E6 Trajectory COUNT produced from rich gold (Task 1 output) — is ~48 rich tasks enough signal, or widen (D2)?
- E7 Drive mount path + free space for checkpoints (adapter + optimizer.pt per epoch); confirm space for the run.
- E8 HF token + (if used) Kaggle token delivery into Colab WITHOUT committing secrets (Colab secrets / env var,
  never written to the repo).

NOTE: E1–E8 are gaps the spec cannot fill from the repo alone — they require a live Colab session to measure or a
user confirmation. Task 0 and Task 3.1 must record these before the full run (Task 5) proceeds.

### MEASURED (2026-10-10, via GitHub->Colab browser run of colab_env_probe.ipynb):
- E1 RESOLVED: GPU = **NVIDIA A100-SXM4-40GB** (40GB total, ~42GB free reported). VERDICT: **OK for 31B QLoRA
  (>=40GB)**. => D4 RESOLVED: the Colab tier holds the 31B QLoRA. Execution mechanism = GitHub->Colab web UI
  (open https://colab.research.google.com/github/GeorgeRCAdamJohnson/Gemma_Competition/blob/main/<path>.ipynb,
  set A100 runtime, Run All). This SIDESTEPS the colab-CLI OAuth wall entirely (CLI auth kept failing on
  invalid_grant; browser login is native). The CLI/MCP paths are abandoned as unnecessary.
- D1 (rank r=32), D2 (rich-only gold, 23 trajectories built in Task 1) remain the chosen defaults.
- D3: train a bf16 sibling (NOT W4A16); confirm which id via E2 output (HF access). On a 40GB A100, a 31B bf16
  base in NF4 4-bit fits; a 27b/12b sibling is the fallback if the 31b bf16 base is gated/unreachable.
- STILL to confirm from the probe's lower cells: E2 (which bf16 base the HF token reaches), E3 (NF4 load OK),
  E4 (pinned versions). Paste those if alarming; otherwise the 40GB PASS unblocks Task 3 (Colab training notebook).

### Environment MECHANISMS confirmed (2026-10-10) — resolve the "how", not yet the "measured values"
- Code/data into Colab: **Colab is connected to the GitHub repo** `GeorgeRCAdamJohnson/Gemma_Competition` →
  pull train_lora.py + trajectory data directly (no manual upload). (Resolves the delivery half of E8 + Task 3.1 step 1.)
- Run mechanism: **Google Colab VS Code extension** (`google.colab`) connects a workspace .ipynb to a Colab GPU
  kernel; author notebooks locally, run on Colab. (Optional MCP: `googlecolab/colab-mcp`.)
- STILL to MEASURE on connect (unchanged): E1 (GPU/VRAM), E2 (bf16 base id + access), E3 (NF4 footprint),
  E4 (pinned versions), E5 (per-epoch time), E6 (trajectory count), E7 (Drive space).
- FIRST ACTION on a connected GPU session: Run All in `Gemma/train/colab_env_probe.ipynb` → paste output → fill
  E1–E4 → lock D3/D4. Only then build training data (Task 1) / run full job (Task 5).
