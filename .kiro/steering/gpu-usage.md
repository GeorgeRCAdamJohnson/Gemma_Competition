---
inclusion: always
---
# GPU usage for Gemma experiments (E4B, Kaggle/Colab L4)

Evidence: `GEMMA_EXPERIMENT_LOG.md` entries of 2026-11-21 ("vLLM log scan", "GPU-usage guidance"); scripts
`Outputs/_vllm_scan.py`, `Outputs/_vllm_concurrency_check.py`; data `kb/attempts.sqlite` (44 vLLM servers).
Status of each rule is marked VALIDATED (offline or on GPU) or PENDING; do not present a PENDING rule as established.

## Rules
1. **Size every A/B before launch.** Seed39 per-round verified sd is 1.47. To reach t >= 2: ~9 rounds per arm for
   +1.0 task/round, ~35 for +0.5, ~96 for +0.3. A 5-round A/B only detects about +1.5. State the detectable effect in
   the pre-registration. (VALIDATED offline.)
2. **Prefer mechanism metrics first.** Measure an intervention on outcomes that move in nearly every attempt
   (gold-hunk coverage, overlapping re-reads, overflow rate, first-edit file) before spending GPU on solve rate.
3. **Use 12 slots per L4 lane for E4B experiments at 32K** (TP1, gmu 0.85, KV cache 85,216 tokens = 13.03x). VALIDATED
   on GPU 2026-11-22 (`comfyops/e4b-slots-per-lane-8v12-r4`, 156 task/round pairs, identical policy): attempts per
   lane-hour x1.295 (105.0 vs 81.1; projection was x1.33), mean attempt x1.115 (357.5 s vs 320.7 s), none over 30 min,
   paired verified solves 45 vs 48 (-1.92 points; the pass line was -2.0), vLLM errors only context overflow.
   CAVEATS: the solve check passed by 0.08 points and overflows were 19 vs 13 attempts (12.2% vs 8.3%, not
   significant at this size). Keep reporting slots per lane in every pre-registration, and watch the overflow rate in
   runs at 12 slots; revert to 8 if a run shows a sustained overflow or solve-rate gap.
4. **Stopping an attempt at its first context overflow is outcome-neutral on all recorded data (experiments only).**
   0 of 1,305 overflow attempts were ever resolved. Overflow is NOT a single dead request: after the first one the
   agent keeps working (59% of logged overflow attempts made edits afterwards; 60% overflowed in 2+ separate bursts),
   and every attempt ends within 30 s of its LAST overflow, which records the error. The time after the first overflow
   is 11.7% of slot time. Use the early stop only in experiments that are not studying overflow recovery, and never in
   a scored submission. (Outcome-neutrality VALIDATED offline; implementation PENDING.)
5. **Context size costs concurrency.** 64K gives 7.11x and 131K 3.72x max concurrency, and those runs recovered no
   verified solves. Do not raise max_model_len to fix overflow without a pre-registered reason.
6. **Save server telemetry with every run.** Keep each lane's vLLM log, the lane id and timestamps beside the results
   (Colab `gpu_ab_run.py` currently does not), so runs join to load and errors in the intel DB. Rebuild the DB after
   pulling results: `python kb/attemptdb/build.py; python kb/attemptdb/verify.py`.
7. **Overflow log lines carry no size.** vLLM always reports "at least 27769 input tokens" (the 32,768 limit minus the
   5,000-token output reserve, plus one). Use the trace's per-step prompt_tokens for prompt sizes.
8. **Scorer parity.** These runs use TP1 per L4 lane; the competition scorer uses 4xL4 with TP4. Throughput and timing
   rules here apply to experiments, not to predictions of scorer wall time.
