# Decode-commitment sweep — build + run review

The build delivers an in-repo, idempotent sweep runner (`local_eval/decode_sweep.py`) that drives the existing local agent loop across a pre-registered arm table × a frozen rich task set, scores every agent attempt through the FIXED per-task-pinned gold-first replay engine (`kb/kblib/replay.py`, rp-4), and emits the pre-registered report + raw JSONL. The one supporting edit to `run_local.py` adds `frequency_penalty`/`presence_penalty` forwarding, guarded so a 0.0 penalty leaves the request payload byte-identical to prior behavior. The run itself produced NO measured arm numbers: the local backend (llama-server on 127.0.0.1:8081) was down, so all 96 cells are recorded NOT-RUN with the connection error, no arm was scored, and no winner was declared.

Watch for: nothing blocking. The run is an honest null-of-execution (backend down), the scorer path is the real rp-4 engine, the `run_local.py` edit is additive and no-op at defaults, both clones are clean, and the report carries the verbatim pre-registered bar, MEASURED-vs-NOT-MEASURED tagging, and the LOCAL-ONLY caveat. One NIT on an mtime coincidence with the experiment log (confirmed unrelated).

**Verdict**: APPROVED

## High-level view

The scorer reuse is correct and is the single most important constraint. `decode_sweep.py` imports `kblib.replay` and routes validity through `ReplayEngine.gold_first` and scoring through `ReplayEngine.run_candidate` (both `RP_VERSION == "rp-4"`), mirroring the per-task `result_criterion` (`harness_like` vs `gold_relative`) that the gold gate chose. There is no home-grown pass/fail check and `run_local.verify()` is deliberately avoided for scoring.

The `run_local.py` edit is additive and backward-compatible. Two module globals default to 0.0; `chat()` forwards them only under `if FREQUENCY_PENALTY:` / `if PRESENCE_PENALTY:`, so at defaults the payload is unchanged. The argparse flags default to 0.0. This satisfies the "additive, no behavior-changing default" constraint.

The pre-registered bar is frozen in code and echoed verbatim at the top of the report, with the DISCOVER/CONFIRM split disjoint and covering (asserted in `--list`), the bar judged only on CONFIRM, and the win condition encoded exactly as the brief requires (resolves ≥ baseline AND strictly better commit-timing, OR strictly more resolves; a tie on resolves with equal/worse timing is a FAIL). The baseline is a hard floor; a null is a valid result.

The run is a backend-down null. Every cell is NOT-RUN with the WinError 10061 reason; `resolved` is null throughout the JSONL; the report VERDICT reads "NOT MEASURED — backend was down" and explicitly states the resolve/commit-timing numbers were not fabricated. No arm is a WINNER. This is the correct recorded outcome under the "never fake numbers" rule.

Writes are confined to `Gemma/kb/` and `Gemma/local_eval/`. Both rich and fastapi clones are clean (`git status --porcelain` empty, independently confirmed). No `submit_*` dir has a modification time near this build, and no decode-sweep entry was appended to `GEMMA_EXPERIMENT_LOG.md`.

<details>
<summary>Issues (1)</summary>

1. **Experiment-log mtime coincidence (NIT)** — `GEMMA_EXPERIMENT_LOG.md` has a later mtime (9:47 PM) than the deliverables (9:35 PM), but its tail is a content-correctness-LoRA audit entry, not a decode-sweep entry; no decode-sweep build text was appended. Attributable to a separate concurrent workflow, not this build. No action.

</details>

<details>
<summary>Details</summary>

## Scorer path — real rp-4, no bypass

`run_cell` scores the agent diff by opening `with rp.ReplayEngine(tasks_gold) as eng:` and calling `eng.run_candidate(repo, tid, base_commit, kind="patch", patch_text=diff, gold_pass_tests=gold_rec.get("gold_pass_tests"), timeout_s=...)`. Validity comes from `eng.gold_first(...)` in `gold_gate`. Both are the public rp-4 API (`RP_VERSION = "rp-4"` in `replay.py`, stamped into every result as `engine_version`). The `resolved` flag mirrors the per-task criterion the gate used — `res["harness_like"]` when the gate was harness-like, else `res["gold_relative"]` — which is the approved rp-4 contract, not a new rule. A task whose gold is INVALID locally is excluded up front (`run_all` emits an `EXCLUDED` row and never scores an attempt against invalid gold). No alternative pass/fail logic exists in the runner. This clears the primary blocking constraint.

## `run_local.py` edit — additive, no-op at defaults

```python
FREQUENCY_PENALTY = 0.0
PRESENCE_PENALTY = 0.0
...
if FREQUENCY_PENALTY:
    payload["frequency_penalty"] = FREQUENCY_PENALTY
if PRESENCE_PENALTY:
    payload["presence_penalty"] = PRESENCE_PENALTY
```

The truthiness guard means 0.0 never enters the payload, so the default request is byte-identical to the pre-2026-10-15 behavior. The two new argparse flags (`--freq-penalty`, `--presence-penalty`) default to 0.0. This is strictly additive and changes no default behavior — it is not a behavior-changing edit to `run_local.py` defaults.

## Pre-registered bar and held-out split

`PREREGISTERED_BAR` in `decode_sweep.py` is the verbatim text reproduced at the top of the report, and the win condition is encoded in `verdict_for`: `r_arm > r_base` → WIN; `r_arm == r_base` with strictly-better timing → WIN; `r_arm == r_base` with equal/worse timing → `FAIL(tie-no-timing-gain)`; fewer resolves → FAIL. `_timing_better` is earlier median first_edit OR fewer no-edit runs. The split is disjoint and covering, asserted at `--list` time (`set(DISCOVER) & set(CONFIRM) == set()` and union == TASK_SET), and the per-arm table is judged on CONFIRM with DISCOVER shown separately. A winner can only be chosen on tasks it was not tuned on. The two multi-file giants (rich_3930, rich_4070) are excluded up front with reasons.

## The run — honest backend-down null

The report's verification block records the backend DOWN (WinError 10061), the gold gate at 12/12 VALID, both clones clean, writes confined, and no lingering `%TEMP%` scratch. Every JSONL row carries `status="NOT-RUN"`, `resolved=null`, and the connection-refused reason; the per-arm table shows `0/0 (+6 not-run)` and VERDICT `NOT-RUN` for every arm, `BASELINE` for baseline. The VERDICT section states "NOT MEASURED — backend was down … the resolve/commit-timing numbers are NOT MEASURED and were NOT fabricated." No arm is declared a WINNER, so the no-win-without-clearing-the-bar constraint cannot be violated. The report is labeled LOCAL-ONLY / FREE-GATE-CANDIDATE in both the header and the caveat.

## Writes and clones

Independent checks: `git -C repos/rich status --porcelain` and the fastapi equivalent both returned empty (clean). Deliverables (`.md`, `.jsonl`, `decode_sweep.py`, `run_local.py`) all sit under `Gemma/kb/` and `Gemma/local_eval/`. No `submit_*` directory shows a modification time near this build (latest is 10/14). `GEMMA_EXPERIMENT_LOG.md` carries a later mtime than the deliverables, but its tail is a content-correctness-LoRA audit entry and a grep for decode-sweep terms finds only pre-existing study notes about the 0.13 submission — no decode-sweep build entry was appended, so the build did not edit the log. Treated as a mtime coincidence from a concurrent workflow, not a build violation.

</details>

<details>
<summary>File map</summary>

- `Gemma/local_eval/decode_sweep.py` — sweep runner: arm table, frozen task set + split, gold gate, per-cell agent-run-then-rp-4-score with caching, `--run-all` orchestration, report/JSONL writers.
- `Gemma/local_eval/run_local.py` — additive `FREQUENCY_PENALTY`/`PRESENCE_PENALTY` globals + guarded forwarding in `chat()` + two 0.0-default CLI flags.
- `Gemma/kb/audits/2026-10-15-decode-commitment-sweep.md` — report with verbatim bar, task set/split, per-arm table, NOT-MEASURED verdict, LOCAL-ONLY caveat.
- `Gemma/kb/audits/2026-10-15-decode-commitment-sweep.jsonl` — 96 NOT-RUN rows, resolved=null, backend-down reason.

</details>
