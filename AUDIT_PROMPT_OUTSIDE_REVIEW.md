# OUTSIDE REVIEW BRIEF — audit this project's work for flaws and inconsistencies

You are an independent reviewer. Your job is **not** to be encouraging. It is to find errors,
unsupported claims, inconsistent numbers, and methodological mistakes in the work described
below. Assume the author is competent but motivated to believe their own conclusions — that is
exactly the failure mode you are here to catch.

Write your findings as a table of **findings**, each with: what was claimed, what the evidence
actually supports, the specific file/line, severity (blocking / material / minor), and what
should be done. If a claim survives scrutiny, say so briefly and move on. Do not pad.

---

## 1. What this project is

Kaggle competition "Gemma 4 Developer Agent": submit an agent bundle (prompt + tools + sampling
config) that a harness runs against ~58 hidden SWE-style tasks. Two tracks: a main track
(best score **0.20**) and a **$10K Small Model Prize** for the E4B model (current score
**0.03**, board top **0.10**).

A practice set of **129 tasks** with public gold patches is used for local experimentation.
Everything below concerns that practice set and the local evaluation rig.

Environment: Windows, PowerShell, Python 3.13, llama.cpp `llama-server` on `127.0.0.1:8081`
serving `gemma-4-E4B_q4_0-it.gguf`, and a Docker image `gemma-parity-rig` containing the real
harness (`swegemma` 0.2.11 + `adk_submission` 0.2.13 + `adk_eval_core` 0.1.0).

---

## 2. Where everything lives

Root: `C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\`

| path | what it is |
|---|---|
| `GEMMA_EXPERIMENT_LOG.md` | append-only human-readable log, ~16,200 lines. **The primary evidence source.** |
| `kb/logdb.sqlite` | machine-readable index of **every** `## ` unit in the log (SQLite + FTS5), plus 1,206 extracted claims and 129 task gold records |
| `kb/kblib/logdb.py` | query CLI for the above |
| `kb/tasks_gold.json` | per-task gold metadata: files, functions, n_files, added, removed, `difficulty.kb_mech_class` |
| `kb/runs.jsonl` | 4,486 run records (13.7 MB) |
| `kb/near_miss.jsonl` | per-run stage tracking (READ_GOLD_FILE / SAW_GOLD_HUNK / APPLIED / RESOLVED) |
| `RICH_48_DIFFICULTY_MAP.md` | per-task difficulty analysis of the 48 rich tasks |
| `comp_files/tasks.jsonl` | the 129 task definitions (problem statement, gold `patch`, `test_patch`) |
| `comp_files/system.md` | the **official Google starter prompt** |
| `local_eval/parity_rig/` | the local evaluation rig |
| `local_eval/parity_rig/replay_verify2.py` | model-free replay verifier (applies a patch, applies the official test_patch, runs the tests) |
| `local_eval/parity_rig/agent_ctrl_*` | agent bundle variants (prompt + tools + sampling) |
| `local_eval/parity_rig/m1_capped/agent_ctrl_e4b_r0`, `_r1` | two full 129-task ca5 runs, identical config |
| `local_eval/parity_rig/m1_faithful/agent_ctrl_e4b_r0` | a third, sampler-matched run |
| `local_eval/parity_rig/m1_noprompt129/` | full 129 with `prompts/system.md` = **0 bytes** |
| `local_eval/parity_rig/m1_refdef/` | the 7-task "reference-vs-definition" cohort with a modified rule |
| `local_eval/decode_sweep.py` | the decode-parameter sweep driver |
| `local_eval/sweep_stats.py` | sweep significance analysis |
| `kb/audits/2026-10-15-decode-commitment-sweep.{md,jsonl}` | the frozen pre-registration and 88 measured cells |
| `kaggle_pkg/out_e4b/results/` | the **real Kaggle** E4B run: 10/129, with per-task `test_outputs/*.log` |
| `kaggle_pkg/out_gold_fa/` | gold-patch validation of all 67 fastapi tasks on a CPU Kaggle kernel |
| `kaggle_pkg/out_v7/` | a 31B run: 35/129 |
| `..\.kiro\specs\gemma-swebench-agent\` | the original design spec (requirements, design, HARNESS_FACTS) — note this is at the `kAGGLE\` root, one level **above** `Gemma\` |
| `SESSION_TRANSCRIPT_2026-11-01.md` | the full chat transcript of the session that produced this work |

**Query the log with the index, not with grep** (grep on 16k lines truncates and has already
caused errors):

```
python kb/kblib/logdb.py "inline_snapshot"
python kb/kblib/logdb.py "E4B AND 129"
python kb/kblib/logdb.py "dependencies/utils.py"
python kb/kblib/logdb.py --task rich_3518
python kb/kblib/logdb.py --sql "select line,heading from units where body like '%18 fastapi%'"
```

Each run directory holds `task_results.jsonl` (one row per task: `resolved`,
`test_exit_code`, `tool_calls`, `duration_seconds`, `agent_patch_size`), `patches/*.patch`,
`traces/trace_*.json` (steps with `tool_calls[].function_name` and `.arguments`), and
`test_outputs/*.log`.

---

## 3. Claims to audit

For each, verify independently from the artifacts. Do not take the log's word for it — the log
contains both the claim and, in places, its own retraction.

### A. Benchmark characterisation

**A1.** Of the 129 tasks, only **59 are truly solvable**: 60 pass with the gold patch (validated
by replaying gold), minus 1 (`requests_6644`) that also passes with an **empty** patch
(degenerate). **34 tasks are dead** because the official eval image cannot even collect their
tests (`ModuleNotFoundError: inline_snapshot` / `dirty_equals`), so no submission can resolve
them. All 34 are fastapi.
- Check: `kaggle_pkg/out_e4b/results/test_outputs/*.log` and
  `local_eval/parity_rig/m1_capped/agent_ctrl_e4b_r0/test_outputs/*.log` for
  `No module named 'inline_snapshot'`. Check the gold/empty replay JSONs.
- **Audit question:** is "dead" the right classification? Is a collection error *always* the
  environment's fault, or could the agent's own patch break an import? The log claims the latter
  cases were excluded — verify that the exclusion rule was applied consistently and did not
  quietly remove real agent failures from the denominator.

**A2.** Per-repo: fastapi 67 total / **29 gold-valid** / 34 dead / **8 genuine solves** /
**4 stable**; rich 48 / 30 / 0 / 7 / 2.
- **Audit question:** do these per-repo numbers reconcile with A1? Is the fastapi live
  denominator (29 or 33) stated consistently everywhere?

**A3.** The leaderboard denominator is **58**, and the public score is
`floor(k/58*100)/100` — inferred by brute-forcing N over the distribution of 3,871 public scores.
**Since then this has been independently confirmed by six of our own submissions**, each of which
maps to a single integer k: 0.20=12, 0.18=11, 0.17=10, 0.15=9, 0.13=8, 0.03=2. The ladder is
gap-free and every adjacent step is one task.
- **Audit question:** is the N=58 inference sound? What else could produce the observed set of 14
  unique score values with systematic holes, *and* a gap-free 1-task ladder across six known points?

**A4.** Grader stochasticity on a **fixed artifact** is **1 task**. Measured directly: the 0.20 pack
was resubmitted with byte-identical bytes and scored **0.18**, i.e. 12/58 → 11/58.
- **Audit question:** is one pair of draws enough to estimate sigma? Does it matter that the two
  draws were 3 days apart (possible task-set or grader changes)? What would a proper estimate need?

### B. The local rig is (or is not) a faithful proxy

**B1.** The rig **false-positives on exactly 3 tasks**: `requests_7309`, `requests_7315`,
`requests_7427`. Mechanism claimed: the rig image has no `/wheels`, so
`pip install -e /workspace` fails (rc=1) and is swallowed by `|| true`; for `requests` the
package lives at `src/requests` and therefore pytest imports the **site-packages** copy instead
of the patched source. For `rich` and `fastapi` the package is at the repo root and pytest's
rootdir insertion makes the patched source win — verified by sabotaging the workspace copy and
observing a collection error.
- **Audit question:** is the sabotage test conclusive? Does it generalise to every task, or only
  to the two repos tested? Are there tasks whose *test* imports differ (e.g. `docs_src/`
  fixtures) where the same hole reappears?
- **Audit question:** the rig's `requests` results should be treated as invalid. Were they?
  Three of them appear in every solve count — check whether any conclusion was computed on
  recorded rather than corrected numbers.

**B2.** Local vs Kaggle agreement: local ca5 genuine 9–11/129; Kaggle E4B 10/129 with **zero**
provable false positives. Claim: the rigs agree within noise.
- **Audit question:** the local rig never produced a context-overflow or a wall-clock death,
  while Kaggle had 6 overflows and 2 timeouts. Is "they agree" defensible when the error
  profiles differ? Does that difference bias which tasks each can solve?

### C. Measurement power

**C1.** Run-to-run noise is **±2 tasks per 129**. Evidence: two identical-config runs scored
12 and 14 (agreement 121/129); a third, sampler-matched run scored 14.
- **Audit question:** n=3. Is ±2 defensible, or is the true variance larger? Note the same
  config also produced 15 in an earlier, uncapped run. Does the log's noise claim survive that?

**C2.** Every arm tested in this project landed within ±1–3 tasks: locate-numeral, thinking
budget 512/1024, def-substitute, decode penalties, multi-agent routing, submission-rule
changes. Claim: **all were measured below the noise floor**, so the nulls are uninformative
rather than evidence of no effect.
- **Audit question:** is that the correct interpretation, or does it let every null off the
  hook? If the instrument cannot resolve 2 tasks, what *was* learnable, and were those things
  learned?
- **Counter-evidence to check:** the board *did* separate arms by more than the noise floor —
  A3 hard 10/58, A23 9/58, A25 router 8/58, ca5 12/58. The multi-agent router cost **4 tasks**,
  a regression far larger than the local noise band. Does that contradict the "everything is
  below the noise floor" claim? Note the local rig tested the router too and found ~0.

**C3.** A recommendation was made — twice — that **repeated identical resubmission** of the E4B
pack would reach 0.10–0.12. It was computed with a binomial sigma of 2.07. The measured sigma is
1 (A4), which caps resubmission at **0.05–0.06**; reaching 0.10 requires 6/58, i.e. **4 sigma**
above the mean of 2.
- **Audit question:** the recommendation was retracted. Is the retraction correct? Is 4 sigma the
  right framing, or is the mean of 2 itself uncertain enough that the whole calculation is moot?

### D. Prompt value

**D1.** A **0-byte** system prompt scores **7 genuine** vs ca5's **9/11/11**. Pairwise McNemar
p = 0.29–0.75. Claim: the prompt is worth **+2 to +4** solves, and it is responsible for 3
tasks that are solved in all three ca5 runs and never by the empty prompt (`fastapi_14463`,
`fastapi_14616`, `rich_3905`).
- **Audit question:** with one empty-prompt run, can "never solved by the empty prompt" be
  distinguished from "not solved in that one draw"? The no-prompt arm has no replicates. What
  would it take to make this claim sound?
- **Audit question:** is the +2–4 estimate contaminated by the 3 phantom `requests` tasks being
  subtracted differently across arms?

### E. Rule compliance

**E1.** A modified prompt rule ("grep for the symbol's **definition**, not its usage") was
executed **repo-wide 0 of 7 times**. In 3 of 7 runs the model ran a *single-file* definition
grep — inside the file it had already chosen — which cannot falsify that choice. Both solves in
that arm came from runs that never ran the rule.
- **Audit question:** verify from `traces/*.json` → `steps[].tool_calls[].arguments`. Is the
  scope classification right? Were any repo-wide greps missed by the pattern?
- **Audit question:** the same arm was earlier reported as "100% compliant" (regex over raw
  trace text matched the *prompt text embedded in the trace*) and then as "~25% compliant"
  (inferred from lack of effect). Both were retracted. Check that no surviving conclusion
  depends on either.

### F. Decode sweep

**F1.** A pre-registered sweep (frozen 2026-10-15, **never run** until now) produced **4 "WIN"
verdicts** — and all four are noise: `freq_02`/`freq_04` convert exactly **one** task
(`rich_3518`), 1-vs-0 on n=5, McNemar p = 1.00; `temp_00`/`pres_02` "win" only on a
one-call median shift. Greedy decode **lost** the baseline's only DISCOVER solve.
`reserve_tail` scored 2/6 on DISCOVER and 0/5 on CONFIRM.
- **Audit question:** is the pre-registered bar itself badly designed (it permits a one-call
  median shift on n=5 to count as a win)? Does that invalidate the "4 wins" as a *finding about
  the bar*, and is that distinction stated?
- **Audit question:** one task (`rich_3772`) was excluded mid-run because its replay exceeded a
  900 s timeout, changing CONFIRM from 6 to 5 tasks. Is that a legitimate protocol deviation or
  does it undermine the pre-registration?

### G. Process

**G1.** An audit of the session transcript found **44 distinct corrected errors**, of which
**13 (30%) were facts already present in the log** and 2 more re-derived an existing artifact.
- **Audit question:** verify the classification on a sample. Is "retrieval failure" being
  assigned generously? Are instrument bugs (C bucket, 16) being kept separate from
  reasoning errors (D, 9)?

---

## 4. Things already retracted — do not just re-report these

The log already contains these self-corrections. Finding them again is not a finding. If you
believe a retraction is itself wrong (i.e. the original claim was right), that IS a finding.

- "The 10/129 local result was really a 12B model" — retracted; all local runs are E4B.
- "The prompt's stated budget (8 min / 28 calls) is false" — retracted; the grader reads those
  four fields and they were verified non-binding (max 22 calls, max 419 s observed).
- "The context window is the lever (local 90k vs Kaggle 32k)" — retracted; `-c` is divided by
  `-np`, so per-slot context is 30,208, *smaller* than Kaggle's 32,768.
- "Observing 2/58 against a 10/129 rate is a 2.3× mystery" — retracted; a binomial puts it at
  p = 0.163, i.e. ordinary noise.
- "The benchmark is 26% broken, so fastapi is dead weight" — retracted framing; fastapi supplies
  53% of genuine solves and 67% of stable ones.
- "The local rig is crippled by missing test dependencies" — retracted; the official Kaggle
  image has the same gaps.
- "The sampler divergence (`top_k` 64 vs off, `min_p` 0.05 vs 0) is a lever" — measured null.
- "Repeated identical resubmission of the E4B pack will reach 0.10–0.12" — retracted; the measured
  grader sigma is 1 task, which caps resubmission at 0.05–0.06. Reaching 0.10 needs 4 sigma.
- "The winnability map was first established this session" — false; it dates from 2026-10-11.

---

## 5. Traps specific to this project

If you fall into these, your review will be wrong:

1. **Subset selection.** Comparing runs on different task subsets has twice produced a phantom
   "irreproducibility crisis". Always compare on the intersection, and never exclude the tasks
   that carry the effect.
2. **Phantom tasks.** `requests_7309/7315/7427` resolve in every local run for the wrong reason.
   Any local number that has not had them removed is inflated by 3.
3. **Dead tasks.** 34 tasks cannot resolve for anyone. Any per-repo or per-task rate computed
   over all 129 is diluted by them.
4. **Text vs execution.** Compliance and tool usage must be read from
   `steps[].tool_calls[].arguments`, never from regex over raw trace text — the trace embeds the
   system prompt, so a naive regex matches the *instruction*.
5. **Union vs single run.** A union of 3 runs is not comparable to a single run.
6. **Cached results.** The replay engine caches per (config, task). A "new" run may be reading
   stale cache; check for `[cache]` markers.
7. **Truncated search.** Grep on a 16k-line log with a `head_limit` has already caused a
   conclusion of "not in the log" for something that was at line 5,237. Query the index.

---

## 6. What I want back

1. **Findings table** — as described at the top. Ordered by severity, not by section.
2. **The three claims most likely to be wrong**, and what test would settle each.
3. **Any number that appears in more than one place with different values.** List both
   occurrences with file/line.
4. **What this project has actually established**, stated conservatively enough that you would
   defend it in front of a sceptical reviewer.
5. **What you would do next**, given: one submission slot per day, no GPU budget for the local
   rig, and the goal of moving the E4B score from 0.03 to ≥ 0.10.

Be specific. Cite file and line. Distinguish clearly between **measured**, **inferred**, and
**assumed**. If you cannot verify something, say so rather than assuming it is correct.
