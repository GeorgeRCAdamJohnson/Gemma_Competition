# The Missing Connections — a read-only audit of what the log has, and what it never joined up

Audit date: 2026-10-11. Sources: `GEMMA_EXPERIMENT_LOG.md` (6,976 lines), `comp_files/HARNESS_README.md`,
`comp_files/system.md` + `agent.yaml` (the **official starter baseline**, shipped with the competition),
`refs/{verra,honghanh,lavinwins,dmitrii}` (4 public LB kernels), and the v6b live traces.

**Scope discipline:** the reference kernels are read for INSIGHT ONLY — no code, prompt text, or config is
copied. Where a lever is named below, it is a mechanism we can adopt and re-derive ourselves, and each one
is stated so it can be verified against our own harness docs rather than trusted.

---

## 0. THE ONE-LINE ANSWER

We have had the answer for the entire project and mis-filed it. Three separate findings, logged in three
different places, all say the same thing — and the log's standing-truth block never merged them:

> **The problem is not that the model won't commit. It's that we never told it a patch that was never
> submitted still counts — and we spent 22 versions optimizing the one step that was never the bottleneck.**

The log's standing-truth bullet #1 says "THE WALL IS COMMITMENT, not localization." That is right about the
*symptom* and wrong about the *cause*. Below are the five joins that were never made.

---

## 1. THE JOIN THAT MATTERS MOST: submit_patch is OPTIONAL — the working tree is graded

**Where we already knew it, but never used it:**
- `HARNESS_README.md` §8.1 "Automatic Unsubmitted Patch Recovery": if an agent exhausts tool_calls/turns
  or times out **without ever calling `submit_patch()`**, the harness still runs `git add -N . &&
  git diff --binary _swegemma_baseline` and records `agent_patch` for Phase-2 scoring.
- Both 0.18 reference prompts state it to the model in plain language: *"When either runs out, the working
  tree is graded as it is, so an edit made in time counts even if you never reach `submit_patch`."*

**Why this is the missing join:** our own prompt has spent the entire project treating `submit_patch` as the
goal and "never submitted" as the failure. The v6b `system.md` says *"The moment you have ANY applying patch,
call submit_patch"* and *"NEVER call submit_patch twice"* — and the traces show the model burning its last
turns reasoning about whether to submit rather than making the edit that would have scored anyway.

**The evidence we're misreading.** v6b's three nulls all reported `patch_chars=0`. That number is *not*
proof the model failed to commit — it's proof **the working tree was clean**, i.e. no edit was ever written.
The two failure modes we have been conflating for 20 versions:

| what the log calls it | what it actually is |
|---|---|
| "search-death / never committed" | no edit was ever written to the tree |
| "never reached submit_patch" | **irrelevant** — the harness recovers the diff anyway |

So the bar we have been optimizing against — "reach submit_patch" — is the wrong bar. The right bar is
**"a source file must be modified before the wall."** Every one of our prompts states the wrong objective.

**This also explains the v10 retraction** (line ~4757): both local "wins" were at 277–288s and died at
302–305s in the committed run. We attributed that to environment latency. But if the diff is auto-recovered,
then a task that was *edited* and then timed out would still have scored — so the real question is whether
those two runs had edits on disk at all. The `patch_chars=0` in the committed run says they did not. The
latency story may be a red herring sitting on top of a never-committed edit.

**Action:** change the stated objective in the prompt from "submit the patch" to "modify a source file
before the wall; submission is a formality the harness handles." Pre-register a gate that measures
`patch_chars` at wall-time, not at submit-time.

---

## 2. THE JOIN ABOUT TOOLS: we REMOVED two tools the 0.18 recipe KEEPS, and the reason we gave was one bad trace

**The facts, side by side:**

| | tools shipped |
|---|---|
| starter baseline (`comp_files/agent.yaml`) | all 9, **incl. `edit_file` + `write_file`** |
| honghanh (0.18) | 6 — explicitly FORBIDS the 3 graph tools, **keeps `edit_file`/`write_file`** |
| lavinwins | all 9 |
| verra (0.18) | all 9 |
| **our v6b / v6c** | 7 — **`edit_file` + `write_file` removed** |

Every scoring kernel keeps `edit_file`. We cut it.

**The log's justification** (v6b header): *"live v6 trace rich_4070 proved edit_file death-spirals at thinking
4096 (empty old_string, ~8 wasted calls, timeout w/ unsubmitted patch)"* → drop it, route edits through
`run_command` python-replace.

**Why that's a one-trace over-correction:** the project has an explicit rule about this — logged at line
~2395, *"diagnose a gate from ALL its traces, not one grep"* — and `HARNESS_README` §10.1 names the *actual*
cause of exactly that symptom: *"When an LLM generates a massive thought block followed by a large
`edit_file` tool call that hits `max_output_tokens`, the `<|tool_call>` tag gets cut off before closing."*
The documented remedy is **`thinking_budget` 4096 + reasonable `max_output_tokens` + incremental edits** —
i.e. keep the tool, fix the truncation. We instead removed the tool and inherited a worse problem: a
`run_command` heredoc that must be byte-exact, needs quoting discipline, and is a *second* thing to get
right. v21's trace read already found run_command edits landing only on short-anchor adds.

**Cost accounting:** removing `edit_file` bought us the freedom to stop worrying about `<|tool_call>`
truncation, but we paid for it with a strictly harder edit mechanism — and we did it on ONE task's trace,
while four independent kernels kept the tool and scored higher than us.

---

## 3. THE JOIN ABOUT LOCALIZATION: we called the graph tools "the strongest lever we've found" — they are the three tools our best competitors DELETE

This is the sharpest contradiction in the log, and it sits in plain sight.

**Line ~4721 (v10 forensics) — "THE SMOKING GUN ... WHY THIS IS THE STRONGEST LEVER WE'VE FOUND":**
```
search_similar_code: 0 | get_code_neighbors: 0 | get_code_subgraph: 0 | grep: 121 | read_file: 108
```
The reasoning: the harness built semantic+graph retrieval *precisely* for signal-poor localization (our exact
problem — rich problem statements are 2-word PR titles), the model never calls them, so we should prompt
harder. Pre-registered a gate to make the model use them first.

**Both 0.18 reference prompts say the opposite, and they went further than "don't bother":**
- The starter baseline says: *"use `search_similar_code` with keywords from the error message."*
- Every 0.18 kernel **replaced that line with a prohibition**: *"Do not use `search_similar_code`,
  `get_code_neighbors` or `get_code_subgraph`: they only accept exact fully-qualified ids and usually
  return nothing."*
- honghanh went further — it hard-codes them out of the archive and **fails its own build** if they appear:
  ```python
  FORBIDDEN_TOOLS = ["get_code_neighbors", "search_similar_code", "get_code_subgraph"]
  for tool in FORBIDDEN_TOOLS:
      if tool in agent: raise SystemExit(f"Graph tool still registered: {tool}")
  ```

**The reframe that connects the two halves:** our "0 calls" observation and their "returns nothing" claim
are the **same measurement**. The tools return nothing *because* they demand exact fully-qualified ids and our
problem statements are vague — so the model tries, gets nothing, and falls back to grep. We read the 0 calls
as "unused potential"; they read it as "dead weight." **Both are right, and the correct action is opposite
to ours: stop prompting for them, and consider removing them.**

Our own log contains the confirming data at line ~3511: *"33% text >> ~0% usable from the graph tools."* We
had that number. We then promoted the tools to "strongest lever" anyway.

**Action:** test removing the three graph tools (honghanh's exact move) rather than pushing the model to use
them. Also note the starter prompt's advice is actively misleading for rich's vague titles — a second reason
to run our own prompt, not the stock one.

---

## 4. THE JOIN ABOUT THE PROMPT ITSELF: we never ran the stock baseline, and 0.18 = stock + ONE section

The competition ships an official starter at `comp_files/system.md` + `agent.yaml`. I diffed it against the
0.18 winner's prompt. **The entire delta is 2 hunks, ~800 chars:**

```diff
- use `search_similar_code` with keywords ... rather than running `find` or `grep`
+ search for its most specific identifier or error string with `git grep -n "text" -- '*.py' | head -20`
+ Do not use `search_similar_code`, `get_code_neighbors` or `get_code_subgraph`: ... usually return nothing.

+ ## Budget: 28 tool calls, 8 minutes
+ - When either runs out, the working tree is graded as it is, so an edit made in time counts even if you
+   never reach `submit_patch`.
+ - Use at most about 10 tool calls to find and read the code.
+ - By your 12th tool call you must have edited a source file. If it has not, stop exploring and make your
+   best-guess edit in the most likely place now. Runs that are still only reading after 12 calls almost
+   never succeed; more reading does not help.
+ - After your edit: one check, one correction, then submit. Do not start new exploration after call 20.
```

**What this means:**

1. **0.18 is not a clever method. It is the stock prompt plus a budget section and a tool deletion.** We spent
   22 versions inventing a "sibling-conform" method, and scored *below* "stock + budget paragraph."
2. **We have never measured the stock baseline as a control.** Grepping the log for `starter`/`baseline
   prompt`/`control run` returns one unrelated hit. Every v1–v22 number is measured against *our own* prior
   version, never against the thing everyone else is shipping. **We do not know whether our prompt is better
   than the default.** That is the single biggest hole in the whole experiment series.
3. **Their commit rule is absolute and checkable; ours is relative and vague.** "By your 12th tool call you
   must have edited" is a hard, self-auditable trigger. Ours says "MAX 3-4 locate calls" — advisory, no
   number the model can check itself against, and (per §1) no mention of the oracle that would let it check.
4. **They tell the model the failure statistic.** "Runs that are still only reading after 12 calls almost
   never succeed; more reading does not help." That is a *measured* claim about its own failure mode, stated
   as motivation. Our prompts assert rules without ever telling the model why the rule exists.

**On respecting the boundary:** we are not copying this prompt. We are taking the *insight* — "the 0.18 gap
is a budget-discipline paragraph and a tool deletion, not an architecture" — and the testable claim it
implies. The experiment to run is **our own** prompt in the same shape as a control, not their text.

---

## 5. THE JOIN ABOUT WHAT WE HAVE NEVER MEASURED

- **No stock-baseline control** (§4). Unknown whether our prompt beats the default at all.
- **n is tiny everywhere.** Every conclusion rests on 3–6 rich tasks, and those same tasks have been reused
  for ~20 versions. They are no longer a held-out set — they are a training set we keep re-scoring. The one
  task we call our anchor (rich_4077) has been looked at so many times that "it resolves" may be partly
  "we have accidentally tuned to it."
- **Resolution is deterministic per CSV, but our free gates have not been re-run to confirm stability.**
  v10 already produced one retraction (2/10 → 0/10) from environment latency alone. Any single-task gate
  result should be treated as needing a re-run before it means anything.

---

## 6. WHAT THIS ADDS UP TO

The log is not missing data. It is missing **joins** — five claims that each sit in a different section,
each individually well-evidenced, and each pointing at the same conclusion:

| # | The join | Where the halves already are |
|---|---|---|
| 1 | submit_patch is optional; the graded artifact is the **edit** | `HARNESS_README` §8.1 + our prompt's "never submitted" framing |
| 2 | `edit_file` should stay; the documented fix is truncation control, not tool removal | `HARNESS_README` §10.1 vs our one-trace removal |
| 3 | graph tools return nothing → **remove** them, don't promote them | line ~4721 ("strongest lever") vs ~3511 ("~0% usable") + 0.18 prohibition |
| 4 | 0.18 = **stock prompt + budget section**; we never ran stock as a control | `comp_files/system.md` vs our 22-version custom method |
| 5 | our gate set is **no longer held-out** | every version re-scores the same 5–6 rich tasks |

**The one thing I would do first is not a new agent at all:** run the **stock starter prompt** on our rich
gate, unmodified. It costs one free run, it is the control every one of our numbers is missing, and if it
lands near 0.18 it reorders the entire strategy — because it would mean the answer was never our method, it
was always the budget rule and the tool list, and every version we built on top of the defaults was
subtracting from it.

---

### Appendix — evidence index

| claim | source |
|---|---|
| auto-recovery of unsubmitted patches | `comp_files/HARNESS_README.md` §8.1 (agent_runner.py 760–795) |
| `<\|tool_call>` truncation is the real `edit_file` failure | `HARNESS_README.md` §10.1 |
| 0.18 ships all 9 tools | `refs/verra`, `refs/lavinwins` agent.yaml |
| 0.18 ships 6 tools, graph tools hard-banned | `refs/honghanh` cell 7 (`FORBIDDEN_TOOLS` + `raise SystemExit`) |
| stock baseline ships all 9 + a sub-agent | `comp_files/agent.yaml` |
| stock→0.18 delta is 2 hunks | diff of `comp_files/system.md` vs `refs/verra` system.md |
| graph tools called 0 times | log line ~4721 (v10 forensics) |
| graph tools "~0% usable", text 33% | log line ~3511 |
| v6b `patch_chars=0` on all 3 nulls | `submit_v6b/out_v6b/*.log` SUMMARY |
| models state "0 tool calls, cannot edit" | `trace_rich_4079.json` step 31, `trace_rich_4070.json` steps 31–33 |
| no stock-baseline control anywhere in log | grep `starter|baseline prompt|stock prompt|control run` → 1 unrelated hit |

Read-only audit. No experiment code, prompt, or competition artifact was modified.

---

# RETRACTION & CORRECTION (same day) ? verified line-by-line against the log

The user asked whether these five claims had actually been validated against `GEMMA_EXPERIMENT_LOG.md`, and
whether our own experiments already covered them. I re-read the log against each claim. **Three of the five
are refuted by our own prior entries.** The audit above overstated how much was missing. Corrected record:

| # | claim as written | VERDICT | what the log already says |
|---|---|---|---|
| 1 | "submit_patch is optional ? nobody told us" | **REFUTED (known since ~line 4611)** | Already stated verbatim twice: *"if the agent exhausts tool_calls/turns OR TIMES OUT WITHOUT calling submit_patch, the harness AUTO-RUNS `git add -N . && git diff`"* and *"A TIMEOUT DOES NOT AUTOMATICALLY SCORE 0."* Plus the correct reframe: *"chars=0 after timeout = the agent NEVER EDITED THE TREE AT ALL (not 'edited but forgot to submit')."* This was known, stated correctly, and then **not carried into the prompts.** |
| 2 | "we cut a tool the 0.18 recipe keeps" | **PARTIALLY REFUTED** | v19 **already re-enabled `edit_file`** using exactly the ?10.1 mechanism, with the reasoning written down. The removal happened later, in v6b, on one trace. So the finding is not "nobody read ?10.1" ? it's "we solved it at v19, then re-broke it at v6b." |
| 3 | "graph tools are our strongest lever; competitors delete them" | **REFUTED as new** | Already measured and already acted on: *"33% text >> ~0% usable from the graph tools (search_similar_code free-text returns [])"* and the v7 lever was explicitly *"STOP sending the agent to the dead search_similar_code."* |
| 4 | "we never ran the stock baseline as a control" | **SURVIVES** | Exhaustive regex over the log: no stock/baseline-prompt/control-arm run exists. Still a real gap. |
| 5 | "the gate is no longer held-out" | **PARTIALLY SURVIVES** | The log already runs pre-registered held-out splits and already retracted a contaminated v9 result. What is true is narrower: the *5-task rich dev gate* specifically has been reused ~20 versions. |

## The finding that replaces the first three

The knowledge was there. **The propagation was not.** Three concrete, dated instances:

1. **Line 4611 / 5082** ? auto-recovery correctly identified. **Line 6797** then reports *"Submit-fast prompt
   worked"* as a *success*, and the v6b pre-registration (line 6744) makes *"NO task times out unsubmitted"* a
   PASS BAR. **A fact that was known to be irrelevant became a scoring criterion.**
2. **Line 5588?5590** ? the free `get_status` reserve-tail is designed in detail: *"call get_status after each
   tool call; the moment tool_calls_remaining <= 3, STOP searching and apply your edit NOW ... NEVER TRIED in
   v1-v18."* It shipped in v19 (line 5627) and **worked**: line 5724 records *"get_status reserve-tail +
   edit-SHAPE KILLED search-death: every task now REACHES an edit (first_edit_at not None; v18 had 4/5 never
   editing). CONFIRMED working."**
3. And then **v6c re-proposes that same lever today**, citing the same traces, as if it were new.

**So the single most important correction is to myself, not to the log: the v6c "budget oracle" is v19's
lever #4, already measured as CONFIRMED WORKING.** v19's attribution proves the oracle reaches an edit on
every task. What v19 then found is the *next* wall ? the edit lands but the anchor fails to apply
(`edit_fail`), because the model edits at call 17/18 with no budget to recover.

**Therefore v6c, as currently written, is a re-run of a measured-working lever and is unlikely to move the
score by itself.** Its only genuinely new element is the commit-by-remaining *thresholds* (<=14/<=7/<=3) and
bank-as-you-go. I flagged the bank-as-you-go idea as new in the log; the log at line 5616-5620 shows the
edit-SHAPE and first_edit_at problem was already named, so that too is partly a re-run.

**Honest correction to the v6c pre-registration:** it should have been filed as *"v19's oracle lever,
re-tested at the 0.18 budget with revised thresholds"* rather than presented as a novel diagnosis. The
pre-registered bar still stands, but the prior probability of a flip should be read as *"this lever worked
before; does it still work when reads are cheaper at 28 calls?"* ? not as a first attempt.

## What actually survives as actionable

Only **two** items, and both are small:

- **#4 (no stock-baseline control):** still unrun and still cheap. The competition ships
  `comp_files/system.md`; running it unmodified costs one free gate and gives every v1?v22 number the
  reference point it lacks. **This is the only genuinely new experiment the audit produced.**
- **#5 (dev-gate reuse):** the 5-task rich set has gated ~20 versions. Any next gate should add *fresh* RICH
  tasks never used before, so the result has some held-out power.

And one **process** finding, which is arguably worth more than either:

> The log is disciplined about *recording* findings and weak about *carrying them forward*. At least three
> times a correct, measured conclusion sat in the log and a later version re-derived it as new ? or inverted
> it into a pass-bar. The failure mode is not missing information. It is that each new session reads the
> recent entries and the standing-truth block, and the standing-truth block was never updated to carry
> forward the auto-recovery fact or the v19 oracle confirmation.

**Recommended process fix (cheap, no GPU):** the standing-truth block at the top of the log has six bullets
and predates most of these findings. Adding "submit_patch is optional (auto-recovery, L4611)", "the free
get_status oracle is CONFIRMED WORKING (v19, L5724)", and "do not re-propose either as new" would have
prevented both this audit's first three claims and the v6c re-run.
