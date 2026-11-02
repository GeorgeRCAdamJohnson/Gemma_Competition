# Proposal: rich near-miss forensic (2026-10-11)

Type: diagnosis. No config change is proposed up front; the audit must end with exactly one proposed next rich-only free-gate change and its pre-registered bar.
Requested by: user. Written by: top-level session. Status: UNAUDITED.

## Question (user's words)

"Across every run on disk, for each rich task ever attempted: where did the agent find the gold fix (read the file, saw the hunk, wrote the change) without landing it, what stopped it each time, and would the attempted change have passed the tests? Which standing truths and verdicts in the log does the raw data contradict? What have we been missing? What is the one next rich-only free-gate change, with a pre-registered bar?"

## Required outputs

1. Per rich task ever attempted, per run: the furthest near-miss stage reached (read gold file / saw gold hunk in a tool result / wrote the gold change in text or tool args / tried to apply / applied / submitted), what stopped it, the trace step_ids, and the local replay result of the attempted change. Gold must pass its test_patch locally before any agent replay counts.
2. Each lead below marked SUPPORTED / CONTRADICTED / UNVERIFIED, with evidence (file paths, step_ids, log line numbers).
3. Every READ-THIS-FIRST standing truth and every log verdict the raw data contradicts, each with proposed CORRECTED text. The top-level session appends these to the log; the auditor does not edit the log.
4. "What we've been missing": ranked, each item backed by evidence.
5. The ONE next rich-only free-gate change: the single change vs the v6 / v6b config, the task set (rich only, each task's difficulty class stated), and the pre-registered pass bar.

## Leads (unverified; check, don't assume)

1. Both v6b hard-rich failures ended with an edit the harness didn't apply: rich_4079 tried a python-replace on rich/markdown.py (step_id 31) and rich_4070 on rich/console.py (step_id 32), both after the agent said it was out of calls, then an empty submit. Read those observations, compare with the gold patches, and replay the attempted edits.
2. In v21 every edit on the losing tasks failed, and v6b rich_4076 took 3 tries to get a python-replace to apply (quoting/anchor errors). Standing truth #2 ("edit mechanics aren't the bottleneck") was measured on edit_file in the LoRA forensic, not on this path.
3. A v6 re-run trace (pasted by the user earlier) shows rich_4070 timing out with an unsubmitted 5,228-char patch after an edit_file empty-old_string loop. Find it (`Gemma\myshit`, `Gemma\_v6out`, `Gemma\pulled_v6`). Would that patch have passed? What does the harness score when a run ends without a successful submit_patch?
4. The log contradicts itself on v6: READ-THIS-FIRST #4 says v6 resolved rich_4077 + rich_4079 (2/6) and "confirmed distinct fixes ever = 2, both rich"; the v6b pre-registration says v6 scored 1/6 on the same sample. Settle it from v6's outputs, then diff every run that resolved rich_4079 against the ones that didn't.
5. Gate makeup: the difficulty class of each gate task (rich_3469, 4070, 4076, 4077, 4079). `Gemma\RICH_48_DIFFICULTY_MAP.md` says 20/48 rich tasks are EASY. If the gate is mostly HARD, it can't see gains on the slice that moves the leaderboard.
6. The v1 entry says the sub-agent found a "Column docstring deviation" for rich_4079, but v6b's rich_4079 problem statement is "Inline table code". Check which matches the gold.

## Log entries from the last session to check claim by claim

At the end of `Gemma\GEMMA_EXPERIMENT_LOG.md` (about lines 6740-6869):
- "v6b RESULT — FREE GATE COMPLETE"
- "v21 vs v6b — BUDGET A/B ON THE SAME HARD RICH TASKS → 'more budget' is FALSIFIED"

Known suspect claims in them: rich_4079 labeled "mislocalization" (against standing truth #1); "v6b rich_4070 made 31 calls, ALL grep/read symbol-tracing, not ONE python-replace edit"; budget declared "a dead lever ... at both ends of the range"; the offer to treat rich_4070/4079 as structurally out of reach. That session read 3 traces from one run and never opened the gold patches or earlier traces.

## Constraints

- v6 @ 0.12 is live-best and sacred. One scored submission per day. Every change goes to a free Kaggle gate first with a pre-registered bar. The next gate is rich-only (fastapi dropped).
- Gold patches are for diagnosis only. Never put gold patches or problem-statement fingerprints into an agent config (`Gemma\VULN_PUBLIC_TASK_PATCH_STAGING.md`).
- 12B is parked. Out of scope.
- No Kaggle pushes, no gates, no commits. The user decides what ships.
