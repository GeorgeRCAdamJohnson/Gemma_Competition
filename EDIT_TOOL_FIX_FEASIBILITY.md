# EDIT_TOOL_FIX_FEASIBILITY — zero-GPU edit-interface fix feasibility

Read-only investigation. No code changed, nothing run in the sandbox, nothing submitted.
Scope: given the confirmed root cause (gemma-4-31b cannot serialize an `edit_file(old_string=<big multiline>, new_string=...)` call), determine the concrete zero-GPU fix and whether we control it.

Legend: **[MEASURED]** = read directly from a config, harness doc, or trace. **[INFERENCE]** = reasoned from measured facts.

---

## SUMMARY ANSWER (bottom line first)

**Yes — there is a zero-GPU, in-our-control fix, and it does not require us to change the tool.**

1. **Who controls `edit_file`:** The harness. `edit_file` and all 8 sibling tools are defined inside the `swegemma` / `adk-eval-core` packages and resolved against a *closed* `ToolRegistry`; the submission is declarative-YAML-only and the compiler never imports competitor Python (`importlib` is never used). We **cannot** change the tool's signature, matcher, or add a new tool. **[MEASURED]**
2. **What we DO control:** the **system prompt** (`prompts/system.md`), the **sampling config**, the **eval budgets**, and critically the **`tools:` list** in `agent.yaml` — we choose *which* of the 9 harness tools the agent is allowed to call. **[MEASURED]**
3. **The safe shapes that avoid a big multiline tool argument exist in the harness today:** `run_command` (shell: `sed`/python heredoc) and `write_file` (whole-file content). `run_command` is the one shape measured to actually land multi-line edits where `edit_file` loops. **[MEASURED]**
4. **The single most promising fix to try first:** **remove `edit_file` from the `tools:` list entirely** (not just tell the prompt to avoid it) AND attack the *other* wall this investigation surfaced — the `read_file(start_line,end_line)` pagination failure that burns the budget before the edit is ever reached. v18 tried the run_command route but left `edit_file` in the tool list and did not touch the read/search wall, which is why it scored 1/5. **[MEASURED + INFERENCE]**

**Important honest-null / correction to the brief:** the brief states the serialization bug is *the* wall and v18 "did not stick." The traces show **two independent walls**, and the serialization bug is only the *second* one. In the run the user pointed at (`Gemma/Outputs/v19_Lora_v3`), rich_4079 spent its first ~10 calls fighting a **`read_file` pagination bug** (every `start_line/end_line` request returned the top of the file), fell back to `sed` to read, and only reached `edit_file` near the end — *then* hit the serialization loop and died at 25/30 calls with the clock also at 7.9/8 min. A fix that removes the serialization wall but ignores the read/search wall will not resolve these tasks. **[MEASURED]**

---

## 1. WHO CONTROLS `edit_file` — HARNESS-FIXED, NOT OURS

**[MEASURED] The tools are harness-defined and the submission cannot author or override them.**

- `Gemma/comp_files/HARNESS_README.md` §1: `adk-submission` "compiles untrusted submission directories ... into live Google ADK `BaseAgent` trees (`compile_submission`) **without executing arbitrary competitor Python code (`importlib` is never used)**."
- §2.1 Declarative-Only Security Model: "Competitors **do not** submit Python code entrypoints ... All agents, sub-agents, workflows, tools, and generation parameters are declared in YAML and resolved against **closed host registries (`ToolRegistry`, `ModelRegistry`, ...)**."
- §6: "`SwegemmaContext.create_tools()` registers **9 tools** in `ToolRegistry`. Your `agent.yaml` ... can attach any **subset** of these tools **by name**." The tool bodies live in `swegemma/tools/execution.py`, `swegemma/tools/workspace.py`, `swegemma/tools/graph.py`, and the 3-tier matcher is `adk-eval-core`'s `apply_replacement`.
- Local confirmation: a repo-wide search found **no vendored `swegemma`/`adk` tool source** (`def edit_file` returns zero matches; no `workspace.py`/`execution.py` under any `swegemma`/`adk` path). The packages are installed from the wheelhouse at runtime on Kaggle, not shipped in our submission dir.

**[INFERENCE] Consequences for the fix space:**
- We **cannot** change the `old_string`/`new_string` signature, add a line-range parameter, add a new "apply-diff" tool, or re-parse the model's malformed call host-side. Those would require editing harness code, which is not part of our submission.
- Candidate "(b) accept the model's observed malformed shape and re-parse it host-side" from the root-cause note is **IMPOSSIBLE** — that code is the harness's, not ours.
- What *is* ours is purely declarative: the `tools:` whitelist, the prompt, sampling, budgets.

**[MEASURED] What our submission actually ships** (`Gemma/submit_v19_lora_v2/notebook_src.py`, the inline `agent.yaml` writer):
```yaml
name: sibling_conform_agent
model: gemma-4-31b-it-qat-w4a16-ct
adapter: main_lora
instruction: !include prompts/system.md
tools:
  - run_command
  - read_file
  - edit_file        # <-- harness-defined; we only choose to EXPOSE it
  - write_file
  - get_status
  - submit_patch
  - get_code_neighbors
  - search_similar_code
  - get_code_subgraph
generate_content_config: !include configs/sampling.yaml
```
The `tools:` list is authored by us. Removing a line here removes that tool from the agent — this is the lever we control.

---

## 2. FULL LIST OF EDIT SHAPES THE HARNESS SUPPORTS — SAFE vs UNSAFE

"Safe" = does NOT require the model to place a large multi-line code string into a structured tool-call argument (the thing gemma-4 cannot serialize). All facts from HARNESS_README §6. **[MEASURED]**

| # | Shape | Harness tool & signature | Puts big multi-line string in a tool ARG? | Verdict |
|---|-------|--------------------------|-------------------------------------------|---------|
| A | **old/new replace** | `edit_file(filepath, old_string, new_string, allow_multiple=False)` | YES — two large string args; this is the exact failing call | **UNSAFE** |
| B | **shell edit (sed)** | `run_command("sed -i 's/OLD/NEW/' f.py")` | NO — one `command` string; no structured multi-line arg | **SAFE** (single-line / regex edits) |
| C | **shell edit (python heredoc replace)** | `run_command("python3 - <<'EOF' ... p.write_text(s.replace(old,new,1)) ... EOF")` | NO — the whole program incl. multi-line `old`/`new` rides inside ONE `command` string | **SAFE** (this is the one measured to land multi-line edits) |
| D | **whole-file write** | `write_file(filepath, content)` | PARTIAL — `content` is a structured arg; a whole file is huge/multi-line | **UNSAFE for large files** (same serialization risk as `old_string`); only safe for tiny/new files, and it overwrites the WHOLE file (risk of clobbering unrelated code) |
| E | **append/insert** | no dedicated tool | — | Not a distinct harness tool; must be done via C (`run_command` python/`cat >>`) → inherits C's SAFE status |
| F | **apply-a-diff / patch** | no tool exposes this to the agent | — | **Not available to the agent.** The harness applies the *final* `agent_patch` via `git apply` in Phase 2, but there is no in-loop "apply this diff" tool the model can call |
| G | **line-range / line-number replace** | **does not exist** | — | **Not available.** `edit_file` has no line-range mode; `read_file` has `start_line/end_line` but there is no `edit_by_line` tool. (Candidate "(a) line-range replace" from the root-cause note is IMPOSSIBLE — the harness has no such tool.) |

**Key matcher nuance on `edit_file` (shape A), relevant even though A is UNSAFE for big spans [MEASURED]:**
`edit_file` uses `adk-eval-core`'s `apply_replacement` 3-tier matcher — tier1 `exact`, tier2 `flexible` (strips per-line leading/trailing whitespace, auto-re-indents), tier3 `regex` (tokenizes around `()[]{}:<>=` and joins with `\s*`). The README documents three tiers, but the live success trace shows a **fourth strategy name**: rich_4077's landed edit reports `'strategy': 'unescaped'` (`Gemma/Outputs/v19_Lora_v3`, t=49.9s). **[MEASURED]** This means the matcher is forgiving about whitespace/escaping — so when `edit_file` works it works on a *short* `old_string`. The failure is NOT the matcher rejecting the anchor; it is that the call **never arrives with `old_string` populated at all** ("mandatory input parameters are not present: old_string"). I.e. the break is at tool-call *serialization*, upstream of the matcher. **[INFERENCE from measured trace]**

**Only two shapes are both available-to-the-agent AND serialization-safe: B and C (both `run_command`).** `write_file` (D) is available but re-introduces the same big-structured-arg risk for anything but a trivial file.

---

## 3. DO WE CONTROL THE SYSTEM PROMPT AND THE EXPOSED TOOL LIST? — YES, BOTH

**[MEASURED]** Both are authored inline by our notebook and written into the submission dir:

- **System prompt** — `Gemma/submit_v19_lora_v2/notebook_src.py` writes `AGENT_DIR/prompts/system.md` and references it from `agent.yaml` via `instruction: !include prompts/system.md`. HARNESS_README §2.2 confirms `.md` files load as the raw instruction string, and §5.1 confirms the harness interpolates `{problem_description}`/`{hints}` into it. We write every word of this file.
- **Exposed tool list** — the `tools:` block in the inline `agent.yaml` (quoted in §1 above) is ours. §6 confirms we attach "any subset" by name. We can therefore *drop* `edit_file` and leave only serialization-safe shapes.
- **Sampling** — `AGENT_DIR/configs/sampling.yaml` is ours (`temperature`, `top_p`, `frequency_penalty: 0.4`, `thinking_budget`, etc.), all legal per §2.4.
- **Budgets** — `AGENT_DIR/eval_config.yaml` is ours (`max_tool_calls`, `max_time_minutes`, `max_turns`), per §2.2 / §7.1.

So every non-weight lever that matters for steering the edit shape is in our hands. The only thing out of reach is the tool *implementation*.

---

## 4. RECOMMENDED FIX — chosen only from what is available AND controllable

### Possible (ours to change)
- **R1 — Hard-remove `edit_file` from the `tools:` whitelist.** Not "tell the prompt to avoid it" (v18 did that and the model still reached for it because the tool was still exposed — see §5). If the tool is absent from the registry binding, the model physically cannot emit the failing call and cannot loop on it. Leaves `run_command` (B/C) + `write_file` (D) as edit paths. **In our control.** **[INFERENCE]**
- **R2 — Prompt all edits through `run_command` python-heredoc (shape C)**, with the `assert old in s` guard so a bad anchor fails loudly instead of silently. This is the only measured-to-land multi-line edit mechanism. **In our control.** **[MEASURED mechanism works; see §5]**
- **R3 — Fix the OTHER wall: the `read_file` pagination failure.** In both rich_4079 and rich_4076 the model's `read_file(start_line,end_line)` requests kept returning the file's top 150 lines, so it could never page to the target function and burned ~8-10 calls before falling back to `sed -n`. Steer the agent to read with `run_command("sed -n '300,350p' f.py")` from the start instead of `read_file` line-ranges. **In our control (prompt).** **[MEASURED]**
- **R4 — Prefer the ADD/OVERRIDE edit shape** (add a new self-contained method/override rather than replacing a multi-line span). The one reliably-resolved task (rich_4077) is a small forwarding-method add. Smaller edits serialize even through `edit_file`. **In our control (prompt).** **[MEASURED]**

### Impossible (harness-fixed)
- Re-parsing the malformed `edit_file` call host-side — harness code, not ours.
- Adding a line-range / `edit_by_line` tool — no such tool in the registry.
- Exposing an "apply-diff/patch" tool to the agent — none exists in-loop.
- Changing `edit_file`'s signature to a single-arg shape — signature is fixed by the harness.

### Single most promising first move
**R1 + R3 together, as ONE change set, keeping R2 as the mandated edit path.** Rationale: R1 removes the serialization loop at the source (the model can't call the tool it can't serialize), R2 gives it the one shape it serializes correctly, and R3 removes the read/search-death that killed rich_4079 *before* the edit even mattered. v18 did R2-in-prose only and left both R1 and R3 undone — the two reasons it did not stick (§5). Per rule 7 (one change per submission) these are tightly coupled "remove the broken edit path + its upstream blocker"; if a stricter one-knob reading is required, do **R1 first** (hardest-stop on the exact logged failure) and measure.

---

## 5. v18 RE-EVALUATION — did run_command-edit sidestep the serialization bug? YES. Why 1/5? Different wall.

**[MEASURED] What v18 actually was** (`Gemma/Outputs/v18/submission/`):
- `system.md` STEP 2: *"APPLY THE EDIT WITH run_command (NOT edit_file) ... the edit_file tool is UNRELIABLE for you ... DO NOT USE edit_file. Instead apply the edit with run_command."* It mandated the python-heredoc `replace` with `assert old in s`, and `sed -i` for single lines.
- **But `agent.yaml` STILL listed `edit_file` in `tools:`** (identical 9-tool list to v19). So the prohibition was prose-only; the tool remained callable.

**[MEASURED] Did run_command-edit sidestep the serialization bug?** Yes, where the agent reached the edit:
- Experiment log (`GEMMA_EXPERIMENT_LOG.md`, v18 result section): *"run_command edits fine when reached; rich_4070 even produced a 3157-char patch via run_command — it just ran out of budget first."* So the serialization bug is genuinely sidestepped by `run_command` (shapes B/C). The mechanism is sound.

**[MEASURED] Why it scored 1/5 anyway — the wall moved to the SEARCH phase:**
- Log v18 verdict: *"the model does NOT fail at edit execution, it never REACHES the edit."* rich_4079 committed to the correct file at step 4, then spent steps 5-20 (~16 calls) searching, and died. *"v18 did not touch the search phase — it only changed how edits are applied — so it could not move the number."*
- The `Gemma/Outputs/v19_Lora_v3` trace (the folder the user pointed at) shows the search-death mechanism concretely and adds a second cause the log had not isolated: **`read_file(start_line,end_line)` was effectively broken for the model** — every paged read of `rich/markdown.py` / `rich/text.py` returned the top of the file ("I keep getting the beginning of the file", "I am losing my mind. Why does read_file keep returning the start"), forcing `sed -n` workarounds and burning the budget. **[MEASURED]**

**[INFERENCE] Net:** v18 proved the run_command-edit idea *works as an edit mechanism* and is NOT the thing to abandon. It scored 1/5 because (a) it left `edit_file` exposed so the model could still fall into the serialization loop, and (b) it did nothing about the read/search-death that consumes the budget before the edit. Per accountability rule 11, the v18 "1/5" is a debugging result on execution gaps (tool still exposed + unaddressed read wall), not a verdict that routing edits through `run_command` is wrong.

---

## 6. BOTTOM LINE

- **Is there a zero-GPU, in-our-control fix that avoids forcing a big multi-line `old_string`? → YES. [MEASURED + INFERENCE]**
- It does NOT require changing the tool (which we cannot do). It uses shapes already in the harness and levers already in our submission: drop `edit_file` from the `tools:` whitelist, mandate the `run_command` python-heredoc `replace` (the one measured-to-land multi-line edit), and — equally necessary — stop the agent reading via the broken `read_file` line-range paging by routing reads through `sed -n` too.
- **Single most promising first try:** remove `edit_file` from `agent.yaml`'s `tools:` list (so the serialization loop is physically impossible) + prompt all reads via `sed -n` and all edits via the `run_command` python replace. This attacks *both* measured walls at once; v18 attacked only the edit path (and only in prose) and so could not move the score.
- **Honest caveat (uncertainty, rule 9):** the fix is in-our-control and the edit mechanism is measured to work, but it is **not yet measured to resolve these tasks** — the only external judge is a Kaggle run. The run/read-death wall is the live risk: if removing `edit_file` + `sed`-reads still leaves the model wandering the search phase, the remaining lever is weights (edit/loop-discipline LoRA), which is out of scope for a zero-GPU change. Pre-register the bar (e.g. rich_4079 and/or rich_4076 flip to resolved on the 5-task rich sample) before submitting.

---

### Evidence index (files read for this report)
- `Gemma/comp_files/HARNESS_README.md` — §1 (library stack / declarative-only), §2.1-2.4 (submission contract, limits, generation config), §5 (prompt + nudges), §6 (9-tool reference incl. `edit_file`/`run_command`/`write_file`/`read_file` signatures), §7 (budgets), §10 (gotchas).
- `Gemma/submit_v19_lora_v2/notebook_src.py` — the inline `agent.yaml` / `system.md` / `sampling.yaml` / `eval_config.yaml` writer (our controllable surface).
- `Gemma/GEMMA_EXPERIMENT_LOG.md` — "ROOT CAUSE CAUGHT LIVE" (serialization), v18 result + verdict, standings table.
- `Gemma/Outputs/v19_Lora_v3` — live trace: rich_4077 success (`strategy: 'unescaped'`), rich_4079 read-pagination death then edit_file serialization loop (25/30 calls, resolved=False, 0 chars), rich_4076 same read-pagination death.
- `Gemma/Outputs/v18/submission/{agent.yaml,prompts/system.md}` — v18 mandated run_command-edit in prose but left `edit_file` in the tool list.
- Repo-wide search — confirmed no vendored `swegemma`/`adk` tool source locally (tools are harness-side only).

Content was rephrased/condensed for compliance; direct quotes from the harness doc and traces are kept short and attributed to their file/section.
