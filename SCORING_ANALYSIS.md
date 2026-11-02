# SCORING ANALYSIS — what the board actually rewards

Read-only audit. No experiment code touched. Sources: `kaggle competitions submissions`
(our 8 scored records), `kaggle competitions leaderboard` (top 25, 2026-10-12),
`GEMMA_EXPERIMENT_LOG.md`, `RICH_48_DIFFICULTY_MAP.md`, `comp_files/`.

---

## 1. OUR COMPLETE SCORED RECORD (8 submissions, 1 error)

| date | ref | description | status | score |
|---|---|---|---|---|
| 10-02 | 56775978 | "One shot" | COMPLETE | 0.10 |
| **10-03** | **56806249** | **"beat...beat....no one else can be defeated"** | **COMPLETE** | **0.12** ← BEST |
| 10-04 | 56835583 | v10 Notebook Version 2 | **ERROR** | — |
| 10-04 | 56835719 | v10 budget-40 (300s) | COMPLETE | 0.08 |
| 10-05 | 56856000 | v15 anti-word-trap, budget 12 | COMPLETE | 0.08 |
| 10-07 | 56896956 | v15 short-trajectory, budget 12 | COMPLETE | 0.10 |
| 10-10 | 57054171 | "kjhgiughj" | COMPLETE | 0.05 |
| 10-12 | 57098497 | **v6w** (1024) | **PENDING** | — |

## 1b. THE MOST IMPORTANT LINE IN THE TABLE — the LoRA scored 0.05

**The 10-10 LoRA validation scored 0.05 — the worst result in our entire record.**

| arm | score |
|---|---|
| prompt-only validations | 0.08, 0.08, 0.10 |
| prompt-only BEST | **0.12** |
| **LoRA validation** | **0.05** |
| leaderboard top | 0.24 |

This matters because the log records the decision that moved the project off prompts and onto weights:
*"The prompt channel is EXHAUSTED ... That is WHY the effort moved to weights (LoRA)"* (lines 30-32).
**The weights move has now been tested on the real board and scored 0.05 — 42% of our best prompt-only
result.** The premise for abandoning prompts was never validated; the replacement was, and it lost.

It is fully consistent with every local measurement, which makes it convergent rather than an outlier:
- **v2 real-adapter gate: 0/5**, degenerate output (malformed tool syntax emitted as plain text, mode
  collapse including Persian-text repetition), 31-105s/task, agent never produced a valid tool call
- **v19-LORA gate: 1/5**, `edit_fail` worse than base
- **E2B/12B A/B sweep: every adapter produced fewer patches than its own unadapted base**

**CAVEAT THAT MUST TRAVEL WITH THIS NUMBER:** log lines 5923-5924 state that the v1-LORA gate *"may ALSO
have tested the sample adapter, not v1"* because of the same glob bug that invalidated v2 run #1. **If the
10-10 zip carried the sample adapter or a mis-wired one, then 0.05 measures the WIRING, not our training.**
Confirm which adapter was inside `kjhgiughj` before quoting this as "our LoRA scored 0.05." Either way it is
the lowest number we have recorded, and **no adapter arm has ever beaten a prompt-only arm** on any judge.

## 2. THE CEILING IS 0.24, AND THE LOG ERASED IT

The log contains a correction (line ~6616): *"**'0.24' IS NOT A REAL SCORE — it is the kernel TITLE, not
an achieved badge.**"*

**That correction was half-right and it cost us the target.** The specific kernel (`gemma-4-baseline-lb-0-24`)
was indeed titled above its badge. But the LEADERBOARD as of today:

```
Yurnero              2026-10-11   0.24
Yike Xu              2026-10-08   0.24
Francis Joseph       2026-10-10   0.22
Deepest Mind         2026-10-09   0.22
... 20+ teams at 0.20
```

**0.24 is achieved and has been since at least 10-08.** The retraction collapsed "that kernel's title was
inflated" into "0.24 is not real" — and the project has spent a day optimising against a 0.18 ceiling that
was never the ceiling. Our rank is **1050 / 2497**.

## 3. THE CENTRAL FINDING — our gate is 5.6x optimistic and structurally incapable of predicting the board

| measurement | value | what it samples |
|---|---|---|
| **our 6-task gate (today)** | **4/6 = 67%** | **6/6 EASY, 0 MEDIUM, 0 HARD** |
| representative-10 (v9, trustworthy) | **0/10 = 0%** | representative |
| rep-10 (v10, committed run) | 0/10 | representative |
| **live board** | **0.12** | the real ~120-task scored set |
| leaderboard top | 0.24 | — |

**Gate vs board = 5.6x.** And the reason is not noise — it is composition:

| | EASY | MEDIUM | HARD |
|---|---|---|---|
| **our 6-task gate** | **100%** | 0% | **0%** |
| the real 129 (rich 20/12/16 + fastapi 19/8/40) | ~30% | ~16% | **~43%** |

Every single task we gated on today was hand-picked from the difficulty map's *"top 15 easiest"* list.
We spent the whole session comparing configs on a task set we had *already selected because we could
solve them*. Four consecutive experiments (v6t, v6v, v6w, v6x/v6y) returned 4/6, 3/6, 4/6, 4/6, 3/6 —
a noise band around a number that was never a forecast of anything.

**Arithmetic of the gap:** if we resolve ~67% of EASY and ~0% of everything else, expected board =
0.30 × 0.67 ≈ 20%. We score 12%. The residual is explained by fastapi being materially harder than rich
at equal nominal class (28% vs 42% easy), which is consistent with *"zero fastapi has ever resolved."*

## 4. WHAT THIS IMPLIES — ranked by expected board movement

**(a) The gate is finished as an instrument.** It cannot see MEDIUM or HARD, which are ~59% of tasks and
where the entire gap from 0.12 to 0.24 lives. Any further A/B on these 6 tasks is measurement of nothing.
*This is the same conclusion as the saturation finding, arrived at from the scoring side instead.*

**(b) A representative gate is the missing instrument.** v9/v10 used a representative-10 and got 0/10 —
correctly measuring near-zero, which the easy gate could never have revealed. A rep gate would be *harder
to move* but it would move for the right reasons. **Any future gate must be random/representative, never
hand-picked.**

**(c) The 12h truncation question is still untested and is now the highest-value unknown.** The scored set
is ~120 tasks. Our arithmetic puts 8 min/task at ~13h — **over the cap**. If the harness errors the
submission on overrun, every "0.08" we have ever recorded could be a partially-completed run rather than
an agent-quality signal. One ERROR already appears in our history (10-04), so the failure mode is real.
**This is testable for free from our own scored data** and should be tested before the next submission.

**(d) The four regressions since 0.12 deserve one retrospective, not four.** Every config since has been
tried against the 6-task gate, all of which read ~50% variance around a number disconnected from the
board. The regressions may say more about the instrument than the configs.

## 5. WHAT WOULD ACTUALLY MOVE THE SCORE

Ranked by leverage, not by ease:

1. **Resolve anything MEDIUM or HARD.** ~59 tasks sit there and we currently convert ~none. Even 10%
   on MEDIUM alone = +2 tasks ≈ +0.016.
2. **Confirm the run completes all tasks inside 12h.** Binary, and an overrun may zero the whole thing.
3. **Stop measuring on EASY-only hand-picked gates.** Costs nothing, prevents further false signals.
4. Re-examine why 0.12 (10-03) beat everything since — one retrospective on the four regressions.

## Appendix — reproducibility

```
kaggle competitions submissions -c gemma-4-developer-agent
kaggle competitions leaderboard  -c gemma-4-developer-agent --show
```

Read-only. No submission, kernel push, or competition state was modified.