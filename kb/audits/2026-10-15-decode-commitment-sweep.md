# decode-toward-COMMITMENT sweep -- LOCAL gold-first scorer (rp-4)

> **LOCAL-ONLY, FREE-GATE-CANDIDATE -- a win here is a hypothesis for the FREE Kaggle gate per gemma-submission-protocol.md, NOT a scored-slot change; the local backend (llama-server at 127.0.0.1:8081) is NOT the competition 31B.**

## Verification (read without re-running)

- Backend 127.0.0.1:8081: UP.
- Scorer: FIXED per-task-pinned gold-first replay engine rp-5 (kb/kblib/replay.py); agent attempts scored via ReplayEngine.run_candidate, validity via ReplayEngine.gold_first.
- rich clone `C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval\repos\rich` git status: DIRTY:
M rich/padding.py
- fastapi clone `C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval\repos\fastapi` git status: clean
- Writes confined to Gemma/kb/ and Gemma/local_eval/ (report, jsonl, _decode_sweep_cache/, replays/cache/); run_local.py edit is additive (penalty 0.0 == prior payload).
- %TEMP% gkb_* scratch after run: ['C:\\Users\\Biges\\AppData\\Local\\Temp\\gkb_11432_cu4979ul', 'C:\\Users\\Biges\\AppData\\Local\\Temp\\gkb_11452_gqakdxfg', 'C:\\Users\\Biges\\AppData\\Local\\Temp\\gkb_17736_fxup5toj', 'C:\\Users\\Biges\\AppData\\Local\\Temp\\gkb_30080_gw_8e3rl', 'C:\\Users\\Biges\\AppData\\Local\\Temp\\gkb_40868_79h7i3wa'].
- Gold gate: 11/11 tasks VALID.

## PRE-REGISTERED BAR (frozen before any arm ran)

Baseline arm = v6w-equivalent sampling (temperature 0.2, top_p 0.95, top_k 64, NO penalty), run FIRST locally through the FIXED per-task-pinned gold-first scorer, establishing the LOCAL resolve count and the commit-timing proxy for THIS backend. The local backend is a local llama-server at 127.0.0.1:8081, NOT the competition 31B, so the LOCAL baseline is the only comparator -- never the 0.15 board number. An arm WINS on the held-out CONFIRM split only if it either (i) resolves at least as many CONFIRM tasks as baseline AND strictly improves the commit-timing proxy (strictly earlier median first_edit_at OR strictly fewer no-edit runs), OR (ii) resolves strictly more CONFIRM tasks. A tie on resolves with equal-or-worse commit-timing is a FAILURE. One axis changes per arm; the baseline is a hard floor. A null (no arm beats baseline on CONFIRM) is a valid reported result.

_Success bar (short):_ WIN on CONFIRM iff (i) resolves >= baseline AND strictly better commit-timing (earlier median first_edit_at OR fewer no-edit runs), OR (ii) resolves strictly more. Tie-resolves-with-equal-or-worse-timing = FAILURE.

Board context (NOT a comparator): v6w @ 0.15 (submission 57098497) is live-best; v6w+temp1.0/topk64 @ 0.13 (submission 57201051) regressed. These are 31B board numbers, quoted as context only.

## Frozen task set, EASY/HARD labels, held-out split

| task | gold class | split | gold gate | included |
|---|---|---|---|---|
| rich_4077 | EASY | DISCOVER | VALID-HARNESS-LIKE | yes |
| rich_4079 | EASY | DISCOVER | VALID-HARNESS-LIKE | yes |
| rich_4076 | EASY | CONFIRM | VALID-HARNESS-LIKE | yes |
| rich_3469 | EASY | CONFIRM | VALID-HARNESS-LIKE | yes |
| rich_3471 | EASY | DISCOVER | VALID-HARNESS-LIKE | yes |
| rich_3278 | EASY | CONFIRM | VALID-HARNESS-LIKE | yes |
| rich_2943 | EASY | DISCOVER | VALID-HARNESS-LIKE | yes |
| rich_3470 | EASY | CONFIRM | VALID-HARNESS-LIKE | yes |
| rich_3882 | EASY | DISCOVER | VALID-HARNESS-LIKE | yes |
| rich_3518 | EASY | CONFIRM | VALID-HARNESS-LIKE | yes |
| rich_3935 | HARD | DISCOVER | VALID-HARNESS-LIKE | yes |

DISCOVER (tune): rich_4077, rich_4079, rich_3471, rich_2943, rich_3882, rich_3935

CONFIRM (held-out, judges the bar): rich_4076, rich_3469, rich_3278, rich_3470, rich_3518

Excluded up front (multi-file giants, out of a 28-call agent's reach):
- rich_3930: 26 files / 12.7k lines (grapheme rewrite) -- out of a 28-call agent's reach
- rich_4070: 9 files / 128 lines (import-defer perf refactor) -- out of a 28-call agent's reach

## Per-arm vs baseline (judged on CONFIRM)

All numbers below are MEASURED (each ties to a JSONL row / cache file) unless a cell says INFERRED. `median first_edit_at` and `no-edit runs` are the commit-timing proxy.

| arm | axis | CONFIRM resolves (n/N ran) | CONFIRM median first_edit_at | CONFIRM no-edit runs | CONFIRM mean tool_calls | DISCOVER resolves | VERDICT |
|---|---|---|---|---|---|---|---|
| baseline | v6w-equivalent sampling (comparator / hard floor) | 0/5 | 9 | 0 | 12.8 | 1/6 | BASELINE |
| temp_00 | axis(a) greedy decode | 0/5 | 8 | 0 | 8.6 | 0/6 | WIN |
| temp_01 | axis(a) temperature 0.1 | 0/5 | 9 | 0 | 12.4 | 0/6 | FAIL(tie-no-timing-gain) |
| freq_02 | axis(b) frequency_penalty 0.2 | 1/5 | 8 | 0 | 12.6 | 1/6 | WIN |
| freq_04 | axis(b) frequency_penalty 0.4 (log: killed repeat-loop) | 1/5 | 8 | 0 | 12.2 | 1/6 | WIN |
| pres_02 | axis(b) presence_penalty 0.2 | 0/5 | 7 | 0 | 11.8 | 0/6 | WIN |
| pres_04 | axis(b) presence_penalty 0.4 | 0/5 | 10 | 0 | 12.8 | 0/6 | FAIL(tie-no-timing-gain) |
| reserve_tail | axis(c) commit-by-remaining nudge via kaggle NUDGE_MODE + reserve-tail (nudge_max 5) | 0/5 | 9 | 0 | 11.6 | 2/6 | FAIL(tie-no-timing-gain) |

## VERDICT

**WIN candidate(s): temp_00, freq_02, freq_04, pres_02** -- cleared the pre-registered bar on the held-out CONFIRM split vs the LOCAL baseline. LOCAL-ONLY, FREE-GATE-CANDIDATE -- a win here is a hypothesis for the FREE Kaggle gate per gemma-submission-protocol.md, NOT a scored-slot change; the local backend (llama-server at 127.0.0.1:8081) is NOT the competition 31B.

## Caveat

LOCAL-ONLY, FREE-GATE-CANDIDATE -- a win here is a hypothesis for the FREE Kaggle gate per gemma-submission-protocol.md, NOT a scored-slot change; the local backend (llama-server at 127.0.0.1:8081) is NOT the competition 31B.
