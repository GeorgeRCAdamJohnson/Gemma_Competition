# Task-Router LoRA — spec (2026-10-15)

Origin: user direction — *"the leader is going to have trained a model that can evaluate each task,
decide the best path for each task, then uses the ML engine to guide every tool call."*

Status: SPEC. Nothing built, nothing trained, no GPU spent, no scored slot spent.

---

## 0. Why this is the right target (and why it is not the commitment LoRA)

**The declarative surface cannot express per-task routing.** Verified from HARNESS_README:
- `tools` and `system_instruction` inside `generate_content_config` are excluded by schema design and
  raise a validation error if set (L154). An agent cannot rewrite its own tool surface at runtime.
- `eval_config.yaml` budgets (`max_tool_calls`, `max_time_minutes`, `max_turns`, `timeout_seconds`) are a
  single global block for the whole submission — not per-task, not per-agent, not runtime-editable (L98).
- Sub-agents are refuted twice (dmitrii sweep; our v8 regression) on the shared-budget-pool and
  never-compact-overflow failure modes.

So YAML can express a STATIC branch (what the 0.12 branching submission did via `{problem_description}`
templating) but never a LEARNED one. **The weights are the only legal channel for a per-task controller.**

**Measured evidence pointing here:**
- 12B oracle-context test: outcomes are TASK-determined, not sampling-determined — the same five tasks
  resolved at temp 0.2 and at temp 1.0/top_k 64 (5/12 vs 14/36, same five). The task picks the outcome;
  the policy executes.
- rich_3944 edited the WRONG FILE because the issue contained the word "font" — a routing failure.
- WRONG-FIX is 34/56 of traced rich rows: well-formed edits on the right file with wrong content, which is
  what a badly-chosen path produces.
- The static branching prompt scored 0.12 (within noise of 0.15). Same hypothesis, crude execution.

**Why this survives the data ceiling that killed the commitment LoRA:**
Routing is a far lower-entropy target than fix synthesis. There are roughly 5-10 distinct paths; there are
129 distinct fixes. A router trained on 129 examples can plausibly generalize. A fix-memorizer trained on
the same 129 cannot — it is trying to learn 129 separate answers.

**The mechanism for "guide every tool call" demonstrably exists.** The v2 adapter (410 modules, all 60
layers) changed tool-call behavior catastrophically: 81-100% malformed `edit_file` calls on the adapter
runs. So a LoRA reaches into the tool-call policy. The open question is whether it can be trained to GUIDE
rather than CORRUPT — a data-shape problem, which is the one thing already diagnosed.

---

## 1. Path labels + headroom (NO GPU, ~hours)

**1a. Derive ground-truth paths from gold, for all 129 public tasks.**

Inputs we already have: `comp_files/tasks.jsonl` (instance_id, repo, base_commit, patch, test_patch,
problem_statement, hints_text) and `local_eval/repos/<repo>` clones.

Per task, compute:
- `target_files` — files touched by the gold patch (test files excluded; the harness resets them)
- `target_symbol` — nearest enclosing `def`/`class` of the first gold hunk
- `n_edits` — gold hunk count
- `n_files` — distinct source files in the gold patch
- `test_nodes` — `def test_*` added by `test_patch` (the exact rule swegemma uses:
  `_extract_test_functions_from_patch`, added-defs first, then hunk-header/context fallback)
- `target_named_in_issue` — does the problem statement name the target symbol or file? (This is the
  CASE A / CASE B distinction the branching prompt used.)
- `repo`, `symptom_class` (coarse: render/parse/contract/io/config)

Anti-leak rule: labels are derived from GOLD, which is fine for building a router (the router never sees
gold at inference — it sees only the issue). Record per-task provenance so this is auditable.

**1b. Measure router headroom against our existing traces (the free falsifier).**

Against the 149 traced rich rows in `kb/runs.jsonl` + trace files, classify each failure:
- `path_wrong` — the model edited a file/symbol gold never touches (a router could have helped)
- `path_right_content_wrong` — right file, wrong content (a router CANNOT help; this is synthesis)
- `never_committed` — no edit attempt (a router could have helped by forcing commit-fast)
- `unreachable` — gold path needs more calls than the budget allowed (a router cannot help)

**Pre-registered bar:** if `path_right_content_wrong` dominates, the router is aiming at the wrong class
and we stop before spending GPU. This is the cheapest possible falsifier and it uses only files on disk.

Output: `train/data/router_labels.json` + a headroom report.

---

## 2. Router training set + train (GPU, small)

**2a. Build (issue -> path) trajectories.**

Format matches `train_lora.py`'s `messages` schema (chat-templated, loss masked to assistant turns).
System prompt = the SHIPPED prompt (candidate D, sha256 de1dbc39103a0970) so train/serve match.

Assistant turn emits a terse structured verdict, then the agent proceeds:
```
TARGET: <file> :: <symbol>
EDITS: <n>
TESTS: <node>, <node>
```
then the real tool calls (grep -> read -> edit -> submit), grounded to real bytes at base_commit exactly
as `build_rich_sft_data.py` already does.

**Capacity discipline (from the measured overfit diagnosis):**
- q/v only or all-linear, **r=8-16**, `alpha/r <= 1`, **1 epoch**
- capacity matched to ~129 examples — NOT 410 modules
- early-stop on a BEHAVIORAL metric (path-match on holdout), never on loss. Loss 0.30 was the overfit
  signal nobody acted on last time.
- `--maxlen >= 8192` (all 45 existing trajectories exceed the 768 default and would truncate the edits)

**2b. By-task holdout.** Split the 129 tasks so that no task appears in both train and holdout. The
holdout is the only number that counts.

---

## 3. Router validation (GPU, light)

Three metrics, in order:
1. **Path-match on holdout** — does the predicted `TARGET`/`EDITS`/`TESTS` match gold? This is cheap: it
   needs one generation per task, not a full agent run.
2. **Beat the trivial baseline** — "always predict the most common path" and "always predict the
   single-file, target-named path". A router that does not beat these is not routing.
3. **No serialization regression** — zero malformed `edit_file` calls and zero argument-collapse in the
   traces. This is the failure that killed every prior adapter.

**Pre-registered bar:** path-match on holdout must beat the trivial baseline by a clear margin AND
serialization must be clean. Otherwise stop.

---

## 4. Integration gate (GPU, full)

Router LoRA + the existing agent, on the **faithful scorer** (swegemma 0.2.11 + `SubprocessManager`,
semantics now known exactly), over a LARGE task set — not 6.

Paired baseline/change, floor-guaranteed on the 6 rich tasks we have ever resolved (rich_3278, 3471,
3676, 3882, 4077, 4079 — base resolves them, so any adapter that drops them is caught immediately).

**Bar:** resolve >= baseline on the floor set AND >= baseline on the hard set (4076, 4079, 3469), with
zero serialization regression.

**Falsifier:** if a correctly-shaped, correctly-targeted router still degrades patch generation, the
LoRA path is dead and we stop spending on it.

---

## Risks, stated honestly

| risk | severity | mitigation |
|---|---|---|
| Generalization: 129 public tasks, hidden board | HIGH | by-task holdout; route on SHAPE never identity |
| Forbidden bake: recognize task -> emit answer | DISQUALIFYING | train on structure only; metadata stripped at inference; holdout shares no tasks |
| Router aims at the wrong failure class | MEDIUM | Step 1b headroom gate, free, before any GPU |
| Serialization corruption (killed 3 prior adapters) | HIGH | clean-serialization bar in Step 3; capacity matched to data |
| Overbake (killed v2) | HIGH | r<=16, alpha/r<=1, 1 epoch, behavioral early-stop |
| GPU quota: 30 GPU-hrs/week | MEDIUM | Steps 1 is CPU-only; test TP=1 on 1xL4 (31B w4a16 ~16GB in 24GB) before 4xL4 |

## What is NOT in scope

- No autonomous self-tuning loop. Arms are run and scored; a human decides what changes. The
  one-change-per-test discipline is what caught the inverted-alpha error, the circular catchability
  signals, and the 3/4-vs-2/4 miscount this session. A loop that tunes itself would have shipped all three.
- No scored submission until a gate beats baseline on the faithful scorer.
- v6w @ 0.15 remains live-best and is never overwritten without a verified beat.
