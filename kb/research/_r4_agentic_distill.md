# R4 — Agentic / Tool-Use / Trajectory Distillation

> READ-ONLY web research for the "what do we train into a thin LoRA so a FIXED
> `gemma-4-31b-it-qat-w4a16-ct` commits an edit instead of exploring to budget death" question.
> Scope: rejection-sampling SFT / STaR / "distill your own passing trajectories" (the host-blessed
> recipe); how trajectory/format QUALITY drives tool-call reliability; a mechanistic account of the
> v2 serialization key-collapse bug; whether "commit early, stop exploring" is an SFT-trainable trait;
> and a concrete safe trajectory/template shape that avoids the v2 bug.
>
> Every nontrivial claim is cited (URL + date). Paraphrase only, inline attribution. Labels:
> **MEASURED** (our local evidence, from `_priors_brief.md`), **ESTABLISHED** (published / documented),
> **INFERRED** (my reasoning across the two).

---

## 0. The three MEASURED local facts this research is built on (do not contradict)

- **MEASURED (A1/A7, C2):** the binding failure is COMMITMENT, not localization. The model locates
  the gold file, then explores (grep/read/pytest) until the 15-call budget dies without calling
  `edit_file`. In the v2 forensic, 3 of 5 tasks made 0 edit attempts and shipped empty patches.
  (`_priors_brief.md` §A1, §A7, §C2.)
- **MEASURED (C3):** v2's `edit_file` tool calls key-collapsed — the model serialized the dual-string
  payload so `new_string`'s value ran into the literal text `` `,old_string: ``, and the string that
  should have been `old_string` became a JSON *key* with value a lone backtick. 11+ of 16 calls were
  rejected for "mandatory input parameters are not present: old_string." `run_command` (single-string)
  was NOT corrupted. (`_priors_brief.md` §C3.)
- **MEASURED (E, host-blessed):** the legitimate data recipe is "run the agent on PUBLIC GitHub issues
  and keep ONLY test-passing trajectories — self-distill passing trajectories." No gold-patch staging,
  no problem-statement fingerprinting, no task-id conditioning. (`_priors_brief.md` §E.)

Everything below reinterprets these with cited theory. It never overrides them.

---

## 1. Rejection-sampling SFT / STaR / "distill your own passing trajectories"

### 1.1 The host-blessed recipe IS a named, published method (several names, one idea)

The recipe in §E — generate with the model, keep only verifier-passing outputs, fine-tune on those,
repeat — is the well-established **rejection-sampling fine-tuning / self-training-with-a-verifier**
family. The canonical citations:

- **STaR (Self-Taught Reasoner), Zelikman et al., 2022-03-28, arXiv:2203.14465.** The loop is, in
  their words, generate rationales for many questions, keep the ones that reach the correct answer,
  fine-tune on the correct-yielding rationales, and repeat; the paper states STaR "lets a model
  improve itself by learning from its own generated reasoning." **ESTABLISHED.**
  (https://arxiv.org/abs/2203.14465, 2022-03-28.)

- **ReST^EM / "Beyond Human Data", Singh et al., 2023-12-11 (rev 2024-04-18), arXiv:2312.06585.**
  Formalizes the loop as expectation-maximization: (1) sample from the model and filter with binary
  feedback, (2) fine-tune on the kept samples, (3) repeat. They report it "scales favorably with model
  size and significantly surpasses fine-tuning only on human data" on MATH and the APPS *coding*
  benchmark — i.e. the method is proven where correctness is machine-verifiable, exactly our
  pytest-pass signal. **ESTABLISHED.** (https://arxiv.org/abs/2312.06585, 2023-12-11.)

- **Llama 2, Touvron et al., 2023-07-18, arXiv:2307.09288.** Productionized "rejection sampling
  fine-tuning": sample K outputs, score them, keep the best, and SFT on the kept set as a distinct
  stage. **ESTABLISHED.** (https://arxiv.org/abs/2307.09288, 2023-07-18.)

- **Toolformer, Schick et al., 2023-02-09, arXiv:2302.04761.** The same filter-then-train idea applied
  specifically to TOOL CALLS: the model inserts candidate API calls, and only calls that *reduce
  loss on future tokens* (a self-supervised utility filter) are kept for training. Precedent that
  "keep only the tool calls that actually helped" is a trainable signal. **ESTABLISHED.**
  (https://arxiv.org/abs/2302.04761, 2023-02-09.)

### 1.2 The method is proven on OUR exact task shape (SWE agents), not just math

- **SWE-Gym, Pan et al., 2024-12-30 (rev 2025-06-06), arXiv:2412.21139, ICML 2025.** Trains open-weight
  SWE agents on real Python task instances (codebase + runtime + unit tests + NL task) and reports "up
  to 19% absolute gains in resolve rate" on SWE-Bench Verified/Lite, and a new open-weight SOTA when
  combined with a verifier trained on sampled agent trajectories. This is the direct precedent for
  our setup: self-sampled, test-filtered SWE trajectories → measurable resolve-rate gain.
  **ESTABLISHED.** (https://arxiv.org/abs/2412.21139, 2024-12-30.)

- **FireAct, Chen et al., 2023-10-09, arXiv:2310.05915.** Fine-tuning a backbone on *agent
  trajectories* (not just answers) "consistently improved" the agent; fine-tuning Llama2-7B on 500
  GPT-4 trajectories gave a 77% HotpotQA increase, and *more diverse* fine-tuning data (multiple tasks
  / prompting methods) improved it further. Precedent that trajectory diversity, not volume, carries
  the gain — relevant to our tiny-dataset regime. **ESTABLISHED.**
  (https://arxiv.org/abs/2310.05915, 2023-10-09.)

**INFERRED for us:** the host-blessed recipe is not a workaround — it is the state-of-the-art training
signal for exactly this task class, and it is the ONLY recipe that is simultaneously (a) permitted by
§E and (b) immune to the "no provenance check" scorer-gaming trap, because a test-passing trajectory
is a *behavior* the model generated, not a memorized gold diff. The verifier (hidden pytest's public
analogue: our own run of the public repo's tests) is the external judge the accountability rules demand.

---

## 2. How trajectory / format QUALITY drives tool-call reliability

### 2.1 Format is LEARNED from a handful of examples — which cuts both ways

- **LIMA, Zhou et al., 2023-05-18, arXiv:2305.11206.** 1,000 curated examples were enough for the model
  to reliably reproduce "specific response formats"; the paper's thesis is that alignment largely
  *surfaces* formats/behaviors already latent from pretraining and "only limited instruction tuning
  data is necessary." **ESTABLISHED.** (https://arxiv.org/abs/2305.11206, 2023-05-18.)

**INFERRED (the double edge):** if ~1k (or, in our v2 case, ~23) examples are enough to *install* a
format, they are equally enough to *install a malformed one*. A tiny dataset whose tool-call
serialization is subtly wrong will teach the wrong serialization with high fidelity and little
averaging-out — which is precisely the v2 outcome (§3). LIMA's lesson is that at small N, **format
correctness of every single example is load-bearing**, not optional polish.

### 2.2 Reliable tool-use SFT depends on the trajectory being valid, executable, and verifier-filtered

- **ToolLLM / ToolBench, Qin et al., 2023-07-31 (rev 2023-10-03), arXiv:2307.16789.** Builds tool-use
  SFT data by annotating a *valid solution path* (a chain of real API calls) per instruction and
  training on those paths; the resulting ToolLLaMA generalizes to unseen APIs. The quality lever is
  that each trajectory is a *working* call sequence, not a plausible-looking one. **ESTABLISHED.**
  (https://arxiv.org/abs/2307.16789, 2023-07-31.)

**INFERRED:** "quality" for our purposes is operationalized as: (1) every tool call in the kept
trajectory actually executed without a parse/arg error, (2) the trajectory ended in pytest-pass, and
(3) the call is serialized in the model's *native* wire format (§3). (1) and (3) are what v2 violated.

---

## 3. WHY a training-data TEMPLATE SHAPE corrupts tool-call serialization — the v2 bug, mechanistically

### 3.1 Gemma 4's native tool-call wire format is NOT plain JSON

From Google's own "Function calling with Gemma 4" page (Google AI for Developers, last updated
2025-03-21, retrieved 2026-10-14): when a structured `tool_calls` message is rendered by the chat
template, the on-the-wire string is control-token delimited, roughly:

`<|tool_call|>call:get_current_temperature{location:<|"|>London<|"|>}<tool_call|>`

Key structural facts from that page:
- The call opens/closes with the reserved tokens `<|tool_call|>` ... `<tool_call|>`.
- Arguments are rendered as `key:value` pairs inside `{ }`, comma-separated.
- **STRING values are wrapped in a reserved quote token `<|"|>` ... `<|"|>`**, not in ASCII `"`.
- Tool DECLARATIONS use a parallel `<|tool|>declaration:...` block, and tool RESULTS use
  `response:name{...}`.
- The page's own parser pulls keys with the regex `(\w+):` and values as either the `<|"|>`-wrapped
  span OR everything up to the next comma/`}` (`[^,}]*`).
(https://ai.google.dev/gemma/docs/capabilities/function-calling, 2025-03-21.)

The structured input side is governed by the HF/Transformers tool-use contract: the tool call must
live in the assistant message's `tool_calls` key as a **dict** whose `arguments` is itself a dict, and
the docs explicitly warn that passing a JSON *string* (OpenAI-style) "may cause errors or strange
model behavior" because Transformers expects a dict. (HF Transformers "Tool use", `main`, retrieved
2026-10-14: https://huggingface.co/docs/transformers/main/en/chat_extras.)

Gemma's formatting page adds the governing invariant: you may use any control-token schema when you
fine-tune, "as long as it's consistent between your training and inference use cases." (Gemma
"Formatting and system instructions", last updated 2025-03-21:
https://ai.google.dev/gemma/docs/core/prompt-structure.)

### 3.2 The mechanism of the v2 key-collapse (one-paragraph account)

**INFERRED (consistent with MEASURED §C3 and the two docs above):** The v2 training examples
serialized the `edit_file` call's two strings (`old_string`, `new_string`) as a single hand-written /
JSON-ish blob instead of letting Gemma's chat template emit each argument as a *separate* key:value
pair inside the native `{ }` with each string value wrapped in the reserved `<|"|>` token. Because the
`edit_file` payload is the only *dual-string* argument in the toolset, the two long, newline- and
backtick-bearing values sat adjacent in the template with a mis-placed or missing value-delimiter
between them. The model learned that exact byte pattern. At inference it reproduced it: it emitted
`new_string`'s value, then — instead of a clean argument boundary — the literal characters
`` `,old_string: ``, so the fragment `old_string:` landed in *key position* of the `key:value` grammar
and captured a lone backtick as its value, while the real `old_string` content never got a key. The
harness/parser then reports "mandatory input parameters are not present: old_string," which is exactly
what §C3 observed, repeated 11+ times (a degenerate repeat-loop). It is specific to `edit_file` and
spares `run_command` precisely because only `edit_file` has two string values whose boundary the
mis-template collapsed; a single-string call has no interior boundary to corrupt. The alpha/r = 0.5
scale amplified the memorized malformed pattern rather than causing it. (MEASURED §C3; mechanism per
Gemma function-calling grammar 2025-03-21 and HF dict-vs-string warning, retrieved 2026-10-14.)

In one line: **the template taught the model to write the argument *separator* as data, so the parser
re-tokenized a value as a key — a serialization-grammar violation installed by a mis-shaped example,
not a reasoning failure.**

### 3.3 Why "4-bit + long context + alpha/r=0.5" makes it worse, not the cause

- **ESTABLISHED:** 4-bit weight quantization is broadly "competitive" (arXiv:2411.02355) but loses
  heavily on *long-context* tasks (arXiv:2505.20276) — both already in `_priors_brief.md` §A8. SWE is
  long-context, so the model is already operating in its most fragile regime when it must emit a
  precise long structured call. **INFERRED:** quantization narrows the margin for a correct
  serialization; a mis-templated adapter pushes it over the edge. Quantization is an *amplifier*, the
  template shape is the *cause*.

---

## 4. Is "commit early / stop exploring" an SFT-trainable trait? (precedent)

### 4.1 The failure has a named, measured published analogue

- **"The Danger of Overthinking", Cuadron et al., 2025-02-12, arXiv:2502.08235.** On SWE-Bench
  Verified, over 4,018 analyzed trajectories, they name three recurring patterns — **Analysis
  Paralysis, Rogue Actions, Premature Disengagement** — and find higher "overthinking" (favoring
  internal reasoning / exploration over environment interaction) correlates with LOWER resolve rate.
  Critically: *selecting* the lower-overthinking trajectory improved performance "by almost 30% while
  reducing computational costs by 43%." They suggest native function-calling and selective RL to
  mitigate it. **ESTABLISHED.** (https://arxiv.org/abs/2502.08235, 2025-02-12.)

**INFERRED:** our "exploration death / grep-death" (MEASURED A1) is literally Analysis Paralysis in a
15-call budget. This is strong external precedent that (a) the trait is real and measurable, (b) it is
*separable from capability* — the same model has both good and overthinking trajectories, so a
*selection* over trajectories can isolate the committed ones, and (c) the fix lever they endorse is
trajectory selection + light RL, not a bigger model.

### 4.2 Trait = a behavior carried by trajectory shape, which SFT demonstrably installs

Combine the chain: SWE-Gym (§1.2) proves SWE *resolve behavior* is SFT-transferable from trajectories;
FireAct (§1.2) proves *trajectory style* transfers and that diversity of style matters; Overthinking
(§4.1) proves commit-vs-explore is a measurable, selectable trajectory property. **INFERRED:** "commit
to an edit fast, stop searching" is therefore an SFT-trainable trait IF the training set is composed of
trajectories that EXHIBIT early commitment (short locate → edit → verify) and EXCLUDE the long
explore-then-die ones. The trait is installed by the *distribution of trajectory shapes you keep*, not
by any instruction text — which also matches MEASURED A4 (the prompt channel is exhausted for
commitment, so the lever must be in the weights/data).

### 4.3 The selection filter that targets commitment (not just correctness)

**INFERRED, from §1 + §4.1:** standard rejection sampling keeps *correct* trajectories. For our trait
we want a *two-key* filter: keep a trajectory only if (1) it ends in pytest-pass AND (2) it reaches its
first successful `edit_file` within a small call budget (e.g. ≤ k calls) with few redundant
read/grep/pytest cycles (an overthinking-score proxy à la 2502.08235). This biases the kept set toward
early-commit behavior and is still 100% behavior-distilled (no gold-patch staging), so it stays inside
§E.

---

## 5. The SAFE trajectory / template prescription (what avoids the v2 key-collapse)

Concrete, defensible shape. Each rule ties to a cited mechanism.

1. **Never hand-serialize tool calls. Build structured messages and let the chat template render
   them.** Represent every assistant tool call as
   `{"role":"assistant","tool_calls":[{"type":"function","function":{"name":"edit_file",
   "arguments":{"path":..., "old_string":..., "new_string":...}}}]}` with `arguments` as a **dict**,
   and apply the model's own `apply_chat_template(..., tools=...)`. Do NOT put a JSON *string* in
   `arguments`. (HF warns dict-vs-string mismatch "may cause errors or strange model behavior":
   https://huggingface.co/docs/transformers/main/en/chat_extras, retrieved 2026-10-14.) This structurally
   removes the possibility of the two strings running together, because the template emits each
   argument as its own `key:<|"|>value<|"|>` pair with a template-owned separator. (Gemma grammar:
   https://ai.google.dev/gemma/docs/capabilities/function-calling, 2025-03-21.)

2. **Train with the SAME template/tokenizer used at inference — byte-identical.** Gemma's own rule:
   the control-token schema must be "consistent between your training and inference use cases."
   (https://ai.google.dev/gemma/docs/core/prompt-structure, 2025-03-21.) Serve-time wire format
   (vLLM's Gemma-4 parser + the reserved `<|tool_call|>`, `<|"|>` tokens) MUST equal the
   `apply_chat_template` output used to build labels. A dev/eval template mismatch here is the
   foundation-level drift the accountability rules were written to catch.

3. **Round-trip-validate every training row before it enters the set.** For each serialized assistant
   turn, run the model's own parser (the `extract_tool_calls` regex shipped on the Gemma page,
   `<\|tool_call\|>call:(\w+)\{(.*?)\}`, keys via `(\w+):`) and assert it round-trips back to the
   original `{name, arguments}` dict with `old_string` and `new_string` BOTH present and byte-equal.
   Drop (or fix) any row that does not round-trip. This is a mechanical gate that would have caught v2
   before training. (Parser per https://ai.google.dev/gemma/docs/capabilities/function-calling,
   2025-03-21.)

4. **Protect strings that contain the delimiter characters.** `edit_file` values legitimately contain
   newlines, commas, braces, and backticks — the exact characters the `key:value`/`[^,}]*` grammar
   treats as boundaries. Ensure such values are always emitted inside the `<|"|>` quote-token span (so
   the parser takes the quoted branch, not the "up to next comma/brace" branch). Add explicit
   round-trip tests whose `old_string`/`new_string` deliberately contain `,`, `}`, backtick and `\n`.
   (Grammar branches per the Gemma parser regex, 2025-03-21.)

5. **Mask loss to assistant/tool-call tokens only — and verify the mask is nonzero.** Use TRL's
   `assistant_only_loss=True` (or `completion_only_loss` for prompt-completion data). TRL builds the
   assistant mask from the chat template's `{% generation %}` region, so the template MUST mark
   assistant turns or the mask is empty. (TRL `SFTTrainer` docs, `main`, retrieved 2026-10-14:
   https://huggingface.co/docs/trl/main/en/sft_trainer — "Train on assistant messages only … loss is
   computed only on the assistant responses.") This directly addresses `_priors_brief.md` §D's noted
   loss-masking bug (an all-masked run gave mean_loss 0.0000). Assert mean_loss > 0 and that the masked
   token count matches the assistant-turn token count on a sample before a full run.

6. **Keep examples few, diverse, and every one format-correct.** LIMA (2023-05-18) and FireAct
   (2023-10-09) both say diversity + per-example correctness beats volume; at N≈tens, a single
   malformed row is a large fraction of signal. Prefer a handful of *verified-passing, early-commit,
   round-trip-valid* trajectories over many unchecked ones.
   (https://arxiv.org/abs/2305.11206; https://arxiv.org/abs/2310.05915.)

7. **Keep the adapter small / low-scale.** v2's degradation emerged dose-dependently with adapter
   scale (MEASURED §C4: degen≈0 at serve-scale ≤0.5, severe at 1.0), and LoRA "learns less and forgets
   less" at low rank — it is the safer regime for not overwriting the base model's already-working
   serialization. (LoRA Learns Less and Forgets Less, Biderman et al., 2024-05-15, arXiv:2405.09673.)
   A correctly-templated, round-trip-validated, assistant-masked dataset is the primary fix; low scale
   is the amplifier-side safety margin, consistent with the §F budget constraint (small/low-rank
   adapters preserve KV-cache).

---

## 6. Uncertainty ledger

- **MEASURED (local, from `_priors_brief.md`):** the commitment-not-localization failure (A1, A7); the
  v2 key-collapse signature and its `edit_file`-only specificity (C3); dose-dependent degradation with
  adapter scale (C4); the host-blessed self-distill recipe and the §E forbidden list; the loss-masking
  bug (D); the long-context quantization caveat (A8).
- **ESTABLISHED (published/documented):** STaR, ReST^EM, Llama-2 rejection sampling, Toolformer (§1);
  SWE-Gym 19% absolute SWE gain, FireAct trajectory SFT + diversity (§1.2); LIMA format-from-few (§2.1);
  ToolLLM valid-solution-path training (§2.2); Gemma 4 native tool-call grammar and the
  consistency rule (§3.1, 3.2); HF dict-vs-string warning (§3.1); overthinking patterns + selection
  gain on SWE-Bench (§4.1); TRL assistant-only loss mechanics (§5.5); LoRA-learns-less (§5.7).
- **INFERRED (my cross-reasoning, labeled in text):** that the v2 bug is a mis-shaped-example
  serialization-grammar violation amplified (not caused) by scale/quantization (§3.2–3.3); that
  "commit early" is SFT-trainable via a trajectory-shape filter (§4.2–4.3); the specific round-trip /
  masking / delimiter-protection prescription (§5). These are hypotheses to be judged by the FREE gate
  and then the leaderboard — NOT verdicts. No training was run here (read-only task).

---

## Sources (URL + date retrieved/published)

1. STaR: Bootstrapping Reasoning With Reasoning — arXiv:2203.14465, 2022-03-28. https://arxiv.org/abs/2203.14465
2. Beyond Human Data (ReST^EM) — arXiv:2312.06585, 2023-12-11 (rev 2024-04-18). https://arxiv.org/abs/2312.06585
3. Llama 2 — arXiv:2307.09288, 2023-07-18 (rejection-sampling fine-tuning). https://arxiv.org/abs/2307.09288
4. Toolformer — arXiv:2302.04761, 2023-02-09. https://arxiv.org/abs/2302.04761
5. SWE-Gym — arXiv:2412.21139, 2024-12-30 (rev 2025-06-06), ICML 2025. https://arxiv.org/abs/2412.21139
6. FireAct — arXiv:2310.05915, 2023-10-09. https://arxiv.org/abs/2310.05915
7. LIMA: Less Is More for Alignment — arXiv:2305.11206, 2023-05-18. https://arxiv.org/abs/2305.11206
8. ToolLLM — arXiv:2307.16789, 2023-07-31 (rev 2023-10-03). https://arxiv.org/abs/2307.16789
9. The Danger of Overthinking — arXiv:2502.08235, 2025-02-12. https://arxiv.org/abs/2502.08235
10. LoRA Learns Less and Forgets Less — arXiv:2405.09673, 2024-05-15 (rev 2024-09-20). https://arxiv.org/abs/2405.09673
11. Gemma — Function calling with Gemma 4 (native tool-call grammar + parser) — Google AI for Developers, last updated 2025-03-21, retrieved 2026-10-14. https://ai.google.dev/gemma/docs/capabilities/function-calling
12. Gemma — Formatting and system instructions (control-token consistency rule; no system role) — last updated 2025-03-21, retrieved 2026-10-14. https://ai.google.dev/gemma/docs/core/prompt-structure
13. HF Transformers — Tool use (tool_calls dict contract; dict-vs-JSON-string warning) — `main`, retrieved 2026-10-14. https://huggingface.co/docs/transformers/main/en/chat_extras
14. HF Transformers — Chat templating (apply_chat_template, generation-prompt) — `main`, retrieved 2026-10-14. https://huggingface.co/docs/transformers/main/en/chat_templating
15. TRL — SFTTrainer (assistant_only_loss / completion_only_loss; mask built from chat template) — `main`, retrieved 2026-10-14. https://huggingface.co/docs/trl/main/en/sft_trainer

> NOTE: items 11–15 are living docs; versions/dates are as retrieved 2026-10-14. The arXiv dates are
> submission/revision dates. Also referenced from `_priors_brief.md` §A8: arXiv:2411.02355 (4-bit
> competitive) and arXiv:2505.20276 (4-bit long-context loss).
