# V3 "Commitment" LoRA — Adversarial Pressure Test (READ-ONLY, pre-GPU)

**Question under test:** Can a v3 LoRA trained by SFT on our own past *successful* agent
trajectories teach the gemma-4-31b agent to COMMIT (localize → `edit_file` → `submit_patch`)
instead of exploring until the ~15-call budget dies ("search-death")? Is building it worth GPU,
or dead on arrival?

**Method:** Parsed every `results/traces/*.json` (ATIF-v1.7) under `Gemma/`. For each trajectory
I counted ordered tool calls and their observation status. **Committed** is defined per the brief
and tightened: `(a)` ≥1 `edit_file` call whose observation `status ∈ {ok, success}` **AND**
`(b)` a `submit_patch` whose observation reports `status=ok` with non-zero `patch_size`/`files_changed`.
All counts below are **measured** from traces. Where I state resolution (tests passed) vs commitment
(patch submitted) I say which — the traces record *patch submission*, not hermetic-pytest resolution,
so resolution is taken from the brief / `GEMMA_EXPERIMENT_LOG.md`, labeled as such.

---

## BOTTOM LINE: 🔴 RED → do NOT train v3 as a from-our-trajectories commitment SFT LoRA

The honest-null answer. The counts do not support it, and three of the five attacks land hard:

- **18 committed trajectories, but only ~10 distinct tasks, and the diversity is an illusion of
  volume** (Attack 1 + 2). Half the "signal" is the same two free tasks repeated across runs.
- **Every clean, few-call, low-difficulty commit is on a task we already resolve for free**
  (rich_4077 = "proxy isatty", 1-line). The genuinely hard commits (fastapi_14487 at 40 calls /
  31 before first edit) are long, idiosyncratic, and few (Attack 3).
- **Commitment is already explicitly prompt-driven** in every committed trace — "EDIT EARLY, DON'T
  EXPLORE", "COMMIT TO A PATH FIRST", "the moment `tool_calls_remaining <= 4`: STOP ... APPLY YOUR
  EDIT". An adapter trained on outputs those prompts produced is largely redundant with the prompt
  (Attack 5).
- Prior art agrees: the v2 adapter (46 examples) was a documented **NULL** and introduced a
  tool-call serialization pathology (`GEMMA_EXPERIMENT_LOG.md` L21–L26). 18 committed trajectories
  is the *same order of magnitude* — we would be repeating the overfit-on-a-handful mistake.

Attack 4 is the one green light: matched committed/search-death pairs **do** exist for 4 tasks, so
*contrastive/preference* data is available. That changes the recommendation only at the margin (see
"If you train anyway").

---

## (1) Which run folders actually contain `results/traces/*.json`

The brief named several `Outputs/vXX` folders; most are **empty stub folders** — the real v10 data
lives in `_v10_kaggle_pull`. Measured:

| Run folder | Has `results/traces/`? | # trace JSON | Notes |
|---|---|---:|---|
| `_v6out` | yes | 6 | v6 live-best, **prompt-only, NO adapter** (resolved 2/6: rich_4077, rich_4079) |
| `_v10_kaggle_pull` | yes | 10 | v10 pull (brief says resolved 2/10) |
| `v2_gate_s05c` | yes | 5 | **v2 adapter** contrast run (3/5 search-death) |
| `v2_gate_out` | yes | 5 | v2 adapter run |
| `v2_gate_out2` | yes | 5 | v2 adapter run — **all 5 traces have 0 tool calls** (dead/empty run) |
| `Outputs/v18` | yes | 5 | v18 |
| `Outputs/v19` | yes | 5 | v19 |
| `Outputs/v19v3` | yes | 5 | v19v3 |
| `Outputs/v19_lora` | yes | 5 | v19 + lora |
| `Outputs/v9_2, v10, v11, v12_v2, v13, v13_v2, v14, v15, v16` | **no** | 0 | empty stub folders, no traces |

**Total trace files analyzed: 51** (46 with ≥1 tool call; `v2_gate_out2`'s 5 are empty).

---

## (2) Committed-trajectory count — per run and per task

**Measured committed trajectories: 18** (edit_file-ok AND non-empty submit_patch).

Per run:

| Run | Committed trajectories |
|---|---:|
| `_v6out` | 4 (fastapi_15588, rich_4070, rich_4077, rich_4079) |
| `_v10_kaggle_pull` | 5 (fastapi_14356, fastapi_14485, fastapi_14487, requests_7315, requests_7502) |
| `v2_gate_s05c` | 1 (rich_4077) |
| `v2_gate_out` | 2 (rich_4076, rich_4077) |
| `Outputs/v19` | 2 (rich_4070, rich_4077) |
| `Outputs/v19v3` | 3 (rich_4070, rich_4076, rich_4077) |
| `Outputs/v19_lora` | 1 (rich_4077) |
| `Outputs/v18`, `v2_gate_out2` | 0 |

Per task (how many runs committed it):

| Task | # committed traces | Repo |
|---|---:|---|
| rich_4077 (`proxy isatty`) | **6** | rich |
| rich_4070 (`perf: defer imports`) | 3 | rich |
| rich_4076 (`preserve newlines`) | 2 | rich |
| fastapi_14356 | 1 | fastapi |
| fastapi_14485 | 1 | fastapi |
| fastapi_14487 | 1 | fastapi |
| fastapi_15588 | 1 | fastapi |
| requests_7315 | 1 | requests |
| requests_7502 | 1 | requests |
| rich_4079 (`inline table`) | 1 | rich |

**Verdict for Attack 1 (SAMPLE SIZE): closer to ~6 than to dozens.** 18 raw rows, but after
de-duplicating the same task repeated across runs it is **10 distinct tasks**, and ~1/3 of the raw
rows are a single trivial task (rich_4077 ×6). A 244M-param adapter trained on effectively ~10
distinct positive examples is in the **same overfit-prone regime** that already produced the v2 NULL
(46 examples). This is a measured count, and it fails the "needs more than a handful" bar.

---

## (3) Distinct-task coverage (Attack 2 — circularity / held-out)

**Distinct tasks with ≥1 committed trajectory: 10**
`fastapi_14356, fastapi_14485, fastapi_14487, fastapi_15588, requests_7315, requests_7502,
rich_4070, rich_4076, rich_4077, rich_4079`.

Circularity check against the "free" set (tasks v6 prompt-only already resolves: **rich_4077,
rich_4079**):

- The **most-committed** task by far is rich_4077 (6 of 18 rows) — a task we already pass for free.
- rich_4079 (also free) contributes 1 row.
- So **7 of 18 committed rows (39%) are on the two tasks we already resolve without any adapter.**
- The remaining diversity (fastapi ×4 distinct, requests ×2 distinct, rich_4070/4076) is **real**
  and is the only thing keeping this from being a pure RED on circularity alone — but each of those
  is a **single** trajectory (n=1 per task), so there is no within-task redundancy to learn a robust
  pattern from.

**Verdict for Attack 2:** Not "almost entirely rich_4077/4079" — there is genuine cross-repo
coverage. But the volume is top-heavy on the free task, and the non-free tasks are n=1 each. Coverage
is **broad but paper-thin**: 10 tasks, 6 of them represented by exactly one trajectory.

---

## (4) Difficulty classification per committed task (Attack 3 — attribution)

Columns: calls = total tool calls in the trajectory; 1stEdit = call index of the first *successful*
`edit_file`. "Localization burden" ≈ how many calls were spent before the model committed.

| Committed trace (run/task) | total calls | 1st edit-ok @ | patch size | class |
|---|---:|---:|---:|---|
| `_v6out`/rich_4077 | 16 | 14 | 396 | **EASY** (1-line `proxy isatty`; late but tiny) |
| `v2_gate_out`/rich_4077 | 7 | 5 | 396 | **EASY** (near-linear, 7 calls total) |
| `v2_gate_s05c`/rich_4077 | 17 | 15 | 324 | EASY task, late commit |
| `Outputs/v19`/rich_4077 | 14 | 9 | 324 | EASY |
| `Outputs/v19v3`/rich_4077 | 13 | 6 | 324 | EASY |
| `Outputs/v19_lora`/rich_4077 | 15 | 11 | 324 | EASY |
| `_v6out`/rich_4079 | 22 | 20 | 562 | borderline (committed on the 20th call) |
| `_v6out`/rich_4070 | 23 | 3 | 2223 | NON-TRIVIAL fix, but **fast** commit (3rd call) |
| `Outputs/v19`/rich_4070 | 20 | 3 | 1047 | NON-TRIVIAL, fast commit |
| `Outputs/v19v3`/rich_4070 | 23 | 4 | 1428 | NON-TRIVIAL, fast commit |
| `v2_gate_out`/rich_4076 | 17 | 15 | 473 | medium, very late commit |
| `Outputs/v19v3`/rich_4076 | 20 | 15 | 552 | medium, very late commit |
| `_v6out`/fastapi_15588 | 16 | 11 | 1513 | **NON-TRIVIAL** (SSE field validation) |
| `_v10`/fastapi_14356 | 18 | 14 | 3192 | NON-TRIVIAL (extra non-body param parsing) |
| `_v10`/fastapi_14485 | 27 | 24 | 1096 | **NON-TRIVIAL** (`TYPE_CHECKING` annotations; 24 calls to commit) |
| `_v10`/fastapi_14487 | 40 | 31 | 8719 | **HARD** (docs/validation re-raise; 31 calls, 8.7KB patch) |
| `_v10`/requests_7315 | 18 | 4 | 1395 | NON-TRIVIAL, fast commit (preserve leading slashes) |
| `_v10`/requests_7502 | 29 | 18 | 1513 | **NON-TRIVIAL** (`__getattr__` file wrappers; 18 calls to commit) |

**Verdict for Attack 3:** NOT every commit is on an EASY task — fastapi_14487 (31 calls before
commit), fastapi_14485 (24), requests_7502 (18) are genuine "commitment under difficulty" examples.
**But:** (a) the EASY/free rich_4077 dominates by count; (b) the hard examples are each **n=1**, very
long, and highly task-specific (an 8.7KB fastapi docs patch is not a transferable "commit fast"
pattern); (c) several "fast commit" NON-TRIVIAL cases (rich_4070, requests_7315) committed at call
3–4, which is the *prompt's* "AT MOST 3-4 calls then edit" rule firing — i.e. the behavior is already
produced by the prompt, not latent in need of a weight. There is a thin, non-trivial signal, but it
is too sparse and too heterogeneous to SFT into a 244M adapter without overfitting to specific tasks.

---

## (5) Matched committed / search-death pairs (Attack 4 — contrast data)

"Search-death" = trajectory with **zero** successful `edit_file` (explored then died). Tasks that
have BOTH ≥1 committed trace AND ≥1 search-death trace (so a contrastive pair on the *same* task is
constructible):

| Task | committed in | search-death in | pair? |
|---|---|---|---|
| rich_4077 | _v6out, v2_gate_s05c, v2_gate_out, v19, v19v3, v19_lora | _v10, v2_gate_out2, v18 | ✅ |
| rich_4070 | _v6out, v19, v19v3 | v2_gate_out, v2_gate_out2, v18, v19_lora | ✅ |
| rich_4076 | v2_gate_out, v19v3 | _v6out, _v10, v2_gate_s05c, v2_gate_out2, v18, v19, v19_lora | ✅ |
| rich_4079 | _v6out | v2_gate_s05c, v2_gate_out, v2_gate_out2, v18, v19, v19v3, v19_lora | ✅ |

**4 tasks with matched pairs** (all `rich`; `v2_gate_out2`'s empties excluded as degenerate). The
fastapi/requests committed tasks have **no matched search-death** in this corpus (they were only run
in `_v10`), so no same-task contrast there.

**Verdict for Attack 4:** Contrastive/preference data **is** possible, but only on 4 rich tasks, one
of which (rich_4077) is the trivial free task. This is the single argument *for* training — if you
train, do **preference (DPO-style) on these matched pairs**, not SFT on positives alone, because the
positive-only set is what overfit in v2.

---

## (6) Prompt confound — commitment is already instructed (Attack 5)

Three **distinct** system prompts appear across the committed traces, **all prompt-only / the
committed outputs were produced under explicit commitment instructions.** Verbatim lines (quoted
short, ≤30 words each, for compliance):

**Prompt A (`_v6out`, ~22-call budget):**
> "The one rule that matters: EDIT EARLY, DON'T EXPLORE."
> "Spend AT MOST 3-4 tool calls locating the bug, then MAKE YOUR EDIT."

**Prompt B (`_v10_kaggle_pull`, ~40-call budget):**
> "After 2 searches that return nothing useful, STOP searching." … "make your best edit"
> "Every call you save on searching is a call you can spend making or correcting the fix."

**Prompt C (`v2_gate_s05c` / v2-era, ~15-call budget, FREE get_status):**
> "STEP 0 — COMMIT TO A PATH FIRST, IN WRITING, BEFORE ANY TOOL CALL."
> "THE MOMENT `tool_calls_remaining <= 4`: STOP all searching/reading and APPLY YOUR EDIT THIS TURN."
> "commit, confirm, edit." / "A landed edit on your committed TARGET beats a perfect plan you never apply."

**Verdict for Attack 5:** Commitment in the positive trajectories is **plausibly prompt-driven**.
The fast-commit cases (edit at call 3–4) line up exactly with "AT MOST 3-4 tool calls then edit." An
adapter trained to reproduce these outputs would largely re-encode behavior the prompt already elicits
— **redundant with the prompt**, and the prompt channel is already documented as EXHAUSTED for
*durable* commitment (`GEMMA_EXPERIMENT_LOG.md` L30–L32). Training weights to imitate prompt-induced
outputs does not obviously add anything the prompt doesn't, and risks the v2 serialization pathology.

---

## Measured vs inferred (per accountability rules)

- **Measured from traces:** all trajectory/edit/submit/call counts; the 18 committed count; the 10
  distinct tasks; the matched-pair structure; the three prompt texts; difficulty call-indices.
- **Inferred / from external docs (labeled):** that "committed" ≈ "resolved" — it does **not**;
  traces record patch submission, not pytest pass. Resolution counts (v6 2/6, v10 2/10, v2 3/5
  search-death) come from the brief and `GEMMA_EXPERIMENT_LOG.md`, not re-derived here.
- **Prior art (context, not verdict):** low-resource LoRA SFT is prone to catastrophic overfitting /
  model collapse ([PMC comparative study](https://pmc.ncbi.nlm.nih.gov/articles/PMC12705377/));
  conversely, small open-weight LMs *can* learn specific behaviors data-efficiently via fine-tuning
  on targeted data as an alternative to prompting
  ([arXiv 2507.04889](https://arxiv.org/html/2507.04889v1)) — the image-LoRA "style/behavior transfers
  with few examples" parallel. These inform, they do not decide; the counts decide. *Content was
  rephrased for compliance with licensing restrictions.*

---

## Recommendation (only what the counts support)

**Do NOT spend GPU on v3 as "SFT on our own successful trajectories to teach commitment."** It fails
sample size (effectively ~10 distinct positives, 6 of them n=1), fails circularity-weighting (the
dominant positive is the free rich_4077), and is confounded by prompts that already instruct exactly
the commit behavior. This is the same overfit-on-a-handful setup that already made the v2 adapter a
NULL.

**If a weight-level lever is still wanted, the only count-supported path is narrow:**
1. **Preference, not SFT-on-positives.** Use the **4 matched committed/search-death pairs** (Attack 4)
   as DPO/ORPO preference data (committed = chosen, search-death = rejected on the *same* task). This
   is the only part of the corpus with contrast, and it directly targets the behavior.
2. **Do not expect transfer from 4 rich pairs** — pre-register that this is a *mechanism probe*, not a
   leaderboard move, and judge it on a held-out task the pairs never touched (e.g. a fastapi task),
   not on rich_4077/4079.
3. **First exhaust the cheaper, already-available lever:** the measured fast-commit cases prove the
   *prompt* (Prompt C's `get_status ≤4 → APPLY EDIT`) can force commitment on some tasks for **zero
   GPU**. Before any adapter, quantify how far Prompt C alone gets on the search-death tasks — if it
   closes them, v3 is moot.

**Honest null restated:** the data to teach "commitment under difficulty" by imitation does not exist
in sufficient, diverse, non-confounded quantity. 🔴 RED.
