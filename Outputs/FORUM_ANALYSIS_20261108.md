# Forum analysis, Gemma 4 Developer Agent (dump 2026-11-08)

Source: `discussions/20261108/topics.json` (315 topics). Every topic and nested reply was loaded programmatically and swept (score mentions, host-style phrases, small-model mentions, bug keywords). About 95 topics were read in full or near-full (all high-vote, all host-answer, all bug, all edit_file, all LoRA, all compaction, all noise threads). The remaining ~220 are mostly "stuck/pending/Kaggle Error" status posts, team-up posts and duplicates; they were skimmed by title and sweeps only.

Tag legend. Author names are blank in the dump, so attribution is inferred:
- **HOST-CONFIRMED**: reply is from Ryan Holbrook (@ryanholbrook) or another Kaggle staff member, identified because the thread tags him and the reply speaks with ownership ("I will patch", "fixed in the latest wheelhouse", "the scorer has this update already"), or because a later post cites it as his.
- **HOST-LIKELY**: unlabeled reply with staff-style authority and no contradiction, but not independently confirmed.
- **claimed**: a competitor's statement or measurement.

Quotes are kept under 25 words. Topic ids are in `[topic N]`.

Not in the forum: any config, prompt or method from the #1 team (Yurnero / samson8 as a name). The only 0.29 mention is a one-liner without details [topic 752848]. "@samson8" is addressed once in [topic 750521] ("were you able to achieve 0.24 ... finetuning or just prompts?") and the answer in that thread is not identifiable. No post claims 0.25+ with a disclosed method.

---

## 1. Scorer facts and host statements

### 1.1 Concurrency, sandbox, timeouts, eval_config

- Hidden tasks run **sequentially** (concurrency 1). HOST-CONFIRMED [topic 743063].
- The scorer reads **only four eval_config fields** (`timeout_seconds`, `max_tool_calls`, `max_time_minutes`, `max_turns`); default is no limit. HOST-CONFIRMED [topic 743063].
- eval_config does **not** affect the verification/scoring step. The scorer only receives patches. The verification pytest has a fixed 300 s timeout. The eval_config caps **do** apply while the agent runs. HOST-CONFIRMED [topic 748428].
  - Earlier reading of the code suggested `timeout_seconds` also bounded verification pytest [topic 745805 Q3]; the host said he would double-check. The 748428 answer is the resolution.
- Sandbox: "same sandbox but different wheels" as the public harness; no network-timeout delay at container setup; `enable_sandbox_testing` is true (agent can run pytest); the package under test and its cached test deps are importable in place in both agent and verification sandboxes. HOST-CONFIRMED [topic 748428].
- Host never answered: Docker vs subprocess for the agent phase, python 3.12 vs 3.13 in the agent sandbox, `network_mode none`, `reuse_containers` [topics 748428 follow-ups, 745975, 747704 as cited]. Unanswered as of the dump.
- Host said no significant command overhead vs a plain container [topic 745805 item 4]. HOST-CONFIRMED.
- Host: private Docker sandbox uses the same base image but different dependencies because hidden tasks come from other repos. The public "subprocess" sandbox (Getting Started notebook) is the source of many public-task failures [topic 742882]. HOST-CONFIRMED.
- Parallelism: host said "we don't support parallel calls" [topic 743964]. Later he suggested ParallelAgent for concurrent LLM calls with tool calls still sequential [topic 748287]. A known ADK 1.36 bug breaks ParallelAgent with tool calls; host declined to migrate to ADK v2 ("too risky") [topic 748287]. Workaround claimed: keep parallel sub-agents tool-free [topic 748287]. HOST-CONFIRMED (decline), claimed (workaround).
- ADK: only the wheelhouse set is supported; no ADK 2.x; most ADK 1.x config allowed except arbitrary code execution [topic 743800]. HOST-CONFIRMED.
- Mixing model variants in one submission is not supported (e.g. 31B main + 12B sub-agent); LoRAs may differ per agent [topics 745805 item 8, 748287]. HOST-CONFIRMED.
- Custom Python tools are impossible (closed registries); scripts ship inside skills and are run in the sandbox [topic 743573]. HOST-CONFIRMED. `exit_loop` is not in the tool registry [topic 745792, 747519 item 4], claimed (no host reply).
- Undeclared or hallucinated tool names raise a ValueError in ADK, which ends the task with an empty patch; host replied "let me look into it and I'll implement something" [topic 745028]. The fix status is not confirmed anywhere. The task prompt advertises graph tools even when not declared. Omitting unused tools from agent.yaml is allowed [topic 746235, HOST-LIKELY]. Item 10 in [topic 745805] ("a fix for bad tool calls will also be live soon") is HOST-CONFIRMED but unverified.

### 1.2 The 12 h limit

- 12 h covers the **whole** run for public + private tasks together, ~120 tasks total (~60 public / ~60 private). HOST-CONFIRMED [topics 744258, 746008, 745805 item 5]. Public LB is exactly 58 tasks (derived from truncation of displayed scores) [topic 743506], claimed but exact. 1 task = 0.0172.
- Exceeding 12 h **errors the whole submission** (no partial credit) at least as of 2026-09-24 [topic 743063]. Host planned to score unfinished tasks as 0, then on 10-07 said he was "reconsidering" because public and private run in the same pass [topics 743063, 745805], and on 10-15 said naive zero-scoring "could lead to inconsistent results" on public vs private [topic 749597]. No change was ever made. HOST-CONFIRMED. An independent data point confirms in practice: a config differing only by an extra test-rerun step ended in Notebook Timeout after ~12 h with no score [topic 752017], claimed.
- Reports of runs past 12 h wall-clock that still scored are explained by queue time being excluded: "queue time NOT included, only the run" [topic 748443] (HOST-LIKELY; later cited as the host's 10 Oct reply in [topic 752017]).
- The 12 h charge covers the agent phase including sandbox setup, excluding patch validation [topic 750753 quoting the Evaluation page; 743663]. Patch validation takes ~2 h if every task submits a patch; tasks with no patch skip validation [topic 743663, HOST-LIKELY].
- Scored runs observed to take 8.9 to 11.9 h [topic 752017], claimed. A 4.5-min cap took ~10 h (each task adds ~0.5 min setup and verification) [topic 746250 reply], claimed. A 6-7 min cap fits only if enough tasks end early [same].
- vLLM server start-up counts toward the 12 h: question 6 in the aggregated list was answered "6. Yes." [topic 745805]. HOST-CONFIRMED. (A separate startup limit of 1,200 s applies; exceeding it kills the run before task 1 [topics 751264, 749191].)
- No cancel button for pending submissions; one-pending-submission limit introduced 10-08 [topic 747519]. HOST-CONFIRMED.
- Rerun policy: the 10-08 queue-timeout recovery was "one-time, not continuous" [topic 747519, 10-13 reply]. On 10-22 the host acknowledged a scorer-side failure for "Notebook Threw Exception" and promised reruns [topic 751339]; many users still reported no rerun a week later [same]. HOST-CONFIRMED (promise), claimed (non-delivery).
- Final selection: up to two final submissions; the private score is the better of the two, no downside to picking a second [topic 752220], HOST-LIKELY. Each submission is scored once on the whole set in the same run; hosts do not rerun at the end [topic 746008], HOST-LIKELY. Request for multi-run averaging was not answered by hosts; one commenter says Kaggle never does that [topic 754295], claimed.

### 1.3 Compaction

- The Getting Started notebook uses `token_threshold=14336`; README section 7.2 lists 32768/interval 15 (a stale value). One reply states the scorer uses 14336 [topic 748584, HOST-LIKELY]. Another poster states the scorer compacts at 14,336 with interval 5, overlap 2, retention 5 and the default LlmEventSummarizer [topic 747186], claimed. The host never gave an explicit statement. The same config applies to all variants per host ("everything is the same") [topic 748287], HOST-CONFIRMED.
- Submissions cannot set the compaction prompt or thresholds. The host has not agreed to add it [topics 747186, 752848 complaints]. Host says ADK v2 migration is off [topic 748287].

### 1.4 Hidden vs public data

- Hidden tasks come from **private repositories** not available publicly; none of the published training repositories occur in the test set. HOST-CONFIRMED [topics 744951, 747248].
- Every test task validates at 100% with a gold patch. HOST-CONFIRMED [topics 747248, 742882, 748428].
- Task curation: fail-before/pass-after tests; varied repos and sizes; filtered by running a strong commercial model with a simple config and keeping tasks it solved or missed by one assertion [topic 748428]. HOST-CONFIRMED. Implication: easy-ish/solvable edge cases, different repos.
- Data page says problem statements come from the original problem description, issue thread or bug report (cited in [topic 753499]); whether PR-body-only statements exist in the test set was not answered. 18/129 public statements are title + unreachable link [topic 746944]; hidden-set share unknown.
- Exact hidden task order / public-private interleave: not answered [topics 743063, 745805].

### 1.5 Changes the hosts made during the competition (wheelhouse)

All HOST-CONFIRMED unless noted:
- ~09-26: LoRA support patch for vLLM 0.19.1 ("zeroing" bug fixed in wheelhouse v23) [topics 743508, 743213].
- 09-30: tool results sent as one JSON level instead of double-encoded, and `edit_file` got an "unescaped" retry fallback [topic 744272]. Thought retention across tool calls fixed (reasoning_content) [topic 744354]. `thinking_budget` and `seed` forwarded [topic 744566]. LoRA slots sized from the submission (`max_loras` dynamic) [topic 744794].
- 10-01 to 10-08: test-file reset fix "live soon" [topics 744825, 745805 item 9]; `search_similar_code` output to be limited to `max_stdout_chars` [topic 744577].
- ~10-09/10: `include_thoughts: false` **no longer disables thinking**; `thinking_budget: 0` does. Intentional: `include_thoughts` now controls whether thoughts are carried in the chat template between calls [topic 747914]. Anyone relying on include_thoughts:false got thinking ON from 10-08 on (local 90 s task became 316 s) [topic 747914, claimed measurement].
- 10-11: E2B/E4B/12B added, same scoring conditions as 31B [topic 748287]. 12B requires `--hf-overrides` and a vision_embedder weight-loading fix, "fixed in the most recent wheelhouse" [topic 748287]. Yet several 12B bundles still ended in Notebook Threw Exception [topic 749259], claimed.
- 10-12: wheelhouse update (swegemma 0.2.11, adk_submission 0.2.13); then "unchanged since 10-12" through 10-22 [topic 747519].
- 10-08 queue fix: extended queue timeout, reprocessed timed-out submissions, pending-submission limit [topic 747519].
- 10-20: $10k small-model bonus prize (E2B/E4B) [topic 751104].
- Small-model leaderboard notebook is maintained by the host; best small score was 0.06 on Oct 20 [topic 750974, claimed].

### 1.6 vLLM tool-parser freeze bug status

- vLLM 0.19.1's gemma4 tool parser loops forever on array arguments in specific malformed shapes; it blocks the API server event loop and ignores SIGTERM [topics 746336, 745138, 753973]. Competitor-claimed, with reproducible minimal strings.
- Status: **unresolved**. No host reply in [topic 753973] (last user ping 2026-11-09; "any update on this?" on 11-08). Upstream fix is vLLM #41991, shipped in v0.21.0, so 0.19.1 does not contain it [topic 746336]. No host statement on a guard.
- Second 0.19.1 parser problem: strings written in plain JSON quotes keep the quote characters, e.g. `skill_name:"my-skill"` arrives with quotes [topic 746336, 10-25]. Third: tool calls emitted before the thought channel closes are returned as reasoning and dropped (~1% of local runs, 31B) [topic 753521]. Neither has a host reply.
- Practical trigger: only array-typed tool arguments (e.g. `run_skill_script args:[...]`). A plain single LlmAgent with built-in tools (all arguments are strings) has no array argument [topic 746336 says the affected arg was `args` in `run_skill_script`].

---

## 2. What top teams say they do

Evidence is thin. No disclosed 0.25+ method exists in the forum.

- Consensus from people reporting 0.20-0.24: **single LlmAgent + one `system.md`**, no sub-agents or skills. "Most scores even up to 0.22 are single-agent frameworks" [topic 748051]; the highest public non-LoRA notebooks (~0.22) use a basic LlmAgent and a one-page system.md [topic 754636]; one 0.18-0.20 author says it came from iterative prompt edits and runtime parameters only, no sub-agents or custom skills; sub-agents and skills hurt due to context [topic 750496].
- Public recipes that people cite as the 0.17-0.22 baseline: "Budget-Fit single agent" (8 min / 28 calls, prompt asks for a source edit by call 12) [topics 749198, 750974, 751596]; "Gemma 4 SuperAgent" and "Budget-Aware Coding Agent V10" [topics 748051, 755172, 747519].
- Typical working settings reported: 8 min / 28-30 calls / thinking 4096 / temperature 0.2 / top_p 0.95 / max_output 8192 / timeout 240 [topics 748168, 750496, 755677]. Several runs at 8 min + 28 calls timed out the whole submission [topics 748618, 748168, 750350], others did not (0.17/0.18/0.18 at 8 min/28 calls [topics 747519, 755677]). This is exactly the knife-edge you measured.
- One participant at 0.15-0.17 on a v19 pack: analyzer sub-agent, elapsed-time feedback, 7.5 min [topic 747696]. 0.17 was their best.
- "Prompt gate that forces an edit by call 12": 38% of default-prompt tasks never edit a source file; with the gate it falls to 11.6%, but solved tasks rose only from 26 to 30 of 69 attempted [topic 749198, claimed].
- Quiet signal about hidden vs local: the 0.17 team whose local screen "never ranked our hidden scores": two configs tied 28/74 locally scored 0.17 and 0.10 on the board; a change winning 9-0 locally scored lower [topic 751973].
- 756438 (a reply in a "time allocation" thread): ".20 also scored .18 .17 .17 .17 .13" matches your own draws; it appears to be your own team's post or a near-copy [topic 756438].
- 0.24 (6 teams) and 0.22 (48 teams) are the top plateau; only 14 distinct score levels exist [topic 753524]. No explanation exists for how the 0.29 was reached.
- What people say did not help (top-score adjacent): LoRA (see 3.7), sequential/loop agents with skills (0.03-0.08 for 5-min caps) [topic 750350], analyzer sub-agent (+1 task, noise) [topic 746250], graph tools [topics 746250, 756400, 745731, 748323], higher thinking (HIGH = 60% more time/tokens) [topic 748168].

---

## 3. Known bugs and pitfalls (mechanisms and workarounds)

### 3.1 edit_file argument loss: the likely mechanism for "old_string loss"

Several independent reports describe the same signature:
- Rejected with "mandatory input parameters are not present"; 60/234 `edit_file` and 20/255 `write_file` calls vs 0/1,135 `run_command` calls (31B, thinking 4096, 104 runs) [topic 747519 item 3, claimed].
- Received arguments look like: `new_string` whose value **ends with a backtick** followed by the next key name, `old_string` missing, and a **third key whose name is a line of the source code** with value a backtick [topics 747519, 756051]. In one run 51 consecutive calls, 38 byte-identical [topic 756051].
- Other reports: arguments like `<|"|>,filepath` when `old_string` contains `"""` [topic 747168]; `"filepath": "src/x.py\`,old_string:"` [topic 747923].
- 43% of 246 `edit_file` calls failed in one 16-task study [topic 747923]; tools with a single string argument did not lose arguments [topics 747923, 747519].
- It recurs inside runs (4 successful edits then failures), and the model "knows" the correct JSON in its reasoning but still emits the bad call [topic 756051].

**Inferred mechanism (our reading, not stated by anyone as a single sentence):** Gemma's native call syntax wraps each string in `<|"|>`; the vLLM gemma4 parser pairs delimiters in order. When the model emits a backtick (markdown habit) instead of `<|"|>` as the **closing** delimiter of a string argument, the parser keeps reading until the next `<|"|>`, which is actually the **opening** delimiter of the next argument's value. Every delimiter after that is off by one: the first string absorbs `` `,old_string: ``, the real `old_string` content is parsed as a key (the "key that is a line of source code"), and its closing marker becomes the stray backtick value. That reproduces the observed three-key object exactly. Triggers cited: `"""` docstrings and long multi-line strings; multi-string-argument tools (edit_file has three strings) vs single-string tools which never failed. Supporting evidence: a poster's tip to spell `<|"|>` in the prompt because Gemma copies the call spelling it sees [topic 746336, 10-25, measured effect not reported]; "saying don't X makes X more likely, quotes and newlines for example" [topic 746502]. The 'competitor claim' of a one-line prompt fix with affected calls failing 93% vs 11% [topic 756607] is almost certainly about this: affected calls fell from 4.5% to 1.2% and 60+-call retry loops disappeared, but that team says its run with the fix **scored lower on the public LB** and the effect on the hidden score is unconfirmed [topic 756607].
- The harness error names only the missing parameter, so the model cannot tell its call was split and resends identical calls (up to 43 resends) [topics 747519, 747168, 756433]. Rejected calls do not count toward the tool-call cap but cost time [topic 747168].
- Separate cause 1 (fixed by host): double-JSON-encoding of tool results made models copy escapes into `old_string`; 62/299 failures, 39 provably escape-related [topic 744272]. Host fixed it on 09-30 (one JSON level, "unescaped" fallback) [HOST-CONFIRMED]. Residual: if only `old_string` needs unescaping, `new_string` is written with the escapes as typed [topic 744272, 11-08]; 12B copies escapes more than 31B [topic 747923].
- Separate cause 2: models copy line-number prefixes into old_string; prompt "strip line-number prefixes" suggested [topic 745003, claimed].
- Separate cause 3 (E4B): QAT E4B drops a trailing "s" when copying (directs to direct) due to an unusually small `per_layer_model_proj` tensor; doubling it or a training-free rank-128 LoRA fixed 14 of 15 failing copy inputs in a targeted test [topic 753277, claimed].
- Workarounds reported: (a) edit through `run_command` with a heredoc and a SEARCH/REPLACE or single-string-argument editor (`robust-edit` skill: edit_file failures 43% to 29%, editor failures 11%, but resolved count unchanged 6/16) [topic 747923]; (b) a "single-argument heredoc editor" in a public entry [topic 755172]; (c) include the `<|"|>` delimiter instruction in the prompt [topic 746336]; (d) re-read the region before editing [topic 745003].
- Chat template: the original 31B template (June) differs from the July canonical one; visible text plus tool_calls in one assistant message closes the turn without opening a new model turn [topic 744844]. Hosts said they would investigate (10-12). Not confirmed deployed. Submissions cannot change the template.

### 3.2 Loops and repeated calls

- Baseline agent repeats an identical command up to 69 times [topic 745774]; temperature 0.7 made it worse (5/10 tasks looped); reducing the call budget limited damage more than any prompt wording [topics 745774, 746523]. "Never repeat" instructions stop binding once looping [same].
- 34 consecutive byte-identical assistant turns in the edit-failure loop [topic 756051].
- Hosts' callback registry is empty, so loop-breaking callbacks are not possible [topic 743964]. Forced tool calls not exposed [same].

### 3.3 Context overflow and compaction

- ContextWindowExceededError is caught by a generic `except Exception` that **skips the fallback `git diff`**: 44/44 overflowed sessions had an empty patch, 14 after successful edits [topic 744692]. Timeout and call-limit paths do capture the diff. Hosts have not announced a fix (no reply on 744692/745977).
- Overflow rate ~12% of sessions at threshold 14,336 and 17-33% at 32,768; with `max_output_tokens: 8192`, anything over 24,576 prompt tokens cannot be sent [topics 744692, 745977]. Headroom math: 32768 - 14336 - 16384 = 2048 for the default output reservation [topic 747791].
- A single `search_similar_code` call can return >30k tokens (FastAPI nodes of 110-130k chars) and end the task; host agreed to cap output [topic 744577].
- `LlmEventSummarizer` keeps only `part.text`, dropping tool calls and tool results; summaries then say "no actions yet" and the agent loops or restarts [topics 754783, 747186, 744794]. If the model writes text before tool calls (thought summaries), some content survives [topic 754783 reply]. Summary call is sampled without the submission's temperature/top_p/top_k (falls back to generation_config 1.0/0.95/64) [topic 753225, measured locally; scorer unmeasured].
- Compaction triggering mid-pipeline resets multi-agent flows; SequentialAgent restarts from stage 1 on a continuation nudge; one shared clock/counter for all agents [topics 754636, 747519 item 4]. This is why multi-agent routers hurt.
- Automatic budget warning at 80% of `max_tool_calls` only; no time-based warning [topics 750490, 749198 says "10 calls remaining" for caps >= 20]. `get_status()` exists but models ignore periodic-use instructions [topic 750490].

### 3.4 Thinking and sampling plumbing

- Thoughts were not carried between tool calls until the 09-30 fix [topic 744354, HOST-CONFIRMED fix].
- `include_thoughts: false` meant `enable_thinking: false` in 0.2.12; from 0.2.13 (10-08) it no longer disables thinking, `thinking_budget: 0` does [topics 745059, 747914].
- Thought summaries off cost 12 points locally (27.1% vs 39.5%); thinking disabled 17.8% vs 37.2% [topic 746250, claimed].
- `thinking_token_budget` requires `--reasoning-config` on the server side; a missing flag made all 24 tasks fail locally in 0.2.12 [topic 745059]; the scorer started adding `--reasoning-config` and `--no-scheduler-reserve-full-isl` [topic 744807, claimed].

### 3.5 ADK / harness quirks

- Unknown tool name or `run_skill_script file_path` passed as a list raises and ends the task with an empty patch (3% of skill-based runs; 33/960) [topic 745028, claimed]. Prefer no skills, or give a one-element string.
- Task prompt "Workspace Layout" is `find ... | head -150`, which omits the source package in 115/129 tasks (all fastapi and rich) [topic 745220]. `search_similar_code` is an exact node-id lookup; keyword queries return nothing (140/142 empty) [topics 745220, 745028 reply, 746250].
- `read_file` caps at 150 lines (anything over ~400 lines needs grep first) [topic 755291, claimed]; `run_command`/`read_file` output cap is 5,000 chars [topic 744577].
- `run_command` blocks the event loop; multiple tasks per process freeze [topic 747168].
- Test-file reset before test_patch was a no-op (editing existing test files sinks correct fixes) [topic 744825]; host: fix coming. Do not edit existing tests [topic 747923].
- Required-test matching quirks (skipped sibling test or opposite skip conditions) make some public tasks unpassable [topics 751707, 754586, 747248].
- Zip hygiene: directory entries / extra files / `.pyc` cause "incorrect format" or errors [topics 747519 (host reply), 752282].

### 3.6 Docker vs subprocess, public environment

- Plain notebook (subprocess) grading: only 52/129 public gold patches pass (fastapi 10/67) because wheels lack `typing_inspection`, `inline_snapshot`, `dirty_equals`, `pytest-httpbin`, and the repo's own released wheel shadows `/workspace` [topics 747248, 751487, 756400, 750345]. A rebuilt scorer-like sandbox gets 127/129 [topic 751487]. 61 of 129 public tasks "cannot tell agents apart" (gold fails or empty passes) [topic 756400]. Host's stance: the hidden set validates 100%; the training set is being "fixed up" (not delivered by 11-08) [topic 747248].
- Hence local public-set rates are unreliable unless you use a rebuilt sandbox and only the ~68 valid tasks [topic 756400].

### 3.7 LoRA

- Early patch bugs fixed by v23-v25 [topics 743508, 744070]. Adapter outputs unchanged by random weights were explained as saturation plus layer-0-only sample [topic 749528].
- Memory: with `--enable-lora` CUDA graphs are captured twice; KV drops from 36k to ~27.7k tokens (or 7.6k before v28) [topics 744331, 749191]. Startup OOM "warming up sampler with 256 dummy requests" depends on `VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=1` (host: the Getting Started notebook sets it; "successful submissions with LoRA up to rank 64") [topic 749191, HOST-CONFIRMED].
- Time: LoRA adds ~15-29% per task (decode 1.3x slower) [topics 751596, 755677]. A rank-16 adapter at 8 min/4096 thinking ended "complete, no score" (12 h overrun); the same adapter at 6 min/2048 scored 0.17, equal to the no-adapter baseline [topic 755677, claimed]. Another team: same bundle without adapter 0.15, with adapter "exceeded runtime" [topic 749191].
- Results: no one reports a held-out gain. Many null or negative: A1/A2/A3 distillation LoRAs lost or tied prompt-only (0.12 vs 0.15-0.17) [topic 751596]; 1,500-trajectory LoRA scored 0.0 due to scaling and repetition [topic 750713]; E4B SFT, teacher distillation and rejection sampling no better than base [topic 753793]; "none beat baseline" [topic 752797]; only localization-focused SFT "helped" (unquantified) [topic 753793].
- A rank-32 LoRA with a 4-minute cap scored non-zero [topic 755677]. A 489 MB rank-16 scored 0.08 [topic 749191].
- Host: only LoRA adapters are accepted; a reply in [topic 756792] says hand-built adapters are fine "as long as it loads" (claimed, author unclear). 3 GB total submission limit [topic 743964, HOST-CONFIRMED].

### 3.8 Timeouts

- 8-min session timeouts are common; competitor measurements show timeouts 61/129 at a 6-min cap, 26 at 10 min, 3 at 15 min (B40 hardware, faster than L4) [topic 746250].
- Most timeouts come from long model turns (76% of budget is decode) and restating files [topic 755291, 12B, claimed].
- Command timeouts almost never bind: 24 of 7,424 commands exceeded 120 s and all failed or timed out [topic 755066]; command timeout 100-300 s made no detectable difference [topic 747857].
- Seeds: `seed` reaches vLLM since the wheelhouse v28 patch [topic 744566], but sampling is nondeterministic anyway.

---

## 4. Small-model (E2B / E4B / 12B) track

- E4B 0/31 solved at 5-min cap on a 31-task local set; 12B 4/31; 31B 9-11/31. E4B submits a patch in 97% of runs but edited the wrong file in 13/31 tasks and sometimes overwrote whole files [topic 750974].
- 12B decodes ~1.9x faster than 31B on 4xL4 but writes ~1.8x more per call, so no net speed win; 12B never solved a task the 31B missed; patch rate 46% vs 78% [topic 750974 comment, claimed].
- 12B at 8-min caps ran past 12 h and got no score [topic 750974]. Several 12B bundles that were identical to scoring 31B bundles ended in Notebook Threw Exception [topic 749259]; E4B "incorrect format" errors on alias-only bundles [topic 752128]. Host answer: small models use the same conditions [topic 748287].
- E2B study: reads the right file, ~3/4 of failed `edit_file` calls repeat a failed call verbatim, most distinct failures put intended or absent code into old_string; none of harness changes (recovery instructions, tool removal, editor sub-agent, temperature/reasoning) resolved a task [topic 756433].
- What anyone says works for small models: very little. A targeted tensor fix for copy errors (753277, targeted tests only); localization-only SFT [topic 753793]; a hand-built editor skill that removes the edit_file failure class (12B proxy: escapes copied "very common") [topic 747923]. No measured board gain is reported.
- Small leaderboard: 0.06 best on Oct 20 [topic 750974]; the board gap to ~0.10 leader is not explained anywhere in the forum.
- Why practice gains do not transfer (claimed explanations, all unverified for the scorer):
  1. Local public-set results are inflated/noisy: 61/129 tasks cannot discriminate; five pass with empty patch; gold fails on 34 due to missing libs [topic 756400]. 38 Rich tasks CV 0.21-0.32 had LB 0.10-0.03 (inverse) [topic 744319].
  2. Hidden repos are different and "behave very differently"; a 50% public agent timed out at 15 min/task and scored 0.05 at 5 min with thinking off [topic 756400].
  3. Public statements often name the fix function (27/50) or are title + unreachable link (15/50); hidden statements are described as issue-based [topics 753499, 746944]. A small model that does well when the statement names the function loses when it must localize [topic 750573: 43/45 mined statements carried part of the fix].
  4. Hidden tests are slower on heavier repos; local timing underestimates cost of test-running steps (+5% locally, runs that timed out hidden) [topic 752017 comment].
  5. Run-to-run noise (15% of tasks flip between identical Gemma 31B passes) [topic 747168].
  6. Local screening vs board: tied configs scored 0.17 vs 0.10 [topic 751973].

---

## 5. Leaderboard noise

- 58 tasks; score granularity 0.017; truncated display (e.g. 12/58 shows 0.20) [topic 743506].
- Identical ZIP outcomes reported: 0.18 then 0.01 [topic 750521]; 0.22/0.17/0.15 [topic 750350]; 0.17 then 0.15/0.13/0.15 [topic 748051]; 0.17 / 0.18 then 0.00 "succeeded" with an unchanged pack [topic 747519, 10-28]; 0.17 then 0.00 (58012317 vs 58049571) [topic 743683, 11-06]; byte-identical skill agent 0.15 then 0.10 [topic 750350]; three byte-identical b1 packs 0.15/0.17/0.15 [topic 748584]; 7 to 13 of 58 for identical files [topic 751596]; same-config repeats landing 0 tasks apart twice [topic 753524].
- Model of noise: ~2-3 tasks (1 sd) on 58 tasks [topic 753524]; 200+ runs: sigma 1.0 per 7-task rep (~2 on 58); about 67% of tasks "flippy", 23% never solve, 10% always solve; 35 of 38 multi-file golds never solved [topic 753524]. 19 of 123 tasks flipped between two identical Gemma passes locally [topic 747168]. 0.24 vs 0.22 is one task [topics 747168, 753524].
- The 0.00/0.01 outliers (identical to a pack that scored 0.17-0.18) look like infrastructure or server-hang events, not agent variance: suspected parser freeze [topic 750521], scorer-side failures on 10-21 and later [topic 751339 host acknowledgement], 10-27/28 and 11-06 reports [topics 747519, 743683]. Hosts have not explained 0.00 successes.
- Scorer-side failure wave 2026-10-21 onward: "Notebook Threw Exception" within ~20 min (likely model-server startup > 1200 s, 3 of 7 starts slower than limit on 10-21) [topics 747519 item 1, 751264]. HOST-CONFIRMED acknowledged as on their side [topic 751339].
- Final selection advice from posters: repeat a promising run before believing it; spend submissions on changes with a mechanism and an expected effect of several tasks; pick finals for robustness [topic 753524]; use paired local tests instead of board runs [topic 751596]; choose two diverse finals since the better private score counts [topic 752220]. Private set ~60 tasks has the same variance [topic 754295].
- Merged teams: the 25 Nov merge deadline and submission-count cap exists [topics 756607, 748584]; the question of which score a merged team keeps is open [topic 756693].

---

## 6. Ideas with a reported measurement we may not have tried

(All single-team claims; numbers are what the poster reports.)

1. **Thinking on with summaries on** is the largest local lever: thinking off 17.8% vs 37.2%; thought summaries off 27.1% vs 39.5% [topic 746250]. Thinking budget 2048 vs 4096 vs 6144: 38.8/37.2/37.2 (no gain from more) [same]. Thinking budget 4096 + include_thoughts true is already standard.
2. **Time budget curve (B40, not L4):** 6 min 37 solved, 10 min 46, 15 min 54, 60 min 51 of 129; 25 vs 50 calls: 36 vs 50 solved (-14) [topic 746250]. On Kaggle 4xL4 the safe cap is ~5.5 min/task sequential [topics 746250, 747857]. Your 28 calls at 8 min is at the edge; halving calls was costly.
3. **Edit-by-call-12 prompt gate** cut no-source-edit tasks from 38% to 11.6%, with only +4 solved of 69 [topic 749198].
4. **Candidate-listing localization**: first identifier-grep hit is the gold file 30% of tasks; grep+BM25 top-5 = 61%, top-10 = 74% (rich worst at 48% top-5, requests 92%) [topics 747980, 746250 reply]. Not scored as an agent change by anyone. Seeding from exact symbol names + neighbors gets within 2 hops of the edit site 47.9% vs 14.5% TF-IDF Hit@5 [topic 746250 reply].
5. **Single-argument editing** via `run_command` heredoc: removes argument loss (editor failures 8/75 = 11% vs 43% `edit_file`), but resolved counts stayed 6/16 [topic 747923]. A separate public entry uses a heredoc editor with 0.17-0.18 range [topic 755172].
6. **Re-reading before edits / no restating files**: 8 of 43 steps hold 56% of the budget; rules: never restate a file after reading, pass start/end lines, treat any step >60 s as a prompt bug [topic 755291, 12B, no score effect].
7. **Raw-text observation encoding** (replay of 30 edit contexts): 22% failure with double JSON, 62% with one level, 0% with raw text [topic 744272]. Host moved to one level + unescape fallback, so the raw-text gain is not available to submissions.
8. **LoRA with shorter caps** (rank 32, 4-min cap; or rank 16 at 6 min / 2048 thinking) reached 0.17 = baseline, no gain [topic 755677].
9. **Temperature 1.0 vs 0.2**: 51 vs 48 resolved on 129 (+3, noise) [topic 746250]; temperature 0 vs 1 tied [topic 755066]. 0.7 increased looping [topic 745774].
10. **Command timeout 100/150/250/300 s**: 43/44/40/47; no signal [topic 747857]. Empty system prompt: fewer tokens but more test-patch conflicts (9-11 vs 2-4), lower pass rate [topic 747857].
11. **E4B copy-bug tensor fix** (doubling `per_layer_model_proj` or a training-free r128 LoRA): copy inputs failed 15/18 unmodified vs 1/18 with the adapter [topic 753277], targeted copy tests only; LoRA on E4B at the scorer is unconfirmed [topic 752239].
12. **Tool-call count and rewarding commit**: first edit lands at ~106 s in solved runs vs ~183 s in failed ones; prompt rules to edit earlier were mostly ignored [topic 752848].
13. **Verification step**: test feedback loops raised a local rate 26% to 42% in one poster's study [topic 751104 reply]; but a test-file rerun step added ~5% median time locally and still timed out the 12 h run on the scorer [topic 752017].

---

## 7. Five most actionable items for our team

1. **Treat 0.00 to 0.05 outcomes of a known-good pack as likely infrastructure/server events, not agent regressions, and resubmit before drawing conclusions.** Evidence: byte-identical packs went 0.18 to 0.01 and 0.17 to 0.00 [topics 750521, 747519, 743683]; hosts acknowledged scorer-side failure waves [topic 751339]. Our board draws 0.13-0.20 are within the 2-3 task noise [topic 753524], so also choose the two finals for robustness (the better private score counts) [topic 752220] rather than the single highest public draw. For E4B, the 0.01/0.03 draws may be a mix of this and weak edits.

2. **Do not touch the global time budget: keep 8 min/28 calls (or 10 min with the 60 s command timeout) and do not add verification loops that run whole test files.** The scorer errors the entire submission above 12 h, with no partial credit and no rerun [topic 743063, HOST-CONFIRMED; topics 752017, 749597]. Safe cap on 4xL4 ~5.5 min/task at 120 tasks [topics 746250, 747857]. Hidden-repo test runs cost more than local runs suggest [topic 752017]. Your measured 15% session timeouts match the forum picture (timeouts 61/26/3 at 6/10/15 min locally) [topic 746250]. Command timeouts rarely bind (24/7,424 > 120 s) [topic 755066], so your 60 s timeout is safe.

3. **Fix `edit_file` argument loss with a prompt-level delimiter instruction and a single-string-argument fallback (heredoc via `run_command`), and measure it on E4B first.** Mechanism: model closes a string with a backtick instead of `<|"|>`, so the parser shifts delimiters and drops `old_string` [topics 747519, 756051, 747923, 746336]. Rejected calls cost time but not call count [topic 747168]; resends loop up to 43 times [same]. The competitor fix is a one-line prompt edit, claimed 93% vs 11% failure [topic 756607], but their LB was lower, and `robust-edit` did not raise resolved counts [topic 747923]. Expect saved turns, not guaranteed score; the benefit should be largest for E4B where verbatim repeats are 3/4 of failed edits [topic 756433]. Specific wording to try: tell the model that every string in a tool call is written between `<|"|>` delimiters and never closed with a backtick (do not say "don't"; a positive instruction is more reliable [topic 746502]).

4. **Reduce wasted calls from tooling the harness misleads about.** (a) Tell the agent not to call `search_similar_code`/`get_code_neighbors`/`get_code_subgraph`: 140/142 calls returned nothing [topics 745028 reply, 745220] and 21/129 tasks wasted calls on them [topic 746250]. Do not rely on omitting the tools from agent.yaml alone: an undeclared tool call ends the task with an empty patch and no fix was confirmed [topic 745028]. Decide per your current YAML. (b) Start with `git ls-files | grep` or `find` for the package, because the prompt's workspace tree omits the source package in 115/129 public tasks [topic 745220]. (c) Cap read output (read_file caps at 150 lines; `search_similar_code` can blow the 32k window) [topics 755291, 744577]. (d) Write brief findings as text before each tool call, since compaction drops tool calls and results but keeps text [topics 754783, 747186].

5. **For E4B, drop `edit_file` as the main edit path and keep thinking on; do not spend a slot on LoRA.** Evidence: E2B/E4B edit loops [topic 756433], E4B wrong-file edits 13/31 [topic 750974], include_thoughts:false no longer disables thinking since 0.2.13 so check your `thinking_budget` is explicit (0 to disable) [topic 747914], routers and extra agents hurt due to shared clock and compaction resets [topics 754636, 747519]. No LoRA gain is reported by anyone, and LoRA adds 15-29% time and unconfirmed small-variant support [topics 751596, 755677, 752239]. Your practice-set gains are a poor predictor (only ~68/129 public tasks are valid locally, inverse CV/LB correlations) [topics 756400, 744319, 751973]. If you want a cheap E4B experiment with a published number, test the copy-bug repair only if you accept the LoRA risk [topic 753277].

### Open items the forum does not answer
- Whether a per-task time cap or the 12 h global is enforced on the agent side beyond the four fields (the hosts say the four fields are honored for the agent phase [topic 748428]; "hard cut" semantics for `timeout_seconds` are unanswered).
- Whether the scorer container is Docker or subprocess; python 3.12 vs 3.13.
- Whether the compaction threshold is 14,336 for sure (best evidence: Getting Started notebook plus a reply in [topic 748584]).
- Whether the vLLM array-argument freeze will be guarded [topic 753973].
- How the 0.29 team got there.
