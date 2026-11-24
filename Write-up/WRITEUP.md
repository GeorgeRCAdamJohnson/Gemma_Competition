# Measure Before You Tune: Building and Auditing a Gemma 4 Coding Agent

*Gemma 4 Developer Agent competition (Kaggle), 2026-10-01 to 2026-12-02. Narrative draft v1, 2026-11-23.
Sources: `GEMMA_EXPERIMENT_LOG.md` (the dated record of every experiment), the project intel database
(`kb/attemptdb/`), and the figures in this folder. Items marked [AUTHOR] need the author's input.*

## Summary

We built single-agent coding agents on Gemma 4 for a benchmark where an agent reads a Python repository and an issue,
edits the code, and is scored by hidden tests on private repositories. Our 31B agent ("ca5") reached **0.20 on the
public leaderboard (12 of 58 tasks), rank 389 of 6,610 teams**. Our small-model agent (E4B with a repair-decisions
LoRA) is our entry for the $10K small-model prize: best draw **0.08, tied for 35th of 1,377 teams** (the 0.08 band covers
ranks 35-206), mean **4.0 of 58** over three draws. The small-model top is 0.12 (7 tasks), two tasks above our best draw.

The score is not the main result. What we can show is that we know *why* the agents succeed and fail, at the level
of individual attempts, and that we can tell a real improvement from noise:

1. **The leaderboard is a 58-task sample with truncated scores**, so byte-identical submissions of our best agent
   scored between 0.13 and 0.20. We worked out the denominator from the gaps in 3,712 team scores, and we sized
   every later experiment against that noise.
2. **We built a database of every agent attempt the project ran**: 17,601 unique attempts, 10,669 full traces,
   step- and tool-call-level detail, joined to GPU server logs, registrations and the experiment log. Every claim in
   this document can be re-derived from it.
3. **Both models fail the same way.** When our agents fail, they usually found the right file and wrote the wrong
   fix. The 31B reaches a file the reference fix touches in 74% of attempts but solves 37%. For E4B, "right file,
   wrong fix" is 55% of failures on the tasks it sometimes solves, and on several hard tasks it writes the *same*
   wrong fix every time.
4. **Nothing we or the public tried moves that number.** Across 32 measured E4B arms, no prompt, skill, budget or
   adapter changed where the agent edits or whether its fix is correct; arms only changed how much work the agent
   did. Re-running the four public 0.22 notebooks on our rig showed none of them beats ca5, and a trained public 31B
   adapter swapped one failure type for another without adding solves.

The rest of this document tells how we got there, including what did not work.

## 1. The task and its constraints

- **Agent format.** Declarative ADK YAML (agent, prompt, tools, sampling, per-task budget), optionally with LoRA
  adapters. No custom code runs in the scorer.
- **Scoring.** The scorer runs the agent sequentially over hidden tasks from private repositories on 4x L4 GPUs, with
  a 12-hour global limit. The public board scores 58 tasks; the private board, about 71 others.
- **Practice data.** 129 public tasks from 4 repositories (mostly `fastapi` and `rich`), with gold patches.
- **Budget.** One scored submission per day; weekly Kaggle GPU quota; Colab compute units bought separately.

Two facts shaped everything: the scored set is hidden and from different repositories, and each scored draw is
noisy. Practice-set results are hypotheses, and single leaderboard draws are weak evidence.

## 2. Phase 1: a fast start from written rules (10-01 to 10-03)

We did not start from zero. Each earlier competition left a lesson and some tooling, and we brought both:

- **The first idea is rarely the final one.** Across competitions we reused tools and adapters from earlier attempts
  instead of starting over, and expected to iterate past the first design.
- **Agent Attack** taught us not to rely on the public leaderboard, which is why we built a local testing framework
  before trusting any score.
- **Poker** extended that: we reverse-engineered the scorer and built our own tests and validators around it.
- **Biohub** is where we learned to train LoRAs and run work on Colab, and started building skills beyond our standard
  processes.
- **Across all of them:** trust your own measurements, and be persistent. Most of the useful results in this project
  came after a run of nulls.

From those we kept a working rule set: pre-register the success bar before each test, change one thing at a time,
treat any local score as a hypothesis, and log retractions next to the original claims.

The first agent resolved 0 of 6 tasks; the cause was four harness and loop bugs, not the method. A local
reproduction of the failure ("the agent explores until it runs out of budget") led to contract-anchored prompts and
**0.12 within three days**.

## 3. Phase 2: the 31B plateau and the first LoRA (10-03 to 10-12)

For ten days nothing beat 0.12 (board 0.08, 0.08, 0.10, 0.05). Every 31B iteration cost a Kaggle run, local proxies
were slow or a different model, and we attacked the diagnosis of the day ("the wall is commitment") with prompt rules
and a LoRA. The edit-discipline adapter made the agent worse and produced **our worst score, 0.05**. Our own
forensics later showed it trained the wrong target. The log's 31B adapter ledger closed eight such levers as negative,
with causes: adapters too strong for the data (rank 32 across 410 modules on ~46 examples), and fabricated training
trajectories that handed the model the target file.

## 4. Phase 3: small models make iteration cheap (10-12 onward)

When smaller Gemma 4 variants became legal, iteration speed changed: E4B ran at ~64 tok/s locally, and a Kaggle node
finished 129 tasks in ~75 minutes. A one-variable size ladder (31B 4/6, 12B 3/6, E4B 3/6, E2B 0/6) showed small models
were good enough to iterate on, not to replace the 31B. Board gains in this phase came from configuration:

| Version | Change | Board |
|---|---|---|
| v6w | budget recipe: 28 calls, 8 min, 80 turns | 0.15 |
| A3 | tool-call delimiter fix | 0.18 |
| **ca5** | anchor-grep rule before every edit, no sub-agents | **0.20** |

## 5. Measuring correctly

**The board denominator.** Only 14 distinct public scores existed across 3,712 teams. The unique fit is 58 tasks with
truncation (`floor(k/58*100)/100`), so one task is 0.017 and the 0.20 cluster is 12 tasks.

**The noise floor.** Byte-identical ca5 submissions scored 0.20, 0.18, 0.17, 0.17, 0.17 and 0.13: a spread of about 4
tasks on the same code. Today 615 teams share our 0.20 and 129 sit at 0.22; one task moves a team hundreds of places.

**Power.** On our 39-task practice cohort the per-round standard deviation is 1.47 tasks. Detecting +1.0 task per
round at t >= 2 needs about 9 rounds per arm; +0.5 needs 35. Our early 5-round A/Bs could only detect about +1.5,
so many early "nulls" said nothing about small real gains, and some early "wins" were noise.

**Scorer parity.** The scorer runs tasks one at a time; our rigs ran several at once, which slows each one (30 -> 23
tok/s per sequence at 4 in flight) and inflates timeouts. We later reproduced the scorer-like rig exactly: ca5 solved
32 of 85 live tasks on a Kaggle 4x L4 run and 32 of 85 on a single Colab G4 GPU a month later.

**What did not cause the variance.** Grading is deterministic: identical patches received identical grades in every
run but one. We also tested the suspicion that results degrade over long runs (server caching or state): solve rates
were flat by round number, by time since the inference server started (0 to 180+ minutes) and by prefix-cache hit
rate (which warms from 64% to 86% and then holds). The variance is the agent's sampling, not the infrastructure.

## 6. A practice win that did not transfer

E4B with a fresh-retry loop (fixer, verifier, deterministic gate) scored **11.5 vs 9.8 tasks per 39-task round
(t = 3.2)** on practice tasks. On the board it scored 0.01 and 0.06. The hidden repositories differ from the
practice ones (confirmed by the host), and small-model gains concentrated in a few practice tasks transferred worst
(board-to-practice ratio 0.2-0.33 for small models vs ~0.65 for the 31B). Lesson: practice A/Bs are necessary, not
sufficient, and gains tied to specific tasks are suspect.

## 7. The clock: the 31B's mechanical losses

About a quarter of 31B runs end mechanically, not on difficulty: 16% hit the 8-minute session limit and 8% overflow
the 32K context. We decomposed the timeouts: 3 of 19 were a single hung command, 16 of 19 were model time in long
deliberation turns (~10k characters before a command). A 6-task, 6-round A/B found a 10-minute cap recovered
time-bound tasks (19/36 vs 9/36, p = 0.03), and a regression check kept 18/18 always-solved tasks. On the board the
combined pack scored 0.15, 0.17 and 0.13, inside ca5's own spread, so we kept ca5.

## 8. An intelligence database for agent runs

By week seven the project held thousands of runs across Kaggle, Colab and local rigs, in a dozen formats. We built
`kb/attemptdb`:

- **Content.** 17,601 unique agent attempts (41,837 rows before deduplication), 10,669 traces decomposed into steps
  and tool calls (tool, arguments, file, command kind, latency, error, edit diff, whether the call touched a gold
  file), per-attempt behaviour features, inference-server metrics and errors joined to each attempt's GPU lane,
  agent bundles with diffs against the baseline, 34,000 crawled documents and all 2,600 experiment-log sections with
  full-text search.
- **Validation.** 27 checks re-derive previously recorded results (paired totals, per-round counts, bundle hashes,
  overflow errors matched to the right GPU lane in 306 of 306 cases) and run after every rebuild.
- **Use as a guard.** `q.py --prior "<idea>"` searches the log and documents before any idea is called new. It caught
  us twice in one afternoon proposing levers the project had already tested.

## 9. What the database showed

**Rounds are coin flips over the same small set of tasks.** Across 49 experiment arms the round-to-round spread
matches independent per-task coin flips, and it is the same ~15 "swing" tasks that decide every round.

**Where the first edit lands decides the attempt.** Comparing winners and losers *on the same task* (103 strata,
1,106 attempts): winners' first edit is on a gold file in 52 strata and losers' in 0 (p = 4e-16). The number of files
edited and the calls before the first edit do not differ. An earlier lead, "incomplete multi-site fixes", turned out
to be a between-task difficulty effect and was retracted.

**Failure-first, not success-first.** We had spent most of our effort studying what made solves happen. Re-centring on
failures was more productive:

| Swing tasks (17, E4B) | Share of failures |
|---|---|
| Right file, wrong fix | 55% |
| Wrong file (one "attractor" file per task) | 19% |
| Context overflow | 19% |
| No edit | 5% |

On 16 hard tasks E4B almost never solves, several fail the same way every time: on `rich_3718`, 62% of failures add
the same symptom patch, while the reference fix and the 31B reuse an existing variable at the point the issue names.
The audit also found a mislabelled task (`fastapi_14851`): 15 of 16 winners never touched the "gold" file, so its
"wrong file" failures were a label error and it was excluded.

**Our arms changed effort, not decisions.** A task-adjusted scan of 32 E4B arms found no arm that moved first-edit
location, right-file conversion or recurring wrong fixes. Arms moved calls, overflow and empty attempts. Differences
between experiment days were as large as any arm effect (the same unchanged control ranged from -1.8 to +4.8 points),
so we compare arms only against their own control.

**Small shifts, stacked.** Instead of discarding arms that missed a single-run threshold, we built a register of each
arm against its own control on six mechanism measures. One pattern pointed the right way in two independent
experiments (read discipline: fewer empty attempts, less overflow); one flipped from 5/6 good to 0/6 good on
replication. The register now decides which patterns go into the training data for our next adapter.

## 10. Auditing the public field

The board's top cluster (0.22-0.24) includes public notebooks, so we checked whether we were missing something. We
re-ran our ca5 and four public 0.22-lineage notebooks byte-for-byte on one server, paired on the 85 live tasks:

| Agent | Solved /85 | 8-min timeouts | Overflow |
|---|---|---|---|
| **ca5 (ours)** | **32** | 15 | 6 |
| denpugovkin (scored 0.22) | 30 | 4 | 17 |
| flexonafft v2 | 29 | 11 | 19 |
| bliverrigpdoge (40 calls) | 31 | 12 | 25 |
| ayush04barai prompt | 32 | 5 | 14 |
| ayush04barai prompt + trained adapter | 34 | 10 | 9 |

None beats ca5 beyond noise. Two settings line up with the two failure types: a longer per-command timeout with more
8-minute timeouts, a larger output-token cap with more overflow. ca5's 5,000-token cap gives the least overflow;
the public configs fixed timeouts and paid for it in overflow. The 0.22s are top draws from families whose own
reported ranges run 0.12-0.22, like our 0.13-0.20.

A dedicated two-round test of ca5 with the public trained adapter (61 vs 63 of 170, bar +4) failed. Its traces show
why: the same reasoning (about 7,000 tokens per attempt), 8% slower generation from serving the adapter, more edits
and fewer empty patches, and the same number of right-file-wrong-fix failures (67 vs 65). The adapter pushes editing;
it does not improve the fix.

## 11. Throughput and infrastructure

Running hundreds of experiments under daily submission limits needed reliable machinery:

- **Kaggle experiment runner** with pre-registration receipts, frozen inputs checked by hash, read-only resume that
  never re-launches, and automatic results tables. Output collection now downloads in parallel (~4x faster).
- **GPU sizing, validated before adoption.** 12 concurrent attempts per L4 lane instead of 8: 1.295x attempts per
  lane-hour with solve rates within the pre-registered -2.0 point line.
- **Colab pipeline** for the 31B on one 96 GB G4: model, environment (19 GB) and snapshots staged from Drive with size
  and header verification, prep in ~12 minutes, a CPU dry-run mode that checks every input before a GPU is
  allocated, and a live status file on Drive.
- **Repeat measurements** as a baseline: 1,700 attempts (17 swing tasks x 100) of the current E4B submission give
  per-task solve rates to within about +-10 points, the reference for evaluating the next adapter.

## 12. Where we are going

Fix correctness is the shared weakness and the lever nothing has moved. Our next step is a multi-pattern repair LoRA
trained on an independent public corpus (the benchmark tasks are held out), targeting right-file wrong-fix behaviour,
wrong-file attractors and read discipline, with patterns admitted only if they replicated. It is evaluated on held-out
cohorts with mechanism measures first (first-edit location, right-file conversion, recurring-wrong-fix share, overflow,
time per attempt), then solves. A synthetic length probe already showed a concrete limit: on one L4 the frozen trainer
runs out of memory at 4,668 supervised tokens, because it materialises full-vocabulary fp32 logits for every target
token at once (4.56 GiB); chunking the loss removes that limit.

## 13. Lessons

**What we would do again.** Written rules; pre-registered bars; one change per test; trace-level mechanism analysis
before declaring a result; logging retractions; validating infrastructure on GPU before adopting it.

**What we would do differently.**
- Measure the board's noise in week one, not week four.
- Build the attempt database early and study failures first.
- Size every A/B for the effect it can detect, and test mechanisms before solve rates.
- Check the project's own record before calling an idea new.
- Reproduce scorer conditions (one task at a time) before trusting timing results.

## 14. Limitations

Practice tasks come from four repositories and the scored tasks are private, so transfer is the open risk. Most
within-task analyses rest on 15-17 swing tasks. Board numbers are single noisy draws. Several log entries were later
corrected; the corrections are kept next to the originals.

## Appendix: key numbers

| Item | Value |
|---|---|
| Public board | 58 tasks, truncated; 6,610 teams; ours 0.20, rank 389 |
| ca5 identical-bytes board draws | 0.20, 0.18, 0.17, 0.17, 0.17, 0.13 |
| ca5 on the 85 live tasks (three runs) | 32, 32, 29 |
| E4B small-model entry (repair-decisions v1) | 0.05, 0.06, 0.08 (mean 4.0 / 58) |
| Database | 17,601 unique attempts; 10,669 traces; 27 validation checks |
| Practice-round noise | sd 1.47 tasks; ~9 rounds per arm to detect +1.0 |
| First-edit-on-gold, winners vs losers within task | 52 vs 0 strata, p = 4e-16 |
| 31B: reaches a gold file / solves | 74% / 37% |
| E4B swing failures: right file, wrong fix | 55% |
| Slots per L4 lane, 12 vs 8 | 1.295x throughput, solves within -2.0 points |
| Public 0.22 configs vs ca5 on our rig | none better; ca5 32 vs 29-32 |

Reproduction: `python kb/attemptdb/build.py; python kb/attemptdb/verify.py`, then the analysis scripts named in the
experiment log entries of 2026-11-21 to 2026-11-23 (`Outputs/_bt_*.py`, `_disc_*.py`, `_swing_dossier.py`,
`_arm_mechanisms.py`, `_direction_register.py`, `_degradation*.py`, `_lb022_interim.py`, `_ca5lora_summary.py`).
