# R3 — LLM/PEFT State of the Art for Behavior / Format / Agentic SFT

> Scope: Research questions 3 and 5 for the FIXED-model Gemma effort.
> Target setting (from `_priors_brief.md`, section F): train a thin QLoRA adapter for
> `gemma-4-31b-it-qat-w4a16-ct` (W4A16 INT4, vLLM, 4×L4, 32k ctx), ≤8 adapters, rank ≤128,
> <3GiB total, 1 scored sub/day, live-best v6w @ 0.15 is SACRED.
> Goal is a **BEHAVIOR** change (commit-to-edit-fast / stop-searching; A1, A3), NOT knowledge,
> on **multi-turn tool-call trajectories**, where format fidelity of `edit_file`'s dual-string
> payload already failed once (C3 serialization key-collapse) and 4-epoch over-training degraded
> the model (C4).
>
> Convention: every nontrivial claim carries a URL + date and inline attribution, paraphrased
> (<=30 consecutive words). Each item is labeled **[ESTABLISHED]** (well-replicated / official
> docs), **[INFERRED]** (my reasoning tying theory to our setting), or **[MEASURED-LOCAL]**
> (ground truth from the priors brief, repeated for the tie-in — not re-derived).

---

## 0. TL;DR — the 3 highest-confidence recommendations (full basis in §9 table)

1. **LOSS MASKING: train only on completion / assistant tokens (mask the prompt and all tool
   outputs).** For multi-turn tool-call fidelity this is the single highest-leverage knob — the
   model must learn to *emit* the tool call, not to *reproduce* the environment's tool results.
   TRL's `DataCollatorForCompletionOnlyLM` / `completion_only_loss` and the chat-template
   `{% generation %}` keyword exist for exactly this. **[ESTABLISHED]** TRL SFT docs,
   https://huggingface.co/docs/trl/en/sft_trainer (accessed 2025-02; "train on completions only"
   section). Tie-in: our C3 key-collapse is a *format* failure on the `edit_file` payload; if the
   trainer computed loss over prompt/tool-result tokens, gradient was spent memorizing non-emitted
   text instead of the call schema. This is the first thing to verify in `train_lora.py`.

2. **alpha = 2 x rank (NOT alpha/r = 0.5), OR switch to rsLoRA.** Our v2 used r=32,
   alpha=16 → **alpha/r = 0.5** (C-context), which *halves* the LoRA update magnitude and is the
   opposite of the common SFT heuristic alpha = 2r. The rank-stabilized scaling result shows the
   `alpha/r` scaling is unstable at higher rank and should scale as `alpha/sqrt(r)`.
   **[ESTABLISHED]** rsLoRA, Kalajdzievski 2023, https://arxiv.org/abs/2312.03732 (2023-12-06);
   HF PEFT `use_rslora=True`, https://huggingface.co/docs/peft/en/developer_guides/lora .
   Tie-in: alpha/r=0.5 under-drives the adapter — exactly consistent with v2 showing *both*
   under-commitment (search-death, C2) and, where it did fire, format collapse (C3). Set
   alpha=2r for r≤32, or enable rsLoRA so rank and strength decouple.

3. **Few hundred (not tens) of high-quality, consistently-formatted completion-masked examples;
   1 epoch; low LR (~1e-4 to 2e-4 for QLoRA) with ~3% warmup + cosine decay.** Our v2 drove loss
   0.907→0.262 over **3 epochs on only 23 examples** (C4) — a textbook over-fit that explains the
   repeat-loop format collapse. LIMA showed strong alignment from ~1k curated examples; QLoRA's
   own guidance and small-SFT practice favor few epochs + low LR. **[ESTABLISHED]** LIMA, Zhou et
   al. 2023, https://arxiv.org/abs/2305.11206 (2023-05-18); QLoRA, Dettmers et al. 2023,
   https://arxiv.org/abs/2305.14314 (2023-05-23). Tie-in: raise example count and cut to 1 epoch
   before any other tuning — C4's over-training fork is cheapest to kill here.

---

## 1. QLoRA — the base recipe (what our setup already is)

**[ESTABLISHED]** QLoRA (Dettmers, Pagnoni, Holtzman, Zettlemoyer), https://arxiv.org/abs/2305.14314
(2023-05-23) introduces: 4-bit NormalFloat (NF4) quantization of the frozen base, double
quantization, and paged optimizers, so LoRA adapters are trained on top of a 4-bit base with
reportedly no measured degradation versus 16-bit full finetuning on their benchmarks. The paper's
Guanaco models were trained this way.

Key QLoRA practice points relevant to us:
- **Target modules matter more than rank.** The QLoRA paper reports that applying LoRA to **all
  linear layers** was important to match full-finetuning quality, and that once you do, **rank had
  little effect** on final quality. https://arxiv.org/abs/2305.14314 (2023-05-23). **[INFERRED]**
  tie-in: this is the empirical basis for v2 widening q/v → all-linear (D). The all-linear choice
  is defensible; our regression (C1) is therefore NOT explained by target-module choice and should
  not be re-litigated there — look at alpha/r (§3), epochs/data (§6), and loss masking (§7).
- NF4 + bf16 compute dtype is the standard combo; the adapter is trained in bf16/fp16 while the
  base stays 4-bit. HF PEFT QLoRA guide, https://huggingface.co/docs/peft/en/developer_guides/quantization
  (accessed 2025-02).

**[MEASURED-LOCAL]** our `smoke_qlora.py` / `train_lora.py` already do NF4 4-bit base + bf16 LoRA
(priors D). GPU/adapter-loading is SOLVED — do not re-litigate.

---

## 2. DoRA — weight-decomposed LoRA (a drop-in upgrade to consider)

**[ESTABLISHED]** DoRA (Liu et al., NVIDIA), https://arxiv.org/abs/2402.09353 (2024-02-14)
decomposes each pretrained weight into **magnitude** and **direction**, applies LoRA only to the
direction, and trains magnitude separately. The paper reports DoRA consistently beats LoRA at the
same parameter budget, with the largest gains at **low rank**, and that its learning pattern more
closely resembles full finetuning. Available in HF PEFT via `use_dora=True`,
https://huggingface.co/docs/peft/en/developer_guides/lora (accessed 2025-02).

**[INFERRED]** tie-in: because our adapter budget forces **low rank** (F: rank ≤128, keep SMALL),
DoRA is squarely in its best-reported regime. Its magnitude/direction split is also plausibly
gentler on format fidelity than a strength-mis-scaled plain LoRA (relevant to C3). Caveat: DoRA
adds a small inference cost and must be supported by the vLLM LoRA path at serve time — verify vLLM
supports DoRA adapters before committing (our serve is vLLM dynamic-LoRA; §8). Treat DoRA as a
**second** experiment after loss-masking + alpha fix, so attribution stays clean (one change per
sub, rule 7 / gemma protocol).

---

## 3. Adapter strength: rsLoRA, the alpha=2r heuristic, and what our alpha/r=0.5 implies

**[ESTABLISHED]** The LoRA update is scaled by `alpha / r` (original LoRA, Hu et al.,
https://arxiv.org/abs/2106.09685 , 2021-06-17; alpha acts like a tunable scaling on the low-rank
update). Common SFT practice sets **alpha = 2 x r** (e.g., r=16 → alpha=32), a convention surfaced
across Unsloth and community SFT guides, Unsloth LoRA hyperparameters guide,
https://docs.unsloth.ai/get-started/fine-tuning-guide/lora-hyperparameters-guide (accessed 2025-02).

**[ESTABLISHED]** rsLoRA (Kalajdzievski), https://arxiv.org/abs/2312.03732 (2023-12-06) shows the
conventional `alpha/r` scaling causes gradient collapse / instability as rank grows, and that
scaling by **`alpha / sqrt(r)`** stabilizes learning so higher ranks actually help. Exposed as
`use_rslora=True` in HF PEFT, https://huggingface.co/docs/peft/en/developer_guides/lora .

**[MEASURED-LOCAL]** v2 used **r=32, lora_alpha=16 → alpha/r = 0.5** (priors C-context). The real
r32 edit-discipline adapter banked separately used alpha=64 (alpha/r=2) (priors D) — so the project
has BOTH extremes on record.

**[INFERRED]** tie-in and recommendation:
- alpha/r = 0.5 **halves** the adapter's effective update. Combined with over-training (C4), you get
  a weirdly-shaped weak update: strong enough to corrupt the `edit_file` serialization template it
  over-memorized (C3) but too weak to install the commit-to-edit *policy* (C2). That is the most
  parsimonious single explanation for "regresses AND format-collapses."
- Fix: either **alpha = 2r** (strength the heuristic expects) or **`use_rslora=True`** (decouple
  rank from strength so you can raise rank without re-tuning alpha). Prefer rsLoRA if you intend to
  sweep rank; prefer plain alpha=2r if you fix rank small.
- There is a measured dose-dependence locally: 12B tool-call argument collapse was ~0 at
  serve-scale ≤0.5, emerged at 0.75, severe at 1.0 (priors C4). **[INFERRED]** that is a serve-time
  *scaling* knob (how hard the adapter is applied at inference), distinct from train-time alpha/r,
  but it says the SAME thing: for format fidelity, keep the *applied* adapter strength modest. The
  clean design is: train at proper alpha=2r/rsLoRA for a well-formed policy, and if format still
  wobbles at serve, down-scale the adapter at serve rather than crippling it at train.

---

## 4. LoRA+ — different learning rates for A vs B

**[ESTABLISHED]** LoRA+ (Hayou, Ghosh, Yu), https://arxiv.org/abs/2402.12354 (2024-02-19) argues the
two LoRA matrices A and B should use **different learning rates** (B larger than A, ratio ~16 in
their experiments) and reports faster convergence and 1–2% accuracy gains at the same cost.
Available in HF PEFT via the `loraplus_lr_ratio` option, HF PEFT docs,
https://huggingface.co/docs/peft/en/package_reference/lora (accessed 2025-02).

**[INFERRED]** tie-in: a convergence/quality lever, not a format-fidelity lever. Low priority for us
until the format/strength/epoch issues (C2–C4) are fixed; it would only muddy attribution if added
early. Reserve as a late optimization once a well-formed commitment adapter exists.

---

## 5. Target-module choice (attn-only vs all-linear vs MLP)

**[ESTABLISHED]** QLoRA's finding that **all-linear** was needed to match full-finetune quality,
https://arxiv.org/abs/2305.14314 (2023-05-23). PEFT exposes `target_modules="all-linear"` as a
shortcut, https://huggingface.co/docs/peft/en/developer_guides/lora (accessed 2025-02). Attn-only
(q/v) is the original LoRA default (Hu et al. 2021) and is cheapest but lower-ceiling.
**[ESTABLISHED/INFERRED]** MLP (gate/up/down) layers carry a large fraction of a transformer's
parameters and are where much task/behavior adaptation lands; including them is part of why
all-linear outperforms attn-only.

**[INFERRED/MEASURED-LOCAL]** tie-in: v2 already uses all-linear on the **text decoder only**, with
vision/audio towers excluded (priors D) — correct for a text tool-call behavior and correct for a
multimodal Gemma base. Keep this. Do NOT revert to q/v-only chasing the C3 collapse; the collapse
is a strength/epoch/masking artifact (§3, §6, §7), not a target-module one. (This directly honors
accountability rule 11: debug the execution, do not retreat to the narrower/standard recipe.)

---

## 6. Epochs, data size, LR, warmup, scheduler for small behavior-shaping SFT

**[ESTABLISHED]**
- **Data size for behavior/alignment:** LIMA, https://arxiv.org/abs/2305.11206 (2023-05-18) — ~1,000
  carefully curated examples produced strong instruction-following, supporting the "Superficial
  Alignment Hypothesis" that alignment mostly re-formats existing capability rather than teaching
  new knowledge. **[INFERRED]** our target IS re-formatting latent capability (commit-to-edit is a
  *policy/format* behavior the 31B already can do — it localizes fine, A1), so LIMA's regime
  applies: aim for **a few hundred** high-quality, format-consistent trajectories, not tens and not
  tens of thousands.
- **Epochs:** small curated SFT typically runs **1–3 epochs**; more invites memorization. QLoRA/TRL
  examples default to short runs. TRL SFT docs, https://huggingface.co/docs/trl/en/sft_trainer
  (accessed 2025-02). **[MEASURED-LOCAL]** our 3-epoch/23-example run over-fit hard (loss →0.262,
  C4) — classic. Recommendation: **1 epoch** at the new (larger) data size, watch eval loss, only
  add epochs if underfit.
- **Learning rate (QLoRA):** community/official QLoRA finetunes commonly use **1e-4 to 2e-4** for
  the adapter (higher than full-finetune LRs because only the small adapter trains). Unsloth guide,
  https://docs.unsloth.ai/get-started/fine-tuning-guide/lora-hyperparameters-guide (accessed
  2025-02). Lower (2e-5–5e-5) is used for larger datasets / more conservative behavior shaping.
- **Warmup + scheduler:** short **warmup (~3% of steps, or 5–20 steps for tiny runs)** then **cosine
  decay** is the standard small-SFT recipe; linear decay is an acceptable alternative. TRL/Unsloth
  defaults, https://huggingface.co/docs/trl/en/sft_trainer (accessed 2025-02).
- **Batch/accumulation:** effective batch 8–32 via grad-accumulation is typical for single-GPU
  QLoRA; larger effective batch stabilizes a tiny-dataset run. **[INFERRED]** for a few-hundred
  example run, effective batch ~16 and 1 epoch gives on the order of low-tens of steps — keep warmup
  a few steps, not a fixed 3% that would round to <1.

---

## 7. LOSS MASKING — mask the prompt, train only on completion/assistant tokens (CRITICAL)

**[ESTABLISHED]** TRL supports **completion-only loss**: `DataCollatorForCompletionOnlyLM` masks
everything before the response template so loss is computed only on assistant tokens, and newer TRL
exposes `completion_only_loss` / `assistant_only_loss` with the chat-template `{% generation %}`
block to mask multi-turn conversations down to assistant turns. TRL SFT docs,
https://huggingface.co/docs/trl/en/sft_trainer (accessed 2025-02; "Train on completions only" /
"Train on assistant messages only"). The HF chat-templating docs describe `return_assistant_tokens_mask`
and the `{% generation %}` keyword used to build that mask, https://huggingface.co/docs/transformers/en/chat_templating
(accessed 2025-02).

**Why this is the top lever for tool-call fidelity [INFERRED, high confidence]:**
- In a multi-turn tool trajectory the sequence is `[user] [assistant tool_call] [tool result]
  [assistant tool_call] ...`. The ONLY tokens the model should emit are the **assistant tool-call**
  tokens. Tool *results* (grep output, pytest output, file contents) are environment-generated and
  must NEVER be a training target — if loss covers them, the model learns to hallucinate
  environment output and spends capacity away from call-schema fidelity.
- **[MEASURED-LOCAL]** our trainer carried a loss-masking bug: the first run was a NULL at
  mean_loss 0.0000 (masked to last turn only + maxlen truncation), then "fixed" to **unmask ALL
  assistant turns** (priors D). Two things to verify precisely, because they are the likeliest
  root cause of C3:
  1. Does "unmask all assistant turns" also (wrongly) unmask **tool-result** turns or the **user**
     prompt? If the mask is "everything that is not the user's first message," tool results leak
     into the loss and corrupt format.
  2. Is the mask aligned to the Gemma-4 chat template's assistant/tool boundaries exactly? A
     one-token misalignment at the `edit_file` payload boundary is a direct mechanical candidate for
     the C3 key-collapse (the `old_string`/`new_string` boundary is exactly where the serialization
     broke).
- Recommendation: use TRL's `assistant_only_loss` with a Gemma-4 chat template that emits
  `{% generation %}` only around assistant turns (NOT tool-result turns), and unit-test the produced
  `assistant_masks` on one `edit_file` example before training. This is the cheapest, highest-value
  fix and should be experiment #1.

---

## 8. Sequence length & packing

**[ESTABLISHED]** Packing concatenates multiple short examples into one max-length sequence to cut
padding waste and speed training; TRL supports `packing=True`. TRL SFT docs,
https://huggingface.co/docs/trl/en/sft_trainer (accessed 2025-02). Packing can let tokens from one
example attend across a document boundary unless the trainer uses the correct attention masking
(FlashAttention cross-document / position-reset); modern TRL/Unsloth handle this.

**[INFERRED]** tie-in and WARNING for our data:
- Our trajectories are **multi-turn tool-call** sequences that can be long. **Do NOT pack**
  tool-call trajectories: packing risks a tool call in example A attending to tool output in example
  B, which is poison for format fidelity. Keep one trajectory per sequence.
- **[MEASURED-LOCAL]** the prior NULL run was partly caused by **maxlen truncation** (priors D).
  Truncating a trajectory can cut off the final assistant `edit_file` turn — i.e., you train the
  model on explore-then-get-cut-off, the exact search-death behavior (C2) you are trying to remove.
  Set `maxlen` large enough to hold the WHOLE trajectory including the terminal edit, and
  **right-truncate from the FRONT (drop early exploration), never drop the final edit** — or filter
  out trajectories that don't fit. Verify the terminal `edit_file` turn survives tokenization for
  every training row.
- Because the serve context is 32k and quantization hurts long-context (A8), keep training
  trajectories as SHORT as the behavior allows — short, decisive commit-to-edit trajectories double
  as the behavioral target AND the easiest to fit under maxlen.

---

## 9. NEFTune — training-time embedding noise

**[ESTABLISHED]** NEFTune (Jain et al.), https://arxiv.org/abs/2310.05914 (2023-10-09) adds uniform
noise to the embedding vectors during finetuning and reports large conversational-quality gains
(e.g., AlpacaEval win-rate jumps) with no inference cost. Exposed in TRL via `neftune_noise_alpha`,
https://huggingface.co/docs/trl/en/sft_trainer (accessed 2025-02).

**[INFERRED]** tie-in: NEFTune mainly boosts free-form conversational quality and reduces overfitting
to the exact training strings — which could *help* our over-fit-on-23-examples failure (C4) by
regularizing. BUT it is a general-chat result; its effect on **strict JSON/tool-call format**
fidelity is NOT established and noise could plausibly hurt a format that must be emitted exactly.
Classify as a **low-priority, test-behind-a-gate** lever: only try after loss-masking + alpha + data
fixes, and only if over-fit persists; a modest `neftune_noise_alpha≈5` is the common starting value
(TRL docs). Do not add it in the same experiment as another change.

---

## 10. Research question 5 — the W4A16 / QLoRA interaction

**The core question:** do you train the adapter on the **bf16 twin** and serve it on the **quantized
(INT4 W4A16) base**? That is exactly our setup.

**[MEASURED-LOCAL]** Train→load→eval is PROVEN on A100 Colab with the **gemma-4-31b-it bf16 base**;
the adapter is then served on the W4A16 base via vLLM, which sets LoRA params dynamically from the
submission (priors D, F). So we already do: **train on bf16 twin, serve on INT4 base.**

**[ESTABLISHED] the precision pitfall of this cross-regime path:**
- A LoRA trained against bf16 base weights is a correction to the **bf16** weights. At serve time it
  is applied to **INT4-quantized** weights, so the base the adapter "expects" differs from the base
  it lands on by the quantization error. QLoRA's own design avoids this by training the adapter
  **against the same NF4-quantized base it will be used with** (the adapter learns to compensate for
  quantization), https://arxiv.org/abs/2305.14314 (2023-05-23). **[INFERRED]** our bf16-train /
  INT4-serve split forgoes that compensation — the cleaner path, if feasible, is to **train the
  QLoRA against the SAME W4A16/NF4 quantization used at serve** so the adapter sees the quantized
  base during training. If exact W4A16 (vLLM's AWQ/compressed-tensors INT4) cannot be reproduced in
  the HF/bitsandbytes training stack, bf16-twin training is the pragmatic fallback, but expect a
  small train/serve mismatch and validate on the FREE gate, never assume parity.
- **QAT nuance:** the ship base is `...-qat-w4a16` — a **quantization-aware-trained** checkpoint, so
  its INT4 weights are tuned to behave well at 4-bit. **[INFERRED]** adapting on a bf16 twin that was
  NOT the QAT-INT4 object risks the adapter correcting toward a slightly different weight manifold.
  Another reason to prefer training against the quantized object if the stack allows it.
- **[ESTABLISHED/MEASURED-LOCAL]** long-context + 4-bit interaction (A8): W4A16 is broadly
  competitive (arXiv 2411.02355) but 4-bit can lose heavily on **long-context** tasks (arXiv
  2505.20276). SWE trajectories are long-context, so the serve-time quantization bites most exactly
  where our trajectories live — a reason to keep trajectories short (§8) and to not spend context
  budget on big adapters (next point).

**[MEASURED-LOCAL / ESTABLISHED] rank, max_lora_rank, and KV-cache at 32k ctx:**
- Constraints: **≤8 adapters, rank ≤128, <3GiB total** (F). vLLM sets LoRA params dynamically from
  the submission, and **FEWER adapters + LOWER rank = MORE KV-cache** (F). vLLM's `max_lora_rank`
  and `max_loras` directly size the reserved LoRA memory; a high `max_lora_rank` reserves more and
  leaves less for KV-cache. vLLM LoRA docs, https://docs.vllm.ai/en/latest/features/lora.html
  (accessed 2025-02).
- **[INFERRED]** recommendation: ship **ONE small adapter at the LOWEST rank that installs the
  commit behavior** (start r=16, alpha=32; only raise if the FREE gate shows underfit, and if you
  raise rank use rsLoRA so strength stays sane). At 32k ctx on 4×L4 the KV-cache is the binding
  resource for long SWE trajectories; a single r=16 adapter costs little `max_lora_rank` and leaves
  context for the agent. A big high-rank LoRA is doubly bad (eats context AND over-powers format,
  C3). This aligns with DoRA's low-rank sweet spot (§2) — low rank is both the constraint and,
  per DoRA, where the method is strongest.

---

## 11. Direct answers to "what does our v2's alpha/r=0.5 imply?"

**[MEASURED-LOCAL + INFERRED]** v2: r=32, alpha=16 ⇒ scaling = alpha/r = **0.5**, i.e. the LoRA
update is applied at **half** its unit strength. Implications:
1. It is the **opposite** of the alpha=2r SFT convention (which would be alpha=64 ⇒ scaling 2.0) and
   of rsLoRA's prescription. The adapter was systematically **under-driven**.
2. An under-driven adapter trained for **4 epochs on 23 examples** (C4) is the worst of both worlds:
   too weak to install the broad commit-to-edit policy (→ search-death C2), yet over-memorized on
   the tiny set so the one thing it DID encode strongly — the exact serialized `edit_file` string
   shape — came out corrupted (→ key-collapse C3). alpha/r=0.5 does not *cause* C3 by itself, but it
   explains why the useful policy did not transfer while the memorized string template still leaked.
3. Prescription: **alpha=2r** (or rsLoRA), **1 epoch**, **few-hundred examples**,
   **completion-only loss**. Change ONE at a time against the FREE gate (gemma protocol), starting
   with loss-masking, because a masking bug at the `edit_file` boundary is the most mechanical
   candidate for C3.

---

## 12. Recommended starting hyperparameters + supported range + citation

| Knob | Recommended start (our 31B behavior-SFT) | Literature range | Primary citation (URL, date) |
|---|---|---|---|
| **Loss masking** | completion/assistant-only (`assistant_only_loss` + `{% generation %}`); mask prompt AND tool-result turns | always mask prompt for instruction/behavior SFT | TRL SFT docs https://huggingface.co/docs/trl/en/sft_trainer (2025-02); chat-template https://huggingface.co/docs/transformers/en/chat_templating (2025-02) |
| **rank r** | 16 (raise only if gate shows underfit) | 8–64 typical; QLoRA: rank ~irrelevant once all-linear; ≤128 (our cap F) | QLoRA https://arxiv.org/abs/2305.14314 (2023-05-23); vLLM LoRA https://docs.vllm.ai/en/latest/features/lora.html (2025-02) |
| **alpha** | 32 (alpha=2r) | alpha=r to alpha=2r; or use rsLoRA to decouple | rsLoRA https://arxiv.org/abs/2312.03732 (2023-12-06); Unsloth guide https://docs.unsloth.ai/get-started/fine-tuning-guide/lora-hyperparameters-guide (2025-02) |
| **scaling mode** | `use_rslora=True` if sweeping rank, else plain alpha=2r | plain alpha/r vs alpha/sqrt(r) | rsLoRA https://arxiv.org/abs/2312.03732 (2023-12-06); PEFT https://huggingface.co/docs/peft/en/developer_guides/lora (2025-02) |
| **target modules** | all-linear, text decoder only (towers excluded) | q/v-only → all-linear | QLoRA https://arxiv.org/abs/2305.14314 (2023-05-23); PEFT `target_modules="all-linear"` (2025-02) |
| **epochs** | 1 | 1–3 for small curated SFT | TRL docs https://huggingface.co/docs/trl/en/sft_trainer (2025-02); LIMA https://arxiv.org/abs/2305.11206 (2023-05-18) |
| **# examples** | few hundred (300–1000), format-consistent, completion-masked | ~1k curated (LIMA) down to low-hundreds for narrow behavior | LIMA https://arxiv.org/abs/2305.11206 (2023-05-18) |
| **learning rate** | 1e-4 (QLoRA adapter) | 2e-5 – 2e-4 | QLoRA https://arxiv.org/abs/2305.14314 (2023-05-23); Unsloth guide (2025-02) |
| **warmup** | ~3% of steps (min a few steps for tiny runs) | 0–10% | TRL/Unsloth defaults (2025-02) |
| **scheduler** | cosine decay | cosine or linear | TRL docs https://huggingface.co/docs/trl/en/sft_trainer (2025-02) |
| **LoRA+ lr ratio** | off initially; ~16 later as optimization | ratio >1 (B faster than A) | LoRA+ https://arxiv.org/abs/2402.12354 (2024-02-19) |
| **DoRA** | consider as experiment #2 (low-rank sweet spot) | on/off | DoRA https://arxiv.org/abs/2402.09353 (2024-02-14) |
| **NEFTune** | off initially; `≈5` only if overfit persists | noise_alpha 5–15 | NEFTune https://arxiv.org/abs/2310.05914 (2023-10-09) |
| **packing** | OFF (multi-turn tool trajectories) | on for short indep. examples | TRL docs https://huggingface.co/docs/trl/en/sft_trainer (2025-02) |
| **max seq len** | hold the WHOLE trajectory incl. terminal edit; filter/front-truncate, never drop the final edit | model/VRAM bound | QLoRA https://arxiv.org/abs/2305.14314 (2023-05-23); A8 long-ctx note |
| **train-vs-serve quant** | ideally train against W4A16/NF4 (match serve); bf16-twin is pragmatic fallback, validate on FREE gate | — | QLoRA https://arxiv.org/abs/2305.14314 (2023-05-23) |
| **serve: max_lora_rank / max_loras** | smallest that fits the shipped adapter (favor KV-cache) | per vLLM; ≤8 adapters, <3GiB (our cap F) | vLLM LoRA https://docs.vllm.ai/en/latest/features/lora.html (2025-02) |

---

## 13. Sources (primary)

1. QLoRA — Dettmers, Pagnoni, Holtzman, Zettlemoyer. https://arxiv.org/abs/2305.14314 — 2023-05-23.
2. LoRA (original) — Hu et al. https://arxiv.org/abs/2106.09685 — 2021-06-17.
3. DoRA — Liu et al. (NVIDIA). https://arxiv.org/abs/2402.09353 — 2024-02-14.
4. rsLoRA (rank-stabilized) — Kalajdzievski. https://arxiv.org/abs/2312.03732 — 2023-12-06.
5. LoRA+ — Hayou, Ghosh, Yu. https://arxiv.org/abs/2402.12354 — 2024-02-19.
6. NEFTune — Jain et al. https://arxiv.org/abs/2310.05914 — 2023-10-09.
7. LIMA ("Less Is More for Alignment") — Zhou et al. https://arxiv.org/abs/2305.11206 — 2023-05-18.
8. HF TRL — SFT Trainer docs (completion-only / assistant-only loss, packing, NEFTune, scheduler).
   https://huggingface.co/docs/trl/en/sft_trainer — accessed 2025-02.
9. HF PEFT — LoRA developer guide (use_rslora, use_dora, target_modules="all-linear").
   https://huggingface.co/docs/peft/en/developer_guides/lora — accessed 2025-02.
10. HF PEFT — quantization/QLoRA guide. https://huggingface.co/docs/peft/en/developer_guides/quantization — accessed 2025-02.
11. HF PEFT — LoRA package reference (loraplus_lr_ratio). https://huggingface.co/docs/peft/en/package_reference/lora — accessed 2025-02.
12. HF Transformers — chat templating (return_assistant_tokens_mask, {% generation %}).
    https://huggingface.co/docs/transformers/en/chat_templating — accessed 2025-02.
13. Unsloth — LoRA hyperparameters guide (alpha=2r convention, LR ranges).
    https://docs.unsloth.ai/get-started/fine-tuning-guide/lora-hyperparameters-guide — accessed 2025-02.
14. vLLM — LoRA adapters (max_lora_rank, max_loras, KV-cache tradeoff).
    https://docs.vllm.ai/en/latest/features/lora.html — accessed 2025-02.
15. (local prior, A8) 4-bit broadly competitive — arXiv 2411.02355; 4-bit long-context loss — arXiv 2505.20276.

---

## 14. Honest uncertainty ledger (accountability rules 9, 12)

- **[ESTABLISHED]** paper existence, headline claims, and the official-doc feature names
  (`use_rslora`, `use_dora`, `assistant_only_loss`, `completion_only_loss`, `loraplus_lr_ratio`,
  `neftune_noise_alpha`, `target_modules="all-linear"`, vLLM `max_lora_rank`) are stable, well-known
  primary facts. Doc URLs are living pages (accessed 2025-02); exact option names can drift across
  library versions — verify against the installed TRL/PEFT/vLLM version before coding.
- **[INFERRED]** every "tie-in" that maps a paper to our C1–C4 failure signatures is MY reasoning,
  not a measured local result. The strongest inference (loss-masking boundary bug as the C3 cause,
  §7) is a HYPOTHESIS to be confirmed by inspecting the actual `assistant_masks` on an `edit_file`
  example — it is not yet a verified finding. Per the accountability contract, none of these become
  "real" until confirmed on the FREE gate / an external judge.
- **[NOT RE-DERIVED]** A1–A8 and C1–C4 are repeated from `_priors_brief.md` as the fixed ground
  truth; this dossier reinterprets them with cited theory and does not contradict them.
- Train-vs-serve quantization (§10): whether the HF/bitsandbytes training stack can exactly
  reproduce vLLM's W4A16 object is UNVERIFIED here; the recommendation to "match the serve
  quantization if feasible" is conditional on that feasibility, which must be checked in-stack.
