# Proposal: raise max_tool_calls 28 -> 50 (2026-10-11)

Type: config change. Status: UNAUDITED.
Floated by the previous session as the "v6bv2-draft" idea, then withdrawn without an audit in the log entry "v21 vs v6b — BUDGET A/B ON THE SAME HARD RICH TASKS → 'more budget' is FALSIFIED" (`Gemma\GEMMA_EXPERIMENT_LOG.md`, end of file, about lines 6809-6869).

## The change

On the v6b config (`Gemma\submit_v6b`: 28 calls / 8 min / 240 s timeout / thinking 4096 / no edit_file, edits via run_command python-replace), change only max_tool_calls 28 -> 50. Everything else identical.

## Rationale given at the time

v6b's hard-rich failures (rich_4070, rich_4079) used the full 28-call budget; rich_4079 reportedly reached rich/markdown.py around call 24 and ran out.

## Why it was withdrawn (claims to check, not facts)

The A/B entry argues that going from 15 to 28 calls resolved zero additional tasks, so budget is "a dead lever at both ends of the range". It also claims v6b rich_4070 made "not ONE python-replace edit".

## What the audit must settle

- Did v6b rich_4070 and rich_4079 end with an edit the harness refused at the call wall (reported at step_ids 32 and 31)? If so, would that edit have passed (local replay, gold first)?
- Is two budget points (15, 28) on two hard tasks, n=1 per task at temperature 0.2, enough to call a lever dead? Check against `.kiro\steering\reverse-engineering-accountability.md` rules 13 and 18. Note v21 also changed thinking budget and timeout, so the A/B is not one-variable.
- Does 50 calls fit inside max_time_minutes=8 and the 240 s per-call timeout given observed per-call durations, or does the time wall bind first? (An earlier log entry, around line 606, says time, not calls, was the binding constraint in that version.)
- Prior art: every version that changed max_tool_calls, max_turns, or max_time_minutes, with per-task outcomes.
- Risk to the always-solved rich_4077 (later or wrong submits with more room).
