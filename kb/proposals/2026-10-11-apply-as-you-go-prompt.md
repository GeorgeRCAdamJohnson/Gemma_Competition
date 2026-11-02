# Proposal: "apply-as-you-go" prompt for multi-item tasks (2026-10-11)

Type: prompt change. Status: UNAUDITED.
Floated as lever (a) under "IMPLICATION for v6bv2 (rich-only)" in the log entry "v21 vs v6b — BUDGET A/B ON THE SAME HARD RICH TASKS" (`Gemma\GEMMA_EXPERIMENT_LOG.md`, end of file, about lines 6863-6869).

## The change

Add one generic instruction to the v6b system prompt: when the problem lists multiple items, make each edit immediately after locating that item (bank partial progress) instead of tracing everything first. No other change. It must stay generic: no task ids, file names, or problem-statement fingerprints (scorer gaming; see `Gemma\VULN_PUBLIC_TASK_PATCH_STAGING.md`).

## Target

rich_4070, described in the log as a multi-file perf refactor across logging.py and console.py where the agent traced every symbol and hit the wall with 0 edits banked.

## What the audit must settle

- Is the stated cause right? Lead: the v6b rich_4070 trace reportedly has a python-replace on rich/console.py at step_id 32, after the agent said it was out of calls. If so, the run was not "0 edits attempted".
- Does the hidden pytest for rich_4070 reward partial progress? Read its test_patch. If the tests need every item, banking a subset still scores 0 and this lever cannot flip the task.
- How many items and hunks does the gold patch have, and what would applying them one at a time cost in calls vs the budget?
- Risk to the always-solved rich_4077 and other easy tasks: earlier, worse edits and more edit errors on the python-replace path.
- Prior art: any earlier prompt that pushed early or incremental edits ("force an edit early", "commit early", v1's 25-call cap), with per-task outcomes.
