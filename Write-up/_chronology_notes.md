# Chronology notes (backbone for write-up). All "L" = line of GEMMA_EXPERIMENT_LOG.md (18,498 lines). Dates as logged.
Caveat: log begins 2026-10-01 (L563); there is NO earlier history in it. Some later dates are mislabeled (see G).

## A. Phases
| Dates | What we did | Key result | Lines |
|---|---|---|---|
| 0. 2026-10-01 design | Hypotheses: gold fixes "conform to a sibling" (Exp 1: 74%), mistake-shape checklist (Exp 2); Biohub discipline imported (pre-register, one change/test, local scorer = hypothesis) | Exp 1 74% RETRACTED same day (Exp 3: ~12% lenient / ~5% strict; fixes ~95% novel synthesis) | L37-49, L77, L293-340, L331-332 |
| 1. 10-01..10-03 early board | v1 timing run: 6 tasks 0 resolved, 4 loop bugs; v2 fixed bugs; first board 0.10; v3 1/6; v5 budget 22 1/6; v6 contract-anchoring 2/6 -> board 0.12 | 0.10 -> 0.12 (public) | L447-470, L529-532, L563-581, L1916, L3461-3468 |
| 2. 10-03..10-12 plateau at 0.12 | v7-v20, v10 (budget 40) 0.08, v15 0.08/0.10, LoRA 0.05; prompt levers (v17, v18, v19v3, v20) all ~1/5; thinking ladder; "v6/0.12 SACRED" | best stays 0.12 for 10 days; 1 scored submission/day; weekly GPU quota | L8393-8405, L8913-8914, L569-575, L5112, L4 standing block L8-35 |
| 3. 10-12..10-17 small models legal | Staff announce E4B/12B/E2B allowed (announcement ~2 days old on 10-12); m12 12B serves 10-13 but 0/4 vs 31B 1/4; clean size ladder 31B 4/6, 12B 3/6, E4B 3/6 (with arch-remap), E2B 0/6 | 12B ~38% slower per task than 31B (309s vs 224s) | L8220-8250, L8513-8537, L11433-11452 |
| 3b. 10-13..10-20 recipe migration | v6w (28/8/80/240 budget, thinking 1024) 0.15 (10-13); A3 delimiter fix 0.18 (10-20) | 0.12 -> 0.15 -> 0.18 | L8393-8415, L11934-11942 |
| 4. 10-17..10-28 local parity rig + E4B | Local E4B/12B parity rigs (llama.cpp, then WSL vLLM) FAIL parity; arms A1-A25 prompt arms; 129-task 31B run 34/129; 58-task denominator cracked | Prompt arms: 8 consecutive nulls; 31B pool 34/129 = 0.264 | L11462-11572, L12572, L12870, L12905-12945 |
| 5. 10-28..11-04 measurement/E4B-prize | E4B $10K track; 31B ca5 0.20 (10-30); 12B-official local 62/91 = 0.681; E4B full pool 10/129; noise floor, retractions, prompt axis closed; E4B board 0.03 | 0.20 best main; E4B 0.03 | L13460-13470, L13760-13768, L13768, L14234, L16238-16250 |
| 6. 11-01..11-10 mechanism work | variance harness (E4B 5 passes mean 10.8 sd 1.17); LoRA path closed (11-04); fresh-retry LoopAgent +1.68 (t=3.18) -> board 0.01; 31B timeout A/B | see C | L17640-17650, L17801-17812, L18145-18150, L18484, L18442-18448 |

## B. Board score history (displayed = floor(k/58*100)/100, L12905-12945)
| Date | Score | Pack | Lines |
|---|---|---|---|
| 10-01/02 | 0.10 | v1/v2-style sibling-conform, "One shot" (log disagrees on date and on whether v1 or v2; see G) | L531, L580, L8399, L8914 |
| 10-03 | 0.12 | v6 (v5 tool_calls 22 + contract anchoring) | L3461-3466, L8400 |
| 10-04 | 0.08 | v10 budget-40 | L8401 |
| 10-05 | 0.08 | v15 budget-12 | L8402 |
| 10-07 | 0.10 | v15 budget-12 (same label, second draw) | L8403 |
| 10-10 | 0.05 | edit-discipline LoRA validation (r32/110 modules) | L8404, L7710, L8296 |
| 10-12/13 | 0.15 | v6w (0.18-recipe budget 28/8/80/240, 9-tool surface, thinking 1024) | L8393-8405 |
| ~10-13 | 0.12 | "branching" (57146757) | L8913 |
| 10-15 | 0.13 | decode sweep (temp 1.0/top_k 64) | L9643-9647 |
| 10-16 | 0.13 | B_temp1 | L10172 |
| 10-16/17 | no score | budget-raise ref 57276407 "scorer threw" | L10275, L10362 |
| 10-20 | 0.18 | A3 delimiter fix @31B ("first confirmed LB win") | L11934-11942 |
| ~10-2x | 0.17 / 0.15 / 0.15 | A3 hard v11 / A23 v3 / A17 | L13419-13420, L16243-16246 |
| 10-27/28 | 0.13 | A25 router (2 sub-agents), blind submission ref 57720023 | L13209, L13416-13427 |
| 10-30 | 0.20 | ca5-31B (pre-edit anchor-grep, no sub-agents, v10 config) | L13760-13761 |
| 10-31 .. 11-01 | 0.22 / 0.15 / 0.17 ; 0.18 | identical-bytes ca5 resubmits | L15131, L16238-16250 |
| ~11-01 | 0.03 | E4B ca5 (2/58) | L16250, L14092 |
| 11-07 | 0.13 | exact 0.20 pack again (ref 58040392); same-byte draws 0.20,0.18,0.17,0.17,0.17,0.13 (mean ~0.17) | L18210-18216 |
| 11-07 | exceeded runtime | 31B cap 50/20 pack (58076615) | L18210-18216 |
| 11-08 | 0.01 | E4B fresh-retry pack 1 (ref 58112867) = 1/58 | L18392, L18484 |
Leader reference: #1 Yurnero 0.29 (17/58); our rank 888/2800 on 10-14. L16717-16726, L8911.

## C. Top findings (measured)
1. Budget/trajectory shape was the real board lever, not the method: 15 calls/120s (v6) -> 28/8/80/240 gave 0.12 -> 0.15 ("+0.03"). L8408-8410
2. Board ~ 0.073 + 0.115 x rich-gate-rate, R^2=0.891 -> each +1 rich resolve ~ +0.019; rich gate is a weak proxy (v10 0/5 yet 0.08). L8681-8720
3. Edit-discipline LoRA (r32 q/v) on 31B: gate 1/5 (edit_fail got worse), board 0.05 - the worst recorded. L5872-5880, L8296
4. Specialist LoRA on E2B, 6 held-out fastapi: base 0/6 (patch 2/6, submit 3/6) vs specialist 0/6 and generalist 0/6 (patch 0/6) -> LoRA degraded loop discipline. L1983-1990, L2082-2094
5. Clean size ladder, identical 6 rich tasks, v6w prompt: 31B 4/6 (1331s), 12B 3/6, E4B 3/6 (376s, only with arch remap), E2B 0/6; earlier 3-way curve VOIDED (five variables moved). L11433-11452, L13499-13506
6. Prompt axis closed: eight consecutive prompt arms null (A24 n=120/arm); empty-prompt baseline: ca5's 7,833-byte prompt worth only +2 to +4 solves. L12870, L16081, L13996
7. 31B full 129: 34/129 = 0.264 (A3); "zero fastapi ever resolved" overturned. L12572
8. Public board denominator = 58 tasks, truncated scores; 1 task = 0.017; gap to #1 was 3 tasks. L12905-12945
9. Board noise: identical bytes scored 0.20, 0.18, 0.17, 0.17, 0.17, 0.13 (also 0.22/0.15/0.17); sigma ~2-3 tasks, not 1. L18210-18216, L15131, L16649, L13343
10. Multi-agent router is monotone-worse: ca5 12 > A3hard 10 > A23 9 > A25 8 (tasks of 58); sub-agent/router axis closed. L16278-16283 region, L13418-13427
11. Budget axis: E4B cap-15 NULL (within variance of cap-28); cap-relaxed NULL n=24; 31B cap 50/20 exceeds scorer runtime. L17114, L13816, L18213
12. Thinking-budget: ladder 4096/2048/1024/OFF tied on gate; E4B main-agent thinking sweep NULL; 4096->512 removes all overflow but converts zero tasks. L7390, L13596, L14558
13. E4B full pool at locked config 10/129, a localization/search deficit; later 5 passes k = 11,9,12,10,12 (mean 10.8, sd 1.17). L14234, L17640-17649
14. Fresh-retry LoopAgent[fixer,verifier] on 39 ever-solved ids, E4B: 11.50 vs control 9.82 (+1.68, Welch t=3.18, sd 1.22 vs 1.69); repro gate 8.88 loses (context overflow 32%). Packs validated: 12.00 (t=3.91) and 11.45. Board: 0.01 (1/58), E4B plain 0.03. L18145-18153, L18257-18262, L18484-18488
15. 31B timeout-recovery A/B, 6 recoverable tasks x 6 rounds: ca5 28/8/300 9/36 (25%); timeout_seconds 60 16/36 (p=0.137); max_time_minutes 10 19/36 (53%, Fisher p=0.029); 12 of 19 solves finished 511-608s. B+C check: 18/18 always-solved kept, recoverable 4/6, task-seconds -3%. L18442-18478
16. Official-12B local rig: 62/91 = 0.681 (claim "established"); local E4B rig does NOT reproduce Kaggle E4B; local requests solves are false positives. L13768, L14767, L14827
17. Sibling-mirror prompt: neutral on 31B paired A/B (85 live tasks). L17763

## D. Retractions / corrections
- Exp 1 "74% sibling-conformable" -> artifact; true ~12%/5% (L293, L331); then over-correction "method dead" corrected (L342).
- v1 "6 tasks 0 resolved = method failing" -> 4 loop bugs (L492); v2 "fixes" regressed (L590).
- 10-02 "3 of my own prior claims RETRACTED" local harness bugs (L1109); wheelhouse-fix hypothesis falsified (L954).
- Specialist-LoRA "format mismatch" theory retracted (L2034); "prose" mechanism corrected to argument collapse (L2387); `1`-collapse was GGUF/base mismatch (L2649, L2714).
- v8 declared negative prematurely (L3951); fastapi_15588 "near-unwinnable" retracted (L4006); verify() mismatch bug (L4062).
- v9 "1/10 and parallel validated" wrong -> 0/10 (L4281, L4311); v10 "2/10" not reproducible (L4746).
- "LoRA is net-negative/parked" wrong - trained wrong (L5010); "LoRA untouched" wrong (L13863).
- Board denominator 129 -> 58; "0.18 ~= 23/129" wrong (L8917, L12944).
- Graph tools: skills "can't ship .py" wrong (L16451); 3 code-intel tools dead (L14385).
- Size ladder voided (L11163, L13499); arch-remap over-generalisation retracted (L11405); "ARM A2 PASS" overstated (L11626); D-arms/A18 edit_err retracted (L12295, L12361); "26-hour server degradation" misdiagnosis (L11872).
- "17 no-patch tasks lever" worth zero (L13974); "phantom budget" was my reproduction bug (L14067); "E4B pool" was actually 12B (L14102), then local ca5 runs ARE E4B (L14797); def2 null, 86% artifact (L14739); "rig is crippled" retracted (L15152).
- Sigma: sigma=1 inferred from one pair (L16238-16260) -> user right, ~2 (L16649); "0.21 score" does not exist (L16654).
- Outside review: three blocking errors in headline numbers (L16301, L16401).
- Cap-simulation 28/8 prediction wrong (L18034); repro-gate "false rejections" -> false ACCEPTS from stale bytecode (L18201-18206).
- "Sub-agent 12B 2x throughput" claim did not hold (L8533-8537).

## E. Earlier competitions / prior experience
- Biohub Cell-tracking (imported discipline): L3-7, L37-49, L2126, L5121, L9576. Lesson: local scorer anti-correlated with LB; pre-register; one change per test.
- Poker: L47 ("poker negative-space insight"), L415 ("redirect to CASMI/poker"), L542 ("append-only, like poker lb_anchors").
- Attack competition (same Gemma family, ~40 scored submissions): L429, L631-663 (multi-tool prompts halve score ~20 vs ~50; shorter prompts no speed gain; ~2-10 tok/s on 5070 Ti; budget discipline), L670, L775.
- CASMI: mentioned only at L415.
- No detailed postmortem of any of these inside the log; only pointers. Attack findings were applied: v3 "tighten for speed" (L665).

## F. Hardware
- Local desktop: RTX 5070 Ti 16 GB, sm_120 Blackwell, torch 2.11 cu128 (L1693-1701). QLoRA stack verified there 10-02 (L1687-1784).
- Cannot train 31B locally ("needs ~80GB", L934, L3178); Colab (L5046, L5296) / Kaggle L4x4 (30 GPU-h/wk, L3604) used instead.
- Local inference: Ollama gemma4:26b -> llama.cpp (10-02, L712, L847); Attack data: gemma-4-26B Q4 ~2-10 tok/s on 5070 Ti (L647); HF+bnb ~5-6 tok/s vs GGUF 64.5 tok/s (12B, L2314); 12B per-task ~9 min locally (L6418).
- E4B local GGUF: Q4_0 64 t/s, Q4_K_M 11.7, Q8 3.8-4.1 (L13640-13645); 52.6 t/s ctx 65536 (L13656). WSL vLLM (L11528, L13714-13743).
- Scoring HW: 4xL4, 31B ~25.5 tok/s (L1060); competitor 12B ~67 vs 31B ~35 (L8249); measured aggregate: per-seq 30 -> 23 tok/s at 4 in flight (L18368-18376).
- Laptop RTX 4050 6 GB (~4.5 free): local E4B NOT viable (L17883-17888); setup attempt via Q4_0 GGUF (L17894-17899).
- Stray llama-server held 6 GB RAM + GPU ~90 min (L8732).

## G. Gaps / contradictions with the author's narrative
1. No pre-10-01 history; "Phase 0 carried lessons" supported only by Biohub, poker (pointers), Attack (L631). "Attack agent" = Attack competition (not "attack agent").
2. First board scores: log shows 0.10 (10-01/02) -> 0.12 (10-03) -> then 0.08, 0.08, 0.10, 0.05 before 0.15 (10-13). It is NOT a monotone quick climb; v1 listed "0.08-ish" at L160 vs 0.10 at L580; L536 says "SECOND submission", L566 corrects to first.
3. Phase 2 cause: log does NOT say the stall was because 31B was slow locally. It documents: 1 scored submission/day (L569), weekly GPU quota (L5112), wrong levers (commitment/LoRA). No record of any attempt to run the 31B locally; log says it cannot be trained locally (L934), and uses gemma4:26b/12B proxies. No local-31B speed number exists. 31B speed only on 4xL4 (~25-35 tok/s).
4. llama.cpp/GGUF/Ollama were used on the 5070 Ti from 10-02, i.e. BEFORE the small models; "pivot after smaller models" for local running is not supported - local proxies existed from day 2, and the 12B was already attempted on Kaggle (v22 v1-v4, "12B CLOSED") before 10-12 (L8230).
5. Small-model release: staff announcement ~2 days before 10-12 (L8220-8222), i.e. ~10-10/11, not 10-11/13; 12B first served 10-13 (L8513).
6. Laptop 4050 appears only 11-04 (L17883) and is rejected as non-viable; no laptop E4B result. The 5070 Ti has no 31B run.
7. LoRA: first idea was edit-discipline (L5857, L8207); localizer trajectories planned (L5345, L3723) and router LoRA spec 10-15 (L9769); only edit-discipline LoRA reached the board (0.05). Date conflict: board table 10-10 (L8404) vs gate result 10-11 (L5872). Also "LoRA did not help" is partly execution-confounded: log itself says v2 trained the wrong target (L5010, L8230 premise).
8. Fresh-retry board 0.01 is not "lower than practice because it failed"; log attributes it to poor E4B practice->hidden transfer (ratio ~0.2-0.33 vs ~0.65 for 31B), and 1 vs 2 of 58 is noise (L18484-18488). Plain E4B ca5 was 0.03.
9. "Hidden repos disjoint": log asserts private repos (L3165) but later infers 129 = 58 public + 71 private mixed (L12934); unresolved. Sequential scorer supported (L197).
10. Date glitches: "2026-12-12" (L8098), "2026-10-09 session"/"2026-10-10" labels on entries at L17928, L17958, L18087, L18145 that sit after 11-04 and before 11-07 (L18210) -> likely 11-0x. Treat as unverified.
11. Sigma: log reverses itself (1 at L16258, ~2 at L16649, 2-3 at L18214); cite the final form.
12. Tasks are 129 in pool but board is 58 (L12905); "58-task public LB" supported.
