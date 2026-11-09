# Paper outline - Gemma 4 Developer Agent (working draft)

Sources: `GEMMA_EXPERIMENT_LOG.md` (cited as L<line>), `Write-up/_chronology_notes.md`, `PAPER_FINDING1_DRAFT.md`,
`Outputs/FORUM_ANALYSIS_20261108.md` (cited as [topic id]). Figures are in this folder (`Fig N` = file below).
Items marked **[AUTHOR]** need your input; items marked **[GAP]** are claims the log does not yet support.

---

## Working titles
1. *Measure Before You Tune: What 30 Submissions Taught Us About Building Coding Agents on Gemma 4*
2. *Noise, Transfer, and the Clock: An Honest Account of a Kaggle Coding-Agent Competition*
3. *Small Models, Big Variance: Iterating on Consumer Hardware for an Agentic SWE Benchmark*

## One-paragraph abstract (draft)
We report a six-week effort to build a Gemma-4 coding agent for Kaggle's Developer Agent competition (Python
repo + issue -> patch, scored by hidden pytest). Carrying discipline from earlier competitions (pre-registered
bars, one change per test, distrust of local scorers), we reached 0.12 within three days, then stalled for ten
days while working only with the 31B model, where every iteration cost a Kaggle run and LoRA fine-tuning made
the agent worse (board 0.05). The release of smaller Gemma-4 variants let us iterate locally and on Kaggle at
far higher throughput; a budget recipe and a delimiter fix moved us to 0.20. Our main contributions are
methodological: (1) the public leaderboard has 58 tasks with truncated scores, so identical submissions vary by
2-3 tasks (0.13-0.20 for byte-identical bytes); (2) gains measured on the public practice set transfer poorly to
the hidden repositories, worst for small models (board/practice ratio 0.2-0.33 vs 0.65 for 31B); (3) the
31B's dominant loss is the per-task clock, driven by a few very long model turns, and a 10-minute cap recovers
time-bound tasks (19/36 vs 9/36, p=0.03) at no total-runtime cost. We document our retractions alongside our
results.

---

## 1. Introduction
- Task, model and scoring constraints (L37-49): declarative ADK YAML only; 4xL4; 32k context; 1 scored
  submission/day; 12 h global limit; per-task caps in `eval_config.yaml`.
- Why this is hard to optimise: the scored set is hidden and from different repositories [topics 744951, 747248,
  host-confirmed]; the public board is 58 tasks (L12905); one submission per day (L18210).
- Contributions (bullet the four from the abstract).
- **Fig 10** (phase timeline) as the opening figure: it tells the whole story at a glance.

## 2. Starting point: design and lessons carried from earlier competitions
Narrative: we did not start from zero; we started from a written rule set.
- **Biohub (cell tracking)** - the main imported discipline (L3-7, L37-49, L2126):
  - a local scorer can be anti-correlated with the leaderboard -> a local number is a hypothesis;
  - pre-register the success bar before each probe;
  - change one thing per test;
  - "model the deviation": the bug is the deviation from the pattern its neighbours imply (also the
    poker "negative-space" insight, L47).
- **Attack competition** (same Gemma family under a time wall, ~40 scored submissions, L631-663):
  - multi-tool prompts halved the score (~20 vs ~50); fewer, simpler calls win;
  - shorter prompts did not raise throughput;
  - local gemma-4-26B Q4 on the 5070 Ti ran at ~2-10 tok/s;
  - budget discipline (hard stop before the wall) won.
  These directly produced v3's "tighten for speed" design (L665).
- **Poker / CASMI**: pointers only in the log (L47, L415, L542). **[AUTHOR]** a paragraph from you on what those
  competitions taught (agent design? evaluation? submission strategy?) would strengthen this section.
- Initial design spec: sibling-conformance hypothesis and its same-day retraction (74% claimed -> ~12% lenient /
  ~5% strict; fixes are ~95% novel synthesis, L293-340). Good early example of the method working on ourselves.

## 3. Phase 1 - early wins (10-01 to 10-03)
- v1: 6 tasks, 0 resolved -> traced to 4 harness/loop bugs, not the method (L447-470, L492).
- Local free harness on Ollama gemma4:26b reproduced the Kaggle failure mode ("exploration death") (L683-708).
- Board: 0.10 (v1/v2) -> **0.12 (v6, contract anchoring)** on 10-03 (L8399-8400). Rank climbed quickly.
- What worked: the imported discipline (pre-registered bars, one change at a time) plus a faithful local
  reproduction of the failure.
- **Fig 10** (P1 band). **[GAP]** rank-over-time numbers: the log has rank 888/2800 on 10-14 (L8911) only; a rank
  history would make "ranking up quickly" concrete - pull from leaderboard snapshots if you have them.

## 4. Phase 2 - the 31B-only plateau (10-03 to 10-12)
Narrative: ten days without beating 0.12; board 0.08, 0.08, 0.10, 0.05 (L8401-8404).
- **Why we stalled** (log-supported reasons):
  - one scored submission per day and a weekly GPU quota made every 31B iteration expensive (L569, L5112);
  - the only local proxies were slow or not the 31B: gemma4:26b via Ollama (~2-10 tok/s), 12B via HF+bnb
    ~5-6 tok/s, 12B GGUF 64.5 tok/s (L712, L847, L2314); a 12B task took ~9 min locally (L6418);
  - we were pulling the wrong levers: the standing diagnosis was "the wall is commitment" (L8-35) and we
    attacked it with prompt rules and LoRA.
  - **[GAP]** the log records no run of the 31B itself on the 5070 Ti and no local 31B speed. If you did get
    the 31B running locally (llama.cpp?), please give the setup and tok/s - it is a strong detail for this
    section; otherwise phrase it as "the 31B could not be iterated on locally".
- **LoRA: the first idea did not help** (the section reviewers will care most about):
  - edit-discipline adapter (r32 q/v) -> gate 1/5 with edit_fail worse; **board 0.05, our worst** (L5872-5880, L8296);
  - scale-down to 0.5 -> 0/3, patches *worse* than no adapter (L8257-8296);
  - E2B specialist: base 0/6 (patch 2/6), specialist 0/6 (patch 0/6) (L1983-2094);
  - mechanisms: narration at 2B, tool-argument collapse to `1` at 12B, dose-dependent on adapter scale
    (`PAPER_FINDING1_DRAFT.md`);
  - honest framing: our own forensics say the adapter **trained the wrong target** (anchors, not commitment)
    (L5010, L6-35 item 3) -> "this LoRA did not help", not "LoRA cannot help". The forum agrees nobody
    reported a held-out LoRA gain [topics 751596, 750713, 753793].
- **Fig 10** (P2 band, LoRA 0.05 marked). Candidate new figure: LoRA dose-response (degen vs serve-scale).

## 5. Phase 3 - the pivot to small models (10-12 onward)
- Smaller Gemma-4 variants became legal ~10-10/11 (announcement noted 10-12, L8220-8250).
- What changed: iteration speed. E4B GGUF ran at 64 tok/s locally (Q4_0, L13640-13645); Kaggle per-node runs of
  E4B finished 129 tasks in ~75 min. We built local parity rigs (llama.cpp, then WSL vLLM) (L11462-11572).
- Size ladder, one variable (the model): 31B 4/6, 12B 3/6, E4B 3/6 (with remap), E2B 0/6 (L11433-11452).
  -> small models were good enough to *iterate* on, not to replace the 31B. **Fig 11**.
- Board gains in this phase came from configuration, not new methods:
  - v6w budget recipe (28 calls / 8 min / 80 turns / 240 s) -> **0.15** (L8393-8415);
  - A3 delimiter fix -> **0.18** (L11934-11942);
  - ca5 anchor-grep prompt, no sub-agents -> **0.20** (L13760).
- **[GAP] / [AUTHOR]** the laptop (RTX 4050, 6 GB): the log has only a "not viable for E4B" verdict (L17883-17888)
  and a Q4_0 setup started 11-04. If small models ran usefully on the laptop, add the setup + speed; otherwise
  credit the 5070 Ti and Kaggle per-node runs.

## 6. Measuring correctly (core contribution)
- **The board is 58 tasks, truncated** - derived from the *holes* in 3,712 team scores (only 14 distinct values;
  N=58 + truncation is the unique fit) (L12905-12945). One task = 0.017.
- **Noise floor**: byte-identical ca5 bytes scored 0.20, 0.18, 0.17, 0.17, 0.17, 0.13 (L18210); sigma about 2-3
  tasks (L16649, [topic 753524]). Our own sigma estimate moved 1 -> 2 -> 2-3 as data arrived (honest note).
  **Fig 1** (all submissions).
- **The scorer runs tasks sequentially** [topic 743063, host-confirmed]; our test harness ran 4-8 at once, which
  slows each task (30 -> 23 tok/s at 4 in flight) and makes timeouts more frequent than on the board. **Fig 5**.
- **Local rigs are weak proxies** (L14767, L14827); several "wins" were scorer bugs:
  - decode sweep compared different scoring engines (outside review, L16301-16401);
  - stale bytecode in our own gate made it falsely accept wrong same-size patches (L18201-18206).
- Retractions table (from `_chronology_notes.md` section D) - recommend including it as an appendix.

## 7. Axes we closed, with numbers
| axis | evidence | verdict |
|---|---|---|
| prompt wording | 8 consecutive null arms; A24 n=120/arm; ca5 vs empty prompt only +2-4 solves (L12870, L16081) | saturated |
| sub-agents / routers | ca5 12 > A3 10 > A23 9 > router 8 of 58 (L16278); E4B router tournament (L13242) | closed |
| tool-call / time caps | E4B cap 15 = cap 28 (L17114); 50/20 31B pack exceeded scorer runtime (L18213) | closed (except 10-min, sec. 9) |
| thinking budget | 4096/2048/1024 ladder tied; cap binds in 1 of 2,917 steps (L7522, L12716) | not a lever |
| presubmit check (31B) | never fired in 170 runs; 32 vs 33 of 85 (presubmit-85) | null |
- **Fig 3** (31B 32-34 of 85 whatever we add) and **Fig 8** (per-task heatmap: ~28 always / ~8 flippy / ~49 never).

## 8. A practice-set win that did not transfer: E4B fresh-retry
- Design: LoopAgent[fixer, verifier]; deterministic gate (existing tests); rejected attempts undone; best restored.
- Practice result: **11.50 vs 9.82 per 39-task pass (+1.7, t=3.2)**; validation 12.00 (n=20) (L18145-18262). **Fig 2**.
- Mechanism (trace-level): 80% of solves are attempt 1; the retry adds 31 conversions, half because the gate
  rejected syntax-broken first attempts; the first versions of this idea were null because of the stale-bytecode
  gate bug. **Fig 6**.
- Board: **0.01** (1/58) vs plain E4B 0.03 (2/58) - within noise, but both far below prediction (L18484).
- Why: hidden repos differ [host-confirmed]; the gain was concentrated in 5 practice tasks; small-model transfer
  ratio 0.2-0.33. **Fig 7**.
- Lesson: practice-set A/Bs are necessary but not sufficient; gains tied to specific practice tasks are suspect.

## 9. The clock is the 31B's real wall
- Diagnosis: 8-min session timeouts are ~11-15% of runs; they come from a few very long model turns (>60 s turns
  are ~10% of turns but ~60% of model time in timeout runs) plus occasional hung repro commands. **Fig 9**.
- Recoverable tasks: 6 of 15 timeout tasks are solved in other runs (the model can do them).
- A/B (6 tasks x 6 rounds): ca5 9/36, 60 s command timeout 16/36 (p=0.14), **10-min cap 19/36 (p=0.03)**; 12 of the
  19 solves landed between 511 and 608 s. **Fig 4**.
- Regression check: 18/18 always-solved kept; total task time -3% (the 60 s kill offsets the extra minutes).
- Caveat: our tests ran under heavier load than the sequential scorer, so the board gain will be smaller.
- **[PENDING]** board result of the B+C pack - fill in when scored.

## 10. Discussion - what we would do again, and differently
- Again: written rules from prior competitions; pre-registered bars; one change per test; trace-level mechanism
  analysis before declaring a result; logging retractions.
- Differently:
  - measure the board's noise (resubmit one pack twice) in week 1, not week 4;
  - test on the scorer's conditions (sequential, Docker) before trusting timing-sensitive results;
  - treat the public practice set as a development set, not a predictor;
  - spend fewer submissions on single-draw comparisons of near-equal configs.

## 11. Limitations
- Small n per A/B (often 6-39 tasks); one model family; practice tasks from 4 repositories.
- The hidden set is unobservable; board numbers are single noisy draws.
- Several log entries were later corrected (appendix); some dates in late entries are unverified (`_chronology_notes.md` G.11).

## Appendices
- A. Board submission table (from `_chronology_notes.md` B).
- B. Retractions and corrections (section D).
- C. Hardware and throughput (section F; Fig 5).
- D. Forum-sourced scorer facts with host-confirmed / claimed tags (`Outputs/FORUM_ANALYSIS_20261108.md`).
- E. Reproducibility: kernels, builders and analysis scripts (`kaggle_pkg/`, `Outputs/_*.py`).

---

## Figure map
| Fig | file | section |
|---|---|---|
| 1 | `10_phase_timeline.png` | 1, 3-5 (opening figure) |
| 2 | `01_board_timeline.png` | 6 |
| 3 | `11_size_ladder.png` | 5 |
| 4 | `03_31b_85_rounds.png` | 7 |
| 5 | `08_31b_task_heatmap.png` | 7 |
| 6 | `02_e4b_arms_39.png` | 8 |
| 7 | `06_e4b_retry_mechanism.png` | 8 |
| 8 | `07_transfer.png` | 8 |
| 9 | `09_31b_turn_times.png` | 9 |
| 10 | `04_timeout_ab.png` | 9 |
| 11 | `05_telemetry.png` | 6 |
Still to build: LoRA dose-response (sec. 4), the 58-task "holes" histogram (sec. 6), a retraction timeline.

## Open questions for the author
1. Earlier competitions: what exactly carried over from poker and the attack agent (one paragraph each)?
2. Did the 31B run on the 5070 Ti? Setup and tok/s, or should the text say "could not iterate locally"?
3. What ran on the laptop, and how fast?
4. Target venue/format (Kaggle write-up, blog, workshop paper)? That sets length and tone.
