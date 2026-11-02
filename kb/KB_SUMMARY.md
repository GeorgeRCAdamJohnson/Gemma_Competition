<!-- build-stamp: built=2026-11-02T13:52:33Z inputs=439dc3fe0c4c discovery=439dc3fe0c4c -->
Build stamp: built 2026-11-02T13:52:33Z Â· inputs 439dc3fe0c4c Â· freshness check: python c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\kb\build_kb.py check-fresh
BASELINE: steering says v6w @ 0.15 (ref 57098497, gemma-submission-protocol.md L23); curated baseline v6w @ 0.15 (ref 57098497); LB best main track (from pulled/submissions/20261101T055511Z.csv) ca5: pre-edit anchor-grep rule, no sub-agents, v10 config @ 0.20 (ref 57760641)
BASELINE CONFLICT: steering=v6w@0.15 57098497 curated=v6w@0.15 57098497 lb_best_main=ca5: pre-edit anchor-grep rule, no sub-agents, v10 config@0.20 57760641 (source pulled/submissions/20261101T055511Z.csv) — nothing adopted; the user decides (see curated/_proposed_updates.md)
SMALL-MODEL TRACK: lb_best_small=E4B ca5 anchor-grep: pre-edit rule, no sub-agents, v10 ca...@0.03 57807043 (source pulled/submissions/20261101T055511Z.csv); BASELINE CONFLICT (small-model): no curated small-model baseline

# KB_SUMMARY

## 2. Coverage
- run-dirs parsed: 102
- run-dir-failed: 20 ['comp_other/flexonafft_v2/output', 'kaggle_archive/ci-tools-probe/output', 'kaggle_archive/gemma-localizer-lora-train/output', 'kaggle_archive/gemma-sibling-conform-12b-a3/output', 'kaggle_archive/gemma-sibling-conform-12b-a5/output', 'kaggle_archive/gemma-sibling-conform-31b-a23-arm/output', 'kaggle_archive/gemma-sibling-conform-v10/output', 'kaggle_archive/gemma-sibling-conform-v22/output', 'kaggle_archive/gemma-sibling-conform-v6z/output', 'kaggle_archive/probe-models/output', 'kaggle_archive/probe-unq/output', 'kaggle_archive/tmpl-probe/output', 'kaggle_pkg/out_ci_probe', 'kaggle_pkg/out_ci_probe2', 'kaggle_pkg/out_tmpl', 'local_eval/pull_a23_out', 'probe_models/out', 'probe_unq/out', 'submit_size_12b/out_v2', 'submit_v6z/out_v6z']
- run-dir-empty: 3 ['submit_v22/out_v22', 'v2_gate_s05', 'v2_gate_s05b']
- pasted-logs: 14
- reference-logs (not our runs, 0 rows): ['compeition/data', 'compeition/getting started', 'getting_started/_cells.txt', 'kaggle_archive/archive_run.log', 'local_eval/decode_sweep_run.log', 'local_eval/decode_sweep_run2.log', 'local_eval/parity_rig/_forensic_4077.out.txt', 'local_eval/parity_rig/_gate_offline_17.log', 'train/_ab12b_ourbase_run.log', 'train/_ab12b_run.log', 'train/_ab12b_spec.log'] [LIVE snapshot â€” this list reflects files present at build time; a file appearing/vanishing in local_eval/runs/ correctly trips freshness]
- staged-submissions: ['submit_branch_final', 'submit_t4096']
- trace files parsed: 4083
- runs.jsonl rows: 5863
- beyond walk depth: []

### Rows by run_kind / track (REV5 R5.2)
- by run_kind: kaggle-kernel=1750, kaggle-pulled=40, kaggle-pulled-legacy=4, local-rig=2289, local-sweep=1574, pasted-log=206
- by (platform, track): kaggle/dev-proxy=59, kaggle/main=1177, kaggle/small-model=764, local-rig/dev-proxy=1350, local-rig/main=189, local-rig/small-model=750, local-sweep/dev-proxy=759, local-sweep/small-model=815
- kaggle-eval-runs: 7; rig-runs: 228; sweep-tags: 779; pulled-runs: ['kb/pulled/gemma-sibling-conform-v1/20261101T062706Z', 'kb/pulled/gemma-sibling-conform-v11/20261101T062717Z', 'kb/pulled/gemma-sibling-conform-v15-cpu/20261101T061857Z', 'kb/pulled/gemma-sibling-conform-v16/20261101T062742Z', 'kb/pulled/gemma-sibling-conform-v17/20261101T062757Z', 'kb/pulled/gemma-sibling-conform-v2/20261101T062807Z', 'kb/pulled/gemma-sibling-conform-v20/20261101T062819Z', 'kb/pulled/v6w_temp1_probe']; partial: []
- foreign tools (listed, never run): ['EXPERIMENT_KB.sqlite', 'build_kb.py', 'kb_query.py']
- reference kernels (not ours): ['comp_other/flexonafft_v2', 'comp_other/matterhorn_superagent', 'competitor_probe', 'getting_started']
- outcome sources: None=764, kernel-log=1077, recovered-proxy=120, sweep-pinned=1378, sweep-raw=196, task_results=2328

### Staged submissions and scored zips (D3-4: config + zip_drift)
| dir | kind | zip_drift | config |
|---|---|---|---|
| submit_branch_final | staged-submission | MATCH | model=gemma-4-31b-it-qat-w4a16-ct budget=28/8/80/240 temp=0.2 top_k=- thinking=1024 tools=9 prompt=8da2005aaea1 |
| submit_t4096 | staged-submission | MATCH | model=gemma-4-31b-it-qat-w4a16-ct budget=28/8/80/240 temp=0.2 top_k=- thinking=4096 tools=9 prompt=9c2fa3587f25 |
| kaggle_archive/gemma-sibling-conform-v15-cpu/output | scored-zip | MATCH | model=gemma-4-31b-it-qat-w4a16-ct budget=12/5/20/120 temp=0.2 top_k=- thinking=256 tools=9 prompt=144651bd11db |
| kaggle_archive/gemma-sibling-conform-v7-d-t4x2/output | scored-zip | MATCH | model=gemma-4-31b-it-qat-w4a16-ct budget=28/8/80/240 temp=0.2 top_k=- thinking=4096 tools=9 prompt=de1dbc39103a |
| kaggle_archive/gemma-submission-packager-a25-router/output | scored-zip | MATCH | model=- budget=28/8/120/300 temp=- top_k=- thinking=- tools=- prompt=702183a6d3ee |
| kaggle_archive/gemma-submission-packager-ca5-anchor/output | scored-zip | MATCH | model=gemma-4-31b-it-qat-w4a16-ct budget=28/8/120/300 temp=0.2 top_k=- thinking=4096 tools=9 prompt=b9aeaa9a53ce |
| kaggle_archive/gemma-submission-packager/output | scored-zip | MATCH | model=gemma-4-31b-it-qat-w4a16-ct budget=28/8/80/240 temp=0.2 top_k=- thinking=1024 tools=9 prompt=e2c069d494e8 |
| kb/pulled/gemma-sibling-conform-v15-cpu/20261101T061857Z | scored-zip | MATCH | model=gemma-4-31b-it-qat-w4a16-ct budget=12/5/20/120 temp=0.2 top_k=- thinking=256 tools=9 prompt=144651bd11db |
| local_eval/out_submit_mobile | scored-zip | MATCH | model=gemma-4-31b-it-qat-w4a16-ct budget=28/8/120/300 temp=0.2 top_k=- thinking=4096 tools=9 prompt=b9aeaa9a53ce |
| local_eval/pull_packager_a25_out | scored-zip | MATCH | model=- budget=28/8/120/300 temp=- top_k=- thinking=- tools=- prompt=702183a6d3ee |
| local_eval/pull_packager_ca5_out | scored-zip | MATCH | model=gemma-4-31b-it-qat-w4a16-ct budget=28/8/120/300 temp=0.2 top_k=- thinking=4096 tools=9 prompt=b9aeaa9a53ce |
| local_eval/pull_packager_out | scored-zip | MATCH | model=gemma-4-31b-it-qat-w4a16-ct budget=28/8/80/240 temp=0.2 top_k=- thinking=1024 tools=9 prompt=e2c069d494e8 |
| submit_A17_31b | scored-zip | MATCH | model=gemma-4-31b-it-qat-w4a16-ct budget=28/8/80/240 temp=0.2 top_k=- thinking=1024 tools=9 prompt=42632a8e23f4 |
| submit_v6w_12b/out | scored-zip | MATCH | model=gemma-4-12b-it-qat-w4a16-ct budget=28/8/80/240 temp=0.2 top_k=- thinking=1024 tools=9 prompt=9c2fa3587f25 |
| submit_v6w_budget/out | scored-zip | MATCH | model=gemma-4-31b-it-qat-w4a16-ct budget=100/60/500/240 temp=0.2 top_k=- thinking=1024 tools=9 prompt=9c2fa3587f25 |
| submit_v7_d/kaggle_output | scored-zip | MATCH | model=gemma-4-31b-it-qat-w4a16-ct budget=28/8/80/240 temp=0.2 top_k=- thinking=4096 tools=9 prompt=de1dbc39103a |
| submit_v7_d/kaggle_output_v2 | scored-zip | DRIFT(['<bad zip>']) | model=- budget=-/-/-/- temp=- top_k=- thinking=- tools=- prompt=de1dbc39103a |
| submit_v7_d/out | scored-zip | MATCH | model=gemma-4-31b-it-qat-w4a16-ct budget=28/8/80/240 temp=0.2 top_k=- thinking=4096 tools=9 prompt=de1dbc39103a |
| submit_v7_temp1/out | scored-zip | MATCH | model=gemma-4-31b-it-qat-w4a16-ct budget=28/8/80/240 temp=1.0 top_k=64 thinking=1024 tools=9 prompt=9c2fa3587f25 |
- submission zip archives (local_eval/pull_submissions): ['local_eval/pull_submissions/57424022_Lets_go_bishes.zip', 'local_eval/pull_submissions/57470483_Why_not.zip', 'local_eval/pull_submissions/57530249_sadgdvzxgv.zip', 'local_eval/pull_submissions/57551592_again.zip', 'local_eval/pull_submissions/57582998_Lucy.zip']
- LB snapshots: ['local_eval/leaderboard/lb.csv']

### Since the previous build (2026-10-16T07:16:10Z; D5-6)
- 1390 discovered sources have mtime newer than the previous build stamp, in 314 groups (members listed per group).
| kind | path | n | parsed | reason | members |
|---|---|---|---|---|---|
| foreign-tool | . | 3 | no | the user's own tool; listed, never run | EXPERIMENT_KB.sqlite, build_kb.py, kb_query.py |
| kaggle-eval-run | kaggle_archive/ca5-31b-full129-eval/output | 1 | yes | outcomes from task_results.jsonl (no resolved= lines); rows emitted | - |
| kaggle-eval-run | kaggle_archive/ca5-e4b-full129-eval/output | 1 | yes | outcomes from task_results.jsonl (no resolved= lines); rows emitted | - |
| kaggle-eval-run | kaggle_pkg | 5 | yes | outcomes from task_results.jsonl (no resolved= lines); rows emitted | out_e4b, out_e4b_r2, out_e4b_v3, out_v6, out_v7 |
| large-binary | kaggle_archive/gemma-localizer-lora-train/output/localizer_v1_adapter.zip | 1 | no | over 50 MB, not read | - |
| large-binary | kaggle_archive/gemma-sibling-conform-v11/output/submission.zip | 1 | no | over 50 MB, not read | - |
| large-binary | kaggle_archive/gemma-sibling-conform-v19-lora/output/submission.zip | 1 | no | over 50 MB, not read | - |
| large-binary | kaggle_pkg/snapshots_ds/snapshots.tar | 1 | no | over 50 MB, not read | - |
| large-binary | local_eval/snapshots | 115 | no | over 50 MB, not read | fastapi_11194.tgz, fastapi_11355.tgz, fastapi_12942.tgz, fastapi_13207.tgz, fastapi_13537.tgz, fastapi_13713.tgz, fastapi_13786.tgz, fastapi_13920.tgz, fastapi_14077.tgz, fastapi_14099.tgz, fastapi_14186.tgz, fastapi_14246.tgz, fastapi_14258.tgz, fastapi_14262.tgz, fastapi_14266.tgz, fastapi_14297.tgz, fastapi_14301.tgz, fastapi_14303.tgz, fastapi_14306.tgz, fastapi_14349.tgz, fastapi_14356.tgz, fastapi_14360.tgz, fastapi_14361.tgz, fastapi_14371.tgz, fastapi_14372.tgz, fastapi_14419.tgz, fastapi_14430.tgz, fastapi_14448.tgz, fastapi_14455.tgz, fastapi_14458.tgz, fastapi_14459.tgz, fastapi_14463.tgz, fastapi_14479.tgz, fastapi_14482.tgz, fastapi_14485.tgz, fastapi_14487.tgz, fastapi_14492.tgz, fastapi_14512.tgz, fastapi_14583.tgz, fastapi_14605.tgz, fastapi_14609.tgz, fastapi_14616.tgz, fastapi_14786.tgz, fastapi_14791.tgz, fastapi_14794.tgz, fastapi_14851.tgz, fastapi_14873.tgz, fastapi_14953.tgz, fastapi_14962.tgz, fastapi_14964.tgz, fastapi_14978.tgz, fastapi_14986.tgz, fastapi_15023.tgz, fastapi_15030.tgz, fastapi_15280.tgz, fastapi_15588.tgz, fastapi_15589.tgz, fastapi_15661.tgz, fastapi_15745.tgz, fastapi_15763.tgz, fastapi_15785.tgz, fastapi_15800.tgz, fastapi_5077.tgz, fastapi_5624.tgz, fastapi_9425.tgz, fastapi_9555.tgz, fastapi_9753.tgz, rich_2725.tgz, rich_2943.tgz, rich_3006.tgz, rich_3043.tgz, rich_3052.tgz, rich_3061.tgz, rich_3063.tgz, rich_3064.tgz, rich_3067.tgz, rich_3105.tgz, rich_3130.tgz, rich_3180.tgz, rich_3278.tgz, rich_3296.tgz, rich_3454.tgz, rich_3468.tgz, rich_3469.tgz, rich_3470.tgz, rich_3471.tgz, rich_3472.tgz, rich_3480.tgz, rich_3486.tgz, rich_3506.tgz, rich_3518.tgz, rich_3521.tgz, rich_3535.tgz, rich_3675.tgz, rich_3676.tgz, rich_3718.tgz, rich_3772.tgz, rich_3777.tgz, rich_3782.tgz, rich_3882.tgz, rich_3894.tgz, rich_3905.tgz, rich_3930.tgz, rich_3934.tgz, rich_3935.tgz, rich_3938.tgz, rich_3942.tgz, rich_3944.tgz, rich_3953.tgz, rich_4006.tgz, rich_4070.tgz, rich_4075.tgz, rich_4076.tgz, rich_4077.tgz, rich_4079.tgz |
| large-binary | train/gemma4-12b-it-ours-q4_0.gguf | 1 | no | over 50 MB, not read | - |
| lb-snapshot | local_eval/leaderboard/lb.csv | 1 | no | public LB snapshot; read by the LB step (FEAT-002) | - |
| pasted-log | Outputs | 3 | yes | - | 31b_A21_Arm, 31b_A23, Gemma_Sibling-conform_31b_A3_Hard_version10 |
| pulled-run | kb/pulled/gemma-sibling-conform-v1/20261101T062706Z | 1 | yes | rows emitted | - |
| pulled-run | kb/pulled/gemma-sibling-conform-v11/20261101T062717Z | 1 | yes | rows emitted | - |
| pulled-run | kb/pulled/gemma-sibling-conform-v15-cpu/20261101T061857Z | 1 | yes | 0 rows | - |
| pulled-run | kb/pulled/gemma-sibling-conform-v16/20261101T062742Z | 1 | yes | rows emitted | - |
| pulled-run | kb/pulled/gemma-sibling-conform-v17/20261101T062757Z | 1 | yes | rows emitted | - |
| pulled-run | kb/pulled/gemma-sibling-conform-v2/20261101T062807Z | 1 | yes | rows emitted | - |
| pulled-run | kb/pulled/gemma-sibling-conform-v20/20261101T062819Z | 1 | yes | rows emitted | - |
| pulled-source | kb/pulled/gemma-sibling-conform-v1/20261101T062706Z/source | 1 | no | kernel source pulled with -m; read for its pulled run | - |
| pulled-source | kb/pulled/gemma-sibling-conform-v11/20261101T062717Z/source | 1 | no | kernel source pulled with -m; read for its pulled run | - |
| pulled-source | kb/pulled/gemma-sibling-conform-v15-cpu/20261101T061857Z/source | 1 | no | kernel source pulled with -m; read for its pulled run | - |
| pulled-source | kb/pulled/gemma-sibling-conform-v16/20261101T062742Z/source | 1 | no | kernel source pulled with -m; read for its pulled run | - |
| pulled-source | kb/pulled/gemma-sibling-conform-v17/20261101T062757Z/source | 1 | no | kernel source pulled with -m; read for its pulled run | - |
| pulled-source | kb/pulled/gemma-sibling-conform-v2/20261101T062807Z/source | 1 | no | kernel source pulled with -m; read for its pulled run | - |
| pulled-source | kb/pulled/gemma-sibling-conform-v20/20261101T062819Z/source | 1 | no | kernel source pulled with -m; read for its pulled run | - |
| reference-log | kaggle_archive/archive_run.log | 1 | no | result-like lines outside pasted-log locations | - |
| reference-log | local_eval | 2 | no | result-like lines outside pasted-log locations | decode_sweep_run.log, decode_sweep_run2.log |
| reference-log | local_eval/parity_rig | 2 | no | result-like lines outside pasted-log locations | _forensic_4077.out.txt, _gate_offline_17.log |
| rig-run | local_eval/parity_rig | 4 | yes | rows emitted | m12_official_smoke, m12_smoke, m1_results, m1_router |
| rig-run | local_eval/parity_rig/m1_batch/ctrl | 11 | yes | rows emitted | r0, r1, r10, r2, r3, r4, r5, r6, r7, r8, r9 |
| rig-run | local_eval/parity_rig/m1_batch/router | 3 | yes | rows emitted | r0, r1, r2 |
| rig-run | local_eval/parity_rig/m1_batch_multi/b12 | 3 | yes | rows emitted | r0, r1, r2 |
| rig-run | local_eval/parity_rig/m1_batch_multi/ca5 | 29 | yes | rows emitted | r1, r10, r11, r12, r13, r14, r15, r16, r17, r18, r19, r2, r20, r21, r22, r23, r24, r25, r26, r27, r28, r29, r3, r4, r5, r6, r7, r8, r9 |
| rig-run | local_eval/parity_rig/m1_batch_multi/ddv2_4077 | 24 | yes | rows emitted | r0, r1, r10, r11, r12, r13, r14, r15, r16, r17, r18, r19, r2, r20, r21, r22, r23, r3, r4, r5, r6, r7, r8, r9 |
| rig-run | local_eval/parity_rig/m1_batch_multi/ddv3_4077 | 24 | yes | rows emitted | r0, r1, r10, r11, r12, r13, r14, r15, r16, r17, r18, r19, r2, r20, r21, r22, r23, r3, r4, r5, r6, r7, r8, r9 |
| rig-run | local_eval/parity_rig/m1_batch_multi/ddv4077 | 24 | yes | rows emitted | r0, r1, r10, r11, r12, r13, r14, r15, r16, r17, r18, r19, r2, r20, r21, r22, r23, r3, r4, r5, r6, r7, r8, r9 |
| rig-run | local_eval/parity_rig/m1_batch_multi/off12 | 13 | yes | rows emitted | r0, r1, r10, r11, r12, r2, r3, r4, r5, r6, r7, r8, r9 |
| rig-run | local_eval/parity_rig/m1_batch_multi/off4077 | 5 | yes | rows emitted | r0, r1, r2, r3, r4 |
| rig-run | local_eval/parity_rig/m1_batch_multi/off4077t | 24 | yes | rows emitted | r0, r1, r10, r11, r12, r13, r14, r15, r16, r17, r18, r19, r2, r20, r21, r22, r23, r3, r4, r5, r6, r7, r8, r9 |
| rig-run | local_eval/parity_rig/m1_batch_multi/t0 | 3 | yes | rows emitted | r0, r1, r2 |
| rig-run | local_eval/parity_rig/m1_batch_multi/t1024 | 3 | yes | rows emitted | r0, r1, r2 |
| rig-run | local_eval/parity_rig/m1_batch_multi/t2048 | 3 | yes | rows emitted | r0, r1, r2 |
| rig-run | local_eval/parity_rig/m1_batch_multi/t512 | 3 | yes | rows emitted | r0, r1, r2 |
| rig-run | local_eval/parity_rig/m1_batch_multi/tk0 | 3 | yes | rows emitted | r0, r1, r2 |
| rig-run | local_eval/parity_rig/m1_batch_multi/v4 | 2 | yes | rows emitted | r0, r1 |
| rig-run | local_eval/parity_rig/m1_batch_multi/v5 | 4 | yes | rows emitted | r0, r1, r2, r3 |
| rig-run | local_eval/parity_rig/m1_batch_multi/v6 | 2 | yes | rows emitted | r0, r1 |
| rig-run | local_eval/parity_rig/m1_batch_multi/v7 | 2 | yes | rows emitted | r0, r1 |
| rig-run | local_eval/parity_rig/m1_batch_v2/router_v2 | 3 | yes | rows emitted | r0, r1, r2 |
| rig-run | local_eval/parity_rig/m1_batch_v3/router_v3 | 3 | yes | rows emitted | r0, r1, r2 |
| rig-run | local_eval/parity_rig/m1_capped | 2 | yes | rows emitted | agent_ctrl_e4b_r0, agent_ctrl_e4b_r1 |
| rig-run | local_eval/parity_rig/m1_faithful/agent_ctrl_e4b_r0 | 1 | yes | rows emitted | - |
| rig-run | local_eval/parity_rig/m1_full129 | 3 | yes | rows emitted | ca5, ca5_v2, off12_r0 |
| rig-run | local_eval/parity_rig/m1_locate | 6 | yes | rows emitted | agent_ctrl_12b_locate_r0, agent_ctrl_e4b_def2_r0, agent_ctrl_e4b_def_r0, agent_ctrl_e4b_locate_r0, agent_ctrl_e4b_r0, agent_ctrl_e4b_t512_r0 |
| rig-run | local_eval/parity_rig/m1_noprompt/agent_ctrl_e4b_noprompt_r0 | 1 | yes | rows emitted | - |
| rig-run | local_eval/parity_rig/m1_noprompt129/agent_ctrl_e4b_noprompt_r0 | 1 | yes | rows emitted | - |
| rig-run | local_eval/parity_rig/m1_refdef/agent_ctrl_e4b_def_r0 | 1 | yes | rows emitted | - |
| rig-run | local_eval/parity_rig/m1_skilltest | 18 | yes | rows emitted | cap15_r0, cmp15_r0, cmp28_r0, cmp28_r1, cmp28_r9, gated_r0, gated_r1, nosub_r0, retry2_r0, retry2_r1, retry2_r2, retry2_r9, retry_r0, retry_r1, retry_r2, retry_r9, tw_r0, tw_r9 |
| run-dir | . | 3 | yes | rows emitted | out_k_e4ba3, out_k_e4ba5, out_repeat_v2 |
| run-dir | kaggle_archive/gemma-sibling-conform-12b-a10-ones-oracle-9t/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-12b-a11-tight-fails/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-12b-a13-nol48-fails/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-12b-a14-tmp-fix/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-12b-a3-9t/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-12b-a3-rerun3006/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-12b-a5-9t/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-12b-a5-rerun3006/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-12b-a6-r3006/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-31b-a21-arm/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-31b-a22-arm/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-31b-a3-hard/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-cover-rich/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-e4b-a3/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-e4b-a5/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-m12/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-remap-e2b/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-remap-e4b/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-repeat-live/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-size-12b/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-size-e2b/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-size-e4b/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v1/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v11/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v16/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v17/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v18/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v19/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v19-lora/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v19v3/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v2/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v20/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v21/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v5/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v6/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v6b/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v6c/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v6s-stock-prompt-control/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v6t/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v6u/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v6v/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v6w/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v6x/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v6y/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v7-d-l4x4/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v7-e2b/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gemma-sibling-conform-v7-e4b/output | 1 | yes | rows emitted | - |
| run-dir | kaggle_archive/gold-fastapi/output | 1 | yes | 0 rows | - |
| run-dir | kaggle_archive/replay-base/output | 1 | yes | 0 rows | - |
| run-dir | kaggle_archive/replay-k10/output | 1 | yes | 0 rows | - |
| run-dir | kaggle_archive/replay-verify/output | 1 | yes | 0 rows | - |
| run-dir | kaggle_pkg | 4 | yes | 0 rows | out_gold_fa, out_replay, out_replay_base, out_replay_k10 |
| run-dir | local_eval | 4 | yes | rows emitted | pull_31ba3hard_out, pull_31ba3hard_v11_out, pull_a21_out, pull_a22_out |
| run-dir | submit_cover_rich/out_v5 | 1 | yes | rows emitted | - |
| run-dir | submit_remap_e2b/out_v1 | 1 | yes | rows emitted | - |
| run-dir | submit_remap_e4b/out_v1 | 1 | yes | rows emitted | - |
| run-dir | submit_repeat_live/out_v1 | 1 | yes | rows emitted | - |
| run-dir | submit_size_12b/out_v3 | 1 | yes | rows emitted | - |
| run-dir | submit_size_e2b/out_v1 | 1 | yes | rows emitted | - |
| run-dir | submit_size_e4b/out_v1 | 1 | yes | rows emitted | - |
| run-dir | submit_v7_e2b/out_v2 | 1 | yes | rows emitted | - |
| run-dir | submit_v7_e4b/out_v2 | 1 | yes | rows emitted | - |
| run-dir-failed | kaggle_archive/ci-tools-probe/output | 1 | yes | 0 result rows | - |
| run-dir-failed | kaggle_archive/gemma-localizer-lora-train/output | 1 | yes | 0 result rows | - |
| run-dir-failed | kaggle_archive/gemma-sibling-conform-12b-a3/output | 1 | yes | 0 result rows | - |
| run-dir-failed | kaggle_archive/gemma-sibling-conform-12b-a5/output | 1 | yes | 0 result rows | - |
| run-dir-failed | kaggle_archive/gemma-sibling-conform-31b-a23-arm/output | 1 | yes | 0 result rows | - |
| run-dir-failed | kaggle_archive/gemma-sibling-conform-v10/output | 1 | yes | 0 result rows | - |
| run-dir-failed | kaggle_archive/gemma-sibling-conform-v22/output | 1 | yes | 0 result rows | - |
| run-dir-failed | kaggle_archive/gemma-sibling-conform-v6z/output | 1 | yes | 0 result rows | - |
| run-dir-failed | kaggle_archive/probe-models/output | 1 | yes | 0 result rows | - |
| run-dir-failed | kaggle_archive/probe-unq/output | 1 | yes | 0 result rows | - |
| run-dir-failed | kaggle_archive/tmpl-probe/output | 1 | yes | 0 result rows | - |
| run-dir-failed | kaggle_pkg | 3 | yes | 0 result rows | out_ci_probe, out_ci_probe2, out_tmpl |
| run-dir-failed | local_eval/pull_a23_out | 1 | yes | 0 result rows | - |
| run-dir-failed | probe_models/out | 1 | yes | 0 result rows | - |
| run-dir-failed | probe_unq/out | 1 | yes | 0 result rows | - |
| run-dir-failed | submit_size_12b/out_v2 | 1 | yes | 0 result rows | - |
| scored-zip | submit_A17_31b | 1 | yes | submission.zip vs submission/ (zip_drift) | - |
| scored-zip | kaggle_archive/gemma-sibling-conform-v15-cpu/output | 1 | yes | submission.zip vs submission/ (zip_drift) | - |
| scored-zip | kaggle_archive/gemma-sibling-conform-v7-d-t4x2/output | 1 | yes | submission.zip vs submission/ (zip_drift) | - |
| scored-zip | kaggle_archive/gemma-submission-packager/output | 1 | yes | submission.zip vs submission/ (zip_drift) | - |
| scored-zip | kaggle_archive/gemma-submission-packager-a25-router/output | 1 | yes | submission.zip vs submission/ (zip_drift) | - |
| scored-zip | kaggle_archive/gemma-submission-packager-ca5-anchor/output | 1 | yes | submission.zip vs submission/ (zip_drift) | - |
| scored-zip | kb/pulled/gemma-sibling-conform-v15-cpu/20261101T061857Z | 1 | yes | submission.zip vs submission/ (zip_drift) | - |
| scored-zip | local_eval | 4 | yes | submission.zip vs submission/ (zip_drift) | out_submit_mobile, pull_packager_a25_out, pull_packager_ca5_out, pull_packager_out |
| scored-zip | submit_v6w_12b/out | 1 | yes | submission.zip vs submission/ (zip_drift) | - |
| scored-zip | submit_v6w_budget/out | 1 | yes | submission.zip vs submission/ (zip_drift) | - |
| submission-zip-archive | local_eval/pull_submissions | 5 | yes | submission zip (config hashes) | 57424022_Lets_go_bishes.zip, 57470483_Why_not.zip, 57530249_sadgdvzxgv.zip, 57551592_again.zip, 57582998_Lucy.zip |
| submit-dir | . | 2 | yes | kernel_family=probe | probe_models, probe_unq |
| submit-dir | . | 38 | yes | kernel_family=sibling-conform | push_12b9_12ba3, push_12b9_12ba5, push_12b_12ba3, push_12b_12ba3r3006, push_12b_12ba5, push_12b_12ba5r3006, push_12b_12ba6r3006, push_12b_A10_9t, push_12b_A11_fails, push_12b_A13_fails, push_12b_A14_tmp, push_31b9_31ba3, push_31b9_31ba5, push_31b_31ba3, push_31b_31ba3broad, push_31b_31ba3hard, push_31b_31ba5, push_31b_31be1, push_31b_31be1broad, push_31b_31be1hard, push_31b_A17_full, push_e4b_all1s, push_e4b_e4ba3, push_e4b_e4ba5, submit_12b_arm, submit_A17_31b, submit_cover_rich, submit_remap_e2b, submit_remap_e4b, submit_repeat_live, submit_size_12b, submit_size_e2b, submit_size_e4b, submit_v6, submit_v6w, submit_v7, submit_v7_e2b, submit_v7_e4b |
| submit-dir | kaggle_archive/ca5-31b-full129-eval/src | 1 | yes | kernel_family=full129-eval | - |
| submit-dir | kaggle_archive/ca5-e4b-full129-eval/src | 1 | yes | kernel_family=full129-eval | - |
| submit-dir | kaggle_archive/ci-tools-probe/src | 1 | yes | kernel_family=probe | - |
| submit-dir | kaggle_archive/gemma-localizer-lora-train/src | 1 | yes | kernel_family=train | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-12b-a10-ones-oracle-9t/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-12b-a11-tight-fails/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-12b-a13-nol48-fails/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-12b-a14-tmp-fix/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-12b-a3/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-12b-a3-9t/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-12b-a3-rerun3006/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-12b-a5/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-12b-a5-9t/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-12b-a5-rerun3006/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-12b-a6-r3006/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-31b-a21-arm/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-31b-a22-arm/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-31b-a23-arm/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-31b-a3-hard/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-cover-rich/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-e4b-a3/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-e4b-a5/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-m12/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-remap-e2b/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-remap-e4b/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-repeat-live/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-size-12b/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-size-e2b/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-size-e4b/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v1/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v10/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v11/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v12/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v13/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v13-v2/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v14-rich/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v15/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v15-cpu/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v16/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v17/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v18/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v19/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v19-lora/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v19-lora-v2/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v19v3/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v2/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v20/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v21/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v22/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v3/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v4/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v5/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v6/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v6b/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v6c/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v6s-stock-prompt-control/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v6t/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v6u/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v6v/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v6w/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v6x/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v6y/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v6z/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v7/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v7-d-l4x4/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v7-d-t4x2/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v7-e2b/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v7-e4b/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-sibling-conform-v9/src | 1 | yes | kernel_family=sibling-conform | - |
| submit-dir | kaggle_archive/gemma-submission-packager/src | 1 | yes | kernel_family=packager | - |
| submit-dir | kaggle_archive/gemma-submission-packager-a25-router/src | 1 | yes | kernel_family=packager | - |
| submit-dir | kaggle_archive/gemma-submission-packager-ca5-anchor/src | 1 | yes | kernel_family=packager | - |
| submit-dir | kaggle_archive/gold-fastapi/src | 1 | yes | kernel_family=other | - |
| submit-dir | kaggle_archive/probe-models/src | 1 | yes | kernel_family=probe | - |
| submit-dir | kaggle_archive/probe-unq/src | 1 | yes | kernel_family=probe | - |
| submit-dir | kaggle_archive/replay-base/src | 1 | yes | kernel_family=other | - |
| submit-dir | kaggle_archive/replay-k10/src | 1 | yes | kernel_family=other | - |
| submit-dir | kaggle_archive/replay-verify/src | 1 | yes | kernel_family=other | - |
| submit-dir | kaggle_archive/tmpl-probe/src | 1 | yes | kernel_family=probe | - |
| submit-dir | kaggle_pkg | 3 | yes | kernel_family=full129-eval | push_129_e4b, push_129_e4b_cap15, push_129_off31 |
| submit-dir | kaggle_pkg | 4 | yes | kernel_family=other | push_gold_fa, push_replay, push_replay_base, push_replay_k10 |
| submit-dir | kaggle_pkg | 2 | yes | kernel_family=probe | push_ci_probe, push_tmpl |
| submit-dir | local_eval/push_submit_mobile | 1 | yes | kernel_family=other | - |
| submit-dir | local_eval | 3 | yes | kernel_family=packager | push_packager, push_packager_a25, push_packager_ca5 |
| submit-dir | local_eval | 10 | yes | kernel_family=sibling-conform | pull_31ba3hard_kern, pull_31ba3hard_v11, pull_a23_kern, pull_a3hard_v3, pull_a3hard_v4, pull_a3hard_v7, push_31b_a21, push_31b_a22, push_31b_a23, push_31b_a25 |
| sweep-tag | local_eval/runs/A18* | 8 | yes | summary-only rows (guard+results+trace); rows emitted | A18_r0_rich_2725, A18_r0_rich_2943, A18_r1_rich_2725, A18_r1_rich_2943, A18_r2_rich_2725, A18_r2_rich_2943, A18_r3_rich_2725, A18_r3_rich_2943 |
| sweep-tag | local_eval/runs/A3_r0_rich_2725 | 1 | no | no results/pinned file (trace) | - |
| sweep-tag | local_eval/runs/A3* | 22 | yes | summary-only rows (guard+results+trace); rows emitted | A3_r0_rich_2943, A3_r0_rich_3006, A3_r0_rich_3067, A3_r0_rich_3454, A3_r0_rich_3772, A3_r0_rich_3882, A3_r0_rich_3905, A3_r0_rich_4077, A3_r1_rich_2725, A3_r1_rich_2943, A3_r1_rich_3006, A3_r1_rich_3067, A3_r1_rich_3454, A3_r1_rich_3772, A3_r1_rich_3882, A3_r1_rich_3905, A3_r1_rich_4077, A3_r2_rich_2725, A3_r2_rich_2943, A3_r2_rich_3067, A3_r3_rich_2725, A3_r3_rich_2943 |
| sweep-tag | local_eval/runs/D1* | 9 | yes | summary-only rows (guard+results+trace); rows emitted | D1_r0_rich_2725, D1_r0_rich_2943, D1_r0_rich_3067, D1_r1_rich_2725, D1_r1_rich_2943, D1_r1_rich_3067, D1_r2_rich_2725, D1_r2_rich_2943, D1_r2_rich_3067 |
| sweep-tag | local_eval/runs/D2* | 9 | yes | summary-only rows (guard+results+trace); rows emitted | D2_r0_rich_2725, D2_r0_rich_2943, D2_r0_rich_3067, D2_r1_rich_2725, D2_r1_rich_2943, D2_r1_rich_3067, D2_r2_rich_2725, D2_r2_rich_2943, D2_r2_rich_3067 |
| sweep-tag | local_eval/runs/D3* | 9 | yes | summary-only rows (guard+results+trace); rows emitted | D3_r0_rich_2725, D3_r0_rich_2943, D3_r0_rich_3067, D3_r1_rich_2725, D3_r1_rich_2943, D3_r1_rich_3067, D3_r2_rich_2725, D3_r2_rich_2943, D3_r2_rich_3067 |
| sweep-tag | local_eval/runs/_contaminated | 1 | no | not attributable to a sweep tag; not parsed | - |
| sweep-tag | local_eval/runs/a18_anchor | 1 | no | aggregate .sweep.jsonl only (per-tag files are the row source) | - |
| sweep-tag | local_eval/runs/a20_1024 | 1 | no | aggregate .sweep.jsonl only (per-tag files are the row source) | - |
| sweep-tag | local_eval/runs/a20_1024_A20* | 18 | yes | summary-only rows (guard+pinned+results+trace); rows emitted | a20_1024_A20_r0_rich_2725, a20_1024_A20_r10_rich_2725, a20_1024_A20_r11_rich_2725, a20_1024_A20_r12_rich_2725, a20_1024_A20_r13_rich_2725, a20_1024_A20_r14_rich_2725, a20_1024_A20_r15_rich_2725, a20_1024_A20_r16_rich_2725, a20_1024_A20_r17_rich_2725, a20_1024_A20_r1_rich_2725, a20_1024_A20_r2_rich_2725, a20_1024_A20_r3_rich_2725, a20_1024_A20_r4_rich_2725, a20_1024_A20_r5_rich_2725, a20_1024_A20_r6_rich_2725, a20_1024_A20_r7_rich_2725, a20_1024_A20_r8_rich_2725, a20_1024_A20_r9_rich_2725 |
| sweep-tag | local_eval/runs/a20_1024_A3* | 18 | yes | summary-only rows (guard+pinned+results+trace); rows emitted | a20_1024_A3_r0_rich_2725, a20_1024_A3_r10_rich_2725, a20_1024_A3_r11_rich_2725, a20_1024_A3_r12_rich_2725, a20_1024_A3_r13_rich_2725, a20_1024_A3_r14_rich_2725, a20_1024_A3_r15_rich_2725, a20_1024_A3_r16_rich_2725, a20_1024_A3_r17_rich_2725, a20_1024_A3_r1_rich_2725, a20_1024_A3_r2_rich_2725, a20_1024_A3_r3_rich_2725, a20_1024_A3_r4_rich_2725, a20_1024_A3_r5_rich_2725, a20_1024_A3_r6_rich_2725, a20_1024_A3_r7_rich_2725, a20_1024_A3_r8_rich_2725, a20_1024_A3_r9_rich_2725 |
| sweep-tag | local_eval/runs/a24_1025 | 1 | no | aggregate .sweep.jsonl only (per-tag files are the row source) | - |
| sweep-tag | local_eval/runs/a24_1025_A24* | 125 | yes | summary-only rows (guard+pinned+results+trace); rows emitted | a24_1025_A24_r0_rich_2725, a24_1025_A24_r0_rich_2943, a24_1025_A24_r0_rich_3006, a24_1025_A24_r0_rich_3067, a24_1025_A24_r0_rich_3454, a24_1025_A24_r0_rich_3772, a24_1025_A24_r0_rich_3882, a24_1025_A24_r0_rich_3905, a24_1025_A24_r0_rich_4077, a24_1025_A24_r10_rich_2725, a24_1025_A24_r10_rich_2943, a24_1025_A24_r10_rich_3006, a24_1025_A24_r10_rich_3067, a24_1025_A24_r10_rich_3454, a24_1025_A24_r10_rich_3772, a24_1025_A24_r10_rich_3882, a24_1025_A24_r10_rich_3905, a24_1025_A24_r10_rich_4077, a24_1025_A24_r11_rich_2725, a24_1025_A24_r11_rich_2943, a24_1025_A24_r11_rich_3006, a24_1025_A24_r11_rich_3067, a24_1025_A24_r11_rich_3454, a24_1025_A24_r11_rich_3772, a24_1025_A24_r11_rich_3882, a24_1025_A24_r11_rich_3905, a24_1025_A24_r11_rich_4077, a24_1025_A24_r12_rich_2725, a24_1025_A24_r12_rich_2943, a24_1025_A24_r12_rich_3006, a24_1025_A24_r12_rich_3067, a24_1025_A24_r12_rich_3454, a24_1025_A24_r12_rich_3772, a24_1025_A24_r12_rich_3882, a24_1025_A24_r12_rich_3905, a24_1025_A24_r12_rich_4077, a24_1025_A24_r13_rich_2725, a24_1025_A24_r13_rich_2943, a24_1025_A24_r13_rich_3006, a24_1025_A24_r13_rich_3067, a24_1025_A24_r13_rich_3454, a24_1025_A24_r13_rich_3772, a24_1025_A24_r13_rich_3882, a24_1025_A24_r13_rich_3905, a24_1025_A24_r13_rich_4077, a24_1025_A24_r14_rich_2725, a24_1025_A24_r14_rich_2943, a24_1025_A24_r14_rich_3006, a24_1025_A24_r14_rich_3067, a24_1025_A24_r14_rich_3454, a24_1025_A24_r14_rich_3882, a24_1025_A24_r14_rich_3905, a24_1025_A24_r14_rich_4077, a24_1025_A24_r1_rich_2725, a24_1025_A24_r1_rich_2943, a24_1025_A24_r1_rich_3006, a24_1025_A24_r1_rich_3067, a24_1025_A24_r1_rich_3454, a24_1025_A24_r1_rich_3882, a24_1025_A24_r1_rich_3905, a24_1025_A24_r1_rich_4077, a24_1025_A24_r2_rich_2725, a24_1025_A24_r2_rich_2943, a24_1025_A24_r2_rich_3006, a24_1025_A24_r2_rich_3067, a24_1025_A24_r2_rich_3454, a24_1025_A24_r2_rich_3882, a24_1025_A24_r2_rich_3905, a24_1025_A24_r2_rich_4077, a24_1025_A24_r3_rich_2725, a24_1025_A24_r3_rich_2943, a24_1025_A24_r3_rich_3006, a24_1025_A24_r3_rich_3067, a24_1025_A24_r3_rich_3454, a24_1025_A24_r3_rich_3882, a24_1025_A24_r3_rich_3905, a24_1025_A24_r3_rich_4077, a24_1025_A24_r4_rich_2725, a24_1025_A24_r4_rich_2943, a24_1025_A24_r4_rich_3006, a24_1025_A24_r4_rich_3067, a24_1025_A24_r4_rich_3454, a24_1025_A24_r4_rich_3882, a24_1025_A24_r4_rich_3905, a24_1025_A24_r4_rich_4077, a24_1025_A24_r5_rich_2725, a24_1025_A24_r5_rich_2943, a24_1025_A24_r5_rich_3006, a24_1025_A24_r5_rich_3067, a24_1025_A24_r5_rich_3454, a24_1025_A24_r5_rich_3882, a24_1025_A24_r5_rich_3905, a24_1025_A24_r5_rich_4077, a24_1025_A24_r6_rich_2725, a24_1025_A24_r6_rich_2943, a24_1025_A24_r6_rich_3006, a24_1025_A24_r6_rich_3067, a24_1025_A24_r6_rich_3454, a24_1025_A24_r6_rich_3882, a24_1025_A24_r6_rich_3905, a24_1025_A24_r6_rich_4077, a24_1025_A24_r7_rich_2725, a24_1025_A24_r7_rich_2943, a24_1025_A24_r7_rich_3006, a24_1025_A24_r7_rich_3067, a24_1025_A24_r7_rich_3454, a24_1025_A24_r7_rich_3882, a24_1025_A24_r7_rich_3905, a24_1025_A24_r7_rich_4077, a24_1025_A24_r8_rich_2725, a24_1025_A24_r8_rich_2943, a24_1025_A24_r8_rich_3006, a24_1025_A24_r8_rich_3067, a24_1025_A24_r8_rich_3454, a24_1025_A24_r8_rich_3882, a24_1025_A24_r8_rich_3905, a24_1025_A24_r8_rich_4077, a24_1025_A24_r9_rich_2725, a24_1025_A24_r9_rich_2943, a24_1025_A24_r9_rich_3006, a24_1025_A24_r9_rich_3067, a24_1025_A24_r9_rich_3454, a24_1025_A24_r9_rich_3882, a24_1025_A24_r9_rich_3905, a24_1025_A24_r9_rich_4077 |
| sweep-tag | local_eval/runs/a24_1025_A24* | 10 | yes | summary-only rows (guard+results+trace); rows emitted | a24_1025_A24_r14_rich_3772, a24_1025_A24_r1_rich_3772, a24_1025_A24_r2_rich_3772, a24_1025_A24_r3_rich_3772, a24_1025_A24_r4_rich_3772, a24_1025_A24_r5_rich_3772, a24_1025_A24_r6_rich_3772, a24_1025_A24_r7_rich_3772, a24_1025_A24_r8_rich_3772, a24_1025_A24_r9_rich_3772 |
| sweep-tag | local_eval/runs/a24_1025_A3* | 120 | yes | summary-only rows (guard+pinned+results+trace); rows emitted | a24_1025_A3_r0_rich_2725, a24_1025_A3_r0_rich_2943, a24_1025_A3_r0_rich_3006, a24_1025_A3_r0_rich_3067, a24_1025_A3_r0_rich_3454, a24_1025_A3_r0_rich_3882, a24_1025_A3_r0_rich_3905, a24_1025_A3_r0_rich_4077, a24_1025_A3_r10_rich_2725, a24_1025_A3_r10_rich_2943, a24_1025_A3_r10_rich_3006, a24_1025_A3_r10_rich_3067, a24_1025_A3_r10_rich_3454, a24_1025_A3_r10_rich_3882, a24_1025_A3_r10_rich_3905, a24_1025_A3_r10_rich_4077, a24_1025_A3_r11_rich_2725, a24_1025_A3_r11_rich_2943, a24_1025_A3_r11_rich_3006, a24_1025_A3_r11_rich_3067, a24_1025_A3_r11_rich_3454, a24_1025_A3_r11_rich_3882, a24_1025_A3_r11_rich_3905, a24_1025_A3_r11_rich_4077, a24_1025_A3_r12_rich_2725, a24_1025_A3_r12_rich_2943, a24_1025_A3_r12_rich_3006, a24_1025_A3_r12_rich_3067, a24_1025_A3_r12_rich_3454, a24_1025_A3_r12_rich_3882, a24_1025_A3_r12_rich_3905, a24_1025_A3_r12_rich_4077, a24_1025_A3_r13_rich_2725, a24_1025_A3_r13_rich_2943, a24_1025_A3_r13_rich_3006, a24_1025_A3_r13_rich_3067, a24_1025_A3_r13_rich_3454, a24_1025_A3_r13_rich_3882, a24_1025_A3_r13_rich_3905, a24_1025_A3_r13_rich_4077, a24_1025_A3_r14_rich_2725, a24_1025_A3_r14_rich_2943, a24_1025_A3_r14_rich_3006, a24_1025_A3_r14_rich_3067, a24_1025_A3_r14_rich_3454, a24_1025_A3_r14_rich_3882, a24_1025_A3_r14_rich_3905, a24_1025_A3_r14_rich_4077, a24_1025_A3_r1_rich_2725, a24_1025_A3_r1_rich_2943, a24_1025_A3_r1_rich_3006, a24_1025_A3_r1_rich_3067, a24_1025_A3_r1_rich_3454, a24_1025_A3_r1_rich_3882, a24_1025_A3_r1_rich_3905, a24_1025_A3_r1_rich_4077, a24_1025_A3_r2_rich_2725, a24_1025_A3_r2_rich_2943, a24_1025_A3_r2_rich_3006, a24_1025_A3_r2_rich_3067, a24_1025_A3_r2_rich_3454, a24_1025_A3_r2_rich_3882, a24_1025_A3_r2_rich_3905, a24_1025_A3_r2_rich_4077, a24_1025_A3_r3_rich_2725, a24_1025_A3_r3_rich_2943, a24_1025_A3_r3_rich_3006, a24_1025_A3_r3_rich_3067, a24_1025_A3_r3_rich_3454, a24_1025_A3_r3_rich_3882, a24_1025_A3_r3_rich_3905, a24_1025_A3_r3_rich_4077, a24_1025_A3_r4_rich_2725, a24_1025_A3_r4_rich_2943, a24_1025_A3_r4_rich_3006, a24_1025_A3_r4_rich_3067, a24_1025_A3_r4_rich_3454, a24_1025_A3_r4_rich_3882, a24_1025_A3_r4_rich_3905, a24_1025_A3_r4_rich_4077, a24_1025_A3_r5_rich_2725, a24_1025_A3_r5_rich_2943, a24_1025_A3_r5_rich_3006, a24_1025_A3_r5_rich_3067, a24_1025_A3_r5_rich_3454, a24_1025_A3_r5_rich_3882, a24_1025_A3_r5_rich_3905, a24_1025_A3_r5_rich_4077, a24_1025_A3_r6_rich_2725, a24_1025_A3_r6_rich_2943, a24_1025_A3_r6_rich_3006, a24_1025_A3_r6_rich_3067, a24_1025_A3_r6_rich_3454, a24_1025_A3_r6_rich_3882, a24_1025_A3_r6_rich_3905, a24_1025_A3_r6_rich_4077, a24_1025_A3_r7_rich_2725, a24_1025_A3_r7_rich_2943, a24_1025_A3_r7_rich_3006, a24_1025_A3_r7_rich_3067, a24_1025_A3_r7_rich_3454, a24_1025_A3_r7_rich_3882, a24_1025_A3_r7_rich_3905, a24_1025_A3_r7_rich_4077, a24_1025_A3_r8_rich_2725, a24_1025_A3_r8_rich_2943, a24_1025_A3_r8_rich_3006, a24_1025_A3_r8_rich_3067, a24_1025_A3_r8_rich_3454, a24_1025_A3_r8_rich_3882, a24_1025_A3_r8_rich_3905, a24_1025_A3_r8_rich_4077, a24_1025_A3_r9_rich_2725, a24_1025_A3_r9_rich_2943, a24_1025_A3_r9_rich_3006, a24_1025_A3_r9_rich_3067, a24_1025_A3_r9_rich_3454, a24_1025_A3_r9_rich_3882, a24_1025_A3_r9_rich_3905, a24_1025_A3_r9_rich_4077 |
| sweep-tag | local_eval/runs/a24_1025_A3* | 15 | yes | summary-only rows (guard+results+trace); rows emitted | a24_1025_A3_r0_rich_3772, a24_1025_A3_r10_rich_3772, a24_1025_A3_r11_rich_3772, a24_1025_A3_r12_rich_3772, a24_1025_A3_r13_rich_3772, a24_1025_A3_r14_rich_3772, a24_1025_A3_r1_rich_3772, a24_1025_A3_r2_rich_3772, a24_1025_A3_r3_rich_3772, a24_1025_A3_r4_rich_3772, a24_1025_A3_r5_rich_3772, a24_1025_A3_r6_rich_3772, a24_1025_A3_r7_rich_3772, a24_1025_A3_r8_rich_3772, a24_1025_A3_r9_rich_3772 |
| sweep-tag | local_eval/runs/abl2_A3* | 6 | yes | summary-only rows (pinned+results+trace); rows emitted | abl2_A3_r1, abl2_A3_r2, abl2_A3_r3, abl2_A3_r4, abl2_A3_r5, abl2_A3_r6 |
| sweep-tag | local_eval/runs/abl2_E1* | 6 | yes | summary-only rows (pinned+results+trace); rows emitted | abl2_E1_r1, abl2_E1_r2, abl2_E1_r3, abl2_E1_r4, abl2_E1_r5, abl2_E1_r6 |
| sweep-tag | local_eval/runs/abl3_A3_r1 | 1 | yes | summary-only rows (results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/abl3_probe | 1 | yes | summary-only rows (results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/abl_A3_r1 | 1 | yes | summary-only rows (pinned+results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/abl_E1_r1 | 1 | yes | summary-only rows (results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/capconv_ctrl | 1 | no | aggregate .sweep.jsonl only (per-tag files are the row source) | - |
| sweep-tag | local_eval/runs/capconv_ctrl_A3_r0_rich_3772 | 1 | no | no results/pinned file (guard+trace) | - |
| sweep-tag | local_eval/runs/capconv_ctrl_A3* | 76 | yes | summary-only rows (guard+pinned+results+trace); rows emitted | capconv_ctrl_A3_r0_fastapi_11194, capconv_ctrl_A3_r0_fastapi_13537, capconv_ctrl_A3_r0_fastapi_13713, capconv_ctrl_A3_r0_fastapi_13786, capconv_ctrl_A3_r0_fastapi_14077, capconv_ctrl_A3_r0_fastapi_14099, capconv_ctrl_A3_r0_fastapi_14258, capconv_ctrl_A3_r0_fastapi_14266, capconv_ctrl_A3_r0_fastapi_14301, capconv_ctrl_A3_r0_fastapi_14306, capconv_ctrl_A3_r0_fastapi_14371, capconv_ctrl_A3_r0_fastapi_14372, capconv_ctrl_A3_r0_fastapi_14419, capconv_ctrl_A3_r0_fastapi_14430, capconv_ctrl_A3_r0_fastapi_14458, capconv_ctrl_A3_r0_fastapi_14459, capconv_ctrl_A3_r0_fastapi_14463, capconv_ctrl_A3_r0_fastapi_14482, capconv_ctrl_A3_r0_fastapi_14485, capconv_ctrl_A3_r0_fastapi_14492, capconv_ctrl_A3_r0_fastapi_14512, capconv_ctrl_A3_r0_fastapi_14583, capconv_ctrl_A3_r0_fastapi_14605, capconv_ctrl_A3_r0_fastapi_14609, capconv_ctrl_A3_r0_fastapi_14616, capconv_ctrl_A3_r0_fastapi_14786, capconv_ctrl_A3_r0_fastapi_14794, capconv_ctrl_A3_r0_fastapi_14851, capconv_ctrl_A3_r0_fastapi_14873, capconv_ctrl_A3_r0_fastapi_15023, capconv_ctrl_A3_r0_fastapi_15280, capconv_ctrl_A3_r0_fastapi_15589, capconv_ctrl_A3_r0_fastapi_15745, capconv_ctrl_A3_r0_fastapi_15785, capconv_ctrl_A3_r0_fastapi_15800, capconv_ctrl_A3_r0_fastapi_5077, capconv_ctrl_A3_r0_fastapi_5624, capconv_ctrl_A3_r0_fastapi_9425, capconv_ctrl_A3_r0_fastapi_9555, capconv_ctrl_A3_r0_fastapi_9753, capconv_ctrl_A3_r0_rich_2725, capconv_ctrl_A3_r0_rich_2943, capconv_ctrl_A3_r0_rich_3006, capconv_ctrl_A3_r0_rich_3043, capconv_ctrl_A3_r0_rich_3061, capconv_ctrl_A3_r0_rich_3063, capconv_ctrl_A3_r0_rich_3064, capconv_ctrl_A3_r0_rich_3067, capconv_ctrl_A3_r0_rich_3105, capconv_ctrl_A3_r0_rich_3180, capconv_ctrl_A3_r0_rich_3278, capconv_ctrl_A3_r0_rich_3454, capconv_ctrl_A3_r0_rich_3469, capconv_ctrl_A3_r0_rich_3470, capconv_ctrl_A3_r0_rich_3471, capconv_ctrl_A3_r0_rich_3472, capconv_ctrl_A3_r0_rich_3480, capconv_ctrl_A3_r0_rich_3506, capconv_ctrl_A3_r0_rich_3518, capconv_ctrl_A3_r0_rich_3521, capconv_ctrl_A3_r0_rich_3718, capconv_ctrl_A3_r0_rich_3777, capconv_ctrl_A3_r0_rich_3782, capconv_ctrl_A3_r0_rich_3882, capconv_ctrl_A3_r0_rich_3894, capconv_ctrl_A3_r0_rich_3905, capconv_ctrl_A3_r0_rich_3930, capconv_ctrl_A3_r0_rich_3934, capconv_ctrl_A3_r0_rich_3935, capconv_ctrl_A3_r0_rich_3938, capconv_ctrl_A3_r0_rich_3942, capconv_ctrl_A3_r0_rich_4006, capconv_ctrl_A3_r0_rich_4075, capconv_ctrl_A3_r0_rich_4076, capconv_ctrl_A3_r0_rich_4077, capconv_ctrl_A3_r0_rich_4079 |
| sweep-tag | local_eval/runs/capconv_raised | 1 | no | aggregate .sweep.jsonl only (per-tag files are the row source) | - |
| sweep-tag | local_eval/runs/capconv_raised_A3* | 77 | yes | summary-only rows (guard+pinned+results+trace); rows emitted | capconv_raised_A3_r0_fastapi_11194, capconv_raised_A3_r0_fastapi_13537, capconv_raised_A3_r0_fastapi_13713, capconv_raised_A3_r0_fastapi_13786, capconv_raised_A3_r0_fastapi_14077, capconv_raised_A3_r0_fastapi_14099, capconv_raised_A3_r0_fastapi_14258, capconv_raised_A3_r0_fastapi_14266, capconv_raised_A3_r0_fastapi_14301, capconv_raised_A3_r0_fastapi_14306, capconv_raised_A3_r0_fastapi_14371, capconv_raised_A3_r0_fastapi_14372, capconv_raised_A3_r0_fastapi_14419, capconv_raised_A3_r0_fastapi_14430, capconv_raised_A3_r0_fastapi_14458, capconv_raised_A3_r0_fastapi_14459, capconv_raised_A3_r0_fastapi_14463, capconv_raised_A3_r0_fastapi_14482, capconv_raised_A3_r0_fastapi_14485, capconv_raised_A3_r0_fastapi_14492, capconv_raised_A3_r0_fastapi_14512, capconv_raised_A3_r0_fastapi_14583, capconv_raised_A3_r0_fastapi_14605, capconv_raised_A3_r0_fastapi_14609, capconv_raised_A3_r0_fastapi_14616, capconv_raised_A3_r0_fastapi_14786, capconv_raised_A3_r0_fastapi_14794, capconv_raised_A3_r0_fastapi_14851, capconv_raised_A3_r0_fastapi_14873, capconv_raised_A3_r0_fastapi_15023, capconv_raised_A3_r0_fastapi_15280, capconv_raised_A3_r0_fastapi_15589, capconv_raised_A3_r0_fastapi_15745, capconv_raised_A3_r0_fastapi_15785, capconv_raised_A3_r0_fastapi_15800, capconv_raised_A3_r0_fastapi_5077, capconv_raised_A3_r0_fastapi_5624, capconv_raised_A3_r0_fastapi_9425, capconv_raised_A3_r0_fastapi_9555, capconv_raised_A3_r0_fastapi_9753, capconv_raised_A3_r0_rich_2725, capconv_raised_A3_r0_rich_2943, capconv_raised_A3_r0_rich_3006, capconv_raised_A3_r0_rich_3043, capconv_raised_A3_r0_rich_3061, capconv_raised_A3_r0_rich_3063, capconv_raised_A3_r0_rich_3064, capconv_raised_A3_r0_rich_3067, capconv_raised_A3_r0_rich_3105, capconv_raised_A3_r0_rich_3180, capconv_raised_A3_r0_rich_3278, capconv_raised_A3_r0_rich_3454, capconv_raised_A3_r0_rich_3469, capconv_raised_A3_r0_rich_3470, capconv_raised_A3_r0_rich_3471, capconv_raised_A3_r0_rich_3472, capconv_raised_A3_r0_rich_3480, capconv_raised_A3_r0_rich_3506, capconv_raised_A3_r0_rich_3518, capconv_raised_A3_r0_rich_3521, capconv_raised_A3_r0_rich_3718, capconv_raised_A3_r0_rich_3772, capconv_raised_A3_r0_rich_3777, capconv_raised_A3_r0_rich_3782, capconv_raised_A3_r0_rich_3882, capconv_raised_A3_r0_rich_3894, capconv_raised_A3_r0_rich_3905, capconv_raised_A3_r0_rich_3930, capconv_raised_A3_r0_rich_3934, capconv_raised_A3_r0_rich_3935, capconv_raised_A3_r0_rich_3938, capconv_raised_A3_r0_rich_3942, capconv_raised_A3_r0_rich_4006, capconv_raised_A3_r0_rich_4075, capconv_raised_A3_r0_rich_4076, capconv_raised_A3_r0_rich_4077, capconv_raised_A3_r0_rich_4079 |
| sweep-tag | local_eval/runs/d_arms | 1 | no | aggregate .sweep.jsonl only (per-tag files are the row source) | - |
| sweep-tag | local_eval/runs/dur9_A3* | 11 | yes | summary-only rows (pinned+results+trace); rows emitted | dur9_A3_r1, dur9_A3_rep1, dur9_A3_rep10, dur9_A3_rep2, dur9_A3_rep3, dur9_A3_rep4, dur9_A3_rep5, dur9_A3_rep6, dur9_A3_rep7, dur9_A3_rep8, dur9_A3_rep9 |
| sweep-tag | local_eval/runs/dur9_A3_r2 | 1 | yes | summary-only rows (results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/dur9_A5* | 10 | yes | summary-only rows (pinned+results+trace); rows emitted | dur9_A5_rep1, dur9_A5_rep10, dur9_A5_rep2, dur9_A5_rep3, dur9_A5_rep4, dur9_A5_rep5, dur9_A5_rep6, dur9_A5_rep7, dur9_A5_rep8, dur9_A5_rep9 |
| sweep-tag | local_eval/runs/dur9_E1_r1 | 1 | yes | summary-only rows (pinned+results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/e4b_A1_par6* | 5 | yes | summary-only rows (pinned+results+trace); rows emitted | e4b_A1_par6_rep1, e4b_A1_par6_rep2, e4b_A1_par6_rep3, e4b_A1_par6_rep4, e4b_A1_par6_rep5 |
| sweep-tag | local_eval/runs/e4b_A2_par6* | 5 | yes | summary-only rows (pinned+results+trace); rows emitted | e4b_A2_par6_rep1, e4b_A2_par6_rep2, e4b_A2_par6_rep3, e4b_A2_par6_rep4, e4b_A2_par6_rep5 |
| sweep-tag | local_eval/runs/e4b_A2_rich44 | 1 | yes | summary-only rows (pinned+results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/e4b_A3_rich44 | 1 | yes | summary-only rows (pinned+results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/e4b_A3_rich44_rep2 | 1 | yes | summary-only rows (results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/e4b_A4_rich44 | 1 | yes | summary-only rows (pinned+results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/e4b_A5_rich44 | 1 | yes | summary-only rows (pinned+results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/e4b_arms_1024 | 1 | no | aggregate .sweep.jsonl only (per-tag files are the row source) | - |
| sweep-tag | local_eval/runs/e4b_arms_1024_A19* | 36 | yes | summary-only rows (guard+pinned+results+trace); rows emitted | e4b_arms_1024_A19_r0_rich_2725, e4b_arms_1024_A19_r0_rich_2943, e4b_arms_1024_A19_r10_rich_2725, e4b_arms_1024_A19_r10_rich_2943, e4b_arms_1024_A19_r11_rich_2725, e4b_arms_1024_A19_r11_rich_2943, e4b_arms_1024_A19_r12_rich_2725, e4b_arms_1024_A19_r12_rich_2943, e4b_arms_1024_A19_r13_rich_2725, e4b_arms_1024_A19_r13_rich_2943, e4b_arms_1024_A19_r14_rich_2725, e4b_arms_1024_A19_r14_rich_2943, e4b_arms_1024_A19_r15_rich_2725, e4b_arms_1024_A19_r15_rich_2943, e4b_arms_1024_A19_r16_rich_2725, e4b_arms_1024_A19_r16_rich_2943, e4b_arms_1024_A19_r17_rich_2725, e4b_arms_1024_A19_r17_rich_2943, e4b_arms_1024_A19_r1_rich_2725, e4b_arms_1024_A19_r1_rich_2943, e4b_arms_1024_A19_r2_rich_2725, e4b_arms_1024_A19_r2_rich_2943, e4b_arms_1024_A19_r3_rich_2725, e4b_arms_1024_A19_r3_rich_2943, e4b_arms_1024_A19_r4_rich_2725, e4b_arms_1024_A19_r4_rich_2943, e4b_arms_1024_A19_r5_rich_2725, e4b_arms_1024_A19_r5_rich_2943, e4b_arms_1024_A19_r6_rich_2725, e4b_arms_1024_A19_r6_rich_2943, e4b_arms_1024_A19_r7_rich_2725, e4b_arms_1024_A19_r7_rich_2943, e4b_arms_1024_A19_r8_rich_2725, e4b_arms_1024_A19_r8_rich_2943, e4b_arms_1024_A19_r9_rich_2725, e4b_arms_1024_A19_r9_rich_2943 |
| sweep-tag | local_eval/runs/e4b_arms_1024_A3* | 36 | yes | summary-only rows (guard+pinned+results+trace); rows emitted | e4b_arms_1024_A3_r0_rich_2725, e4b_arms_1024_A3_r0_rich_2943, e4b_arms_1024_A3_r10_rich_2725, e4b_arms_1024_A3_r10_rich_2943, e4b_arms_1024_A3_r11_rich_2725, e4b_arms_1024_A3_r11_rich_2943, e4b_arms_1024_A3_r12_rich_2725, e4b_arms_1024_A3_r12_rich_2943, e4b_arms_1024_A3_r13_rich_2725, e4b_arms_1024_A3_r13_rich_2943, e4b_arms_1024_A3_r14_rich_2725, e4b_arms_1024_A3_r14_rich_2943, e4b_arms_1024_A3_r15_rich_2725, e4b_arms_1024_A3_r15_rich_2943, e4b_arms_1024_A3_r16_rich_2725, e4b_arms_1024_A3_r16_rich_2943, e4b_arms_1024_A3_r17_rich_2725, e4b_arms_1024_A3_r17_rich_2943, e4b_arms_1024_A3_r1_rich_2725, e4b_arms_1024_A3_r1_rich_2943, e4b_arms_1024_A3_r2_rich_2725, e4b_arms_1024_A3_r2_rich_2943, e4b_arms_1024_A3_r3_rich_2725, e4b_arms_1024_A3_r3_rich_2943, e4b_arms_1024_A3_r4_rich_2725, e4b_arms_1024_A3_r4_rich_2943, e4b_arms_1024_A3_r5_rich_2725, e4b_arms_1024_A3_r5_rich_2943, e4b_arms_1024_A3_r6_rich_2725, e4b_arms_1024_A3_r6_rich_2943, e4b_arms_1024_A3_r7_rich_2725, e4b_arms_1024_A3_r7_rich_2943, e4b_arms_1024_A3_r8_rich_2725, e4b_arms_1024_A3_r8_rich_2943, e4b_arms_1024_A3_r9_rich_2725, e4b_arms_1024_A3_r9_rich_2943 |
| sweep-tag | local_eval/runs/e4b_arms_1024_D2* | 36 | yes | summary-only rows (guard+pinned+results+trace); rows emitted | e4b_arms_1024_D2_r0_rich_2725, e4b_arms_1024_D2_r0_rich_2943, e4b_arms_1024_D2_r10_rich_2725, e4b_arms_1024_D2_r10_rich_2943, e4b_arms_1024_D2_r11_rich_2725, e4b_arms_1024_D2_r11_rich_2943, e4b_arms_1024_D2_r12_rich_2725, e4b_arms_1024_D2_r12_rich_2943, e4b_arms_1024_D2_r13_rich_2725, e4b_arms_1024_D2_r13_rich_2943, e4b_arms_1024_D2_r14_rich_2725, e4b_arms_1024_D2_r14_rich_2943, e4b_arms_1024_D2_r15_rich_2725, e4b_arms_1024_D2_r15_rich_2943, e4b_arms_1024_D2_r16_rich_2725, e4b_arms_1024_D2_r16_rich_2943, e4b_arms_1024_D2_r17_rich_2725, e4b_arms_1024_D2_r17_rich_2943, e4b_arms_1024_D2_r1_rich_2725, e4b_arms_1024_D2_r1_rich_2943, e4b_arms_1024_D2_r2_rich_2725, e4b_arms_1024_D2_r2_rich_2943, e4b_arms_1024_D2_r3_rich_2725, e4b_arms_1024_D2_r3_rich_2943, e4b_arms_1024_D2_r4_rich_2725, e4b_arms_1024_D2_r4_rich_2943, e4b_arms_1024_D2_r5_rich_2725, e4b_arms_1024_D2_r5_rich_2943, e4b_arms_1024_D2_r6_rich_2725, e4b_arms_1024_D2_r6_rich_2943, e4b_arms_1024_D2_r7_rich_2725, e4b_arms_1024_D2_r7_rich_2943, e4b_arms_1024_D2_r8_rich_2725, e4b_arms_1024_D2_r8_rich_2943, e4b_arms_1024_D2_r9_rich_2725, e4b_arms_1024_D2_r9_rich_2943 |
| sweep-tag | local_eval/runs/e4b_par6* | 4 | yes | summary-only rows (pinned+results+trace); rows emitted | e4b_par6_rep2, e4b_par6_rep3, e4b_par6_rep4, e4b_par6_rep5 |
| sweep-tag | local_eval/runs/e4b_parity6 | 1 | yes | summary-only rows (pinned+results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/e4b_qat_par6* | 5 | yes | summary-only rows (pinned+results+trace); rows emitted | e4b_qat_par6_rep1, e4b_qat_par6_rep2, e4b_qat_par6_rep3, e4b_qat_par6_rep4, e4b_qat_par6_rep5 |
| sweep-tag | local_eval/runs/e4b_vllm88_par6* | 5 | yes | summary-only rows (pinned+results+trace); rows emitted | e4b_vllm88_par6_rep1, e4b_vllm88_par6_rep2, e4b_vllm88_par6_rep3, e4b_vllm88_par6_rep4, e4b_vllm88_par6_rep5 |
| sweep-tag | local_eval/runs/e4b_vllm_HFMAINTMPL_partial | 1 | yes | summary-only rows (results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/e4b_vllm_smoke | 1 | yes | summary-only rows (results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/fa18_A3* | 2 | yes | summary-only rows (results+trace); rows emitted | fa18_A3_r1, fa18_A3_r2 |
| sweep-tag | local_eval/runs/fin_A3_r1 | 1 | yes | summary-only rows (pinned+results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/fin_E1_r1 | 1 | no | no results/pinned file (trace) | - |
| sweep-tag | local_eval/runs/iso_A3_base | 1 | no | aggregate .sweep.jsonl only (per-tag files are the row source) | - |
| sweep-tag | local_eval/runs/kaggle_12b_v3.kscore.jsonl | 1 | no | not attributable to a sweep tag; not parsed | - |
| sweep-tag | local_eval/runs/kaggle_e2b_remap_v1.kscore.jsonl | 1 | no | not attributable to a sweep tag; not parsed | - |
| sweep-tag | local_eval/runs/kaggle_e4b_remap_v1.kscore.jsonl | 1 | no | not attributable to a sweep tag; not parsed | - |
| sweep-tag | local_eval/runs/llama_server_12b_ours_q4_0_20261029 | 1 | no | no results/pinned file (aux files only) | - |
| sweep-tag | local_eval/runs/llama_server_12b_q4km_20261029 | 1 | no | no results/pinned file (aux files only) | - |
| sweep-tag | local_eval/runs/llama_server_12b_q4km_bigctx_20261029 | 1 | no | no results/pinned file (aux files only) | - |
| sweep-tag | local_eval/runs/llama_server_12b_q8_20261029 | 1 | no | no results/pinned file (aux files only) | - |
| sweep-tag | local_eval/runs/llama_server_12b_q8_bigctx_20261029 | 1 | no | no results/pinned file (aux files only) | - |
| sweep-tag | local_eval/runs/llama_server_e4b | 1 | no | no results/pinned file (aux files only) | - |
| sweep-tag | local_eval/runs/llama_server_e4b_qat | 1 | no | no results/pinned file (aux files only) | - |
| sweep-tag | local_eval/runs/llama_server_e4b_qat_20261027 | 1 | no | no results/pinned file (aux files only) | - |
| sweep-tag | local_eval/runs/llama_server_e4b_qat_restore_20261029 | 1 | no | no results/pinned file (aux files only) | - |
| sweep-tag | local_eval/runs/p3772_A3* | 3 | yes | summary-only rows (guard+results+trace); rows emitted | p3772_A3_r1, p3772_A3_r2, p3772_A3_r3 |
| sweep-tag | local_eval/runs/p3772_P1_r4 | 1 | no | no results/pinned file (guard+trace) | - |
| sweep-tag | local_eval/runs/p3772_P1* | 3 | yes | summary-only rows (guard+results+trace); rows emitted | p3772_P1_r1, p3772_P1_r2, p3772_P1_r3 |
| sweep-tag | local_eval/runs/p3772_P2* | 3 | yes | summary-only rows (guard+results+trace); rows emitted | p3772_P2_r1, p3772_P2_r2, p3772_P2_r3 |
| sweep-tag | local_eval/runs/p3772_P3* | 3 | yes | summary-only rows (guard+results+trace); rows emitted | p3772_P3_r1, p3772_P3_r2, p3772_P3_r3 |
| sweep-tag | local_eval/runs/pilot_A2* | 2 | yes | summary-only rows (pinned+results+trace); rows emitted | pilot_A2_rep1, pilot_A2_rep2 |
| sweep-tag | local_eval/runs/pilot_A3* | 2 | yes | summary-only rows (pinned+results+trace); rows emitted | pilot_A3_rep1, pilot_A3_rep2 |
| sweep-tag | local_eval/runs/probe2 | 1 | yes | summary-only rows (results+trace); rows emitted | - |
| sweep-tag | local_eval/runs/v2_A3* | 5 | yes | summary-only rows (pinned+results+trace); rows emitted | v2_A3_r1, v2_A3_r3, v2_A3_r4, v2_A3_r5, v2_A3_r6 |
| sweep-tag | local_eval/runs/v2_A3_r2 | 1 | yes | summary-only rows (pinned+trace); rows emitted | - |
| sweep-tag | local_eval/runs/v2_E1* | 6 | yes | summary-only rows (pinned+results+trace); rows emitted | v2_E1_r1, v2_E1_r2, v2_E1_r3, v2_E1_r4, v2_E1_r5, v2_E1_r6 |
| sweep-tag | local_eval/runs/v3_A3* | 4 | yes | summary-only rows (pinned+results+trace); rows emitted | v3_A3_r1, v3_A3_r2, v3_A3_r3, v3_A3_r4 |
| sweep-tag | local_eval/runs/v3_E1* | 4 | yes | summary-only rows (pinned+results+trace); rows emitted | v3_E1_r1, v3_E1_r2, v3_E1_r3, v3_E1_r4 |
- GEMMA_EXPERIMENT_LOG.md: 181 new `## ` units after L10108 (first L10115, last L16963); parsed: yes (claims engine).

## 3. Task x run outcome matrix
- tasks attempted: 129; runs: 1096
- cell counts: ?=1358, F=168, I=4, L=586, N=510, R=1237, S=97, W=1903

Legend: R resolved · W wrong-fix · W* junk-patch-only · N landed-not-submitted · F found-not-landed · S saw-only · L locate · I infra · ? no-trace · · not-in-run · ~ tool-call malformation share>=0.5 · ^ edit after last submit

## 7. LB scores and live-best
- LB source: `pulled/submissions/20261101T055511Z.csv` â€” newest pulled snapshot 2026-11-01T05:55:11Z is newer than curated/submissions.csv (mtime 2026-10-16T01:33:34Z)
- dates: newest pulled snapshot 2026-11-01T05:55:11Z; curated/submissions.csv mtime 2026-10-16T01:33:34Z
- rows in LB source: 25

| ref | date | status | publicScore | track | description |
|---|---|---|---|---|---|
| 57847285 | 2026-10-31 18:24:26 | PENDING | - | main | ca5: pre-edit anchor-grep rule, no sub-agents, v10 config (resubmit of 0.20 pack ref 57... |
| 57807043 | 2026-10-30 13:38:29 | COMPLETE | 0.03 | small-model | E4B ca5 anchor-grep: pre-edit rule, no sub-agents, v10 caps (small-model candidate) |
| 57760641 | 2026-10-29 05:56:50 | COMPLETE | 0.20 | main | ca5: pre-edit anchor-grep rule, no sub-agents, v10 config |
| 57720023 | 2026-10-28 01:57:10 | COMPLETE | 0.13 | main | A25 router blind: classify-dispatch, 2 sub-agents, summarized returns, v10 caps |
| 57681095 | 2026-10-26 23:27:29 | COMPLETE | 0.15 | main | (no description) |
| 57640430 | 2026-10-25 19:04:53 | COMPLETE | 0.17 | main | .26? |
| 57582998 | 2026-10-24 04:58:00 | COMPLETE | 0.17 | main | Lucy |
| 57551592 | 2026-10-23 06:20:51 | COMPLETE | 0.12 | main | again |
| 57530249 | 2026-10-22 15:40:08 | COMPLETE | 0.18 | main | sadgdvzxgv |
| 57470483 | 2026-10-21 06:55:00 | COMPLETE | - | main | Why not |
| 57424022 | 2026-10-20 05:35:08 | COMPLETE | 0.18 | main | Lets go bishes |
| 57399296 | 2026-10-19 14:22:10 | COMPLETE | 0.15 | main | A17 @31B: v6c structure + time-first framing + de-hedged triggers + THE fix granularity |
| 57359160 | 2026-10-18 15:12:43 | COMPLETE | 0.13 | main | testing |
| 57317996 | 2026-10-17 16:23:56 | COMPLETE | - | dev-proxy | MODEL-SIZE LADDER, single axis vs v6w(0.15): agent.yaml model line only, gemma-4-31b-it... |
| 57276407 | 2026-10-16 16:51:32 | COMPLETE | - | main | BUDGET RAISE, single axis vs v6w(0.15): eval_config only. max_tool_calls 28->100, max_t... |
| 57201051 | 2026-10-15 01:15:05 | COMPLETE | 0.13 | main | v6w + temperature 1.0 / top_k 64 (only change vs the 0.15 v6w baseline) |
| 57146757 | 2026-10-13 14:31:31 | COMPLETE | 0.12 | main | PER-TASK BRANCHING: first use of ADK {problem_description} templating - system.md now i... |
| 57098497 | 2026-10-12 06:44:05 | COMPLETE | 0.15 | main | v6w: 0.18 budget (28/8/80/240) + 9-tool surface with edit_file primary + thinking_budge... |
| 57054171 | 2026-10-10 23:01:55 | COMPLETE | 0.05 | main | kjhgiughj |
| 56896956 | 2026-10-07 01:48:09 | COMPLETE | 0.10 | main | v15 short-trajectory (no sub-agent, thinking 256, budget 12) via CPU packaging notebook |
| 56856000 | 2026-10-05 15:43:10 | COMPLETE | 0.08 | main | v15 short-trajectory: anti-word-trap localization + no sub-agent + thinking 256 + budge... |
| 56835719 | 2026-10-04 23:36:10 | COMPLETE | 0.08 | main | v10 budget-40 agent (300s), uploaded from V1 committed output |
| 56835583 | 2026-10-04 23:26:08 | ERROR | - | main | Notebook Gemma Sibling-Conform v10 / Version 2 |
| 56806249 | 2026-10-03 20:34:11 | COMPLETE | 0.12 | main | beat...beat....no one else can be defeated |
| 56775978 | 2026-10-02 14:35:58 | COMPLETE | 0.10 | main | One shot |

- LB best main: ca5: pre-edit anchor-grep rule, no sub-agents, v10 config @ 0.20 (ref 57760641, 2026-10-29)
- LB best small-model: E4B ca5 anchor-grep: pre-edit rule, no sub-agents, v10 ca... @ 0.03 (ref 57807043, 2026-10-30)
- LB best dev-proxy: none COMPLETE with a score
- curated BASELINE pointer (policy, main track): v6w @ 0.15 (submission 57098497)
- curated small-model baseline: none
- BASELINE CONFLICT: LB best on main track (ca5: pre-edit anchor-grep rule, no sub-agents, v10 config @ 0.20, ref 57760641) != curated baseline (v6w@0.15 57098497) â€” not adopted
- branch_final (ref 57146757): COMPLETE 0.12 (from pulled/submissions/20261101T055511Z.csv)
- curated run_labels.json pending[branch_final] says PENDING â€” stale (see curated/_proposed_updates.md)
- log-claim LB checks use the LB source above (scores: 0.03, 0.05, 0.08, 0.10, 0.12, 0.13, 0.15, 0.17, 0.18, 0.20)

### Pulled outputs vs submissions (D5-10; `kernels output` = latest version only)
- `kb/pulled/gemma-sibling-conform-v1/20261101T062706Z` slug=gemma-sibling-conform-v1 label=v1 kind=latest-at-pull explains_refs=[] deleted=[]
  - no submission maps to this pulled run
- `kb/pulled/gemma-sibling-conform-v11/20261101T062717Z` slug=gemma-sibling-conform-v11 label=v11 kind=latest-at-pull explains_refs=[] deleted=[]
  - no submission maps to this pulled run
- `kb/pulled/gemma-sibling-conform-v15-cpu/20261101T061857Z` slug=gemma-sibling-conform-v15-cpu label=v15-cpu kind=latest-at-pull explains_refs=[] deleted=[]
  - ref 56856000 [description mentions v15]: ATTRIBUTION-UNVERIFIED: no stated config fact differs; no local submission zip for this ref
  - ref 56896956 [description mentions v15]: ATTRIBUTION-UNVERIFIED: no stated config fact differs; no local submission zip for this ref
- `kb/pulled/gemma-sibling-conform-v16/20261101T062742Z` slug=gemma-sibling-conform-v16 label=v16 kind=latest-at-pull explains_refs=[] deleted=[]
  - no submission maps to this pulled run
- `kb/pulled/gemma-sibling-conform-v17/20261101T062757Z` slug=gemma-sibling-conform-v17 label=v17 kind=latest-at-pull explains_refs=[] deleted=[]
  - no submission maps to this pulled run
- `kb/pulled/gemma-sibling-conform-v2/20261101T062807Z` slug=gemma-sibling-conform-v2 label=v2 kind=latest-at-pull explains_refs=[] deleted=[]
  - no submission maps to this pulled run
- `kb/pulled/gemma-sibling-conform-v20/20261101T062819Z` slug=gemma-sibling-conform-v20 label=v20 kind=latest-at-pull explains_refs=[] deleted=[]
  - no submission maps to this pulled run
- `kb/pulled/v6w_temp1_probe` slug=gemma-sibling-conform-v6w label=v6w kind=manual-legacy (no _pull_meta.json; treated as latest-at-pull) explains_refs=[] deleted=[]
  - ref 57098497 [description mentions v6w]: ATTRIBUTION-UNVERIFIED: no stated config fact differs; no local submission zip for this ref
  - ref 57146757 [description mentions v6w]: ATTRIBUTION-UNVERIFIED: description states no config facts; no local submission zip for this ref
  - ref 57201051 [description mentions v6w]: ATTRIBUTION-MISMATCH: pulled output does not explain ref 57201051 (temperature: pulled 0.2 vs submission 1)
  - ref 57276407 [description mentions v6w]: ATTRIBUTION-MISMATCH: pulled output does not explain ref 57276407 (max_tool_calls: pulled 28 vs submission 100)
  - ref 57317996 [description mentions v6w]: ATTRIBUTION-MISMATCH: pulled output does not explain ref 57317996 (model: pulled 31b vs submission 12b)

## 8. Log claims
- engine cl-4: 1246 claims from 1339 `##`/`###` units; by status: {'CONTRADICTED': 1, 'SUPERSEDED': 13, 'SUPPORTED': 121, 'UNVERIFIED': 1111}
- facts: 1529; auto-checked: 960; decided (SUPPORTED/CONTRADICTED): 594; disagreements NOT asserted (weak binding / different rep / budget sanity, listed in log_claims.md Â§3b): 40
- supersession: 13 claims SUPERSEDED in 7 chains (9 applied links; 11 unresolved citations; 137 keyword-overlap candidates, never applied)
- LB checks against `pulled/submissions/20261101T055511Z.csv`; F10 live-best claims are checked against curated/run_labels.json:baseline only (never adopted)
- log live-best chain (F10, first line per change): v6 L27 -> v7 L3499 -> v6 L3599 -> v6w L8393 -> ca5 L13760
- internal-consistency checks before any CONTRADICTED: 9 facts inside quoted retractions (never asserted; 3 quoted-fact supersession links); 2 facts where the log disagrees with itself (log_claims.md §3c); 1 label collision(s):
  - `v10` names experiment run(s) {'Outputs/v10': 10} AND kernel `gemma-sibling-conform-31b-a3-hard-version10` ({'gemma-sibling-conform-31b-a3-hard-version10': 129} tasks); 15 log lines use it as the kernel version (e.g. L12738, L13199, L13212, L13246); `v10 config`/`v10 caps` route to the kernel; a bare `v10` never yields a CONTRADICTED
- CONTRADICTED claims: 1
  - C-5a87e8cac8 L171: F1 v17=1/5:CON â€” resolved 1/5: all 1 bound run(s) disagree (kaggle_archive/gemma-sibling-conform-v17/output: 0/5) â€” evidence: kb/runs.jsonl run kaggle_archive/gemma-sibling-conform-v17/output
- curated claims merged: 6 (6 with all evidence paths present); orphans 0; curation conflicts 0
- full tables: log_claims.md; query: `build_kb.py claims --task/--version/--lever/--text/--status/--limit`

## 9. Harness semantics
DOCUMENTED: tool_calls budget per HARNESS_README.md Â§6.1; submit_patch/get_status are free (count_tool_call=False).
MEASURED (count model cm-2): residual 0 on 3193/3199 traces that carry a harness tool_calls value.
Scored state: last successful submit_patch snapshot, else the working tree when submit_patch was never called (README Â§6.1 tool 2 / Â§8.1).
DOCUMENTED scorer EventsCompactionConfig (comp_files/HARNESS_README.md:L555): compaction_interval = 5, overlap_size = 2, token_threshold = 14336
MEASURED (dev-harness AST pass dh-1, per run): matches scorer 3, does NOT match 97, unknown 996 of 1096 runs (unknown = no notebook or no EventsCompactionConfig call found; by platform: kaggle=19, local-rig=228, local-sweep=749).
- dev notebook values compaction_interval=15, overlap_size=2, token_threshold=14336: 94 runs
- dev notebook values compaction_interval=2222, overlap_size=2, token_threshold=14336: 3 runs
- dev notebook values compaction_interval=5, overlap_size=2, token_threshold=14336: 3 runs

## 10. Near-miss and cross-task false-positive control
- near_miss rows: 5863 (4083 with a trace; 4083 scored by the nm-3 line-level matcher).
- furthest-stage histogram (traced): APPLIED=510, None=415, READ_GOLD_FILE=171, RESOLVED=818, SAW_GOLD_HUNK=97, SCORED_NONEMPTY=1904, TRIED_APPLY=142, WROTE_GOLD_CHANGE=26
- cross-task FP control (Â§9.4): 736/142120 (trace, other-task) pairs fired WROTE_GOLD_CHANGE = 0.518% (bar <= 1%: PASS; sampling hash-cap-40: per trace the 40 same-repo other tasks with the smallest sha256(task+other), deterministic).

## 13. Replay table (gold-first)
- replay records: 1038. Counts by (tier, kind, agent result) (tier 0 = curated min set + all_runs rules; 1 Kaggle main; 2 Kaggle other tracks; 3 local rig; '-' = cached record of a plain build):

| tier | kind | agent | n |
|---|---|---|---|
| - | cached | N | 816 |
| - | cached | Y | 222 |

Per (task, run, candidate) — tier-0 rows, plain-build cached rows and every agent PASS (cap 80): gold-passed-locally | agent-candidate-passed | counterfactual-passed | notes.

| task | run | candidate | gold-local | agent | counterfactual | notes |
|---|---|---|---|---|---|---|
| rich_2725 | (cached) | cached | Y | N | - | from cache |
| rich_2725 | (cached) | cached | Y | N | - | from cache |
| rich_2725 | (cached) | cached | Y | N | - | from cache |
| rich_2725 | (cached) | cached | Y | N | - | from cache |
| rich_2725 | (cached) | cached | Y | N | - | from cache |
| rich_2725 | (cached) | cached | Y | N | - | from cache |
| rich_2725 | (cached) | cached | Y | N | - | from cache |
| rich_2725 | (cached) | cached | Y | Y | - | from cache |
| rich_2725 | (cached) | cached | Y | Y | - | from cache |
| rich_2943 | (cached) | cached | Y | N | - | from cache |
| rich_2943 | (cached) | cached | Y | Y | - | from cache |
| rich_2943 | (cached) | cached | Y | N | - | from cache |
| rich_2943 | (cached) | cached | Y | N | - | from cache |
| rich_2943 | (cached) | cached | Y | N | - | from cache |
| rich_2943 | (cached) | cached | Y | N | - | from cache |
| rich_2943 | (cached) | cached | Y | N | - | from cache |
| rich_2943 | (cached) | cached | Y | Y | - | from cache |
| rich_2943 | (cached) | cached | Y | Y | - | from cache |
| rich_2943 | (cached) | cached | Y | N | - | from cache |
| rich_2943 | (cached) | cached | Y | N | - | from cache |
| rich_2943 | (cached) | cached | Y | N | - | from cache |
| rich_2943 | (cached) | cached | Y | N | - | from cache |
| rich_3006 | (cached) | cached | Y | N | - | from cache |
| rich_3006 | (cached) | cached | Y | N | - | from cache |
| rich_3006 | (cached) | cached | Y | Y | - | from cache |
| rich_3006 | (cached) | cached | Y | Y | - | from cache |
| rich_3006 | (cached) | cached | Y | Y | - | from cache |
| rich_3006 | (cached) | cached | Y | Y | - | from cache |
| rich_3006 | (cached) | cached | Y | Y | - | from cache |
| rich_3006 | (cached) | cached | Y | Y | - | from cache |
| rich_3006 | (cached) | cached | Y | Y | - | from cache |
| rich_3006 | (cached) | cached | Y | N | - | from cache |
| rich_3006 | (cached) | cached | Y | N | - | from cache |
| rich_3006 | (cached) | cached | Y | N | - | from cache |
| rich_3006 | (cached) | cached | Y | N | - | from cache |
| rich_3006 | (cached) | cached | Y | N | - | from cache |
| rich_3006 | (cached) | cached | Y | Y | - | from cache |
| rich_3006 | (cached) | cached | Y | Y | - | from cache |
| rich_3006 | (cached) | cached | Y | Y | - | from cache |
| rich_3006 | (cached) | cached | Y | N | - | from cache |
| rich_3006 | (cached) | cached | Y | N | - | from cache |
| rich_3006 | (cached) | cached | Y | N | - | from cache |
| rich_3006 | (cached) | cached | Y | Y | - | from cache |
| rich_3006 | (cached) | cached | Y | Y | - | from cache |
| rich_3006 | (cached) | cached | Y | Y | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | Y | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | Y | - | from cache |
| rich_3043 | (cached) | cached | Y | Y | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3043 | (cached) | cached | Y | N | - | from cache |
| rich_3052 | (cached) | cached | Y | N | - | from cache |
| rich_3052 | (cached) | cached | Y | N | - | from cache |
| rich_3052 | (cached) | cached | Y | N | - | from cache |
| rich_3052 | (cached) | cached | Y | N | - | from cache |
| rich_3052 | (cached) | cached | Y | N | - | from cache |
| rich_3052 | (cached) | cached | Y | N | - | from cache |
| rich_3052 | (cached) | cached | Y | N | - | from cache |
| rich_3052 | (cached) | cached | Y | N | - | from cache |
| rich_3052 | (cached) | cached | Y | N | - | from cache |
| ... | 958 more rows in KB/replays/replays.jsonl | | | | | |

- replays_pending=0.
- NOTE: the reference-logs list and the clones' HEAD/index are a LIVE snapshot; the user moves checkouts between tasks, so HEAD drift during a build is external state, not a builder change (see replays/clone_state.json). Replays checkout the task's base_commit explicitly, so HEAD position does not affect them.

### 13a. Gold coverage (rp-5 gold-first, local Windows; KB/replays/gold_coverage.json)
- rich rows: 48 — by verdict: INFRA 5, VALID-HARNESS-LIKE 43
- fastapi rows attempted: 67 — by verdict: INFRA 67
- concordance with replays/goldgate_all.json (rp-4, reference only): absent 67, agree 43, disagree 5

| task | rp-5 verdict | reason | pins | gold pass n | hunk-mode | goldgate_all | decode-sweep |
|---|---|---|---|---|---|---|---|
| fastapi_11194 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_11355 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_12942 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_13207 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_13537 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_13713 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_13786 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_13920 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14077 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14099 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14186 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14246 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14258 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14262 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14266 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14297 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14301 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14303 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14306 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14349 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14356 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14360 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14361 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14371 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14372 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14419 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14430 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14448 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14455 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14458 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14459 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14463 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14479 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14482 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14485 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14487 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14492 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14512 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14583 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14605 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14609 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14616 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14786 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14791 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14794 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14851 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14873 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14953 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14962 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14964 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14978 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_14986 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_15023 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_15030 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_15280 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_15588 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_15589 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_15661 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_15745 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_15763 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_15785 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_15800 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_5077 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_5624 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_9425 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_9555 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| fastapi_9753 | INFRA | package under test failed to import in the base env: missing starlette | - (none) | 0 | - | absent | absent |
| rich_2725 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.16.1 (lockfile) | 11 | - | agree | absent |
| rich_2943 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.16.1 (lockfile) | 27 | - | agree | agree |
| rich_3006 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.15.1 (lockfile) | 8 | VALID-HARNESS-LIKE | agree | absent |
| rich_3043 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.15.1 (lockfile) | 85 | VALID-HARNESS-LIKE | agree | absent |
| rich_3052 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.16.1 (lockfile) | 7 | - | agree | absent |
| rich_3061 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.15.1 (lockfile) | 83 | - | agree | absent |
| rich_3063 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.15.1 (lockfile) | 21 | - | agree | absent |
| rich_3064 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.15.1 (lockfile) | 4 | - | agree | absent |
| rich_3067 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.15.1 (lockfile) | 7 | VALID-HARNESS-LIKE | agree | absent |
| rich_3105 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.16.1 (lockfile) | 85 | VALID-HARNESS-LIKE | agree | absent |
| rich_3130 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.15.1 (lockfile) | 6 | - | agree | absent |
| rich_3180 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.16.1 (lockfile) | 92 | - | agree | absent |
| rich_3278 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.16.1 (lockfile) | 4 | - | agree | agree |
| rich_3296 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.16.1 (lockfile) | 20 | - | agree | absent |
| rich_3454 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.16.1 (lockfile) | 7 | VALID-HARNESS-LIKE | agree | absent |
| rich_3468 | INFRA | required nodes skipped on this platform: does not run on windows | markdown-it-py==2.2.0, pygments==2.17.2 (lockfile) | 86 | - | disagree (INVALID) | absent |
| rich_3469 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.17.2 (lockfile) | 7 | - | agree | agree |
| rich_3470 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.17.2 (lockfile) | 86 | - | agree | agree |
| rich_3471 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.17.2 (lockfile) | 86 | - | agree | agree |
| rich_3472 | INFRA | test dependency missing in the base env: missing attr | markdown-it-py==2.2.0, pygments==2.17.2 (lockfile) | 0 | - | disagree (VALID-GOLD-RELATIVE) | absent |
| rich_3480 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.17.2 (lockfile) | 87 | - | agree | absent |
| rich_3486 | INFRA | required nodes skipped on this platform: Not applicable after Python 3.11 | markdown-it-py==2.2.0, pygments==2.17.2 (lockfile) | 18 | - | disagree (INVALID) | absent |
| rich_3506 | VALID-HARNESS-LIKE |  | markdown-it-py==2.2.0, pygments==2.17.2 (lockfile) | 29 | - | agree | absent |
| rich_3518 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.18.0 (lockfile) | 12 | - | agree | agree |
| rich_3521 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.18.0 (lockfile) | 29 | - | agree | absent |
| rich_3535 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.18.0 (lockfile) | 8 | - | agree | absent |
| rich_3675 | INFRA | required nodes skipped on this platform: does not run on windows / not relevant on Windows | markdown-it-py==3.0.0, pygments==2.18.0 (lockfile) | 87 | - | disagree (INVALID) | absent |
| rich_3676 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.18.0 (lockfile) | 19 | - | agree | absent |
| rich_3718 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.1 (lockfile) | 7 | - | agree | absent |
| rich_3772 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.1 (lockfile) | 20 | - | agree | agree |
| rich_3777 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.1 (lockfile) | 87 | - | agree | absent |
| rich_3782 | INFRA | required nodes skipped on this platform: permissions error on Windows | markdown-it-py==3.0.0, pygments==2.19.1 (lockfile) | 21 | - | disagree (INVALID) | absent |
| rich_3882 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 8 | - | agree | agree |
| rich_3894 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 15 | - | agree | absent |
| rich_3905 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 35 | - | agree | absent |
| rich_3930 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 104 | - | agree | absent |
| rich_3934 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 11 | - | agree | absent |
| rich_3935 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 14 | - | agree | agree |
| rich_3938 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 120 | - | agree | absent |
| rich_3942 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 7 | VALID-HARNESS-LIKE | agree | absent |
| rich_3944 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 12 | - | agree | absent |
| rich_3953 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 14 | - | agree | absent |
| rich_4006 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 15 | - | agree | absent |
| rich_4070 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 108 | VALID-HARNESS-LIKE | agree | absent |
| rich_4075 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 88 | - | agree | absent |
| rich_4076 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 5 | - | agree | agree |
| rich_4077 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 4 | - | agree | agree |
| rich_4079 | VALID-HARNESS-LIKE |  | markdown-it-py==3.0.0, pygments==2.19.2 (lockfile) | 8 | - | agree | agree |

### 13b. Required-node gap (tasks whose test_patch adds no `def test_*`: the local bar falls back to the whole test file)
- the local bar differs from the harness for these tasks (HARNESS_README L609: required = FAIL_TO_PASS / PASS_TO_PASS / test functions extracted from test_patch). `n hunk funcs` is static (hunk headers + def lines in hunks); `hunk` is the rp-5 `--required-nodes hunk` gold verdict where run.

| task | test files | n hunk funcs (static) | funcs | hunk verdict | hunk required n |
|---|---|---|---|---|---|
| fastapi_13207 | tests/test_computed_fields.py | 2 | test_get, test_openapi_schema | not run | - |
| fastapi_13713 | tests/main.py, tests/test_application.py | 1 | test_openapi_schema | not run | - |
| fastapi_13786 | tests/test_security_api_key_cookie.py, tests/test_securit... | 16 | test_openapi_schema, test_security_api_key, test_security_api_key_n... | not run | - |
| fastapi_14077 | tests/test_enforce_once_required_parameter.py | 3 | test_get_invalid, test_get_valid, test_schema | not run | - |
| fastapi_14186 | tests/test_compat.py, tests/test_get_model_definitions_fo... | 7 | test_get_model_fields_cached, test_invalid_response_model_field_pv1... | not run | - |
| fastapi_14371 | tests/test_request_params/test_body/test_list.py, tests/t... | 53 | test_list_alias_and_validation_alias_by_alias, test_list_alias_and_... | not run | - |
| fastapi_14448 | tests/test_dependency_wrapped.py | 1 | test_class_dependency | not run | - |
| fastapi_14458 | tests/test_dependency_class.py | 1 | test_class_dependency | not run | - |
| fastapi_14479 | tests/test_invalid_sequence_param.py | 4 | test_invalid_dict, test_invalid_sequence, test_invalid_simple_dict,... | not run | - |
| fastapi_14487 | tests/test_tutorial/test_handling_errors/test_tutorial004.py | 2 | test_get_http_error, test_get_validation_error | not run | - |
| fastapi_14492 | tests/test_tutorial/test_metadata/test_tutorial001_1.py | 1 | test_openapi_schema | not run | - |
| fastapi_14605 | tests/benchmarks/test_general_performance.py, tests/test_... | 5 | test_body_example_deprecation_warning, test_body_regex_deprecation_... | not run | - |
| fastapi_14791 | tests/test_additional_properties.py, tests/test_additiona... | 3 | test_openapi, test_openapi_schema, test_openapi_schema_no_separate | not run | - |
| fastapi_15023 | tests/test_tutorial/test_stream_data/test_tutorial002.py | 1 | test_openapi_schema | not run | - |
| httpx_3672 | tests/test_parsers.py | 5 | test_client_connection_close, test_parser, test_parser_repr, test_p... | not run | - |
| requests_7309 | tests/test_utils.py | 3 | test__parse_content_type_header, test_get_encoding_from_headers, te... | not run | - |
| rich_3006 | tests/test_repr.py | 4 | test_rich_angular, test_rich_repr, test_rich_repr_auto, test_rich_r... | VALID-HARNESS-LIKE | 1 |
| rich_3043 | tests/test_console.py | 4 | test_export_html, test_export_html_inline, test_save_html, test_sav... | VALID-HARNESS-LIKE | 3 |
| rich_3067 | tests/test_highlighter.py | 1 | test_wrong_type | VALID-HARNESS-LIKE | 0 |
| rich_3105 | tests/test_console.py | 4 | test_export_html, test_export_html_inline, test_save_html, test_sav... | VALID-HARNESS-LIKE | 3 |
| rich_3454 | tests/test_highlighter.py | 1 | test_wrong_type | VALID-HARNESS-LIKE | 0 |
| rich_3942 | tests/_card_render.py, tests/test_markdown.py, tests/test... | 5 | test_inline_styles_in_table, test_inline_styles_with_justification,... | VALID-HARNESS-LIKE | 5 |
| rich_4070 | tests/test_console.py, tests/test_syntax.py | 0 | - | VALID-HARNESS-LIKE | 1 |

## 6. Levers
- lever matrix lv-1; lexicon: `kblib/lever_lexicon_default.json (code-owned default; curated/lever_lexicon.json absent)`
- instance = config-field diff vs the track reference or vs the previous run of the same label; prompt levers = lexicon pattern presence in the run's prompt; dev-harness = notebook value vs the scorer; log levers have no config field (mentions only).
- counts are `rows / distinct tasks` of the runs carrying an instance (never pooled across tracks); per-task = `task:resolvedR/rows`.

### Track: main (1366 rows / 129 distinct tasks; reference: curated baseline v6w run kaggle_archive/gemma-sibling-conform-v6w/output; levers with instances: 18/24)

| lever | kind | runs | rows/distinct | labels/arms | stack | transitions | per-task outcomes | LB refs | log mentions | latest verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| max_tool_calls | config | 31 | 183/27 | -v10-kaggle-pull, -v6out, v1, v11, v16, v17 +13 | kaggle:30, local-rig:1 | 28->15 (baseline) x20; 28->40 (baseline) x5; 28->22 (baseline) x3 | rich_4077:19R/30 rich_4076:0R/29 rich_4079:2R/29 rich_4070:0R/24 rich_3469:0R/20 | 57098497(0.15), 57276407(-) | 20 | C-423cfd43e5 L13430 (UNVERIFIED) |
| max_time_minutes | config | 13 | 99/24 | -v10-kaggle-pull, -v6out, repeat-live, v1, v11, v2 +2 | kaggle:12, local-rig:1 | 8->5 (baseline) x10; 5->8 (prev-same-label) x1; 8->9 (baseline) x1 | rich_4077:5R/11 rich_4076:0R/10 rich_4079:2R/10 fastapi_15588:0R/7 fastapi_15661:0R/7 | 57098497(0.15) | 7 | C-d1b542d656 L4992 (UNVERIFIED) |
| max_turns | config | 69 | 929/129 | -v10-kaggle-pull, -v6out, 31b-a21-arm, 31b-a22-arm, 31b-a3-hard, ca5-31b-full129-eval +23 | kaggle:42, local-rig:27 | 80->120 (baseline) x38; 80->24 (baseline) x20; 80->40 (baseline) x5 | rich_4077:27R/66 rich_3777:2R/37 rich_4079:3R/37 rich_3006:32R/35 rich_3454:31R/35 | 57098497(0.15) | 4 | C-7c08c0ff65 L4383 (UNVERIFIED) |
| timeout_seconds | config | 67 | 909/129 | -v10-kaggle-pull, -v6out, 31b-a21-arm, 31b-a22-arm, 31b-a3-hard, ca5-31b-full129-eval +22 | kaggle:40, local-rig:27 | 240->300 (baseline) x37; 240->120 (baseline) x30; 120->300 (prev-same-label) x1 | rich_4077:27R/66 rich_4079:3R/37 rich_3777:1R/35 rich_3006:30R/33 rich_3454:29R/33 | 57098497(0.15) | 4 | C-7e30670e57 L767 (UNVERIFIED) |
| thinking_budget | config | 71 | 928/129 | -v10-kaggle-pull, 31b-a21-arm, 31b-a22-arm, 31b-a3-hard, ca5-31b-full129-eval, ctrl +27 | kaggle:47, local-rig:24 | 1024->4096 (baseline) x37; 1024->256 (baseline) x20; 1024->512 (baseline) x6 | rich_4077:33R/70 rich_4079:4R/44 rich_3882:15R/41 rich_4076:0R/40 rich_3777:1R/32 | 56856000(0.08), 56896956(0.10), 57098497(0.15) | 17 | C-f227d4e5d3 L14569 (UNVERIFIED) |
| temperature | config | 0 | 0/0 | - | - | - | - | 57201051(0.13) | 14 | C-d7d80f9987 L13606 (UNVERIFIED) |
| top_k | config | 0 | 0/0 | - | - | - | - | 57201051(0.13) | 4 | C-cbe9c181d5 L10173 (UNVERIFIED) |
| top_p | config | 0 | 0/0 | - | - | - | - | - | 1 | - |
| max_output_tokens | config | 92 | 1106/129 | -v10-kaggle-pull, 31b-a21-arm, 31b-a22-arm, 31b-a3-hard, ca5-31b-full129-eval, cover-rich +41 | kaggle:65, local-rig:27 | 16384->5000 (baseline) x37; 16384->8192 (baseline) x31; 16384->6144 (baseline) x17 | rich_4077:41R/80 rich_3882:22R/51 rich_4079:5R/51 rich_4076:0R/47 rich_3777:5R/40 | - | 6 | C-9ed9e4799c L8672 (UNVERIFIED) |
| frequency_penalty | log | 0 | 0/0 | - | - | - | - | - | 5 | C-42af12e163 L11915 (UNVERIFIED) |
| tools | tools | 6 | 34/10 | v21, v6b, v6c | kaggle:6 | 9 tools->7 tools (baseline) x4; 9 tools->6 tools (baseline) x2 | rich_4076:0R/6 rich_4077:6R/6 rich_4079:2R/6 rich_4070:0R/4 fastapi_15588:0R/2 | 57098497(0.15), 57146757(0.12) | 12 | C-2a480cf0ad L14385 (UNVERIFIED) |
| subagents-router | log | 0 | 0/0 | - | - | - | - | 56856000(0.08), 56896956(0.10), 57720023(0.13), 57760641(0.20), 57847285(-) | 23 | C-fe0e14b408 L13418 (SUPPORTED) |
| adapter-lora | config | 2 | 20/10 | v11 | kaggle:2 | main_lora->localizer_v1 (baseline) x2 | fastapi_14246:0R/2 fastapi_14356:0R/2 fastapi_14485:0R/2 fastapi_14487:0R/2 requests_7315:0R/2 | 57276407(-) | 88 | C-3193f13ced L13863 (UNVERIFIED) |
| model-size | config | 0 | 0/0 | - | - | - | - | 57399296(0.15) | 1 | C-423cfd43e5 L13430 (UNVERIFIED) |
| prompt-text | config | 97 | 1140/129 | -v10-kaggle-pull, -v6out, 31b-a21-arm, 31b-a22-arm, 31b-a3-hard, ca5-31b-full129-eval +43 | kaggle:70, local-rig:27 | 8da2005a->b9aeaa9a (baseline) x19; 8da2005a->2a5ee1ad (baseline) x16; 8da2005a->9c2fa358 (baseline) x12 | rich_4077:46R/87 rich_4079:7R/58 rich_4076:0R/54 rich_3882:22R/51 rich_3777:5R/40 | - | 13 | C-42af12e163 L11915 (UNVERIFIED) |
| prompt-anchor-grep | prompt | 19 | 499/129 | ca5-31b-full129-eval, t0, t1024, t2048, t512, v5 | kaggle:3, local-rig:16 | absent->present (baseline) x19; absent->present (prev-same-label) x1 | rich_3006:18R/19 rich_3454:16R/19 rich_3518:7R/19 rich_3777:0R/19 rich_3882:2R/19 | 57760641(0.20), 57847285(-) | 1 | - |
| prompt-delimiter-fix | prompt | 37 | 733/129 | 31b-a21-arm, 31b-a22-arm, 31b-a3-hard, ca5-31b-full129-eval, ctrl, t0 +4 | kaggle:10, local-rig:27 | absent->present (baseline) x37; absent->present (prev-same-label) x1 | rich_4077:8R/37 rich_3777:1R/35 rich_3006:30R/33 rich_3454:29R/33 rich_3882:5R/33 | - | 5 | C-859d2f5547 L12409 (UNVERIFIED) |
| prompt-apply-as-you-go | prompt | 37 | 733/129 | 31b-a21-arm, 31b-a22-arm, 31b-a3-hard, ca5-31b-full129-eval, ctrl, t0 +4 | kaggle:10, local-rig:27 | absent->present (baseline) x37; absent->present (prev-same-label) x1 | rich_4077:8R/37 rich_3777:1R/35 rich_3006:30R/33 rich_3454:29R/33 rich_3882:5R/33 | - | 4 | C-bed1e1ccd6 L9369 (UNVERIFIED) |
| prompt-locate-numeral | prompt | 63 | 961/129 | -v10-kaggle-pull, -v6out, 31b-a21-arm, 31b-a22-arm, 31b-a3-hard, ca5-31b-full129-eval +20 | kaggle:36, local-rig:27 | absent->present (baseline) x63; absent->present (prev-same-label) x2 | rich_4077:26R/58 rich_3882:17R/45 rich_3777:5R/40 rich_3006:35R/38 rich_3454:34R/38 | - | 1 | C-c4622aecff L14485 (UNVERIFIED) |
| prompt-verify-rule | prompt | 65 | 967/129 | -v10-kaggle-pull, -v6out, 31b-a21-arm, 31b-a22-arm, 31b-a3-hard, ca5-31b-full129-eval +21 | kaggle:38, local-rig:27 | present->absent (baseline) x65; present->absent (prev-same-label) x2 | rich_4077:26R/60 rich_3882:17R/45 rich_3777:5R/40 rich_3006:35R/38 rich_3454:34R/38 | - | 1 | - |
| prompt-compliance-salience | prompt | 64 | 967/129 | -v10-kaggle-pull, -v6out, 31b-a21-arm, 31b-a22-arm, 31b-a3-hard, ca5-31b-full129-eval +22 | kaggle:37, local-rig:27 | absent->present (baseline) x64; absent->present (prev-same-label) x3 | rich_4077:27R/59 rich_3882:18R/47 rich_3777:5R/40 rich_3006:35R/38 rich_3454:34R/38 | - | 13 | C-26959dd8ea L12637 (UNVERIFIED) |
| prompt-patch-size | prompt | 59 | 925/129 | 31b-a21-arm, 31b-a22-arm, 31b-a3-hard, ca5-31b-full129-eval, cover-rich, ctrl +18 | kaggle:32, local-rig:27 | absent->present (baseline) x59; absent->present (prev-same-label) x3 | rich_4077:23R/54 rich_3882:19R/47 rich_3777:5R/40 rich_3006:35R/38 rich_3454:34R/38 | - | 3 | C-7b20c876d6 L16525 (UNVERIFIED) |
| prompt-one-to-1 | prompt | 44 | 777/129 | -v6out, 31b-a21-arm, 31b-a3-hard, ca5-31b-full129-eval, ctrl, t0 +9 | kaggle:17, local-rig:27 | present->absent (baseline) x44 | rich_4077:13R/44 rich_3882:7R/35 rich_3006:30R/33 rich_3454:29R/33 rich_3777:1R/33 | - | 6 | C-0fa820c98a L12872 (UNVERIFIED) |
| dev-harness-compaction | dev-harness | 68 | 558/129 | -v6out, 31b-a21-arm, 31b-a22-arm, 31b-a3-hard, cover-rich, repeat-live +36 | kaggle:68 | 5->15 (scorer) x65; 5->2222 (scorer) x3 | rich_4077:39R/54 rich_4079:7R/52 rich_4076:0R/48 rich_4070:0R/28 rich_3471:5R/22 | 56856000(0.08) | 12 | C-4d631bd07c L16922 (UNVERIFIED) |

### Track: small-model (2329 rows / 129 distinct tasks; reference: modal value over the track's runs (no curated baseline); levers with instances: 15/24)

| lever | kind | runs | rows/distinct | labels/arms | stack | transitions | per-task outcomes | LB refs | log mentions | latest verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| max_tool_calls | config | 4 | 24/6 | v7-e2b, v7-e4b, v7_e2b, v7_e4b | kaggle:4 | 28->22 (modal) x4 | rich_3006:2R/4 rich_3043:0R/4 rich_3454:2R/4 rich_3782:0R/4 rich_3894:2R/4 | - | 20 | C-04f910f4c6 L14364 (UNVERIFIED) |
| max_time_minutes | config | 4 | 24/6 | v7-e2b, v7-e4b, v7_e2b, v7_e4b | kaggle:4 | 8->5 (modal) x4 | rich_3006:2R/4 rich_3043:0R/4 rich_3454:2R/4 rich_3782:0R/4 rich_3894:2R/4 | - | 6 | C-d1b542d656 L4992 (UNVERIFIED) |
| max_turns | config | 16 | 248/45 | e4b-a3, e4b-a5, remap-e2b, remap-e4b, size-e2b, size-e4b +4 | kaggle:16 | 120->80 (modal) x12; 120->40 (modal) x4 | rich_3006:8R/16 rich_3043:0R/16 rich_3454:4R/16 rich_3894:4R/16 rich_3938:0R/16 | - | 2 | - |
| timeout_seconds | config | 16 | 248/45 | e4b-a3, e4b-a5, remap-e2b, remap-e4b, size-e2b, size-e4b +4 | kaggle:16 | 300->240 (modal) x12; 300->120 (modal) x4 | rich_3006:8R/16 rich_3043:0R/16 rich_3454:4R/16 rich_3894:4R/16 rich_3938:0R/16 | - | 4 | C-7e30670e57 L767 (UNVERIFIED) |
| thinking_budget | config | 15 | 1266/129 | agent_ctrl_e4b, agent_ctrl_e4b_def, agent_ctrl_e4b_def2, agent_ctrl_e4b_locate, agent_ctrl_e4b_noprompt, agent_ctrl_e4b_t512 +1 | kaggle:4, local-rig:11 | 1024->4096 (modal) x14; 1024->512 (modal) x1 | rich_4077:4R/14 fastapi_14077:3R/13 fastapi_14301:8R/13 fastapi_14372:0R/13 fastapi_14458:1R/13 | - | 22 | C-f227d4e5d3 L14569 (UNVERIFIED) |
| temperature | config | 0 | 0/0 | - | - | - | - | - | 16 | C-d570096853 L14369 (UNVERIFIED) |
| top_k | config | 0 | 0/0 | - | - | - | - | - | 6 | C-479540464e L11501 (UNVERIFIED) |
| top_p | config | 0 | 0/0 | - | - | - | - | - | 2 | C-479540464e L11501 (UNVERIFIED) |
| max_output_tokens | config | 15 | 1266/129 | agent_ctrl_e4b, agent_ctrl_e4b_def, agent_ctrl_e4b_def2, agent_ctrl_e4b_locate, agent_ctrl_e4b_noprompt, agent_ctrl_e4b_t512 +1 | kaggle:4, local-rig:11 | 8192->5000 (modal) x15 | rich_4077:4R/14 fastapi_14077:3R/13 fastapi_14301:8R/13 fastapi_14372:0R/13 fastapi_14458:1R/13 | - | 6 | C-9ed9e4799c L8672 (UNVERIFIED) |
| frequency_penalty | log | 0 | 0/0 | - | - | - | - | - | 4 | C-a7d2ddf753 L9590 (SUPPORTED) |
| tools | tools | 0 | 0/0 | - | - | - | - | - | 14 | C-2a480cf0ad L14385 (UNVERIFIED) |
| subagents-router | log | 0 | 0/0 | - | - | - | - | 57807043(0.03) | 26 | C-67759bd031 L13419 (UNVERIFIED) |
| adapter-lora | config | 0 | 0/0 | - | - | - | - | - | 96 | C-5015262669 L14579 (UNVERIFIED) |
| model-size | config | 27 | 1490/129 | agent_ctrl_e4b, agent_ctrl_e4b_def, agent_ctrl_e4b_def2, agent_ctrl_e4b_locate, agent_ctrl_e4b_noprompt, agent_ctrl_e4b_t512 +7 | kaggle:16, local-rig:11 | gemma-4-->gemma-4- (modal) x27 | rich_3006:18R/25 rich_3454:8R/25 rich_3894:3R/25 rich_3043:0R/22 rich_3938:0R/22 | 57807043(0.03) | 8 | C-423cfd43e5 L13430 (UNVERIFIED) |
| prompt-text | config | 22 | 464/129 | agent_ctrl_e4b_def, agent_ctrl_e4b_def2, agent_ctrl_e4b_locate, agent_ctrl_e4b_noprompt, e4b-a3, e4b-a5 +8 | kaggle:16, local-rig:6 | b9aeaa9a->9c2fa358 (modal) x8; b9aeaa9a->78c9778b (modal) x4; b9aeaa9a->0aae1a1e (modal) x2 | rich_3006:12R/20 rich_3454:7R/20 rich_3894:4R/20 rich_3043:0R/18 rich_3938:0R/17 | - | 11 | C-b9c9bb65fd L12870 (UNVERIFIED) |
| prompt-anchor-grep | prompt | 13 | 1135/129 | agent_ctrl_e4b, agent_ctrl_e4b_def, agent_ctrl_e4b_def2, agent_ctrl_e4b_locate, agent_ctrl_e4b_t512, ca5-e4b-full129-eval | kaggle:4, local-rig:9 | absent->present (modal) x13 | fastapi_14077:3R/12 fastapi_14301:7R/12 fastapi_14372:0R/12 fastapi_14458:1R/12 fastapi_14463:7R/12 | 57807043(0.03) | 1 | - |
| prompt-delimiter-fix | prompt | 12 | 72/6 | remap-e2b, remap-e4b, size-e2b, size-e4b, v7-e2b, v7-e4b +2 | kaggle:12 | present->absent (modal) x12 | rich_3006:4R/12 rich_3043:0R/12 rich_3454:4R/12 rich_3782:0R/12 rich_3894:4R/12 | - | 4 | C-00e990d2c2 L12673 (UNVERIFIED) |
| prompt-apply-as-you-go | prompt | 15 | 1266/129 | agent_ctrl_e4b, agent_ctrl_e4b_def, agent_ctrl_e4b_def2, agent_ctrl_e4b_locate, agent_ctrl_e4b_noprompt, agent_ctrl_e4b_t512 +1 | kaggle:4, local-rig:11 | absent->present (modal) x15 | rich_4077:4R/14 fastapi_14077:3R/13 fastapi_14301:8R/13 fastapi_14372:0R/13 fastapi_14458:1R/13 | - | 4 | C-bed1e1ccd6 L9369 (UNVERIFIED) |
| prompt-locate-numeral | prompt | 0 | 0/0 | - | - | - | - | - | 7 | C-4e47cdbcb3 L14788 (UNVERIFIED) |
| prompt-verify-rule | prompt | 48 | 48/4 | D2, P3 | local-sweep:48 | absent->present (modal) x48 | rich_2725:6R/21 rich_2943:1R/21 rich_3067:2R/3 rich_3772:0R/3 | - | 1 | - |
| prompt-compliance-salience | prompt | 0 | 0/0 | - | - | - | - | - | 15 | C-00e990d2c2 L12673 (UNVERIFIED) |
| prompt-patch-size | prompt | 4 | 24/6 | v7-e2b, v7-e4b, v7_e2b, v7_e4b | kaggle:4 | present->absent (modal) x4 | rich_3006:2R/4 rich_3043:0R/4 rich_3454:2R/4 rich_3782:0R/4 rich_3894:2R/4 | - | 4 | C-7b20c876d6 L16525 (UNVERIFIED) |
| prompt-one-to-1 | prompt | 19 | 1290/129 | agent_ctrl_e4b, agent_ctrl_e4b_def, agent_ctrl_e4b_def2, agent_ctrl_e4b_locate, agent_ctrl_e4b_noprompt, agent_ctrl_e4b_t512 +5 | kaggle:8, local-rig:11 | present->absent (modal) x19 | rich_3006:14R/17 rich_3454:8R/17 rich_3894:3R/17 rich_3043:0R/14 rich_3938:0R/14 | - | 6 | C-0fa820c98a L12872 (UNVERIFIED) |
| dev-harness-compaction | dev-harness | 16 | 248/45 | e4b-a3, e4b-a5, remap-e2b, remap-e4b, size-e2b, size-e4b +4 | kaggle:16 | 5->15 (scorer) x16 | rich_3006:8R/16 rich_3043:0R/16 rich_3454:4R/16 rich_3894:4R/16 rich_3938:0R/16 | - | 12 | C-c717cb0e22 L16931 (UNVERIFIED) |

### Track: dev-proxy (2168 rows / 129 distinct tasks; reference: modal value over the track's runs (no curated baseline); levers with instances: 16/24)

| lever | kind | runs | rows/distinct | labels/arms | stack | transitions | per-task outcomes | LB refs | log mentions | latest verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| max_tool_calls | config | 77 | 77/77 | A3 | local-sweep:77 | 28->60 (modal) x77; 28->60 (prev-same-label) x1 | fastapi_11194:0R/1 fastapi_13537:0R/1 fastapi_13713:0R/1 fastapi_13786:0R/1 fastapi_14077:0R/1 | 57317996(-) | 19 | C-423cfd43e5 L13430 (UNVERIFIED) |
| max_time_minutes | config | 0 | 0/0 | - | - | - | - | 57317996(-) | 6 | C-d1b542d656 L4992 (UNVERIFIED) |
| max_turns | config | 10 | 109/48 | agent_ctrl_12b_locate, router, router_v2, router_v3 | local-rig:10 | 80->120 (modal) x10 | rich_3006:7R/10 rich_3454:10R/10 rich_3882:1R/10 rich_3905:4R/10 rich_4077:1R/10 | 57317996(-) | 2 | - |
| timeout_seconds | config | 10 | 109/48 | agent_ctrl_12b_locate, router, router_v2, router_v3 | local-rig:10 | 240->300 (modal) x10 | rich_3006:7R/10 rich_3454:10R/10 rich_3882:1R/10 rich_3905:4R/10 rich_4077:1R/10 | 57317996(-) | 4 | C-7e30670e57 L767 (UNVERIFIED) |
| thinking_budget | config | 1 | 46/46 | agent_ctrl_12b_locate | local-rig:1 | 1024->4096 (modal) x1 | fastapi_11355:0R/1 fastapi_12942:0R/1 fastapi_14099:0R/1 fastapi_14246:0R/1 fastapi_14266:0R/1 | 57317996(-) | 14 | C-f227d4e5d3 L14569 (UNVERIFIED) |
| temperature | config | 2 | 6/5 | q_on1024_t1, r_on1024_t1 | local-sweep:2 | 0.2->1.0 (modal) x2 | rich_4077:0R/2 rich_3454:1R/1 rich_3518:1R/1 rich_3944:0R/1 rich_4079:0R/1 | 57317996(-) | 12 | C-d7d80f9987 L13606 (UNVERIFIED) |
| top_k | config | 0 | 0/0 | - | - | - | - | - | 5 | C-cbe9c181d5 L10173 (UNVERIFIED) |
| top_p | config | 0 | 0/0 | - | - | - | - | - | 0 | - |
| max_output_tokens | config | 1 | 46/46 | agent_ctrl_12b_locate | local-rig:1 | 8192->5000 (modal) x1 | fastapi_11355:0R/1 fastapi_12942:0R/1 fastapi_14099:0R/1 fastapi_14246:0R/1 fastapi_14266:0R/1 | - | 5 | C-9ed9e4799c L8672 (UNVERIFIED) |
| frequency_penalty | log | 0 | 0/0 | - | - | - | - | - | 3 | C-d69e3b6611 L7461 (UNVERIFIED) |
| tools | tools | 0 | 0/0 | - | - | - | - | - | 12 | C-2a480cf0ad L14385 (UNVERIFIED) |
| subagents-router | log | 0 | 0/0 | - | - | - | - | - | 20 | C-fe0e14b408 L13418 (SUPPORTED) |
| adapter-lora | config | 0 | 0/0 | - | - | - | - | 57317996(-) | 85 | C-e487ffc878 L13864 (UNVERIFIED) |
| model-size | config | 0 | 0/0 | - | - | - | - | 57317996(-) | 1 | C-423cfd43e5 L13430 (UNVERIFIED) |
| prompt-text | config | 20 | 147/57 | 12b-a10-ones-oracle-9t, 12b-a11-tight-fails, 12b-a13-nol48-fails, 12b-a14-tmp-fix, 12b-a3-9t, 12b-a3-rerun3006 +9 | kaggle:13, local-rig:7 | 3ca5ba56->702183a6 (modal) x3; 3ca5ba56->efbde09b (modal) x3; 3ca5ba56->0aae1a1e (modal) x2 | rich_3006:14R/15 rich_3882:3R/13 rich_4077:2R/13 rich_3454:12R/12 rich_3905:6R/10 | - | 11 | C-bf096a8196 L13826 (UNVERIFIED) |
| prompt-anchor-grep | prompt | 1 | 46/46 | agent_ctrl_12b_locate | local-rig:1 | absent->present (modal) x1 | fastapi_11355:0R/1 fastapi_12942:0R/1 fastapi_14099:0R/1 fastapi_14246:0R/1 fastapi_14266:0R/1 | - | 0 | - |
| prompt-delimiter-fix | prompt | 4 | 20/10 | m12, size-12b, v6z_on_v6w-m12 | kaggle:4 | present->absent (modal) x4 | rich_3006:2R/2 rich_3043:0R/2 rich_3454:2R/2 rich_3535:0R/2 rich_3675:0R/2 | - | 3 | C-859d2f5547 L12409 (UNVERIFIED) |
| prompt-apply-as-you-go | prompt | 10 | 109/48 | agent_ctrl_12b_locate, router, router_v2, router_v3 | local-rig:10 | absent->present (modal) x10 | rich_3006:7R/10 rich_3454:10R/10 rich_3882:1R/10 rich_3905:4R/10 rich_4077:1R/10 | - | 4 | C-bed1e1ccd6 L9369 (UNVERIFIED) |
| prompt-locate-numeral | prompt | 2 | 8/4 | m12, v6z_on_v6w-m12 | kaggle:2 | present->absent (modal) x2 | rich_3535:0R/2 rich_3675:0R/2 rich_3676:0R/2 rich_3934:0R/2 | - | 1 | C-c4622aecff L14485 (UNVERIFIED) |
| prompt-verify-rule | prompt | 2 | 8/4 | m12, v6z_on_v6w-m12 | kaggle:2 | absent->present (modal) x2 | rich_3535:0R/2 rich_3675:0R/2 rich_3676:0R/2 rich_3934:0R/2 | - | 1 | - |
| prompt-compliance-salience | prompt | 2 | 8/4 | m12, v6z_on_v6w-m12 | kaggle:2 | present->absent (modal) x2 | rich_3535:0R/2 rich_3675:0R/2 rich_3676:0R/2 rich_3934:0R/2 | - | 12 | C-8d142f42df L11603 (UNVERIFIED) |
| prompt-patch-size | prompt | 2 | 8/4 | m12, v6z_on_v6w-m12 | kaggle:2 | present->absent (modal) x2 | rich_3535:0R/2 rich_3675:0R/2 rich_3676:0R/2 rich_3934:0R/2 | - | 3 | C-7b20c876d6 L16525 (UNVERIFIED) |
| prompt-one-to-1 | prompt | 1 | 46/46 | agent_ctrl_12b_locate | local-rig:1 | present->absent (modal) x1 | fastapi_11355:0R/1 fastapi_12942:0R/1 fastapi_14099:0R/1 fastapi_14246:0R/1 fastapi_14266:0R/1 | - | 5 | C-0fa820c98a L12872 (UNVERIFIED) |
| dev-harness-compaction | dev-harness | 13 | 59/17 | 12b-a10-ones-oracle-9t, 12b-a11-tight-fails, 12b-a13-nol48-fails, 12b-a14-tmp-fix, 12b-a3-9t, 12b-a3-rerun3006 +6 | kaggle:13 | 5->15 (scorer) x13 | rich_3006:7R/8 rich_3772:0R/6 rich_3882:2R/6 rich_4077:1R/6 rich_3454:5R/5 | - | 10 | C-4d631bd07c L16922 (UNVERIFIED) |

## 11. Known limitations
- functions_source=ast@base_commit on 46/48 rich tasks; the 2 misses are pure new-file additions with no base file to parse.
- IMPLEMENTED this iteration: static edit reconstruction (Â§8), near-miss line-level fuzzy matcher nm-3 (Â§9.2) + cross-task FP control (Â§9.4), and the gold-first git-worktree replay engine rp-3 (Â§13). See Â§10 and Â§13.
- REV5 FEAT-001: dev-harness AST pass (D3-5, dh-1) and staged-submission config + zip_drift (D3-4) are implemented; see Â§2 and Â§9.
- REV5 row scope: local-sweep rows are summary-only (no ATIF trace); local-rig and sweep rows never verify the served model (stack.model_served_verified=false).
- REV5 FEAT-003: claims cl-4 (Â§12.1-Â§12.7: tables A/B/C, F1 bar/unit/keyed classifier, ref binding, supersession chains), lever matrix lv-1 (Â§6) and STANDING_TRUTHS.md are implemented. Heuristic limits: facts come from explicit regexes only; a disagreement is asserted (CONTRADICTED) only on a same-line / column / idiom binding to a run of the stack the entry names; weaker bindings are listed, not asserted (log_claims.md Â§3b).
- lv-1 limits: run dates are not recorded, so `prev-same-label` lineage is run_id order; non-main tracks have no curated baseline, so their reference is the modal config (ASSUMED reference); sub-agents / frequency_penalty have no config field (log mentions only).

