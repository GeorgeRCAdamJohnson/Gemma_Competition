# R2 — Lessons from Image/Video-Generation LoRA Craft, Translated to Text/Agentic

> READ-ONLY web research. Target question for the whole effort: *what do we train into a thin LoRA
> so the FIXED `gemma-4-31b-it-qat-w4a16-ct` COMMITS to an edit instead of searching until the
> budget dies (the "search-death" / commitment failure, prior A1)?* This file mines the one body of
> craft the user explicitly asked for — the SDXL/Flux/SD1.5/AnimateDiff LoRA community — and gives
> an explicit image→text analogy for every principle, plus the places the analogy BREAKS.
>
> Labeling convention: **[MEASURED]** = a result in our local priors brief or a number stated in a
> cited source; **[ESTABLISHED]** = widely-reproduced community/paper practice; **[INFERRED]** = my
> cross-domain translation, a hypothesis for the gates to decide (per accountability rules 6/11).
> Nothing here contradicts a MEASURED LOCAL FACT (priors brief §A). Citations: URL + date inline.

---

## 0. TL;DR for the impatient

The image/video-LoRA community solved "teach a frozen model one new *behavior* from very little
data without wrecking the base" a thousand times over. Their hard-won craft maps onto our problem
with surprising fidelity, and it converges on a consistent story that our v2 failure is a **textbook
over-baked / format-collapsed character LoRA**, not evidence the LoRA path is dead:

1. **Small-but-clean >> large-but-noisy.** The "20–50 great images" ethos ≈ LIMA's 1k curated
   examples. Our commitment adapter should be a *small, surgically clean* set of **passing
   commit-fast trajectories**, not a big dump. (§1)
2. **Caption what varies; bake in what is constant.** The commitment *behavior* (stop searching →
   emit `edit_file`) is the thing to BAKE; the bug, repo, and file must stay VARIABLE in the
   prompt — baking any of those is the forbidden scorer-gaming failure. (§2)
3. **v2's `alpha/r = 0.5` is NOT inherently wrong** — Raschka found `alpha/r = 0.5` *optimal* at
   r=256. The implicated variable is **4 epochs on 23 examples** (over-bake) + a **template that
   fused the two edit strings**, i.e. an overfit/format-collapse signature, which the image
   community diagnoses and fixes routinely. (§3, §5)
4. **The commitment problem is a "motion/behavior LoRA," not a "subject/knowledge LoRA."**
   AnimateDiff's MotionLoRA (adapt *motion patterns* as a separable low-rank module) is the closest
   analog in the whole field, and it is a *behavior* adapter. (§6)
5. **Where it breaks:** the single cleanest break is **the loss objective** — image LoRAs optimize a
   per-pixel denoising MSE where every element is supervised in parallel; our adapter optimizes
   autoregressive next-token CE over a *structured tool-call + multi-turn trajectory* where one
   malformed `edit_file` key (v2's C3) poisons the entire turn. "Deep-fry/burn" has a direct text
   analog; "limited poses" has a *partial* one; **JSON-key-collapse has no image analog at all.** (§7)

---

## 1. Dataset curation & balance — "20–50 great images" ⇒ "20–50 clean passing trajectories"

**The image craft.** The canonical community science doc ("The Other LoRA Rentry," rentry.co/59xed3,
updated through 2023-08) states the baseline recipe is *"grab 30–100 images of decent quality and go
wild"* with *"1000 total steps on average and about 50-100 images"* and that *"The AI is more
tolerant of a few low quality images than of a few bad tags"* — i.e. the binding constraint is
**label cleanliness, not volume** (rentry.co/59xed3, 2023-08). The doc's single loudest warning is
*"Bad tags contaminate the model"* and false-positive tags are called *"EL DIABLO"* because
*"consistency drops considerably"* (rentry.co/59xed3, 2023-08).

**The text-side confirmation.** This is exactly LIMA's thesis: a 65B model fine-tuned on *"only 1,000
carefully curated prompts and responses"* learns *"to follow specific response formats from only a
handful of examples"* and generalizes to unseen tasks (LIMA, arXiv:2305.11206, 2023-05-18)
**[MEASURED in source]**. QLoRA independently reports that *"finetuning on a small high-quality
dataset leads to state-of-the-art results"* (QLoRA, arXiv:2305.14314, 2023-05-23) **[MEASURED in
source]**. Raschka reproduced LIMA's edge: his best LoRA config *"on LIMA, I got similar, if not
better, performance than the 50x larger Alpaca dataset"* (sebastianraschka, 2023-11-19)
**[MEASURED in source]**.

**Diversity vs concept bleed.** The rentry doc teaches that if you train a subject only in one
context, that context *"bleeds"* into everything: *"If you train with just images of Superman in his
costume, the AI will attempt to draw the logo on pretty much everything you prompt for, even a
business suit."* The fix is **on/off examples**: *"you want images where that element is clear, and
images where the element is not present"* because *"The Unet seems to learn by 'difference'"*
(rentry.co/59xed3, 2023-08) **[ESTABLISHED]**.

**→ Text/agentic analogy [INFERRED].**
- *How many trajectories?* The craft says the answer is **tens, not thousands** — matched to our
  reality that v2 trained on **23 examples** (priors C4) and the real lever is cleanliness. Do not
  "fix" v2 by scaling to a big trajectory dump; fix the *per-example quality*.
- *How diverse?* Diverse enough to prevent **context-bleed**: the "Superman logo on a business suit"
  failure is our risk of baking a *particular repo's* edit style, or a *particular file path*, into
  the behavior. Vary repo, bug type, file, and surrounding code so only the *commit-fast motion*
  is the invariant that gets learned — not any specific answer.
- *How clean?* "Bad tags contaminate the model" ⇒ a single trajectory whose "assistant" turn
  contains a *malformed* `edit_file` call, or a trajectory where the model searched before
  committing, is a poison label that teaches the exact failure we are trying to remove. Every
  trajectory must be a **clean, minimal, commit-first** demonstration. This ties to the host-blessed
  legitimate path (priors E): *run the agent on public issues and keep ONLY test-passing
  trajectories* — that IS the image community's "only use clean images" rule.
- *The on/off principle* is the subtle one: to teach "stop searching, commit," you arguably want
  BOTH commit-fast trajectories AND (negatively-weighted or contrastively-structured) counter
  examples — but SFT has no "negative" channel the way a prompt negative does (see §7 break #4), so
  the clean route is to make the *positive* class overwhelmingly the commit-fast motion.

---

## 2. Captioning / conditioning discipline — "tag the variable, bake the constant"

**The image craft (the single most transferable idea in the whole doc).** The rentry doc's rule:
*"Training works by instructing the AI to 'find' the tagged elements."* A tagged thing becomes
**promptable/variable**; an *un-tagged* thing gets **baked into the trigger/subject** and fires
regardless. Concretely: *"If you have a character in a cape, it'll always consider the cape part of
the character unless you tell it the character is wearing a cape"* (rentry.co/59xed3, 2023-08). The
activation/trigger token *"should be the very first tag ... and present in every tag file,"* and at
generation time *"this activation word can be weighted in a prompt (like (character:1.2))"*
(rentry.co/59xed3, 2023-08) **[ESTABLISHED]**. The discipline is therefore:

> **Caption (= leave variable) everything the user will want to change; OMIT (= bake into weights)
> only the invariant you are training.** Over-tagging makes the model *"too rigid"*; under/mis-tagging
> *"can ruin your model"* (rentry.co/59xed3, 2023-08).

**→ Text/agentic analogy [INFERRED].**
- **What belongs in the prompt/system (= "caption", variable):** the bug symptom, the repo tree, the
  file contents, the failing test, the tool schema. These MUST stay in-context and MUST drive each
  decision — they are the "pose/clothing/background" that changes every task.
- **What to bake into the weights (= the untagged trigger/subject):** the *commit-fast motion
  itself* — the policy "once you've localized, emit `edit_file` rather than another grep." This is
  the one invariant across all tasks, so it is exactly what should be un-captioned and absorbed into
  weights. This matches priors A3 (train COMMITMENT) and A4 (the prompt channel is exhausted for
  commitment — i.e. captioning the behavior in-prompt *decayed*; the craft predicts a baked,
  un-captioned behavior is the durable channel).
- **Trigger-token / activation-phrase analogue:** the image community's "first tag, every file,
  weightable" trigger ≈ a reserved **activation phrase or a consistent assistant-turn preamble**
  (e.g. the agent's own "I have located the fault; applying the fix:" immediately before the edit).
  Baking a consistent *commit preamble* gives the behavior a handle, the way `(character:1.2)` gives
  the subject a handle. **[INFERRED — a gate must test it.]**
- **THE FORBIDDEN BAKE (scorer-gaming, priors E).** The image analog of "baking in the problem
  statement" is baking the *gold diff* keyed on the repo/problem text. The rentry's "Superman logo"
  warning is the benign version; our version is actively banned: do **not** caption/condition on
  `instance_id`, problem-statement fingerprints, or ship gold patches. The craft rule "bake only the
  invariant *behavior*, keep the task-specific content variable" is precisely the line that keeps us
  on the legal side: *commit-fast* is a generalizable invariant; *the answer to rich_4077* is not.

---

## 3. Rank / alpha / dim — what capacity to give the behavior, and is v2's `alpha/r = 0.5` implicated?

**What rank controls.** The LoRA paper decomposes the weight update ΔW into low-rank A·B; rank r is
*"a hyperparameter"* trading capacity vs parameter count and the paper gives *"an empirical
investigation into rank-deficiency"* showing a very low rank already captures most of the useful
update (LoRA, arXiv:2106.09685, 2021-06). Community craft: *"higher the value the higher the
'expressive power' ... but has a drawback of higher file size,"* with the pragmatic ladder
**"a size of 64 tends to suffice ... 128 is already a bit of a waste"** for a single subject, higher
only for very diverse concept sets (rentry.co/59xed3, 2023-08) **[ESTABLISHED]**. The image rule
"larger r for more diverse content" is echoed exactly by Raschka: *"the more diverse the tasks in
the dataset, the larger the r should be"* and *"too large could result in more overfitting"*
(sebastianraschka, 2023-11-19) **[ESTABLISHED]**.

**The alpha/rank scaling convention.** Both communities use the identical formula
`scaling = alpha / r`, applied as `weight += (B@A) * scaling`. Image craft: alpha *"is basically a
learning brake, or dampener ... relative to the value of net dim ... multiplying them by
(alpha/net dim)"*; the worked example is explicit — *"Alpha 64 = 64/128 = x0.5"*, and
*"Alpha needs to be equal or lower than rank"*; pushing alpha *above* rank "burned up" the output
(rentry.co/59xed3, 2023-08). Text side, same formula and the famous heuristic: *"Choosing alpha as
two times r is a common rule of thumb when using LoRA for LLMs"* (sebastianraschka, 2023-11-19)
**[ESTABLISHED]**.

**Is v2's `alpha/r = 0.5` the culprit? — reconciling with a MEASURED local fact.**
v2 = **r=32, alpha=16 ⇒ scaling = 16/32 = 0.5** (priors C3). Two cited facts constrain the reading:
- By the shared formula, **0.5 is a LOW / dampened scaling** (half strength), not an amplified one.
  The rentry's "burn" regime is `alpha > rank` (scaling > 1), the opposite end. So on the pure
  scaling convention, 0.5 should *attenuate* the adapter's influence, which is why the one resolve
  "happened IN SPITE of the adapter" (priors C1) is coherent — a half-strength adapter nudges little.
- Raschka's data makes the key point: `alpha/r = 0.5` is **not inherently broken** — he found
  *"r=256 and alpha=128 (a 0.5-fold scaling) performance is even better"* than the 2× rule
  (sebastianraschka, 2023-11-19) **[MEASURED in source]**. So the ratio alone does not explain v2.

> **Reconciliation [INFERRED, labeled].** The priors forensic (C3) attributes the serialization
> key-collapse to the training-data template shape *"amplified at alpha/r=0.5,"* and the priors brief
> itself flags that attribution as an *inference, not measured against the training set* (priors §
> Uncertainty ledger). The image/text craft here suggests the **ratio is a red herring and the real
> implicated variables are (a) the fused-string template (§2/§5) and (b) over-baking (§4/C4)**. At
> r=32 the half-scaling would, if anything, *reduce* corruption, not amplify it — so a format
> collapse at scaling 0.5 points to the *data template* teaching the collapse, exactly the rentry's
> "bad tags contaminate the model." This is a hypothesis for a gate (vary template at fixed r/alpha),
> consistent with but not overriding the MEASURED signature C3.

**→ Rank recommendation [INFERRED].** The commitment behavior is **low-diversity** (one motion:
localize→commit), and "LoRA Learns Less and Forgets Less" shows *"full finetuning learns
perturbations with a rank that is 10-100X greater than typical LoRA"* while LoRA *"better maintains
the base model's performance on tasks outside the target domain"* (Biderman et al.,
arXiv:2405.09673, 2024-05) **[MEASURED in source]**. For a *narrow behavior* that must NOT disturb
the base model's coding ability, the image rule ("err on the side of lower values") + the
forgetting-mitigation finding both argue for a **low rank** (the deployment constraint, priors F,
independently caps rank ≤128 and rewards low rank for KV-cache). v2's r=32 is already in a sane band;
the fix is upstream of rank.

---

## 4. Learning rate, steps/epochs, repeats, and regularization images ⇒ replay/anchor data

**Image craft.** The doc's "Easy settings" are **~1000 total steps, 50–100 images, alpha 1 (heavy
dampen), rank 64**, with adaptive optimizers to *"remove the guesswork"* (rentry.co/59xed3, 2023-08).
Crucially: *"The more steps you can fit into the training without burning up the Unet ... the
better. So at times you may want to dampen learning so you can train more"* — i.e. **dampen + more
gentle steps beats few aggressive steps** (rentry.co/59xed3, 2023-08) **[ESTABLISHED]**.

**Text side — epochs are dangerous.** Raschka: increasing Alpaca iterations ~2× gave *"a decline in
model performance ... multi-epoch training might not benefit instruction finetuning since it can
deteriorate the results ... likely due to increased overfitting"*, and *"I observed the same with
the 1k-example LIMA dataset"* (sebastianraschka, 2023-11-19) **[MEASURED in source]**. This is a
direct hit on **priors C4: v2 ran 4 epochs** and drove loss **0.9068 → 0.4270 → 0.2621 over 3
epochs on only 23 examples** — a near-memorization curve that both communities flag as over-bake.

**Regularization images ⇒ replay/anchor data (the catastrophic-forgetting lever).** The image doc:
reg images are the *"screensaver"* that stops the Unet "burning," using same-class images so the
model keeps its general prior (rentry.co/59xed3, 2023-08). The text analog is explicit and measured:
Raschka's LoRA *"unlearned arithmetic because the Alpaca dataset did not contain corresponding
examples ... it's probably a good idea to include examples of each task you care about"*
(sebastianraschka, 2023-11-19) **[MEASURED in source]**. Catastrophic forgetting *"is generally
observed in LLMs ranging from 1b to 7b"* and *"general instruction tuning can help alleviate the
forgetting"* (Luo et al., arXiv:2308.08747, 2023-08) **[MEASURED in source]**. And the good news for
our method: *"LoRA mitigates forgetting more than common regularization techniques such as weight
decay and dropout"* (Biderman et al., arXiv:2405.09673, 2024-05) **[MEASURED in source]**.

**→ Text/agentic analogy [INFERRED].**
- **Fewer epochs, gentler.** The direct remedy to C4: **1 epoch** (the priors brief itself names a
  "1-epoch ablation" as the open fork), low LR, and let a small clean set do the work. Both
  communities independently say over-iteration is the overfit mechanism.
- **Replay/anchor data = regularization images.** To protect the base model's coding/tool-use
  ability from being "burned" by a narrow commitment set, mix in **anchor trajectories of normal,
  correct multi-step tool use** (including cases where *more* investigation legitimately precedes an
  edit) — the "same-class reg images" so the adapter learns "commit faster" without unlearning "when
  genuinely to look first." This is also a defense against turning search-death into its mirror
  failure (premature wrong-fix; note priors A7 already shows WRONG-FIX is the single largest cell).

---

## 5. OVERFITTING SIGNATURES — image "burn/artifacts/limited poses" ⇒ what is the text analog, and
what was v2?

**Image signatures.** Overfit = Unet *"burning up"* → *"probabilities for things set too high or too
low,"* visually **deep-fry/artifacts**, and behaviorally **rigidity**: *"If you have to lower
[strength] to not ruin images, it's overfit or poorly trained"*, and the model fixates — *"limited
poses"* / *"samey poses"* when the data lacked variety (rentry.co/59xed3, 2023-08) **[ESTABLISHED]**.
The diagnostic is the **epoch XY-plot**: save every epoch, sweep strength 0→1, and *"epoch 7/10 ...
is perfectly fine"* — pick the pre-burn checkpoint (rentry.co/59xed3, 2023-08) **[ESTABLISHED]**.

**Text analogs [INFERRED unless noted].**
| Image overfit signature | Text/agentic analog |
|---|---|
| **Deep-fry / burn** (probabilities pushed to extremes) | **Degenerate decoding**: collapse to a near-deterministic token path; repetition loops. v2's C3 repeat-loop of the *same malformed* `edit_file` is burn: the adapter forced one output distribution so hard it repeated a broken serialization 11+ times. **[MEASURED signature, C3]** |
| **Limited / samey poses** (low output diversity) | **Behavioral collapse to one action**. v2's C2 search-death — 3/5 tasks make **0 edit attempts**, every budget spent on grep/read — is "samey poses": the adapter collapsed the policy toward one mode. **[MEASURED signature, C2]** |
| **Needs strength < 1.0 to not ruin output** | **Needs low adapter scaling / early checkpoint to not regress**. The 12B dose-dependent finding (priors C4: degen≈0 at scale ≤0.5, severe at 1.0) is the *exact* text version of the strength-sweep diagnostic. **[MEASURED, C4]** |
| **Burn even at epoch 1** → data/LR problem, not just over-bake | Format collapse present early ⇒ **training-data template bug**, not pure over-iteration. |

**So: was v2 overfit, a data-shape bug, or both? [INFERRED verdict, for the gates]** — **Both, and
the craft lets us separate them:**
- **C2 (search-death) and the dose-dependence are classic over-bake/over-scale** (deep-fry +
  samey-poses) — remedied by *fewer epochs + lower effective scale*, straight from §4. The image
  community would say "you cooked it; use epoch 1 and lower strength."
- **C3 (serialization key-collapse)** is **NOT** the generic burn signature — it is a *structured*
  corruption specific to `edit_file`'s dual-string payload, which `run_command` does NOT show
  (priors C3). An image LoRA has no "two-field payload that can fuse," so this is the **data-shape /
  template bug** ("bad tags contaminate the model"): the training template serialized `old_string`
  and `new_string` so they ran together, and the adapter memorized that fused shape. The fix is a
  **captioning/template fix (§2) + fewer epochs (§4)**, not a rank change.
- This reconciles with the MEASURED facts without contradiction: the priors brief already labels the
  template attribution an *inference* and leaves the over-bake-vs-intrinsic fork *open pending a
  1-epoch ablation* — the image craft predicts the 1-epoch + clean-template adapter fixes C2 and C3
  respectively.

---

## 6. "Likeness vs flexibility" & style-vs-subject ⇒ "behavior LoRA vs knowledge LoRA"

**Image craft.** The doc separates **subject/character LoRAs** (learn a specific *thing*, "likeness")
from **style/concept LoRAs** (learn a *way of doing*, applied across subjects): LyCORIS/LoCon are
*"great for style and concept stuff"* and style LoRAs tolerate bigger ranks and larger noisy sets,
whereas characters need tighter curation (rentry.co/59xed3, 2023-08). The core tradeoff is
**likeness vs flexibility**: over-fit a subject and it stops being promptable (rigidity above).

**Video pushes this furthest — the single best structural analog in the field.** AnimateDiff
factorizes a *"plug-and-play motion module"* trained to learn *"transferable motion priors from
real-world videos"* that is **separate from the subject/style**, and **MotionLoRA** is *"a
lightweight fine-tuning technique ... [to] adapt to new motion patterns, such as different shot
types, at a low training and data collection cost"* (AnimateDiff, arXiv:2307.04725, 2023-07 / rev
2024-02) **[MEASURED in source]**. A MotionLoRA learns a *behavior over time* (how things move), not
*what* things are — and it composes with any subject LoRA from the same base.

**→ Text/agentic translation [INFERRED].**
- **Knowledge LoRA** ("subject/likeness") = memorizing *content*: APIs, a codebase, specific fixes.
  This is both (a) weaker for LoRA — *"LoRA substantially underperforms full finetuning"* in-domain
  on programming (Biderman, arXiv:2405.09673, 2024-05) **[MEASURED]** — and (b) the one that slides
  toward the **forbidden gold-diff bake** (§2). Avoid.
- **Behavior LoRA** ("style/motion") = our target: a *policy over the trajectory* — "once localized,
  **move** to the edit." Commitment is literally a **motion over the agent's turn sequence**, so
  MotionLoRA is the precise analog: train a small, separable, low-rank module that changes the
  *dynamics* (stop circling, advance to commit) while the base model keeps its "visual quality"
  (coding ability). This is the strongest theory-backed argument that the commitment adapter is a
  real, well-posed, in-genre LoRA — a *motion* LoRA for an agent.
- **Flexibility cost to respect:** just as an over-fit MotionLoRA forces the *same* camera move on
  every scene, an over-fit commitment LoRA risks forcing an edit even when the model *should* look
  more (premature wrong-fix, priors A7's dominant WRONG-FIX cell). The §4 anchor/replay data is the
  "keep it flexible" guard.

---

## 7. WHERE THE IMAGE ANALOGY BREAKS — do not over-transfer

Four breaks, ordered by how badly they bite us. **Break #1 is the single clearest place the analogy
fails.**

**Break #1 — The training objective (THE clean break). [ESTABLISHED]**
A diffusion LoRA optimizes a **denoising MSE**: the model predicts noise over the *whole latent at
once*, every pixel supervised in parallel, and errors are *local and graded* (a slightly-off pixel is
a slightly-worse image). Our adapter optimizes **autoregressive cross-entropy** over a *sequence*:
each token is conditioned on all prior tokens, errors **compound left-to-right**, and the output must
be **discretely valid** (a tool call either parses or it does not). There is no "slightly malformed
JSON that still mostly works." This is why v2's C3 is possible at all and has **no image analog**: a
single mis-serialized key (`old_string` → a lone backtick) makes the *entire* `edit_file` call
rejected, and because loss is sequential the model can lock onto that broken continuation and repeat
it. In images you cannot "accidentally turn a required field into a key." *Consequence:* the image
community's tolerance — *"more tolerant of a few low quality images than of a few bad tags"* — is
even *more* true for us, but the failure mode of a bad label is **catastrophic structural
corruption**, not a soft quality drop. Clean, parseable tool-call serialization in every training
example is non-negotiable in a way "clean images" never had to be.

**Break #2 — The unit of supervision: single frame vs multi-turn trajectory. [INFERRED]**
An image LoRA's training example is *one image → one caption*, i.i.d. Our example is a **multi-turn
agent trajectory**: tool call → environment response → next decision, where the "right" action
depends on *what the tools returned*, which is absent at training time unless the trajectory is
recorded faithfully. "Pose variety" partially maps (trajectory variety), but there is no image analog
to **the environment's response mid-example** or to **credit assignment across turns** (which turn
actually earned the resolve?). SFT on trajectories flattens this into next-token prediction and loses
the causal structure — a reason some argue the commitment problem is partly a **decoding/RL-shaped**
problem, not purely weights (consistent with priors §B leaving this fork open: `freq_penalty 0.4`
killed the repeat-loop at *decode* time).

**Break #3 — Strength knob at inference. [MEASURED asymmetry]**
Image users set LoRA **strength per generation** (`<lora:x:0.8>`) and even split Unet/TE strength to
diagnose over-bake live. We do **not** get a free per-request strength dial in the same way — vLLM
sets LoRA params from the submission (priors F), and the "strength sweep" diagnostic has to be done
at *train/scale* time (the 12B dose study, C4), not interactively. The elegant image debug loop
("sweep strength, pick the pre-burn checkpoint") becomes a **train-many-epochs-save-each + offline-
eval-each** loop for us (priors D's `eval_hf_adapter.py` is the stand-in for the XY-plot).

**Break #4 — No "negative prompt" channel. [INFERRED]**
Image craft leans on **negatives** ("tag it so you can put it in the negative"). SFT has no symmetric
negative channel — you cannot at inference say "edit_file:1.3, grep:-1.0." The nearest equivalents
are preference methods (DPO) or decode-time penalties (`freq_penalty`), not plain LoRA SFT. So the
on/off "difference learning" trick (§1) only partially transfers: we can supply positive commit-fast
trajectories, but "teach it what *not* to do" needs a different mechanism than a LoRA caption.

**Also note (not a break, a caveat that compounds):** our serving regime is **W4A16 INT4** and 4-bit
*"loses up to 59% on long-context tasks"* (arXiv:2505.20276, 2025-05) even though W4A16 is broadly
*"competitive"* (arXiv:2411.02355, 2024-11) **[MEASURED, priors A8]**. SWE trajectories are
long-context, so any adapter that eats context (high rank / many adapters) is doubly penalized here
in a way image LoRAs — short, fixed-size conditioning — never face. Keep the behavior adapter small.

---

## 8. IMAGE → TEXT TRANSLATION TABLE (the deliverable)

| # | Image/Video-LoRA principle (source) | Text/Agentic analog for the commitment LoRA | Label |
|---|---|---|---|
| T1 | "30–100 decent images"; "bad tags contaminate the model" (rentry 2023-08) | **20–50 clean passing commit-fast trajectories**; one malformed tool-call poisons the set | ESTABLISHED→INFERRED |
| T2 | LIMA: formats learned from ~1k curated examples (arXiv:2305.11206) | Small curated trajectory set teaches the *format/behavior* of committing | MEASURED |
| T3 | Learn by **difference**: on/off images (rentry 2023-08) | Contrast commit-fast vs over-search; but SFT lacks a true negative channel (Break #4) | ESTABLISHED (partial) |
| T4 | **Tag = variable, un-tag = baked** (rentry 2023-08) | Bug/repo/file stay in prompt (variable); **commit-fast motion is baked** | ESTABLISHED→INFERRED |
| T5 | Trigger/activation token, first & every file (rentry 2023-08) | Consistent **commit preamble** ("fault located; applying fix:") as behavior handle | INFERRED |
| T6 | Baking the "Superman logo" everywhere = concept bleed (rentry 2023-08) | Baking a gold diff / problem-statement fingerprint = **forbidden scorer-gaming** (priors E) | ESTABLISHED→MEASURED-constraint |
| T7 | `scaling = alpha/r`; alpha ≤ rank; alpha>rank "burns" (rentry 2023-08) | Same formula; `alpha/r=0.5` is **dampened, not amplified** — not v2's culprit (Raschka: 0.5 can be optimal) | ESTABLISHED/MEASURED |
| T8 | "err toward lower rank"; bigger r only for diverse sets (rentry 2023-08) | Low rank for a **narrow behavior**; also KV-cache + forget-less (arXiv:2405.09673) | ESTABLISHED/MEASURED |
| T9 | Multi-epoch "burns the Unet"; pick a pre-burn epoch (rentry 2023-08) | Multi-epoch **deteriorates instruction tuning** (Raschka 2023-11); v2's 4 epochs = over-bake (C4) | ESTABLISHED/MEASURED |
| T10 | **Regularization images** = anti-burn "screensaver" (rentry 2023-08) | **Replay/anchor trajectories** of normal correct tool use → prevents forgetting coding ability (arXiv:2308.08747; Raschka arithmetic-unlearning) | ESTABLISHED/MEASURED |
| T11 | **Deep-fry / burn** overfit | **Degenerate decoding / repeat-loop** → v2 C3's 11× malformed `edit_file` | MEASURED (C3) |
| T12 | **Limited / samey poses** overfit | **Behavioral collapse to one action** → v2 C2 search-death (0 edits) | MEASURED (C2) |
| T13 | "Lower strength to not ruin it = overfit" (rentry 2023-08) | 12B **dose-dependent** degen (≈0 at scale ≤0.5, severe at 1.0) (priors C4) | MEASURED (C4) |
| T14 | **Subject/likeness LoRA** vs **style/concept LoRA** (rentry 2023-08) | **Knowledge LoRA** (memorize fixes — weak + forbidden) vs **Behavior LoRA** (the target) | ESTABLISHED→INFERRED |
| T15 | **MotionLoRA**: adapt *motion patterns* as a separable module (arXiv:2307.04725) | **Commitment = a motion over the agent's turn sequence**; the precise genre for our adapter | MEASURED→INFERRED |
| T16 | Denoising MSE, parallel pixel supervision | **Autoregressive CE**, compounding sequential errors, discrete-valid tool calls — **the clean break** | ESTABLISHED (break) |
| T17 | One image = one i.i.d. example | **Multi-turn trajectory** with mid-example env responses + cross-turn credit assignment | INFERRED (break) |
| T18 | Per-generation **strength dial** + Unet/TE split for live debug | No free inference strength dial; sweep at **train/scale** via offline eval (priors D) | MEASURED asymmetry (break) |
| T19 | **Negative prompt** channel | No LoRA-SFT negative; needs DPO or decode penalties (`freq_penalty`) | INFERRED (break) |

---

## 9. What this says for the next MOVE (hypotheses, not verdicts — rules 6/11/13)

These are **falsifiable hypotheses for the FREE gate**, not conclusions:
- **H1 (template fix).** Re-serialize every `edit_file` training example as clean, separated
  `old_string`/`new_string` JSON (fix the fused-string template, §2/§5). Predict: eliminates C3
  key-collapse at fixed r/alpha. *This is the highest-value single change the craft points to.*
- **H2 (1 epoch).** Train the commitment set for **1 epoch**, not 4 (§4, C4). Predict: reduces C2
  search-death / samey-pose collapse. (The priors brief's own named open ablation.)
- **H3 (replay anchor).** Mix normal correct-tool-use trajectories as "regularization images" (§4,
  T10). Predict: preserves base coding ability; guards against premature wrong-fix (A7).
- **H4 (behavior framing).** Keep rank low and treat it as a MotionLoRA for commitment (§3, §6);
  do not scale rank to chase in-domain knowledge (Biderman: LoRA underperforms FT there anyway).
- **Caution (Break #2/#4 + priors §B).** The analogy itself warns commitment may be partly
  decode/RL-shaped; a LoRA-SFT behavior adapter has no negative channel. Hold the honest null open:
  if a clean-template, 1-epoch, replay-anchored behavior LoRA still does not beat the SACRED v6 @
  0.15 on a drift-passing gate, that is a RESULT (rule 3), and the decode-time lever (`freq_penalty`)
  remains the live alternative.

---

## Sources (URL + date accessed 2026; publication/update date noted)

1. "The Other LoRA Rentry" — SD LoRA training science & craft (dataset size, tagging/trigger tokens,
   rank/alpha scaling, regularization images, overfit/burn signatures, strength test).
   https://rentry.org/59xed3 (canonical https://rentry.co/59xed3), guide updated through 2023-08.
2. S. Raschka, "Practical Tips for Finetuning LLMs Using LoRA (Low-Rank Adaptation)."
   https://magazine.sebastianraschka.com/p/practical-tips-for-finetuning-llms , 2023-11-19.
   (alpha=2×r heuristic + 0.5-fold can win; multi-epoch deteriorates; all-layers; arithmetic
   unlearning / include-each-task.)
3. Hu et al., "LoRA: Low-Rank Adaptation of Large Language Models." arXiv:2106.09685, 2021-06-17.
   (ΔW=A·B, rank-deficiency, scaling.)
4. Dettmers et al., "QLoRA: Efficient Finetuning of Quantized LLMs." arXiv:2305.14314, 2023-05-23.
   (small high-quality dataset → SoTA; NF4.)
5. Zhou et al., "LIMA: Less Is More for Alignment." arXiv:2305.11206, 2023-05-18.
   (1k curated examples teach response formats; generalize to unseen tasks.)
6. Guo et al., "AnimateDiff / MotionLoRA." arXiv:2307.04725, 2023-07-10 (rev 2024-02-08).
   (plug-and-play motion module; MotionLoRA = lightweight behavior/motion adapter.)
7. Biderman et al., "LoRA Learns Less and Forgets Less." arXiv:2405.09673, 2024-05-15.
   (LoRA underperforms FT in-domain on code/math but forgets less; FT rank 10–100× LoRA.)
8. Luo et al., "An Empirical Study of Catastrophic Forgetting in LLMs During Continual Fine-tuning."
   arXiv:2308.08747, 2023-08-17. (CF across 1b–7b; instruction tuning mitigates.)
9. (Priors A8, verified) "Does quantization affect models' performance on long-context tasks?"
   arXiv:2505.20276, 2025-05-26. (4-bit can lose up to ~59% on long-context.)
10. (Priors A8, verified) "Give Me BF16 or Give Me Death? Accuracy-Performance Trade-Offs in LLM
    Quantization." arXiv:2411.02355, 2024-11-04. (W4A16 broadly competitive.)
