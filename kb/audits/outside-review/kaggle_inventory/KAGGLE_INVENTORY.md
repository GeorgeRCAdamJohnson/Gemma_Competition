# Kaggle inventory (live pull, 2026-11-01)

Sources: `kaggle kernels list --mine` saved to `kernels_p1.csv` / `kernels_p2.csv`, and `kaggle competitions
submissions gemma-4-developer-agent` saved to `submissions_live.csv`. Both are read-only pulls. The full Gemma
kernel list is in `gemma_kernels.txt`.

- 118 unique kernels (the UI shows 123; the difference is UNVERIFIED and may be drafts or deleted kernels); 79 are Gemma.
- 25 scored submissions on the live board; `kb/curated/submissions.csv` holds only 10 (see M23).

## E4B on Kaggle

| kernel | tasks | resolved | solved | on disk |
|---|---|---|---|---|
| ca5-e4b-full129-eval (v1) | 129 | 10 (9 genuine) | fastapi 14077, 14301, 14463, 14786, 14851; rich 3006, 3454, 3894, 3905; requests_6644 | `kaggle_pkg/out_e4b` (`out_e4b_v3` is a copy) |
| ca5-e4b-full129-eval (v3) | 129 | PENDING | replication pushed 2026-11-01 | to be pulled to `kaggle_pkg/out_e4b_r2` |
| gemma-sibling-conform-e4b-a3 | 44 rich | 2 | rich_3006, 3905 | `out_k_e4ba3/` (log only) |
| gemma-sibling-conform-e4b-a5 | 44 rich | 3 | rich_3006, 3067, 3905 | `out_k_e4ba5/` (log only) |
| gemma-sibling-conform-remap-e4b | 6 | 3 | rich_3006, 3454, 3894 | `submit_remap_e4b/out_v1` |
| gemma-sibling-conform-size-e4b | 6 | 0 | — | `submit_size_e4b/out_v1` |
| gemma-sibling-conform-v7-e4b | 6 | 2 | rich_3006, 3454 | `submit_v7_e4b/out_v2` |
| scored submission 57807043 | 58 hidden | 0.03 = 2/58 | unknown (hidden) | — |

Counts are parsed from the `resolved=` lines in each kernel's stdout log. Every task solved by any E4B Kaggle run
is inside the 17-task local E4B union, so Kaggle shows no E4B-only solves. Only the latest version of each kernel
can be pulled, so earlier versions are UNVERIFIED.

## Not yet inventoried

There are 12B kernels (a3, a5, a6, a10, a11, a13, a14, rerun3006, 9t, size-12b), 31B arms (a21, a22, a23,
a3-hard, ca5-31b-full129-eval) and the v1–v22 / v6* series. Most have local pulls under `Gemma/submit_*` or
`Gemma/Outputs/`; they are not cross-checked here.
