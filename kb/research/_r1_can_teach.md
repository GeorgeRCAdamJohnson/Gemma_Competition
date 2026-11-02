# R1 — What a LoRA Can and Cannot Teach (capability vs behavior)

> READ-ONLY web research deliverable. Research date: 2026-10-14.
> Question: does the literature support treating "commit-to-edit-fast / stop-searching after
> locating" as a **LoRA-shaped (weights) behavior problem** or a **prompt/decoding-shaped problem**,
> and what is the fastest cheap offline test to settle it on our own dev tasks?
>
> Labeling convention used throughout:
> - **[MEASURED/ESTABLISHED]** = result shown in the cited literature.
> - **[INFERRED]** = my extrapolation from that literature to our fixed `gemma-4-31b-it-qat-w4a16-ct`
>   agentic-SWE setting. Inferences are hypotheses, not verdicts (per the accountability contract).
> - **[LOCAL FACT]** = a measured prior from `_priors_brief.md` (not re-litigated here).
>
> Content compliance: all sources paraphrased; no quote exceeds 30 consecutive words; inline
> attribution + a dated URL list at the end. External theory may reinterpret a local prior but does
> not override a MEASURED LOCAL FACT.

---

## TL;DR (the defensible answer)

**"Commit-to-edit-fast / stop-searching after locating" is predominantly a DECODING- and
PROMPT-shaped problem, NOT a knowledge/capability problem — and therefore it is only *weakly*
LoRA-shaped.** The literature is consistent that fine-tuning (LoRA included) reliably reshapes
*behavior that the base model already can produce* — output format, response shape, when-to-stop /
when-to-commit, tool-call syntax, tone, refusal/commit tendency — and reliably *fails* to install
new *capability* (new reasoning skill or new factual knowledge). Our target is a behavior
(commitment timing), so it is in LoRA's "can-teach" class in principle. **But** the same literature
says (a) a *behavior* this local and this sample-starved is exactly what decoding controls and a few
curated examples both already move, (b) SFT/LoRA memorizes and transfers OOD *worse* than other
levers, and (c) our own [LOCAL FACT] evidence is that the one commitment lever that *durably* worked
was a **decode-time** change (freq_penalty 0.4 killed the repeat-loop; reserve-tail + edit-shape made
every task reach an edit — priors A/B §B), while the only LoRA we trained *regressed* into
search-death and tool-call serialization collapse (C1-C3).

**Net recommendation: LoRA is not the first tool here. Spend the next cheap cycles proving the
decoding/prompt channel is actually exhausted for commitment with a controlled sweep, because the
cross-domain evidence says that channel is where "when to stop/commit" lives.** If — and only if — a
pre-registered decode sweep fails to move commitment on a by-task holdout, then a *commitment-shaped*
LoRA (not an edit-anchor LoRA) becomes the justified next lever, trained as a behavior-cloning /
self-distill of *passing* commit-fast trajectories, low-rank, 1 epoch, scale ≤0.5. This is **not** a
retreat to the herd (the herd runs adapter-free too, A6); it is sequencing the cheapest falsifying
test first per the accountability rules.

---

## 1. What LoRA / fine-tuning RELIABLY changes (behavior) — [MEASURED/ESTABLISHED]

**1.1 Output format and response shape — strongly learnable from very few examples.**
LIMA (Zhou et al., 2023) fine-tuned a 65B base on only 1,000 curated prompt-response pairs with plain
supervised loss, no RL, and the model learned to follow specific response formats from a handful of
examples and generalized to unseen tasks; the authors argue almost all knowledge is from pretraining
and alignment mainly teaches *format/style* ("Superficial Alignment Hypothesis"). This is the single
strongest literature anchor that **format/shape/style = behavior = few-shot learnable by SFT/LoRA.**
([MEASURED] arXiv 2305.11206, 2023-05-18.)

**1.2 "How to use existing ability," not "new ability."**
Gekhman et al. ("Does Fine-Tuning LLMs on New Knowledge Encourage Hallucinations?", 2024) show in a
controlled closed-book-QA setup that models acquire *new facts* through fine-tuning very slowly, and
that fine-tuning mostly teaches the model to **use pre-existing knowledge more efficiently** rather
than install new knowledge. Mapped to us: a LoRA can plausibly teach the model *to deploy its
existing editing ability sooner* (a usage/behavior change) but cannot teach it *to edit code it
couldn't already edit* (a capability it would have to already possess). ([MEASURED] arXiv 2405.05904,
2024-05-09.) [INFERRED] commitment-timing is a "use what you already have sooner" change → inside
LoRA's reliable class.

**1.3 Tool-call syntax / argument serialization — learnable, and fragile under over-scaling.**
Instruction-tuning on tool demonstrations is the classic way to teach tool-call *syntax* (ToolkenGPT,
Hao et al., 2023, surveys the finetune-on-tool-demos paradigm and its costs). [MEASURED] arXiv
2305.11554, 2023-05-19. But the LoRA *scaling factor* governs how hard the adapter pushes: rsLoRA
(Kalajdzievski, 2023) shows the conventional alpha/r scaling slows learning and "stunts" higher-rank
adapters, and that the scale factor directly controls effective learning strength. [MEASURED] arXiv
2312.03732, 2023-11-28. [INFERRED] this is the mechanistic literature match for our [LOCAL FACT] C3
"serialization key-collapse" and C4 "dose-dependent argument collapse at scale ≥0.75": a tool-call
*format* behavior was over-driven by adapter scale, producing a degenerate repeated malformed
serialization — a *format collapse*, not evidence the behavior is unlearnable.

**1.4 Refusal / commit tendency is a tunable behavior (and easy to over-tune).**
The over-refusal literature (OR-Bench, Cui et al., 2024) establishes that "when to refuse vs commit"
is a *behavioral dial* that alignment moves, and that pushing it one way reliably produces the
opposite failure (over-refusal / under-commit). [MEASURED] arXiv 2405.20947, 2024-05-31. [INFERRED]
"keep searching instead of committing to an edit" is the agentic analogue of over-refusal: a
commit/withhold behavior that is tunable but prone to overshoot — consistent with our LoRA tipping
3/5 tasks into *zero* edit attempts (C2).

**1.5 Image/video-generation LoRA — the same lesson, cross-domain.** (user explicitly asked to learn
from image/video LoRA practice)
- DreamBooth (Ruiz et al., 2022) binds a *new behavior/subject* into a frozen diffusion model from
  **just a few images** by associating a unique identifier — the diffusion-world proof that LoRA-style
  low-data adaptation teaches *appearance/behavior binding*, not new generative *capability*.
  [MEASURED] arXiv 2208.12242, 2022-08-25.
- B-LoRA (Frenkel et al., 2024) shows a LoRA cleanly separates **style from content** — i.e. the
  adaptation targets the *presentational/behavioral* axis (style) while leaving *content/capability*
  intact. [MEASURED] arXiv 2403.14572, 2024-03-21.
- [INFERRED] The transferable craft lesson from image/video LoRA (DreamBooth/B-LoRA + widespread
  practitioner practice): LoRA excels at **"do it in THIS style / with THIS behavior,"** needs **few
  but clean, consistent exemplars**, and **collapses when over-trained or over-scaled** (the diffusion
  analogue of our C3/C4 — "frying" a style LoRA at too-high weight/too-many-steps is the exact same
  failure mode as our serialization collapse at alpha/r pressure). Our target ("commit to the edit in
  THIS decisive style") is squarely a style/behavior-binding task in LoRA's wheelhouse — *if* trained
  on clean passing exemplars at low scale.

---

## 2. What LoRA / fine-tuning STRUGGLES to add (capability) — [MEASURED/ESTABLISHED]

**2.1 New factual knowledge — slow and hallucination-inducing.** Gekhman et al. (2405.05904): new
knowledge is learned much slower than knowledge-consistent examples, and as the new-knowledge
examples *are* eventually fit, they **linearly increase hallucination**. [MEASURED] 2024-05-09.
[INFERRED] irrelevant to our target directly (we are not teaching facts), but it is the warning rail:
if a "commitment" dataset smuggles in task-specific *answers* (forbidden-list E), we would be teaching
new "facts" and inducing exactly this hallucination/overfit — reinforcing the forbidden-list.

**2.2 New reasoning/skill — LoRA underperforms, and memorizes rather than generalizes.**
- "LoRA Learns Less and Forgets Less" (Biderman et al., 2024): on **programming and math** (our exact
  domain class), LoRA *substantially underperforms* full fine-tuning at standard low ranks, though it
  forgets the base less; full FT needs rank 10–100× higher than typical LoRA. [MEASURED] arXiv
  2405.09673, 2024-05-15. [INFERRED] a LoRA is a poor vehicle for installing *coding skill*; good
  thing our target is not coding skill (A1) — but it also means do NOT expect a LoRA to compensate for
  any genuine capability gap; it can only reshape behavior.
- "SFT Memorizes, RL Generalizes" (Chu et al., 2025): SFT tends to **memorize training data and
  struggles OOD**, while outcome-reward RL generalizes; crucially, SFT's main *useful* role is that it
  **stabilizes output format** so RL can then work. [MEASURED] arXiv 2501.17161, 2025-01-28.
  [INFERRED] this is the central caution for us: a *supervised* commitment-LoRA will likely memorize
  the shape of our ~dozens of dev trajectories and transfer poorly to the hidden holdout (echoing our
  C1 regression and the by-task holdout requirement in the forbidden-list). It argues for (a) training
  on *behavioral shape* (commit-fast structure) not task content, and (b) treating a supervised LoRA
  as a *format stabilizer*, not a generalizing fix.

**2.3 Why low-rank even works for behavior (and why that bounds it).** Intrinsic-dimension (Aghajanyan
et al., 2020) shows pretrained models have very low intrinsic dimension — a few hundred parameters can
reach ~90% of full-FT on a task — which is *why* LoRA/low-rank adaptation can reshape behavior at all.
[MEASURED] arXiv 2012.13255, 2020-12-22. [INFERRED] a *behavior* like commit-timing should sit in a
low-dimensional subspace → a **very low rank** adapter should suffice; a high-rank adapter (our r=32,
167MB) is over-parameterized for a behavior dial and raises the C3/C4 collapse risk for no benefit,
and it eats KV-cache (constraint F).

---

## 3. The pivotal fork: is commitment DECODING-shaped or WEIGHTS-shaped?

**3.1 The decoding literature says "repetition / failure-to-terminate" is a DECODING phenomenon.**
Holtzman et al. ("The Curious Case of Neural Text Degeneration", 2019) show the *same* model produces
bland, **repetitive** text or good text depending **only on the decoding strategy** — degeneration is
not fixed in the weights, it is a decode-time property. [MEASURED] arXiv 1904.09751, 2019-04-22.
[INFERRED] our "repeat-until-death loop" and "grep/read/pytest until budget dies" are the agentic
analogue of neural degeneration: a loop the decoder falls into. The literature predicts this is
movable at decode time — which is **exactly what our [LOCAL FACT] already observed**: freq_penalty 0.4
killed the repeat-loop (max_repeat ≤2 on every task) and a reserve-tail + edit-shape made every task
*reach* an edit (priors §B, log ≈5104-5107 / 5723-5727). That is strong convergent evidence the
*mechanism* lives at decode time.

**3.2 But the prompt channel is [LOCAL FACT]-declared saturated (A4).** Adding prompt text *degrades*
this model (v20, v19v3). So the fork is really **decoding vs weights**, with prompt largely spent.

**3.3 Reconciliation / defensible position.**
- The behavior is *in LoRA's teachable class* (it is behavior, not capability — §1). So "LoRA cannot
  do this" is **false** and should not be claimed.
- BUT the *cheapest, highest-evidence* channel for "when to stop/commit" is decoding (§3.1 + our own
  decode wins), and SFT/LoRA on a few dozen trajectories is the channel most likely to *memorize and
  fail the holdout* (§2.2). So **decoding should be falsified first**, not because it is the herd
  (A6/rule 14) but because it is the fastest falsifying test and the one our own data already lit up.
- A commitment-LoRA remains the justified *next* lever if decoding is proven exhausted — and it must
  be trained as a **low-rank, low-scale, 1-epoch behavior clone of passing commit-fast trajectories**
  (§1.5 craft + §2.2 memorization caution + §2.3 low-rank sufficiency), NOT a high-rank edit-anchor
  adapter (which the forensic already proved is the wrong LoRA, A3/C).

This is a "LoRA is probably not the *first* tool; prove the decode channel first, keep a correctly
shaped LoRA as the sequenced fallback" finding — a valid null-leaning result, not a forced pro-LoRA
conclusion.

---

## 4. The fastest cheap OFFLINE test to settle it (pre-registered)

Goal: decide decode-vs-weights **before** spending a GPU training cycle, using the existing local
plumbing (`eval_hf_adapter.py`, dev tasks, by-task holdout). Two arms, run on the *same* held-out
split that shares NO tasks with any tuning split.

**Pre-registration (write before running — rule 2):**
- **Bar:** a lever "moves commitment" iff it raises *edit-attempt rate* (fraction of tasks that emit
  ≥1 `edit_file`) on the holdout from the measured search-death baseline (3/5 made 0 edits, C2) to a
  pre-set threshold (e.g. ≥4/5 reach an edit) **AND** does not reduce resolves below the v6 baseline
  (2/5). Edit-attempt-rate is the right proxy because the [LOCAL FACT] failure is "never calls
  edit_file," and it is observable without the hidden pytest.
- **Null it must beat:** the no-change v6 decode config at the same budget.
- **Judge:** by-task holdout, metadata-stripped (forbidden-list E / rule 8), reported pass/fail; a
  miss is a FAILURE, reported as such.

**Arm A — DECODING sweep (do this first; hours, no training).** On the fixed model, sweep the
decode/budget dials the degeneration literature + our own log implicate, one at a time:
`frequency_penalty` (around the 0.4 that already worked), `presence_penalty`, `temperature` /
nucleus `top_p` (per Holtzman, lower-entropy nucleus curbs loops), and the get_status reserve-tail /
edit-shape budget knob. Each config → edit-attempt-rate + resolves on the holdout. **If Arm A already
clears the bar, LoRA is unnecessary for commitment and the finding is "decoding-shaped, confirmed."**

**Arm B — minimal behavior-probe (only if A fails).** Build a *tiny* self-distilled set of
**passing commit-fast trajectories** (host-blessed self-distill, forbidden-list legitimate path):
run the agent, keep only trajectories that located-then-committed-then-passed, strip task identity,
train a **rank-8, alpha≤8 (scale ≤1), 1-epoch** LoRA (low-rank per §2.3, low-scale per §1.3/C4,
1-epoch per C4 overfit caution), eval on the same holdout with the same bar. A win here that Arm A
could not reach is the evidence that the residual is weights-shaped. A regression (as in C1) confirms
decode is the right channel.

**Falsification logic:** Arm A clears bar → *decode-shaped*. Arm A fails, Arm B clears → *weights-
shaped, LoRA justified, correctly shaped this time*. Both fail → the behavior may need outcome-reward
RL (§2.2 SFT-memorizes/RL-generalizes) or is capability-bound, i.e. an honest harder null.

**Why this is cheap and decisive:** Arm A needs zero training and reuses the exact decode levers that
already produced local signal; Arm B is a single small 1-epoch run. It directly tests the §3 fork
instead of debating it, and it respects the accountability contract (external-ish judge = by-task
holdout, pre-registered bar, one change at a time, honest null allowed).

---

## 5. Mapping to the local priors (no contradictions claimed)

| Local prior | Literature view | Verdict |
|---|---|---|
| A1 commitment is the binding failure | commitment = behavior (§1.1/1.2/1.4) | consistent; behavior is teachable but decode-first |
| A3 need a COMMITMENT LoRA not an edit-anchor LoRA | §2.3 low-rank behavior + §2.2 shape-not-content | consistent; if LoRA, train commit-fast *shape*, low rank/scale |
| A4 prompt channel exhausted | §3.2 | accepted (local measured) → fork is decode vs weights |
| §B decode wins (freq_penalty, reserve-tail) | §3.1 degeneration is decode-controlled | strong convergent support → test decode first |
| C3/C4 serialization/argument collapse at scale | rsLoRA scale factor (§1.3), image-LoRA "frying" (§1.5) | mechanistic match → low scale, low rank, 1 epoch |
| A6 LB top is adapter-free | — | decode-first is NOT herd-retreat; it is the fastest falsifier (rule 14) |

Nothing above contradicts a MEASURED LOCAL FACT. The only *new* stance is sequencing: **falsify
decoding before training**, justified by the degeneration literature + our own decode-time wins.

---

## Sources (URL + date)

1. Hu et al., *LoRA: Low-Rank Adaptation of Large Language Models* — https://arxiv.org/abs/2106.09685 (2021-06-17)
2. Dettmers et al., *QLoRA: Efficient Finetuning of Quantized LLMs* — https://arxiv.org/abs/2305.14314 (2023-05-23)
3. Zhou et al., *LIMA: Less Is More for Alignment* — https://arxiv.org/abs/2305.11206 (2023-05-18)
4. Biderman et al., *LoRA Learns Less and Forgets Less* — https://arxiv.org/abs/2405.09673 (2024-05-15)
5. Gekhman et al., *Does Fine-Tuning LLMs on New Knowledge Encourage Hallucinations?* — https://arxiv.org/abs/2405.05904 (2024-05-09)
6. Aghajanyan et al., *Intrinsic Dimensionality Explains the Effectiveness of Language Model Fine-Tuning* — https://arxiv.org/abs/2012.13255 (2020-12-22)
7. Chu et al., *SFT Memorizes, RL Generalizes* — https://arxiv.org/abs/2501.17161 (2025-01-28)
8. Hao et al., *ToolkenGPT: Augmenting Frozen Language Models with Massive Tools* — https://arxiv.org/abs/2305.11554 (2023-05-19)
9. Holtzman et al., *The Curious Case of Neural Text Degeneration* (nucleus sampling) — https://arxiv.org/abs/1904.09751 (2019-04-22)
10. Ruiz et al., *DreamBooth: Fine Tuning Text-to-Image Diffusion Models* — https://arxiv.org/abs/2208.12242 (2022-08-25)
11. Frenkel et al., *Implicit Style-Content Separation using B-LoRA* — https://arxiv.org/abs/2403.14572 (2024-03-21)
12. Kalajdzievski, *A Rank Stabilization Scaling Factor for Fine-Tuning with LoRA (rsLoRA)* — https://arxiv.org/abs/2312.03732 (2023-11-28)
13. Cui et al., *OR-Bench: An Over-Refusal Benchmark for Large Language Models* — https://arxiv.org/abs/2405.20947 (2024-05-31)
14. Hugging Face PEFT — *LoRA conceptual guide* — https://huggingface.co/docs/peft/main/en/conceptual_guides/lora (accessed 2026-10-14)

*Freshness note:* arXiv abstracts + HF docs fetched and parsed on 2026-10-14. Dates above are the
arXiv citation_date (first-version) for each paper.
