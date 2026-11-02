# What To Train Into A LoRA — Research Dossier

> Synthesis date: 2026-10-14. READ-ONLY synthesis of five research notes + the measured local
> priors brief. Target: a FIXED `gemma-4-31b-it-qat-w4a16-ct` (W4A16 INT4, vLLM, 4×L4, 32k ctx)
> that LOCATES the right file then fails to COMMIT an edit ("search-death"). The user's literal
> question: **what do we actually train that enables the model to improve?**
>
> **Labeling discipline (applied throughout).**
> - **[MEASURED-LOCAL]** = a measured prior from `_priors_brief.md` (ground truth; not re-litigated).
> - **[MEASURED/ESTABLISHED]** = a result shown in the cited external literature / official docs.
> - **[INFERRED]** = extrapolation from literature to OUR fixed W4A16 agentic-SWE setting — a
>   hypothesis for a gate, never a verdict (per the accountability contract).
> Every nontrivial external claim keeps its URL + date. External theory may reinterpret a local
> prior but does NOT override a MEASURED-LOCAL fact. Content compliance: all sources paraphrased,
> no quote exceeds 30 consecutive words, inline attribution + source lists per section. *Content was
> rephrased for compliance with licensing restrictions.*
>
> **Input provenance / gap flag.** All five inputs were present and substantive: `_priors_brief.md`,
> `_r1_can_teach.md`, `_r2_image_video.md`, `_r3_peft_sota.md`, `_r4_agentic_distill.md`. No input
> was missing or thin. One mechanical note: `_r2` exceeded the single-read limit and was read in two
> passes (its full translation table T1–T19 and §9 hypotheses were captured). No content gap.

---

## 1. EXECUTIVE ANSWER — WHAT TO TRAIN (one page)

**The honest answer the research supports: do NOT train an edit-anchor LoRA, do NOT train a
knowledge/capability LoRA, and do NOT train a LoRA *first*. Train the DECODER first (free, hours,
no GPU), because the behavior you want — "stop searching, commit to the edit" — is predominantly a
DECODING-shaped and trajectory-SHAPE problem, not a knowledge problem.** If, and only if, a
pre-registered decode sweep fails to move commitment on a by-task holdout, THEN the justified next
lever is a **commitment behavior-clone LoRA** — a "motion LoRA" for the agent's turn sequence —
trained on self-distilled passing *commit-fast* trajectories.

This is not a pro-LoRA conclusion forced onto the data, and it is not a retreat to the herd (the
leaderboard top is adapter-free, [MEASURED-LOCAL] A6). It is sequencing the cheapest falsifying test
first (accountability rules 2, 6).

**If/when you DO train the LoRA, here is exactly WHAT to train and HOW — the five load-bearing specs:**

1. **Train the BEHAVIOR, not the content.** Bake ONE invariant into the weights: the *commit-fast
   motion* — "once the fault is localized, emit `edit_file` instead of another grep/read/pytest." The
   bug, repo, file, and failing test stay VARIABLE in the prompt (never baked). This is the
   image-world "tag the variable, bake the constant" rule ([MEASURED/ESTABLISHED] rentry 2023-08),
   and it is exactly [MEASURED-LOCAL] A3 ("train COMMITMENT, not edit-anchors").

2. **The data is self-distilled passing trajectories, two-key filtered.** Run the agent on PUBLIC
   GitHub issues; keep a trajectory ONLY if (a) it ends in pytest-pass AND (b) it reached its first
   successful `edit_file` within a small call budget with few redundant read/grep cycles (an
   overthinking-score proxy). This is the host-blessed recipe ([MEASURED-LOCAL] E) and the published
   rejection-sampling / STaR / ReST^EM / SWE-Gym family ([MEASURED/ESTABLISHED]). No gold patches, no
   problem-statement fingerprints, no task-id conditioning (the [MEASURED-LOCAL] E forbidden list).

3. **Fix the three mechanical bugs that sank v2 before touching anything else:**
   - **Serialization template (the C3 cause):** never hand-serialize tool calls. Build structured
     messages (`arguments` as a dict) and let the model's own `apply_chat_template(..., tools=...)`
     render them, so each argument is its own `key:<|"|>value<|"|>` pair with a template-owned
     separator. Round-trip-validate every row through Gemma's own parser before it enters the set.
   - **Loss masking:** compute loss on assistant tool-call tokens ONLY — mask the prompt AND tool
     results (grep/pytest/file output). Verify the mask is nonzero and aligned to the `edit_file`
     payload boundary (the exact place v2 broke).
   - **Over-training:** 1 epoch, not 4; a few hundred clean examples, not 23.

4. **Correctly shaped hyperparameters:** low rank (start **r=16**), **alpha=2r (=32)** or
   `use_rslora=True` — NOT v2's under-driven alpha/r=0.5 — all-linear on the text decoder only, LR
   ~1e-4, ~3% warmup, cosine decay, packing OFF, trajectory held whole (never truncate the terminal
   edit). Mix in replay/anchor trajectories of normal correct tool use so the base coding ability is
   not "burned" and search-death does not flip into premature wrong-fix (A7).

5. **Keep the adapter small and validate the quant mismatch:** ship ONE low-rank adapter (KV-cache is
   the binding resource at 32k on 4×L4). Ideally train against the SAME W4A16/NF4 quantization used at
   serve; the proven bf16-twin → INT4-serve path is the pragmatic fallback but must be validated on
   the FREE gate, never assumed to transfer.

**The single most important sentence:** the literature says commitment timing is *in LoRA's teachable
class* (it is behavior, not capability), so "a LoRA can't do this" is false — but the cheapest,
highest-evidence channel for "when to stop/commit" is the decoder, and our own data already lit that
up (`freq_penalty 0.4` killed the repeat-loop; a reserve-tail made every task reach an edit,
[MEASURED-LOCAL] §B). Falsify the decoder before spending a GPU cycle; keep the correctly-shaped
commitment LoRA as the sequenced, justified fallback.

---

## 2. RESEARCH QUESTION 1 — What a LoRA CAN and CANNOT teach (behavior vs capability; LoRA vs prompt/decoding)

**Verdict: commitment is BEHAVIOR (teachable by LoRA in principle), but it is predominantly
DECODING-shaped, so it is only WEAKLY LoRA-shaped — decoding should be falsified first.** This is a
null-leaning finding, not a forced pro-LoRA conclusion (`_r1`, TL;DR).

### What fine-tuning RELIABLY changes — behavior [MEASURED/ESTABLISHED]
- **Format/style/shape is few-shot learnable.** LIMA fine-tuned a 65B base on ~1,000 curated pairs
  and learned response formats, generalizing to unseen tasks — the "Superficial Alignment Hypothesis"
  that alignment teaches format/style, not knowledge. Zhou et al., arXiv:2305.11206 (2023-05-18).
- **"Use existing ability sooner," not "new ability."** Fine-tuning mostly teaches a model to deploy
  pre-existing knowledge more efficiently; new facts are learned slowly. Gekhman et al.,
  arXiv:2405.05904 (2024-05-09). [INFERRED] commitment-timing is a "deploy existing editing ability
  sooner" change → inside LoRA's reliable class.
- **Tool-call syntax is learnable but fragile under over-scaling.** Finetune-on-tool-demos is the
  classic paradigm (ToolkenGPT, Hao et al., arXiv:2305.11554, 2023-05-19); the LoRA scale factor
  controls learning strength and can "stunt" or over-drive adapters (rsLoRA, Kalajdzievski,
  arXiv:2312.03732, 2023-11-28). [INFERRED] mechanistic match for the C3 serialization collapse.
- **Commit/refuse tendency is a tunable dial that overshoots.** Over-refusal work shows "when to
  withhold vs commit" is a behavioral dial that overshoots into the opposite failure (OR-Bench, Cui
  et al., arXiv:2405.20947, 2024-05-31). [INFERRED] "keep searching instead of committing" is the
  agentic analogue of over-refusal — tunable but prone to tip into zero-edit search-death (C2).

### What fine-tuning STRUGGLES to add — capability [MEASURED/ESTABLISHED]
- **New facts: slow + hallucination-inducing.** Gekhman et al. (2405.05904): fitting new-knowledge
  examples linearly increases hallucination. [INFERRED] warning rail — a commitment set must not
  smuggle task-specific answers (that would be the forbidden-list failure, E).
- **New reasoning/skill: LoRA underperforms full FT and memorizes.** On programming and math LoRA
  substantially underperforms full fine-tuning at low rank, though it forgets the base less; full FT
  needs rank 10–100× higher. Biderman et al., arXiv:2405.09673 (2024-05-15). SFT memorizes and
  struggles OOD while RL generalizes; SFT's useful role is stabilizing format. Chu et al.,
  arXiv:2501.17161 (2025-01-28). [INFERRED] a supervised commitment-LoRA will tend to memorize the
  shape of a few dozen dev trajectories and transfer poorly — train on behavioral SHAPE, not content,
  and treat SFT as a format stabilizer.
- **Why low-rank works for behavior (and bounds it).** Pretrained models have very low intrinsic
  dimension; a few hundred parameters reach ~90% of full-FT on a task. Aghajanyan et al.,
  arXiv:2012.13255 (2020-12-22). [INFERRED] a behavior like commit-timing sits in a low-dimensional
  subspace → very low rank suffices; v2's r=32/167MB is over-parameterized for a behavior dial.

### The pivotal fork — DECODING vs WEIGHTS
- **Repetition / failure-to-terminate is a DECODING phenomenon.** The same model degenerates into
  repetitive text or produces good text depending only on decode strategy. Holtzman et al.,
  arXiv:1904.09751 (2019-04-22). [INFERRED] the "repeat-until-death loop" and "grep/read/pytest until
  the budget dies" are the agentic analogue of neural degeneration — a decoder loop.
- **This is exactly what our own data showed.** [MEASURED-LOCAL] §B: `freq_penalty 0.4` killed the
  repeat-loop (max_repeat ≤2 on every task); a reserve-tail + edit-shape made every task REACH an
  edit. Strong convergent evidence the mechanism lives at decode time.
- **The prompt channel is spent.** [MEASURED-LOCAL] A4: adding prompt text DEGRADES this model
  (v20, v19v3 both regressed). So the real fork is **decoding vs weights**, with prompt eliminated.

**Reconciliation (defensible position).** "LoRA cannot do this" is FALSE (commitment is behavior,
§1). But the cheapest, highest-evidence channel is decoding, and SFT on a few dozen trajectories is
the channel most likely to memorize and fail the holdout. Therefore: falsify decoding first (because
it is the fastest falsifier and our own data lit it up, not because it is the herd), and keep a
correctly-shaped commitment LoRA as the sequenced fallback (`_r1` §3.3).

---

## 3. RESEARCH QUESTION 2 — Image/Video LoRA craft, TRANSLATED to text (+ where the analogy breaks)

The image/video community solved "teach a frozen model one new *behavior* from little data without
wrecking the base" repeatedly, and their craft diagnoses v2 as a **textbook over-baked /
format-collapsed character LoRA**, not evidence the LoRA path is dead (`_r2` §0).

Core craft principles (sources: "The Other LoRA Rentry," https://rentry.org/59xed3, updated through
2023-08 [MEASURED/ESTABLISHED community craft]; Raschka practical tips,
https://magazine.sebastianraschka.com/p/practical-tips-for-finetuning-llms, 2023-11-19; AnimateDiff/
MotionLoRA, arXiv:2307.04725, 2023-07-10 rev 2024-02-08):
- **Small-but-clean >> large-but-noisy** ("bad tags contaminate the model"), matching LIMA.
- **Tag the variable, bake the constant** — the single most transferable idea.
- **`scaling = alpha/r`; alpha ≤ rank; alpha > rank "burns"** — the identical formula both communities
  use; Raschka found alpha/r=0.5 can be optimal at r=256, so the ratio alone did not sink v2.
- **Multi-epoch burns the Unet / deteriorates instruction tuning** — pick a pre-burn checkpoint.
- **Regularization images** = anti-burn "screensaver" → text analogue is replay/anchor data.
- **MotionLoRA**: a separable low-rank module that adapts *motion patterns* (behavior over time) — the
  precise genre for "commitment = a motion over the agent's turn sequence."

### 3a. THE IMAGE → TEXT TRANSLATION TABLE (deliverable, from `_r2` §8, T1–T19)

| # | Image/Video-LoRA principle (source) | Text/Agentic analog for the commitment LoRA | Label |
|---|---|---|---|
| T1 | "30–100 decent images"; bad tags contaminate (rentry 2023-08) | 20–50 clean passing commit-fast trajectories; one malformed call poisons the set | ESTABLISHED→INFERRED |
| T2 | LIMA: formats from ~1k curated examples (2305.11206) | Small curated set teaches the *format/behavior* of committing | MEASURED |
| T3 | Learn by **difference**: on/off images | Contrast commit-fast vs over-search; but SFT lacks a true negative channel (Break #4) | ESTABLISHED (partial) |
| T4 | **Tag = variable, un-tag = baked** (rentry) | Bug/repo/file stay in prompt (variable); **commit-fast motion is baked** | ESTABLISHED→INFERRED |
| T5 | Trigger/activation token, first & every file | Consistent **commit preamble** ("fault located; applying fix:") as a behavior handle | INFERRED |
| T6 | "Superman logo" bleed = concept bleed | Baking a gold diff / problem-statement fingerprint = **forbidden scorer-gaming** (E) | ESTABLISHED→MEASURED-constraint |
| T7 | `scaling=alpha/r`; alpha>rank "burns" | Same formula; `alpha/r=0.5` is **dampened, not amplified** — not v2's culprit (Raschka: 0.5 can be optimal) | ESTABLISHED/MEASURED |
| T8 | "err toward lower rank"; bigger r only for diverse sets | Low rank for a **narrow behavior**; also KV-cache + forget-less (2405.09673) | ESTABLISHED/MEASURED |
| T9 | Multi-epoch "burns"; pick a pre-burn epoch | Multi-epoch **deteriorates instruction tuning** (Raschka); v2's 4 epochs = over-bake (C4) | ESTABLISHED/MEASURED |
| T10 | **Regularization images** = anti-burn | **Replay/anchor trajectories** of normal tool use → prevents forgetting coding ability (2308.08747; Raschka arithmetic-unlearning) | ESTABLISHED/MEASURED |
| T11 | **Deep-fry / burn** overfit | **Degenerate decoding / repeat-loop** → v2 C3's 11× malformed `edit_file` | MEASURED (C3) |
| T12 | **Limited / samey poses** | **Behavioral collapse to one action** → v2 C2 search-death (0 edits) | MEASURED (C2) |
| T13 | "Lower strength to not ruin it = overfit" | 12B **dose-dependent** degen (≈0 at scale ≤0.5, severe at 1.0) (C4) | MEASURED (C4) |
| T14 | **Subject/likeness** vs **style/concept** LoRA | **Knowledge LoRA** (memorize fixes — weak + forbidden) vs **Behavior LoRA** (the target) | ESTABLISHED→INFERRED |
| T15 | **MotionLoRA**: motion patterns as a separable module (2307.04725) | **Commitment = a motion over the turn sequence**; the precise genre for our adapter | MEASURED→INFERRED |
| T16 | Denoising MSE, parallel pixel supervision | **Autoregressive CE**, compounding sequential errors, discrete-valid tool calls — the clean break | ESTABLISHED (break) |
| T17 | One image = one i.i.d. example | **Multi-turn trajectory** with mid-example env responses + cross-turn credit assignment | INFERRED (break) |
| T18 | Per-generation **strength dial** + Unet/TE split | No free inference strength dial; sweep at **train/scale** via offline eval (D) | MEASURED asymmetry (break) |
| T19 | **Negative prompt** channel | No LoRA-SFT negative; needs DPO or decode penalties (`freq_penalty`) | INFERRED (break) |

### 3b. WHERE THE IMAGE ANALOGY BREAKS (do not over-transfer — `_r2` §7)

- **Break #1 — the training objective (THE clean break) [ESTABLISHED].** A diffusion LoRA optimizes a
  denoising MSE where every pixel is supervised in parallel and errors are local/graded. Our adapter
  optimizes autoregressive cross-entropy over a sequence: errors compound left-to-right and the output
  must be discretely valid (a tool call either parses or it does not). There is no "slightly malformed
  JSON that still mostly works." This is why v2's C3 is possible and has **no image analog** — in
  images you cannot accidentally turn a required field into a key. Consequence: clean, parseable
  tool-call serialization in every training example is non-negotiable in a way "clean images" never
  were.
- **Break #2 — unit of supervision: single frame vs multi-turn trajectory [INFERRED].** An image
  example is one image→one caption, i.i.d. Ours is a multi-turn trajectory where the right action
  depends on what tools returned mid-example, and credit assignment across turns has no image analog.
  SFT flattens this to next-token prediction and loses the causal structure — part of why commitment
  is arguably partly decode/RL-shaped (consistent with §B's decode wins).
- **Break #3 — strength knob at inference [MEASURED asymmetry].** Image users set LoRA strength per
  generation and split Unet/TE to debug over-bake live. We do not get a free per-request strength dial
  the same way; vLLM sets LoRA params from the submission, so the "strength sweep" diagnostic becomes a
  train-many-epochs-save-each + offline-eval-each loop (`eval_hf_adapter.py` is the XY-plot stand-in).
- **Break #4 — no negative-prompt channel [INFERRED].** SFT has no symmetric negative channel; you
  cannot say "edit_file:1.3, grep:-1.0." The nearest equivalents are preference methods (DPO) or
  decode penalties (`freq_penalty`), not plain LoRA SFT. The on/off "difference learning" trick only
  partially transfers — supply overwhelmingly positive commit-fast trajectories.
- **Compounding caveat (not a break) [MEASURED, A8].** Serving is W4A16 INT4, and 4-bit loses heavily
  on long-context tasks (arXiv:2505.20276, 2025-05-26) even though W4A16 is broadly competitive
  (arXiv:2411.02355, 2024-11-04). SWE trajectories are long-context, so any context-eating adapter is
  doubly penalized — keep the behavior adapter small.

---

## 4. RESEARCH QUESTION 3 — PEFT SOTA + starting hyperparameters

Sources throughout: QLoRA (Dettmers et al., arXiv:2305.14314, 2023-05-23); LoRA (Hu et al.,
arXiv:2106.09685, 2021-06-17); DoRA (Liu et al., arXiv:2402.09353, 2024-02-14); rsLoRA
(Kalajdzievski, arXiv:2312.03732, 2023-12-06); LoRA+ (Hayou et al., arXiv:2402.12354, 2024-02-19);
NEFTune (Jain et al., arXiv:2310.05914, 2023-10-09); LIMA (arXiv:2305.11206, 2023-05-18); HF TRL SFT
docs (https://huggingface.co/docs/trl/en/sft_trainer, accessed 2025-02); HF PEFT LoRA guide
(https://huggingface.co/docs/peft/en/developer_guides/lora, accessed 2025-02); Unsloth LoRA
hyperparameters (https://docs.unsloth.ai/get-started/fine-tuning-guide/lora-hyperparameters-guide,
accessed 2025-02); vLLM LoRA (https://docs.vllm.ai/en/latest/features/lora.html, accessed 2025-02).

The three highest-confidence levers (`_r3` §0), in order:

1. **LOSS MASKING — the single highest-leverage knob [ESTABLISHED].** Train only on assistant/completion
   tokens; mask the prompt AND all tool-result turns. TRL exposes `completion_only_loss` /
   `assistant_only_loss` driven by the chat-template `{% generation %}` block. [INFERRED] if loss
   covered tool-result tokens, gradient was spent memorizing environment output instead of the call
   schema — the likeliest mechanical candidate for the C3 key-collapse (the mask boundary sits exactly
   at the `old_string`/`new_string` payload). Verify the actual `assistant_masks` on one `edit_file`
   example before any full run. This is experiment #1.
2. **alpha = 2r (NOT alpha/r=0.5), or switch to rsLoRA [ESTABLISHED].** v2's r=32/alpha=16 halves the
   update — the opposite of the alpha=2r convention. rsLoRA scales by `alpha/√r` to keep higher rank
   stable (`use_rslora=True`). [INFERRED] an under-driven adapter over-trained on 23 examples is the
   worst of both worlds — too weak to install the commit *policy* (C2) yet over-memorized on the one
   string shape it did encode, which came out corrupted (C3).
3. **Few hundred clean examples, 1 epoch, low LR [ESTABLISHED].** v2 drove loss 0.907→0.262 over 3
   epochs on 23 examples (C4) — textbook over-fit. LIMA shows strong alignment from ~1k curated
   examples; QLoRA favors a small high-quality set, few epochs, low LR.

Other SOTA levers:
- **QLoRA target modules [ESTABLISHED].** All-linear matters more than rank; once all-linear, rank has
  little effect on final quality. v2's all-linear (text decoder only) is CORRECT — do not revert to
  q/v chasing C3; the collapse is a strength/epoch/masking artifact, not a target-module one (`_r3`
  §5, honoring accountability rule 11: debug execution, do not retreat).
- **DoRA [ESTABLISHED].** Decomposes weights into magnitude + direction; beats LoRA at equal budget,
  largest gains at LOW rank — squarely our regime. [INFERRED] experiment #2 after masking + alpha, and
  only if vLLM's serve path supports DoRA adapters (verify first).
- **LoRA+ [ESTABLISHED].** Different LRs for A vs B (B larger, ~16× in their experiments); a
  convergence/quality lever, not a format lever — reserve as a late optimization.
- **NEFTune [ESTABLISHED].** Embedding noise helps conversational quality and reduces over-fit, but its
  effect on strict tool-call format is NOT established and noise could hurt an exactly-emitted format.
  Low-priority, test-behind-a-gate, only if over-fit persists.
- **Packing OFF [INFERRED].** Multi-turn tool trajectories must not be packed — a call in example A
  attending to output in example B is poison for format fidelity. One trajectory per sequence; hold
  the whole trajectory incl. the terminal edit; filter/front-truncate, never drop the final edit (the
  prior NULL run was partly maxlen truncation, which trains explore-then-get-cut-off = search-death).

### Starting-hyperparameters table (`_r3` §12)

| Knob | Recommended start (31B behavior-SFT) | Literature range | Primary citation (URL, date) |
|---|---|---|---|
| **Loss masking** | completion/assistant-only; mask prompt AND tool-result turns | always mask prompt for behavior SFT | TRL SFT docs (2025-02); HF chat-templating (2025-02) |
| **rank r** | 16 (raise only if gate shows underfit) | 8–64 typical; ≤128 (cap F) | QLoRA 2305.14314 (2023-05-23); vLLM LoRA (2025-02) |
| **alpha** | 32 (alpha=2r) | alpha=r to 2r; or rsLoRA | rsLoRA 2312.03732 (2023-12-06); Unsloth guide (2025-02) |
| **scaling mode** | `use_rslora=True` if sweeping rank, else plain alpha=2r | alpha/r vs alpha/√r | rsLoRA 2312.03732 (2023-12-06); PEFT guide (2025-02) |
| **target modules** | all-linear, text decoder only (towers excluded) | q/v-only → all-linear | QLoRA 2305.14314 (2023-05-23); PEFT (2025-02) |
| **epochs** | 1 | 1–3 for small curated SFT | TRL docs (2025-02); LIMA 2305.11206 (2023-05-18) |
| **# examples** | few hundred (300–1000), format-consistent | ~1k curated (LIMA) down to low-hundreds | LIMA 2305.11206 (2023-05-18) |
| **learning rate** | 1e-4 (QLoRA adapter) | 2e-5 – 2e-4 | QLoRA 2305.14314 (2023-05-23); Unsloth (2025-02) |
| **warmup** | ~3% of steps (min a few steps for tiny runs) | 0–10% | TRL/Unsloth defaults (2025-02) |
| **scheduler** | cosine decay | cosine or linear | TRL docs (2025-02) |
| **LoRA+ lr ratio** | off initially; ~16 later | ratio >1 (B faster) | LoRA+ 2402.12354 (2024-02-19) |
| **DoRA** | experiment #2 (low-rank sweet spot) | on/off | DoRA 2402.09353 (2024-02-14) |
| **NEFTune** | off initially; ≈5 only if over-fit persists | 5–15 | NEFTune 2310.05914 (2023-10-09) |
| **packing** | OFF (multi-turn tool trajectories) | on for short indep. examples | TRL docs (2025-02) |
| **max seq len** | hold WHOLE trajectory incl. terminal edit; filter/front-truncate | model/VRAM bound | QLoRA 2305.14314 (2023-05-23); A8 |
| **train-vs-serve quant** | ideally train against W4A16/NF4; bf16-twin fallback, validate on FREE gate | — | QLoRA 2305.14314 (2023-05-23) |
| **serve: max_lora_rank/max_loras** | smallest that fits (favor KV-cache) | ≤8 adapters, <3GiB (cap F) | vLLM LoRA (2025-02) |

---

## 5. RESEARCH QUESTION 4 — Trajectory distillation, the v2 serialization-key-collapse mechanism, and the safe template

### 5a. The host-blessed recipe IS a named, published method [MEASURED/ESTABLISHED]
"Generate with the model, keep only verifier-passing outputs, fine-tune on those, repeat" is the
rejection-sampling / self-training-with-a-verifier family: STaR (Zelikman et al., arXiv:2203.14465,
2022-03-28), ReST^EM / "Beyond Human Data" (Singh et al., arXiv:2312.06585, 2023-12-11, which reports
gains on MATH and the APPS *coding* benchmark — machine-verifiable correctness, exactly our
pytest-pass signal), Llama-2 rejection-sampling fine-tuning (Touvron et al., arXiv:2307.09288,
2023-07-18), and Toolformer's filter-then-train applied to TOOL CALLS (Schick et al.,
arXiv:2302.04761, 2023-02-09). Proven on OUR task shape: **SWE-Gym** reports up to 19% absolute
resolve-rate gains training open-weight SWE agents on self-sampled, test-filtered trajectories (Pan et
al., arXiv:2412.21139, 2024-12-30, ICML 2025); **FireAct** shows trajectory style transfers and
*diversity* carries the gain more than volume (Chen et al., arXiv:2310.05915, 2023-10-09). [INFERRED]
the host-blessed recipe is the SOTA signal for this task class and the only recipe simultaneously
permitted by E and immune to the no-provenance scorer-gaming trap.

### 5b. "Commit early / stop exploring" IS an SFT-trainable trait [MEASURED/ESTABLISHED + INFERRED]
"The Danger of Overthinking" (Cuadron et al., arXiv:2502.08235, 2025-02-12) analyzed 4,018 SWE-Bench
Verified trajectories, named Analysis Paralysis / Rogue Actions / Premature Disengagement, found higher
overthinking correlates with LOWER resolve, and that *selecting* the lower-overthinking trajectory
improved performance by nearly 30% while cutting cost 43%. [INFERRED] our grep-death (A1) IS Analysis
Paralysis in a 15-call budget — the trait is real, measurable, separable from capability, and the
endorsed fix is trajectory selection + light RL, not a bigger model. Combined with SWE-Gym (resolve
behavior is SFT-transferable) and FireAct (style transfers), commit-fast is installable by the
*distribution of trajectory shapes you keep* — hence the **two-key filter**: keep a trajectory only if
it (1) ends in pytest-pass AND (2) reaches its first `edit_file` within ≤k calls with few redundant
cycles. Still 100% behavior-distilled, inside E.

### 5c. The v2 serialization-key-collapse mechanism (one-paragraph account) [INFERRED, consistent with MEASURED C3]
Gemma 4's native tool-call wire format is **not plain JSON**: a call is control-token delimited
(`<|tool_call|>call:name{key:value,...}<tool_call|>`), string values are wrapped in a reserved quote
token `<|"|>` (not ASCII `"`), and the parser pulls keys via a `(\w+):` regex with values taken either
from the `<|"|>` span or up to the next comma/brace (Google, "Function calling with Gemma 4,"
https://ai.google.dev/gemma/docs/capabilities/function-calling, last updated 2025-03-21, retrieved
2026-10-14). The v2 training examples hand-serialized `edit_file`'s two strings as a single blob
instead of letting the chat template emit each argument as a separate `key:<|"|>value<|"|>` pair.
Because `edit_file` is the only *dual-string* argument, the two long newline/backtick-bearing values
sat adjacent with a mis-placed value-delimiter; the model memorized that byte pattern and at inference
emitted `new_string`'s value followed by the literal characters `` `,old_string: ``, so `old_string:`
landed in KEY position and captured a lone backtick while the real `old_string` never got a key — the
harness then reported "mandatory input parameters are not present: old_string," 11+ times in a
repeat-loop. It spares `run_command` because a single-string call has no interior boundary to corrupt.
In one line: **the template taught the model to write the argument *separator* as data, so the parser
re-tokenized a value as a key — a serialization-grammar violation installed by a mis-shaped example,
not a reasoning failure.** The alpha/r=0.5 scale and W4A16 long-context fragility are AMPLIFIERS, not
the cause (HF warns a JSON-string `arguments` mismatch "may cause errors or strange model behavior",
https://huggingface.co/docs/transformers/main/en/chat_extras, retrieved 2026-10-14; A8 quant caveat).

### 5d. The SAFE trajectory/template prescription (`_r4` §5)
1. **Never hand-serialize.** Build structured messages — `arguments` as a **dict** — and apply the
   model's own `apply_chat_template(..., tools=...)`. Do NOT pass a JSON string in `arguments` (HF
   dict-vs-string warning, retrieved 2026-10-14). This structurally removes the possibility of the two
   strings fusing.
2. **Byte-identical train/serve template.** Gemma's rule: the control-token schema must be consistent
   between training and inference (https://ai.google.dev/gemma/docs/core/prompt-structure, 2025-03-21).
   The vLLM Gemma-4 parser output MUST equal the `apply_chat_template` output used to build labels — a
   dev/eval template mismatch here is the foundation-level drift the accountability rules exist to catch.
3. **Round-trip-validate every row** through Gemma's own parser; assert `old_string` and `new_string`
   both round-trip byte-equal. Drop/fix any row that does not. This mechanical gate would have caught v2.
4. **Protect delimiter-bearing strings.** `edit_file` values legitimately contain newlines, commas,
   braces, backticks — ensure they always land inside the `<|"|>` quote span; add round-trip tests whose
   values deliberately contain `,`, `}`, backtick, `\n`.
5. **Mask loss to assistant/tool-call tokens only, and verify the mask is nonzero** (TRL
   `assistant_only_loss` with `{% generation %}` only around assistant turns, NOT tool-result turns).
   Directly addresses the §D loss-masking bug (an all-masked run gave mean_loss 0.0000). Assert
   mean_loss > 0 and the masked token count matches the assistant-turn count on a sample first.
6. **Few, diverse, every one format-correct** (LIMA + FireAct: at N≈tens a single malformed row is a
   large fraction of signal).
7. **Keep the adapter small / low-scale** — v2's degradation was dose-dependent in adapter scale (C4);
   LoRA "learns less and forgets less" at low rank is the safer regime (Biderman et al., 2405.09673).

---

## 6. RESEARCH QUESTION 5 — The W4A16/QLoRA interaction (train bf16 twin → serve on quantized base; rank/KV-cache at 32k)

**The setup is exactly: train on the bf16 twin, serve the adapter on the INT4 W4A16 base.**
[MEASURED-LOCAL] train→load→eval is PROVEN on A100 Colab with the gemma-4-31b-it bf16 base; vLLM sets
LoRA params dynamically from the submission (priors D, F).

**The precision pitfall [ESTABLISHED + INFERRED].** A LoRA trained against bf16 base weights is a
correction to the *bf16* weights, but at serve time it lands on *INT4-quantized* weights — the two
differ by the quantization error. QLoRA's own design avoids this by training the adapter against the
same NF4-quantized base it will be used with, so the adapter learns to compensate for quantization
(QLoRA, arXiv:2305.14314, 2023-05-23). [INFERRED] our bf16-train/INT4-serve split forgoes that
compensation; the cleaner path, if the training stack can reproduce vLLM's W4A16/NF4 object, is to
train the QLoRA against the SAME quantization used at serve. If exact W4A16 cannot be reproduced in
the HF/bitsandbytes stack, bf16-twin training is the pragmatic fallback — but expect a small
train/serve mismatch and validate on the FREE gate, never assume parity. **QAT nuance:** the ship base
is a quantization-aware-trained checkpoint whose INT4 weights are tuned to behave well at 4-bit;
adapting on a bf16 twin that was not the QAT-INT4 object risks correcting toward a slightly different
weight manifold — another reason to prefer training against the quantized object if feasible. Whether
the stack can reproduce W4A16 exactly is UNVERIFIED and must be checked in-stack.

**Rank / max_lora_rank / KV-cache at 32k [MEASURED-LOCAL + ESTABLISHED].** Constraints: ≤8 adapters,
rank ≤128, <3GiB total; fewer adapters + lower rank = more KV-cache; vLLM's `max_lora_rank`/`max_loras`
directly size reserved LoRA memory and trade against KV-cache (vLLM LoRA docs,
https://docs.vllm.ai/en/latest/features/lora.html, accessed 2025-02). [INFERRED] ship ONE small adapter
at the LOWEST rank that installs the commit behavior (start r=16, alpha=32; raise only on gate-shown
underfit, and if you raise rank use rsLoRA). At 32k ctx on 4×L4 the KV-cache is the binding resource
for long SWE trajectories, and 4-bit bites hardest exactly on long context (A8) — so a big high-rank
LoRA is doubly bad (eats context AND over-powers format, C3). This aligns with DoRA's low-rank sweet
spot: low rank is both the constraint and where the method is strongest.

---

## 7. MEASURED vs CLAIMED — the labeling discipline (summary)

- **[MEASURED-LOCAL] (not re-litigated):** commitment-not-localization is the binding failure (A1,
  A7); the edit-anchor skill is a non-problem the harness forgives (A2); v2 is the WRONG LoRA, not
  proof the LoRA path is wrong (A3); the prompt channel is exhausted and extra prompt load regresses
  the model (A4); live-best is v6w @ 0.15, adapter-free (A5); the LB top is adapter-free (A6); the v2
  forensic signatures C1 (regression 1/5 vs 2/5), C2 (search-death, 3/5 made 0 edits), C3
  (serialization key-collapse, edit_file-only), C4 (4-epoch over-train + dose-dependent scale degen);
  the decode-time wins in §B (`freq_penalty 0.4`, reserve-tail); the training/eval machinery (D); the
  scorer-gaming forbidden list (E); the hard constraints (F); the long-context quant caveat (A8).
- **[MEASURED/ESTABLISHED] (external literature, each with URL + date above):** LIMA, Gekhman,
  Biderman, Chu (SFT-memorizes/RL-generalizes), Aghajanyan, Holtzman, OR-Bench, ToolkenGPT, DreamBooth,
  B-LoRA, rsLoRA, QLoRA, DoRA, LoRA+, NEFTune, STaR, ReST^EM, Llama-2, Toolformer, SWE-Gym, FireAct,
  ToolLLM, Overthinking (2502.08235), AnimateDiff/MotionLoRA, the rentry craft doc, Raschka's tips,
  Gemma function-calling + prompt-structure docs, HF Transformers/TRL/PEFT docs, vLLM LoRA docs, the
  two quantization papers (2411.02355, 2505.20276).
- **[INFERRED] (our-setting extrapolation — hypotheses, not verdicts):** every mapping of a paper onto
  C1–C4; that the C3 collapse is a mis-shaped-example grammar violation amplified (not caused) by
  scale/quant; that the loss-masking boundary bug is the likeliest mechanical C3 cause (a HYPOTHESIS to
  confirm by inspecting actual `assistant_masks`); that commit-fast is SFT-trainable via a
  trajectory-shape filter; that decoding should be falsified before training. None are "real" until an
  external judge (by-task holdout or the FREE gate, then the LB) confirms them.

No external claim above contradicts a MEASURED-LOCAL fact; where theory reinterprets a prior (e.g.
alpha/r=0.5 as "dampened, not the C3 culprit"), the reinterpretation is cited and labeled INFERRED and
leaves the MEASURED signature intact.

---

## 8. HOW WE'D SETTLE OPEN DISAGREEMENTS ON OUR OWN DATA (cheap offline tests)

All arms run via the existing `eval_hf_adapter.py` plumbing on dev tasks with a **by-task holdout that
shares NO tasks with any tuning split** (metadata-stripped per forbidden-list E / rule 8). Pre-register
each arm's bar, null, and judge BEFORE running; a miss is a FAILURE reported as such; a null is a
result (rules 2, 3).

**Shared pre-registration.** *Bar:* a lever "moves commitment" iff it raises the edit-attempt rate
(fraction of tasks emitting ≥1 `edit_file`) on the holdout from the measured search-death baseline
(3/5 made 0 edits, C2) to ≥4/5, AND does not drop resolves below the v6 baseline (2/5). Edit-attempt
rate is the right proxy because the measured failure is "never calls edit_file," observable without
the hidden pytest. *Null to beat:* the no-change v6 decode config at the same budget. *Judge:* the
by-task, metadata-stripped holdout.

**The disagreements and the fastest falsifying test for each:**

- **DISAGREEMENT A — decode vs weights (the pivotal fork, §2/§B).** *Arm 1 (do first; hours, no GPU):*
  sweep decode/budget dials one at a time — `frequency_penalty` (around the 0.4 that already worked),
  `presence_penalty`, `temperature`/`top_p` (lower-entropy nucleus curbs loops, per Holtzman), and the
  get_status reserve-tail/edit-shape knob — each → edit-attempt-rate + resolves on the holdout. If Arm
  1 clears the bar, LoRA is unnecessary for commitment ("decoding-shaped, confirmed"). *Arm 2 (only if
  Arm 1 fails):* a tiny self-distilled set of passing commit-fast trajectories, two-key filtered, train
  a rank-8/alpha≤8, 1-epoch LoRA, eval on the same holdout/bar. Arm 2 clearing what Arm 1 could not =
  weights-shaped, LoRA justified. Both fail = honest harder null (may need outcome-reward RL per
  SFT-memorizes/RL-generalizes).

- **DISAGREEMENT B — is C3 a loss-masking boundary bug or the template shape? (§4/§5).** Cheapest test
  needs NO training: inspect the actual `assistant_masks` produced on one `edit_file` example — assert
  mean_loss > 0, the masked token count equals the assistant-turn count, and tool-result/user tokens
  are masked. If the mask leaks tool-result tokens or misaligns at the `old_string`/`new_string`
  boundary, that is the mechanical C3 cause. Independently, round-trip every row through Gemma's parser
  (also no training) — any row that fails round-trip is a confirmed poison label. Run both before
  spending a GPU cycle.

- **DISAGREEMENT C — is v2's degradation over-training or intrinsic? (C4, the open fork).** Train the
  SAME data at **1 epoch** vs 4 epochs, fixed r/alpha, and A/B edit-attempt-rate + C3 incidence on the
  holdout. If 1-epoch removes C2/C3, degradation was over-bake (expected); if it persists, it is more
  intrinsic. Pair with a serve-scale sweep (0.5 / 0.75 / 1.0) to confirm the dose-dependence directly.

- **DISAGREEMENT D — bf16-twin vs quantization-matched training (§6).** If the stack can reproduce
  W4A16/NF4, train one adapter each way on identical data and A/B on the holdout + FREE gate. If it
  cannot, that is itself the finding (bf16-twin is the only feasible path) — validate its serve-time
  behavior on the FREE gate rather than assuming parity.

**Sequencing (accountability rules).** Run the zero-training tests first (Arm 1 decode sweep;
Disagreement B's mask + round-trip inspection), because they are the fastest falsifiers and two of them
need no GPU at all. Only move to a training arm after the free/offline arms are exhausted, one change
per submission, FREE gate before the scored slot.

---

## Source index (consolidated; all cited inline above with dates)

**arXiv:** 2106.09685 (LoRA, 2021-06-17); 2012.13255 (Intrinsic Dim, 2020-12-22); 2203.14465 (STaR,
2022-03-28); 2208.12242 (DreamBooth, 2022-08-25); 2302.04761 (Toolformer, 2023-02-09); 2305.11206
(LIMA, 2023-05-18); 2305.11554 (ToolkenGPT, 2023-05-19); 2305.14314 (QLoRA, 2023-05-23); 2307.04725
(AnimateDiff/MotionLoRA, 2023-07-10); 2307.09288 (Llama 2, 2023-07-18); 2307.16789 (ToolLLM,
2023-07-31); 2308.08747 (Catastrophic Forgetting, 2023-08-17); 2310.05914 (NEFTune, 2023-10-09);
2310.05915 (FireAct, 2023-10-09); 2312.03732 (rsLoRA, 2023-12-06/2023-11-28); 2312.06585 (ReST^EM,
2023-12-11); 2402.09353 (DoRA, 2024-02-14); 2402.12354 (LoRA+, 2024-02-19); 2403.14572 (B-LoRA,
2024-03-21); 2405.05904 (Fine-Tuning New Knowledge, 2024-05-09); 2405.09673 (LoRA Learns Less,
2024-05-15); 2405.20947 (OR-Bench, 2024-05-31); 2411.02355 (W4A16 competitive, 2024-11-04); 2412.21139
(SWE-Gym, 2024-12-30); 2501.17161 (SFT Memorizes RL Generalizes, 2025-01-28); 2502.08235 (Overthinking,
2025-02-12); 2505.20276 (4-bit long-context loss, 2025-05-26); 1904.09751 (Neural Text Degeneration,
2019-04-22).

**Docs:** Gemma function-calling https://ai.google.dev/gemma/docs/capabilities/function-calling
(2025-03-21); Gemma prompt-structure https://ai.google.dev/gemma/docs/core/prompt-structure
(2025-03-21); HF Transformers tool use https://huggingface.co/docs/transformers/main/en/chat_extras;
HF chat templating https://huggingface.co/docs/transformers/en/chat_templating; HF TRL SFT
https://huggingface.co/docs/trl/en/sft_trainer; HF PEFT LoRA
https://huggingface.co/docs/peft/en/developer_guides/lora; HF PEFT quantization
https://huggingface.co/docs/peft/en/developer_guides/quantization; vLLM LoRA
https://docs.vllm.ai/en/latest/features/lora.html; Unsloth LoRA hyperparameters
https://docs.unsloth.ai/get-started/fine-tuning-guide/lora-hyperparameters-guide; "The Other LoRA
Rentry" https://rentry.org/59xed3 (2023-08); Raschka practical tips
https://magazine.sebastianraschka.com/p/practical-tips-for-finetuning-llms (2023-11-19).

*Content was rephrased for compliance with licensing restrictions; all external claims paraphrased
with inline attribution and dated URLs.*
