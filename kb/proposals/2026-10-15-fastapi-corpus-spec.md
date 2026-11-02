# FastAPI as the primary training corpus — spec (2026-10-15)

Origin: user direction — *"we've been attacking Rich but are the fastapi issues easier to train off and
have less randomness?"*

Status: SPEC. Nothing built, nothing trained, no GPU spent, no scored slot spent.

---

## 0. What we have actually measured (all from files on disk, no GPU)

| | rich | fastapi |
|---|---|---|
| public tasks | 48 (37%) | **66 (52%)** |
| traced runs | 201 | 29 |
| resolved runs | 58 (29%) | **0 (0%)** |
| statement chars, median | 138 | **676** |
| statement chars, mean | 486 | **1112** |
| statements < 100 chars | 20/48 (**42%**) | 3/66 (**5%**) |
| `target_named_in_issue` | 7/48 (15%) | 12/66 (18%) |
| multi-file gold | 11/48 (23%) | 23/66 (35%) |
| gold `n_edits`, median | 2 | 2 |
| tasks with >=3 traced runs | 17 | 5 |
| per-task resolve rate, mean | 0.24 | **0.00** |
| deterministic tasks (rate >=0.8 or <=0.2) | 15/17 (88%) | **5/5 (100%)** |
| coin-flip tasks (0.3 < rate < 0.7) | **0/17** | **0/5** |

Two facts dominate and they point in opposite directions:

1. **fastapi statements carry ~5x more information.** Median 676 vs 138 chars; only 5% are terse vs 42%.
   For any task where the input is the issue text, that is a large difference in learnable signal.
2. **fastapi has never resolved.** 0 of 29 traced runs. Its 100% determinism is deterministic FAILURE,
   not stability. There is no positive agent behaviour to imitate.

**The reframe that matters:** for a ROUTER we do not need successful agent runs. We need
`(statement -> gold path)` pairs, and the gold path is derivable for all 66 fastapi tasks from the gold
patch + test_patch. So fastapi is the *better* label source even though it is the worse *agent*.

**And the board is majority fastapi.** 66 of 129 public tasks (52%) vs rich 48 (37%). We have been
optimising the smaller, terser, noisier slice.

---

## 1. FastAPI headroom classification (NO GPU, ~1 hour)

`train/build_router_labels.py` currently filters to rich only. Change the filter and re-run the same
four-way classification (`never_committed` / `path_wrong` / `path_right_content_wrong` / `unreachable`)
over the 29 traced fastapi rows.

**Why this is first:** it tells us whether fastapi's 0% is a routing failure (addressable), a synthesis
failure (not addressable by a router), or a commitment failure (the 8-refuted-lever problem). We are
currently guessing, and the guess determines whether fastapi is worth any effort at all.

**Pre-registered bar:** if fastapi failures are dominated by `path_right_content_wrong`, fastapi is a
synthesis problem and better statements do not help — stop.

## 2. Statement informativeness -> path inferability (NO GPU, ~2 hours)

For all 114 labelled tasks, measure how much of the gold path is *inferable from the statement alone*:
- does the statement name the target file? the target symbol? a symbol in the same module?
- statement length bucketed against "target inferable" rate
- the same cut by repo

**This is the test the log explicitly flagged as never run** (~L8864: *"statements under 100 chars went
0/4; statements of 450+ chars went 5/7 ... NOT tested on the other 36 rich tasks"*). Step 1 of the router
spec already supplied the mechanism for rich (all three routing failures had 71-75 char statements).
This extends it across both repos and turns a post-hoc hunch into a measured feature.

**Pre-registered bar:** if statement length/informativeness does not predict path inferability in BOTH
repos, the feature is rich-specific and not a general lever.

## 3. Domain-shift check (NO GPU, ~1 hour)

A router trained on fastapi statements must serve rich statements too. Measure:
- feature distributions (length, target_named, symptom_class, n_files) per repo — how far apart are they?
- if we train on fastapi and validate on rich (and vice versa), does path-match survive?

**Pre-registered bar:** cross-repo path-match must beat the trivial baseline in BOTH directions. If it
only works within-repo, the router is a per-repo lookup and generalises to nothing.

## 4. Only then: decide the corpus (decision, no GPU)

Pick the training corpus on evidence:
- fastapi-only, rich-only, or mixed
- and record WHY, with the numbers from steps 1-3

---

## Risks

| risk | severity | mitigation |
|---|---|---|
| fastapi 0% means no positive agent behaviour to imitate | HIGH | router labels come from GOLD, not from agent runs — this is why fastapi is viable for a router and was not viable for the commitment LoRA |
| domain shift fastapi -> rich | MEDIUM | step 3 cross-repo validation, both directions |
| better statements may simply mean easier TASKS, not more signal | MEDIUM | step 2 measures inferability of the PATH, not task difficulty |
| forbidden bake | DISQUALIFYING | route on shape/features, never instance identity; by-task holdout |
| fastapi tasks are bigger (35% multi-file, statements to 10k chars) | MEDIUM | cap statement length in training; measure whether truncation hurts path-match |

## Not in scope

- No training until steps 1-3 report.
- No scored submission. v6w @ 0.15 live-best, never overwritten without a verified beat.
- No autonomous tuning loop.
