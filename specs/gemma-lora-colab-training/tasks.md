# Tasks — Gemma Edit-Discipline LoRA on Colab

Each task is incremental, reuses existing code where noted, and ends in a verifiable artifact. Check off as done.
Pre-registered gate before any scored submission: free Kaggle 5-task run, resolved > v19's 1/5 AND edit_fail↓.
v6/0.12 SACRED — never overwritten by an unverified config.

## 0. Confirm open decisions (blocks Task 1)
- [ ] 0.1 Lock D1 train rank (rec r=32), D2 trajectory source (rec rich-only gold), D3 training base, D4 Colab
      GPU tier (must be 80GB-class for 31B QLoRA; T4/16GB will not fit).
  _Req: D1–D4. No code; a decision recorded in requirements.md._

## 1. Build & verify trajectory data (R2, R3, R4)
- [ ] 1.1 Adapt `train/build_localization_trajectories.py` → `train/build_edit_discipline_data.py`: for each
      rich gold task, clone repo at base_commit, locate the gold edit region, emit a trajectory
      system(v19 prompt) → user(task prompt) → read_file(region) → tool(real slice) →
      edit_file(old=verbatim-span-from-slice, new=gold change) → submit_patch → END.
  _Req: R2, R3; Design C1._
- [ ] 1.2 Add `_verify`: assert every trajectory's `old_string` is a substring of the returned slice AND that
      applying `new_string` reproduces the gold post-image; REJECT and log any trajectory that fails.
  _Req: R2 (byte-faithful), R10 (honesty); Design C1 testing._
- [ ] 1.3 Keep trajectories terse (≤ ~6 assistant actions, no repeated calls); write
      `train/data/edit_discipline_rich.jsonl` + a build report (counts, rejects).
  _Req: R3, R4._

## 2. Variant emitter (R6) — build before training so the pipeline is ready
- [ ] 2.1 Write `train/make_variant.py`: `--adapter --scale --rank --out`. Strength = rewrite `lora_alpha`;
      rank = slice lora_A rows / lora_B cols to K + set `r=K`; always emit a valid PEFT dir + manifest row.
  _Req: R6.1, R6.2; Design C3._
- [ ] 2.2 Unit-check on ANY existing adapter (e.g. a prior `_smoke_adapter`): emit scale 0.5 and rank 8, confirm
      the output dir loads with PEFT (shapes consistent, config valid).
  _Req: R6; Design C3._

## 3. Colab training notebook (R1, R5, R9)
- [ ] 3.1 Write `train/colab_train_lora.ipynb`: mount Drive, pin versions, set_seed(0), assert 80GB GPU, pull
      repo + data, set `OUT` on Drive.
  _Req: R1, R9; Design C5._
- [ ] 3.2 Wire the training cell to call the REUSED `train/train_lora.py --out $OUT --r 32
      --stage s1=data/edit_discipline_rich.jsonl:3`; tail per-epoch loss.
  _Req: R1, R4; Design C2._
- [ ] 3.3 Verify resume: interrupt after epoch 1, re-run the same cell → it resumes at epoch 2 (reads
      progress.json, restores optimizer). Then bump `:3`→`:5` and confirm only epochs 4–5 run.
  _Req: R5; Design C2/C5._

## 4. Smoke the whole chain cheap (before the full run)
- [ ] 4.1 Reuse `smoke_qlora.py` (or a 1-epoch/2-example run of train_lora.py) to confirm adapter saves and
      reloads end-to-end on the chosen base.
  _Req: R1; Design testing._
- [ ] 4.2 Run `make_variant.py` on the smoke adapter → emit r32-s1.0 + r16-s1.0 → both pass `probe_lora_load`
      under vLLM with max_lora_rank=128.
  _Req: R6, R7; Design C4._

## 5. Full training run (R1, R5)
- [ ] 5.1 On Colab 80GB, train r=32 for 3 epochs on `edit_discipline_rich.jsonl`; checkpoint to Drive each epoch.
  _Req: R1, R5._
- [ ] 5.2 Inspect loss curve; if still dropping, resume to 5 epochs (same `--out`, raise target). Record final
      loss + sha256 + size in the manifest.
  _Req: R5, R9._

## 6. Emit variant family (R6)
- [ ] 6.1 `make_variant.py` → emit {r32,r16} × {scale 0.5, 1.0, 1.5}; each passes `probe_lora_load` (R7),
      recorded in `adapters/manifest.jsonl` with probe_pass.
  _Req: R6, R7; Design C3/C4._

## 7. External-judge gate (R8, R10) — the only thing that earns the scored slot
- [ ] 7.1 Build `submit_v19_lora/` = v19 agent dir + `adapters/main_lora/<best probe-passing variant>` +
      `agent.yaml adapter: main_lora`; assemble via the syntax-gate assembler; push a FREE Kaggle run on the
      fixed 5-task rich sample.
  _Req: R8; Design C6._
- [ ] 7.2 Pull output; read the attribution table. Pre-registered bar: resolved > 1/5 AND edit_fail drops vs v19.
      If multiple variants are close, A/B the top 2 (different scale) — one free run each, one variable.
  _Req: R8, R10._
- [ ] 7.3 Record verdict in GEMMA_EXPERIMENT_LOG.md with the pre-registered bar + held-out result. A null (no
      beat of v19) is logged as a null. ONLY a bar-clearing variant may use the daily scored slot, and only
      after re-confirming the winning variant alone.
  _Req: R8, R10; v6/0.12 sacred._

## 8. Iterate on the configurable surface (no retrain)
- [ ] 8.1 If a variant is close but over/under-steers, sweep the STRENGTH dial (make_variant --scale) and
      generation knobs (freq_penalty, thinking_budget) — all no-GPU — and re-probe/re-run only the free judge.
  _Req: R6.3; Design C3._
- [ ] 8.2 Only if the whole family fails the bar: revisit trajectory data (Task 1) or train more epochs (Task 5
      resume) — NOT a from-scratch retrain. Log the decision + why.
  _Req: R5, R10._

## Dependencies / reuse map
- REUSE (no rebuild): `train/train_lora.py` (R5 resume + R4 loss-mask), `probe_lora_load` (R7),
  `submit_vN` pipeline + syntax-gate assembler (C6), `comp_files/tasks.jsonl` gold diffs (C1).
- NEW: `build_edit_discipline_data.py` (C1), `make_variant.py` (C3), `colab_train_lora.ipynb` (C5).
- BLOCKED until Task 0: D4 (GPU tier) gates whether the 31B base trains directly or via a bf16 sibling (D3).
