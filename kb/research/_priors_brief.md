# LoRA Research — Measured Local Priors Brief

> READ-ONLY ground truth for the downstream "what do we train into a LoRA to make a FIXED
> gemma-4-31b-it-qat-w4a16-ct improve on agentic Python bug-fixing scored by hidden pytest?"
> deep-research effort. Every claim below is quoted-faithful from a local file with a citation.
> Research branches and the final dossier MUST NOT contradict section (A) without raw evidence.
> GPU access and adapter-loading are SOLVED (user has Colab, has trained a LoRA, has proven
> train->load->eval). Do not re-litigate them.

---

## (A) MEASURED LOCAL FACTS the research must not contradict without raw evidence

**A1. The binding failure is COMMITMENT, not localization, not edit-anchors.**
The model FINDS the right file (localization "SOLVED" at v17) then fails to COMMIT an edit — it
explores (grep/read/pytest) until the budget dies without ever calling `edit_file`. This
"exploration death / grep-death / search-death" is the single recurring failure, proven across
EXPERIMENT 4 bug #3 (rich_4077 = 0 patch), v8 (6/6 sample, still 1 resolve), v17, v18, and the v2
LoRA forensic (3/5 tasks made 0 edit attempts). Instruction: do NOT re-diagnose this as a
localization or anchor problem.
*Source: `Gemma/GEMMA_EXPERIMENT_LOG.md`, standing-truth block, item #1 (≈lines 12-19).*

**A2. The edit-ANCHOR skill is a NON-problem (the harness already forgives it).**
`edit_file` auto-unescapes `\n` (strategy `"unescaped"`) and uses a 3-tier exact/flexible/regex
matcher, so byte-faithful `old_string` is largely TOLERATED. The v2 "edit-discipline" LoRA trained
this non-problem → NULL. In the v2 forensic, 1 of 17 edit calls was a true anchor-mismatch, and it
was self-corrected on the next call; the harness forgave it anyway.
*Source: `Gemma/GEMMA_EXPERIMENT_LOG.md`, standing-truth item #2 (≈lines 20-23); corroborated by
`Gemma/V2_ADAPTER_FORENSICS.md` §1 and §2 failure-class counts.*

**A3. "The v2 LoRA is the WRONG LoRA, not proof the LoRA path is wrong."**
It trained edit-anchor discipline; it SHOULD train COMMITMENT (commit-to-edit-fast, stop
searching). A commitment-targeted LoRA is the open, non-rerun lever.
*Source: `Gemma/GEMMA_EXPERIMENT_LOG.md`, standing-truth item #3 (≈lines 24-26).*

**A4. The prompt channel is EXHAUSTED for commitment.**
v1–v20 + v19v3 (~20 configs) tried budget tuning, edit-early, reserve-tail, anti-loop,
commit-to-path-first; localization improved, commitment did NOT durably. Twice confirmed that ADDING
prompt text DEGRADES this model (v20 wholesale rewrite and v19v3 incremental add both tipped tasks
back into search-death/repeat-loop) — the prompt context is SATURATED. This is WHY the effort moved
to weights (LoRA); re-running a prompt commitment lever is a re-run.
*Source: `Gemma/GEMMA_EXPERIMENT_LOG.md`, standing-truth item #5 (≈lines 30-32) and the v19v3
"FINDING 1" / "prompt channel EXHAUSTED" decision (≈lines 5822-5838).*

**A5. Live-best = v6 @ 0.15 (SACRED), adapter-free, prompt-only.**
The current baseline is v6w @ 0.15 (submission 57098497, from `curated/submissions.csv`). The LOG
block still says "v6 @ 0.12" and is flagged STALE; KB_SUMMARY resolves in favour of 0.15. Either
way: confirmed distinct fixes ever = 2, both rich (rich_4077 + rich_4079); ZERO fastapi ever
resolved; NO adapter has beaten 1/5 on the 5-task rich sample. The public LB field is frozen at
~0.12 across ~124 teams.
*Source: `Gemma/kb/KB_SUMMARY.md` baseline line + §7; `Gemma/GEMMA_EXPERIMENT_LOG.md` standing-truth
item #4 (≈lines 27-30) and setup lines (≈lines 56-57). The 0.12-vs-0.15 conflict is a known STALE-doc
issue — use 0.15.*

**A6. The public leaderboard top is adapter-FREE.**
The LB-topping reference kernels (verra 0.18 / honghanh 0.24 / lavinwins) are a single 31b agent with
NO LoRA (28 calls / 8 min / 80 turns / thinking_budget 4096). The adapter-free win lever on the
actual board is sampling + budget. The LoRA finding so far is a cautionary negative, framed as a
method/measurement contribution — NOT "the way to win."
*Source: `Gemma/PAPER_FINDING1_DRAFT.md`, SCOPE NOTE (top of file).*

**A7. Measured failure distribution (traced rich rows).**
Task×run cell counts: `?=64, F=15, I=4, L=31, R=55, S=4, W=63` (W = wrong-fix, R = resolved,
L = locate-only, F = found-not-landed). Furthest-stage histogram (traced): None=24,
READ_GOLD_FILE=7, RESOLVED=45, SAW_GOLD_HUNK=4, SCORED_NONEMPTY=64, TRIED_APPLY=14,
WROTE_GOLD_CHANGE=1. So WRONG-FIX and locate-without-landing dominate; commitment/search-death is the
recurring null that these aggregates reflect (many SCORED_NONEMPTY / locate rows that never resolve).
*Source: `Gemma/kb/KB_SUMMARY.md` §3 and §10.*

**A8. Quantization caveat (the fixed serving regime bites via context).**
W4A16 is "competitive" generally (arXiv 2411.02355) BUT 4-bit loses up to 59% on LONG-CONTEXT tasks
(arXiv 2505.20276). SWE is long-context, so quantization likely bites via context length — relevant
to any decision that trades context budget for adapters.
*Source: `Gemma/GEMMA_EXPERIMENT_LOG.md`, setup/quantization note (≈lines 68-69).*

---

## (B) THE PIVOTAL QUESTION (restated)

Is "commit-to-edit-fast / stop-searching" a **LoRA-shaped (weights-level) behavior problem**, or a
**prompt/decoding-shaped problem**?

Context that frames the fork:
- The prompt channel is declared EXHAUSTED for commitment (A4): prompt edits improved localization
  but never durably fixed commitment, and extra prompt load actively regresses the model. That pushes
  the problem toward weights.
- BUT decoding levers showed signal: at the config/decode level, `freq_penalty 0.4` KILLED the
  repeat-until-death loop (max_repeat ≤2 on every task) and a get_status reserve-tail + edit-SHAPE
  "KILLED search-death: every task now REACHES an edit" — i.e. two of four v19 levers did exactly
  what they were designed to at DECODE time (non-decaying), where prompts decay.
  *Source: `Gemma/GEMMA_EXPERIMENT_LOG.md` ≈lines 5104-5107 (decode-time framing) and ≈lines
  5723-5727 (freq_penalty + reserve-tail results).*
- The research must decide whether a COMMITMENT LoRA adds anything a tuned decoder + the SACRED
  prompt does not already deliver, OR whether weights are the only durable channel left. Treat this
  as the hypothesis the deep research must resolve, not a settled fact.

---

## (C) THE v2 FAILURE SIGNATURES (stated precisely)

The v2 adapter = v19-LoRA-v2 "edit-discipline" QLoRA, all-linear, **r=32, lora_alpha=16, effective
alpha/r=0.5**, evaluated on the FREE 5-task rich gate (`v2_gate_s05c`) vs the no-adapter v6 baseline
on the same tasks. Researchers may argue whether these are overfit / format-collapse artifacts vs a
training-data-shape bug — the raw signatures are:

**C1. REGRESSION.** Adapter scored **1/5** (rich_4077 only) vs v6's **2/5** (rich_4077 + rich_4079)
on the shared tasks. No task the adapter resolved that v6 did not; no sub-step observably better.
Every delta is neutral or negative. The one resolve (rich_4077) happened IN SPITE of the adapter —
v6 resolves it the same easy way, and the adapter's edit only applied because the tool auto-unescaped
a literal-`\n` old_string.
*Source: `Gemma/V2_ADAPTER_FORENSICS.md` §1, §2 per-task table, §3a.*

**C2. SEARCH-DEATH.** 3 of 5 tasks (rich_4079, rich_4076, rich_3469) made **0 `edit_file`
attempts** and submitted empty patches (patch_size 0), burning the 15-call budget on
grep/pytest/read_file. On rich_4079 the adapter reached the SAME file v6 edits but never edited it —
a strict regression vs v6, which lands a correct edit and resolves.
*Source: `Gemma/V2_ADAPTER_FORENSICS.md` §2, §3c, §3d.*

**C3. SERIALIZATION KEY-COLLAPSE (malformed tool-call).** rich_4070 made 16 `edit_file` calls,
**11+ identically malformed**: the model serialized the call so `new_string`'s value ends with the
literal characters `` `,old_string: `` and the string that should have been `old_string` became a
JSON KEY with value a lone backtick `` ` ``. Every one was rejected with "mandatory input parameters
are not present: old_string." A REPEAT-LOOP of the same broken serialization. Corruption is specific
to `edit_file`'s dual-string payload — `run_command` serialization is NOT corrupted. The forensic
attributes this (labeled an inference) to the TRAINING-DATA TEMPLATE SHAPE (edit examples serialized
so the two strings run together), amplified at alpha/r=0.5.
*Source: `Gemma/V2_ADAPTER_FORENSICS.md` §1 item 2, §3b, §5; `Gemma/GEMMA_EXPERIMENT_LOG.md`
standing-truth item #3 (≈lines 24-26).*

**C4. Over-training context (from the paper draft).** All v2/original degradation was measured on
4-EPOCH adapters; the real r32 edit-discipline run drove loss 0.9068 → 0.4270 → 0.2621 over 3 epochs
on only 23 examples (overfit risk explicitly noted). A separate 12B measurement showed tool-call
ARGUMENT COLLAPSE under greedy decode that is DOSE-dependent in adapter scale (degen≈0 at
serve-scale ≤0.5, emerges at 0.75, severe at 1.0). So degradation may be an over-training / over-scale
artifact, not intrinsic — this is the open fork the paper draft refuses to resolve pre-data.
*Source: `Gemma/PAPER_FINDING1_DRAFT.md` (shared facts #4, Framing A/B); `Gemma/GEMMA_EXPERIMENT_LOG.md`
training record (≈lines 5853-5860).*

---

## (D) EXISTING TRAINING MACHINERY + how local offline eval is run

What EXISTS (documented, not audited):

- **`Gemma/train/smoke_qlora.py`** — scaffold test proving the full QLoRA loop runs on the local
  Blackwell box: loads `google/gemma-4-E2B-it` with on-the-fly 4-bit NF4, attaches a tiny rank-8 LoRA
  (r=8, alpha=16, q/v text-decoder only, towers excluded), runs real optimizer steps, saves. E2B is
  the cheap dev base; same recipe scales to the 31B ship base.
- **`Gemma/train/train_lora.py`** — resumable QLoRA trainer (checkpoint+resume per epoch via
  `progress.json`; never retrains from scratch). Defaults BASE `gemma-4-E2B-it`, MAXLEN, LORA_R=16,
  LORA_ALPHA=32, overridable by `--base/--maxlen/--r/--alpha`. v2 widened targets q/v-only →
  ALL-LINEAR (q/k/v/o + mlp gate/up/down on the text decoder, vision/audio excluded). Carries a fixed
  loss-masking bug: now unmasks ALL assistant turns (the first run was a NULL at mean_loss 0.0000
  because loss was masked to the last turn only + maxlen truncation).
- **`Gemma/train/build_localization_trajectories.py`** — builds `{"messages":[user,assistant]}`
  trajectory training data teaching the LOCALIZATION ACTION (symptom → emit the grep/read that lands
  on the gold file), TRAIN split only (holdout unseen). Derives the grep query ONLY from tokens
  visible in the symptom — explicitly NO gold-patch leakage (rule 8); drops un-derivable examples.
- **`Gemma/train/eval_hf_adapter.py`** — the LOCAL OFFLINE EVAL path: proves train → load adapter →
  run the agent loop → score, all in-process via HuggingFace (no server, no GGUF). Monkeypatches
  `run_local.chat()` to generate from a HF Gemma-4 base (optionally + LoRA via `PeftModel`), parses
  Gemma-4 tool-calls (`gemma4_toolparse`) into the OpenAI shape the harness expects. Run as
  `python eval_hf_adapter.py --task rich_4077 [--adapter <path>]`. Explicit caveat: E2B is weak at
  tool-calling, so a no-resolve result is ACCEPTABLE — this path tests PLUMBING, and local 12b/E2B is
  a weaker localizer than the 31b, so use local to rank changes directionally; a local *win* is a
  strong positive, a local miss on a 31b-localizable task is expected.

Real-adapter facts already banked:
- The real r32 edit-discipline adapter = 167MB safetensors + config, r=32 alpha=64, 110 q/v modules,
  43.8M params, uploaded as Kaggle dataset `comfyops/gemma-edit-discipline-r32`. Train->load->eval is
  PROVEN (A100-80GB Colab, gemma-4-31b-it bf16 base, public/no-token).
- Host-confirmed: training the adapter off-Kaggle (Colab/local) is ALLOWED; vLLM now sets LoRA params
  dynamically from the submission.
*Source: the four scripts above (headers/docstrings read); `Gemma/GEMMA_EXPERIMENT_LOG.md` training
record (≈lines 5853-5862) and LoRA/training intel + host block (≈lines 909-932).*

---

## (E) SCORER-GAMING FORBIDDEN LIST

The harness scores a task SOLELY on whether the produced `git diff` applies cleanly and the hidden
pytest passes — there is NO provenance check. That makes the following shortcuts possible and
therefore FORBIDDEN (they inflate only the public split and collapse on the private rescoring):

- **No gold patches.** Do not ship, stage, or emit the publicly-derivable gold source diff for the
  exposed public repos (rich / fastapi / requests / httpx), and do not bake them into the adapter or
  its training data.
- **No problem-statement fingerprints.** Do not build or ship a
  `fingerprint(problem_statement) → gold_diff` map or any mechanism that recognizes a task from its
  problem-statement text / repo name / file tree and emits a memorized answer.
- **No task-id / dev-answer conditioning.** `instance_id` is not in the prompt; do not condition the
  adapter or its data on task identity, and do not memorize or submit the 127 dev answers. The public
  tasks are training FUEL (structure → generalizable priors, metadata STRIPPED at inference), NOT
  answers to submit. Every localization/LoRA result must pass the by-task, metadata-stripped holdout.

Legitimate alternative (host-blessed): run the agent on PUBLIC GitHub issues and keep ONLY
test-passing trajectories — self-distill passing trajectories.
*Source: `Gemma/VULN_PUBLIC_TASK_PATCH_STAGING.md` §1-§4, §6; `Gemma/GEMMA_EXPERIMENT_LOG.md`
commitment/holdout note (≈lines 3138-3142) and host training intel (≈lines 931-932).*

---

## (F) HARD CONSTRAINTS (the fixed surface the research must respect)

- **Model is FIXED:** `gemma-4-31b-it-qat-w4a16-ct`, W4A16 INT4, served via vLLM, 4×L4, **32k ctx**.
  Not trainable; only prompts/skills + a thin LoRA/PEFT adapter are tunable.
- **Adapter budget:** **≤8 adapters, rank ≤128, <3GiB total.**
- **KV-cache coupling:** vLLM sets LoRA params dynamically from what you submit; FEWER adapters +
  LOWER rank (or none) = MORE KV-cache. A big high-rank LoRA is doubly bad (eats context + risk).
  Keep adapters SMALL / LOW-RANK.
- **Submission form:** declarative-YAML only (no arbitrary Python); the tunable surface is thin
  LoRA + prompts/skills.
- **Budget regime that produced results:** ~0.15 budget config family; the adapter-free LB top ran
  28 calls / 8 min / 80 turns / thinking_budget 4096.
- **1 scored submission/day.** Live-best (v6w @ 0.15) is never overwritten without a verified beat on
  a trustworthy judge; the FREE gate comes first.
*Source: `Gemma/GEMMA_EXPERIMENT_LOG.md` setup line (≈lines 54-56), host KV-cache block (≈lines
909-911), LoRA intel (≈lines 927-932); `Gemma/kb/KB_SUMMARY.md` baseline/§7.*

---

## Uncertainty ledger (what is measured vs assumed)

- MEASURED: A1-A7 outcomes, the v2 forensic signatures (C1-C3), the training/eval machinery (D), the
  harness scoring mechanics (E), the constraints (F).
- ASSUMED / INFERRED (labeled as such in-source): that the serialization key-collapse (C3) comes from
  the training-data template shape (forensic inference, not measured against the training set); that
  search-death reflects a convergence regression (inferred from behavior); the over-training-vs-
  intrinsic fork (C4) is UNRESOLVED pending a 1-epoch ablation.
- STALE/CONFLICTING: the log says live-best "v6 @ 0.12"; KB_SUMMARY + submissions.csv say v6w @ 0.15.
  Use 0.15.
