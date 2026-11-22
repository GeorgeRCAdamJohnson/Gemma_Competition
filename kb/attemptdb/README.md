# Project intel database (`kb/attempts.sqlite`)

Every agent attempt the project holds (14,739 unique; 36,113 rows incl. copies; 7,807 traces), decomposed to the step and tool-call
level, joined to the experiment, registration, agent bundle, vLLM server state, task gold data, the experiment log and
every other project document. Use it to analyse at scale, and to check whether a planned experiment has effectively
been run before.

```
python kb/attemptdb/build.py               # full rebuild (~60-90 s), read-only on the repo
python kb/attemptdb/build.py --stages core,traces   # partial (core must run first on a fresh DB)
python kb/attemptdb/verify.py              # 16 checks; exit 1 on failure -- run after every build
python kb/attemptdb/q.py --schema
python kb/attemptdb/q.py --task rich_3782
python kb/attemptdb/q.py --exp kaggle_e4b_seed39_evidence_first --by round
python kb/attemptdb/q.py 'SELECT ... FROM attempts_unique ...'
python kb/attemptdb/inventory.py           # raw-material inventory of the repo
```
The `.sqlite` is gitignored (derived, ~0.5 GB): commit code, rebuild after pulling results.

## Layers
| layer | tables / views | source |
|---|---|---|
| attempts | `attempts`, **`attempts_unique`** (use for rates), `pass_summary`, `task_rates` | task_results.jsonl, lora_progress.json, progress/variance_ab summaries, **tar archives** (31B ca5 results.tar.gz) |
| experiments | `experiments` (registration + report JSON), `arms`, `registered_files`, `exp_bundles` | registration.json, result_report.json |
| agent bundles | `bundles`, `bundle_files` (contents), `bundle_diffs` (vs pack 1), `arm_bundles` | every dir with an agent.yaml (133) |
| traces | `traces`, `steps` (full message text, tokens), `tool_calls` (tool, args, file, command kind, latency, status, error type/message, exit code, edit strategy/diff, gate verdict, gold-file flag, repeat flag, full observation) | 4,375 ATIF traces incl. archives and old submission folders |
| display logs | `log_events` | 4,104 logs of attempts without a trace (Colab A/B runs) |
| behaviour | `attempt_features` (calls by tool and command kind, failed/repeated calls, edits ok/failed, first edit file and whether gold, gold touches, calls/seconds to first edit, fixer/verifier/tester calls, loop iterations, gate verdicts, max prompt tokens, thinking chars, tool sequence); `basis` = trace or log | traces, logs |
| vLLM | `vllm_servers` (version, args, context, LoRA modules, KV cache, concurrency, init), `vllm_metrics` (10 s), `vllm_errors` (timestamped; overflow token counts), `vllm_http`, `attempt_server_load` (each attempt's lane load in its window) | 44 vllm_gpuN logs |
| crawl | `documents` + `documents_fts` (FTS5), `kernels`, `adapters` | 4,472 notebooks (with outputs), kernel-metadata, registrations, receipts, adapter configs, training artifacts, run logs, docs, code, chat history |
| experiment log | `log_sections` + `log_sections_fts`, `log_mentions` (exp, slug, task, submission, bundle sha12, drive tag) | GEMMA_EXPERIMENT_LOG.md |
| lineage | `experiment_catalog` (cohort hash, models, adapters, context, totals, signature), `arm_catalog`, `repeated_experiments` | all of the above |
| tasks, submissions | `tasks` (statement, gold patch, test patch), `submissions` | tasks.jsonl, _submissions.json |

## Definitions
- `verified`: resolved, no error, exit 0, non-empty real test output and, where recorded, no routing violation and
  `real_grade` (the handoff definition). NULL = inputs not on disk; never read NULL as a failure.
- swegemma `tool_calls` = all calls except `get_status` and `submit_patch` (matches decoded traces in 97.8%).
- Dedupe key: task, round, arm, outcome, patch size, duration (0.01 s), tool/LLM calls; round-less flat copies merge
  within the same experiment only when unambiguous. Precedence task_results > lora_progress > summary; folders > archives.
- vLLM timestamps carry no year/zone: year from the experiment's traces, UTC assumed; untimestamped lines inherit the
  previous timestamp (<= ~10 s). Validated: 306/306 overflow attempts have a vLLM overflow on their lane in their window.
- Log-basis features come from truncated display logs: diffs, exit codes and full observations are missing, and
  `n_repeat_calls` is inflated (truncated arguments look identical). Compare trace and log bases separately.

## Example queries
```sql
-- does a tool-level failure predict the outcome within the same tasks?
SELECT error_type, COUNT(*) FROM tool_calls WHERE is_edit = 1 AND edit_ok = 0 GROUP BY 1 ORDER BY 2 DESC;
-- server load while an attempt ran
SELECT a.task, a.resolved, l.kv_max, l.waiting_max, l.lane_overflows_in_window
FROM attempts_unique a JOIN attempt_server_load l ON l.attempt_id = a.id WHERE a.exp = 'kaggle_tool_lora_p5_repeat39';
-- what has the log said about an experiment?
SELECT s.line_start, s.heading FROM log_mentions m JOIN log_sections s USING (sec_id) WHERE m.value = 'kaggle_tool_lora_p5_repeat39';
-- full-text search across every notebook, doc and log
SELECT path FROM documents_fts WHERE documents_fts MATCH 'include_contents NEAR verifier' LIMIT 20;
-- has this been tried? (same cohort + models + adapters + changed files)
SELECT * FROM repeated_experiments;
```

## Known limits
- Only data on this machine. Colab A/B traces come from `Outputs/drive_ab_runs` (copy of Drive `gemma_fasteval/ab_runs`;
  refresh with `robocopy "G:\My Drive\gemma_fasteval\ab_runs" Outputs\drive_ab_runs /E /MT:32` outside the sandbox).
- `obs_status` is normalised: tools report ok / success / error (skills use "success"); plain-text harness errors
  ("Invoking `edit_file()` failed ...") become error; the rest unknown.
- `model` comes from a trace's `model_name` (LoRA runs show the adapter alias) or the path (`model_basis='path'`).
- 951+ attempts have no parseable arm (single-arm runs); 20/34 registered roles map to an on-disk bundle.
- `n_iterations`/`n_retry_msgs` count verifier segments and RETRY messages; the LoopAgent may phrase retries differently.
