# Design — Gemma Edit-Discipline LoRA on Colab

## Overview
Train one QLoRA adapter on Colab from terse localize→edit→submit trajectories, checkpointing to Drive for
resume. From that single run, emit a FAMILY of submit-ready variants (strength × rank × generation knobs) with
no retraining. Gate every variant on a free Kaggle 5-task run before the scored slot. Reuse the existing
`train/train_lora.py` (resume + loss-mask + chat-template already built) and `probe_lora_load`; add two small
tools (data builder adaptation + variant emitter) and one Colab notebook wrapper.

```
gold rich diffs ──▶ build trajectories (R2/R3/R4) ──▶ data/edit_discipline_*.jsonl
                                                            │
                        Colab A100 (Drive-mounted) ◀────────┘
                        train_lora.py --r 32 (resumable, R5)
                                   │
                         adapters/<run>/  (adapter_model.safetensors + config)
                                   │
                     make_variant.py (R6: scale/rank, offline, no GPU)
                      ├─ r32-s1.0  ├─ r32-s0.5  ├─ r16-s1.0 ...
                                   │
                   probe_lora_load (R7, local, free)  ──▶ pass/fail
                                   │
                   FREE Kaggle 5-task run (R8) ──▶ attribution (resolved, edit_fail)
                                   │
                   bar: >1/5 AND edit_fail↓  ──▶ (only then) scored slot
```

## Components

### C1 — Trajectory builder  `train/build_edit_discipline_data.py` (adapt existing build_localization_trajectories.py)
Input: gold `patch` + repo snapshot for each rich task (from `comp_files/tasks.jsonl` + cloned repo at base_commit).
Output: JSONL of `{"messages": [...]}` chat trajectories. Each trajectory:
1. system = v19's frozen prompt (so the adapter learns to ACT UNDER the exact prompt we ship).
2. user = the harness task prompt (repo + problem_statement), built like `build_agent_prompt`.
3. assistant turns, TERSE:
   - a `read_file(file, start, end)` call covering the gold edit region;
   - tool response = the real file slice (so the next step can copy from it);
   - an `edit_file(file, old_string, new_string)` call where **old_string is a short exact span copied verbatim
     from that slice** and new_string applies the gold change (R2);
   - `submit_patch()` then END — no trailing text (R3).
Rules: keep ≤ ~6 assistant actions (R4 short); no repeated calls; mask loss to assistant tokens only (handled by
train_lora.py's encode_example for the `messages` format). Emit a `_verify` report: for each trajectory, assert
`old_string in file_slice` and that applying new_string yields the gold post-image (reject any trajectory that
doesn't — we only teach anchors that actually match).

### C2 — Trainer  `train/train_lora.py` (REUSE, verified)
Already provides: QLoRA 4-bit base, q/v target modules on the text decoder, chat-template render + loss mask to
assistant turn (R4), per-epoch checkpoint of adapter+optimizer+progress.json (R5), resume on same `--out`,
`--r/--alpha/--lr/--maxlen/--stage` flags. Invoke with `--r 32` (D1) so variants can slice down (R6.2).
No code change required for core training; only confirm `--base` points at the base the Colab GPU holds (D3).

### C3 — Variant emitter  `train/make_variant.py` (NEW, offline, CPU)
`python make_variant.py --adapter adapters/<run> --scale S --rank K --out adapters/<run>-rK-sS`
- Strength (R6.1): load `adapter_config.json`, set `lora_alpha = round(S * r_effective_base)`, write out. Pure
  config edit; weights unchanged. (Effective scale = alpha/r, so S is the multiplier on the trained default.)
- Rank truncation (R6.2): load `adapter_model.safetensors`; for each `lora_A` (shape r×in) keep first K rows and
  each `lora_B` (out×r) keep first K cols; set config `r=K`, `lora_alpha` scaled to preserve chosen S. Save.
- Always re-emit a valid PEFT dir (config + safetensors) that drops into a submit notebook `adapters/`.
- Prints a manifest row (run, r, alpha, effective-scale, bytes) for the log.

### C4 — Load probe  `probe_lora_load` (REUSE)
Attach each emitted variant to the base under vLLM with `enable_lora=True, max_lora_rank=128` exactly as the
scoring notebook (R7). Fail closed: a variant that doesn't load never reaches a GPU eval.

### C5 — Colab notebook  `train/colab_train_lora.ipynb` (NEW)
Thin wrapper, reproducible (R9). EXECUTION MECHANISM (confirmed): author the .ipynb in the workspace, open it
via the Google Colab VS Code extension (`google.colab`), Select Kernel -> Colab -> Auto Connect on a GPU runtime.
Code+data reach Colab via the **GitHub connection** (Colab <-> `GeorgeRCAdamJohnson/Gemma_Competition`), NOT manual upload.
1. Pull the repo through the Colab-GitHub link (gets `train_lora.py` + `train/data/edit_discipline_rich.jsonl`).
2. Mount Drive; set `OUT=/content/drive/MyDrive/gemma_lora/<run>` (checkpoints survive disconnect -> resume).
3. Pin versions (the E4 combo), `set_seed(0)`, assert GPU VRAM >= threshold (E1/D4) else stop.
4. Run `train_lora.py --out $OUT --r 32 --stage s1=train/data/edit_discipline_rich.jsonl:3` (start 3 epochs).
5. Tail per-epoch loss; if still dropping, re-run same cell with `:5` (resume adds epochs 4-5 — R5).
6. Save `$OUT` adapter to Drive AND commit it back to the repo (git-ignored weights path or a release), so the
   submit pipeline can pull it. Print sha256 + size for the manifest.

### C7 — Execution + I/O channels (confirmed, 2026-10-10)
- IN (code/data -> Colab): Colab's GitHub integration pulls from `GeorgeRCAdamJohnson/Gemma_Competition`.
- RUN: Google Colab VS Code extension (`google.colab` v0.9.7) connects a workspace .ipynb to the Colab GPU kernel.
  (Optional: `googlecolab/colab-mcp` MCP server for programmatic drive; NICE-TO-HAVE, not required — the
  extension alone suffices. MCP config must be added by the USER — Kiro guards .kiro/settings/.)
- PERSIST: Google Drive mount for per-epoch checkpoints (resume across disconnects, R5/R9).
- OUT (adapter -> submit): commit adapter back to the repo (or Drive download) -> `submit_v19_lora/adapters/`.
- First action on connect: run `train/colab_env_probe.ipynb` (Run All) to fill E1-E4 before any heavy step.

### C6 — Submit integration (REUSE submit_vN pipeline)
A submit notebook variant (e.g. `submit_v19_lora/`) = v19's agent dir (frozen prompt + 4 levers) with
`adapters/main_lora/<emitted variant>` added and `agent.yaml` declaring `adapter: main_lora`. The 3 robust
resolvers + defensive import + syntax-gate assembler all carry over unchanged.

## Data model
- Trajectory JSONL record: `{"messages":[{"role":"system","content":...},{"role":"user",...},
  {"role":"assistant","content":...,"tool_calls":[...]},{"role":"tool",...}, ... ]}`.
- Checkpoint dir `<out>/ckpt/`: `adapter_model.safetensors`, `adapter_config.json`, `optimizer.pt`,
  `progress.json` (`{"done": {"s1": <epochs_completed>}}`).
- Variant manifest `adapters/manifest.jsonl`: `{run, r, alpha, effective_scale, bytes, sha256, probe_pass}`.

## Decisions & rationale
- **Train r=32, ship sliced** — one run yields r32/r16/r8 (R6.2); r=32 well under the 128 cap and <3GiB.
- **System prompt = v19 verbatim inside trajectories** — teach the adapter to act under the EXACT shipped prompt,
  not a training-only prompt (avoids the train/serve mismatch that broke the earlier "trained wrong" adapter).
- **Verify every trajectory's anchor applies** — we only teach old_strings that byte-match + reach the gold
  post-image; a bad trajectory would teach the very failure we're fixing.
- **Strength as the primary post-train knob** — effective-α is a single-number dial from one adapter; cheapest
  possible configurability (R6.1), tunable per scored submission.

## Risks & mitigations
- **Colab disconnect** → Drive-mounted `OUT` + per-epoch checkpoint = resume, ≤1 epoch lost (R5/R9).
- **31B won't fit** → confirm 80GB GPU (D4); if only 40GB, fall back to the agreed bf16 sibling for training and
  rely on the already-verified adapter-transfer-to-W4A16 (D3), re-probe (R7).
- **Adapter over-steers / regresses** (like the "trained wrong" one) → strength dial down toward 0 (R6.1); w=0
  equals base, so a bad adapter can always be neutralized without retrain; gate on free run (R8) before scored.
- **Train/serve tokenizer or chat-template mismatch** → render trajectories with the SAME chat template the
  scoring server uses; probe (R7) attaches under the real vLLM path to catch format drift early.
- **Overfitting to 5 sample tasks** → build trajectories from the broader rich gold set, hold the 5-task sample
  as judge only; report edit_fail on tasks NOT in training.

## Testing strategy
- Builder: `_verify` asserts every trajectory's old_string ∈ slice AND applying it == gold post-image.
- Trainer: smoke run 1 epoch on 2 examples (reuse `smoke_qlora.py`) → adapter saves + reloads.
- Variant: emit r32-s1.0 and r16-s1.0 → both pass probe (R7); manifest records bytes/sha.
- End-to-end: one FREE Kaggle 5-task run of the top variant vs v19-no-adapter; read attribution (R8).
