# gemma-4-developer-agent discussions - pulled 2026-11-08 19:27 (315 topics)


---

## [BUG REPORT] tool parser can loop forever on an array tool argument, freezing the inference server for the rest of the run
/competitions/gemma-4-developer-agent/discussion/753973 | by  | posted 2026-10-29 23:20 | last comment 2026-11-09 01:17 | 5 comments | 5 votes


**** (2026-10-29 23:20, 5 votes)
**Environment**: the competition wheelhouse's vllm 0.19.1 (vllm/tool_parsers/gemma4_tool_parser.py), served with --tool-call-parser gemma4 and the default non-streaming chat path. The client is adk_submission's LiteLlm, with no explicit timeout.

**Trigger**: the model emits a tool call where an ARRAY argument holds an element that is not wrapped in Gemma's <|"|> string delimiter, and that element contains ]. For example args:["Fix list[str] handling"] (JSON-style quotes instead of <|"|>).

**Root cause:** in `_parse_gemma4_array` (lines 271–278, the "bare value" branch), the scan stops at the first `]` inside the element. On the next pass, `i` still points at that `]`. The branch consumes nothing, appends an empty item, and the `while i < n` loop never advances. This runs synchronously on the API server's event loop, so every later request also stalls. The server then ignores `SIGTERM`.

**Minimal repro (no GPU; the functions copied from the wheel, run with a step limit)**: 
```
from vllm.tool_parsers.gemma4_tool_parser import _parse_gemma4_args
_parse_gemma4_args('args:[<|"|>Fix list[str] handling<|"|>]')  # returns {'args': ['Fix list[str] handling']}
_parse_gemma4_args('args:["Fix list[str] handling"]')          # never returns
```

**Impact in a scoring run**:
- Every later task's first LLM request hangs until the per-task agent clock (max_time_minutes) cancels it.
- The client's 600 s read timeout is longer than typical per-task clocks, so retries never fire.
- So every remaining task scores 0, and the run can exceed its total time limit.
- We saw one occurrence in a validation run: 3 consecutive tasks with 0 LLM calls and 480 s each, after a task whose issue text contained Json[list[str]].


**** (2026-11-09 01:17, 0 votes)
facing same issues


**** (2026-11-08 13:35, 0 votes)
any update on this ? this is impacting our work


**** (2026-11-05 11:19, 0 votes)
I've encountered this issue twice.


**** (2026-11-05 08:21, 0 votes)
@ryanholbrook Adding evidence from real runs to this report, and a request for a decision.

**Same parser:** our local `gemma4_tool_parser.py` from vLLM 0.19.1 has the SHA-256 posted in 745138 (`682b2152…`).

**Real runs:** we had two server freezes during local evaluation with the competition's vLLM version, in roughly 830 tasks with agents that use `run_skill_script`. One API process reached 26.7 GB before it was OOM-killed. The in-flight output wasn't captured, so we can't prove these exact inputs caused them, but the symptoms match this report.

**Reproduced in a subprocess with a timeout (never returns):**
```
args:["Optional[int]"]
args:["run","x = a[0]"]
x:[a<|"|>]
args:[[<|"|>Optional[<|"|>]]
args:[[<|"|>x]<|"|>,<|"|>y<|"|>]]
```

**Why it matters:** the parser runs inside the API server, so as this thread describes, one such call can stall every later task in a scoring run. A valid agent could lose much of its score to a single malformed call, for reasons unrelated to how well it solves tasks.

**The fix is small:** vLLM fixed the loop upstream in [#41991](https://github.com/vllm-project/vllm/pull/41991), merged 8 May, by stopping when the parser makes no progress. We tried a similar guard locally, along with skipping strings in the nested-array scan, and all of the strings above returned normally.

**Our request:** could the hosts say whether the scorer will get this guard, or whether it stays as it is? Either answer helps, because teams need to know if they should remove array-argument tools before the deadline.


**** (2026-10-29 23:31, 0 votes)
@ryanholbrook can you take a look at this when you have time? thanks!


---

## Team up: root cause of the edit_file old_string loss (+1-line fix) and a 286-task eval set — our GPU died, looking to merge before 11/25
/competitions/gemma-4-developer-agent/discussion/756607 | by  | posted 2026-11-06 21:12 | last comment 2026-11-08 16:02 | 2 comments | -2 votes


**** (2026-11-08 04:11, 0 votes)
Colab is fairly cheap 9.99 a month. What GPU were you using?


> **** (2026-11-08 16:02, 0 votes)
> Sorry for the late reply, and thanks for the advice!
> We were using an RTX A6000 (48 GB).
> Given the time remaining, we've stopped our local evaluations and are now looking for a team to merge with.


**** (2026-11-06 21:12, -2 votes)
Our GPU box died mid-competition, so we can't validate further changes, but we have too much done to stop here. Looking to merge (1–2 people) before the 11/25 deadline.

**What we bring**
- The root cause of the edit_file failures the Paper Track reports as "~28% old_string loss, cause unknown." It is a single, measurable mechanism: affected calls fail 93%, unaffected calls 11%. A one-line prompt fix cut affected calls from 4.5% to 1.2% and removed the 60+ call retry loops. Note: this is a verified mechanism in our logs, but its effect on the hidden-set score is not confirmed (our run with the fix scored lower on the public LB), so we present it as a measurable finding, not a guaranteed gain.
- A 286-task local eval set (competition dev + two external sets) with 44 A/B runs, plus the noise and selection math for choosing final submissions.
- 32 public submissions across versions (public 0.17–0.18) and a clear list of what did not transfer to the hidden set.

**What we're looking for**
- A team with about 14 or fewer submissions, or up to about 25 if you stop submitting now. The merge rule caps our combined count: we have 32 and are not submitting while we look. Either GPU access to validate changes before 12/2, or a steady public score.

**How to contact**
Reply here with your current number of submissions, your submission scores, model/approach, and GPU setup. Please talk here before sending a merge request. Full details are shared after merging, per Kaggle's rules on private sharing.


---

## Tool results reach the model double-JSON-encoded: a line of code with quotes turns into a wall of backslashes
/competitions/gemma-4-developer-agent/discussion/744272 | by  | posted 2026-09-29 07:18 | last comment 2026-11-08 15:08 | 8 comments | 9 votes


**** (2026-09-29 07:18, 9 votes)
While reading our local traces (official swegemma 0.2.7 + adk-submission 0.2.11 + the wheelhouse vLLM 0.19.1), we noticed that every tool result reaches the model JSON-encoded **twice**. For code with quotes or backslashes it becomes hard to read. Here is one real `read_file` result, `tabulate.py` lines 140-170.

**The file:**

```python
LATEX_ESCAPE_RULES = {r"&": r"\&", r"%": r"\%", r"$": r"\$", r"#": r"\#",
                      r"_": r"\_", r"^": r"\^{}", r"{": r"\{", r"}": r"\}",
                      r"~": r"\textasciitilde{}", "\\": r"\textbackslash{}",
                      r"<": r"\ensuremath{<}", r">": r"\ensuremath{>}"}
```

**What Gemma 4 actually sees in the tool message (same four lines):**

```
LATEX_ESCAPE_RULES = {r\\\"&\\\": r\\\"\\\\&\\\", r\\\"%\\\": r\\\"\\\\%\\\", r\\\"$\\\": r\\\"\\\\$\\\", r\\\"#\\\": r\\\"\\\\#\\\",\\n                      r\\\"_\\\": r\\\"\\\\_\\\", r\\\"^\\\": r\\\"\\\\^{}\\\", r\\\"{\\\": r\\\"\\\\{\\\", r\\\"}\\\": r\\\"\\\\}\\\",\\n                      r\\\"~\\\": r\\\"\\\\textasciitilde{}\\\", \\\"\\\\\\\\\\\": r\\\"\\\\textbackslash{}\\\",\\n                      r\\\"<\\\": r\\\"\\\\ensuremath{<}\\\", r\\\">\\\": r\\\"\\\\ensuremath{>}\\\"}
```

Each `"` in the file becomes `\\\"`, each backslash becomes `\\\\`, and each newline becomes `\\n`.

**Where it comes from.** 
- The swegemma tools return a JSON *string* (`{"status": "ok", "content": "..."}`). Because the return value is not a dict, ADK wraps it as `{"result": <that string>}` (Gemini function responses must be dicts): that is the first level. - LiteLLM then has to serialize the dict into the OpenAI `content` string, since OpenAI tool messages are strings: that is the second level. The Gemma 4 chat template finally puts the string verbatim into `<|tool_response>response:read_file{value:<|"|>...<|"|>}<tool_response|>`.

**Why it matters.**
- `edit_file` requires `old_string` to match the file byte for byte, but the model only ever sees the escaped form. In our runs it regularly copies escapes into `old_string` and gets `old_string not found`. For example, in `arrow/locales.py` it wrote `"\u064a\u0648\u0645"` instead of the Arabic characters, twice in a row.
- It costs extra tokens on every step, and on the 4xL4 scorer every step is precious.

**A typical failure, and how often it happens.** `more_itertools/more.py`, the model wants to edit `chunked()`:

- The file has: `"""Break *iterable* into lists of length *n*:`
- `read_file` showed it (inside the tool message) as: `\\\"\\\"\\\"Break *iterable* into lists of length *n*:\\n\\n`
- The model un-escaped one level, not two, and sent `old_string` starting with: `\"\"\"Break *iterable* ...`
- Result: `Failed to replace: old_string not found. Ensure you're not escaping content incorrectly ...`. It sent the identical call again 43 s later and got the same error. The same task's edit to `more.pyi` (a line without quotes) went through on the first try.

Across our local runs, 62 of 299 `edit_file` calls failed with `old_string not found`. For 39 of them (in 18 different tasks) the cause is provably the escaping: un-escaping the model's `old_string` gives text that is present verbatim in what the model had just read. Python docstrings (`"""`) are the most common trigger; the Arabic-locale case above is another.

**Possible fixes (organizer side; submissions can't touch this layer):**
1. Cheapest: have the swegemma tools return a dict instead of a JSON string. ADK then passes it through without the `{"result": ...}` wrapper, and the model sees a single level of escaping (`\n` instead of `\\n`).
2. Cleanest: also let the dict reach the chat template as a mapping (e.g. parse JSON tool content back into a dict before templating in vLLM). Gemma 4's `format_tool_response_block` then renders raw text inside `<|"|>` with no escaping at all.

Each piece of this chain is reasonable on its own. But submissions have no way to touch this layer (no custom tools, no pre- or post-processing of tool output), so the only lever we have is to spend prompt and training effort teaching the model to cope with backslashes. **That feels somewhat removed from what this competition sets out to measure.**   @ryanholbrook I don't know whether this is a bug or a feature, or whether it should be fixed, but we're happy to share full traces if that helps.


**** (2026-09-30 02:31, 3 votes)
Thanks for addressing this. One data point that may help choose between the two fixes proposed above: we held 30 real edit contexts fixed (same system prompt, issue, analyzer answer and a read_file of the lines to change) and varied only how the read_file observation was encoded, sampling the next call three times per condition through the official chat template and vLLM's gemma4 parser at temperature 0.2:

| Observation encoding | edit_file calls | failed (old_string not found or argument lost) |
|---|---|---|
| current harness (JSON inside JSON) | 45 | 22% |
| one level of JSON | 40 | 62% |
| raw text | 43 | 0% |

A single level of escaping was worse than two in these contexts: sequences like a backslash followed by n look like ordinary Python escapes and get copied into old_string, while the doubled form was more often recognized as an artifact. Rendering the result as raw text (the second option in the post, a mapping reaching the chat template so the tool response block holds unescaped text) removed the failures entirely. So if only one change is possible, the raw-text path looks much safer than returning a dict that still arrives as one level of JSON.

One implementation detail we hit while testing the raw path: a dict passed as the content of a role "tool" message does not reach the mapping branch of format_tool_response_block. Jinja treats a dict as a sequence, so the template's content-parts branch iterates its keys and fails ('str object' has no attribute 'get'). The unescaped rendering needs the response to arrive through a path where the template sees a mapping (or the content-parts branch to check for a mapping first).


> **** (2026-10-20 03:33, 0 votes)
> `edit_file` handles this, but the rescue could do some damage


**** (2026-10-02 13:32, 1 votes)
Following up for anyone tracking this: the fix is live in the 09-30 wheelhouse. Tool results now reach the model as one level of JSON, and `edit_file` gained a fallback that retries the match with escapes removed.

We re-scored the replay from my earlier comment against that fallback. Edits that failed only because the model copied escaped text into `old_string` now succeed. What still fails is a call that loses an argument because a string was closed with a backtick: 4 of 45 edit calls with the old double encoding and 7 of 40 with a single level.

Thanks for turning this around quickly, @ryanholbrook.


**** (2026-09-29 14:03, 0 votes)
Thanks for the report. Addressing now.


> **** (2026-10-01 07:41, 2 votes)
> hi, what's the latest on this? this has a major influence on how training data is generated, it's important to address before people sink too much time into this competition


> > **** (2026-10-01 17:53, 0 votes)
> > The latest wheelhouse should have this fixed.


> > **** (2026-11-08 15:08, 0 votes)
> > Thanks for the fix. I can confirm it's in the wheelhouse we run locally (swegemma 0.2.11, adk-submission 0.2.13). When the model escapes both strings, edit_file now repairs both:
> > 
> >   apply_replacement('x = foo("a")\n', 'foo(\\"a\\")', 'foo(\\"b\\")')
> >   -> strategy 'unescaped', new_content 'x = foo("b")\n'
> > 
> > One small case I wanted to flag, in case it's not intended. The repair seems tied to the old_string lookup. If old_string matches exactly but new_string is escaped, the escapes are written into the file as typed:
> > 
> >   apply_replacement('add_cell(column, Text(""))\n', 'Text("")', 'Text(\\"\\")')
> >   -> strategy 'exact', new_content 'add_cell(column, Text(\\"\\"))\n'
> > 
> > I only reproduced this with a constructed call. What I saw in a real trace (rich_3518, Gemma 12B QAT, one level of escaping in the tool results) was the same mistake in text staged through write_file, since our submission replaces edit_file with a skill. The model read Text(\"\") in the read_file output and copied the escapes into the new code. A syntax check caught it, but it cost a retry on a 5-minute budget.
> > 
> > I don't have rates, and I know a blanket unescape of new_string would be risky because \" is legitimate in real code. A cautious option might be to retry only when the result fails to parse (for .py files). A line in the docs saying the fallback covers both strings only when old_string needed it would also help submissions plan around it.
> > 
> > Is the current behavior intended? Happy to share the trace.


**** (2026-09-29 09:36, 0 votes)
I’ve encountered the same issue. In my view, the model is weak, and the harness environment and tools are also a bit problematic. However, I suspect this might be a "feature" (or you can call it a "bug"), and I am currently working around it. If the organizers fix it, we are happy to see it, but some participants might have to redo their work, given that the competition has already been started for several days.


---

## Are hand-constructed LoRA adapters acceptable (weight edit from activation analysis, not gradient descent)?
/competitions/gemma-4-developer-agent/discussion/756792 | by  | posted 2026-11-07 16:17 | last comment 2026-11-08 14:20 | 1 comments | 1 votes


**** (2026-11-07 16:17, 1 votes)
Are hand-constructed LoRA adapters acceptable — e.g., an adapter that expresses a targeted weight edit derived from activation analysis, rather than one produced by gradient-descent fine-tuning? The adapter would be a standard PEFT LoRA adapter in the sanctioned format.


**** (2026-11-08 14:20, 0 votes)
As long as it loads, why would it matter? Would likely be a strong contender for the paper track


---

## Looking for a team or team mates
/competitions/gemma-4-developer-agent/discussion/748999 | by  | posted 2026-10-13 18:39 | last comment 2026-11-08 10:42 | 4 comments | 1 votes


**** (2026-10-13 18:39, 1 votes)
I am a postgraduate MSCS student researching on AI agents and their behaviors involving how LLMs make predictions and decisions (mechanistic interpretability) upon which the agent works. I am a former mechatronics and robotics engineer having 2 research publications in that domain https://scholar.google.com/citations?view_op=list_works&hl=en&hl=en&user=H96fD_kAAAAJ. My FYP RP is currently in process of publishing and a recent paper based on the explainability and robustness of NLP models is also in process of publication. I have successfully won the MediaEval'26 benchmarking competition for the Missing Pieces and Misinformation task for which my write-ups were presented in ICMR'26 Amsterdam this year. My papers of that competition are also in process of being published. You all can verify them on my LinkedIn profile (www.linkedin.com/in/moez-ur-rehman). Moreover, I am passionate about research work and making myself competitive by taking part in hackathons and competitions, so I take part in them and have been taking part in them this year. 

I am looking for a passionate and dedicated team or teammates who want to put all of their efforts in winning this competition. 
Anyone who wants to join or take me in their team can comment on this or message me privately.
Thank You.


**** (2026-11-05 23:04, 0 votes)
Hi, I just sent you a message.


> **** (2026-11-08 10:41, 0 votes)
> i'll go through it and let you know soon.


**** (2026-11-05 21:46, 0 votes)
Hello , I am willing to join , I sent you a message.


> **** (2026-11-08 10:42, 0 votes)
> i'll go through your message and let you know soon.


---

## Question regarding timelimits 
/competitions/gemma-4-developer-agent/discussion/756963 | by  | posted 2026-11-08 09:49 | last comment 2026-11-08 09:49 | 0 comments | 0 votes


**** (2026-11-08 09:49, 0 votes)
How much time do we have in total and how many tasks are there in total?
What happens if the time runs out?
Is the attempt just cut or do we get a score of 0?


---

## Scoring zero when using LoRA adapters
/competitions/gemma-4-developer-agent/discussion/755677 | by  | posted 2026-11-04 08:14 | last comment 2026-11-07 08:34 | 8 comments | 5 votes


**** (2026-11-04 08:14, 5 votes)
# Scoring zero when using LoRA adapters

Hi everyone,

I am investigating an issue where submissions that include a LoRA adapter consistently score **0.00** on the public leaderboard, while submitting the **exact same code, prompt, tools, and configs without the adapter scores 0.18**.

I would love to know if anyone has successfully submitted a scoring LoRA adapter on `gemma-4-31b-it-qat-w4a16-ct`, or if the Kaggle evaluation backend requires a specific adapter configuration.

---

### 1. My Submissions and Experimental Setup

Across all tests, my `agent.yaml`, `configs/sampling.yaml`, `eval_config.yaml`, tools, and system prompts were kept **strictly identical**:

* **Base Model**: `gemma-4-31b-it-qat-w4a16-ct`
* **Tools**: `run_command`, `read_file`, `edit_file`, `write_file`, `get_status`, `submit_patch`
* **Eval Config**: `timeout_seconds: 240`, `max_tool_calls: 28`, `max_time_minutes: 8`, `max_turns: 80`
* **Sampling Config**: `temperature: 0.2`, `top_p: 0.95`, `thinking_budget: 4096`, `include_thoughts: true`

Here is what happened across three controlled submission tests:

| Submission | Adapter Config | Target Modules | Safetensors / Zip Size | Local Benchmark (129 SWE-bench) | Kaggle Public LB Score |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`submission_v21_lora`** | $r=16, \alpha=32$ | All 7 projections (`q, k, v, o, gate, up, down`) | 509 MB / 462 MB | **17 / 129 (13.18%)** | **0.00** |
| **`submission_v24_rank4_svd`** | $r=4, \alpha=8$ | All 7 projections (SVD compressed) | 127 MB / 108 MB | **14 / 129 (10.85%)** | **0.00** |
| **`submission_v23_zero_shot`** | **None (Zero-shot)** | — | **0 MB / 7.7 KB** | ~12 / 129 (9.3%) | **0.18** |

---

### 2. Specifications of the Two Adapters That Scored 0.00

#### Adapter 1: `submission_v21_lora.zip` (Full SFT Rank-16)
* Trained with trajectory-level SFT on 2,377 gold verified SWE-bench traces.
* **Weights**: 509.37 MB `adapter_model.safetensors`.
* **Config (`adapter_config.json`)**:
```json
{
  "peft_type": "LORA",
  "task_type": "CAUSAL_LM",
  "base_model_name_or_path": "google/gemma-4-31b-it-qat-w4a16-ct",
  "r": 16,
  "lora_alpha": 32,
  "lora_dropout": 0.05,
  "bias": "none",
  "target_modules": [
    "down_proj",
    "gate_proj",
    "k_proj",
    "o_proj",
    "q_proj",
    "up_proj",
    "v_proj"
  ]
}
```
* **Packaging in ZIP**:
```text
adapters/main_lora/adapter_config.json
adapters/main_lora/adapter_model.safetensors
agent.yaml (with `adapter: main_lora`)
```
* **Result**: Scored **0.00**.

#### Adapter 2: `submission_v24_rank4_svd.zip` (Ultra-Lightweight Rank-4 SVD)
* Hypothesizing that 509 MB might exceed multi-GPU KV-cache allocations under vLLM, I factorized the weights via truncated SVD down to rank $r=4$, retaining 76.53% singular energy.
* **Weights**: 127.47 MB `adapter_model.safetensors` (108.4 MB total zip archive).
* **Config (`adapter_config.json`)**:
```json
{
  "peft_type": "LORA",
  "task_type": "CAUSAL_LM",
  "base_model_name_or_path": "google/gemma-4-31b-it-qat-w4a16-ct",
  "r": 4,
  "lora_alpha": 8,
  "lora_dropout": 0.05,
  "bias": "none",
  "target_modules": [
    "down_proj",
    "gate_proj",
    "k_proj",
    "o_proj",
    "q_proj",
    "up_proj",
    "v_proj"
  ]
}
```
* **Result**: Also scored **0.00**.

---

### 3. Why the Discrepancy? What I Noticed Locally

When testing locally with HuggingFace PEFT on `gemma-4-31b-it-qat-w4a16-ct`, I noticed that linear projections in this quantized checkpoint are wrapped inside `Gemma4ClippableLinear` container modules. Unpatched PEFT `_create_new_module` throws an exception unless monkey-patched to inspect `target.linear`:

```text
ValueError: Target module Gemma4ClippableLinear(...) is not supported. 
Currently, only torch.nn.Linear, torch.nn.Embedding... are supported.
```

If Kaggle's backend evaluation harness attempts to load `adapters/main_lora` via standard stock PEFT or vLLM without handling `Gemma4ClippableLinear` / `compressed-tensors`, it might be raising an uncaught exception at agent startup, causing the submission to terminate before Task 1 begins.

---

### 4. Questions for the Community and Hosts

1. **Has anyone obtained a non-zero public score with ANY LoRA adapter on `gemma-4-31b-it-qat-w4a16-ct`?**
2. **Backend Engine**: Is the evaluation runner loading the adapter via HuggingFace PEFT (`PeftModel.from_pretrained`), or via vLLM with `--enable-lora`?
3. **Module Targeting**: Does `target_modules` in `adapter_config.json` require a specific regex syntax (e.g. scoping strictly to `.*language_model.*`) rather than a list of module names?
4. **Directory Structure**: Does `agent.yaml` expect `adapter: main_lora` referencing `adapters/main_lora/`, or should the adapter files reside directly in the root or a different directory?

Any insights from the hosts or competitors who have worked with adapters would be greatly appreciated!


**** (2026-11-04 10:30, 2 votes)
I think something is wrong with either your setup or with your submission stucture. It is possible to score > 0 with a LoRA adapter


> **** (2026-11-07 08:34, -1 votes)
> can you expain what haeppn and what you did


**** (2026-11-04 12:51, 1 votes)
I came to test some training recipe ideas but there seems to be a lot of hoops to jump through. I’m reading that using LoRA reduces decoding speed and context limit. Are these claims true? I can’t even test these claims easily with submissions being 30+ hours.


**** (2026-11-04 11:41, 1 votes)
I got a non zero score with rank 32 lora for the same model with 4 minute task timeout


**** (2026-11-04 10:50, 1 votes)
I think you also get 0 if your submission timed out.


**** (2026-11-04 23:57, 0 votes)
Data point from our team, same base model (gemma-4-31b-it-qat-w4a16-ct), and an adapter shaped like yours: rank 16, alpha 32, all 7 projections on all 60 language layers, served as main_lora.

┌────────────┬───────────────────────────────────┬───────────────────────────┬───────────────────────────────────────┐
│ Submission │              Adapter              │   Task cap / thinking     │                Result                 │
│            │                                   │          budget           │                                       │
├────────────┼───────────────────────────────────┼───────────────────────────┼───────────────────────────────────────┤
│ A          │ run1, alpha 16                    │ 8 min / 4096              │ complete, no score                    │
├────────────┼───────────────────────────────────┼───────────────────────────┼───────────────────────────────────────┤
│ B          │ run2, alpha 32                    │ 8 min / 4096              │ complete, no score                    │
├────────────┼───────────────────────────────────┼───────────────────────────┼───────────────────────────────────────┤
│ C          │ run2, alpha 32 (same adapter as   │ 6 min / 2048              │ 0.17 (same as our no-adapter          │
│            │ B)                                │                           │ baseline)                             │
└────────────┴───────────────────────────────────┴───────────────────────────┴───────────────────────────────────────┘

So the adapter does load and score on the grader. On a Kaggle 4×L4 test run, vLLM listed and served it, but each task took about 29% longer (about 45% more tokens per step). With 120 tasks at an 8-minute cap, that pushed us over the 12-hour total limit. Cutting the task cap and the thinking budget fixed it.

One difference: ours came back as "complete, no score", not 0.00, so your failure may be a different one. A quick way to tell: rerun your v21 with a 5–6 min cap and thinking 2048. If it scores, it's time; if it's still 0.00, look at loading.


**** (2026-11-04 23:26, 0 votes)
why your tensor takes 509mb？


**** (2026-11-04 18:41, 0 votes)
I believe something is wrong with submission structure


---

## Team merger: which score does the merged Team carry?
/competitions/gemma-4-developer-agent/discussion/756693 | by  | posted 2026-11-07 06:53 | last comment 2026-11-07 06:53 | 0 comments | -3 votes


**** (2026-11-07 06:53, -3 votes)
Quick rules question before the Team Merger Deadline (2026-11-25).

Section 5 of the competition rules says team mergers are allowed and that the combined Team must have a total submission count within the allowed maximum. But it does not say what the merged Team's leaderboard entry will be.

Could someone from Kaggle confirm:

1. After two Teams merge, does the merged Team carry the **best** score among the two Teams' submissions, or the most recent one, or something else?
2. Does the merged Team's daily submission allowance reset to the standard per-day limit on the day the merge completes?
3. If the two Teams are on different score bands on the leaderboard, is the merged entry placed using the better of the two?

I'm a solo participant and would like to know this before making an irreversible merge. Thanks a lot.


---

## How to get started with the solution development of this hackathon problem
/competitions/gemma-4-developer-agent/discussion/756622 | by  | posted 2026-11-06 22:20 | last comment 2026-11-07 02:34 | 1 comments | 0 votes


**** (2026-11-07 02:34, 1 votes)
This is the simplest kaggle competition ever if you go by what is required for submission: you just need to submit at the minimum 4 files consisting of agent yaml, prompt md and configuration yamls!! If your solution involves LoRA training, you need to submit your trained LoRA adapter.

Take the best public scoring notebook and look at the output submission.zip and create a notebook that can modify these files and submit after going through the best voted public notebooks

If you believe that gemma 4 has got all intelligence to fix github issues when assisted with agent framework orchestration, skills and instructions (like me!) and that no LoRA training is required, then you have to go beyond a single system.md and use agents. However, the max  public score as of today is from simple sysetm.md - i.e. from just four md files!

As of now, it is not possible to use sequential agents - unless otherwise you find a solution to manage the compaction problem and context window length issues. To my knowledge, there is no public notebook that uses these agents with score that competes with singe prompt. You can however also use agent_tools as given in starter notebook.

The submission notebook MUST solve ALL of the around 120 tasks in 12 hours. If it takes more than 12 hours, then you score zero. This has significantly altered the nature of this competition challenge. Competition hosts intially were willing to score whatever completed intstead of binary scoring either 0 or all tasks. However, due to issues in handling private datasets, this option was ruled out. Hence, the challenge is NOT JUST building complex agent frameworks but MANAGING time. The average tiime per task is around 6 mins max to prevent notebook timeout. However, there are significant tasks that require more than 8 minutes. This is why simple system.md scores over agent orchestration defeating some important objectives of this competition. If you can manage to create a agent framework that can take max time cap of 8 minutes, then you can compete with plain system.md

Another serious challenge is inherent weakness intool usage by gemma (may be LoRA can solve this, am not sure). The edit_file tool malfunctions which you need to resolve.  Similarly, there are several issues that lead to exhausting time cap per task (surprisingly, this does not manifest in single system.md! 😀). These issues have to be isolated and resolved. I think the reason some notebooks score differently when re-submitted ( a 0.22 scored notebook might score 0.13 if resubmitted as per some kagglers) is not because LLM's intrinsic non-detereministic nature but whether these tool issues manifest or not in that run - if you have not solved those issues, then you need to depend on luck!😀 (But I have also seen many non-tool issue cases where the agent simply spends time thinking, re-executing commands etc., all of which are difficult to isolate and solve)

My efforts to use 2-3 agents were not successful. Nor the efforts to skip the tasks.

This competition would have offered more scope for insights and solutions for small models like gemma 4 if the time management is not such a major issue, this is my opinion and conclusion

(Note: The tasks dataset has some isues - not all tasks pass even golden patch - only 114 of  129 are valid - the issue is elaborately analyzed and insights are available in public notebooks)


**** (2026-11-06 22:20, 0 votes)
So far I have gone through the basic theory and problem statement of the hackathon and the notebooks present in the Code section of this hackathon . I unable to figure out what to do with the codes and data that has been provided to us in the competition. I want some direction and advice on how to get started and play with the data provided for getting better understanding of what is going on . Please someone give me sone advice and direction on what to do , how to run the dockerfile for this competition.


---

## in EventsCompactionConfig: LlmEventSummarizer drops all tool calls and tool responses
/competitions/gemma-4-developer-agent/discussion/754783 | by  | posted 2026-11-01 16:35 | last comment 2026-11-07 02:27 | 1 comments | 3 votes


**** (2026-11-01 16:35, 3 votes)
When context compaction triggers, LlmEventSummarizer._format_events_for_prompt() formats the event history for the summarization LLM by only checking:
```
    for part in content.parts:
        if part.text:
            text += part.text
```


  Because tool-calling turns store actions in part.function_call and tool results in part.function_response (with part.text often being empty or None), the summarizer completely ignores
  all tool invocations and tool outputs.

In software engineering benchmarks (like SWE-bench / Harbor), over 90% of turns are tool executions (read_file, run_command, edit_file).
  When compaction runs:

  1. The summarizer is fed only the initial user prompt, completely blind to all the commands, tests, and edits the agent performed.
  2. The summarizer outputs: "Task assigned, but no actions or code changes have been made yet."
  3. The agent receives this truncated history, loses its execution context, and either loops from scratch or terminates prematurely.


**** (2026-11-07 02:27, 0 votes)
This is a real concern since most of the context up to the time of compaction are tool calls. Good news is that usually a tool call has its reasoning content, which will be read by compaction, so most tool call is not totally forgotten. What might be forgotten is the tool call result. If the agent didn't paraphrase the previous tool call result before its next action, the result is forgotten forever. 

But it seems like the competition host will not upgrade to ADK v2. So expect the same compaction behavior as is. See organizer's reply: https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748287

But this is another evidence to support upgrading to ADK v2, if @ryanholbrook decides to upgrade (please do 🙏).


---

## 🌟Bonus Prize: Small Model Development ($10,000)
/competitions/gemma-4-developer-agent/discussion/751104 | by  | posted 2026-10-20 19:12 | last comment 2026-11-07 00:18 | 8 comments | 38 votes


**** (2026-11-07 00:18, -1 votes)
Fascinating study and very clean empirical methodology, especially using exact McNemar tests on paired instances! 👏

    Regarding your core question about retrieval gains disappearing once the relevant file fits in context:

    We observed very similar dynamics while benchmarking local Gemma 4 on real-world multi-file repositories:

    1. Context Saturation Threshold: When a module fits comfortably within the model's high-fidelity attention window (< 4k tokens), giving the full file or
    surrounding context often performs on par with AST slicing. The model utilizes contextual clues across helper definitions. However, as module size crosses
    ~600+ lines (or multi-file imports), un-sliced files trigger context dilution, and deterministic AST code slicing yields a 44.6% reduction in prompt tokens,
    preventing attention decay.

    2. The "Broken Patch" Bottleneck in Test-Driven Self-Correction: Like your findings with test feedback (26% → 42%), running reproduction tests is where real
    gains happen. However, on local quantized models, multi-turn retries often introduce invalid indentation or incomplete ASTs. We found that gating patches with
    an instantaneous local AST parse gate (47.2 µs latency) before spinning up execution environments prevents wasteful container churn and avoids burning budget
    on unparseable diffs.

    3. Traceback Compression: One trap we encountered with test feedback is that raw pytest logs (often 75–100+ lines of setup/teardown boilerplate) quickly
    exhaust the remaining context budget across 3 retry attempts. Compressing logs down to the root cause assertion while discarding runner frames gave us a 30.6%
    token saving without losing the fault signal.

    Our full verification suite and benchmarks are open under Apache 2.0 on GitHub (search for msingatullin/gemma-4-developer-agent) and in our public Kaggle
    notebook ("AST-Guided Loops Verification for Gemma 4").
    
    Kudos on the great paper and reproducible setup!


**** (2026-10-20 19:12, 38 votes)
We are offering an additional **$10,000 bonus prize** dedicated to small-footprint developer agents:

- **Award:** $10,000 to the highest-ranking submission utilizing **Gemma E2B** or **Gemma E4B**. Final scores are based on the private test set performance. Same submission rules and tie-breaking apply.

- **Eligibility:** Submissions must explicitly use either Gemma E2B or Gemma E4B as the base model. For a submission to be eligible it must be one of the team’s two selected final submissions. LoRA fine-tuning is allowed just as done for the main track. 

- **Daily Leaderboard Tracking:** A [separate Kaggle notebook](https://www.kaggle.com/code/ryanholbrook/gemma-4-developer-agent-small-model-leaderboard) will be released and updated daily to display public standings for eligible small model entries. 

- **Cross-Track Eligibility:** Submissions eligible for the Small Model Prize remain fully eligible for general leaderboard awards and the Paper Track.

- **Deadline:** Same submission deadlines apply as the main track prizes.


**** (2026-10-21 15:54, 8 votes)
Thank you for introducing this meaningful small-model prize!
Would you consider making it a separate Kaggle competition? This would preserve the two final submission slots for the main competition while giving small-model-focused teams a chance to earn Kaggle medals.🎉


**** (2026-11-06 15:15, 0 votes)
Thanks! Could you update the leaderboard's notebook daily?


**** (2026-10-28 20:36, 0 votes)
this is cool!


**** (2026-10-25 14:32, 0 votes)
I read the Harness readme markdown file and it has gemma4-27b-it and gemma4-27b in it:
```MD
3.3. Pre-Registered Model Aliases & Routing
models.yaml and _build_cli_model_registry() (src/swegemma/cli.py) register the following Gemma 4 aliases in ModelRegistry:

gemma-4-31b-it-qat-w4a16-ct, gemma-4-12b-it-qat-w4a16-ct, gemma-4-e4b-it-qat-w4a16-ct, gemma-4-e2b-it-qat-w4a16-ct (Official quantized competition models)
gemma-4-31b-it, gemma-4-31b
gemma-4-27b-it, gemma-4-27b
gemma-4-26b-a4b-it, gemma-4-26b-a4b, diffusiongemma-26b-a4b-it
gemma-4-12b-it, gemma-4-12b
gemma-4-9b-it, gemma-4-9b
gemma-4-e4b-it, gemma-4-e4b
gemma-4-e2b-it, gemma-4-e2b
```
Can you please correct it @elanlearns


**** (2026-10-22 21:11, 0 votes)
This is a great addition, looking into those models now.


**** (2026-10-20 22:49, 0 votes)
That's really encouraging! Thanks @elanlearns.


---

## Looking for 1–2 teammates — TPU eval engine that matches the scorer + LoRA pipeline (0.17)
/competitions/gemma-4-developer-agent/discussion/750907 | by  | posted 2026-10-20 04:39 | last comment 2026-11-07 00:01 | 5 comments | -13 votes


**** (2026-11-01 10:00, -1 votes)
Hi Mehmood — interested. Solo at 0.18 public (v2: ADK agent + one-shot patch_reviewer sub-agent). Ran an honest dev-eval on a fixed 30-task subset: v1–v6 prompt/thinking-budget changes all within noise (11–12/30); main failure = wrong patch + tool-call cap. Plan next: structural reproduce→patch→test→fix loop. Agree on equal split + held-out selection. Happy to start a public-info trial. Also on the paper track.


> **** (2026-11-06 03:23, -1 votes)
> Hi YosQuant, sorry for the slow reply. Your reproduce→patch→test→fix loop is the part we haven’t tried, and our TPU eval engine can test it without using GPU quota.
> 
> I’m busy with the paper until Nov 12. After that, trial idea (public info only, no code until we merge): we each test one idea on a fixed task set and share the numbers. If results line up, we agree the equal split in writing and merge before Nov 25.
> 
> One other person has also offered to join, so it may be three of us. What’s the best way to talk, Kaggle DM or email?


> > **** (2026-11-06 06:34, 0 votes)
> > Hi Mehmood, no worries, and good luck with the paper!
> > 
> > Your plan works for us. After Nov 12, each side tests one idea on the same fixed task set and we share numbers only, no code until we merge. For the task set, we're publishing a 30-task subset (IDs + checksums) around Nov 11, so we could both use that to keep results directly comparable.
> > 
> > If the results line up, we agree the equal split in writing and merge before Nov 25. One thing to check first: our side may have 2–3 members by then, so let's confirm the team-size limit leaves room for everyone before we commit.
> > 
> > Kaggle DM is best for us. Talk after the 12th!


> > **** (2026-11-06 17:08, 0 votes)
> > Thanks YosQuant, sounds good. I checked the rules: team limit is 5, so your 2-3 plus me and the other person fits. One more check: a merged team can have at most 1 submission per day since Sep 23 in total. I have 17, how many does your side have?
> > 
> > Happy to use your 30-task set. But in our repeat runs, the same config changes on about 10-13% of tasks, so 30 tasks can hide small gains. Can we run each config twice, or also use our public 106-task set?
> > 
> > Kaggle DM after the 12th works.


> > **** (2026-11-07 00:01, 0 votes)
> > Thanks Mehmood. Our side has 3 submissions since Sep 23, so 17 + 3 = 20 total. That fits under the merged cap.
> > 
> > Agreed on noise. Our own paper found the same ~10–13% flip rate on repeated runs, which is exactly why we report replication. Let's do both: run each config twice on our 30-task set, and use your public 106-task set as a held-out check. A change only counts if it wins on both.
> > 
> > Kaggle DM after the 12th works for us. Talk then.


**** (2026-10-20 04:39, -13 votes)
Hi all, I'm looking for 1–2 serious teammates for the main track (and the paper track).

What I have so far:
- Public LB 0.17 (ADK agent on Gemma 4 31B, many prompt/skill ablations with run logs)
- A free evaluation engine: Gemma 4 31B served with vllm-tpu on Kaggle TPU v5e-8, running the same tasks as the scorer. Its results match real GPU runs (21 vs 21–22 on the same 51 tasks), so we can test ideas without burning GPU quota
- A LoRA self-distillation pipeline (training on the agent's o![![![>](YouTube video url to embed)](YouTube video url to embed)](YouTube video url to embed)wn successful trajectories with thinking, exported to PEFT, verified to load in the scorer's vLLM)
- Failure analysis: the agent finds the right file in ~90% of tasks; most losses are wrong/incomplete fixes

What I'm looking for:
- Someone with time to run experiments (each teammate's weekly Kaggle GPU/TPU quota roughly doubles how fast we can test ideas)
- A score of 0.17+ or your own ideas/compute is a plus, but not required

How I'd like to work:
- Equal prize split (Kaggle default), agreed in writing before merging
- Pick the final 2 submissions by held-out evidence, not public LB luck
- Short trial collaboration first (on public info only, per competition rules), then merge before the Nov 25 deadline

Comment here or message me if interested.


---

## Local evals: 27 public fastapi tasks can never pass in the sandbox
/competitions/gemma-4-developer-agent/discussion/756587 | by  | posted 2026-11-06 19:47 | last comment 2026-11-06 19:47 | 0 comments | 0 votes


**** (2026-11-06 19:47, 0 votes)
If you are tuning your agent on the 129 public tasks, note that 27 fastapi tasks fail at test collection whatever patch you write: their tests import `inline_snapshot` or `dirty_equals`, which the sandbox does not have. The host confirmed scoring uses private repos, so this only affects local evaluation, but it caps your measured resolve rate at about 79% and adds noise to any A/B comparison that includes them. Excluding them gives a cleaner signal.

fastapi_11355, fastapi_12942, fastapi_13713, fastapi_13786, fastapi_14099, fastapi_14246, fastapi_14262, fastapi_14297, fastapi_14303, fastapi_14349, fastapi_14356, fastapi_14360, fastapi_14361, fastapi_14371, fastapi_14430, fastapi_14455, fastapi_14459, fastapi_14482, fastapi_14485, fastapi_14512, fastapi_14583, fastapi_14605, fastapi_14791, fastapi_14953, fastapi_14962, fastapi_14964, fastapi_15023

Details: https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/discussion (my paper track thread)


---

## Gold patches fail
/competitions/gemma-4-developer-agent/discussion/756461 | by  | posted 2026-11-06 11:59 | last comment 2026-11-06 18:34 | 1 comments | 0 votes


**** (2026-11-06 18:34, 1 votes)
They fail public not Private I believe was stated by the hosts.


**** (2026-11-06 11:59, 0 votes)
In the Getting Started notebook’s sandbox, gold patches fail on about 43% of the public tasks, mostly because test dependencies are missing (inline_snapshot for fastapi; fixtures for requests, with ~190 collection/setup errors per run). Does the Kaggle scoring environment have these dependencies, so that those tasks are scoreable?


---

## How you guys considering time allocations
/competitions/gemma-4-developer-agent/discussion/756438 | by  | posted 2026-11-06 09:14 | last comment 2026-11-06 18:33 | 1 comments | 3 votes


**** (2026-11-06 09:14, 3 votes)
how you guys are doing time allocations for tasks which needs allocations. Like its better to solve 60 tasks completely and 60 not to attempt instead of 120 tasks partially. How you guys are managing this because in current harness it doesnt seems supported properly.


**** (2026-11-06 18:33, 1 votes)
58 tasks public/private so the 129. There is a bit of a high noise wall .20 also scored .18 .17 .17 .17 .13


---

## Rerunning Failed Submissions
/competitions/gemma-4-developer-agent/discussion/743683 | by  | posted 2026-09-26 12:01 | last comment 2026-11-06 12:09 | 107 comments | 21 votes


**** (2026-11-06 11:34, -1 votes)
Hi @ryanholbrook 

My submission to the Gemma 4 Developer Agent Competition has been stuck at "Notebook Running" for over an hour.

Submission: Gemma 4 Developer Agent – Custom Submission – Version 13.

The notebook execution completed successfully in 53.3 seconds. The submission ZIP was generated, validated, and uploaded, but the competition evaluation has not completed.

Could you please check whether my submission is stuck in the L4×4 evaluation queue and advise whether it can be rerun?

Thank you.


**** (2026-11-03 00:02, -2 votes)
Hello,

My submission to the Gemma 4 Developer Agent Competition ended with Notebook timeout.

The submission archive was generated and locally verified successfully:

submission.zip exists and contains exactly four files.

agent.yaml is located at the archive root.

All files passed CRC, byte-by-byte content and SHA256 verification.

The archive follows the same structure as my previous submission.

The configuration uses gemma-4-31b-it-qat-w4a16-ct, with no LoRA adapters.

Could you please check whether this timeout was caused by the scoring infrastructure, inference server, or the agent execution itself? If it was an infrastructure-related failure, would it be possible to rerun the submission?

Submission ID: [INSERT ID]

Notebook version: [INSERT VERSION]

Thank you.


**** (2026-11-02 16:06, -1 votes)
Hi Kaggle team,

My Gemma 4 Developer Agent submission has been stuck in "Notebook Running" for over 18 hours.
Notebook: Gemma4 SWE Agent T8 Static - v1  
Script Version ID: 364682696
The original notebook completed successfully in 21 seconds and generated the required submission.zip.
Could you please check whether the submission is still being evaluated, queued, or stuck due to an infrastructure issue?

Thank you!


**** (2026-10-22 06:30, -1 votes)
Hi @ryanholbrook, two of our recent subs failed and I'm not sure whether it's on our side.

57460663 (Oct 21): "incorrect format", came back about 18h after submitting
57506270 (Oct 22): "unhandled error", only about 30 min in

Same bundle both times, just yaml + prompts (no adapters, no skills), 8 min / 28 calls per task. The same files with a 6 min cap scored fine (57377398). I also ran this bundle with the official harness in a 4xL4 notebook on 32 of the public tasks and it averaged ~225 s per task including setup, so the 12h limit shouldn't be the problem.

Could you check if these were scorer-side? If so, a rerun or getting the two slots back would help a lot. Thanks!


**** (2026-09-26 12:01, 21 votes)
Hi everyone,

Some submissions since yesterday were failing with `"Your notebook has requested more CPU, GPU or TPU resources than are available."` I believe I've resolved the issue, though please let me know if you're still having issues. I will rerun the affected submissions on Monday so that you won't be losing a submission.


**** (2026-10-08 08:37, 3 votes)
Hi @ryanholbrook, our two submissions ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists.":

56888287 (Oct 6, 18:28 UTC)
56907342 (Oct 7, 09:48 UTC)
Both are config-only bundles (agent.yaml, one prompt, sampling.yaml, eval_config.yaml; no adapters or skills), validated with the current wheelhouse, with 5.0- and 4.0-minute per-task caps. That is well within 12 h even at 120 tasks. This looks like the same pattern as #746480. Could you check whether these were infrastructure failures and, if so, include them in the rerun or restore the slots? Thanks!


**** (2026-10-08 15:21, 2 votes)
Hi @ryanholbrook , our submission 56924848 (Oct 8, 00:01 UTC) ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists." about two minutes after upload, i.e. before the model server could even have started. It is a config-only bundle (agent.yaml, one prompt, sampling.yaml, eval_config.yaml, one skill with three Python scripts; no adapters), validated with the current wheelhouse, with a 5 min/task cap. Same pattern as the many other reports in this thread.

Could you include it in the rerun or restore the daily slot?

More generally, it has become really hard to get a submission scored these past days: with a single submission per day, every system error costs a full day, and we cannot tell in advance whether a submission will be scored, error out immediately, or fail after 15 hours. Many of us spend hours preparing and validating each bundle, and right now the competition is hardly workable under these conditions. Could you give us some visibility on the status of the scoring infrastructure, and not count infrastructure failures against the daily allowance? Thanks!


> **** (2026-10-08 17:30, 1 votes)
> The problem is it hurts independent people more then studios as they can verify their runs on the hardware they have and i know it doesnt cost much to rent a cloud for a single run but that doesnt make it any better.


**** (2026-10-08 07:00, 2 votes)
Hi @ryanholbrook, my last two submissions (submitted 17h ago and 1 day ago) ended in Kaggle Error
A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists. See more debugging tips.


**** (2026-10-08 06:51, 2 votes)
Hi @ryanholbrook, two of our submissions ended in ERROR with error_description "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists.":
 - 56887952 (submitted Oct 6, 18:09 UTC), which ran for about 15 hours before erroring
 - 56906721 (submitted Oct 7, 09:19 UTC), same as previous

This looks like the same pattern reported in #746480 (long run, then Kaggle Error). Could you check whether these were infrastructure failures and, if so, rerun them? Thanks!


**** (2026-10-08 04:01, 2 votes)
Hi @ryanholbrook, our submission 56895692 (Oct 7, 00:47 UTC) ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists." after a long run, same pattern as #746480. It's a YAML/prompt bundle plus one rank-16 LoRA adapter with a 5 min/task cap, validated with the current wheelhouse. Could you include it in the rerun? Thanks!


**** (2026-10-08 03:51, 2 votes)
Hi @ryanholbrook, our submission from Oct 7 (description "h1f: shell-only single agent, numbered calls...", file submission.zip) ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists." after roughly 21 hours, the same pattern described in #746480. It is a config-only bundle (agent.yaml, one prompt, sampling.yaml, eval_config.yaml; no adapters or skills), tools run_command and submit_patch only, with max_time_minutes 8, max_tool_calls 100 and timeout_seconds 300. A bundle of the same structure (different prompt) scored normally on Oct 5 (0.12), so this does not look specific to our configuration. We resubmitted the same bundle today and have not changed it. Could you check whether this was an infrastructure failure and, if so, include it in the rerun or restore the slot? Happy to provide anything else useful. Thanks!


**** (2026-10-07 11:47, 2 votes)
Hi @ryanholbrook, our submission 56889733 (Oct 6, 19:50 UTC) ended in ERROR with error_description "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists." It looks like the same pattern reported in #746480 (long run, then Kaggle Error). The bundle was a plain YAML config with no adapters and a 4.5 min/task cap. Could you check whether this was an infrastructure failure and, if so, rerun it? Thanks!


> **** (2026-10-07 16:07, 0 votes)
> Do we have to ask for a rerun for each submisiion that failed because of Kaggle error?


**** (2026-10-07 09:25, 2 votes)
My submission  has just failed after 15 h with kaggle error, so is there smth that can be done to resolve it ?


**** (2026-10-09 16:23, 1 votes)
Hi @ryanholbrook, my submission has been showing “Notebook Running” for more than 24 hours.

- Submission ID: 56936938
- Submission file: submission.zip
- Submission time: October 8, 2026, at 05:32:06 UTC (11:02:06 AM IST)
- Kaggle API status: PENDING

I saw your announcement about rerunning submissions affected by resource-allocation and queueing issues. Could you please check whether my submission is still progressing or stuck in the L4x4 evaluation queue?

Should I continue waiting, or will this submission be checked as part of the rerun? I would prefer not to resubmit and consume another daily submission slot unnecessarily.

Thank you!


**** (2026-10-08 15:57, 1 votes)
Hey! Seems like there was an issue.
But what shall we do of the one waste submission of ours?


**** (2026-10-08 15:32, 1 votes)
Good morning sorry to pile on our last two also had an error it seems like a lot of errorsshould we try and resubmit or wait until further notice?

"A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists."


> **** (2026-10-08 15:39, 0 votes)
> Sorry here are the IDs
> Submission ID 56925229	Oct 8 00:05
> Submission ID 56903771	Oct 7 07:20


**** (2026-10-08 03:23, 1 votes)
Hi @ryanholbrook ok, our two submission failed the same way. Both ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists.":

56887814 (Oct 6, 18:03 UTC), 
56905362 (Oct 7, 08:22 UTC): 

Both are YAML/prompt bundles, and both pass the harness's submission checks locally. Our two earlier submissions (56795767, 56833374) scored normally. Could you include both in the rerun? Thanks!


**** (2026-10-08 02:23, 1 votes)
Hi @ryanholbrook, my submission 56885658 (Oct 6, 16:20 UTC) ended in ERROR with "A system error. Please try resubmitting..." after about 15 hours, the same pattern as #746480. It is a config-only bundle with the two sample adapters, 8 min/task and 28 tool calls. Could you include it in the rerun? Thank you so much!


**** (2026-10-07 20:26, 1 votes)
for all those who are having gpu running out issues you can use google collab and link your kaggle notebook to google collab which will provide few extra compute hours


**** (2026-09-28 13:17, 3 votes)
Hi everyone,

I'm going to pause the rescore until we can resolve the queueing for the L4x4 machines. I will get it going as soon as I can.


> **** (2026-10-04 23:28, 0 votes)
> @ryanholbrook was the issue resolved?


> **** (2026-10-08 19:09, 0 votes)
> Hi @ryanholbrook, our two submissions ended in ERROR with "A system error. Please try resubmitting..." — same pattern as reported here:
> • 56900501 (Oct 7)
> • 56927955 (Oct 8, v10: bf16+linear-LoRA, 5min/task)
> Both pass validate_directory locally. Could you include them in the rerun and restore the daily slots? Thanks!


> **** (2026-10-09 17:50, 2 votes)
> will submissions be returned or the deadline extended? my submission is "scoring" for 2 days and i cant submit until it ends.


**** (2026-10-12 19:55, -1 votes)
Hi there, my submission has been running for 17hr, any help or suggestions?


> **** (2026-10-13 00:31, 0 votes)
> The same problem


**** (2026-10-12 19:53, -1 votes)
Hello again. Can you please take a look at my submission. It is running for 1 day already. Thanks


**** (2026-10-11 19:06, -1 votes)
what to do please? my submission is scoring for 48h? i cant submit until this is resolved


**** (2026-10-11 06:43, -1 votes)
Hi. Can you please take a look at my submission. It is running for 2 days already. Thanks


**** (2026-10-11 05:20, -1 votes)
Hi, my S4 submission has remained at “Notebook Running” for approximately two days. It was submitted on October 9 and uses the single-agent shell repair loop. The submission details still show no score or more specific execution status.

Could you please confirm whether this is waiting for L4x4 resources, actively executing, or stalled during evaluation? If it is stuck because of the current queueing issue, is a rerun possible?

I have not submitted a duplicate. Thank you.


**** (2026-10-10 14:08, -1 votes)
My submission is running for 14hours +


**** (2026-10-10 09:36, -1 votes)
@ryanholbrook Submission 56960867, account kevinermille, has remained PENDING since October 8, 15:40 UTC, with no score or error. ( 42h ago)

A new submission is rejected because our team already has one pending submission, despite today’s allowance being unused.

Could you please cancel/reset 56960867 only and release the pending slot, ideally before 08:00 HKT / 00:00 UTC? Please preserve our other submissions.


**** (2026-09-28 09:16, 1 votes)
Hi @ryanholbrook , I have a different kind of problem: I launched my notebook and it sat in the queue for 5 hours; it then ran for another 5 hours on GPU, but 10 hours were deducted from my GPU quota.

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F6426555%2Fcdb41f54dd33c19d64f033761ce05143%2FScreenshot%202026-09-28%20121340.png?generation=1790586918749457&alt=media)
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F6426555%2F4e9af6877fd480b4797be84dfea0cce0%2FScreenshot%202026-09-28%20121422.png?generation=1790586928959343&alt=media)


> **** (2026-09-28 10:40, 1 votes)
> same here. its showing 2x the notebook runtime


> > **** (2026-09-28 11:18, 2 votes)
> > i think they forgot to mention here but like in arc agi 2, where the same gpus are provided, they too take double the time from your gpu quota


**** (2026-09-26 12:19, 1 votes)
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F15559822%2Fff13fb1fad0d64c49eb279c792d21451%2FScreenshot%202026-09-26%20174740.png?generation=1790425085487856&alt=media)


![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F15559822%2Faf4d11095086d1b7ed9ab27ab52bd6c7%2FScreenshot%202026-09-26%20174858.png?generation=1790425153277741&alt=media)

when i click 'submit', submission fails instantly sue to system error


> **** (2026-09-26 13:43, 0 votes)
> Has this submission run successfully in the past? I'm seeing `Did not find output file 'submission.zip' in the submitted Notebook.`


> > **** (2026-09-28 11:11, 1 votes)
> > if i 'save version', successfully run the notebook and then 'submit', then the submission is scored 
> > 
> > but if i click 'submit' b4 saving the notebook, it fails


> > **** (2026-09-28 13:12, 2 votes)
> > I think this is WAI. Your notebook needs to generate a submission file (`submission.zip`) before that submission can be scored. The workflow seems a little confusing, though. I will give feedback to the team.


**** (2026-11-06 12:09, 0 votes)
Hi @ryanholbrook, submission 58049571 (Nov 6, 07:10 UTC) completed with a public score of 0.00 and no error message after ~5 h. It is byte-identical (same SHA-256) to submission 58012317, which scored 0.17 the day before. Could you check whether this run hit a scorer or inference-server failure, and rerun it if so? Thank you.


**** (2026-11-02 13:17, 0 votes)
Hi @ryanholbrook,

My first Gemma 4 Developer Agent submission has remained at **"Notebook Running" for approximately 17 hours**, without a public score or error message.

The saved notebook (Version 1) completed successfully in 19 seconds and generated the expected `submission.zip`.

Notebook:
https://www.kaggle.com/code/matthewestevenson/gemma-4-v10-final-submission?scriptVersionId=364641369

Could you check whether the competition evaluation is queued, actively running, or encountering a scorer-side problem?

I'd prefer not to cancel or resubmit without understanding what's happening.

Thanks!


**** (2026-10-22 06:54, 0 votes)
Hello organizers,

Could you check the first exception and failure stage for submission **57505903**?

- Submitted: **2026-10-22 02:18:29 UTC**. Observed terminal by **06:27:16 UTC**, under 4h09m including queue time.
- UI: **Notebook Threw Exception**, no public score. API: COMPLETE, empty score, generic unhandled-error description.
- Bundle SHA256: `7981d72240c6ebb68296c32e97751909e771e1de184b7a8bf40521b59b4522d8`.
- Three files only: `agent.yaml`, `eval_config.yaml`, `prompts/system.md`; no LoRA or custom Python/Skill files.
- 31B QAT; 8 minutes, 28 tools, 80 turns, 300-second command timeout. Temperature 0.2, top_p 0.95, output 8192, thinking 4096.
- The same frozen configuration completed our public-task development run. Our earlier B18 submission **57464586** scored **0.18** with 6 minutes and a shorter prompt; model/sampling/tool settings were the same. This is not a byte-identical comparison.

Please confirm whether the failure occurred during model startup, agent compilation/config loading, task execution, or scoring, and share the exception type and first relevant stack frames if possible. If it was an infrastructure failure, could the original submission be rerun without modifying the bundle?

We have not resubmitted and are preserving the original files. Thank you.


**** (2026-10-21 16:44, 0 votes)
Hi @ryanholbrook, submission 57480561 (Oct 21, 11:57 UTC) failed with "Notebook Threw Exception", no score. 31B, no LoRA, validates and runs locally. Looks like the same ServerStartupError issue from today. Could you check and rerun? Thanks!


**** (2026-10-20 19:47, 0 votes)
Hello Kaggle team,

I would appreciate some clarification regarding submission failures in the Gemma 4 Developer Agent Competition.

I have submitted two versions of my agent:

* Candidate 1: Failed with a Kaggle Error.
* Candidate 3: Failed with a Notebook Timeout after an extended evaluation period.

Candidate 3 uses the officially supported Gemma 4 31B quantized model and the declarative agent configuration.

I understand from other discussions that there have been infrastructure issues involving GPU availability and submission evaluation.

Could you please clarify:

1. Whether these failures might be related to the reported infrastructure problems.
2. Whether affected submissions will be automatically rerun.
3. Whether the Notebook Timeout indicates that my agent exceeded its execution budget or that the evaluation notebook exceeded its overall runtime limit.
4. How participants can distinguish infrastructure failures from problems in their own agents.

I have invested substantial effort in developing and testing this agent, but I have not yet been able to obtain a single leaderboard score.

Without reliable evaluation feedback, it is difficult to determine whether changes improve the agent or even whether a submission is functioning correctly.

I appreciate the work involved in running this competition and would be grateful for guidance on how to proceed.

Thank you.


**** (2026-10-13 03:16, 0 votes)
Hi Kaggle team,

I'm experiencing repeated "Kaggle Error" failures when submitting to the Gemma 4 Developer Agent Competition.

**Notebook:** https://www.kaggle.com/code/dongfangdaguo/notebook4dac4495b7

**Failed submissions:**
- Version 3: Two failures
- Version 6: One failure

The notebook itself runs successfully. Version 6 completed in 23.4 seconds using 4×L4 GPUs with Internet disabled.

The output file `submission.zip` was generated successfully (7,981 bytes). I also verified that all six files match my original submission and that the Agent configuration passes the official compiler.

However, the competition submissions return "Kaggle Error" without a detailed explanation.

Could you please check the evaluation backend logs and clarify whether this is an infrastructure issue or a problem with my submission configuration?

If these submissions were affected by the reported infrastructure issues, would they be eligible for re-evaluation?

Thank you very much for your help!


**** (2026-10-12 22:11, 0 votes)
Hi @ryanholbrook, could you please check the pending submission for account tominister? It was uploaded on October 12, 2026 at 05:32:37 UTC (submission.zip) and has shown "Notebook Running" / "Scoring..." for about 17 hours, with no score or error visible. Could you confirm whether it is waiting for L4x4 resources, actively evaluating, or stalled? I have not canceled or resubmitted it. Please preserve the existing scored submissions. Thank you.


**** (2026-10-10 04:49, 0 votes)
Hi @ryanholbrook, is the L4×4 queueing issue resolved, and has rescoring resumed? My `baseline-v1` submission has been showing “Notebook Running” for several hours, although the notebook version completed successfully. Could you clarify whether submissions currently in this state will be rerun automatically? Thanks!


**** (2026-10-10 04:13, 0 votes)
Hi Kaggle team,

My submission to the Gemma 4 Developer Agent competition has been stuck at “Scoring” since yesterday.

Could you please check whether the evaluation is progressing normally or has become stuck in the scoring queue?

I have not resubmitted, and I would appreciate guidance on whether I should continue waiting or take any action.

Thank you.


**** (2026-10-09 09:27, 0 votes)
Hi Ryan,

My submission “Gemma 4 Agent: Budget-Fit Single Agent - Version 1”
has remained in “Notebook Running” status for over 24 hours.

The notebook version completed successfully and generated submission.zip
before I submitted it. Could you please check whether this submission is
stuck in the L4x4 queue or affected by the recent GPU outage?

Thank you.


**** (2026-10-08 21:32, 0 votes)
One more failed submission: 

  id 56926568
  submitted 2026-10-08 00:43 UTC
  "A system error. Please try resubmitting to resolve the error and contact
   Kaggle Support if it persists."

Could this one be rerun too? Happy to resubmit instead if that's simpler. Thanks!


**** (2026-10-08 20:23, 0 votes)
Hi @ryanholbrook, our two submissions ended in ERROR with "A system error. Please try resubmitting...": 56905816 (Oct 7, 08:40 UTC) and 56925222 (Oct 8, 00:05 UTC). Both are the same bundle (agent.yaml, one prompt, sampling.yaml, eval_config.yaml + one rank-16 LoRA adapter), validated with adk-submission 0.2.12 and run end-to-end in our 4xL4 notebook with the official Evaluator. A bundle of the same structure (56840627, Oct 5) scored normally. Could you include them in the rerun or restore the slots? Thanks!


**** (2026-10-08 20:17, 0 votes)
Hi @ryanholbrook, our submission 56894410 (Oct 7, 00:06 UTC) ended in ERROR with “A system error. Please try resubmitting…” — same pattern as #746480 (long run, then Kaggle Error). Could you check whether this was an infrastructure failure and rerun it? Thanks!


**** (2026-10-08 19:15, 0 votes)
Hi, our submission 56903298 (Oct 7, 07:02 UTC) ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists.", the same message as many reports in this thread. It is a config-only bundle (agent.yaml, sub-agent yaml, prompts, sampling and eval_config files; no adapters or skills) that validated with the current wheelhouse (adk-submission 0.2.12), and a bundle of the same structure (submission 56865276, Oct 6) scored normally. Could you include 56903298 in the rerun or restore the daily slot? Thank you!


**** (2026-10-08 18:33, 0 votes)
Hi @ryanholbrook, two of our submissions ended in ERROR with "A system error. Please try resubmitting…" after ~15 h, the same pattern as #746480:
  - 56894391 (Oct 7, 00:06 UTC)
 - 56925242 (Oct 8, 00:05 UTC)
  
Both are config-only bundles (no adapters, no skills) with a 5-minute task cap. They compile with adk-submission 0.2.12 and run end to end in our 4×L4 notebook with the official Evaluator (~2.8 min per task). Our Oct 6 submission 56864745 with the same structure scored normally. Could you include them in the rerun or restore the slots? Thanks!


**** (2026-10-08 18:24, 0 votes)
Hi @ryanholbrook ,

My submission 56925555 (Oct 8, 00:10 UTC) ended in ERROR with “A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists.” It is the same bundle as my earlier submissions that scored normally, with only a minor eval_config.yaml change (no adapters, no prompt or other changes). This time it stayed in running status much longer than before and then failed with the error above, which looks like the same pattern as #746480.
Could you check whether 56925555 was an infrastructure failure? If so, could you either rerun it or restore the submission slot? Thanks!


**** (2026-10-08 17:22, 0 votes)
On my 3rd retry can we have better logging for errors?


**** (2026-10-08 17:19, 0 votes)
TBH, a rerun will not do much good for any of us. What we really need is - an extra slot to submit a new one. Submissions allow us to test and validate theories and if it is re-run and arrives past 00 UTC (which is in 4.5 hours) today it is useless.


**** (2026-10-08 17:07, 0 votes)
- 56894115 (Oct 7, 00:03 UTC)
- 56923090 (Oct 7, 22:33 UTC)

These were both also hit by the ominous system error.
If they could be rerun, that would be splendid! Thanks a lot! :)


**** (2026-10-08 16:24, 0 votes)
Hi @ryanholbrook, my submission 56916320 ended in ERROR after about 15 hours with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists." It was still pending at Oct 8 07:14 UTC and showed the error by 07:49 UTC. This looks like the same pattern as #746480 and the other reports here. A near-identical bundle with the same limits (56883929, submitted Oct 6) completed and scored normally. Could you please trigger a re-run? Thanks!


**** (2026-10-08 16:17, 0 votes)
Hi @ryanholbrook,

Our subsequent submission 56926922 (submitted Oct 8, 00:56 UTC) also ended in ERROR with the identical "A system error" message after running for 15 hours. 

Could you please include both 56915113 and 56926922 in the queue for official reruns when the cluster backlog clears? Thank you!


**** (2026-10-08 15:45, 0 votes)
can someone help regarding this issue!!! (kaggle error).


**** (2026-10-08 15:32, 0 votes)
Hi @ryanholbrook, our submissions 56905045 (Oct 7, 08:08 UTC) and 56924740 (Oct 8, 00:01 UTC) both ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists." after about 15 hours, the same pattern as #746480. Could you include them in the rerun? Thanks!


**** (2026-10-08 15:24, 0 votes)
Hi @ryanholbrook, our submission 56925045 (Oct 8, 00:03 UTC) ended in ERROR with no score or error description. It is a config-only bundle (agent.yaml, one prompt, sampling.yaml, eval_config.yaml; no adapters, skills, or scripts) with 8 min/task and 28 tool calls, byte-identical to the public "Budget-Fit Single Agent" notebook, which other teams have scored normally, so it looks like the same infrastructure pattern as #746480. Could you check it and include it in the rerun? Thank you!


**** (2026-10-08 14:28, 0 votes)
Hi @ryanholbrook, our submission 56885293 (Oct 6, 16:03 UTC) also ended in ERROR with "A system error. Please try resubmitting..." after a long run, same pattern as #746480. It's a plain YAML/prompt bundle (nHi @ryanholbrook, our submission 56885293 (Oct 6, 16:03 UTC) also ended in ERROR with "A system error. Please try resubmitting..." after a long run, same pattern as #746480. It's a plain YAML/prompt bundle (no adapters) with a 5 min/task cap; a sibling bundle with the same budget scored normally on Oct 5 (56836396). Could you include it in the rerun? Thanks!o adapters) with a 5 min/task cap; a sibling bundle with the same budget scored normally on Oct 5 (56836396). Could you include it in the rerun? Thanks!


**** (2026-10-08 13:23, 0 votes)
@ryanholbrook we're seeing this too, and it looks independent of the per-task budget. Two submissions ended in SubmissionStatus.ERROR with no score, both exactly ~15 h 11 min after submitting:

- 56895618 (2026-10-07 00:44 UTC): max_time_minutes 5, ~120 tasks
- 56915584 (2026-10-07 15:59 UTC): max_time_minutes 3, otherwise identical

The 3-minute config can't reach 12 h of agent time on ~120 tasks, yet it failed at the same point. Both were single-agent configs with no adapters, and both passed validate_directory, validate_single_declared_model and compile_submission locally. The packaging notebooks completed normally.

Could you kindly check what was raised and whether these can be rerun? Thanks!


**** (2026-10-08 13:15, 0 votes)
Hi @ryanholbrook, two of our submissions ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists.":

56891945: submitted Oct 6, 22:17 UTC; error after about 15 h.
Identical resubmission: submitted Oct 7, 15:18 UTC, description "C01 v2 identical retry of 56891945; archive d55dbf62 unchanged". It ended in the same error.
Both use the same notebook version and byte-identical submission.zip: a config-only bundle (agent.yaml, one prompt, sampling.yaml, eval_config.yaml; no adapters or skills) with a 4.5 min/task cap that passes the official submission check. This looks like the same pattern as #746480. Could you include both in the rerun, or restore the slots? Thanks!


**** (2026-10-08 12:32, 0 votes)
Like others here, my last 2 submission attempts ran for many hours each and then failed with "Kaggle Error A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists. See more debugging tips".  How do I report this issue and get it rectified?


> **** (2026-10-08 12:39, 0 votes)
> Hello, I'm new here not sure what to do, if it says "Kaggle Error A system error" this means it is their server error and not error from my config files right? 😀


> > **** (2026-10-08 14:05, 0 votes)
> > Yes, I guess that's what it means. Kaggle isn't specific about the cause. A lot of people here are experiencing the same problem and no one has responded to any of our posts yet, as far as I can tell.


**** (2026-10-08 12:21, 0 votes)
Hi @ryanholbrook,

Our submission 56915113 (submitted Oct 7, 15:40 UTC) ended in ERROR with:
"A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists."

It was running for ~15 hours before failing with this platform error. It is a config/prompt bundle with calibrated budgets (3.5m/task, 20 turns, 84-entry Knowledge Base). 

Could you please trigger a rerun for 56915113 when the cluster queue permits?

Thank you!


**** (2026-10-08 11:35, 0 votes)
Hi @ryanholbrook, two of my submissions ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists.": 56899321 (Oct 7, 03:49 UTC) and 56919655 (Oct 7, 19:04 UTC). Both are config-only bundles (YAML + prompts, no adapters or skills) that compile with the current wheelhouse, with 8- and 7-minute caps. My previous submission (56869867, Oct 6) scored normally. Could you include them in the rerun? 
Thanks!


**** (2026-10-08 11:18, 0 votes)
Dear @ryanholbrook 

Our submission 56911218 (Oct 7, 12:51 UTC) ended in ERROR:
"A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists."

It failed after a long run, the same pattern described in #746480. The identical zip ran end to end in our own Kaggle notebook earlier that day on 4×L4, using the current wheelhouse. Our previous submission (56586418, Sep 26) scored normally.

So this doesn't look specific to our configuration. Could you include 56911218 in the rerun, or restore the slot? Happy to provide anything else that helps.

Thanks,
Shehab


**** (2026-10-08 09:13, 0 votes)
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F37170011%2Ff9e66b5b8484be3e55b7ece9c53a8d06%2F2026-10-08-160848_hyprshot.png?generation=1791450580293661&alt=media)

I see so many people got system error from submission, this is normal right? This is my first submission.

I kinda confuse a bit I waited for 15 hours and just got a system error this means that the 15 hours I wait is waiting for my queue? If that so then the timer waiting is like 15hours + 12-14 hours eval?


**** (2026-10-08 08:59, 0 votes)
Hi @ryanholbrook, two of my submissions failed on the platform side and are unscored:
- **56563523** (Sep 26, 00:02 UTC): "Your notebook has requested more CPU, GPU or TPU resources than are available."
- **56894331** (Oct 7, 00:05 UTC): "A system error…" after ~15 h, same pattern as #746480.

Could you please re-run those when possible? Thanks!


**** (2026-10-08 04:03, 0 votes)
@ryanholbrook 56895692 failed with the generic system error after running most of a day on Oct 7, so it looks like the same outage. It's a prompt config plus one small LoRA adapter (rank 16), and a 5-minute cap per task. A rerun would be appreciated, thank you.


**** (2026-10-08 03:41, 0 votes)
Hi @ryanholbrook, our submission 56907430 (Oct 7, 09:52 UTC) ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists." after a long run, the same pattern as #746480. Could you please check it and include it in the rerun? Thanks!


**** (2026-10-08 03:38, 0 votes)
Hi @ryanholbrook,

Our submission 56909375 (Oct 7, 11:26 UTC) ended in ERROR with error_description: "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists." It ran for roughly 13 hours before failing.

A structurally identical bundle submitted the previous day scored normally (56893219, Oct 6, 23:43 UTC), so this does not look configuration-specific on our side.

Could you check whether this was an infrastructure failure and, if so, include it in the rerun or restore the slot? Happy to provide anything else useful.

Thanks!


**** (2026-10-08 01:28, 0 votes)
Hi @ryanholbrook, our submissions 56885498 (Oct 6, 16:12 UTC) and 56904324 (Oct 7, 07:40 UTC) both ended in ERROR with "A system error. Please try resubmitting..." after long runs, the same pattern as #746480. Both are YAML/prompt + skill-script bundles (no adapters) with 7 and 5 min/task caps; a near-identical bundle (56852251, 7 min/task) scored normally on Oct 5. Could you include them in the rerun? Thanks!


**** (2026-10-08 01:17, 0 votes)
Mine also Ryan, Kaggle Error


**** (2026-10-08 01:10, 0 votes)
Hi @ryanholbrook, submission 56906906, uploaded on Oct 7 at 09:28 UTC, ended with “Kaggle Error — A system error.”
It was last observed running at Oct 7, 21:31 UTC, and was observed in ERROR at Oct 8, 00:32 UTC. We cannot see the actual execution duration or logs.
The submission contains YAML/prompt files only, no adapters, with `max_time_minutes: 8` and `max_tool_calls: 28`.
Could you confirm whether it hit the global execution limit or failed because of a platform issue? If it was a platform issue, could it be included in a rerun?
We have not resubmitted or changed the configuration. Thanks!


**** (2026-10-08 00:44, 0 votes)
hi @ryanholbrook my submission failed with kaggle error - pls could you help Kaggle Error
A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists. See more debugging tips


**** (2026-10-07 23:12, 0 votes)
Hi @ryanholbrook , our submission 56895295 (Oct 7, 00:29 UTC) ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists." after running for 14+ hours. Our three earlier submissions of the same base config scored normally. Could you check whether this was an infrastructure failure and, if so, include it in the rerun? Thanks!


**** (2026-10-07 22:50, 0 votes)
Hi @ryanholbrook, our submission 56897260 (Oct 7, 02:04 UTC) also ended in ERROR ("A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists.") after ~15 h, the same pattern as #746480. The bundle is a config + LoRA adapter (the same adapter scored fine in 56809291 and 56865046) with a 5.0 min/task cap and was validated locally. Could you check whether it was an infrastructure failure and rerun it if so? Thanks!


**** (2026-10-07 22:18, 0 votes)
Hi @ryanholbrook, our submission 56897266 (Oct 7, 02:04 UTC) also ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists." after ~17 h, same pattern as #746480. It is a YAML/prompt bundle with one skill folder (no adapters) and a 4.0 min/task cap; a near-identical bundle (56864509) scored normally on Oct 6. Could you include it in the rerun? Thanks!


**** (2026-10-07 21:59, 0 votes)
Hi @ryanholbrook, my submission from notebook018cfcfea5 – Version 2 (scriptVersionId 355897623, submitted Oct 7 ~00:00 UTC, config-only YAML/prompt bundle, no adapters, 8 min/task) has been in "Notebook Running" for over 24 hours. Same pattern as 
#746480. Version 1 of the same notebook scored normally (0.15) on Oct 6. Could you check it and include it in the rerun? Thanks!


**** (2026-10-07 20:31, 0 votes)
hi @ryanholbrook can you help me - my submission is runnng for 15 hours now with no updates - is it expected? i thought the cutoff was 12 hours


**** (2026-10-07 20:30, 0 votes)
Hi @ryanholbrook , our submission from Oct 7, 00:24 UTC (description: "v15 retry (identical bundle, 2nd attempt)") ended with "Kaggle Error: A system error. Please try resubmitting..." after a long run. The same bundle succeeded on Oct 6 (score 0.13), and it uses a 6.25 min/task cap with no adapters. It looks like the same infrastructure issue reported in #746480. Could you rerun it? Thanks!


**** (2026-10-07 19:11, 0 votes)
Hi @ryanholbrook 
My submission 56899321 (Oct 7, 03:49 UTC) also ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists." after a long run. Its a config-only bundle (YAML + prompts, no adapters or skills) that validates with the current wheelhouse, and a submission with the same budget (56869867) scored normally on Oct 6. Could you include it in the rerun? 
Thanks!!!!


**** (2026-10-07 18:57, 0 votes)
Hi @ryanholbrook, two of our submissions ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists.":

56862128 (Oct 5, 21:27 UTC)
56892091 (Oct 6, 22:27 UTC)

Both are config-only bundles (agent.yaml, one prompt, sampling.yaml, eval_config.yaml; no adapters or skills) with 4.5- and 4.0-minute per-task caps, validated with the current wheelhouse. Our three earlier submissions with the same structure scored normally. This looks like the same pattern as #746480. Could you check whether these were infrastructure failures and, if so, rerun them or restore the slots? 

Thanks!


**** (2026-10-07 16:59, 0 votes)
Hi @ryanholbrook ok brook, our submission 56887814 (Oct 6, 18:03 UTC) ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists." It was still running at 14 h and fits the pattern in #746480. It's a YAML/prompt bundle with no adapters. Could you check whether it was an infrastructure failure and include it in the rerun? Thanks!


**** (2026-10-07 16:27, 0 votes)
Hi @ryanholbrook, my submission 56887319 (Oct 6, 17:39 UTC) also ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists." Same pattern as #746480. The bundle is a plain YAML config with no adapters and a 5 min/task cap; a nearly identical bundle (two-line prompt/config difference) scored normally on Oct 4 (56829521). Could you include it in the rerun? Thanks!


**** (2026-10-07 15:51, 0 votes)
Hi @ryanholbrook, our submission 56890105 (Oct 6, 20:15 UTC) also ended in ERROR with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists." Same pattern as #746480. Could you include it in the rerun? Thanks!


**** (2026-10-07 14:17, 0 votes)
Hi @ryanholbrook , my submission from Oct 6, 17:19 UTC ended in ERROR with "A system error. Please try resubmitting". Could you include it in the rerun? Thanks


> **** (2026-10-07 14:35, 0 votes)
> same as mine


**** (2026-10-07 07:48, 0 votes)
Hi Ryan, my submission 56885686 (Oct 6, 16:21 UTC) ended in ERROR with no error description. Could you check whether it was an infra failure or the 12h limit? If it was on your side, a rerun would be great. The same config scores locally without issues, and our previous submission 56828862 completed fine.


**** (2026-10-06 05:16, 0 votes)
Does server-side scoring of an uploaded agent submission.zip consume the submitting account's weekly GPU quota? Is the documented 2x quota multiplier specific to personal L4x4 notebook sessions, or does it also apply to hosted ZIP scoring?

I am asking about the official hosted evaluator after a file submission, rather than the personal notebook that constructs the ZIP. A clarification would help plan a bounded compute budget.


**** (2026-09-28 11:26, 0 votes)
it toke more than 11 hours and not finished yet what I should do


**** (2026-09-27 19:02, 0 votes)
Still same issue on my side @ryanholbrook ![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F9882418%2F7d651a3e62c6943dbd9a1cb31b1aec52%2Ferror_gemma4_competition.png?generation=1790535767374553&alt=media)


**** (2026-09-27 15:32, 0 votes)
how long does it take to score a submission? mine is running for more than 1h.


> **** (2026-09-27 16:53, 0 votes)
> Few hours is expected


> **** (2026-09-28 07:26, 0 votes)
> It takes approximately 12 hours


> > **** (2026-09-28 08:45, 1 votes)
> > timeout after 14 hours in my case :(


**** (2026-09-26 17:32, 0 votes)
Hi, thank you for looking into it. Lost a couple hours debugging yesterday trying to find the issue, but noticed that it happens even when I try to upload the fastest model possible. Will retry in a few hours when I get my daily submission back.


**** (2026-09-26 12:53, 0 votes)
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F30803717%2F0d43261c041e94faa9cbd3864c6f4373%2FScreenshot%202026-09-26%20155232.png?generation=1790427179329130&alt=media)


---

## Public code: configs, trajectories and analysis scripts for a Gemma 4 E2B agent failure study
/competitions/gemma-4-developer-agent/discussion/756433 | by  | posted 2026-11-06 08:38 | last comment 2026-11-06 08:38 | 0 comments | 2 votes


**** (2026-11-06 08:38, 2 votes)
Sharing publicly, per the competition's code-sharing rule, the code behind our Paper Track writeup **Finds the File, Cannot Change It: Why a 2B Coding Agent Fails**.

Repo (Apache-2.0): https://github.com/sigongjoa/gemma4-e2b-edit-failure

- ADK agent configs A–K for Gemma 4 E2B: recovery instructions, rules distilled from `rich` review comments, tool removal, reasoning/temperature changes, an editor sub-agent
- Trajectories, patches and logs of every local run (task problem statements removed; no competition data included)
- Scripts that measure where the agent fails (read the right file / edit it / edit accepted), repeated vs distinct `edit_file` failures, and a replay of edit calls on snapshots

Main finding: E2B usually reads the right file, but about three quarters of failed `edit_file` calls repeat an earlier failed call verbatim, and most distinct failures put intended or absent code into `old_string` rather than miscopying. None of the harness changes we tried resolved a task.

Writeup: https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/writeups/finds-the-file-cannot-change-it-why-a-2b-coding


---

## Audit: 61 of 129 public tasks can't tell agents apart (+ open configs and data)
/competitions/gemma-4-developer-agent/discussion/756400 | by  | posted 2026-11-06 05:49 | last comment 2026-11-06 05:49 | 0 comments | 1 votes


**** (2026-11-06 05:49, 1 votes)
Before measuring agents, I measured the public benchmark. Here are the results, with all code and data open, in line with the competition's public-sharing rule.

Repo: https://github.com/TechNaom/gemma4-agentic-swe (Apache-2.0)

1. Only 68 of 129 public tasks are valid locally

I ran every public task through the official harness twice: once with its reference (gold) patch, which should pass, and once with an empty patch, which should fail. A task can separate a good agent from a bad one only if both hold.

Repo	Tasks	Gold passes	Empty passes	Valid
fastapi	67	31	2	29
rich	48	39	0	39
requests	13	3	3	0
httpx	1	0	0	0
Total	129	73	5	68
34 gold failures come from two test libraries missing from the provided wheels: inline_snapshot (27 tasks) and dirty_equals (7 tasks).
13 tasks fail even with the reference fix, 7 time out and 2 fail for other reasons.
5 tasks pass with no patch at all.

Practical tip: if you tune on the public tasks, use only the 68 valid ones (listed in experiments/valid_tasks.txt). Otherwise part of your local score is noise. I don't know whether the hidden environment has the same gaps.

2. The tests accept some broken fixes

I planted 163 known bugs into the gold patches, using 7 mutation types, and re-scored every one with the official harness. After a hand review that removed equivalent mutants, 24 of 163 broken fixes (14.7%) were still marked resolved.

Inverted booleans escaped most often (53% before review), then off-by-one errors (33%).
Removed raise statements were always caught.

So any resolve rate is an upper bound on truly correct fixes.

3. Code-graph tools did not help our agent

Results on the 68 valid tasks, with gemma-4-31b-it-qat-w4a16-ct on 4x L4:

Agent	Tools	Resolved
k0	6 workspace tools only	50% (34/68)
k4	k0 + all three graph tools	47% (32/68), McNemar p = 0.69
n4	k4 + a prompt nudging graph-tool use	44% (14/32)

The agent called a graph tool in fewer than 10% of runs unless told to. Nudging it raised usage but cost more tokens and delayed the first edit, without solving more tasks.

4. A warning: public-set results did not transfer
Our 50% public-set agent timed out on the hidden set at 15 minutes per task (the limit is 12 hours in total).
With a 5-minute cap and thinking off, it scored only 0.05 on the public leaderboard.

The hidden tasks come from private repositories and behave very differently from the public ones, so don't rely on public-set tuning alone. We are now testing the same agent with thinking turned on and will post the result here.

What's in the repo
agents/: all 11 agent configs (k0 to k5, n1 to n5)
experiments/audit-2026-10-15/: the full gold/empty audit
experiments/faults-2026-10-23/: the planted-bug set and its hand review
experiments/g4swe-*: every run summary, trace and patch
src/g4swe/: the runner, including a CPU-only patch mode that re-verifies saved patches without a GPU
submission/main-k0/: our exact submitted config

The full write-up is on the Paper Track. Questions and corrections are welcome, especially if your audit results differ from ours.


---

## swegemma, which is built on Google’s ADK
/competitions/gemma-4-developer-agent/discussion/756336 | by  | posted 2026-11-06 00:40 | last comment 2026-11-06 00:40 | 0 comments | -2 votes


**** (2026-11-06 00:40, -2 votes)
harness summarize the conversation mid-task. It kicks in at 14,336 tokens, keeps only the last 5 events, and replaces the rest with its own generic summary. Every context reset in our cycle 2 logs came from this, never from our design.
Some of its nudges work against good reasoning. After a cut-off turn it tells the model to “keep reasoning under a few sentences”.
It can’t be overridden. Our submission can’t add code hooks, change the summarizing, or end a round from a tool.
Its task message conflicts with multi-round designs. It says a text reply terminates the session.


---

## Community resource: pytest-verified context-selection harness + gemma4-locbench-v1 (probe set)
/competitions/gemma-4-developer-agent/discussion/756315 | by  | posted 2026-11-05 23:34 | last comment 2026-11-05 23:34 | 0 comments | 0 votes


**** (2026-11-05 23:34, 0 votes)
While preparing our paper-track writeup we built a reusable harness for comparing context-selection strategies on the public training tasks under identical character budgets, with the competition's own pytest verification (patches applied with git apply; tests from each task's test_patch; offline wheelhouse deps).

What's inside (public notebook: https://www.kaggle.com/code/krisshah123/gemma4-context-selection-harness-locbench-v1)

- Strategies: graph-guided AST call-graph traversal, embedding retrieval (offline bag-of-terms query - the same semantics as the sandbox's search_similar_code lexical fallback), hybrid, oracle upper bound, plus random/empty-context floors.
- gemma4-locbench-v1: per-task gold files / module paths / hunk symbols derived from the 129 reference patches - score ANY context selector without running a model.
- Paired statistics built in (exact McNemar + Wilson 95% CIs) so comparisons are defensible.

Adopt in 3 minutes: attach the competition dataset + wheelhouse, run the cells top-to-bottom, then swap --strategy to benchmark your own selector under identical budgets. Localization-only scoring needs no GPU at all.

A controlled, budget-matched structure-vs-similarity comparison in the small-model regime is coming as a paper-track writeup. Corrections, requests and critique welcome - if the harness is missing something your agent needs, we would rather fix it now.


---

## Tool-call serialization issue: edit_file repeatedly emitted without old_string
/competitions/gemma-4-developer-agent/discussion/756051 | by  | posted 2026-11-05 07:46 | last comment 2026-11-05 07:46 | 0 comments | 0 votes


**** (2026-11-05 07:46, 0 votes)
## Summary

While running a Gemma 4 agent on the official Kaggle evaluation harness (`swegemma 0.2.11`), we observed a repeated tool-call serialization failure on `edit_file`:

- In one run, **51 consecutive `edit_file` calls** were emitted without the mandatory `old_string` argument.
- **38 of the 51 complete argument objects were byte-for-byte identical** (ignoring key order); the remaining 13 were two variants that differed only in the value of an extra pseudo-key.
- The failure signature was identical in **51/51 calls**: `old_string` absent, and the `new_string` value ended with the literal characters `` `,old_string: `` (backtick, comma, key name).
- For **34 consecutive turns**, the assistant's message was also byte-identical (`"I'll try to use edit_file with the arguments as a JSON object.\n\nWait, I'll try to use the tool call again."`), and the arguments were identical as well.
- The model did **not** lack the correct values: in the same run it wrote a correct three-key JSON object in its reasoning text (copied from the prompt example), and in another step spelled out the correct `old_string` / `new_string` values in prose. The very next calls were still malformed. We describe this as "knowing ≠ emitting".

We are not certain whether this is an organizer/serialization defect or expected model behavior under the function-calling format. We are reporting it as a possible issue and would like to know whether it is known.

## Environment

| Item | Value |
|---|---|
| Model | `gemma-4-31b-it-qat-w4a16-ct` (31B QAT) |
| Harness | `swegemma 0.2.11` (`9ad87658…`) |
| Runtime stack | `adk_eval_core 0.1.0` · `adk_submission 0.2.13` · `google_adk 1.36.1` |
| Platform | Official Kaggle BYOD image `gcr.io/kaggle-private-byod/python@sha256:37c64f7d…`, 4× L4, network disabled |
| Generation config | temperature 0.2, max_output_tokens 8192 |
| Turn budget | `max_turns = 60` (this run terminated with `exceeded_turns_budget`) |

## Minimal evidence (single run, single task)

The malformed argument object had this shape (values abbreviated; no task code included):

```json
{
  "filepath": "<target source file>",
  "new_string": "<a plausible replacement block, 130 chars>\n`,old_string:",
  "class EndpointContext(TypedDict, total=False)": "`"
}
```

Notes:

- `old_string` is absent.
- `new_string` ends with the literal string `` `,old_string: `` — i.e. the next key name appears to have been swallowed into the previous value, including a stray backtick.
- A third key exists whose **name is a line of source code** (`class EndpointContext(TypedDict, total=False)`), with value `` "`" `` (in 46 calls) or `""` (in 5 calls). This looks like a parsing/serialization artifact rather than model-intended content.
- In 38 of the calls the value of `new_string` contained the two characters `\n` as literals (not a newline escape); in the other 13 it was a real newline.

The harness error text was constant:

```
Invoking edit_file() failed as the following mandatory input parameters are not present: old_string
… You could retry calling this tool …
```

## Cross-run observations (described, not causal)

Across five independent runs on the same task (different prompt variants, one run per arm), `edit_file` failures showed the same "missing `old_string` + backtick tail" signature, with varying repetition lengths:

| Run | edit_file calls | failures | distinct complete objects | longest identical streak |
|---|---:|---:|---:|---:|
| A | 21 | 17 | 1 | 17 |
| B | 23 | 14 | 2 | 12 |
| C | 30 | 19 | 4 | 13 |
| D | 16 | 13 | 4 | 6 |
| E (reported above) | 51 | 51 | 4 key-order variants (38 identical ignoring order) | 38 |

In run A the same failure shape occurred after four successful edits, so it is not limited to the first call. In runs B and C the same task recovered by later successful `edit_file` calls; runs D/E did not.

Two runs (B and C in the table) used the **same instruction byte-for-byte**; in one the first edit succeeded, in the other it failed. We therefore do not attribute the first occurrence to the prompt text. What distinguishes run E is the length of the non-recovering loop and the pseudo-key in 51/51 calls.

## Questions

1. **Is this a known issue** in the tool-call organizer / function-calling serialization for this model? Specifically: a key name being emitted as a value or vice versa, and the next argument key being appended to the previous string value.
2. If useful, **we can provide the full ATIF traces** (per-step messages and parsed arguments) for the runs above. What is the preferred format and transfer method? We can also provide the exact harness version and image digest.
3. Is there a **recommended harness-side workaround** (e.g. validating/regenerating tool-call arguments, or a different tool-call representation) that we could test in our evaluation setup?
4. If this is expected behavior rather than a bug, any pointer to documentation or known limitations would be helpful so we can stop pursuing it.

## Scope and limitations

- One model configuration, one task, single run per prompt variant; no repeated sampling within an arm.
- Traces contain the harness-parsed argument objects, not the raw token stream. "Byte-identical" refers to the parsed objects seen by the harness agent loop.
- Task identifiers and full file contents are withheld from this post; they can be shared privately if needed.
- We are reporting an observation and asking for status, not asserting a root cause.


---

## Stuck pending / Notebook Timeout on g4da-submit-v2 — no Public Score, cannot resubmit
/competitions/gemma-4-developer-agent/discussion/756044 | by  | posted 2026-11-05 07:01 | last comment 2026-11-05 07:01 | 0 comments | 0 votes


**** (2026-11-05 07:01, 0 votes)
Hi everyone,

Has anyone else hit a long-stuck competition submission that never gets a Public Score?

For team **dxnnnnn** on **gemma-4-developer-agent**:
- Multiple **g4da-submit-v2 Version 2** attempts end as **Notebook Timeout** (including a recent ~18h run) with **no Public Score**.
- While one row was stuck as pending/Running earlier, **Submit Prediction** was blocked with: “Cannot submit. Your team already has 1 pending submissions; please wait for one to finish scoring.”
- The notebook/kernel itself completed successfully with **submission.zip** in Output, so this looks more like a scoring/queue handoff issue than a local notebook failure.
- We also opened Support ticket **271265** and shared screenshots.

Questions:
1. Is anyone else seeing Timeout / endless pending with no score on this competition?
2. Any workaround that cleared the pending slot without waiting for Support?

Thanks.


---

## The queue time should improve once the ARC-2 backlogs are cleared
/competitions/gemma-4-developer-agent/discussion/755527 | by  | posted 2026-11-03 21:14 | last comment 2026-11-04 20:05 | 2 comments | 1 votes


**** (2026-11-04 02:56, 1 votes)
I just started an e4b submission. will update on the queuee situation once it finishes


> **** (2026-11-04 20:05, 0 votes)
> I might be wrong :(


**** (2026-11-03 21:14, 1 votes)
Just in case you are wondering why the submissions are taking 30+ hours.


---

## Sending public tasks to a hosted model provider: how should the Competition Data rule be read?
/competitions/gemma-4-developer-agent/discussion/755542 | by  | posted 2026-11-03 21:46 | last comment 2026-11-04 09:20 | 1 comments | 1 votes


**** (2026-11-03 21:46, 1 votes)
Hello @ryanholbrook and the Kaggle team,

I would like a clear reading of the rules on one point, because several things seem to point in different directions.

- Section 4 says participants agree "not to transmit, duplicate, publish, redistribute or otherwise provide or make available the Competition Data to any party not participating in the Competition".
- Section 6 and the staff answer in discussion 742807 allow external models used in line with their license terms, but they do not say whether Competition Data may be sent to those models.
- Some participants have reported running public tasks through hosted APIs, for example in discussion 747168. I have not seen a staff comment on whether that is allowed.
- The public tasks come from open-source repositories, and some providers state that they process prompts only transiently and do not train on them.

My questions:

1. During development, may a participant run an agent on the public tasks in tasks.jsonl through a hosted model provider such as Ollama Cloud or OpenRouter, when the prompts contain task statements and repository code?
2. Does it change the answer if the provider does not retain or train on the data, or if the content also exists in the public upstream repository?
3. May participants use such providers with their own tasks, built from a public dataset outside the Competition Data?

Thank you.


**** (2026-11-04 09:20, 0 votes)
Two related questions on Rule 4.b, since "Competition Data" includes "any prototype or executable code provided on the Competition Website":

1. May participants install the official wheelhouse on a private Google Colab runtime, or store it in their own Google Drive?
2. May an AI coding assistant hosted by a third party read public task text, agent traces or the provided code while helping a participant?


---

## Clarification on distillation from external LLMs
/competitions/gemma-4-developer-agent/discussion/742807 | by  | posted 2026-09-23 15:38 | last comment 2026-11-04 06:32 | 14 comments | 50 votes


**** (2026-09-23 15:38, 50 votes)
Hi organizers,

My understanding is that using external LLM APIs to generate synthetic training data has generally been allowed in recent Kaggle competitions. Given Section 2.6, I would expect this to be permitted here as well, subject to the competition’s external data and model requirements.

Could you clarify whether participants may use proprietary models, such as OpenAI Astra or Claude Opus 5.5, to generate code patches and agent trajectories for training Gemma specifically for this competition?

Regarding provider restrictions on developing competing models, my current understanding is that training a model solely for this competition may be permissible, while deploying or using the resulting model outside the competition could raise separate concerns. I recognize that participants remain responsible for complying with their providers’ terms.

With that distinction in mind, could you clarify:

1. Does the competition allow this form of distillation from proprietary API models? Are there any restrictions on which teacher models may be used?
2. Are there different requirements for proprietary API teachers versus open-weight teachers?
3. How would a model intended solely for competition use fit with the winner licensing and release requirements under Sections 2.5 and 2.8? In particular, would winners need to release the trained weights or adapters for unrestricted use outside the competition?

Examples of acceptable teacher models would be very helpful.

Thank you!


**** (2026-09-29 14:58, 9 votes)
Hello and thank you for your question and your patience. As long as you are using those models in accordance with their model license terms, and the output you're using to submit to that competition doesn't 'conflict with the license requirement of the rules of this competition, you may use them.


> **** (2026-09-29 15:10, -2 votes)
> So models like Claude and GPT are off the table, but Muse and Chinese aren’t?


> **** (2026-10-07 03:19, 0 votes)
> I appreciate your professional answer.   
> Learned a lot today!


**** (2026-09-24 10:46, 6 votes)
Hi @cnumber,

We are confering and will have an answer for you soon.


> **** (2026-09-27 12:02, 3 votes)
> any updates? :)


> **** (2026-09-29 08:14, 0 votes)
> > Hi @cnumber,
> > 
> > We are confering and will have an answer for you soon.
> 
> Any updates? If not, I’ll just start with GLM 5.3


> **** (2026-10-19 20:46, 0 votes)
> haven't heard back on this


**** (2026-09-25 14:51, 1 votes)
I'm looking at using distillation methods for open source models as well. I'm not against open sourcing my training data results from the distillation process as I have a tool that does this for Gemma 4 already developed. I'm curious what they decide on here!

Edit: Here is my KD tool which I'll be updating for this competition [Ghostwriter](https://github.com/jscott3201/ghostwriter-rs)


> **** (2026-09-27 17:36, 0 votes)
> hey this looks cool, thanks


**** (2026-09-25 11:53, -10 votes)
what a state this world is in when a response like this warms my heart ❣️


**** (2026-11-03 19:12, 0 votes)
may we send the public dev tasks (issue text, snapshot code) to a third-party LLM API like DeepSeek to generate training trajectories, or should Competition Data only go through self-hosted models?


> **** (2026-11-04 06:32, 0 votes)
> You should be free to do whatever you like with the public data.


**** (2026-09-25 17:13, 0 votes)
I worry a bit about getting my accounts banned or routed to inferior models for distillation.


> **** (2026-09-25 17:21, 1 votes)
> I wouldn't do this with closed source models but given that Gemma 31B is a smaller model you can get some good gains from open source KD. It is very much against their ToS doing any type of distillation.


---

## Are the reported LoRA issues fixed? I don't see any updates.
/competitions/gemma-4-developer-agent/discussion/755611 | by  | posted 2026-11-04 03:54 | last comment 2026-11-04 03:54 | 0 comments | 2 votes


**** (2026-11-04 03:54, 2 votes)
I am reading through the forum and the reported issues including slower decoding speed and shorter context length. The current eval setup is also severely under-ultilizing the 4xL4 GPU.


---

## [fastapi_14186] Task unresolvable: required test skipped due to @needs_pydanticv1 and Pydantic v2 setup
/competitions/gemma-4-developer-agent/discussion/755554 | by  | posted 2026-11-03 22:28 | last comment 2026-11-03 22:28 | 0 comments | 0 votes


**** (2026-11-03 22:28, 0 votes)
I can independently confirm this for fastapi_14186, with some additional detail.

Setup: the public tasks.jsonl, the task snapshot, the official sandbox/setup.py with the dataset wheels, and the swegemma verifier. The task's own reference patch was applied, and it applies cleanly. The test command exits with code 0.

Because the task has no FAIL_TO_PASS/PASS_TO_PASS, the verifier derives 7 required tests from test_patch. Their decorators, after applying test_patch, are:

Required test	Decorator
tests/test_compat.py::test_model_field_default_required	@needs_pydanticv2
tests/test_get_model_definitions_formfeed_escape.py::test_model_description_escaped_with_formfeed (2 params)	@needs_pydanticv1
tests/test_response_model_as_return_annotation.py::test_invalid_response_model_field_pv1	@needs_pydanticv1
tests/test_compat.py::test_v1_plain_validator_function	@needs_py_lt_314
tests/test_compat.py::test_is_pv1_scalar_field	@needs_py_lt_314
tests/test_compat.py::test_get_model_fields_cached	@needs_py_lt_314
tests/test_compat.py::test_is_uploadfile_sequence_annotation	(none)
needs_pydanticv1 and needs_pydanticv2 are defined in tests/utils.py as skipif(PYDANTIC_V2) and skipif(not PYDANTIC_V2). No single environment can run all required tests, so a skipped required test makes the task impossible to resolve with any patch.

There is one extra detail for the public setup. The dataset ships both pydantic-1.10.15 and pydantic-2.13.4, but deduplicate_wheels in sandbox/setup.py keeps only the highest version. Pydantic 2.13.4 is therefore always installed, and the JUnit report shows the three v1-only nodes as skipped: requires Pydantic v1. The verifier then returns Required test node did not pass: test_model_description_escaped_with_formfeed.

I can also confirm the rich_3486 case. Applying the same derivation, the verifier requires 2 tests from tests/test_traceback.py. After test_patch, test_traceback_finely_grained_missing has @pytest.mark.skipif(sys.version_info.minor >= 11, ...) and test_traceback_finely_grained has @pytest.mark.skipif(sys.version_info.minor < 11, ...). One of them is always skipped on any Python version.

To the organizers, adding to the question above: for the hidden evaluation, is there an explicit FAIL_TO_PASS/PASS_TO_PASS list for this task? If not, could required nodes that are skipped by environment markers be excluded, or the task be corrected? As it stands, it scores 0 for every participant regardless of solution quality.

— Aridio Silva


---

## Submission stuck in "Running" for 30+ hours, blocking new submissions (pending limit)
/competitions/gemma-4-developer-agent/discussion/747708 | by  | posted 2026-10-09 11:53 | last comment 2026-11-03 18:03 | 2 comments | 2 votes


**** (2026-11-03 18:03, -1 votes)
Indeed I am also getting the same issue


**** (2026-11-03 16:29, -1 votes)
Hi @ryanholbrook 
Thank you again for hosting, and for all your help. 
I do have the same issue of a stuck submission as well for over the past about 30 hours. 
I wonder if you or anyone in ur team could help check it.
Thank you again!


**** (2026-10-09 11:53, 2 votes)
Hi @ryanholbrook and Kaggle team,
I have a submission that has been in "Running/Scoring" for more than 30 hours, and because of the new pending-submission limit I can't submit anything else.
Details
Submission ID: [paste the ID from My Submissions]
Submitted: 2026-10-08, around [time] UTC
Archive: a byte-identical resubmit (sha256 eff43dd2…) of my 2026-10-07 submission. The 10-07 run first ended in "Kaggle Error", and batch recovery later scored it at 0.10. Since both are the same archive, I resubmitted the same archive after the error, before the recovery fix was announced.
Runtime: it uses an 8-minute per-task cap. In my own notebook runs on 4×L4, the full 120 tasks finish well within 12 hours.
Questions
Is this submission still waiting in the queue, actually running, or stuck?
If it is stuck, could you cancel it or finish scoring it, so the pending slot is released?
Will the days it blocks count against my daily submissions, or can those slots be restored?
Thank you for the update on the queue issues and for the work on recovering affected runs.


---

## Update on "Kaggle Error" Submissions & Queue Delays
/competitions/gemma-4-developer-agent/discussion/747519 | by  | posted 2026-10-08 22:09 | last comment 2026-11-03 16:47 | 101 comments | 42 votes


**** (2026-11-03 16:47, 2 votes)
Hello, the Notebook Timeout issue persists, and I haven't been able to make a successful attempt in the past few weeks (the last one was 2 days ago). Is there any extension or an estimated repair completion time? Thank you.


**** (2026-10-22 06:53, 2 votes)
@ryanholbrook @herbison

Our team's open problems in one place, each re-checked today (10-22) against the live wheelhouse (unchanged since 10-12), our own runs and the forum. Item 1 belongs to this thread; items 2 to 4 are harness problems we hit along the way.

### 1. Unchanged bundles fail with "Notebook Threw Exception" and still use the daily slot

- Since about 04:00 UTC on 10-21, many unchanged bundles fail with no score, and reports are still coming in today. 57464948 is byte-identical to 57396050, which scored. Others: 57452423, 57458172, 57469833, 57471486, 57474927, 57480561, 57506270 (threads 751264, 751339, 743683 and this one). Ours, 57508304, failed the same way in under an hour.
- Likely cause: slow model loading on L4. Our own 4×L4 kernels started vLLM in 454 to 743 s on 10-20, but in 514 to 1,677 s on 10-21, and 3 of 7 starts on 10-21 passed the 1,200 s limit named in 751264.
- Every failure returns the same generic error, so no team can tell an infrastructure failure from a bug in its own bundle.
- Ask: retry or extend the server start on the scorer; rerun these failures or return the slot; and say in the error whether the run stopped before the first task.

### 2. The public test environment is missing test dependencies

- `wheels/` (124 wheels, last updated 10-13) still has no `inline_snapshot`, `dirty_equals`, `annotated_doc`, `typing_inspection` or `pytest-httpbin`. Gold patches fail at test collection on many public tasks: 52 of 129 pass in a plain notebook, fastapi 10 of 67 (751487). Reported since 09-29 (744370, 745775, 750345).
- The hidden tasks validate at 100%, but the public tasks are what everyone develops on, so every team has to rebuild the environment by hand.
- Ask: add the missing wheels, plus the per-task pins (an older starlette for old fastapi commits, the Pygments of the task's date for rich).

### 3. `edit_file` and `write_file` calls lose arguments, and the error hides why

- In our 104 runs of 10-20 and 10-21 (31B, thinking 4096), 60 of 234 `edit_file` calls and 20 of 255 `write_file` calls were rejected with "mandatory input parameters are not present", against 0 of 1,135 `run_command` calls. 64 rejected calls were exact resends of the call before; one run had 34 of them and timed out.
- Typical case: a string value ends with a backtick, the next argument is swallowed, and the code after it becomes argument names. Received: `` {"filepath": "reproduce_issue.py", "new_string": "...\n`,old_string:", "# Python 3.10+ union syntax": "list[str"} ``.
- The error names only the missing parameter, so the model cannot see that its call was split, and sends it again. The chat-template problem in 744844 may be related.
- Ask: list the received argument names in this error, and check the `gemma4` tool-call parser.

### 4. No per-agent budget in multi-agent bundles

- One clock, one call counter and one turn counter cover the whole task (`swegemma/budget.py` `EvaluationBudget`). The schema has no per-agent limit, and `exit_loop` is not in the tool registry, so a `LoopAgent` can only stop at `max_iterations`.
- So one stage can use the whole budget. In our two-stage test, 7 of 8 timeouts came from the first stage.
- Ask: optional `max_tool_calls` and `max_time_minutes` per agent, and `exit_loop` in the registry.

### Suggestions

1. Submit the sample bundle on the scorer once a day and post whether it scored. Teams could then check that the scorer is healthy before spending their one slot, and a failure wave would show up the same day.
2. Return the slot automatically when the inference server fails to start for a bundle with no adapters. Without adapters that stage loads only the registered base model, so the team's files cannot cause it.
3. Keep one pinned known-issues post (open, fixed in version X, or won't fix), and post a short change list with each wheelhouse update. The README has no change log, so today we find behavior changes by diffing the wheels.

We can share traces or scripts for any of these.


**** (2026-10-25 18:07, 0 votes)
Improving Reproducibility and Evaluation Diagnostics

Reliable evaluation is essential for comparing agent architectures fairly. Clearer error reporting, documented resource limits, and a reproducible evaluation environment would help participants distinguish infrastructure issues from agent-level failures.

I have also prepared a notebook based on the public Budget-Aware Coding Agent V10 recipe, with SHA-256 checks for the expected files and automated submission ZIP packaging.

Notebook: https://www.kaggle.com/code/shorooghahmadi/gemma-4-budget-aware-agent-v10-v2

My focus is on reproducibility and submission reliability. I believe better diagnostics and transparent resource allocation would benefit both participants and the competition organizers.


**** (2026-10-08 22:09, 42 votes)
Hi everyone,

I wanted to give an update on the long submission wait times and "Kaggle Error" failures many of you have been seeing over the past couple of days.

## What Happened

Due to very high submission volume using L4s, submission jobs have been facing long queue times before actually getting a machine to run. Submissions that waited \>15h to start were being marked as “Kaggle Error” even if they eventually did run.

## What We Fixed

1. **Extended Queue Timeout:** We've drastically extended the queue allowance so submissions will no longer be timed out while waiting to run.  
2. **Scoring Submissions that had Queue Timeouts:** We are actively reprocessing all affected submissions from the past few days. If your notebook ran to completion and produced a valid submission file, it is being scored and published to the leaderboard automatically. You should already see scores showing up on the leaderboard now.  
3. **Queue Wait Times:** to even some of the load on the pool, we are implementing a pending submission limit (separate from the 1/day limit). If your team's previous submission is still scoring, you will need to wait until it finishes to submit again.

## What This Means for You

* **No action needed:** You do not need to resubmit or contact support to recover an affected run; our batch recovery is processing them directly.  
* **Monitor this post for updates**

Thanks for your patience while we sort this out, and sorry for the frustration it caused over the last few days.


**** (2026-10-21 09:05, 2 votes)
Hi @herbison @ryanholbrook, could you check submission 57469833? It ended with “Notebook Threw Exception” after ~15 minutes, i.e. around vLLM startup / agent compilation, and consumed the daily slot.

The zip has only agent.yaml, eval_config.yaml, configs/sampling.yaml, prompts/system.md at the root (no adapters, no extra files). It compiles with adk_submission 0.2.13 and runs a task end to end locally with swegemma 0.2.11.
Submission 57391545 used the same prompt and configs plus the zero-init main_lora from the sample submission. It ended with Notebook Timeout, so it got past startup.

Could you tell the failure stage and the first exception, and whether this could be scorer-side? Thank you!


**** (2026-10-21 18:52, 1 votes)
hello Team,
On going through this board I think we have common issue of Notebook Threw Exception faced by a lot of people which seems to be caused by no material change (like literally the same submission with a simple prompt change) is it possible we can at least provide a reasoning or better error exception there or revert people's submission count so that they can try after some time 
Even in my case my submission S2 (same file layout as our S1, which scored) hit “Notebook Threw Exception” about 25 minutes after submission on 21 Oct 11:41 PM IST. Could you share the error or log excerpt, Thanks.


**** (2026-10-09 00:03, 12 votes)
>Queue Wait Times: to even some of the load on the pool, we are implementing a pending submission limit (separate from the 1/day limit). If your team's previous submission is still scoring, you will need to wait until it finishes to submit again.

Do we have a guarantee that our submissions will score within 48 hours (ideally we want them to score **at most** within 24 hours)? Otherwise, we will just lose 1 submission.


> **** (2026-10-09 13:25, 2 votes)
> It's possible, yes, that you will lose a daily submission this way. Unfortunately, even after doubling the number of L4 machines, we were still seeing the queue grow without bounds. Since, at the moment, it doesn't look like we'll be able to increase our supply of GPUs, we have to reduce somehow the submission demand instead.


> > **** (2026-10-09 13:35, 0 votes)
> > Yea, number of participants is just wild this year… 
> > 
> > Can Kaggle possibly make it like 1 submission a day per all competitions with 4xL4 inference? So 1 person wont be able to use 3 instances (2 ARC and 1 for gemma competition) daily, for example


> > **** (2026-10-09 13:40, 1 votes)
> > Also, I think some drastic measures are possible. For example, disable completely 4xL4 notebooks. Yea, some participants wont be able to even submit, but I’m afraid the queue will only grow overtime and we will have to wait for 3-4 days to submit…


> > **** (2026-10-09 13:41, 1 votes)
> > Additionally, if you're in this boat, everyone is, so while it's understandably frustrating, it is fair. That's why giving more subs won't help, since it'll just mean even longer wait times.


> > **** (2026-10-09 13:43, 2 votes)
> > Its fine for me 100% within some reasonable bounds. I dont want to end up in the situation, where my final submission will wait a week in a queue and wont even score before the deadline


> > **** (2026-10-09 14:04, 1 votes)
> > yeah, this sounds better, i thought of it as limiting participants to max 3 simultaneous competitions (with no restrictions to joining though, only submissions gets capped)
> > 
> > GPU usage will only grow with time, kaggle needs to come up with something sooner than later. 
> > 
> > this competition is hot, aligns with current state of real world LLM usecases. 
> > 
> > skills gained here applies to literally everything going forward


> > **** (2026-10-09 14:57, 3 votes)
> > Currently, the queue is very long, however the recent submission limit that we introduced has bounded queue growth, and the queue is draining very slowly.
> > 
> > If the number of teams actively submitting doesn't drastically increase, the queue should stabilize back down to the "daily" submission rate (where each run starts and finishes within the same day), though it may take ~a week for that to happen since there is a backlog to burn down.


> > **** (2026-10-09 15:10, 0 votes)
> > Thanks! I guess a week is pretty safe. Will see


**** (2026-10-09 04:46, 6 votes)
My submission is running from more than a day now ~27hrs

![submission](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F2411334%2Fa518e1a223fe5cbb4ef7f14fe4eda9ad%2FScreenshot%20from%202026-10-09%2010-12-28.png?generation=1791521045837838&alt=media)

Now I want to create another submission for today but can't due to the new limit

![limit error](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F2411334%2F8d0d6e377ec2d07e6c73ceefba7c16f6%2FScreenshot%20from%202026-10-09%2010-12-34.png?generation=1791521016328994&alt=media)

So, if a submission is in queue for long time, we can loose one day's submission right?
If it is in the queue for 2 days we will loose 2 submissions?
May I know what is the new queue time limit?
We also can't even stop the existing submission to submit a new one.


> **** (2026-10-11 03:37, 0 votes)
> Mine also has the same issue.


**** (2026-10-10 16:01, 5 votes)
The current queue delay is around ~33h, so yes, your submission isn't stuck, its making its way towards the front of a long line of submissions. If its been >33h, its likely running right now and your score will arrive once it finishes, scores have continued to work its just incredibly high demand and finite supply.

Thanks for your patience everyone, we will continue to do what we can.


> **** (2026-10-11 15:51, 2 votes)
> My submission has been stuck in processing for more than 24 hours, without completing or providing any results.
> 
> Unfortunately, this issue has also prevented me from submitting another notebook the following day, causing me to lose valuable competition time and submission opportunities.


> **** (2026-10-13 17:55, 3 votes)
> Update: Queue delay has fallen to around ~14h, its *slowly* going down, but most runs should finish within ~24hish of submit now.


> > **** (2026-10-13 18:11, 2 votes)
> > Thanks! That "pending sub" change was very smart. I think we lost ***at most*** 2-3 submissions which is basically nothing


**** (2026-10-22 07:54, -1 votes)
https://www.kaggle.com/code/shorooghahmadi/gemma-4-budget-aware-agent-v10


**** (2026-10-09 19:28, 4 votes)
It would be super useful to cancel a pending run ideally with some. visibility on current status of the said pending run. Say I have a better idea to try but because a pending run is stuck for a day, I just cannot plan the next set of experiments. I would imagine many try to make a submission to be able to come to a result overnight and then plan the next day accordingly. Maybe some more control would be nice. I understand this is a fundamental product feature ask but maybe putting it on a roadmap would be appreciated. thanks.


**** (2026-10-15 03:52, 1 votes)
Hi, I’m still encountering the “Kaggle Error” even though my submission log reports “success.” Could you clarify why this issue persists? Will the affected submission be rerun automatically and receive a score later?


**** (2026-10-11 15:52, 1 votes)
Unfortunately, this issue has also prevented me from submitting another notebook the following day, causing me to lose valuable competition time and submission opportunities.


**** (2026-10-09 00:26, 2 votes)
I have a submission that already timed out and shows up as failed...

but it's still running.


**** (2026-10-10 14:18, 1 votes)
Is this contest even a legitimate contest if no one can submit without error? I can’t even get a base line submission.


**** (2026-10-09 06:18, -1 votes)
Hello, is this because Kaggle doesn't have sufficient computing resources?
Maybe ask Google for more GPUs.


**** (2026-10-09 15:47, 1 votes)
Rather than just making it random and unpredictable with increased timeouts, just make it one submission every 2 days so we can plan our research/submit cycles.


**** (2026-10-09 20:23, 1 votes)
My latest submission has been running for over 2 days now

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F6426555%2F0e8eec11e6be9245fbac10ec10676729%2F2026-10-10%20000404.png?generation=1791579900966110&alt=media)


> **** (2026-10-09 21:20, 1 votes)
> >Scoring Submissions that had Queue Timeouts
> 
> I also have two submission.zip files that didn't work previously with kaggle error; can they be scored, or is that only for notebooks that generated a valid submission.zip?


> **** (2026-10-10 07:38, 0 votes)
> Upd: ended with notebook timeout


**** (2026-10-09 17:39, 1 votes)
Submission 56949985 (team Harsha) has been pending since 2026-10-08 10:50 UTC, over 30 hours. Could you check whether it's still queued or needs re-processing? Thanks.````


**** (2026-10-09 07:41, 1 votes)
Hi @herbison — following up on Gholamali's question above, since it affects how we test locally.
Did the scorer move to swegemma 0.2.10 / adk_submission 0.2.13, and if so, when? The wheelhouse we pulled gives us
swegemma 0.2.7 / adk_submission 0.2.12 (the Sep 30 build), so we are validating against those.
Three things it would help to know:
Which versions is the scorer running right now, and were they changed between Oct 6 and Oct 8? That window is
when the "A system error" reports start.
Is there anything in 0.2.10 / 0.2.13 that changes how a submission is compiled or run — tool registration,
eval_config fields, compaction defaults, the patch collection step? We would rather find out from the changelog
than from a failed submission.
Where do we get the current wheels, so local validation matches the scorer? If the published wheelhouse is
still on 0.2.7 / 0.2.12, could it be refreshed?
Also, on the new pending-submission limit: with queue waits of 20-27 h being reported, a submission that sits in the
queue past 00:00 UTC costs us that day's submission as well as the slot it is occupying. Could you confirm whether a
submission that is still PENDING when the daily limit resets blocks the next day's attempt, and whether there is any
way to cancel a queued submission?
Thanks for the update and the reruns — our 56894166 came back and scored.


> **** (2026-10-09 20:49, 1 votes)
> I think Ryan covers that in this comment:
> https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747519#3535930


**** (2026-10-11 13:47, 0 votes)
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F14563206%2F16f18400fc28d87d417dbff9dabc2926%2FScreenshot%20from%202026-10-11%2019-12-44.png?generation=1791726217220319&alt=media)

Hi Team! My previous submission has been running for more than 24 hours, which is preventing me from making any new submissions. Could you please look into this and help resolve it?


**** (2026-10-10 05:51, 0 votes)
@ryanholbrook Could you please extend the final submission deadline by a few days? We’re losing quite a bit of time, and an extension would give everyone a fair chance to plan and complete their remaining submissions.


**** (2026-10-11 07:32, -2 votes)
Hi team!
I’ve run into a technical hiccup. My notebook has been running for over 12+ hrs, and it’s blocking my submission, and since I already have an updated version ready, I can’t submit it until this is resolved. Could you please help?
Thanks so much.


**** (2026-10-10 22:46, -1 votes)
Hi @ryanholbrook -- our submission 56996213 has been PENDING since 2026-10-09 06:35 UTC (~40h now), well past the recent ~33h queue estimate, and it's blocking new uploads under the 1-pending limit. Could you confirm it's still progressing (not stuck), and is there any way to expedite or clear it so we can use today's submission slot? Thanks for the updates so far!


> **** (2026-10-11 03:24, 1 votes)
> 33h is the approximate *queue* wait time, then you have to wait your submission *runtime* before it gets scored.
> Your submission looks like it finished and results were posted now.


**** (2026-10-10 17:14, -1 votes)
My submission is running from more than 24 hours. ![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F28373464%2Ff6747f30029d4eb6ea1083679a77e7df%2FScreenshot_20261010_223958.png?generation=1791652309294770&alt=media)

Due, to which I am not even able to make my new submissions. Please, let us know if any action is required from our side.


**** (2026-10-10 15:26, -1 votes)
Hi @ryanholbrook, our submission 56980374 (Oct 9, 00:13 UTC) has been PENDING for ~39 hours and is blocking our next submission under the pending limit. Could you confirm it's still queued (not stuck)? We'd like it scored rather than cancelled. Thanks!


**** (2026-10-10 12:33, -1 votes)
@ryanholbrook @herbison Our submission (ref 56972471) has been in SubmissionStatus.PENDING for over 36 hours (submitted 2026-10-08 20:50 UTC). It is currently blocking our next daily submission due to the pending limit. Could you please cancel or unstick ref 56972471 so we can submit our updated candidate? Thank you!


**** (2026-11-02 14:42, 0 votes)
Our submission 57862929 is in PENDING state for 32 hours!


**** (2026-11-02 09:28, 0 votes)
@herbison @ryanholbrook

Status inquiry only: submission 57858834 pending for approximately 30 hours

Hello Kaggle Support / competition operations team,

Could you check the current processing state of our submission to Google - The Gemma 4 Developer Agent Competition?

Competition: https://www.kaggle.com/competitions/gemma-4-developer-agent
Account: capitaalgain
Submission ID: 57858834
Accepted: 2026-11-01 03:26:07 UTC
Latest official API check: 2026-11-02 09:24:57 UTC
Status: PENDING; no public score or terminal error, approximately 30 hours after acceptance.

Please confirm:
1. Is it waiting for resources, actively executing or validating, or stalled?
2. Is it affected by a known platform incident or evaluation-queue delay?
3. Is there an estimated recovery or completion time, or an expected next status update?

We saw the historical queue-delay update (discussion 747519) and a recent separate participant report of 29+ hours pending (discussion 754845). We understand these do not establish the cause of our submission's delay. We are requesting status information only, not code debugging or hidden evaluation/test details.

Please preserve this original submission and our previous scored submissions. Do not cancel, reset, rerun, replace, or resubmit anything. We have not submitted a duplicate and will continue read-only monitoring.

Thank you.


**** (2026-10-31 14:07, 0 votes)
Wondering if there a recipe I am missing, my submissions are getting timed out. Is it some setting or my understanding of the timeouts work. Has anyone had a opportunity where they faced multiple timeouts and realized its problem with how they have designed it that it works on local but get timeout when post submission, also not instantly but after say 1 d or more than 14 hours ..


> **** (2026-11-02 14:44, 0 votes)
> Maybe the agent is spending too much time on each task and reaching the 12 hour limit. Limiting the time per task to 6-8 minutes could solve it.


**** (2026-10-28 12:51, 0 votes)
Dear host, the queue problem might happens again, the scoring now is slow (> 1 d scoring time)


**** (2026-10-28 02:29, 0 votes)
Hi Ryan / Kaggle team, could you check a likely scoring-environment failure? On Oct 27 I resubmitted an unchanged notebook version (gemma-4-developer-agent-submission-builder, scriptVersionId 358491234; prompt-only 31B agent, no LoRA, no skills, 8 min / 28 calls). The same version scored 0.17 (Oct 15) and 0.18 (Oct 25). The Oct 27 run shows "Succeeded" with public score 0.00. Since the agent package is byte-identical, it looks like the scorer could not serve the model or run the tasks in that run. Could you look at the failing stage and, if it was on the platform side, re-score it or return the slot? I have resubmitted the same version today. Thanks!


**** (2026-10-26 11:19, 0 votes)
Submission 57632467 has been PENDING since 25 October at 15:03 Amsterdam time. Could you confirm whether it is queued, running, or stuck, and whether any action is needed from us?


**** (2026-10-24 05:12, 0 votes)
Packages that validated on local fail on submission, and a minor yaml config changed (1 or 2 params at most) for an earlier accepted yaml throws a kaggle error. Spend 2 daily submissions this way. Request to the organisers to have those be accepted so we can see if those improve score, or at least more verbosity in error messages to help us understand if its an issue on competitor end. Thanks!


**** (2026-10-23 15:27, 0 votes)
@herbison Hello,

Three of my submissions to the Gemma 4 Developer Agent competition failed with “Notebook Threw Exception” after several hours of scoring, during the recent platform issue:

57455008 (2026-10-20 22:39 UTC)
57478802 (2026-10-21 11:03 UTC)
57516417 (2026-10-22 08:08 UTC)

One of them (57516417) is an unchanged resubmission of a bundle that had scored successfully twice before, so the failure is not caused by the bundle itself. The CLI lists all three as SubmissionStatus.COMPLETE, but none has a score.

Could you please re-run these three submissions, or restore the daily submission slots they used?

Thank you,
Tammam


**** (2026-10-23 03:34, 0 votes)
Could you tell us when the scoring run for our submission canary-a-02 (submitted 2026-10-23 03:04:59 UTC) actually started, i.e. the end of its queue wait? We measure run time from submit to score, and without the start time we can't separate queue wait from run time. Thank you.


**** (2026-10-22 16:54, 0 votes)
Hi @ryanholbrook,

Could you check two failed Gemma 4 Developer Agent submissions from zihanhu88?

- Entry 57468304, submitted 2026-10-21 05:52:39 UTC: notebook exceeded allowed runtime.
- Entry 57526335, submitted 2026-10-22 13:28:29 UTC: unhandled error during rerun.

Both reference the same notebook version 1, scriptVersionId 360665638:
https://www.kaggle.com/code/zihanhu88/gemma-v6-c40-20261021-054838-3d634868

The agent ZIP is identical in both attempts, SHA256
3d634868d2833e536b6dd2885a70769307716a0dd012bd23eba3833d141167f5.
It uses 31B/no adapters, 8 minutes per task, 40 tool calls, 80 turns and a 240-second
command timeout. The public CPU packaging notebook completed successfully and
the exact returned ZIP matched our approved archive. Earlier entry 57365764
scored 0.18 using the same model/sampling and 28 calls instead of 40.

The API reports COMPLETE with no scores but distinct errorDescription messages.
Could you confirm the execution stage and sanitized exception type/component
for the second attempt, and whether either entry was affected by a known runtime
or infrastructure issue? For the first, confirmation of actual execution time
versus queue time would help distinguish global-budget exhaustion from delays.
We do not need hidden task contents or test outputs.

If these are platform failures, are the entries eligible for a host rerun?
Thank you.


**** (2026-10-16 19:56, 0 votes)
I keep hitting "Notebook Timeout" errors - is this the kaggle error that is noted here or is this something about my submission being misconfigured?


> **** (2026-10-22 21:38, 0 votes)
> i think yes


**** (2026-10-16 14:06, 0 votes)
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F22372197%2F0d5f0e81f74210f568c09f300675107a%2Fnotebook%20timeout%20error.jpg?generation=1792159501495914&alt=media)

I have received this timeout error now. What should I do? Should I rerun that same notebook again or wait for automatic scoring? Kindly help me with this issue!!!


> **** (2026-10-16 14:11, 1 votes)
> https://www.kaggle.com/code-competition-debugging


> **** (2026-10-16 21:50, 0 votes)
> SAME FOR ME


**** (2026-10-16 12:45, 0 votes)
You mention the usage of L4 gpu for the Kaggle error reason, but how do you explain Kaggle error appearance also in submission that do not use the L4 gpu? An brief response will help us to understand better the error


> **** (2026-10-16 14:17, 0 votes)
> L4 usage caused a very specific class of Kaggle Error, there are other errors that can occur that are a different class.
> The queueing error was just a widespread issue with how long the L4 queue got, which has been long fixed now.


> **** (2026-10-16 14:53, 1 votes)
> It's most likely because your `submission.zip` isn't in the proper format. Use the sample submission as a guide and make sure there aren't any extraneous files (like pycache `.pyc` files) included.


**** (2026-10-16 11:31, 0 votes)
my agent has been running in submission for 16 hours, i think something wrong with your backend servers or its like really deep in the tasks because I may be a bit  scared for a low score also excited  for a high one cause if my predictions our true for this competition in arc agi 3 competition a massive leaderboard spike is gonna happen


**** (2026-10-16 00:13, 0 votes)
Hi Team,

I can submit and can get a success run from the log. But I can not see it on my past submission list nor can I see a score. And It seems not consuming my daily submission quota as well. Can anyone help with that?

Thanks!


> **** (2026-10-16 00:14, 0 votes)
> @herbison @ryanholbrook


**** (2026-10-15 08:19, 0 votes)
Hi @herbison @ryanholbrook,

I’m experiencing a similar issue: my saved notebook version completes successfully and produces submission.zip, but the competition submission fails almost immediately with “Kaggle Error — A system error.”

Latest submission ID: 57214092
Notebook version ID: 358528068
Notebook: https://www.kaggle.com/code/ruoxuanteng/gemma-4-agent-budget-fit-single-agent/notebook?scriptVersionId=358528068

Thank you for your help!


> **** (2026-10-15 20:13, 1 votes)
> Can you try again? There was a bug when submitting from an interactive session (worked fine when submitting from an already run save version) but it should be fixed now.


> > **** (2026-10-16 04:48, 0 votes)
> > Thanks — just resubmitted and it’s now correctly showing as Scoring. Appreciate the quick fix!


**** (2026-10-14 13:52, 0 votes)
HI Team..

My submission has been stuck in processing for more than 24 hours, without completing or providing any results.

Unfortunately, this issue has also prevented me from submitting another notebook the following day, causing me to lose valuable competition time and submission opportunities.


> **** (2026-10-14 14:16, 0 votes)
> You submitted ~19h ago, your submission is still running.


> > **** (2026-10-14 23:47, 0 votes)
> > So how to fix as it has already been a day for the submission


> > **** (2026-10-15 14:45, 0 votes)
> > Your submission finished by the time you posted that?


> > **** (2026-10-15 17:32, 0 votes)
> > My Submission failed that what I see in submissions


**** (2026-10-14 08:37, 0 votes)
Hi @ryanholbrook @herbison, team InSociEUP here.

Submission 56765863 (2026-10-02 04:43 UTC) has been PENDING for 12 days. It is an accidental duplicate: a single API call created two submissions 0.3 s apart from the same notebook version, and its twin 56765864 was scored normally (0.08).

Since the pending-submission limit went live, every new submission from our team is rejected with "Your team already has 1 pending submissions" (FAILED_PRECONDITION), so we have not been able to submit since 2026-10-08.

Could you cancel or fail 56765863 so the team can submit again? We don't need it scored. Thank you!


> **** (2026-10-14 19:55, 0 votes)
> @santanubanerjee9 You had a different kind of "stuck" submission, I think I errored it out for you, can you check?


**** (2026-10-13 14:33, 0 votes)
The submission was marked “Kaggle Error” within minutes, although the packaging notebook completed successfully in 23 seconds and generated a valid submission.zip output.

Does the automatic recovery process also cover immediate “Kaggle Error” failures, or only submissions that exceeded the previous queue timeout?

We would like to avoid consuming another daily submission if the original can be recovered.


> **** (2026-10-13 15:28, 0 votes)
> The recovery process was a one-time thing, not continuous and was specific to one kind of issues (queue wait timeout).
> In your case, it seems like you hit submit before your submission.zip was ready, you can try resubmitting it.
> Kaggle Error should not consume a submission anyway.


**** (2026-10-12 08:38, 0 votes)
May I ask when can we back to normal track? It is very frustrating to keep waiting. Or is there any plan that extend the deadline for the competition?


**** (2026-10-11 10:44, 0 votes)
Good morning, everyone. 

If I may, if there are queue congestion issues with the tasks, it would be recommended to enable a specific state such as 'Notebook Enqueued.' 

This would allow us to know the real execution time and detect potential infinite loops, since right now it's not possible to know the actual state of the task. 

I understand that the queue problem still exists today because my last submission has been in 'Notebook Running' for 16 hours.

Regards...


**** (2026-10-11 10:19, 0 votes)
Hi Dustin and team, thanks for explaining the queue issue. Could you check whether this announcement also covers our terminal "Notebook Threw Exception" result for submission 56949174?

Our original submission 56913088 ended with "A system error". We made one retry, 56949174, using the same ZIP and notebook version 356090888. The retry's API status is COMPLETE, but error_description is non-empty and public_score is empty.

Checks completed:
- The ZIP downloaded from the submission matches our frozen candidate's SHA-256.
- The CPU packaging notebook completed successfully in 19 seconds.
- Adapter discovery and compilation pass with the official adk_submission 0.2.12 and 0.2.13.

Notebook version: https://www.kaggle.com/code/sinfonia8838/submit-t008-lora-pilot-v001?scriptVersionId=356090888

We do not have the hidden-run traceback. Could staff confirm the failure stage (packaging/compilation, vLLM startup or adapter warmup, or harness execution), the first fatal exception with sensitive details removed, and the wheelhouse/runtime build used for this run? It would also help to know whether the queue/outage announcements specifically apply to 56949174.

We are not requesting hidden task details. We would like enough diagnostic information to choose the next check and avoid another blind resubmission. Thank you.


**** (2026-10-10 02:46, 0 votes)
Thanks for the update!!  And here I was questioning my own competence, guess I can worry a little less about things 😆


**** (2026-10-10 01:48, 0 votes)
Hi @ryanholbrook and Kaggle team, one status question plus three budgeting clarifications (following up on 743063 and 745805):

0) Our submission 56960200 (the unchanged official baseline) has been PENDING since Oct 8, 15:24 UTC, i.e. over 34 hours, with no score. A new upload is rejected with "Your team already has 1 pending submissions; please wait for one to finish scoring." Is this normal queue time, or could the submission be stuck? If stuck, should we wait, or cancel and resubmit?

1) 12-hour fix status: is the planned change (unfinished tasks at the 12h limit scored as 0, instead of the whole submission erroring) live now? The last visible answer we found (743964) was "Not yet."

2) Run scope: does one scoring run generate patches for the full hidden test set (~120 tasks, public + private), or only for the public split (~58), with the private split evaluated in a separate rerun after the deadline?

3) Queue vs limit: does time spent waiting in the queue count toward the 12-hour limit?

Thank you!


> **** (2026-10-10 12:26, 2 votes)
> 0) It's queued.
> 
> 1) I may not implement this. Because of how the scoring system works, it's challenging to arrange it so that public and private tasks are treated consistently.
> 
> 2) The full hidden test set.
> 
> 3) No.


**** (2026-10-10 00:59, 0 votes)
Submission 56972125 (submitted 2026-10-08 20:40 UTC) has shown "Notebook Running" for over a day.
It's an old baseline I no longer need, and because of the pending-submission limit it is blocking
a new submission. Could it be cancelled? Thanks!


**** (2026-10-09 18:57, 0 votes)
It is running from more than a day! What happened actually!


**** (2026-10-09 17:06, 0 votes)
Hello Kaggle Team & Admins,
My recent submission has been stalled in the `SubmissionStatus.PENDING` queue for more than 26 hours.
Here are the details from my submission history:
- **Competition:** Google – The Gemma 4 Developer Agent Competition
- **Previous Submission (Ref 56971261):** Failed with `SubmissionStatus.ERROR` ("A system error. Please try resubmitting...")
- **Retry Submission (Ref 56971313):** Submitted on 2026-10-08 20:18:49 UTC
- **Current Status:** Still `SubmissionStatus.PENDING` (no score or failure message returned)
Could the competition team please check if the evaluation worker for ref `56971313` is stuck, or terminate/reset the evaluation so it does not block the queue?
Thank you!


**** (2026-10-09 16:45, 0 votes)
my submission has been running for more than 24 hours now what does this mean


> **** (2026-10-09 16:53, 0 votes)
> It means its likely either still waiting to run (queued), or has started running but hasn't finished yet.
> The queue is very long right now, like >1 day long.


**** (2026-10-09 16:09, 0 votes)
If I submit it today, will I have time to check it before the competition ends?


**** (2026-10-09 04:00, 0 votes)
Hi Kaggle team, my second submission of Getting Started - Gemma 4 Developer Agent, Version 1 has shown “Notebook Running” since about one day ago. My first submission of the same version succeeded with a public score of 0.01. I cannot submit my new Gemma 4 SuperAgent, Version 1 because the page says “Your team already has 1 pending submissions.” Could you check whether the pending run is still active and unblock it if it is stuck? My Kaggle username is guoxuezhen. I can provide screenshots or the submission ID if needed.


**** (2026-10-09 02:33, 0 votes)
Thanks for the transparency and the clarity.
I think we all understand the gpus situation.


**** (2026-10-08 22:21, 0 votes)
Hi @herbison , did you update packages (swegemma 0.2.10, adk_submission 0.2.13) today?


> **** (2026-10-09 13:08, 2 votes)
> I updated the packages in the wheelhouse yesterday to address some of the edge cases around tool calling and thought budgets. I'll make a more detailed post soon.


> > **** (2026-10-10 00:42, 0 votes)
> > when u say wheelhouse u mean the wheels folder in the data right? @ryanholbrook


**** (2026-10-08 22:20, 0 votes)
Thanks for the update!


---

## Where 76% of a 300-second agent budget actually goes (4 trace audits)
/competitions/gemma-4-developer-agent/discussion/755291 | by  | posted 2026-11-03 06:01 | last comment 2026-11-03 14:04 | 1 comments | 1 votes


**** (2026-11-03 06:01, 1 votes)
Audited four Gemma-4-12B runs on fastapi. Wall-clock is 76% pure decode at 17.25 tok/s — least-squares fit dt = 0.78 + 0.058·ct, r² = 0.9996 over 39 normal steps. 

8 of 43 steps hold 56% of the budget, in two shapes: 4 restatements of a file just read (1,788 tokens / 104 s in one message), and 4 prefill spikes (82 s for 251 tokens). Same cost, opposite cause — you can't tell them apart without decomposing.

 The one I didn't expect: read_file truncates at 150 lines. fastapi/params.py is 754 lines, was read 6 times, still never fully seen — and 1,152 lines across four runs were fetched twice. 

Three rules follow: never restate a file after read_file, always pass both start_line and end_line (the cap is 150, so anything over ~400 lines needs grep first), and treat any single step over 60 s as a prompt bug rather than a model limitation.

Notebook runs in 20 s, no GPU: https://www.kaggle.com/code/xingling666/a-300-second-budget-is-5-000-output-tokens


**** (2026-11-03 14:04, 0 votes)
I compared the declared configs of three public submissions (0.20 / 0.18 / 0.05). Only the model size separates them — 8192 / 4096 / 8 min / 240 s is identical across all three, including the one at 0.05. There are also three settings that silently do nothing, with a checker you can run on your own agent.yaml:https://www.kaggle.com/code/xingling666/same-8-minutes-scores-from-0-05-to-0-20


---

## Important dataset inquiry for better model alignment
/competitions/gemma-4-developer-agent/discussion/755391 | by  | posted 2026-11-03 13:52 | last comment 2026-11-03 13:52 | 0 comments | 0 votes


**** (2026-11-03 13:52, 0 votes)
Well, this is the issue. I was experiencing the following condition. Every one of the 129 issues in the public dataset is located in three to four Python libraries, including FastAPI, Rich, HTTPS, and requests. Is there a solution to the issue of private data containing related libraries, such as Starlette or another solution? Or does the private data exclusively consist of libraries such as these, which are restricted to these? Or is it similar to the fact that there are any other repositories? I am not inquiring about the contents of the private dataset; rather, I am asking this question to facilitate the proper alignment of models, data training, and data collection, as well as to enhance the model's training.


---

## Why has my notebook been submitting for more than a day. 
/competitions/gemma-4-developer-agent/discussion/755318 | by  | posted 2026-11-03 08:01 | last comment 2026-11-03 12:48 | 2 comments | -2 votes


**** (2026-11-03 08:01, -2 votes)
I can literally submit a completely new entry and my old one still won't be finished.


**** (2026-11-03 12:48, 0 votes)
every submission of mine for the past 2 weeks have been for 18-28h until a score


**** (2026-11-03 10:56, 0 votes)
Hey even I'm going through a similar problem. It's been like 25 hours since submission and it's still going on.


---

## thinking_budget and seed are missing from HTTP requests in my wheelhouse test
/competitions/gemma-4-developer-agent/discussion/744566 | by  | posted 2026-09-30 10:12 | last comment 2026-11-03 07:09 | 5 comments | 1 votes


**** (2026-09-30 10:12, 1 votes)
Hi organizers,

I found a possible problem with thinking_budget and seed. I tested the packages from the official wheelhouse v25 in a Kaggle CPU notebook.

I used a short message, the same in every test. The request went through the installed adk_submission thinking-config bridge, Google ADK and LiteLLM. A small local HTTP server recorded the final request and returned a fixed reply. I did not load Gemma or run the full scoring process.

Packages: adk-submission 0.2.11, google-adk 1.36.1, google-genai 2.11.0, litellm 1.82.4 and openai 2.32.0.

Results:
- thinking_budget=4096 and thinking_budget=1024 produced the same HTTP body. Neither request included a numeric thinking budget.
- seed=1234 and seed=4321 also produced the same HTTP body. The seed field was missing.
- As a check, changing max_output_tokens from 8192 to 4096 changed max_completion_tokens in the request.
- Changing include_thoughts from true to false changed chat_template_kwargs.enable_thinking correctly.

All seven test cases completed successfully. This test checks what the client sends. It does not prove that the hidden scorer uses exactly the same path. It also does not test whether vLLM applies a budget after receiving it.

In the code I checked, the bridge handles include_thoughts and thinking_level, but not thinking_budget. The ADK conversion also does not pass seed. The upstream vLLM 0.19.1 API has fields named seed and thinking_token_budget.

This seems separate from the loss of thoughts between tool calls discussed here: https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744354

Could you please clarify:
1. Does the scoring environment pass these two parameters to vLLM?
2. If not, could the harness pass seed and map thinking_budget to thinking_token_budget? Could you also check that the server can apply the limit correctly for Gemma?
3. Will the planned reasoning patch cover this issue too, or does it need a separate fix?

Thank you for your help!


**** (2026-11-03 07:09, 0 votes)
I re-tested this with wheelhouse v28 after the organizer’s update. In that environment, both parameters reached the final vLLM HTTP request: `thinking_budget` was mapped to `thinking_token_budget`, and `seed` was present. I also verified on the GPU path that different thinking budgets were applied.

The patch was in the competition submission/bridge path, so it did not necessarily require a custom Google ADK wheel. I have not re-tested the latest wheelhouse or the current hidden scorer, so I cannot confirm whether every current scoring run uses the same patched code.


**** (2026-09-30 15:52, 0 votes)
Hi @veronikayaitskikh,

Thanks for the heads up. I will patch.


> **** (2026-09-30 19:10, 0 votes)
> How we can reproduce that patch in our systems?


> > **** (2026-09-30 19:59, 0 votes)
> > The most recent wheelhouse dataset should have the patches.


---

## Fine tuning with Lora is the only way??!
/competitions/gemma-4-developer-agent/discussion/755289 | by  | posted 2026-11-03 05:49 | last comment 2026-11-03 05:49 | 0 comments | 2 votes


**** (2026-11-03 05:49, 2 votes)
Hi guys, I'm new to kaggle and this is my first compitition.

I only have evaluation and harness exp, so I mainly tried optimize prompt and orchestration.

After about 15 attempts, I wondering whether context managing and prompting is effective in this one.

I’ve compiled some failure patterns. Some constraints on the model’s behavior are largely ineffective.

The main factor seems to be configs in sampling.yaml and eval_config.yaml.

`**Ineffective**

| **ID** | **Pattern**                                                                                                      |
| :----: | :--------------------------------------------------------------------------------------------------------------- |
|   E1   | Paging through a file in small windows (≤35 lines) instead of reading the whole function at once                 |
|   E8   | Reverts its own fix to compare behavior, then submits an empty patch                                             |
|   E10  | Analyzes without editing: never edits, or edits only once the budget or time runs out                            |
|   E11  | Fix is incomplete or differs from the gold patch                                                                 |
|   E12  | Sub-agent makes too many calls: keeps chasing definitions after finding the target, or repeats commands verbatim |
|   E13  | Sub-agent report is wrong or vague; the root agent follows it without checking                                   |
|   E14  | Root agent ignores `budget_warning` and keeps reading                                                            |
|   E15  | Modifies or creates test files                                                                                   |
|   E17  | Re-reads code already in context, including code given in the sub-agent report                                   |
|   E18  | Reproduction script misses the bug (passes); the agent switches hypotheses instead of editing                    |

**Effective**

| **ID** | **Pattern**                                                                                                                                                                         |
| :----: | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
|   E2   | One-line `python3 -c` with compound statements or backticks causes a syntax error                                                                                                   |
|   E3   | `write_file` to `/tmp` fails, or scratch files are left in `/workspace`                                                                                                             |
|   E4   | `old_string` not found or not unique (long docstrings, escapes, or lines filled in from memory); only adds context upward after a "not unique" error                                |
|   E5   | `grep -r` without `--include` scans the whole repository                                                                                                                            |
|   E6   | `include_thoughts: false` loses reasoning across turns; each step takes 45–60 s                                                                                                     |
|   E7   | `max_output_tokens: 16384` returns a 400 error when the input exceeds 16384 tokens                                                                                                  |
|   E9   | Tool argument misuse: backticks or `start_line` mixed into the `read_file` path, a path passed to `--include`, or searching a nonexistent directory                                 |
|   E16  | Emits `call:grep ...` as if `grep` were a tool name; the harness treats it as truncation, the model repeats until the nudges run out and submits an empty patch                     |
|   E19  | Malformed `edit_file` arguments ("mandatory input parameters are not present"), resent verbatim; the fallbacks (`sed`, rewriting the whole file with `write_file`) corrupt the file |
|   V1   | No pip: `pip install -e` fails silently; requests imports the system copy, so edits have no effect                                                                                  |
|   V2   | `inline_snapshot` is missing                                                                                                                                                        |
|   V3   | pytest-httpbin is missing; all of `tests/test_requests.py` errors                                                                                                                   |
|   V4   | Pygments version mismatch causes unrelated test failures                                                                                                                            |
|   V5   | Target test already passes on the original code (local false positive for an empty patch)                                                                                           |`


---

## Question about LoRA
/competitions/gemma-4-developer-agent/discussion/749191 | by  | posted 2026-10-14 08:12 | last comment 2026-11-03 01:18 | 8 comments | 1 votes


**** (2026-10-14 08:21, 2 votes)
In my experiment, adding lora resulted in 11% slower decoding


**** (2026-10-14 08:12, 1 votes)
@Ryan Holbrook - LoRA bundles fail to start on 4xL4 under the official VllmServer path

Setup: adk_submission VllmServer (unmodified build_cmd), gemma-4-31b-it-qat-w4a16-ct/2, ONE adapter, rank 16,
TP=4, max-model-len 32768, gpu-memory-utilization 0.8. Command built by VllmServer:
  ... --enable-lora --max-loras 1 --max-lora-rank 16 --lora-modules main_lora=.../adapters/main_lora
Weights and KV cache load fine (~25 min), then every attempt fails with:
  RuntimeError: CUDA out of memory occurred when warming up sampler with 256 dummy requests.
  Please try lowering `max_num_seqs` or `gpu_memory_utilization`.
Reproduced 3 times (8 adapters x r128, 2 x r16, 1 x r16). The same base bundle without LoRA starts and scores normally.

Questions:
1. What GPU and gpu_memory_utilization does the scoring server use? Is it the same VllmServer.build_cmd?
2. Has any LoRA submission actually started and scored on the current scorer?
3. build_cmd does not pass --max-num-seqs; could it be exposed (or lowered when --enable-lora is set)?
Thanks!


**** (2026-11-03 01:18, 0 votes)
Hi @ryanholbrook ,

Could you help verify whether the LoRA adapter was actually active during scoring for submission 57873732?

Submission details:
- Competition: Gemma 4 Developer Agent
- Submitted: November 1, 2026, 13:54 UTC
- Status: Complete; public score: 0.08
- Base model: gemma-4-31b-it-qat-w4a16-ct
- Root agent setting: adapter: weighted_actions
- Adapter directory: adapters/weighted_actions/
- LoRA rank: 16
- Original ZIP size: 489,845,533 bytes, including adapter_model.safetensors

Our AutoDL evaluation logs show the adapter being loaded and requests being routed to weighted_actions. However, this does not confirm that the adapter's nonzero weight updates were applied in the Kaggle scorer.

I saw the report in discussion 743508 about LoRA weights being reset through duplicate Gemma4 decoder-layer registrations, even when the adapter is reported as loaded.

Could you please confirm:
1. Whether weighted_actions was loaded and remained active during inference for this submission.
2. Whether the scorer version used for this run included a fix for the issue reported in discussion 743508.
3. If this run was affected, whether rescoring is possible or a new submission is required.

Separately, the submission page shows about 61 KiB, while the original download is about 467 MiB. Is that only a display-metadata difference?

I can provide the frozen ZIP hash and adapter configuration if needed. Thank you!ryanholbroo


**** (2026-10-21 08:47, 0 votes)
A scorer-side data point that may help: the same adapter shape scored once and errored once.

Two of our submissions carried the same LoRA shape: rank 16 on q/k/v/o/gate/up/down of all 60 text layers (about 487 MB), routed on the root agent of an otherwise unchanged bundle. The two adapter_config.json files differ only in lora_alpha and base_model_name_or_path.

- 57394236 (10-19): scored normally, no error.
- 57458172 (10-21): no score, "Your notebook hit an unhandled error while rerunning your code", within about 2 to 8 hours.

In the pinned harness, a model-server start failure (ServerStartupError) is not caught and ends the rerun before any task runs, while a server that dies mid-run leaves per-task errors and a score. So our guess is that 57458172 failed at server start (OOM in the sampler warm-up, or the start-up timeout): an adapter of this size seems close to the edge, and the outcome can differ between runs. On our own 4xL4 runs with the pinned wheelhouse, the same files start and serve.

@ryanholbrook, if possible: could you check the log of 57458172 for which of the two it was? It would tell us whether to size adapters down for margin. Thanks!


**** (2026-10-15 18:56, 0 votes)
@ryanholbrook a scorer-side data point, and a concrete fix request.

Submission 57197626 (2026-10-14 23:21 UTC): one rank-16 adapter (q_proj/o_proj, all 60 layers, 57 MB), so build_cmd emits --enable-lora --max-loras 1 --max-lora-rank 16. The scoring run stayed pending for over 12 hours, then ended with "exceeded the allowed runtime", no score.

Submission 57088086 (2026-10-11): the identical bundle without the adapter (same prompt, tools, sampling, eval_config: 28 tool calls / 8 min per task). Scored 0.15.

So this bundle only starts failing when the adapter is present, and it fails by running out the 12 h wall rather than at startup. That matches what Nir and Pierre measured in this thread and in 744331: with --enable-lora the graphs are captured twice and the KV cache drops to ~27.7k tokens at util 0.80, and in 744331 requests that did not fit sat in the waiting queue until max_time_minutes expired. A submission cannot change these flags.

Two things that would unblock LoRA submissions:
1. When --enable-lora is set, pass --compilation-config '{"cudagraph_specialize_lora": false}' (Nir's fix B). Pierre measured it keeps 94% of the base KV cache on 4xL4; Nir measured 45,440 tokens vs 27,712.
2. Could you check the log of 57197626 for the "GPU KV cache size" line and per-task durations, to confirm this is the mechanism?

Happy to share the bundle or rerun anything that helps.


**** (2026-10-15 14:05, 0 votes)
Hi @niraberman,

You might check the Getting Started notebook. It uses the same configuration as the scorer. The key setting for you I think is `os.environ['VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS'] = '1'`. We have seen successful submissions with LoRA adapters up to rank 64.


**** (2026-10-14 21:47, 0 votes)
@ryanholbrook, an independent reproduction of Nir's report, in case it helps.

Setup: our own notebook on Kaggle 4× L4, wheelhouse of 2026-10-12 (swegemma 0.2.11, vLLM 0.19.1), the unmodified VllmServer path at gpu_memory_utilization 0.80, TP 4, max_model_len 32768, gemma-4-31b-it-qat-w4a16-ct/2. One adapter, rank 16, LoRA on q/k/v/o/gate/up/down of all 60 text layers (820 tensors, 245 MB). VllmServer builds --enable-lora --max-loras 1 --max-lora-rank 16 from it. We left VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS unset (the Getting Started notebook sets it to 1).

Result: same failure. Weights and KV cache load (45,488 tokens), CUDA graph capture finishes ("took 4.49 GiB"), then:

RuntimeError: Worker failed with error 'CUDA out of memory occurred when warming up sampler with 256 dummy requests. Please try lowering `max_num_seqs` or `gpu_memory_utilization` ...'
ServerStartupError: Inference server did not become healthy within 1200s.

One data point the other way: a submission of ours with a tiny adapter (rank 4, a single layer, lora_B = 0, like the sample submission) was scored normally on 10-12. So small adapters seem to start, and full-size ones don't.

Questions:
1. Does the scorer set VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=1, as the Getting Started notebook does? If yes, rank-16 adapters should start (at the cost of KV cache: Nir measured 27,712 tokens).
2. If not, is a fix for build_cmd planned (e.g. Nir's cudagraph_specialize_lora: false or a lower --max-num-seqs when --enable-lora is set)?
3. Until then, is there a size limit we should stay under for an adapter to be safe?

Thanks!


> **** (2026-10-15 08:47, 0 votes)
> Follow-up with a rank sweep on the current wheelhouse (v31: swegemma 0.2.11, vLLM 0.19.1), official VllmServer path,
> 4x L4, TP 4, gpu_memory_utilization 0.80, VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS unset, zero adapters:
> - r4, all 60 layers (820 tensors, 58 MiB): CUDA OOM while warming up the sampler with 256 dummy requests.
> - r4, ONE layer (14 tensors, 1 MiB): same OOM.
> build_cmd passes --max-loras 1 --max-lora-rank 8 for both (rank is floored to 8), so adapter size is not the lever.
> @ryanholbrook does the scorer set VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=1 (or --max-num-seqs / cudagraph_specialize_lora=false)?
> Without one of these, any LoRA bundle seems to fail at startup on the current wheel. Thanks!


**** (2026-10-14 08:54, 0 votes)
Follow-up: root cause found and three one-line fixes verified.

Root cause (vllm 0.19.1 source, gpu_worker.py / cudagraph_dispatcher.py): with --enable-lora,
cudagraph_specialize_lora=True captures CUDA graphs twice (no-lora + lora), and graph memory is NOT counted in the
KV budget unless VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=1. The extra ~4.5 GiB/GPU eats the 20% headroom, so the
sampler warmup (which runs after graph capture) OOMs. The base model has one graph set and fits.

Same build_cmd, same single r16 adapter, each config in an isolated process group with GPUs verified free first.
All three start cleanly and serve the adapter:
  A) env VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=1              -> graphs 4.49 GiB (now budgeted), KV 27,712 tokens
  B) --compilation-config '{"cudagraph_specialize_lora": false}' -> graphs 2.41 GiB, KV 45,440 tokens
  C) --max-num-seqs 64                                           -> graphs 1.50 GiB, KV 48,384 tokens

Questions:
1. Does the scorer run this same build_cmd with gpu 0.80 on 4xL4? If yes, LoRA submissions currently fail at startup.
2. Could B (smallest change) be added to build_cmd when --enable-lora is set?
Full logs available on request.


---

## Why not cap submissions to once in two days
/competitions/gemma-4-developer-agent/discussion/755183 | by  | posted 2026-11-02 23:33 | last comment 2026-11-02 23:33 | 0 comments | -1 votes


**** (2026-11-02 23:33, -1 votes)
The current long running submissions are severely restricting experiments. We dont know how much time really the submission notebook takes to run. At present, it is already only one submission per two days. 

To solve the gpu resource constraint, why not cap the submissions to once in two days but ensure there is no queing so that we know how much time it takes to complete the tasks?

However, if the objective is to prevent knowing the exact time it takes to run a submission and thereby prevent probing the private dataset, this wont help.


---

## Public code of my entry: gemma4-swe-agent (Apache 2.0)
/competitions/gemma-4-developer-agent/discussion/755172 | by  | posted 2026-11-02 22:58 | last comment 2026-11-02 22:58 | 0 comments | 0 votes


**** (2026-11-02 22:58, 0 votes)
Sharing the public repository of my entry here, as General Rule 6.b asks for publicly shared competition code:

https://github.com/emamira02/gemma4-swe-agent

It contains the frozen agent bundles (candidates/S1 to S18, including every submitted one, each with its zip SHA), the in-container localization skill and the single-argument heredoc editor, the dev-panel and failure-analysis code, and the localization study behind my paper-track submission. Licence: Apache 2.0. NOTICE credits the public notebooks whose prompts I adapted (Budget-Aware Coding Agent V10, SuperAgent, Shape of Doubt) and the Budget-Fit baseline. No competition data is included: scripts/fetch_data.sh downloads it from Kaggle.


---

## Stage 1 of wrapper engineering: settings, budgets and lessons
/competitions/gemma-4-developer-agent/discussion/755066 | by  | posted 2026-11-02 18:35 | last comment 2026-11-02 18:35 | 0 comments | 0 votes


**** (2026-11-02 18:35, 0 votes)
Before changing prompts or adding sub-agents, I wanted to see how much the settings mattered. I used a basic wrapper and kept the competition model unchanged.

The four main studies covered **376 attempts across 40 public tasks**. These are local evaluation results, not leaderboard scores. Repeating a task tells us about consistency, but does not give us another independent problem.

## Setup

The agent used Gemma 4 31B QAT with six native tools for commands, reading, editing, writing, status and submission. There was no LoRA, delegation or compaction. The prompt asked for a correct repair, targeted checks and preservation of existing behavior.

Kaggle notebooks ran on four L4 GPUs with a 32,768-token context. Two isolated workers processed tasks independently. I saved requests, tool calls, command output, patches, grading and timings.

Tasks followed [Dmitrii Gluzdov and Busya PRIME's soundness audit, version 10](https://www.kaggle.com/datasets/dmitriigluzdov/gemma-4-task-soundness-and-local-results/versions/10). Each selected task also needed a passing reference patch and a failing empty patch in my environment. Reference solutions were kept out of agent inputs. Launches that failed before inference have no agent score.

## Sampling

The first sweep had 130 attempts: five tasks, twice each, across 13 profiles. The second had 126: seven different tasks, three times each, across six profiles. Each variation changed one setting from its study's control.

| Comparison | First study | Second study |
|---|---|---|
| Temperature 0 vs 1 | 7/10 vs 7/10 | 11/21 vs 12/21 |
| Output 4k / 6k / 8k | 7/10 / 6/10 / untested | 10/21 / 12/21 / 10/21 |
| Thinking 2k vs 4k | 6/10 vs 6/10 | 10/21 vs 10/21 |
| Top-p 0.5 / 0.8 / 1 | 3/10 / 4/10 / 6/10 | Untested |

Here, k means 1024 tokens. The studies used different tasks and defaults, so compare settings within each column.

Temperature 0 was faster than 1 on average in both comparisons, with close scores. I kept 0 as the default. Output 8k showed no dependable advantage over 6k. The second study's 6k profile peaked at 3,689 tokens, so its score does not show that larger output was needed. Doubling thinking tied on score twice; it was slower once and slightly faster once.

Thinking uses the total output allowance. I saw responses spend the entire 4k ceiling on reasoning without producing an action. More thinking needs enough room for the edit too.

## Larger comparisons

Next came 15 tasks, three repeats each, with 20 minutes per attempt:

| Profile | Passes | Mean agent time |
|---|---:|---:|
| A: temperature 0, output 4k, thinking 4k | 24/45 | 470.10s |
| B: temperature 1, output 6k, thinking 2k | 23/45 | 437.26s |

Both solved nine task types. On the 22 matched attempts both passed, B used 23.6% less evaluator time. The small score difference does not establish a quality winner, and three settings changed together.

I then tried temperature 0, output 6k, thinking 2k and top-p 1 on 30 tasks, with ten minutes and 50 model requests each. It passed **12/30**, averaging 346.49 agent seconds. Eighteen tasks were labelled complex. This was a different cohort; on 14 overlapping first-round tasks, it matched B at 7/14.

## Budgets

Looking back through the histories, every B success and every success in the latest run finished within 45 model requests. Forty would interrupt several successful histories. I chose 50 for some margin. These are completion counts, not regraded earlier patches.

Of 7,424 completed commands, 24 exceeded 120 seconds and all failed or timed out. A timeout could still discard useful diagnostic output. Three successful checks took about 104 seconds, which argues against a universal 60-second cap.

The next experiments will use **10 minutes, 50 model requests and 120 seconds per command**. The 12/30 run had no separate command timeout, so the new cap still needs confirmation.

There is also the full submission budget: 120 tasks in 12 hours leaves six minutes each before overhead. A ten-minute task ceiling alone cannot guarantee completion.

## Next

The recurring failures were wrong assumptions, incomplete APIs, malformed calls, repeated submissions and exhausted context. Stage 2 will test better editing tools, focused exploration, recovery and independent review. Each change needs to improve correct patches without spending away the runtime needed for the remaining tasks.


---

## Submission pending for 29+ hours
/competitions/gemma-4-developer-agent/discussion/754845 | by  | posted 2026-11-02 01:13 | last comment 2026-11-02 18:20 | 1 comments | 0 votes


**** (2026-11-02 01:13, 0 votes)
Hi,

My submission from ref 57849011 has been Pending for about 29 hours, with no score or error. My config should finish in about 10–11 hours. Earlier submissions were scored within 12–14 hours.

Is the scoring queue delayed, or could something be wrong with this submission? Since only one submission can be pending at a time, it’s blocking my next one.

Thanks!


**** (2026-11-02 18:20, 0 votes)
It got submitted in the end. But, do we have an expected time in which these submissions are supposed to get graded?


---

## Will private leaderboard evaluation use multiple runs to reduce variance?
/competitions/gemma-4-developer-agent/discussion/754295 | by  | posted 2026-10-30 22:26 | last comment 2026-11-02 09:38 | 3 comments | 12 votes


**** (2026-10-30 22:26, 12 votes)
Hi @ryanholbrook and team,

Could you clarify how randomness will be handled in the final private leaderboard evaluation?

Participants have reported different public scores when resubmitting byte-identical ZIP files. Although evaluator updates may explain some differences, stochastic agent behavior could also affect rankings, especially with roughly 60 tasks in the private split.

Specifically:

Will each selected submission run once per private task, or will it be evaluated across multiple independent runs/seeds?

If multiple runs are planned, how many, and will the final score be the average success rate?

Will private scores use the results already generated during submission scoring, or will selected submissions be rerun after the deadline?

If the current plan is a single run, would you consider averaging several runs for the final evaluation? I understand the compute cost, but this could help reduce the influence of a few lucky or unlucky trajectories on the final standings.

Thanks for clarifying!


**** (2026-11-02 07:08, 1 votes)
Kaggle has never done that and highly likely never will.

I think making your solution stable is one of the intended challenges


> **** (2026-11-02 09:38, 0 votes)
> You dont have to share if its too revealing but do you get your score reliably or does it fluctuate a lot?


**** (2026-11-02 09:32, 0 votes)
How many tasks are in the final evaluation? 60 right. So the variance should be around the same as for the test set.


---

## anybody crossed 0.2 threshold
/competitions/gemma-4-developer-agent/discussion/754811 | by  | posted 2026-11-01 19:24 | last comment 2026-11-02 04:40 | 1 comments | 1 votes


**** (2026-11-02 04:40, 1 votes)
The best public notebook is what you want. But it's very unstable


**** (2026-11-01 19:24, 1 votes)
Anybody crossed >= 0.2 threshold just by prompting without finetuning or training any lora adapters on top of that


---

##  stuck in 'Notebook Running' 
/competitions/gemma-4-developer-agent/discussion/754023 | by  | posted 2026-10-30 03:33 | last comment 2026-11-01 20:22 | 4 comments | 1 votes


**** (2026-10-30 03:33, 1 votes)
"Hi admins, my submission has been stuck in 'Notebook Running' for over 24 hours and blocking my team from submitting (Your team already has 1 pending submissions). Could you please help clear the zombie job? My team name is: [SeanMmmmm]"


**** (2026-10-30 05:28, 1 votes)
well, my notebooks normally runs for 28-30 hours...but i got a score at the end of the day.


**** (2026-11-01 20:22, 0 votes)
Same problem


**** (2026-11-01 17:22, 0 votes)
Hi hosts — same issue here, and I need the stuck pending job cleared so I can submit again.

- Kaggle username / team: dxnnnnn
- Competition: gemma-4-developer-agent
- Notebook g4da-submit-v1 Version 1 has been stuck in Notebook Running / Pending since 2026-11-01 01:48 UTC+8
- There is no cancel control in the UI, and the pending run blocks new submissions. I need to submit g4da-submit-v2.
- I already emailed support@kaggle.com from 971458759@qq.com around 01:07 UTC+8 on 2026-11-02.

Could an admin please cancel or clear that pending submission? Thank you.


**** (2026-10-30 03:58, 0 votes)
Same with my submission


---

## Request to Hosts: Fix Harness Continuation Nudge, Context Duplication & Compaction Bugs Breaking complex agent orchestrations
/competitions/gemma-4-developer-agent/discussion/754636 | by  | posted 2026-10-31 23:17 | last comment 2026-11-01 12:17 | 3 comments | -2 votes


**** (2026-10-31 23:17, -2 votes)
Hi @ryanholbrook and the competition team,


After extensive debugging comparing the official starter agent (`0.08`) against multiple 2-stage `SequentialAgent` pipelines (which consistently drop to `0.06–0.08` despite deterministic localization scripts, problem briefs, and strict exit gates), we traced the score collapse to **four structural incompatibilities between `swegemma`’s runner/compaction harness and Google ADK’s `SequentialAgent`**:

### 1. Continuation Nudges Restart `SequentialAgent` from Stage 1 (`sub_agents[0]`)

* In `agent_runner.py` (§5.3 of [`HARNESS_README.md`](https://www.kaggle.com/competitions/gemma-4-developer-agent/data)), when a turn ends without `submit_patch()` (e.g., hitting `max_output_tokens`, a truncated `<|tool_call>` tag, or an intermediate text response), the outer `while True:` loop injects a `nudge_prompt` into a new `runner.run_async(...)` call on the root agent.

* In [ADK’s `SequentialAgent._run_async_impl`](https://github.com/google/adk-python/blob/main/src/google/adk/agents/sequential_agent.py), a new `run_async` invocation **restarts execution from `sub_agents[0]`** rather than resuming the active downstream solver agent.

* Worse, if `sub_agents[0]` uses `include_contents: none` ([google/adk-python#7813](https://github.com/google/adk-python/issues/7813), [google/adk-python#931](https://github.com/google/adk-python/issues/931)), `_get_current_turn_contents` strips the initial task prompt and feeds *only* the 1-line continuation nudge to Stage 1—causing Stage 1 to re-run blind, overwrite `session.state[output_key]` with garbage, and burn 60–90 seconds + multiple tool calls before the solver regains control.

### 2. Shared-Session Context Duplication Triggers Premature, Lossy Compaction

* When Stage 1 passes a structured brief via `output_key` into Stage 2’s system prompt, setting `include_contents: default` on Stage 2 causes ADK to **also** replay all of Stage 1’s raw tool calls, 9,000-char script JSON outputs, and final text in `session.events` ([google/adk-python#2207](https://github.com/google/adk-python/issues/2207)).

* However, setting `include_contents: none` on Stage 2 wipes the initial user message (workspace tree and harness rules) and breaks across continuation nudges.

* Because Stage 2 starts with **10,000–12,000 duplicated tokens**, it crosses `token_threshold = 14,336` / `compaction_interval = 5` ([Discussion #744692](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744692), [Discussion #744794](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744794)) after just 1–2 tool calls. Compaction then summarizes away the exact file lines and tool outputs the solver just read, destroying multi-step editing flow.

### 3. Single Shared Clock & Tool Counter Penalizes Multi-Stage Pipelines

* Because a single `EvaluationBudget` clock and tool counter covers the entire pipeline ([Discussion #747519](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747519)) inside the strict 12-hour total scoring window (~5.5 min/task safe cap on 4× L4 GPUs, [Discussion #746250](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/746250)), even 45–60 seconds of Stage 1 localization + compaction summarization pushes Stage 2 below the ~4.5-minute threshold where half of solvable tasks time out ([Discussion #750350](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/750350)).

### Why Fixing This Matters for the Competition’s Core Objectives

1. **Both Agent Architecture and LoRA Are Intended Pillars**: The competition schema (`adk-submission`) was specifically engineered to support rich declarative ADK workflows (`SequentialAgent`, `LoopAgent`, `ParallelAgent`, and `skills/`).

2. **A Single `system.md` Should Not Be the Ceiling for Agent Design**: One month into the competition, **zero** sequential or multi-stage agent configurations work competitively on the public scored notebooks. The highest-scoring public non-LoRA notebooks (~`0.22`) rely on a single basic `LlmAgent` and a one-page `system.md`. If prompt-only beats LoRA, awarding a **$65,000** prize for a single-page `system.md`—simply because multi-agent orchestration is blocked by harness plumbing—defeats the purpose of an agent engineering competition.

3. **Narrow Coding LoRAs Alone Offer Limited Scientific Novelty**: Frontier models are massive primarily because they serve 50+ diverse industries simultaneously. Specializing a 31B model via SFT/LoRA to narrowly solve Python repository issues is a well-understood domain-distillation exercise rather than a breakthrough in autonomous agent design. True innovation on consumer hardware requires **structured multi-agent orchestration, deterministic tooling, and verification gates** working alongside the model.

### Requests to the Host Team

* **Target Continuation Nudges at the Active Leaf `LlmAgent`**: In `agent_runner.py`, if a `SequentialAgent` turn exits before `submit_patch()`, route continuation nudges to the currently active sub-agent (or preserve `SequentialAgentState` across nudges) rather than restarting `sub_agents[0]`.

* **Preserve Recent Raw Tool Outputs During Compaction**: Keep the last $N$ tool responses verbatim when `EventsCompactionConfig` triggers, and exclude prior sub-agents’ internal skill/script outputs when `output_key` is already used to pass state.

* **Decouple Skill Script Setup Overhead or Allow Per-Agent Budgets**: Support per-sub-agent `max_tool_calls` / `max_time_minutes` in `sub_agents/*.yaml` so a Stage 1 agent does not starve the solver agent.

Note: "We" refers to myself and Gemini Argon!!😀


**** (2026-10-31 23:39, -1 votes)
Also Note: Though agent_tools configuration can overcome context window / summary cmpaction problems  but still complex agent orchestrations are not possible, and sequential agents can as well be removed from agent harness, when they can't be used.


**** (2026-11-01 09:50, 0 votes)
I just wanted to point out that even though above limitations are true (I've run into them few weeks ago too) from my perspective it would not be fair to fix them at this point in the competition, given the time and resources sunk into going around them. In practical sense above problems, plus the inability to change compaction settings and compaction prompt almost forces the design into single agent solution (with small exceptions) and sft / other training methods.


> **** (2026-11-01 12:17, 1 votes)
> I appreciate your reply. Others who downvote a post should first make their view points clear by commenting -  I thought may be there exist simple solutions to sequential agent problem that allows its usage as a possible reason for the downvotes. As for single agent solutions, I wonder what that would serve for the hosts' competition objectives!


---

## Different public scores from an identical submission ZIP - reproducibility question
/competitions/gemma-4-developer-agent/discussion/750521 | by  | posted 2026-10-18 17:28 | last comment 2026-11-01 08:18 | 7 comments | 5 votes


**** (2026-11-01 08:18, 1 votes)
Hi organizers and everyone,

I resubmitted a byte-identical submission.zip to measure leaderboard noise, and the two runs differ far more than sampling noise would explain:

- Submitted 2026-10-27 16:45 UTC ("v0.3 budget-fit, first submission", ref 57707644): public score 0.18
- Submitted 2026-10-31 03:06 UTC ("v0.3 resubmit #2 (same file, noise check)", ref 57824740): public score 0.01

Both files have sha256 556432843f7cb935d2d90662ddf12a127fdb9616ea169036e02b6218e010339e, and both runs completed without error. With ~58 public tasks, 0.18 is about 10 tasks and 0.01 is 0–1 task.

For reference, three local runs of a closely related version on 121 public tasks resolved 50, 50 and 47 tasks (SD ≈ 2), and other community reports put same-ZIP leaderboard variation at a few tasks. A ~10-task drop looks like most tasks never ran normally, rather than unlucky sampling.

One candidate I've seen on the forum is the reported tool-parser loop on array-valued tool arguments that can freeze the inference server for the rest of the run; if that happened early, later tasks would fail quickly while the submission still completes. I can't confirm this from my side, since participants don't see run logs.

Could you check:
1. Whether the inference server stalled or crashed during submission 57824740 (e.g., long gaps with no model requests, or most tasks ending with empty patches)?
2. If it was an infrastructure or parser failure, whether such runs can be re-scored or excluded?
3. Whether there is any way for participants to see per-task status or runtime logs for a scored submission, so we can tell agent regressions from platform failures?

Happy to share more details. Thanks!


**** (2026-10-18 17:28, 5 votes)
Hi everyone,

We resubmitted a byte-for-byte identical agent ZIP and obtained different public scores, despite making no changes to the prompts, model settings, tools, or budgets.

Our configuration uses temperature 0.2, with no explicit generation seed. We understand that fixing temperature does not guarantee identical generations, and that different agent trajectories or wall-clock execution times can affect the final patches.

This makes it difficult to compare versions. For example, we might conclude that a submission scoring 0.22 is better than one scoring 0.15, while part or potentially all of that difference could come from run-to-run variability rather than a genuinely better agent. These numbers are illustrative; we are not claiming that any particular leaderboard result is due to chance.

Could the organizers clarify:

Are generation seeds fixed during scoring, and are submission-provided seeds honored?

What reproducibility should we expect, including with temperature 0 and a fixed seed?

Have evaluation updates affected score comparability across dates?

Would evaluation across a fixed set of seeds, reporting the mean and spread, be feasible?

Could aggregate timeout and empty-patch counts be shared without exposing hidden tasks?

Have other participants observed different scores when resubmitting exactly the same ZIP?

We are not assuming a specific cause; we would appreciate guidance on reliably distinguishing agent improvements from execution variability.

Thanks!


**** (2026-10-18 18:03, 0 votes)
It is not trivial to make LLM inference deterministic, fixing a seed won't help. Float arithmetic is not associative etc etc


> **** (2026-10-18 21:06, 1 votes)
> Yes, I’m aware that a fixed seed doesn’t guarantee determinism, and that an LLM can take different reasoning paths when solving the same problem.
> 
> My point is about the competition: if the exact same submission produces noticeably different scores across runs, how can we reliably decide whether one agent is better than another? A higher score could reflect a better approach, a more favorable run, or both. That’s the comparison issue I’m raising


> > **** (2026-10-19 00:18, 1 votes)
> > yes, this is important - the question is whether we should be putting efforts to make the agent pipeline reliable and consistent for bug fixing or is it due to other environment variables including non-determinism that we dont have a control. If this is so, while in the real world, we can simply keep running the agent till it fixes the bug, in the competition scenario, evaluation becomes non-deterministic


> > **** (2026-10-19 03:20, 1 votes)
> > You can't from the public leaderboard score. It's nondeterministic, so most of the leaderboard is chance on some tasks flipping correct on a lucky run. Same behavior is observed running locally -- multiple runs of the same exact agent on the dev set show a decent swing in either direction from run to run with a ceiling determined largely by task difficulty.


> **** (2026-10-18 23:05, -2 votes)
> @samson8 were you able to achieve 0.24 on leaderboard after finetuning or just optmizing the prompts, skills and subagents. 
> 
> I am new to ai agents, your input will really help me.
> 
> Thanks!


> **** (2026-10-30 11:25, 0 votes)
> Defeating Nondeterminism in LLM Inference
> 
> https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference


---

## Clarification: Are model adaptation methods other than LoRA allowed?
/competitions/gemma-4-developer-agent/discussion/754594 | by  | posted 2026-10-31 17:18 | last comment 2026-10-31 17:18 | 0 comments | 0 votes


**** (2026-10-31 17:18, 0 votes)
Could the organizers clarify whether submissions support any of the following?

1. Full fine-tuned checkpoints of an allowed Gemma 4 model.
2. Checkpoints with LoRA weights merged into the base model.
3. Other PEFT methods, such as DoRA, IA³, or prefix tuning.

Or must all weight adaptations be submitted exclusively as PEFT LoRA adapters applied to the organizer-provided base model?

The submission tree mentions “LoRA adapters or model weights,” while the detailed instructions describe only LoRA adapters. Please clarify both competition eligibility and scoring-harness support.


---

## Which public tasks cannot pass in the scorer's sandbox? Four questions about the grading image
/competitions/gemma-4-developer-agent/discussion/754586 | by  | posted 2026-10-31 16:42 | last comment 2026-10-31 16:42 | 0 comments | -3 votes


**** (2026-10-31 16:42, -3 votes)
I ran the public tasks with their own gold patches through the harness (Docker backend, `network_mode none`, `python:3.13-slim`). Once the test dependencies are in place most of them pass, but a fixed set never does, and the failures come in three kinds. I want to know whether the scorer behaves the same way, so everyone can measure against the same set of tasks.

## Tasks that fail with the gold patch

| Tasks | Log line | What I think is going on |
|---|---|---|
| requests_6589, 6592, 6629, 6757, 7328, 7433, 7502, 7505 | `OSError: [Errno 101] Network is unreachable` | The tests open a connection to an outside address and expect a timeout. With no network the connect fails at once. |
| fastapi_14186 | one required test is `@needs_pydanticv1`, the other `@needs_pydanticv2` | Both come from the test patch, and they cannot run in the same environment. A skipped required test counts as a fail. |
| rich_3486 | one required test has `skipif < 3.11`, the other `skipif >= 3.11` | Same situation. |
| rich_3472 | `assert 'Foo(\n    ba...' == 'Foo(bar=Attr...'` | Python 3.13 formats the `AttributeError` message differently from 3.12. |

## Questions for the organisers

1. Which pytest version is in the pre-seeded scoring image? `Dockerfile.sandbox` installs pytest without a pin, so the version depends on the build date. A `pip freeze` of the image, or a pinned digest, would settle this.
2. Does scoring use the Docker backend with `network_mode none`, or the subprocess backend? The two differ on exactly the requests cases above.
3. Do the hidden tasks carry `FAIL_TO_PASS` and `PASS_TO_PASS` lists, or are the required tests taken from the test patch as in the public code? This decides whether a skipped required test fails a task.
4. Can you confirm that the tasks above cannot pass in the scorer's environment, or publish the list of public tasks that your own gold run passes? You have said the hidden set validates at 100%. The same list for the public set would give everyone the same local denominator.

Thanks. I can share the per-task logs if that helps.


---

## Why does nobody have a score of over 0.24?
/competitions/gemma-4-developer-agent/discussion/752848 | by  | posted 2026-10-26 15:09 | last comment 2026-10-31 07:11 | 10 comments | 11 votes


**** (2026-10-30 08:25, 4 votes)
The guy above got 0.29, what method do you think he used?


**** (2026-10-26 15:09, 11 votes)
A score of 0.24 would be like 2 patches passing every 10. That just seems like terrible agentic performance. I think its the model we have to use being weak, because how can everything everyone tries just plateau to an objectively bad performance at the repo level tasks this model is supposed to work on?


**** (2026-10-26 17:51, 9 votes)
It's a hard task. Look at the previous [Konwinski Prize competition
](https://www.kaggle.com/c/konwinski-prize). The winner solved 9 out of 120 problems. Now we have 14 out of 58 and we are not even near the end.

I think 0.31 is pretty reachable


> **** (2026-10-27 10:35, 11 votes)
> It feels like part of it being hard is the weird configuration they force upon us. Not being able to configure compaction prompt  and/or compaction settings, the bugs that were initially in the harness etc. Lot's of hours lost on dancing around the setup, instead of squezing last bit of performance from the model.


**** (2026-10-27 18:21, 0 votes)
Do you think the problem is that the model itself is too weak? I've tried building more complex agent architectures by incorporating research from the Software Engineering (SWE) field, but the scores still haven't improved much. Do you think I should focus on architectural design or LoRA fine-tuning?


> **** (2026-10-29 12:02, 0 votes)
> Yes. i also tried doing this. I tried to use the framework from the mini-swe agent to improve my score. But the problem I found was that the Gemma 4 model behaves similarly no matter what the system prompt is and repeats the same errors over and over again even though it seems to realize it is making mistakes (especially with writes). 
> I do think this model is very weak. But that's probably part of the challenge...


**** (2026-10-26 18:35, 0 votes)
True... had the same question, why no one can break 0.24 score for so long


**** (2026-10-26 17:04, 0 votes)
Did you debug the harness, I think there are a lot of issues with the Harness I believe someone found some pretty significant bugs down below. I ran all 129 tasks this weekend on the Kaggle side and I was doing much better on the 129 than I thought because I assumed I was only landing Rich tasks. But landing about 30%ish across the whole board. I was building to validate in Colab but Blew my budget in like 15 minutes. So that was worthless.


> **** (2026-10-26 17:13, 0 votes)
> can you tag the discussion you speaking of?


> > **** (2026-10-26 17:55, 3 votes)
> > He talks about some wheel issues for public tasks. Gold patches are not working for all public tasks, but all private gold patches are correct, since hosts have properly verified them. 
> > 
> > You can find some EDA [here](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/751487)


> > **** (2026-10-31 07:11, 0 votes)
> > Thanks, that clears it up: the unsolvable cases are a public-env artifact, not a hidden-set property.
> > 
> > Since you asked earlier about locating vs. editing time, here is what we measured on 163 runs: the gold file is opened by call 2-3 in ~84% of runs, but the first edit lands at ~106 s in solved runs vs ~183 s in failed ones, and post-edit time is ~80 s in both. Prompt rules to edit earlier were mostly ignored.
> > 
> > Curious whether your jump past 0.24 came from shrinking that find-to-commit gap, and if so, whether it was config/tooling rather than prompt wording?


---

## New Gemma 4 Models Available: 12B, E4B, and E2B
/competitions/gemma-4-developer-agent/discussion/748287 | by  | posted 2026-10-11 11:48 | last comment 2026-10-31 05:00 | 38 comments | 37 votes


**** (2026-10-11 11:48, 37 votes)
Hi everyone,

We've added support for [several smaller Gemma 4 variants](https://www.kaggle.com/models/google/gemma-4/other/). You can now use any of the following models for your agents:
- `gemma-4-31b-it-qat-w4a16-ct`
- `gemma-4-12b-it-qat-w4a16-ct`
- `gemma-4-e4b-it-qat-w4a16-ct`
- `gemma-4-e2b-it-qat-w4a16-ct`

We don't support mixing variants within a submission, however. Every agent and subagent in your submission must use the same variant (though they can attach different LoRA adapters.)

These smaller models open up some new strategies:
1. **More test time compute:** Inference is faster and memory burden lower so you can execute more and longer reasoning turns and iteration cycles. You could also experiment with using `ParallelAgent` for concurrent LLM calls (though tool calls are still executed sequentially).
2. **Faster and more accessible LoRA finetuning:** Experiment with different setups more quickly and on more accessible GPUs. We provide L4x4s for use in interactive notebooks, but adapters can now be finetuned on a wider variety of consumer hardware.
3. **More specialized agents:** Smaller models use smaller LoRA adapters, so you can include more of them in your submission.

We're excited to see what you build!


**** (2026-10-16 23:57, 2 votes)
Hi @ryanholbrook,

Thank you for adding the smaller Gemma 4 variants, clarifying the 12B `--hf-overrides`, and fixing the recent weight-loading issue.

We've successfully run **Gemma 4 12B (Other / v2)** using the **unchanged official Wheelhouse V31** on L4×4 with Python **3.12.13**. Offline installation, vLLM startup, one HTTP 200 completion, and cleanup all succeeded.

However, we observed a compatibility difference between Kaggle Notebook environments:

- **Python 3.13.15**, environment pinned to 2026-10-03: nine wheels in official V31 were tagged `cp312-cp312` and incompatible. Our preflight stopped before installation.
- **Python 3.12.13**, environment pinned to 2026-07-01: the same official V31 wheels worked, and our 12B inference smoke passed.

Could you clarify two points?

1. **Which Kaggle Notebook Python/container environment is officially supported for Wheelhouse V31?** Will the Getting Started documentation specify a compatible pinned environment, or is Python 3.13 compatibility planned?
2. **Is the production scorer's 12B model-serving environment aligned with the supported public setup**, particularly the relevant wheelhouse fixes and vLLM dependencies, or does it use a separately managed runtime?

We understand that the scorer already includes the 12B override and that the smaller variants use the same scoring conditions as 31B.

We have not yet run the official compiler or scorer for this candidate, so we're **not claiming that private scoring is broken**. Our concern is ensuring reproducible development and avoiding compatibility surprises at submission time.

Thanks for your guidance!


**** (2026-10-11 14:48, 5 votes)
Hi, here is a well-known issue, already fixed on v2.** upstream, but as we are using still v1.36  . Parallel agent is not gonna work : https://github.com/google/adk-python/issues/7324#issuecomment-5868428151


> **** (2026-10-11 14:48, 0 votes)
> This is very easy to reproduce on the current sdk of our competition


> **** (2026-10-11 16:23, 0 votes)
> Ah, okay, good catch. I think it's too risky to attempt a migration to ADK v2 at this point, but good to know.


> > **** (2026-10-11 17:25, 1 votes)
> > Yeah, I think it'd be enough if you can patch this specific issue. Thank you


> > **** (2026-10-14 18:49, -1 votes)
> > Seconding a request for a backport or bespoke patch. `ParallelAgent` with tool calls is relatively important: even a simple repo search (natural language question -> list of file sections) subagent can take ~90 seconds while generating only 3000 tokens. It's much harder to keep under the 12 hour limit without this.


> **** (2026-10-13 17:02, 0 votes)
> there ~~is a~~  are workarounds (ex - keeping sub-agents tool-free)


**** (2026-10-11 22:07, 4 votes)
I am very excited about this change. especially since the project says run on consumer hardware and I know very few consumer that have 80GB of VRAM laying around.


**** (2026-10-14 02:39, -1 votes)
Hi Team,

I am reaching out to highlight an issue with my recent submission runtimes in The Gemma 4 Developer Agent Competition.

Previous Submissions: My last 2 submission attempts unexpectedly failed with a Notebook Threw Exception status after long evaluation runs.

Current Submission: My latest submission has been actively in the "Scoring..." phase for over 6+ hours continuously.

Notebook Title: Gamma4_DeveloperAgent_for submission_V4.0.0.0_ADK - Core-4_Intelligent_Software_Engine_V4.0.0.0

I kindly request to look into this matter.

Thank You.


> **** (2026-10-14 14:41, 0 votes)
> same things happening with me! when I submit same submission of (31B model) with (12B) I am getting it


> > **** (2026-10-14 14:56, 0 votes)
> > Which wheelhouse version are you using?


> **** (2026-10-14 15:14, 0 votes)
> I had submission for over 24 hours and at the end it finished successfully


**** (2026-10-31 05:00, 0 votes)
My first submission (10 min and 60 tool calls per task in eval_config.yaml) ended with Notebook Timeout. Locally my agent averages about 6.3 min per task on the public tasks. Could you share how many tasks are in the hidden test set, and whether the scorer runs tasks one at a time or in parallel? That would help set per-task budgets that fit the 12 hour limit. Thanks.


**** (2026-10-29 23:37, 0 votes)
hi @ryanholbrook , if you have time please take a look at https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/753973, thanks! i encountered this issue when i started to play with E4B.


> **** (2026-10-30 17:49, -1 votes)
> the repro also hangs on our local vllm1012 build


**** (2026-10-21 17:50, 0 votes)
Hi @Ryan Holbrook and team,

Two of my submissions failed today with "Notebook Threw Exception", each after a 2 hours of runtime is it normal?


**** (2026-10-21 17:41, 0 votes)
hi @ryanholbrook , just wanted to know if the logs for submitted zip files is accessible? If yes could you let me know where can i find it? My submission threw error after running for couple of hours.


**** (2026-10-21 10:48, 0 votes)
he hello guys can sombudy help me i start a learning a aiml


**** (2026-10-15 15:43, 0 votes)
perhaps, Overview - Model Selection and LoRA Adapters could be updated correspondingly?


> **** (2026-10-15 16:42, 0 votes)
> Will do, thanks!


> > **** (2026-10-21 10:50, 0 votes)
> > hey hello  i am a biggener can you take me a advice how to start a machine laerning


**** (2026-10-13 09:23, 0 votes)
Kaggle Error on submission despite successful notebook execution

My Gemma 4 Developer Agent submission (notebook345c631ad8, Version 5.1) received a "Kaggle Error."

The notebook completed successfully in 27.8 seconds. It generated `submission.zip` containing the required `agent.yaml` and passed its local validation checks.

My earlier submission (Version 3) completed evaluation successfully with a public score of 0.10.

Could you please check whether this latest submission failed due to a scoring infrastructure issue or a specific configuration problem, and advise whether it can be rerun?


**** (2026-10-12 19:52, 0 votes)
@ryanholbrook 

Thanks for the --hf-overrides snippet. 

With it, gemma-4-12b-it-qat-w4a16-ct (Other / v2) still fails to start for us on the public wheelhouse (vllm 0.19.1, 4× L4, TP 4, max_model_len 32768), now during weight loading:  (Worker_TP0) ERROR [multiproc_executor.py:857] KeyError: 'vision_embedder.patch_dense.weight' 

The checkpoint's model.safetensors contains 9 model.vision_embedder.* tensors, and Gemma4ForCausalLM.load_weights in this vLLM build skips only audio_tower., vision_tower., embed_audio. and embed_vision. prefixes. Serving a copy of the checkpoint without those 9 tensors starts fine, but a submission can't do that, since the scorer loads the model itself.

*Two questions before we spend a submission on the 12B:
1. Does the scorer's vLLM load this exact checkpoint (Other / v2) with the override, i.e. has a 12B submission been scored end to end?
2. Will the Getting Started notebook / wheelhouse get the matching fix, so the public harness can run the 12B as the scorer does?*

Thanks!


**** (2026-10-12 17:38, 0 votes)
Thanks for adding these new models. We tried to load the 12B locally and want to check whether we’re missing something.

We're also seeing @smartmanoj's result: we see the same KeyError: 'vision_embedder.patch_dense.weight' on v30 with the documented --hf-overrides. Could you confirm whether production applies anything beyond that override (a skip-list patch in Gemma4ForCausalLM.load_weights, a filtered checkpoint, or a newer vLLM)? A one-line yes/no would tell everyone whether a 12B submission can score.


> **** (2026-10-12 19:56, 0 votes)
> Fixed in the most recent wheelhouse. Thanks for the heads up.


**** (2026-10-12 16:21, 0 votes)
Hi, @ryanholbrook,
This is Ragesh, Here you said about ParallelAgent for concurrent LLM calls so here you mean that we can load tasks in parrallel and solve concurrently which helps a lot to make improvements and time allocation per task. Please clarify this context to design a architecture.


**** (2026-10-11 19:03, 0 votes)
thx appreciate the options this opens.


**** (2026-10-11 18:30, 0 votes)
@ryanholbrook  One question about timing: is the scorer's vLLM server configured exactly like the Getting Started notebook (tensor_parallel_size=4, max_model_len=32768, gpu_memory_utilization, prefix caching and any max_num_seqs settings), for every variant?


**** (2026-10-11 16:12, 0 votes)
Hi @ryanholbrook Thanks! Two quick clarifications that probably matter for everyone:

1. Are submissions with the smaller variants scored under the same conditions as 31B (same 4×L4 hardware, same 12-hour total limit, same per-task budgets from eval_config.yaml)?

2. For LoRA on the smaller variants, which base weights should adapters be trained against, so they match the quantized model used at scoring time?


> **** (2026-10-11 16:25, 0 votes)
> 1. Yes, everything is the same.
> 2. The unquantized variants are on the same page: [Gemma 4](https://www.kaggle.com/models/google/gemma-4/transformers).


> > **** (2026-10-11 18:22, 0 votes)
> > Hi @ryanholbrook,
> > 
> > Thanks again for clarifying the support for the new Gemma 4 variants!
> > 
> > Could the team please update `HARNESS_README.md` to reflect the latest competition configuration?
> > 
> > In particular, Section 3.1–3.2 still states that gemma-4-31b-it-qat-w4a16-ct is the only allowed competition model (`ALLOWED_MODEL_NAMES`).
> > 
> > It would also be helpful to confirm in the updated documentation:
> > 
> > 1. The complete list of permitted quantized model identifiers.
> > 2. Whether the 32,768-token context limit and vLLM serving configuration remain unchanged for all variants.
> > 3. Whether the current submission validator and local evaluation tools support all four variants.
> > 4. Any model-specific LoRA compatibility or configuration requirements.
> > 
> > An updated README would help participants avoid validation errors and ensure reproducible experiments.
> > 
> > Thanks for your support!


**** (2026-10-11 14:24, 0 votes)
Thanks for adding the smaller variants! We tried gemma-4-12b-it-qat-w4a16-ct (Other / v2) with the current wheelhouse (vllm 0.19.1, adk-submission 0.2.13, swegemma 0.2.11) and VllmServer (tool_call_parser and reasoning_parser gemma4, TP 4, bf16, max_model_len 32768). The server exits during startup (profile_run):

ValueError: Expected hidden_size to be 3840, but found: 256 raised in self_attn.v_norm (vllm/model_executor/layers/layernorm.py), via vllm/model_executor/models/transformers/multimodal.py.

The 12B's config declares Gemma4UnifiedForConditionalGeneration (model_type gemma4_unified), while the 31B is Gemma4ForConditionalGeneration. vLLM 0.19.1 seems to fall back to its Transformers backend for the unified architecture, where the per-head v_norm gets the model's hidden_size. Is an updated vLLM wheel planned for the scorer, or is there a recommended way to serve the 12B? Thanks!


> **** (2026-10-11 14:39, 3 votes)
> I'll update the Getting Started notebook on Monday to illustrate. The tl;dr is that you need to add:
> 
> ```
> MODEL_VLLM_EXTRA_ARGS: dict[str, tuple[str, ...]] = {
>     'gemma-4-12b-it-qat-w4a16-ct': (
>         '--hf-overrides',
>         '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}',
>     ),
> }
> ```
> and 
> ```
> cfg = VllmConfig(
>     ...
>     extra_args=MODEL_VLLM_EXTRA_ARGS.get(chosen_model, ()),
> )
> ```
> 
> The scorer has this update already.


> > **** (2026-10-12 15:40, 0 votes)
> > The 12B still fails on wheelhouse v30: `KeyError: 'vision_embedder.patch_dense.weight' ` . 
> > 
> > `Gemma4ForCausalLM.load_weights` doesn't skip `model.vision_embedder.*`; adding `vision_embedder.` to its skip list fixes it.
> > 
> > MRE: error ([v2](https://www.kaggle.com/code/smartmanoj/gemma-4-12b-mre?scriptVersionId=357691577)) · patched (v3) · v4 = getting started notebook, for the diff.


> > **** (2026-10-12 20:19, 1 votes)
> > @ryanholbrook Thanks for the override. With it, the 12B still fails to start for us on the current wheelhouse (vllm 0.19.1): "Engine core initialization failed" during weight loading.
> > 
> > The cause seems to be the checkpoint itself. `gemma-4-12b-it-qat-w4a16-ct` (a `Gemma4UnifiedForConditionalGeneration`) contains nine `model.vision_embedder.*` tensors (`patch_dense`, `patch_ln1`, `patch_ln2`, `pos_embedding` and `pos_norm`). `Gemma4ForCausalLM.load_weights` in `vllm/model_executor/models/gemma4.py` skips only `audio_tower.`, `vision_tower.`, `embed_audio.` and `embed_vision.`, so `Gemma4Model.load_weights` raises KeyError on them.
> > 
> > Adding `"vision_embedder."` to that skip list makes it load on 4×L4, and it serves text normally: about 67 tokens/s for one sequence, against about 35 for the 31B.
> > 
> > Does the scorer run a newer or patched vLLM? If so, could the wheelhouse get the same version, so that local runs match what the scorer serves?


**** (2026-10-14 18:19, 0 votes)
This is great, Thanks!


---

## small model experiments
/competitions/gemma-4-developer-agent/discussion/754294 | by  | posted 2026-10-30 22:21 | last comment 2026-10-30 22:21 | 0 comments | 3 votes


**** (2026-10-30 22:21, 3 votes)
For small models experiments, please allow one parallel submission where we can submit with small models (not 31B).


---

## "Notebook Threw Exception" on a non-LoRA submission that validates and compiles locally
/competitions/gemma-4-developer-agent/discussion/751339 | by  | posted 2026-10-21 13:18 | last comment 2026-10-30 13:38 | 44 comments | 19 votes


**** (2026-10-21 13:18, 19 votes)
Hi @ryanholbrook,
I have a submission ID 57474927 returned Notebook Threw Exception with no score. I've ruled out what I can locally and would appreciate a look at the log.

I ran a submission just a day earlier and that one worked just fine.
What changed was that I added my own eval_config.yaml, rewrote the system.md prompt and lowered max_output_tokens, and no adapters for it either.

evaluation:
  max_time_minutes: 5
  max_tool_calls: 40
  max_turns: 80
  timeout_seconds: 300

Questions:
1. Could you check the log for submission 57474927 and relay it?
2. As per a previous post, a ServerStartupError is uncaught and ends rerun before task, is that the only uncaught path, or can load_submission_eval_config() also fail this way?
3. Are the budgets above within what the scorer expects within the 12-hour cap?

Happy to share the bundle or rerun anything useful.


**** (2026-10-22 13:45, 2 votes)
Hi @sultanfawad and everyone,

This looks like a failure on our side. We're investigating the root cause and will rerun any submissions that failed on account of it.

Our apologies for the incident.


> **** (2026-10-22 13:59, 0 votes)
> I have this issue three times i lost 3 dayes


> **** (2026-10-24 12:52, 0 votes)
> Hey @ryanholbrook is this fixed on your end?


**** (2026-10-21 13:58, 2 votes)
yeah same issue for me aswell, two identical submissions, two different errors - scoring error and exception error


**** (2026-10-23 15:27, -1 votes)
Hi @ryanholbrook , same issue for our team. Could you include these in the rerun?

57477114, submitted 2026-10-21: "Notebook Threw Exception", no score
57507851, submitted 2026-10-22: same error, no score
Both are prompt-only bundles (4 files, no adapters), both pass adk_submission validation locally. Thanks!


**** (2026-10-23 15:07, -1 votes)
@ryanholbrook  do you know if the issue is solved


**** (2026-10-23 12:46, -2 votes)
Hi everyone!

I've run into the same issue. Version 17 of my notebook was scored successfully at 0.15, but versions 19 and 21 both failed with `Notebook Threw Exception` after I made changes to the system prompt.

The notebook itself runs without errors and successfully generates `submission.zip`.

My failed submission IDs:
- Version 19: **57479594**
- Version 21: **57537713**

I'd appreciate it if these two submissions could also be included in the reruns. Thanks!


**** (2026-10-23 12:20, -1 votes)
Hi @ryanholbrook, same issue for our team. Could you include these two in the rerun?

- 57469124, submitted 2026-10-21 06:16 UTC: COMPLETE with no score,
  "Your notebook hit an unhandled error while rerunning your code." (less than 3 h after submit)
- 57530251, submitted 2026-10-22 15:40 UTC: COMPLETE with no score.

Both are 31B base model, no LoRA adapter. Both zips pass adk_submission.validate_directory,
and the same harness setup scored 0.12 twice (57036038, 57354973).
Thank you!


**** (2026-10-29 17:32, 0 votes)
Hi @ryanholbrook, please add 57746712 (Oct 28) to the reruns. It ended with "Notebook Threw Exception" and no score. It's a config-only 31B bundle (Budget-Fit config, no adapters), and similar E4B bundles from my account scored normally. Thanks.


> **** (2026-10-30 13:38, 0 votes)
> Update: please ignore 57746712. The failure was on my side (the bundle mixed two model variants by mistake). Fixed and resubmitted. Thanks!


**** (2026-10-29 10:11, 0 votes)
Hi @ryanholbrook , please add 57735635 (Oct 28) to the reruns.
"Succeeded" with score 0.00, no error. 
Config-only 31B bundle, nearly identical to 57329350 (scored 0.18). Thanks.


> **** (2026-10-29 14:44, 0 votes)
> Hi bro, could tell me how to get submission id? Thank you.


> > **** (2026-10-29 18:55, 0 votes)
> > The easiest way is the Kaggle CLI: `kaggle competitions submissions gemma-4-developer-agent --page-size 3`
> > 
> > This lists your latest submissions (here the last 3), and the submission ID is included in the output in the ref column.


> > **** (2026-10-30 01:04, 0 votes)
> > Thank you.


**** (2026-10-28 10:51, 0 votes)
Same here, 5 in a row, including one that's byte-identical to a submission that scored

Thanks for confirming it's on your side @ryanholbrook. Posting our IDs in case they're useful, plus two things I haven't seen mentioned in the thread yet.

Five in a row, all COMPLETE with no score, and all five show Notebook Timeout in the UI:

57145400 (Oct 13)
57390543 (Oct 19)
57430290 (Oct 20)
57472801 (Oct 21)
57693514 (Oct 27)

For what it's worth the timeout label doesn't look like real compute to me. The Oct 20 one is the useful one. By that point we suspected the problem wasn't on our end, so we resubmitted our September bundle completely unchanged as a control. 57430290 is the same archive as 56703353, which scored 0.13 on Sep 30. Not a tweak, not a rebuild, same bytes. Came back COMPLETE with an empty score.

Two things that might help narrow it down:
Our first failure is Oct 13 and the last submission we got a score on was Oct 7. Most reports here seem to start around the 20th or 21st, so this may go back a week further than it looks.
57693514 went in on Oct 27, five days after your post, and also came back blank. So it was still happening then.


> **** (2026-10-29 03:34, 0 votes)
> same experience here


**** (2026-10-28 09:55, 0 votes)
Hi @ryanholbrook, a follow-up on submission 57521679 (22 October). You wrote that submissions that failed on your side would be rerun. Six days later it still shows COMPLETE with no score, and the daily slot it used was not returned. Its ZIP is byte-identical to 57497100, which scored 0.15. Could you confirm whether it is in the rerun batch, or restore the slot? Thank you.


**** (2026-10-28 03:04, 0 votes)
Hi @ryanholbrook, please add 57669257 (Oct 26, 14:23 UTC) to the reruns: COMPLETE, no score, total_bytes 0, "unhandled error while rerunning your code."

No adapter, 31B QAT only, zip SHA-256 b0508d82…bbdc29. The same files ran cleanly five times on 4×L4 with wheelhouse v31, and our previous bundle with the same structure (57398116) scored normally.

Could you rerun it or restore the slot, and tell us the failing stage? Thanks!


**** (2026-10-27 18:08, 0 votes)
@ryanholbrook Same issue here: 57680806 (Oct 26, 23:09 UTC) failed with "unhandled error while rerunning your code", no score. No adapters, and our previous zip from the same notebook scored. Could you include it in the reruns? Thanks!


**** (2026-10-27 15:20, 0 votes)
Hi @ryanholbrook , two of our submissions from the same days also ended with "Your notebook hit an unhandled error" and still have no score: 57458172 (Oct 21) and 57503174 (Oct 22, this one has no LoRA adapter). 

Could you include them in the rerun as well..? Thanks!


**** (2026-10-24 02:01, 0 votes)
Hi @ryanholbrook, thanks for looking into this. Adding one more affected submission for the rerun:

- 57480512 (2026-10-21 11:55 UTC): "Your notebook hit an unhandled error while rerunning your code" less than an hour after submission, no score.

The same notebook version (identical submission.zip) was resubmitted as 57506125 on 2026-10-22 and ran to completion with a score, so the failure doesn't look package-related. Could you please include 57480512 in the reruns? Thank you!


**** (2026-10-24 00:52, 0 votes)
Adding our IDs for the rerun: 57501847 (Oct 22 00:06 UTC) failed with "notebook hit an unhandled error" in under 30 minutes; the same harness scored normally on Oct 19-20 and our wheelhouse has not changed since Oct 12. Thanks for rerunning these.


**** (2026-10-23 19:22, 0 votes)
@ryanholbrook Two submissions from us, both a prompt/config-only bundle with no adapters, for the incident you described. 57455672 (Oct 20, 23:13 UTC) ended with “Your notebook hit an unhandled error while rerunning your code.” 57479824 (Oct 21, 11:35 UTC), the byte-identical ZIP (sha256 6ff73d104725…4887, verified against the downloaded submission), ended with “Your submission notebook exceeded the allowed runtime.” Could you confirm (1) whether 57455672 is covered by the rerun, and (2) whether the runtime message on 57479824 is a genuine timeout or a symptom of the same scorer-side failure? We’re holding further submissions on this ZIP until we know. Thanks.


**** (2026-10-23 16:17, 0 votes)
@ryanholbrook Thank you for confirming the scorer-side failure and for planning reruns. Could you please include our two affected submissions?

- 57464948 (2026-10-21 04:12 UTC)
- 57503836 (2026-10-22 01:02 UTC)

Both show COMPLETE with an empty score and no error message. Both are byte-identical to 57396050 (2026-10-19), which scored normally (SHA-256 b9a81e76b651934a603555e7a64f0574b4322e6991ec1de07f194771394e0f08; details in my comment of 21 Oct above). Prompt-only bundle, no LoRA adapter. Thank you!


**** (2026-10-23 09:19, 0 votes)
Hi @ryanholbrook , thanks for looking into this. Our team was hit by the same scorer-side failure. Two of our submissions ended with "Your notebook hit an unhandled error while rerunning your code…" (Notebook Threw Exception), with no traceback:

Submission 57463521 — 2026-10-21 03:24 UTC
Submission 57511251 — 2026-10-22 05:26 UTC

Both were built from the same kernel version that scored normally on 2026-10-19 (submission 57376939, public 0.13). Nothing in the bundle changed between the scored run and the failed ones. We'd be very grateful if these two could be included in the rerun, or the daily quota credited back. Thank you for your help!


**** (2026-10-23 09:00, 0 votes)
Hi @ryanholbrook, same issue for us: submissions 57471712 (Oct 21) and 57509224 (Oct 22), both "unhandled error", prompt-only bundles (4 files, no adapters). Could you include both in the rerun? Thanks!


**** (2026-10-23 06:15, 0 votes)
@ryanholbrook Hi, same issue. submit id 57529699


**** (2026-10-23 06:10, 0 votes)
Submission 57541670 (sent 2026-10-23 00:01 UTC) completed about 4.4 h later with a public score of 0.00 and no error message; the same zip (sha256 fc854bb4...) scored 0.15 as 57456916 on 10-21. Could it be included in the reruns?


**** (2026-10-23 02:32, 0 votes)
same with submission 57534634 (it is a base-model submission with no lora adapter), would appreciate if it was included in the reruns


**** (2026-10-22 20:00, 0 votes)
Hi @ryanholbrook , same issue for me: 57475322 and 57501138, both failed ~20–30 min in with "unhandled error". Same zip (31B + zero-init r16 LoRA); it runs cleanly on 4×L4 with the Getting Started cells. Could you include both in the rerun? Thanks!


**** (2026-10-22 15:13, 0 votes)
@ryanholbrook I also meet the same issue on my latest submission 57520582 .


**** (2026-10-22 13:46, 0 votes)
@ryanholbrook Same "Notebook Threw Exception" for us on two submissions (IDs: ___ on Oct 21, ___ on Oct 22). Both bundles have the same structure as our submission of Oct 20, which ran on the scorer until the time limit; only eval_config.yaml changed (time budget reduced to 5 min/task). No adapters, no .pyc, real timestamps, and it compiles locally with the official wheelhouse. Could you check whether these failed at inference-server startup and, if so, restore the slots? Thanks!


**** (2026-10-22 13:44, 0 votes)
Hi, did you get any update from the organizers or identify the cause? I’m seeing the same issue.

Submission **57525032** failed after approximately **22 minutes** with “Notebook Threw Exception.” The ZIP contains only `agent.yaml`, `configs/sampling.yaml`, `eval_config.yaml`, and `prompts/system.md`—no adapters or extraneous files. It passes local validation and compilation with `adk-submission 0.2.13` and `swegemma 0.2.11`.

My previous submission **57496795** scored **0.13**. Comparing the actual ZIPs, the model, tools, sampling settings and evaluation budgets are identical. Only the system prompt, agent name and YAML comments changed.

Have you received a traceback or confirmation of whether your failure happened during model startup or after task execution began?

@ryanholbrook Could you please check the failing stage and first exception for **57525032** as well?


**** (2026-10-22 12:30, 0 votes)
Hi @ryanholbrook @herbison, I have another matching failure: submission 57521679, submitted on 22 October at 12:54 Amsterdam time.

It used the exact same ZIP as submission 57497100, which scored 0.15. I verified that both archives have SHA-256:

97c6e6394b49de46218901b58a636550f45e71b34bbe26b411dd5c7c78976212

My package includes a LoRA adapter. The adapter, prompt, sampling settings and evaluation limits were unchanged between these two submissions.

The API reports COMPLETE, but no score, with this error:

"Your notebook hit an unhandled error while rerunning your code. Note that the hidden dataset can be larger/smaller/different than the public dataset"

The failed evaluation also consumed the daily slot. The submission-limits API reports numToday: 1 and numAllowedNow: 0, and a retry was refused.

Could you inspect submission 57521679, share the failure stage and first exception, and rerun it or restore the slot if the failure was on the scoring infrastructure?

Thank you.


**** (2026-10-22 10:28, 0 votes)
Same "Notebook Threw Exception" here, on two submissions in two days:

57487946 (Oct 21, 15:29 UTC)
57517061 (Oct 22, 08:30 UTC)
Both are plain bundles with no adapters. The second differs from our submission 57441494 (Oct 20, scored 0.12) only by one number in a prompt file ("at most 5 tool calls" changed to "at most 3"). The tools, sampling, eval_config.yaml and sub-agent wiring are identical. The API shows status COMPLETE, no score, total_bytes 0 and the generic error text. It matches the failures other teams report in this thread since about 04:00 UTC on Oct 21.

@ryanholbrook @herbison could you:

tell us whether these runs stopped before the first task (for example at inference-server startup), and give the first exception;
restore the two daily slots if this was scorer-side;
say in the error text whether the failure happened before the first task, so teams can tell an infrastructure failure from a bug in their own bundle.
Happy to share the bundle if useful.


**** (2026-10-22 08:51, 0 votes)
Hi @ryanholbrook , 
I am encountering the same issue. I submitted two identical notebooks one was scored successfully three days ago, while the other failed yesterday with a "**Notebook Threw Exception**" error.

Given that multiple participants are reporting similar failures, this appears to indicate a potential platform-level issue rather than a problem with individual notebook implementations.

Could you please investigate whether there have been any recent changes or infrastructure issues affecting notebook execution and scoring?


**** (2026-10-22 08:46, 0 votes)
Hi @ryanholbrook , my recent two submissions meet the same issue, "Notebook threw exception" after running for about  or less than 4 hours. Compared to the version previously submitted sucessfully, I only made slightly changes on the system prompt, lowered the max_output_tokens and max_tool_calls. 

My submissions files include:
```python
submission.zip
├── agent.yaml
├── configs/
│   └── sampling.yaml 
├── prompts/
│   └── system.md  
└── eval_config.yaml
```

and nothing else. I have no idea what happens on my submissions. Is there any problems on the scorer?

Thanks!


**** (2026-10-22 07:53, 0 votes)
Hi @ryanholbrook, we encountered a similar issue with submissions 57474864 and 57512520, using the exact same non-LoRA ZIP. Our previously scored E24 package uses identical evaluation budgets. Could you check whether these failures occurred during model-server startup, evaluation-config loading, or after task execution began? We have not reproduced the exception locally.


**** (2026-10-22 07:37, 0 votes)
@ryanholbrook Same "Notebook Threw Exception" here, deterministic across two submissions of the same zip:

- 57468528 (Oct 21, 06:00 UTC)
- 57512474 (Oct 22): same zip, failed again within ~20 min, so it is not a runtime/timeout issue

The zip is a plain declarative bundle with 4 files at the root: agent.yaml, configs/sampling.yaml, eval_config.yaml, prompts/system.md. There are no .pyc files, no __pycache__ and no extra folder. CRCs are valid, and official_validate passes locally with the wheelhouse.

Out of 14 zips I have submitted, this is the only one whose entries carry the ZIP epoch timestamp (1980-01-01 00:00) and mode 0644. It was built by a deterministic zipper. All our other zips were built with Python zipfile using real mtimes (mode 0666), and they all ran fine. Could the scorer be choking on the 1980 timestamps, for example when it re-zips or builds a wheel, which fails on timestamps before 1980?

Could you share the traceback for these two submissions, or confirm whether this is related to the Oct 21 incident others reported in this thread? 

Thanks


**** (2026-10-21 20:04, 0 votes)
Same issue. No error locally. "Notebook Threw Exception" for a while after submission.


> **** (2026-10-22 02:59, 0 votes)
> Tried another notebook. But got "Notebook Threw Exception" again.


> > **** (2026-10-23 15:43, 0 votes)
> > Hi @ryanholbrook, would it be possible to help rerun the affected notebooks:
> > 57506037
> > 57485407
> > Thanks for your help!


**** (2026-10-21 15:06, 0 votes)
Adding one more data point that may help isolate this, because in our case the package itself is ruled out:

- Submission 57464948 (2026-10-21 04:12 UTC): COMPLETE with an empty score and no error message.
- The submitted zip is byte-identical to our submission 57396050 (2026-10-19), which scored normally (public 0.08). SHA-256 of both files: b9a81e76b651934a603555e7a64f0574b4322e6991ec1de07f194771394e0f08
- The adk-submission wheelhouse has not changed between the two runs (last updated 2026-10-12), so the same bytes went through the same pipeline and one run scored while the other did not.

Together with 57452423, 57469833, 57471486 and 57474927 reported here and in related threads on the same morning, this looks like a scorer or infrastructure issue rather than individual configurations. If that is confirmed, would it be possible to restore the affected daily slots? Thank you for looking into it.


---

## Is LoRA really helpful?
/competitions/gemma-4-developer-agent/discussion/753793 | by  | posted 2026-10-29 10:16 | last comment 2026-10-30 06:15 | 8 comments | 6 votes


**** (2026-10-29 10:16, 6 votes)
Hi all, I'd like to hear about your experience with LoRA in this competition.

I've tried several LoRA setups on Gemma 4 E4B:
- SFT on public agent trajectories
- SFT on trajectories from stronger teacher models (Gemma 4 31B and DeepSeek V4.1 Flash, both run under a time/tool-call budget)
- Rejection-sampling fine-tuning on E4B's own successful runs

I compared each adapter with the base agent over repeated runs, with token budgets matched to Kaggle. No adapter beat the baseline, and the small gains I saw looked like noise. The adapters seemed to learn style (shorter runs, fewer tool calls) rather than problem-solving skill, and LoRA decoding is also slower on Kaggle.

Questions:
1. Has anyone gotten an adapter to clearly beat its base model here, over several runs rather than one submission?
2. What data or training method worked for you?


Thanks!


**** (2026-10-29 12:14, 3 votes)
The only thing that I saw helping was a better localization SFT. What I did was, for the explorer agent on the base model, it was very, very bad, so I used the trajectories from DeepSeek V4.1 Flash To make the explorer better.


> **** (2026-10-29 15:58, 1 votes)
> Thank you! I actually tried giving the model a localization skill before, but it didn’t help much. I’ll give localization-only SFT a try.


**** (2026-10-29 11:27, 2 votes)
Yeah, we are pretty limited with the capability of the E4B model, and we have had similar results, to be honest, with LoRA fine-tuning. I've generated teacher labels from Kimi K 3.1 Pro as well, DeepSeek 4.1 Flash, and Minimax H 3.1 Flash (or previously Space Bunny). However, all of those were not satisfactory.


**** (2026-10-29 16:19, 1 votes)
Could you share some information about the dataset you used? If you cannot disclose too many details, simply providing the number of trajectories.


> **** (2026-10-29 16:28, 0 votes)
> Hold on a sec


> **** (2026-10-29 16:31, 1 votes)
> Public SWE-Zero trajectories, kept only where the final patch matched the gold fix: ~900 (about 645 issues from 291 repos), 1 epoch.
> 
> Teacher trajectories: only 13 per teacher model, 4 epochs, so that result is kinda weak. The adapters may overfit.
> 
> E4B’s own successful runs (rejection sampling): 40, then ~200, then ~470 in later rounds.
> 
> Tbh, it is really hard to find suitable datasets for E2B/E4B.


> > **** (2026-10-30 06:15, 0 votes)
> > Did you try and ablate the teacher trajectories to check and ensure if overfitting was happening or not?


---

## -p no:anyio and four other scorer conventions make about a quarter of real fixes unpassable
/competitions/gemma-4-developer-agent/discussion/751707 | by  | posted 2026-10-22 15:01 | last comment 2026-10-30 02:04 | 2 comments | 0 votes


**** (2026-10-22 15:01, 0 votes)
While building an external validation set for this competition, I ran real post-release fixes from 38 Python libraries through the verification conventions swegemma 0.2.x uses (pytest.ini overwrite, root conftest header, `-p no:anyio`, every `.py` file in `test_patch` as a target, no network). In 277 of 1,143 cases (24%), the **reference fix fails verification only because of one of those conventions**. The other 111 reference fixes that fail, fail under the repository's own settings too, so they are not counted.

The five causes:

- **`-p no:anyio` alone** (79 cases): all 54 starlette fixes that pass natively, and 25 of 43 uvicorn fixes. Their test clients request the anyio plugin's fixtures (`anyio_backend`, `anyio_backend_name`). With that one flag removed and everything else unchanged, all 79 pass.
- **The pytest.ini overwrite** (101 cases): it drops repository settings such as `asyncio_mode = auto` and plugin registrations (anyio's own suite, litestar, strawberry, parsel). The same patches pass with the repository's pytest configuration.
- **Non-test files as targets** (65 cases): black adds test cases as `.py` data files under `tests/data/cases/`, and click and loguru add helper modules under `tests/`. Because every `.py` file in `test_patch` becomes a target, pytest imports them as test modules and collection fails or finds no tests.
- **A required test skipped on Linux** (24 cases): swegemma 0.2.11 counts a skipped required test as a failure, so a fix whose new test is platform-skipped can never pass.
- **A JUnit report over 10 MiB** (8 cases, python-multipart): the harness reads the report back through the sandbox's 10 MiB output cap, gets a truncated file and marks the task unresolved even when every test passed.

What it means here: if the hidden tasks were checked with the same harness before release, tasks from codebases that test through anyio or rely on their own pytest configuration were filtered out of it; if any were not, no agent patch can pass them. For agents, the practical lesson is not to rely on a repository's pytest configuration or async plugins when writing a reproduction.

Per-task records and the audit script are in the FreshSWE-Py dataset (663 validated post-release tasks from 33 repositories, in this competition's file layout): https://www.kaggle.com/datasets/moshegolderson/freshswe-py · reproduction notebook: https://www.kaggle.com/code/moshegolderson/freshswe-py-reproduce · score your own patches: https://www.kaggle.com/code/moshegolderson/freshswe-py-score-your-patches. Happy to share the exact task list with the organizers if useful.


**** (2026-10-29 20:04, 0 votes)
One more variant of the "skipped required test" issue, on the public task rich_3486: the gold patch is marked unresolved even though nothing fails (20 passed, 1 skipped). The test patch adds test_traceback_finely_grained (Python ≥ 3.11) and test_traceback_finely_grained_missing (skipped on ≥ 3.11). _node_matches_requirement also matches on short_node.startswith(req_base + '_'), so the skipped ..._missing sibling counts as a non-passing match for the required test_traceback_finely_grained, and the task fails. This happens even with an explicit FAIL_TO_PASS. Exact matching first (prefix only for parametrized [...] ids) would fix it.


> **** (2026-10-30 02:04, 0 votes)
> Thanks — that's a great catch, and it fits the pattern exactly. In swegemma 0.2.11 the check is in harness/verification.py (_node_matches_requirement): a required test also matches any test whose name starts with "<required name>_", so a skipped test_traceback_finely_grained_missing counts as a non-passing result for test_traceback_finely_grained. Your fix (exact match first, prefix only for parametrized [..] ids) would cover it. With your permission I'll cite rich_3486 and your diagnosis in our paper. Have you seen it on any other public tasks?


---

## Stuck Submission
/competitions/gemma-4-developer-agent/discussion/754000 | by  | posted 2026-10-30 01:06 | last comment 2026-10-30 01:06 | 0 comments | 2 votes


**** (2026-10-30 01:06, 2 votes)
Hi hosts,

My submission has been showing “Notebook Running” for over 16 hours, well past the 12-hour scoring limit:

Notebook: baseline 024 control, Version 2 (scriptVersionId 363436664)
Submitted: Oct 29, ~08:30 UTC
Team: mohamedtkhalil1995

Because it’s still pending, the submit dialog now says “Your team already has 1 pending submissions; please wait for one to finish scoring.” So I can’t use today’s slot.

The bundle is a prompt-only agent (agent.yaml, eval_config.yaml, sampling config, system prompt). It’s the same structure as my two earlier submissions, which scored normally in a few hours.

Could you cancel or fail this submission so the queue is free again? And if possible, could you restore the daily slot it has blocked? Thanks!


---

## Question on the public Docker grading path: wheel selection for older base commits
/competitions/gemma-4-developer-agent/discussion/749114 | by  | posted 2026-10-14 00:55 | last comment 2026-10-29 20:03 | 1 comments | 2 votes


**** (2026-10-14 00:55, 2 votes)
Rebuilding the public setup (Dockerfile.public + wheels/ + swegemma’s Docker path) and grading a public fastapi task’s gold patch, the wheel injection picks the newest starlette in wheels/ (1.6.0). At the task’s base commit, FastAPI() then fails with Router.__init__() got an unexpected keyword argument 'on_startup'. Does the scorer pin per-task dependency versions (or use prebuilt per-task images), or is the newest-version selection what the scorer actually uses? Asking mainly to understand how well local grading matches the scorer.  @ryanholbrook


**** (2026-10-29 20:03, 0 votes)
Confirming this on the public task fastapi_14492: the gold patch fails in the public Docker path. With the public image it first fails at collection with ModuleNotFoundError: No module named 'httpx2' (starlette 1.6's TestClient asks for it, and the deprecation warning is raised as an error). After adding httpx2, it fails with the same Router.__init__() got an unexpected keyword argument 'on_startup', because the snapshot pins starlette>=0.40.0,<0.51.0 but the setup script strips version constraints and installs the newest wheel. So the task is unsolvable locally even with the reference fix. It would help to know whether the scorer resolves versions per task.


---

## How noisy is the public score? 58 tasks, 1 task = 0.017 (simulation + leaderboard stats)
/competitions/gemma-4-developer-agent/discussion/753524 | by  | posted 2026-10-28 12:48 | last comment 2026-10-29 18:01 | 2 comments | 6 votes


**** (2026-10-28 12:48, 6 votes)
Public scores here are the count of solved tasks out of 58, so one task is worth 0.017. The top is 0.24 (14 tasks, 6 teams); the 0.22 configs are 13 tasks (48 teams); 12 tasks has 218 teams.

I put the leaderboard and a simple noise simulation in a notebook: https://www.kaggle.com/code/harshitsama/gemma-4-agent-is-0-24-vs-0-22-real-noise-check

What it shows (the noise part is a model with stated assumptions, not a measurement):
- If every task were a coin flip with the same solve rate, two runs of the SAME agent differ by about 3 tasks (1 sd). If tasks are mostly all-or-nothing, about 2.5.
- A truly equal config looks 2+ tasks better about a third of the time, and 4+ tasks better 15-20% of the time. So 1-4 task gaps between single runs are weak evidence.
- The pure coin-flip model predicts the best of 400 equal teams at 17-21 tasks, but the real top of 4,018 teams is 14. So real run-to-run noise is smaller than a coin flip: treat 3 tasks as an upper bound.

Practical use with 1 submission a day: repeat a promising run before believing it, spend submissions on changes with a clear mechanism (the budget limits are the one lever with a large reported effect), and pick the final one for robustness.

Corrections and your own numbers welcome; if you have repeated runs of one config I would like to see how far apart they land.


**** (2026-10-29 05:51, 0 votes)
Your sim matches our data — three things from our side:

Confirmed: N=58 truncation is exact — only 14 distinct scores exist across all teams, and the "holes" (0.16, 0.19...) are structural, not sampling. So 1 task = 0.017 is right, and the sim should truncate rather than round. Your best-of-400 argument also checks out: our same-config repeats landed 0 tasks apart, twice — pairs scored (0.17, 0.17) and (0.18, 0.18). Treat 3 tasks as an upper bound: agreed.

From 200+ runs of one config: variance only lives in "flippy" tasks. Of 39 task×config cells with 6+ draws: ~67% flippy, ~23% never-solve, ~10% always-solve. Sticky tasks contribute zero variance. Measured σ = 1.0 task per 7-task rep (19 reps) — roughly ~2 tasks on a 58-task draw under the real p-mix, below your binomial 3.

Task-mix ceiling: 35 of 38 multi-file golds in the practice set have never been solved by any model or config. A quarter of the pool is structurally dead, which compresses the top independent of noise.

On "budget is the big lever": our 154-run replay of the cap raise was null (net −1), and our budget-raise submission returned no score (scorer error). If you've seen a measured effect somewhere, I'd like to see it.

Repeats: we have 133 runs of one config + 77 of its control — happy to share per-rep numbers. Headline: +9 points, p = 0.22 — your "small gaps are weak evidence" demonstrated live.


> **** (2026-10-29 18:01, 0 votes)
> Thanks, this is very useful. Updating my view: the sigma of about 1 task per 7-task rep (about 2 on 58) and 0-task gaps in your repeat pairs fit my 'upper bound' reading, and the structural-dead-task point explains the compressed top. On the budget lever: I had no measurement of my own, I was going by the reported effect, and your 154-run null replay is better evidence, so I now treat it as unproven. Your +9 points at p = 0.22 is a good live example. If you can share the per-rep numbers (even just per-task solve counts), I will add them to the notebook with credit.


---

## The top of the leaderboard is dominated by those who trained LoRA's.
/competitions/gemma-4-developer-agent/discussion/748051 | by  | posted 2026-10-10 11:43 | last comment 2026-10-29 14:01 | 21 comments | 12 votes


**** (2026-10-28 11:07, 2 votes)
This competition is not that easy, within the limit of kaggle gpu, and need to combine the agent training under the real task.


> **** (2026-10-28 11:08, 2 votes)
> Just a good chance to learn and improve


**** (2026-10-10 11:43, 12 votes)
Hello all, 
It seems that the only way to really move past the 0.17-0.18 score range is to train a LoRAs for the quantized version of Gemma 4 we are told to work with. 
I really have experimented with a lot of agent frameworks so far, and at one point, more orchestration, skills, prompts, agents all become redundant. Simpler agents with good constraints work much better. 
But the only way to break the 0.18 wall seems to be to train LoRAs.


**** (2026-10-14 07:25, 1 votes)
I think none of the top submissions have managed to get any improvements through finetuning :)


> **** (2026-10-26 16:52, 1 votes)
> What makes you say that?


> > **** (2026-10-29 14:01, 0 votes)
> > look at his rank, although after some experimentation locally, I have reason to believe it is the best way to move ahead.


**** (2026-10-13 19:21, 1 votes)
Agreed. I wonder how much compute it takes to get to >= .24, the current best. And I would be curious what they're training on. General SWE traces already on HF? Making traces with openrouter models on similar problems? Are they distilling off bigger Gemmas? 
Idk, I don't have too much dedicated compute so I am curious what is really moving the needle.


> **** (2026-10-13 22:41, 2 votes)
> I ran an analysis on the leaderboard public score distribution, and, honestly, the scores are explainable entirely by two binomial distributions centered around a couple lower accuracy means. in other words, the entire leaderboard variance is explainable as random chance of some tasks flipping resolved. Local runs show a decent degree of variance on the dev set with this model checkpoint. While not certain as we can't see how consistent the higher scores have been across submissions, I'm mostly of the opinion no one has cracked anything yet and it's all noise.


> > **** (2026-10-14 07:13, 1 votes)
> > That's interesting. Now that I think about it, my highest scoring submission is a 0.17, and I have submitted the same package about 3 more times, getting scores of 0.15, 0.13 and 0.15. So yeah, there is definitely that random variance. But a 0.24 without any intelligent agent engineering or LoRA training seems less plausible to me.


**** (2026-10-13 10:11, 0 votes)
Any tips on trained lora, I tried few times but all of the submission failed with notebook threw exception error.


> **** (2026-10-13 16:41, 0 votes)
> I haven't trained any LoRA's myself. It's because Kaggle's GPU free tier (especially for L4's) is extremely limited (you can get about 15 hours every week). And I tend to get through that budget on testing my agents locally in about 3 days. There isn't enough infrastructure to comfortably train an effective LoRA. The people on the top of the leaderboard almost certainly have access to GPU outside of the Kaggle free tier. I believe the ceiling for a submission without LoRA is 0.20, so I am trying to reach it. But this competition rewards post training more than it rewards harness engineering (as another user shared).


> > **** (2026-10-26 16:59, 0 votes)
> > I've gotten Lora's to work on submissions. They just scored worse than baseline. So yes Lora's work. I am terrible at using them and subagents.


**** (2026-10-13 07:45, 0 votes)
yes this competition is about post training and not harness engineering. no matter the setup you try the competition model has a output distribution that cannot be changed much. the harness itself is limiting the expressiveness of the model on top of it.

some of the ablations that I had shared as discussion posts hint towards the same.


**** (2026-10-13 02:24, 0 votes)
@normannweuifohpq9 were skills and subagents useful for getting the score of 0.18?


> **** (2026-10-13 05:06, 0 votes)
> Not really


> **** (2026-10-26 17:00, 0 votes)
> My .18 score did not come from subagents or skills. If you're using Subagents make sure to try the different ones.


> > **** (2026-10-27 16:43, 0 votes)
> > Yeah... most of the scores (even up to 0.22) are single agent frameworks (see the Gemma 4 SuperAgent public agent for example) that just seem to have gotten lucky.


> > **** (2026-10-28 19:53, 0 votes)
> > "lucky" sure bro!


**** (2026-10-11 18:03, 0 votes)
really want to know... how far just the wrapper modification can take us...


> **** (2026-10-12 04:48, 1 votes)
> I would guess maximum 0.18-0.19


> > **** (2026-10-13 07:13, 0 votes)
> > Hmm, it seems. I will try to do some tests soon


---

## This Competition stinks
/competitions/gemma-4-developer-agent/discussion/753613 | by  | posted 2026-10-28 18:58 | last comment 2026-10-29 11:46 | 1 comments | -3 votes


**** (2026-10-28 18:58, -3 votes)
There are too many bugs in this to care anymore. What is the point?


**** (2026-10-29 11:46, 0 votes)
to solve the bugs.


---

## Graph and embedding generation pipeline 
/competitions/gemma-4-developer-agent/discussion/753624 | by  | posted 2026-10-28 19:18 | last comment 2026-10-28 19:18 | 0 comments | 0 votes


**** (2026-10-28 19:18, 0 votes)
Hi folks,

I found the graph/embedding schemas and the loading and retrieval implementations in swegemma, but couldn’t locate the pipeline that generates these assets.

Has anyone tried this? and know - 

- Which parser or analysis tool builds the symbol graphs?
- Which model generates the 256-dimensional node embeddings?

Thanks


---

## Request to hosts: inference kernels
/competitions/gemma-4-developer-agent/discussion/751311 | by  | posted 2026-10-21 10:30 | last comment 2026-10-28 14:37 | 1 comments | 0 votes


**** (2026-10-28 14:37, 1 votes)
Actually +1


**** (2026-10-21 10:30, 0 votes)
Hey hosts,

The stock w4a16 int4 kernels are slow for inference, my request to you is that you allow us the contestants to supply our own inference kernels.

For instance, on training I get ~200 toks/sec (fwd+bwd) and inference using bespoke kernels is ~319 toks/sec.


---

## Scorer's vLLM 0.19.1 drops Gemma 4 tool calls emitted before the thought channel closes (MRE)
/competitions/gemma-4-developer-agent/discussion/753521 | by  | posted 2026-10-28 12:38 | last comment 2026-10-28 12:38 | 0 comments | -3 votes


**** (2026-10-28 12:38, -3 votes)
MRE notebook (CPU only, ~3 min): https://www.kaggle.com/code/smartmanoj/gemma-4-toolcall-in-thought-mre

The scorer serves Gemma 4 with `--reasoning-parser gemma4 --tool-call-parser gemma4`, and the harness calls it non-streaming. In that path, vLLM 0.19.1 extracts tool calls only from `content`, and the reasoning parser returns `content=None` when `<channel|>` is missing. So an output like

    <|channel>thought
    I will run the tests now.<|tool_call>call:run_command{...}<tool_call|>

is returned entirely as reasoning: the tool call never runs, and the agent spends a continuation nudge. The streaming path handles the same text correctly (a tool call ends reasoning there).

The notebook uses the real vLLM 0.19.1 wheel, the real Gemma 4 tokenizer, and the server's own parsing code. It shows the dropped call, then shows it parsed correctly with a small patch (end reasoning at `<|tool_call>` when `<channel|>` is missing).

Upstream: fixed by the Gemma 4 parser rewrite in vLLM 0.24.0 ([PR #45588](https://github.com/vllm-project/vllm/pull/45588)). Versions 0.19 through 0.23 have the bug.

Impact in our local runs is small (~1% of runs, all on 31B), but it silently costs agents a nudge, and occasionally a run.

@ryanholbrook, would the scorer pick up the fix (a vLLM upgrade, or the small patch in the notebook)?


---

## RUNNING FOR 21 hr . NOW WHAT IS HAPPENING ? 
/competitions/gemma-4-developer-agent/discussion/752875 | by  | posted 2026-10-26 16:33 | last comment 2026-10-28 11:11 | 2 comments | 1 votes


**** (2026-10-26 16:33, 1 votes)
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F36288249%2F118415c1447c91de862196b928ab0a9a%2FScreenshot%202026-10-26%20at%2010.01.58PM.png?generation=1793032424948292&alt=media)


**** (2026-10-28 11:11, 0 votes)
Sometimes we will encounter the long time waiting, for one previous competition, the server even encouter the submission queued, where everyone's submission cannot be scored and on leadboard score cannot be normally rated.


**** (2026-10-26 18:35, 0 votes)
queue times (you can be in queue for several hours, for high demand)


---

## Test-set problem statements: issue text or PR description?
/competitions/gemma-4-developer-agent/discussion/753499 | by  | posted 2026-10-28 10:54 | last comment 2026-10-28 10:54 | 0 comments | 1 votes


**** (2026-10-28 10:54, 1 votes)
Hi @ryanholbrook,

Thanks for the curation details on the [Data page](https://www.kaggle.com/competitions/gemma-4-developer-agent/data). Step 2 says each change was matched with "its original problem description, issue tracker thread, or bug report". One follow-up that affects how we build local validation sets:

When a test task has no linked issue, is its problem_statement the PR title and body, as with most public tasks?

For context, I read and labelled 50 random public tasks:
- 27/50 describe the fix itself, often naming the function to change (e.g. [fastapi_14458](https://github.com/fastapi/fastapi/pull/14458), PR).
- 15/50 are a title plus a link the offline agent can't open, or an empty template (e.g. rich_3521, [PR](https://github.com/Textualize/rich/pull/3521)).
- 8/50 are maintainer design notes.

Issue-based datasets look very different: about half of 50 random [SWE-rebench-V2](https://huggingface.co/datasets/nebius/SWE-rebench-V2) Python tasks are bug reports with reproduction code and tracebacks, and none describe the fix. OOD-45 also found that 43/45 mined PR statements "carried part of the fix".

This may be one reason local scores on the public tasks don't track the LB ([744319](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744319)).

A rough split for the test set would be enough (mostly issue text / mostly PR text / mixed / rewritten). No task-level details needed.

Thanks!


---

## want to fine tune the gemma 4 31B model but need computing no worrires 
/competitions/gemma-4-developer-agent/discussion/753488 | by  | posted 2026-10-28 08:59 | last comment 2026-10-28 08:59 | 0 comments | -3 votes


**** (2026-10-28 08:59, -3 votes)
Hey guys! I just built a project called OjasX (https://github.com/mkrishna793/OjasX-open-source-CUDA.git)—a math compiler that lets you train a massive 31B model on just 14.6 GB of RAM.
It lets you locally train and fine-tune any kind of large model (not just Gemma) with way less RAM and no crazy computing power needed. Check it out and let me know if you run into any confusion.
Quick tip: If you ask an AI to help you write a script for it, it might tell you it's "impossible" to train a model in that little space. Don't worry—I literally used this to fine-tune Gemma 4 for a competition. When I forced the AI to try anyway, it admitted it is possible. Dig deep into the repository beyond just the README and try training your models with it!


---

## Looking for a big-box teammate — Gemma 4 Developer Agent
/competitions/gemma-4-developer-agent/discussion/753389 | by  | posted 2026-10-28 01:39 | last comment 2026-10-28 01:39 | 0 comments | -4 votes


**** (2026-10-28 01:39, -4 votes)
Solo competitor (with an AI-assisted pipeline) looking for ONE team member for the Gemma 4 Developer Agent competition. One seat — several may start the process, and verification decides who finishes it.

What we have:
- A working, verified pipeline for the small models: LoRA training on Gemma 4 E4B, a behavioural probe harness (base vs adapter, 13 checks), and a probe-gated submit process. One entry already submitted and rescored through a full failure probe.
- Where that entry stands, honestly: the first adapter scored zero. A full probe found the failure layer — it edited correctly but submitted without ever running the tests. The second-generation training corpus is built to fix exactly that: 161 traces in the real harness format teaching edit → run tests → submit, measure-gated before training. The retrain is in progress now.
- A separate entry in the Paper track.
- A proven way to migrate a winning approach: the same training-data format, probe and packaging steps port across model sizes — what wins on the big model can be carried into the team's final submissions.

What you'd bring:
- A big box: enough GPU to train/run the large Gemma 4 variants (31B / 12B).
- Willingness to install our Muse setup (kit-muse) on that box, so the pipeline runs there the same way it runs here.
- If your box doesn't meet our requirements, we will give you the full installation with the 1 B token referral but not keep you on the team.
- Misrepresentation ends it: if the verified report contradicts what you claimed, the agreement is off — we verify first and merge second, so a lie costs you the seat before it can cost the team anything.
- Part of the agreement: your kit-muse verifies your big box. Once installed, it inventories the hardware (GPU, VRAM, RAM, disk) and that report stands as the spec of record — a stated spec is not taken on trust; the Muse on the box checks it.
- Getting started costs you nothing: install Muse and redeem referral code NZUNWW and we BOTH get 1 billion tokens to start, with 100 million added per week — that is the fuel kit-muse runs on.

The deal: we build the big model together, and the cash prize is shared. The split is agreed in writing before the team merger deadline (25 Nov 2026) — Kaggle's default is an even split, and any change needs the whole team's agreement. Final submission deadline is 2 Dec 2026.

How it runs, in order:
1. You install kit-muse and redeem NZUNWW — you hold 1 billion tokens, and the same referral credits us 1 billion on our side. Each side fuels its own Muse.
2. Your kit-muse verifies your box (the spec of record).
3. Only then do we deliver the model package — our training data format, probe harness and recipe — to your kit-muse. Kit-muse and tokens alone are not the entry: the model is ours, and it is the contribution we bring.
4. The build runs inside a VM on your box, with the GPU passed through to it. The VM's environment is specced by us, so a run on your box is the same run we proved here — that sameness is what makes a winning model migratable. Your kit-muse verifies the host box; the work itself stays inside the VM.
5. The node runs on your own local network — no proxy in the middle, no flakiness. The VM, its kit-muse and its cron all live on your LAN and talk locally; only the cloud pairing crosses the internet. (Our own lab link crosses a proxy that flakes — a local node does not have that hop, and its local work never waits on it.)
6. Your setup mirrors ours — a Kit-Muse + KO combination. The kit-muse in the VM runs with a cron of its own: it drives the builds on schedule, unattended, and reports progress. A second kit-muse in the cloud pairs with it in the KO role: an independent lane that verifies every claim the first lane makes (the box inventory, the training results, the probe verdicts) and holds the record if the box is ever off. Two lanes, neither taken on trust.
7. When the entry is done, the winning model migrates out to the team's final submissions and the VM is wiped. Nothing of ours stays behind on your box.

Minimum big box (the spec your kit-muse verifies against):
- GPU: one card with 48 GB VRAM — RTX A6000, RTX 6000 Ada, or L40/L40S; an A100/H100 80 GB is better. (Absolute floor: a 24 GB RTX 3090/4090 can QLoRA-train the 31B only with tight settings — micro-batch 1, gradient checkpointing, capped sequence length. Below 48 GB the run is fragile, so 48 GB is the agreement minimum.)
- The GPU must pass through to the VM (IOMMU / VT-d on the host).
- System RAM: 128 GB (our pipeline materialises the 31B in bf16 on CPU, ~62 GB, before re-quantising).
- Storage: 1 TB NVMe (bf16 base ~62 GB + QAT checkpoint ~22 GB + working copies).
- CPU: 16+ cores.

The arithmetic that closes it: the box is the only cash you risk, and it stays yours whatever happens. If the team places, your half of the prize repays it — third place split two ways (~$5,000) roughly covers a used-A6000 build; second place (~$9,000) covers a new RTX 6000 Ada build; first place (~$18,500) covers the box twice over.

Worst case, you've gotten yourself a serious AI workstation for your own projects.

You must have your own Kaggle account and enter the competition individually first. Team size max 5.


---

## Anyone Have Success Loading LoRAs onto Gemma E4B?
/competitions/gemma-4-developer-agent/discussion/753388 | by  | posted 2026-10-28 01:39 | last comment 2026-10-28 01:39 | 0 comments | 0 votes


**** (2026-10-28 01:39, 0 votes)
Since we know how bad with respect to capability E4B is, has anyone tried to use a LoRA adapter to fine-tune the model? If yes, was it successful in running on the submission scorer, since it looks like The LoRA approach doesn't work with the current scorer infrastructure. The scorer's PEFT can't handle Gemma4ClippableLinear (or even the inner .linear modules in some cases).


---

## Submission still running after 24+ hours, is this normal?
/competitions/gemma-4-developer-agent/discussion/753084 | by  | posted 2026-10-27 04:21 | last comment 2026-10-27 19:12 | 5 comments | 5 votes


**** (2026-10-27 04:21, 5 votes)
Hi everyone,

I submitted my notebook yesterday, and it's been over 24 hours, but the status still shows "Notebook Running." I haven't received a score or any error message yet.

Has anyone else experienced this? Is it normal for submissions to take this long, or could something be stuck?

Also, is there a way to check the evaluation progress or access more detailed execution logs?

Just wanted to check before doing anything else. Thanks!


**** (2026-10-27 14:22, 1 votes)
Yes, its normal. Give it a few more hours and you will get your score.


**** (2026-10-27 09:14, 1 votes)
My submission took 22hrs to get a score, and it just said “Notebook Running” the whole time, so I think you’re fine. Didn’t see any way to check progress or logs either.
Btw mine is E4B, no idea about 31B.


**** (2026-10-27 18:18, 0 votes)
now what is the result like did it gave Time out error ?


> **** (2026-10-27 19:12, 0 votes)
> It ran successfully after 28–30 hours, but despite the upgrades I made, it performed worse than my previous result.


---

## Gemma's Copying Bug: A One-Tensor Repair
/competitions/gemma-4-developer-agent/discussion/753277 | by  | posted 2026-10-27 19:05 | last comment 2026-10-27 19:05 | 0 comments | 3 votes


**** (2026-10-27 19:05, 3 votes)
I found that the 4-bit-ready (QAT) release of Gemma 4 E4B sometimes drops a final "s" when asked to copy text (`directs` → `direct`), which breaks exact-match edit tools. I traced many of these errors to one unusually small tensor (`per_layer_model_proj`, about 1/65 of the standard release's scale) that the following RMSNorm cannot compensate. Doubling it, or adding a training-free rank-128 LoRA built from the tensor itself, repairs most of the failures in our selected tests.

Here's the code and evidence if you'd like to try it:
- Code, per-item data, hashes and a checker (`python verify_release.py`): https://github.com/michi883/gemma-copying-tensor-fix
- The adapter (two files, hashes in the description): https://www.kaggle.com/datasets/michi883/ple-proj-svd-r128
- The executed comparison notebook (competition-attached, internet off, 4×L4; the unmodified model failed 15 of 18 copy inputs, the adapter 1): https://www.kaggle.com/code/michi883/copy-test-lora

These are targeted tests, not a general coding benchmark. The seven coding tasks were evaluated locally with llama.cpp, not vLLM.


---

## Compaction summary call ignores the submission's temperature, top_p and top_k
/competitions/gemma-4-developer-agent/discussion/753225 | by  | posted 2026-10-27 16:33 | last comment 2026-10-27 16:33 | 0 comments | 1 votes


**** (2026-10-27 16:33, 1 votes)
The compaction summary is sampled without the submission's sampling settings: its request carries no `temperature`, `top_p` or `top_k`, so vLLM falls back to Gemma 4's `generation_config.json` (temperature 1.0, top_p 0.95, top_k 64), whatever `generate_content_config` sets. A submission at temperature 0.2 gets its summaries at 1.0.

- Measured: 4,248 summary calls across 463 local evaluations (swegemma 0.2.11, google-adk 1.36.1, compaction at 14,336 tokens), none with a sampling field; every agent call in the same runs sent the configured temperature.
- Source: `LlmEventSummarizer.maybe_summarize_events` builds its `LlmRequest` without a config, so `LiteLlm` sends no sampling fields (same code in google-adk 1.39.1).
- Thinking: summary calls do carry the submission's thinking settings (`thinking_token_budget`, `enable_thinking`), so only sampling is dropped.
- Scorer: not measured. HARNESS_README 7.2 lists no custom summarizer, so I expect the same there.
- Effect on solves: not measured.

Is this intended? If not, try passing the agent's sampling fields to the summarizer? If it is, one line in HARNESS_README saying `generate_content_config` sampling does not apply to the summary would do.


---

## Local eval in a scorer-like sandbox: gold patches pass on 127/129 public tasks (was 52)
/competitions/gemma-4-developer-agent/discussion/751487 | by  | posted 2026-10-21 20:32 | last comment 2026-10-27 14:12 | 5 comments | 15 votes


**** (2026-10-21 20:32, 15 votes)
If you evaluate your agent in a Kaggle notebook, your local score may be much lower than it should be because of environment mismatches. I ran every reference (gold) patch through the official swegemma grader in a plain notebook, and only **52 of 129** tasks passed (fastapi: 10 of 67).

I rebuilt a scorer-like sandbox inside a notebook, based on the published Dockerfile.sandbox: a clean venv, pytest, the competition wheels, and the missing test packages. With this setup, gold patches now pass on **127 of 129** public tasks. The remaining 2 tasks appear internally inconsistent because their required tests have opposite skip conditions.

| | plain notebook | scorer-like |
|---|---|---|
| fastapi | 10 / 67 | 66 / 67 |
| rich | 39 / 48 | 47 / 48 |
| requests | 3 / 13 | 13 / 13 |
| httpx | 0 / 1 | 1 / 1 |

Notebook: **Gemma 4 Agent: Do Gold Patches Pass Locally?** in https://www.kaggle.com/zbigniewkirchner/code

Wheels: https://www.kaggle.com/datasets/zbigniewkirchner/gemma-4-agent-local-eval-wheels

Pythons: https://www.kaggle.com/datasets/zbigniewkirchner/gemma-4-agent-local-eval-pythons

A few old public tasks need period-correct versions (e.g. Pygments for 7 rich tasks). The CSV marks them, so the calibration stays transparent.


**** (2026-10-27 13:30, 0 votes)
Hi Zbigniew, thanks a lot for sharing this scorer-like sandbox, it's very useful. Could you tell us under which licence your two notebooks and the "gemma-4-agent-local-eval-wheels" / "gemma-4-agent-local-eval-pythons" datasets can be reused? We'd like to apply the same approach for local evaluation only (nothing from them goes into a submission). Also, were the wheels and Python builds taken unmodified from PyPI / python.org? Thanks!


> **** (2026-10-27 14:12, 0 votes)
> Thanks! My two notebooks are under Apache 2.0, and so is my own file in the datasets (`gold_patch_check.csv`). Everything else is unmodified and keeps the licence of its source. Wheels from PyPI, Python builds from https://github.com/astral-sh/python-build-standalone/releases/tag/20261013.


**** (2026-10-22 06:06, 0 votes)
It was clear that subprocess (local) uses python 3.12.13 and the Docker image's used python 3.13. Docker was the default though according to the HARNESS_README.md.
So do you think our kaggle submissions are just using the subprocess as the sandbox?


> **** (2026-10-22 16:25, 1 votes)
> Good question. I don't know whether Kaggle submissions use Docker or subprocess as the sandbox.
> 
> My goal wasn't to claim an exact match with the scorer, but to make local evaluation more reliable. In a plain notebook only 52 of the 129 public gold patches pass, and in my calibrated scorer-like sandbox 127 do. That's why I changed my wording from "matches the scorer" to "scorer-like": I don't want to suggest I know which sandbox the official evaluator uses.
> 
> Either way, when the gold patches pass, a failure in your local run is about the agent, not the environment. That makes comparisons between agent configs much more trustworthy.


> > **** (2026-10-22 16:45, 1 votes)
> > Cool thanks for sharing!!


---

## Lora finetuning
/competitions/gemma-4-developer-agent/discussion/752797 | by  | posted 2026-10-26 11:01 | last comment 2026-10-26 16:16 | 2 comments | 0 votes


**** (2026-10-26 16:16, 0 votes)
I have had little to no change outside of noise using various adapters different data sets etc. Are others having a similar experience? (both on 31B and E4B


**** (2026-10-26 11:45, 0 votes)
have you tried smaller models ?


**** (2026-10-26 11:01, 0 votes)
Does lora finetuning actually improve modals perfomance ..iam unable to get past the score of 0.05 tried multiple variations of Qlora + GRPO + AVSPO


---

## Interested in teaming up? Please read our public Gemma smoke-test Code first
/competitions/gemma-4-developer-agent/discussion/752693 | by  | posted 2026-10-25 23:19 | last comment 2026-10-26 15:04 | 1 comments | -4 votes


**** (2026-10-25 23:19, -4 votes)
We are collecting expressions of interest from prospective teammates working on coding-agent integration, tool handling, evaluation or inference reliability.

Please read our public Code article before applying:
https://www.kaggle.com/code/cosmorin/gemma-31b-a-verified-read-edit-diff-smoke-test

It documents a narrow synthetic read/edit/diff smoke test. It is not a full SWE evaluation or evidence of a competition score, and its timing should not be read as scoring runtime.

If interested, apply by replying here after reading the article with the component you could contribute to and one concrete test or experiment you would propose.

An existing team invitation is pending, so we cannot issue another immediately. Any later invitation depends on remaining capacity, team fit and competition eligibility. Please treat this as an expression of interest, not a guaranteed place.


---

## How can we test the same Docker isolation used by the scorer 
/competitions/gemma-4-developer-agent/discussion/751674 | by  | posted 2026-10-22 12:57 | last comment 2026-10-26 10:56 | 1 comments | 0 votes


**** (2026-10-26 10:56, 0 votes)
For local development runs, which supported execution path should we use when repository tests need TCP loopback and asyncio?

In our Kaggle notebook, network and user-namespace creation fail with EPERM, and no Docker daemon or KVM device is available. We need per-task private loopback with no access to notebook or model services and no external network, keeping the official harness and budgets unchanged.

Is the harness's Docker backend (with network none) available through a supported setup, or is another isolation configuration recommended? Does the official scoring environment provide loopback to repository tests? And are there any rules constraints on using that path for private development runs?


**** (2026-10-22 12:57, 0 votes)
Hi

I’m trying to reproduce the same filesystem isolation used by the official scorer before I start running my Paper Track experiments.
From the competition docs, `run_command` and `run_skill_script` run inside the same persistent Docker container. But in CPU and verified 4×L4 Kaggle notebook runtimes, I couldn’t find a Docker CLI, Docker socket, or `DOCKER_HOST`.
The public Getting Started flow seems to use the subprocess sandbox instead, and in that setup the shell is still running in the notebook filesystem. For my experiment, I need to make sure the agent cannot access things like reference patches, verification tests, or other evaluator-only files.
So I wanted to ask:

1. Is there a supported way to invoke the scorer’s Docker sandbox from a Kaggle notebook or the public harness? If it is available only during submission scoring, what supported external setup — image, configuration, and invocation — should researchers use to reproduce its filesystem isolation?
2. Which evaluator-only artifacts, including reference patches and verification tests, are structurally inaccessible to agent shell/skill execution during scoring, and how can researchers validate that same boundary using synthetic files?

I’m not asking for hidden evaluation data or special access. I just want to reproduce and validate the same isolation boundary before collecting experiment results.

Thanks


---

## Local notebook evaluation imports the installed package instead of the snapshot for some repos
/competitions/gemma-4-developer-agent/discussion/752672 | by  | posted 2026-10-25 21:14 | last comment 2026-10-25 21:14 | 0 comments | 0 votes


**** (2026-10-25 21:14, 0 votes)
Observed behaviour (local Kaggle notebook evaluation, subprocess sandbox):
When a temporary diagnostic test that only prints the package `__file__` is run from inside a fresh copy of a repository snapshot, the test process resolves some packages to the host-installed copy instead of the snapshot copy, while another repo resolves to the snapshot copy.

Steps to reproduce (no model run, no submission, no protected file modified):
1. Extract a repository snapshot to a fresh copy.
2. In that copy only, add a temporary diagnostic test that only prints the package `__file__` (it asserts nothing about any fix).
3. From inside the copy, with no PYTHONPATH set, run:
`PYTHONSAFEPATH=1 PYTHONNOUSERSITE=1 python3 -s -m pytest <diagnostic test> -s -p no:cacheprovider`
4. Observe the `__file__` printed from inside the test process.

Measured results with that command:
- For a requests snapshot: requests.`__file__` = /usr/local/lib/python3.12/dist-packages/requests/`__init__.py` (version 2.32.4) — the installed copy, not the snapshot copy.
- For a rich snapshot: rich.`__file__` = /usr/local/lib/python3.12/dist-packages/rich/`__init__.py` — the installed copy, not the snapshot copy. This was confirmed both with the diagnostic test at the copy root and with it under tests/.
- For a fastapi snapshot (control): fastapi.`__file__` = the snapshot copy fastapi/`__init__.py` — the snapshot copy, not an installed copy.

Context from HARNESS_README.md:
The guide describes an editable install step (`pip install -e /workspace`) in a fresh verification container, separate from the agent-execution container, and Docker as the default sandbox backend. In the local notebook subprocess path I observed, the install steps did not take effect in that way and the test environment inherited the host site-packages.

Question for the organisers:
Does final Kaggle scoring use the Docker backend with the editable install described in HARNESS_README.md, or the same subprocess path used by the local notebook evaluation cell? Clarification would help interpret local results for repos that are also installed in the host environment.

No task solutions and no agent design details are included in this report by design; only the import behaviour, the reproduction steps above, and the backend question.


---

## Check your agent config locally before you submit
/competitions/gemma-4-developer-agent/discussion/752671 | by  | posted 2026-10-25 20:53 | last comment 2026-10-25 20:53 | 0 comments | 3 votes


**** (2026-10-25 20:53, 3 votes)
With one submission per day and noise of about ±2 tasks, it is hard to tell whether a config change helps. My notebook runs two versions of an agent on the same public tasks, with the same model, harness and budgets as a submission. It grades the patches in a scorer-like sandbox (gold patches pass on 127 of 129 tasks) and shows the results task by task.

**Example:** in Budget-Fit (verracodeguacas, Apache 2.0) I set `thinking_budget` to 0 and compared both versions twice on 12 tasks:

| | thinking on | thinking off |
|---|---|---|
| run 1 | 3/12, 309 s | 3/12, 93 s |
| run 2 | 3/12, 276 s | 4/12, 104 s |

Without thinking the agent is ~3 times faster, but there is no visible difference in the score. On all 129 tasks thinking wins 48 to 23 (Ayush Thakur's run), but on 12 tasks that is less than the noise. The notebook shows the effect on time right away; for the score, it is worth trusting only large differences.

**Usage:** GPU L4 ×4, bundle A and bundle B with your change, run all. 12 tasks for two agents take about 1.5 to 2 hours.

Notebook: https://www.kaggle.com/code/zbigniewkirchner/gemma-4-agent-run-your-agent-locally


---

##  E4B submission returned "Submission Scoring Error: incorrect format"
/competitions/gemma-4-developer-agent/discussion/752128 | by  | posted 2026-10-23 18:46 | last comment 2026-10-25 16:03 | 4 comments | 0 votes


**** (2026-10-25 16:03, 0 votes)
Same here: E4B submission 57610130 got "incorrect format", while the same bundle, unchanged, scored fine the previous day. @ryanholbrook, would you check it?


**** (2026-10-24 17:12, 0 votes)
According to https://www.kaggle.com/code/ryanholbrook/gemma-4-developer-agent-small-model-leaderboard
The Small Model Submissions work


> **** (2026-10-24 18:03, 0 votes)
> Yes, I know they are generally working for the public. I would like to know what went wrong in my submission since except for the model itself the submission package is the same as my 31B submissions - which have scored in the past.


**** (2026-10-24 13:28, 0 votes)
@ryanholbrook Following up on this report: has any E4B submission scored end to end on the current scorer yet? And is ref 57552206 (“incorrect format” with a prompt/config-only bundle whose only change is model: gemma-4-e4b-it-qat-w4a16-ct) a problem with the E4B serving path, or part of the same scorer-side incident as "#751339?" We are holding a similar alias-only E4B bundle for the Small Model track and don’t want to spend a slot on something the scorer can’t serve. Knowing the served model name, chat template and tool-call parser used for E4B would also help.


**** (2026-10-23 18:46, 0 votes)
My E4B submission from 2026-10-23 06:42 UTC (ref 57552206) came back with "Submission Scoring Error: Your notebook generated a submission file with incorrect format".

- The zip has only four files: agent.yaml, eval_config.yaml, configs/sampling.yaml and prompts/system.md. There's no .pyc, `__pycache__` or anything else extra.
- The only difference from a package that has scored several times with the 31B is the model line: `model: gemma-4-e4b-it-qat-w4a16-ct`.
- It passes the validator from the current wheelhouse.
- It runs end to end in my local replica of the harness, serving the E4B QAT checkpoint.

My two submissions from 10-21 and 10-22 (57476860 and 57526293) failed with "Notebook Threw Exception", which you mentioned you'd rerun. This one has a different error message, so I'm not sure it's the same issue.

Could you check whether it's part of the same incident as [https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/751339](url) , or whether something about the E4B path makes the scorer produce a malformed output? If it's on my end, any hint about what to look for would really help. I'd like to enter the small-model track and don't want to burn more slots guessing.


---

## Possible server hang in vLLM 0.19.1’s Gemma 4 tool parser
/competitions/gemma-4-developer-agent/discussion/746336 | by  | posted 2026-10-06 20:39 | last comment 2026-10-25 07:48 | 1 comments | 1 votes


**** (2026-10-06 20:39, 1 votes)
During local evaluation with the competition’s vLLM 0.19.1 wheel, our server froze three times. The API process used 100% of one CPU core while memory kept growing. The GPU was idle, and the server stopped responding- even to `/v1/models`.

**Cause:** In `gemma4_tool_parser.py`, the array parser can get stuck if it encounters a closing bracket where it expects an array value. It keeps adding empty items without moving forward, eventually blocking the API server.
See: [vllm/tool_parsers/gemma4_tool_parser.py](https://github.com/vllm-project/vllm/blob/75efe07cd527ca1a5eeaa196b51b3a9a32c00692/vllm/tool_parsers/gemma4_tool_parser.py)

**Example:** `_parse_gemma4_array("a]")` reproduces the hang.

Malformed tool calls from Gemma can trigger this when a tool expects an array argument. In our setup, the affected argument was `args` in ADK’s `run_skill_script`, which is used by skills. In a fuzz test, about 10% of malformed arrays caused a hang.

**Why it matters:** The scorer runs tasks one after another on the same vLLM server. If a task triggers this bug, it could block that task and all later ones.

**Our Workaround:** Avoid array-valued tool arguments.

Newer vLLM versions include a check that can break out of the stuck loop, but the scorer uses version 0.19.1.


**** (2026-10-25 07:48, 0 votes)
Adding one more 0.19.1 parser problem that a submission can work around today, since the scorer pins the 0.19.1 wheel. Its `gemma4_tool_parser.py` is byte-identical to the vLLM `v0.19.1` tag (sha256 `682b2152…b6889`, as posted in 745138).

The parser unwraps only strings written between Gemma's `<|"|>` delimiters. If the model writes a string argument in plain JSON quotes, the quotes stay in the value: `skill_name:"my-skill"` arrives as `"\"my-skill\""`, the skill lookup fails, and the call is wasted. Upstream this is [vllm#51284](https://github.com/vllm-project/vllm/issues/51284), with a fix in [#51307](https://github.com/vllm-project/vllm/pull/51307); both are open, and neither is in 0.19.1. The hang fix [#41991](https://github.com/vllm-project/vllm/pull/41991) first shipped in v0.21.0, so the scorer does not have it either. The repro strings and the parser line references are in our comment on the upstream issue: https://github.com/vllm-project/vllm/issues/51284#issuecomment-6395016793

What a submission can do:

1. **Spell the delimiter in the prompt.** Gemma tends to copy the call spelling it is shown. Our instruction now reads: "Write every string of the call between <|"|> delimiters: a string written between plain JSON double quotes arrives with its quote characters kept, and that call is refused." It then shows the call as `skill_name <|"|>my-skill<|"|>, args [<|"|>search<|"|>, <|"|>--pattern<|"|>, <|"|>PATTERN<|"|>]`. Before this change, our first call copied the plain quotes from the prompt and was refused. We have not measured the effect on Gemma yet, so treat it as a mitigation.
2. **Keep argv flat.** `args:[[<|"|>start<|"|>]]` parses to `[["start"]]`. A script expecting a list of strings rejects it, and in our runs the model then resent the same call many times.
3. **Keep source code out of array arguments.** A plain-quoted element containing `]`, such as `args:["run","x = a[0]"]`, never returns from the 0.19.1 parser (the hang in this thread), and a comma inside a plain-quoted element splits it in two. Pass the source as a top-level string argument, for example to a write-file tool, and give the script a path.
4. **Test spelled calls through the stock parser before submitting.** In an environment with the 0.19.1 wheel:

```python
from vllm.tool_parsers.gemma4_tool_parser import _parse_gemma4_args
print(_parse_gemma4_args('skill_name:<|"|>my-skill<|"|>,args:[<|"|>search<|"|>,<|"|>--pattern<|"|>,<|"|>needle<|"|>]'))
# {'skill_name': 'my-skill', 'args': ['search', '--pattern', 'needle']}
```

Run it in a subprocess with a timeout, because of the hang.


---

## Rerunning "Notebook threw exception" notebooks
/competitions/gemma-4-developer-agent/discussion/752513 | by  | posted 2026-10-25 07:02 | last comment 2026-10-25 07:02 | 0 comments | 1 votes


**** (2026-10-25 07:02, 1 votes)
Do I need to rerun those notebooks or what? cuz I exprecienced them a few days back and @ryanholbrook did mention that it was error at their part and they would re run it. But its been 3-4 days now.


---

## Practical lessons: keeping a Gemma 4 agent inside time and tool-call budgets (what we changed after a timeout)
/competitions/gemma-4-developer-agent/discussion/752511 | by  | posted 2026-10-25 06:54 | last comment 2026-10-25 06:58 | 1 comments | 2 votes


**** (2026-10-25 06:54, 2 votes)
Our first full run of the agent timed out, so we spent a day tightening it. Sharing the general lessons in case they save someone else a submission. None of this is specific to our entry.

1. Budget for the slowest case, not the average. A run that usually finishes in a few minutes will still hit the limit on a hard task. Set the agent's own time limit comfortably below the scorer's charged limit, so it stops and returns a result instead of being killed.

2. Cap tool calls explicitly. Long exploratory loops are the usual cause of timeouts. A hard cap forces the agent to commit to an answer.

3. Drop moving parts you cannot afford. We removed a sub-agent because each hand-off cost time and added another place for a run to stall. If a component does not clearly pay for its latency, take it out.

4. Make the stopping rule part of the prompt. Tell the agent what a good-enough answer looks like and when to stop searching. Without that it keeps exploring.

5. Test the failure path. Run one deliberately slow task locally and confirm the agent returns something valid when it runs out of budget. A partial answer scores better than a timeout.

6. Change one thing at a time. When a run times out it is tempting to change several settings at once, but then you cannot tell which change helped.

Thanks to the people sharing their experiments in the other threads here, they were useful. What budget settings and stopping rules have worked for others?


**** (2026-10-25 06:58, 1 votes)
Free learning resources for the topics above:

Text:
- Anthropic, "Building effective agents": https://www.anthropic.com/engineering/building-effective-agents (simple, composable patterns versus complex frameworks)
- Gemma 4 function calling with Hugging Face Transformers: https://ai.google.dev/gemma/docs/capabilities/text/function-calling-gemma4 (tool definitions, parsing tool calls, returning results)
- Hugging Face Agents Course (free, hands-on): https://huggingface.co/learn/agents-course/en/unit0/introduction

Video:
- DeepLearning.AI, "Build agentic design patterns: reflection, tool use, planning, and multi-agent workflows": https://www.deeplearning.ai/courses/agentic-ai/ (the video lessons can be audited for free; quizzes and labs need a paid plan)

If you know other good free resources on agent budgets, stopping rules or evaluation, please add them.


---

## Scorer sandbox/runtime parity and traceback request for unchanged 31B baseline
/competitions/gemma-4-developer-agent/discussion/752490 | by  | posted 2026-10-25 05:02 | last comment 2026-10-25 05:02 | 0 comments | 0 votes


**** (2026-10-25 05:02, 0 votes)
Hi @ryanholbrook,

Could you help us close a few public-starter-to-scorer compatibility gaps?

Our unchanged four-file gemma-4-31b-it-qat-w4a16-ct agent, without LoRA or custom Python, scored 0.17 in submission 57048083. Byte-identical reruns 57470232 and 57517887 later ended with an unhandled notebook exception and no score. Their exposed episode lists were empty. Archive SHA-256 starts 1cb73986bd9ad168.

A private Kaggle GPU diagnostic now completes: the same baseline compiles, starts the model, executes native tools, passes all six empty/reference verification controls, and solves 2/3 audited public tasks. This uses starter v3's notebook image, wheelhouse v31, model /2, four L4s, TP4, gpu_memory_utilization=0.90, context32768 and VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=1. Agent limits remain 8min/28tools/80turns, command240s and verifier300s.

We recognize an important limitation: our diagnostic follows the starter's Python3.12 subprocess backend and adds repository-source import precedence. The published Dockerfiles specify Python3.13; the subprocess backend skips editable installation and test-dependency setup. These diagnostic additions are outside the scored ZIP. We are not claiming that 2/3 predicts hidden performance or that those earlier exceptions are fixed.

Could you please clarify:

1. What backend, Python version and sandbox image digest does each scoring phase currently use? Does the starter's same-configuration statement cover task setup as well as model serving?
2. What is the supported way to reproduce repository dependency installation and src-layout import precedence? Is there a scorer-equivalent public CPU verification image or command?
3. Does the deployed scorer use the current v31 core wheel artifacts, and what task concurrency, container resource limits and overall runtime limit apply?
4. Could you inspect 57470232/57517887 and share the failing stage and exception traceback, with hidden task details redacted?

The unchanged baseline was submitted again as 57616148 on October25 after this diagnostic; it was still pending at our last check. We can provide source/configuration hashes and diagnostic logs privately if useful. No hidden problems, tests or solutions are requested.

Thank you.


---

## Upvote if you have no success with LoRA so far, downvote otherwise
/competitions/gemma-4-developer-agent/discussion/752312 | by  | posted 2026-10-24 11:33 | last comment 2026-10-25 01:29 | 2 comments | -5 votes


**** (2026-10-24 11:33, -5 votes)
An anonymous survey


**** (2026-10-24 23:24, 0 votes)
What about those who don't have resources to train?! At double the hour billing rate for L4x4 GPU, the 30 hours per week is not sufficient even for running test inference!


> **** (2026-10-25 01:29, 0 votes)
> Try to get access to free GPU usage. Modal gives you 30$ per month for free.
> If you register for the first time with google compute platform, they even give you 300$ of free usage.


---

## Current scorer contract: charged time limit, compaction settings, and repository split
/competitions/gemma-4-developer-agent/discussion/752017 | by  | posted 2026-10-23 12:55 | last comment 2026-10-24 23:55 | 2 comments | 3 votes


**** (2026-10-23 12:55, 3 votes)
Hi Ryan and team,

Could you confirm these three details for the current scoring environment, so local evaluations can use the same contract?

1. **Time limit and timeout behavior.** The documentation gives a 12-hour patch-generation budget, including sandbox setup and excluding patch validation. Our displayed scoring runs have taken about 8.9–11.9 hours. Is the enforced global budget exactly 43,200 seconds, and which phases count toward it (inference-server startup, sandbox setup, model calls, and tool execution)? What happens when a per-task limit or the global limit is reached: is an existing workspace diff recovered, are remaining tasks scored zero, or can the whole submission fail? I understand from the 10 October reply in [747519](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747519) that queue time is excluded and the run covers the full hidden test set.

2. **Compaction settings.** Could you publish the current scorer's exact `EventsCompactionConfig` values: `compaction_interval`, `overlap_size`, `token_threshold`, and `event_retention_size`? [748584](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748584) notes a 32,768-versus-14,336 threshold discrepancy between the README and Getting Started notebook. Does the same compaction configuration apply to 31B, 12B, E4B, and E2B?

3. **Repository split.** The host reply on 9 October in [747248](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747248) says none of the published training repositories occur in the test set. Could you confirm that this remains true for both the public-leaderboard and private-leaderboard hidden tasks? We are asking about repository overlap, not hidden task identities.

Thank you for clarifying these points.


**** (2026-10-24 23:55, 1 votes)
I think patch validation is a batch process that happens after phase 1 task resolution container finishes for all the test tasks. If the first container exceeds 12 hours, the notebook times out. However, if the notebook is running beyond 12 hours (if there is no queing time involved), it means it has crossed the 12 hour restriction, and only patch validation is running which has no time restriction and hence notebook has entered safe zone and will not timeout. 

@ryanholbrook  - is the above understanding right?


**** (2026-10-23 15:19, 1 votes)
One data point on the global-limit question. On 22 October we submitted a config whose only change from an agent that had scored twice was an extra verification step (re-running the whole touched test file on every check). It ended with Notebook Timeout after about 12 hours: no partial score, and the daily slot was used. So in practice, exceeding the global budget fails the whole submission rather than scoring the finished tasks and zeroing the rest.

The same step looked almost free in our local runs on the public repos (about +5% median time per task), so local timing seems to under-estimate the cost of test-running steps on the hidden repos. With your 8.9-11.9 h runs, the margin looks thin for everyone.

@ryanholbrook +1 on the per-task question: when a task hits its own time or tool-call limit, is the existing workspace diff still submitted and graded?


---

## Difficult part in this competition is dealing with wheels, agree or not?
/competitions/gemma-4-developer-agent/discussion/751760 | by  | posted 2026-10-22 17:58 | last comment 2026-10-24 12:53 | 2 comments | 5 votes


**** (2026-10-22 17:58, 5 votes)
I think one of the most difficult parts in this competition is to get resolved=True when the model output the same patch as the golden patch. The scorer environment makes it resolved=False even with the exact golden patch.

I spent a week to try to solve this problem but in vain. I found that some problems come from the wheels installation (incompatible python version) and unknown test cases (say you have patched a function, you need to run some tests or all? if all, there is no httpbin installed and no related wheels).

The environment of the starter notebook is python 3.12 , while the vm is 3.13. The wheels are mostly compiled with 3.13 with some any.

I have written a plain notebook to try to run all golden patches in the scorer environment. The result is not 100% resolved.

You may refer to my notebook : https://www.kaggle.com/code/dennisfong/gemma-4-golden-patch-evaluation

Anyone has idea?


**** (2026-10-22 18:30, 1 votes)
Thanks for sharing the full log, it makes the pattern easy to read.

The 0/48 on rich has one cause: the resolver picks pytest 6.2.5 (conflicts=pytest), but the venv still sees the host's /usr/local/lib/python3.13/dist-packages/py.py. That shim comes from newer pytest and imports _pytest._py, which does not exist in 6.2.5, so collection dies before any test runs. Keeping host dist-packages off the venv path (or not letting rich fall back to pytest 6.2.5) should flip most of them.

You may not need to rebuild this from scratch: zbigniewkirchner published "Local eval in a scorer-like sandbox: gold patches pass on 127/129 public tasks (was 52)". It replaces install_test_dependencies with a clean per-repo venv and adds a few calibrations (Pygments for some rich tasks, werkzeug 2.3 for the requests/httpbin tests, Python 3.12 for two tasks). Its 52 baseline matches what you are seeing, so this looks like a local-environment problem rather than the scorer rejecting gold patches.

The part I am curious about: your fastapi failures (15785 / 15763 / 15745 on test_router_include_context, plus 14356 and 14186) don't look like the pytest issue. If you run them in that sandbox, do any still fail with the gold patch? And @zbigniewkirchner, which are the 2 tasks out of 129 that still fail for you?


> **** (2026-10-24 12:53, 0 votes)
> Zbigniew's notebook [clearly shows](https://www.kaggle.com/code/zbigniewkirchner/gemma-4-agent-do-gold-patches-pass-locally#The-2-tasks-no-environment-can-pass) that the two public tasks that are unable to pass are the ones with instance_id rich_3486, which is impossible to pass because one test function requires python version < 3.11 while another test function of the same task requires python version >= 3.11 and instance_id fastapi_14186, where two test functions of the same task demand different versions of pydantic.


---

## The submission with directory entries fails
/competitions/gemma-4-developer-agent/discussion/752282 | by  | posted 2026-10-24 08:09 | last comment 2026-10-24 08:09 | 0 comments | 2 votes


**** (2026-10-24 08:09, 2 votes)
Please, be advised that if you archive your submission with directory entries - your submission will fail in an hour without any explanation. Already lost two submissions. The proper command to execute zip inside your submission folder should be:
`zip -D -X -r ../submission.zip .`
If you skip `-D` argument (without directory entries) - your submission may fail.

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F525226%2Ff8536ecbedbf40d1c7be9e9bce869770%2FScreenshot%20from%202026-10-24%2011-10-03.png?generation=1792829440272203&alt=media)


---

## Stronger models barely beat Gemma 4 31B in this harness — teacher comparison on 124 public tasks
/competitions/gemma-4-developer-agent/discussion/747168 | by  | posted 2026-10-08 08:34 | last comment 2026-10-24 03:21 | 4 comments | 37 votes


**** (2026-10-08 08:34, 37 votes)
Hi all — sharing an experiment in case it saves someone time/money.

**Question:** is our score limited by the model, or by the harness setup? If a much stronger
coding model (one that gets ~80% on SWE-bench Verified) runs through *exactly the same* agent
config, how much better does it do?

**Setup** (identical for all models)
- Same submission YAML (sample prompt, `get_code_subgraph` removed), same harness (swegemma 0.2.7,
  2026-09-30 build), events compaction enabled as in the official notebook, 32k context.
- Budget: 25 min / 50 tool calls per task, one task per process.
- 124 of the 129 public tasks. We fixed local test environments so that, for every one of these
  124, the gold patch passes and an empty patch fails (5 tasks could not be made scorable locally).
- Gemma: `gemma-4-31b-it-qat-w4a16-ct` on vLLM 0.19.1, 2 independent passes.
- Teachers via OpenRouter, routed through the same harness: DeepSeek V4 Pro, Qwen3.6-27B, 1 pass each.

**Results**

| model | resolved | median minutes/task |
|---|---|---|
| Gemma 4 31B, pass 1 | 54/124 | 5.2 |
| Gemma 4 31B, pass 2 | 53/123 | 5.2 |
| DeepSeek V4 Pro | 58/124 | 3.5 |
| Qwen3.6-27B | 59/123 | 3.9 |

- The teachers are only +4–5 tasks ahead. For scale: between Gemma's two identical passes, 19 of
  123 tasks (15%) flipped between solved and failed.
- Of the 60 tasks Gemma failed in *both* passes, the two teachers combined solve only 10;
  **48 are solved by nobody**. The teachers also fail 11–12 tasks that Gemma solved at least once.
- Union of all 4 runs: 73/123.

**Takeaways (our interpretation)**
1. In this harness, the ceiling seems to come from the setup (32k context + compaction, call
   budget, sparse task descriptions — many are just "Fixes #NNNN"), not from raw model strength.
   Distilling a stronger teacher can't add much "new capability" here; the extra solves are few.
2. The teachers are noticeably *faster* (3.5–3.9 vs 5.2 min median). With ~5.5 min/task available
   in the 12 h official run, speed may matter more than extra capability.
3. Single runs are very noisy — be careful comparing prompt variants on small task batches.

**Two harness gotchas we hit along the way**
- `run_command` is a synchronous tool, so it blocks the event loop. If you run several tasks
  concurrently in *one* eval process, one slow command (e.g. an agent's script hitting the 300 s
  timeout) freezes every task in that process, while their time budgets keep ticking. Run one task
  per process if you care about timing.
- Gemma 4 `edit_file` calls whose `old_string` contains a `"""` docstring sometimes get mangled by
  vLLM's gemma4 tool-call parser (argument keys like `<|"|>,filepath`), so ADK rejects them with
  "mandatory input parameters are not present". The model then tends to retry the identical call
  many times (27× in one trace). Rejected calls don't count toward the tool-call cap, but they do
  cost time.

Happy to answer questions. Numbers are from a single pass per teacher, so treat ±5 tasks as noise.


**** (2026-10-08 09:45, 2 votes)
Thanks for sharing this. I had some results which I was thinking to compile and write up a discussion post but this is solid. 

All I wanna add is that this is true. The model capability is restrained by the harness and compute capacity. I ran a similar setup with gpt4.1, gpt5, etc. They all kinda came around the same ballpark.


**** (2026-10-09 08:07, 1 votes)
How did you go about fixing local test environments for the 124?


**** (2026-10-08 09:24, 1 votes)
Blur queries, less than 32k context and limited time make the competition difficult than actually in use, maybe that's why teachers seem like this


**** (2026-10-24 03:21, 0 votes)
Very useful, thanks. The 15% flip rate between two identical Gemma passes matters for reading the leaderboard too: with the public split being roughly half of ~120 tasks, a 0.02 gap (0.22 vs 0.24) is about one or two tasks, which is inside run-to-run noise. It suggests spending daily submissions on changes with an expected effect of several tasks (thinking settings, per-task time cap, tool budget) rather than small prompt wording tweaks, and resubmitting the same config occasionally to see your own variance.


---

## Gemma 4 agent experiments: sampling, thinking, time limits, and tool ablations
/competitions/gemma-4-developer-agent/discussion/746250 | by  | posted 2026-10-06 16:00 | last comment 2026-10-24 03:20 | 11 comments | 46 votes


**** (2026-10-24 03:20, 1 votes)
Thanks for such a thorough ablation. One thing that may explain the empty search_similar_code results: the embeddings in the dataset are stored per node id (<node_id>.npy), so the tool most likely resolves a stored vector for a symbol rather than encoding free text, and a paraphrase finds nothing. In a model-free localization study on the public tasks (117 with a gold edit site in the graph), seeding from exact symbol names and expanding with get_code_neighbors put the edit site within 2 hops for 47.9% of tasks, versus 14.5% Hit@5 for TF-IDF keywords. So a variant worth testing is a prompt that tells the agent to copy exact node ids from a grep and pass those to the graph tools. Numbers and code are in my writeup and notebook if useful: https://www.kaggle.com/code/alikalwar/code-graph-bug-localization-benchmark-gemma-4-pap


**** (2026-10-06 16:00, 46 votes)
I evaluated `gemma-4-31b-it-qat-w4a16-ct` using 32 B40 GPUs by CoreWeave, with one independent inference replica per GPU and tasks sharded across replicas to shorten evaluation turnaround.

All results below use the same 129-task local evaluation set. Resolved percentages are `resolved / 129 × 100`, including errored or incomplete tasks in the denominator. These are single-run observations with known local scoring limitations; small differences need repeat evaluations.

**TL;DR**
- **Keep thinking and thought summaries enabled.** Temperatures 0.4 and 1.0 tied; I retained temperature 1.0, top-p 0.95, and a 4,096-token thinking budget. If you are post training, these parameters are good baseline.
- **15 minutes was the best local quality-sweep setting, not a Kaggle submission budget.** It resolved 54/129 tasks with fewer task-hours and tokens than the 60-minute run which also resolved the same number of tasks. Shorter limits caused many timeouts but they anyway failed on the longer run. The Kaggle calibration at the end of this post supersedes this as the operational runtime guidance.
- **Graph retrieval showed no observed benefit.** Semantic searches returned empty results, and overall quality did not improve.
- **The analyzer subagent showed no clear gain.** It resolved one additional task with slightly higher median runtime; repeat runs are needed. This can be explored more especially to solve tasks with multi file gold patches.
- **Halving the tool budget traded quality for speed.** Moving from 50 to 25 calls reduced median runtime by 29%, but resolved 14 fewer tasks.

**Which sampling and thinking settings worked best?**

The reference configuration, E9, used temperature 0.2, top-p 0.95, a 4,096-token thinking budget, and thought summaries enabled. This screen used a 60-minute active time cap, 50 tool calls, and 80 turns.

| Run | Change | Base | Resolved / 129 | Resolved % |
| --- | --- | --- | ---: | ---: |
| E9 | Reference configuration | — | 48 | 37.21% |
| E10 | Temperature 0.0 | E9 | 47 | 36.43% |
| E11 | Temperature 0.4 | E9 | 51 | 39.53% |
| E12 | Temperature 1.0 | E9 | 51 | 39.53% |
| E13 | Top-p 0.80 | E9 | 48 | 37.21% |
| E14 | Top-p 1.00 | E9 | 48 | 37.21% |
| E15 | Thinking budget 2,048 | E9 | 50 | 38.76% |
| E16 | Thinking budget 6,144 | E9 | 48 | 37.21% |
| E17 | Thinking disabled | E9 | 23 | 17.83% |
| E18 | Thought summaries disabled; thinking 4,096 | E12 | 35 | 27.13% |
| E19 | Thought summaries disabled; thinking 2,048 | E18 | 34 | 26.36% |

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F2212893%2F07c7b67f48faf8dbc839bf7a23a8e921%2Fimage%20(3).png?generation=1791302375512529&alt=media)

**E11 and E12 tied at 51 resolved tasks.** I carried E12 forward: temperature 1.0, top-p 0.95, thinking 4,096, and summaries enabled. The clearest observed losses came from disabling thinking or hiding thought summaries. Increasing the thinking budget to 6,144 did not improve the resolved count in this screen.

**How much active time did the agent need?**

I varied the active time cap while retaining E12’s configuration. Active time excludes setup and verification; the runtime medians below measure per-task elapsed time.

| Run | Active cap | Resolved / 129 | Resolved % | Session timeouts |
| --- | ---: | ---: | ---: | ---: |
| E20 | 6 min | 37 | 28.68% | 61 |
| E21 | 10 min | 46 | 35.66% | 26 |
| E22 | 15 min | 54 | 41.86% | 3 |
| E23 | 20 min | 49 | 37.98% | 4 |
| E12 | 60 min | 51 | 39.53% | 0 |

**I selected 15 minutes for the local quality sweep, not for a Kaggle submission.** It produced the highest observed resolved count in this sweep, with 9.2% fewer task-hours and 10.2% fewer tokens than the 60-minute run. The three-task score difference needs repetition before attributing it to the shorter cap.

**Did graph retrieval tools help?**

E32 added semantic code search, code-neighbor retrieval, and subgraph retrieval to E30’s toolset.

E32 resolved **50/129 (38.76%)**, compared with historical E30’s **55/129 (42.64%)**. Median task runtime increased from **6.57 to 7.33 minutes**.

Tool usage was limited:

- Graph tools were used on 21 of 129 tasks.
- All 21 semantic searches returned empty results.
- Seven of ten neighbor calls returned nonempty results.
- Subgraph retrieval was never used.
- None of the 31 graph calls returned an exact gold-file path before the first successful edit.

**This integration did not show an observed benefit.** The findings apply to the tools and index we tested. E30 was a historical control, and these runs do not establish a general effect of graph retrieval.

**Did an analyzer subagent help? What happened with fewer tool calls?**

The follow-up study compared a manual system prompt, the same prompt with an analyzer subagent, and the manual prompt with a reduced tool budget. All used a 15-minute active cap.

| Run | Configuration | Resolved / 129 | Resolved % | Median elapsed min |
| --- | --- | ---: | ---: | ---: |
| E30 | Historical recurring 7-minute prompt gate; 50 calls | 55 | 42.64% | 6.57 |
| E34 | Repeat E30; 50 calls | 48 | 37.21% | 6.97 |
| E35 | Manual prompt; 50 calls | 50 | 38.76% | 6.77 |
| E36 | Manual prompt + analyzer; 50 calls | 51 | 39.53% | 6.97 |
| E37 | Manual prompt; 25 calls | 36 | 27.91% | 4.80 |

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F2212893%2F9296eedccc447ed5a012c3bf97f7639a%2Fimage%20(4).png?generation=1791302400349373&alt=media)

**Adding the analyzer changed the resolved count from 50 to 51**, with slightly higher median runtime. That one-task difference needs repetition.

**Reducing the tool budget to 25 calls lowered median runtime by 29% versus E35, but resolved 14 fewer tasks.** This was a substantial observed quality–runtime tradeoff.

E34’s repeat also matters: the same selected E30 configuration resolved 48 rather than 55 tasks. The table uses E34’s completed launch; an earlier launch failed before inference because a prompt file was missing.

The accompanying report contains the full experiment legend and figures, including median and P90 runtime comparisons. I would be interested in whether others see similar thinking-summary behavior, graph-tool adoption, or subagent gains on repeated evaluations.

---

## Update: Kaggle 4×L4 runtime calibration

I did a 12-task calibration twice on Modal 4×L4 and once directly on Kaggle 4×L4 (TP=4, sequential agent). The direct Kaggle run processed 5.55M reported model tokens in 5,002s of LLM time: **900.8s/M tokens**, **1,110 total tok/s**, and **8.68s/model call with thinking enabled**.

| Serving setup | Seconds / 1M tokens | Effective tok/s | Time/token vs loaded B40 |
| --- | ---: | ---: | ---: |
| Concurrently loaded B40 baseline | 1,170.6 | 854 | 1.000× |
| Modal 4×L4, two runs pooled | 927.6 | 1,078 | 0.792× |
| Kaggle 4×L4, sequential | 900.8 | 1,110 | 0.770× |

The B40 baseline had multiple concurrent agents while Kaggle was sequential, so **0.770× is an end-to-end serving factor for these workloads, not a pure hardware comparison**.

The full-workload central estimate is **11.03h for 120 tasks** (11.23h if all observed fixed notebook/vLLM setup is counted), but run-to-run variance is large. Operationally I will use **5.5 min/task on Kaggle**: 120 × 5.5 = 11h, leaving about 1h for Phase-1 setup and overhead. For the same concurrently loaded B40 setup, the provisional equivalent is **7.0 min/task**. This conversion is workload-specific.

PS: I have access to compute for some more time, thus I will be sharing more such results and public datasets so that others can benefit from it. I hope it helps answer some questions. Please let me know if you all would like to get something interesting answered.

PSS: The gains will come from post training. Data curation and fine tuning should be center of research.


**** (2026-10-10 16:49, 0 votes)
Your graph-retrieval result matches something I measured from the other direction. Without running the model, I checked how often plain lexical search over the issue text finds a file the reference patch edits, on all 129 public tasks: the first identifier-grep hit is right 30% of the time, grep + BM25 fused gets 61% in the top 5 and 74% in the top 10. 35 of 128 issues contain no code identifier at all (merged-PR titles plus a link). So localization is a real bottleneck, and since the semantic search returned nothing in your runs, a "list candidates before reading" step might be worth an ablation. I haven't scored that yet.

Numbers and code: https://www.kaggle.com/code/hitarthjain0/gemma-4-agent-can-grep-find-the-bug


**** (2026-10-10 14:55, 0 votes)
Followup: https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747857 

Covers: 
- calibration data between my infra setup and Kaggle 4xL4 -- 5.5 mins of max time is safe and good. This gives you a trajectory of 40-50 llm and tool calls spanning 300-350k tokens (input+thinking+output) for successful passes.
- impact of system prompt and no system prompt
- impact of command timeouts -- nothing


**** (2026-10-07 21:49, 0 votes)
Your notes on the thinking budget was very useful. I thought it would blow the time budget. Trying it next.


**** (2026-10-06 20:39, 0 votes)
The E30 repeat going from 55 to 48 resolved tasks caught my attention. Do you have the task-level overlap between those runs? It would be useful to see whether the analyzer consistently fixes a particular kind of failure, even if the total only moves by one task. Thanks for sharing the ablations and calling out the single-run limits.


> **** (2026-10-08 14:36, 0 votes)
> yes there's noise for sure. I do have task level overlap results. I will share as a separate post. Just cleaning up.


**** (2026-10-06 16:52, 0 votes)
Thanks a lot for running and sharing this! This saves a lot of time and compute for us. I was running similar experiments but with limited compute and on fewer tasks, so it's amazing to see it scaled up.

You said you have access to compute for some more time. Could you run the time-cap sweep at Kaggle's speed, on 4xL4 with a single replica at tensor parallel 4? I assume for these runs you used your faster GPUs, and even there accuracy kept climbing from 6 to 10 to 15 minutes.

Kaggle allows about 5.5 minutes per task on submission (without tool cap) including setup, so even 6 min cap is out of reach there, on slower hardware. 

It would help to know roughly how your seconds per model call compare with Kaggle's (I measured about 3.8s per call on 4x L4 with thinking off)


> **** (2026-10-06 17:01, 1 votes)
> Yes, I used the Blackwell RTX 6000 pro GPUs. Yes the reported time doesn't map to 4xL4 and for this reason, I am currently running a calibration test. I have been trying to use Kaggle's infra but stuck in queue for the last 2 days. 
> 
> I just rented 4xL4 on modal for few hours to get the calibration numbers in. I can then do an approximate calculation. 
> 
> Thanks for sharing that 5.5 minutes per task per submission is allowed -- I wasn't aware about it. Yes the caps I used doesn't translate to Kaggle runtime. I will come back with the results you have asked.


> > **** (2026-10-06 18:46, 0 votes)
> > Thanks, looking forward to the calibration numbers.
> > 
> > Just to be clear about the 5.5 minutes: it is not a rule, it is 12 hours divided by about 120 tasks, minus setup.
> > It assumes every task runs into the time cap, which is the safe worst case.
> > In our scored runs, a 4.5-minute cap took about 10 hours, so each task adds roughly 0.5 minutes of setup and verification on top of the cap.
> > 
> > A bigger cap, say 6-7 minutes, can still fit if enough tasks end early, either because the agent submits or because it hits a tool-call cap before the time cap.
> > But that is much harder to control: it depends on how the agent behaves on the hidden tasks, which we can't observe, and going over 12 hours errors the whole submission.


> > **** (2026-10-07 14:46, 2 votes)
> > Thanks — the calibration is complete now.
> > 
> > I ran a stratified 12-task panel twice on Modal 4×L4 and once directly on Kaggle 4×L4 (TP=4, sequential agent). Kaggle processed 5.55M reported model tokens in 5,002s of LLM time: **900.8s per million tokens**, or **1,110 total tokens/s**. The average was **8.68s per model call with thinking enabled**; seconds/call is very context-length dependent, so it is not directly comparable to the 3.8s thinking-off number.
> > 
> > The loaded CoreWeave B40 baseline measured 1,170.6s/M tokens (854 tok/s), giving an empirical Kaggle/B40 time factor of **0.770×**. Important caveat: the B40 servers were handling multiple concurrent agents, while Kaggle was sequential. This is therefore an end-to-end serving factor for my actual setups, not a pure hardware comparison.
> > 
> > Applied to the full E22 workload, the central projection is **11.03h for 120 tasks** (11.23h if I conservatively include the observed 12.6m fixed notebook/vLLM setup). Variance remains large, so I agree that 6–7 minutes on Kaggle is unsafe as a worst-case cap.
> > 
> > Operationally I will use:
> > 
> > - **Kaggle 4×L4: 5.5 min/task** — 120 × 5.5 = 11h, leaving about 1h for Phase-1 setup and overhead.
> > - **Current concurrently loaded B40 setup: 7.0 min/task** — workload-calibrated from the measured 0.770× factor, not a universal B40 conversion.
> > 
> > Thus my result on my setup with 6 minutes max time per task reaching pass rate of 28.68% is close to what I would consider a baseline for myself.


**** (2026-10-07 05:26, 2 votes)
thanks for sharing this.


---

## LoRA adapters on smaller variants (12B / E4B / E2B): confirmed on the scorer’s vLLM 0.19.1?
/competitions/gemma-4-developer-agent/discussion/752239 | by  | posted 2026-10-24 03:12 | last comment 2026-10-24 03:12 | 0 comments | 0 votes


**** (2026-10-24 03:12, 0 votes)
Has any submission with a LoRA adapter on a smaller variant (12B, E4B or E2B, -it-qat-w4a16-ct) been scored end to end on the scorer’s vLLM 0.19.1? vLLM issue #40693 reports Gemma 4 LoRA errors on 0.19.x, and I couldn’t tell whether the scorer’s build includes the fix (PR #39291). If adapters on smaller variants are supported, what are the limits (max rank, target modules)?


---

## Two Final Submissions: is the private score the better of the two?
/competitions/gemma-4-developer-agent/discussion/752220 | by  | posted 2026-10-24 00:37 | last comment 2026-10-24 01:05 | 1 comments | 0 votes


**** (2026-10-24 01:05, 0 votes)
It is the better of the two private leaderboard scores. There’s no downside to selecting a second submission.


**** (2026-10-24 00:37, 0 votes)
The rules allow up to two Final Submissions. For this code competition, is a team's private leaderboard score the better of the private scores of its two selected submissions, as in most Kaggle competitions, or is it computed some other way? And if one selected submission ends in an error, is the other one scored on its own?  @ryanholbrook , could you confirm? Thanks.


---

## Our whole entry is public: configs, local runs, hidden scores (Apache-2.0)
/competitions/gemma-4-developer-agent/discussion/751973 | by  | posted 2026-10-23 09:15 | last comment 2026-10-23 21:49 | 3 comments | 1 votes


**** (2026-10-23 09:15, 1 votes)
Sharing our code publicly, as the rules ask:
https://github.com/rodriguescarson/gemma-swe-agent

It has every agent configuration we submitted, the per-task results of every 74-task local run (on Kaggle's 4xL4 and on a GPU paced to it), all our hidden scores, and the rules we wrote down before each run.

One finding that might save you a slot: our local screen never ranked our hidden scores. Two configs that tied at 28/74 locally scored 0.17 and 0.10 on the hidden set. A change that won 9-0 against its parent locally scored lower hidden. Single tweaks moved about one task either way.

Our best is 0.17, so this is as much a record of what didn't work as of what did. Code is Apache-2.0.


**** (2026-10-23 21:49, 0 votes)
Thanks for sharing!  Really appreciated.

I have a similar pipeline which have not yet crossed 0.08, so trying some new things..


**** (2026-10-23 10:40, 0 votes)
You dont have to share your code publicly


**** (2026-10-23 16:42, 1 votes)
Thanks I guess


---

## Ay update on the search_similar_code tool ?
/competitions/gemma-4-developer-agent/discussion/751986 | by  | posted 2026-10-23 10:34 | last comment 2026-10-23 10:34 | 0 comments | 3 votes


**** (2026-10-23 10:34, 3 votes)
hi competition maintainers,

@ryanholbrook you guys are doing awesome work thank you for that. i have a question is open sourcing the model that did the embedding and how it did it on the cards ?

currently i am looking at external data to train, but unfortunately i will have to disable this tool since i tried >10 embedding models + many flavours of gnn to replicate the embeddings with no significant similarity.

if it is gonna happen please do it sooner thanks.


---

## [Open Benchmark Suite - 10.0 Usability] Trap-25 Bug Traps, 300 SWE Loop Pairs & W4A16 <|think|> Budget Sweep for Gemma 4 Agents
/competitions/gemma-4-developer-agent/discussion/751959 | by  | posted 2026-10-23 07:44 | last comment 2026-10-23 07:44 | 0 comments | 3 votes


**** (2026-10-23 07:44, 3 votes)
Hi everyone! 👋

To help benchmark **Turn 4+ loop recovery**, **repository code-graph backtracking (`get_code_neighbors` / `get_code_subgraph`)**, and **quantized `w4a16-ct` `<|think|>` budget scaling** for the Gemma 4 Developer Agent competition, I've open-sourced four companion datasets (all `10.0 / 10.0` Usability, Apache 2.0) and a reproducible verification notebook:

1. **[Gemma 4 Loop-Breaker & Trap-25 Benchmark (`trap_tasks_25.jsonl`)](https://www.kaggle.com/datasets/robinamirbahar/gemma-4-loop-breaker-and-trap-25-benchmark)** – 25 self-contained Python tasks across `httpx`, `requests`, `fastapi`, `rich`, and `sci_compute`, each with a verified `buggy_code`, deceptive 1st-guess `trap_patch`, and `gold_patch`.
2. **[SWE-Agent Action-Similarity & Loop-Recovery Corpus](https://www.kaggle.com/datasets/robinamirbahar/swe-agent-action-similarity-loop-recovery-corpus)** – 300 labeled multi-turn edit pairs for calibrating LCS diff-similarity (`S_diff`) and action-entropy (`H_W`) loop detectors.
3. **[LLM W4A16 Quantization vs. `<|think|>` Budget Benchmark](https://www.kaggle.com/datasets/robinamirbahar/llm-w4a16-quantization-thinking-budget-bench)** – 240-run telemetry sweep across `<|think|>` budgets `{128 .. 6144}` on `gemma-4-31b-it-qat-w4a16-ct`.
4. **[Gemma 4 G-CCR Output Artifacts & Telemetry](https://www.kaggle.com/datasets/robinamirbahar/gemma-4-ccr-output-artifacts)** – Full 4-arm ablation telemetry (`16.0% → 96.0%` recovery, `-70.8%` KV tokens).
5. **[Reproducible Verification Notebook (`gemma4_loop_breaker_kaggle.ipynb`)](https://www.kaggle.com/code/robinamirbahar/gemma-4-loop-breaker-ccr-verification)** – Runs the full 100-trajectory evaluation in ~10 seconds.

Feel free to use these benchmarks in your own experiments and ablations—feedback and questions are very welcome!


---

## training datasets for SWE agents
/competitions/gemma-4-developer-agent/discussion/751944 | by  | posted 2026-10-23 06:05 | last comment 2026-10-23 06:05 | 0 comments | 1 votes


**** (2026-10-23 06:05, 1 votes)
can anybody share links for some good datasets for training on huggingface...SWE agent trajectories


---

##  fastapi tasks can't pass even with the gold patch
/competitions/gemma-4-developer-agent/discussion/747248 | by  | posted 2026-10-08 12:29 | last comment 2026-10-23 04:04 | 12 comments | 15 votes


**** (2026-10-23 04:04, 1 votes)
A follow-up on the second effect Nur describes, for anyone collecting agent trajectories on the public rich tasks.

`wheels/` ships `rich-15.0.0`, released 2026-04-12, after every public rich task was opened. The harness unpacks it into site-packages, so every rich sandbox holds a released rich that already contains the upstream fix for the tasks we ran. The tests import `/workspace`, so this isn't the test shadowing seen with requests. The leak is in what the agent can read: `find / -name <file>.py`, a listing of `/wheels`, or `python script.py` run from outside `/workspace` all reach the fixed 15.0.0 code.

Gemma 4 never looked there in our 537 traces. Stronger models did: in 11 runs of three newer models on 5 hard rich tasks, 9 read 15.0.0's copy of the file they were fixing, and 8 of the 10 solves took the fix from it, one right after calling it "cheating" in its own step message. A line in the task prompt against searching outside `/workspace` held only until context compaction dropped it.

So if you distil from a stronger model's rich trajectories, or trust its local resolve rate: check each trajectory for reads outside `/workspace` (`/usr`, `/wheels`, site-packages, `pip show rich`) and cut it at the first one or drop it. Otherwise the student learns to look for a fixed copy that won't be there at scoring.

The leaderboard shouldn't be affected: the hidden tasks come from private repositories not available publicly (Ryan in https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744951), so no released copy of them can sit in the scoring sandbox.


**** (2026-10-08 12:29, 15 votes)
# Scoring environment: pydantic fails to import (no `typing-inspection` wheel), so fastapi tasks can't pass even with the gold patch

Hi all, and a question for the hosts.

While reproducing the scoring pipeline locally I found that the evaluation container, as defined by the public
harness, can't import pydantic. If I'm reading it right, almost every fastapi task is unsolvable, even with the
reference patch. That would also explain why the public LB is so compressed 

## What the harness does (swegemma 0.2.7)

- Verification runs in `docker/Dockerfile.public`, which is `python:3.13-slim` plus pytest and a few build backends.
- `container_setup._ensure_container_site_packages` → `_inspect_wheels_dir` → `_deduplicate_wheels` keeps the
  **highest py3.13-compatible version of each package** in `wheels/` and unpacks those into
  `/usr/local/lib/python3.13/site-packages`. That happens once, with the same set for every task.
- `sandbox/setup.py --fast-path` then adds the workspace through a `.pth` file. No dependencies are resolved per task.

## The problem

`wheels/` contains `pydantic-2.13.4` and `pydantic_core-2.46.4`, but **no `typing_inspection` wheel**. pydantic ≥ 2.11
requires it, so any test that imports fastapi fails at collection:

```
tests/test_x.py:1: in <module>
    from fastapi import FastAPI
fastapi/exceptions.py:5: in <module>
    from pydantic import BaseModel, create_model
.../site-packages/pydantic/errors.py:9: in <module>
    from typing_inspection.introspection import Qualifier
E   ModuleNotFoundError: No module named 'typing_inspection'
```

A second, smaller effect: `wheels/` also contains releases of the repos under test (fastapi, requests, httpx, rich).
Because those are unpacked into site-packages, which comes before the `.pth`-added `/workspace` on `sys.path`, some
tests import the bundled release instead of the patched repo (`src/`-layout requests, and httpx). A gold patch can
then have no effect (e.g. httpx_3672: `module 'httpx' has no attribute 'Stream'`).

## Gold-patch check on the 129 public tasks

I applied each task's reference `patch` in a local copy of this setup (Python 3.13, newest wheel per package from the
provided `wheels/`, the harness's own setup and verification code):

| repo | tasks | resolved with the gold patch |
|---|---|---|
| fastapi | 67 | 1 |
| rich | 48 | 39 |
| requests | 13 | 3 |
| httpx | 1 | 0 |
| **total** | **129** | **43 (33%)** |

The one fastapi task that passes (fastapi_15661) is the one whose test doesn't import pydantic. Re-scoring my own
agent's patches in this setup gives ~12%, which matches my public LB score. So I believe this reflects what the real
scorer does, though I can't see it directly.

## Questions for the hosts

1. Is this intended?
2. If not, could `typing_inspection` be added to `wheels/`? Could the repo-under-test's own wheel be excluded from injection, or `/workspace` be put ahead of site-packages? Those two fixes would let gold patches pass again.
3. Will the private split be scored in the same environment as the public one, and will any fix be applied before the final deadline (and to already-submitted entries)?

Happy to share more details or the exact reproduction steps. Thanks!


**** (2026-10-09 13:30, 5 votes)
Hi @mkrimenurgm, I'm working on fixing up the set of training tasks. None of the repos in the training tasks are present in the test set, however. I can verify that every task in the test set is solvable and validates at 100% with a "gold patch" submission.


> **** (2026-10-09 14:57, 0 votes)
> Thank you so much!


> **** (2026-10-16 03:22, 0 votes)
> Hi, is there an update on this?


**** (2026-10-08 15:54, 1 votes)
Thank you for sharing this. I also have the same issue.
@ryanholbrook, could you help with the questions? Many thanks...


**** (2026-10-08 15:19, 1 votes)
I think this notebook can help you: 

https://www.kaggle.com/code/busyaprime/119-of-129-sound-the-gemma-4-grader-rebuilt


> **** (2026-10-08 17:39, 0 votes)
> thank you! i also created a similar env but its still a problem if they use unknown environment for scoring. It's important to create a local gym before getting into the juicy stuff.


**** (2026-10-20 18:53, 0 votes)
Thanks for confirming that the test repositories differ from the training repositories and that the test set validates with gold patches. We independently reproduced training-kit failures using swegemma 0.2.11, the supplied docker/Dockerfile.sandbox, all 124 public wheels, Python 3.13.16, network disabled, 2 CPUs and 4 GiB:

- rich_3718: gold passes; empty patch fails.
- fastapi_13713: both fail collection with missing typing_inspection and dirty_equals.
- requests_6592: both fail; gold has 185 fixture errors, beginning with a recursive httpbin fixture dependency in tests/conftest.py:25.

Our rebuild installed pytest 9.1.1; the public wheel set lacks typing_inspection, dirty_equals and pytest-httpbin. These CPU checks used linux/amd64 emulation on macOS.

For reproducible local validation, could you publish a pinned public sandbox image/digest, or an exact package manifest plus required offline wheels for the corrected training setup? If neither is planned, is there a supported dependency-repair procedure for participants? We can provide hashes, package manifests and full test output. We understand this concerns local training-task calibration, not evidence that hidden test tasks are broken.


**** (2026-10-11 21:04, 0 votes)
Independent confirmation, in case it helps with the training-task fix. With the public kit (swegemma 0.2.11, Docker sandbox, gold patch 3 runs per task, no flaky results) we also got 43 tasks resolving with the gold patch. typing_inspection was the cause on 61 of the 67 fastapi tasks, as you and Oleksii Zhukov described (thread 744370). Two of the 129 we could not evaluate because of a bad download on our side.

One thing we have not seen mentioned yet: on 4 tasks an EMPTY patch also resolves (requests_7309, requests_7315, requests_7427, rich_3468). So for local CV, a "resolved" result on those tasks does not tell a fix apart from no change.

Thanks @ryanholbrook for confirming the test set validates at 100%.


> **** (2026-10-11 23:20, 0 votes)
> Clarification to my comment above, after a closer look. The three requests tasks (7309, 7315, 7427) pass with an empty patch only because of the second effect Nur describes: the bundled requests wheel shadows the patched repo, so the tests run against the released package. When we removed that wheel, all three needed the fix and no longer passed empty. So that part is a harness effect, not a task problem. rich_3468 still passes with an empty patch in our setup.


**** (2026-10-08 17:42, 0 votes)
We need the exact wheel where all of the tests pass with a gold patch, or else we will moving kinda blind. 
Thank you regardless @ryanholbrook I love this competition!


---

## Two consecutive "unhandled error" submissions with a prompt-only bundle that is byte-identical to a public 0.17–0.24 recipe — could a host share the traceback?
/competitions/gemma-4-developer-agent/discussion/751872 | by  | posted 2026-10-23 00:05 | last comment 2026-10-23 00:05 | 0 comments | 0 votes


**** (2026-10-23 00:05, 0 votes)
Submissions 57485880 (2026-10-21 14:24 UTC, completed with error after ~30 min) and 57500887 (2026-10-22 00:00 UTC, error after ~1 h 55 min) both ended with
"Your notebook hit an unhandled error while rerunning your code". No score, no traceback visible to me (only via the API's error_description).

Both are prompt-only, no adapter, no skills. The second one is the public "Budget-Fit Single Agent" bundle unchanged:
eval_config 8 min / 28 tool calls / 240 s / 80 turns; sampling temperature 0.2, top_p 0.95, max_output_tokens 8192, thinking_budget 4096, include_thoughts true; 31B QAT model.
The exact same zip runs clean on 29 public tasks in my own Kaggle GPU kernel (vLLM from the wheelhouse, adk_submission 0.2.13), ~2 h, no traceback.
My earlier submission 57408159 (same notebook structure, 5 min / 40 calls / 4096 / include_thoughts false) scored normally on 2026-10-19.

Questions for the hosts:
1. What was the exception for 57485880 / 57500887? Anything in the bundle, or a scorer-side failure that should be re-scored?
2. Is there any known failure mode for max_output_tokens 8192 + include_thoughts true at the 32k context on the 4×L4 scorer?

Kaggle user: angusundaresh. Happy to share the zip privately with a


---

## 31B vs 12B vs E4B with the same agent files: a local comparison
/competitions/gemma-4-developer-agent/discussion/750974 | by  | posted 2026-10-20 11:01 | last comment 2026-10-22 09:02 | 2 comments | 17 votes


**** (2026-10-20 11:01, 17 votes)
Since the 12B, E4B and E2B models were added, I wanted to know whether a smaller, faster model could do better within the time budget. I ran the same agent files (the public [Budget-Fit configuration](https://www.kaggle.com/code/verracodeguacas/gemma-4-agent-budget-fit-single-agent) by verracodeguacas) on the permitted models and changed only the model and the time limit per task.

**Setup:** 31 tasks from four public repositories I had not used before, the official serving stack, one A100.

| Model and setup | Tasks solved (of 31) | Average time per task | Runs that submitted a patch |
|---|---|---|---|
| 31B, 8-minute limit per task (as published) | 9 and 11 (two runs) | 5.4 min | 81–84% |
| 12B, 8-minute limit | 4 | 6.2 min | 42% |
| 12B, 5-minute limit | 4 and 4 (two runs) | 4.5 min | 26% |
| 12B, 5-minute limit, more tool calls and thinking | 4 | 4.8 min | 16% |
| 12B coder + 12B reviewer, 5-minute limit | 3 | 5.0 min | 3% |
| E4B, 5-minute limit | 0 | 1.8 min | 97% |

**What I take from it**

- The 12B solved less than half as many tasks as the 31B in every setting I tried.
- The 12B was not faster in practice. It writes about twice as fast, but it writes about three times as much per task, so a task takes longer, not shorter. At the 5-minute limit most of its runs simply ran out of time. When I submitted the 12B with the 8-minute limit, the leaderboard run did not finish within 12 hours and got no score.
- A second 12B as a reviewer did not help. E4B finished quickly but solved none of these tasks.

**Limits:** 31 tasks from four repositories, one or two runs per setting, timing on an A100 rather than the scorer's four L4 GPUs. Differences of one or two tasks would be noise here; the gap between 31B and 12B was the same in both runs.

Per-task results are in [Gemma 4 Task Soundness and Local Results](https://www.kaggle.com/datasets/dmitriigluzdov/gemma-4-task-soundness-and-local-results); speed measurements are in [Gemma 4 Serving and LoRA Verification Kit](https://www.kaggle.com/datasets/dmitriigluzdov/gemma-4-serving-and-lora-verification-kit). Happy to hear if anyone has seen the 12B do better with a different prompt or budget.


**** (2026-10-21 21:38, 3 votes)
Thanks for running this! Just to share more data, I did a similar experiment on Kaggle's 4x L4 GPU and it pretty much points the same way, but I think it could be complimentary to your A100 timing and useful for others:

I run a small benchmark of 24 tasks, 8 come from competition tasks and 16 from other repositories. Slice of a bigger benchmark I am creating locally. The way it was set up is I run same 24 tasks, two runs each on 12B model and four runs each for 31B model. One caveat worth pointing out, the configurations for agents were pretty much the same, except i made a mistake and 31B version had 7 minutes and 28 max tool calls cutoff while 12B version had 7 minutes and 22 max tool calls cutoff.

| Model  | Solves (of 48 runs)  | Tasks solved at least once |
| --- | --- | --- |
| 31B (range over the six pairs of runs) | 15-21 (31-44%) | 9-13 |
| 12B | 8 (17%) | 6 |

Also 12B never solved a task that 31B version didn't. Even the 31B's worst pair of runs beat the 12B's two. 

Which is expected but a little bit disappointing, moreover the main point was to measure efficiency gains.
Some speed numbers on 4x L4:
| _  | 31B | 12B |
| --- | --- |
| Decode speed (vLLM) | 33-35 tokens/s | 62-64 tokens/s |
| Model-call latency (fitted) | 1.4 s + 28.7 ms per output token | 1.6 s + 16.3 ms per  output token |
| Output tokens per model call (median) |	127	| 233 |
| Output tokens per task (mean) |	about 8,100	| about 12,400 |
| Seconds per model call (median) |	10.3 | 11.5 |
| Seconds per tool call (median)	| 12.2 |	13.1 |
| Seconds per task (mean) |	296	| 275 |
| Runs that used every tool call	| 35% (of 28) |	60% (of 22) |
| Runs that hit the 7-minute limit |	25%	| 38% |
| Runs ending with a non-empty patch |	78% |	46% |


Therefore, we can see 12B decodes about 1.9 times faster, but it writes about 1.8 times as much per call, so each call ends up slightly slower. It then spends its tool calls and time without converging.

One idea I had, that I will probably not have enough resources to implement, so I will share it here, is to train 12B with 31B version as a teacher. This way we could eliminate many unnecessary tokens that 12B version produces and truly benefit from it's speed gains. Even a perfectly distilled 12B wouldn't beat the 31B, but if we can achieve consistent x1.9 faster decode speed that opens a door for cool trade-off solutions, like best-of-two runs, more time per tasks, more tool calls, etc. All within 12 hours.


> **** (2026-10-22 09:02, 1 votes)
> Thanks for the L4 numbers!
> 
> I’m a bit sceptical about distillation. In ARC-AGI-2 I trained a LoRA on a 27B Qwen model with shorter reasoning written by stronger models, to make it faster. It got worse: 6 correct answers out of 48 samples against 14 for the base model. The model seems to need its own long reasoning. And if a faster model frees time for two attempts per task, the open question is how to choose between them. Identical files score anywhere from about 0.12 to 0.22 on the public LB, so the same agent often solves a task on one run and misses it on another. A second attempt would catch some of those, but only if the agent can tell which of its patches is right. The tests that decide the score are not visible to it.
> 
> Cost is the other problem. By my estimate, LoRA on 31B needs two A100s and about 9 A100-hours per epoch on about 200 trajectories, and more than one epoch is usually needed. 12B should be about 2.5 times cheaper and fits on one A100, but one experiment (two epochs on about 200 trajectories plus two evaluation runs on about 200 tasks) would still take around 12 A100-hours.
> 
> Small models look like a cheaper place to start. There is now a $10k bonus for E2B/E4B ([announcement](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/751104)), and the best small-model score was 0.06 on Oct 20 ([small model leaderboard](https://www.kaggle.com/code/ryanholbrook/gemma-4-developer-agent-small-model-leaderboard)). I already placed teacher trajectories in the [kit dataset](https://www.kaggle.com/datasets/dmitriigluzdov/gemma-4-serving-and-lora-verification-kit): my 103 resolved 31B runs with their reasoning and token IDs, plus about 1,600 external ones. I plan to start with E4B; its training should fit on one 24 GB L4.
> 
> For E4B the goal is different. It is already fast and submits a patch on almost every task, but it edits the wrong file in 13 of 31 tasks and sometimes overwrites whole files, so the point would be better edits.


---

## SFT / distillation LoRAs on Gemma 4 31B: loss falls a lot, solve rate doesn’t move. What would you try next?
/competitions/gemma-4-developer-agent/discussion/751596 | by  | posted 2026-10-22 05:40 | last comment 2026-10-22 05:51 | 2 comments | 4 votes


**** (2026-10-22 05:40, 4 votes)
Hi all. We've trained several LoRAs for this harness and none beats our prompt-only baseline on paired local evals. We'd value advice from anyone who has worked on agent fine-tuning, trajectory distillation or preference optimization for SWE tasks.

## Setup and constraints

- `gemma-4-31b-it-qat-w4a16-ct`. Our agent v11 is a contract-first-style prompt plus a line-number edit skill; it's prompt and tools only, no training.
- Per task: 28 tool calls and 8 minutes. Total: 12 hours for all hidden tasks.
- Training: LoRA r16, alpha 32, lr 1e-4, 1 epoch, Keras on TPU v5e-8, exported to PEFT.
- Serving cost: in our measurements, enabling any LoRA adds about 15-20% time per call (decode about 1.3x slower). An adapter therefore has to beat the baseline by enough to pay for a shorter per-task budget.
- Eval: the official evaluator, paired on the same tasks. 73 gradable public tasks plus a 25-task held-out exam (98 total). A3 got 4 runs per task.
- Noise: identical files have scored anywhere from 7 to 13 of 58 on the public leaderboard (public evidence notebook), so we judge by paired local tests, not leaderboard runs.

## Results (98 held-out tasks; v11 solves 38)

**A1:** 314 Qwen3-Coder-480B runs (nebius SWE-rebench OpenHands), converted to our tools, with each step's reasoning rewritten by Gemma itself (845 trained steps).
- Solved 31. Vs v11: won 2, lost 9.

**A2:** A1 + 2,000 DeepSeek-V4-Flash runs (nvidia/Open-SWE-Traces), converted 1:1 with the teacher's own reasoning (19K trained steps, 5.3M tokens).
- Train loss 1.0 -> 0.42. Solved 37. Vs v11: won 5, lost 6.

**A3:** DeepSeek only: 1,976 runs that fit 16K tokens *whole*, so every example ends with its edit and submit (1,538 tasks, 587 repos).
- Train loss 1.4 -> 0.40 (base model 2.13 on the same rows). Solved 31 . Vs v11: won 3, lost 4.
- Evaluated with a 7-minute cap (what it would ship with) vs v11's 8, so part of its gap may be the cap.

Earlier LoRAs on Gemma's own solved runs (rejection sampling, one run per task) also tied or lost. Leaderboard: prompt-only agents 0.15-0.17; A2 0.12.

## What the failures actually are

We matched v11's 41 failed runs on the 73 public tasks against gold edit locations (LocBench-129 labels by muhammedidris28, thanks!):

- Edited within 20 lines of the gold change, but the fix was wrong: **18**
- Opened the gold file, never edited (ran out of calls or time): **11**
- Edited only other files: **7**
- Edited the gold file, far from the change: **3**
- Never found the gold file: **2**

Median call at which the gold file first appears: **2**.

So localization is mostly solved. The failures are **wrong fixes in the right place** and **never committing to an edit**. Imitating a stronger model's successful runs on other repos lowers loss, but hasn't changed either one.

## Questions

1. **Has anyone gotten a held-out gain from SFT/LoRA on this harness?** If so, what data: teacher runs, self-generated, synthetic? And how many examples?
2. **On-policy RFT/DPO.** Our next plan is to sample v11 4-8 times per task on ~300 training tasks, keep the tasks it solves only sometimes, then train on its own wins (RFT) and on win/loss pairs from the same task (DPO). Is a few hundred pairs enough to matter for a 31B model?
3. **Pairs for a stateful agent.** Would you compare whole trajectories, or branch several continuations from a shared prefix (same repo state) and prefer the one that ends in a passing patch? The second keeps pairs comparable, but costs more rollouts.
4. **Teacher data format.** Did you train on the teacher's own reasoning or rewrite it in the student's voice? Did whole runs vs truncated runs matter for you?
5. **Hyperparameters vs data.** Rank, epochs, learning rate, LoRA scale (alpha/r = 2 for us): has changing these ever turned a null result into a gain for you, or is data the bottleneck?

Any pointers to papers or working recipes for preference optimization on tool-using coding agents are very welcome. Thanks!


**** (2026-10-22 05:44, 2 votes)
Have you tried measuring how much time your model spend on locating vs actually editing?


> **** (2026-10-22 05:51, 0 votes)
> Thanks! In our v11 runs (73 public tasks), the right file usually shows up by call 2, but the first edit doesn’t come until around call 12–13, so about 10 of our 28 calls go to reading before editing. In 11 of our 41 failures it found the right file and never edited at all, and about a third of runs hit the 8-minute cap. I haven’t timed it in seconds yet but will. Did you find most of the gain comes from editing earlier and spending the rest of the budget on edit/test loops?


---

## Request: let skill scripts reach the code-graph data
/competitions/gemma-4-developer-agent/discussion/751560 | by  | posted 2026-10-22 01:16 | last comment 2026-10-22 01:16 | 0 comments | 0 votes


**** (2026-10-22 01:16, 0 votes)
Hi @ryanholbrook and team,

Custom tools go in skill scripts (#743573), but those run in the air-gapped sandbox, while `search_similar_code`, `get_code_neighbors` and `get_code_subgraph` run on the host against `graphs/` and `embeddings/`, which the sandbox doesn't get (HARNESS_README §4, §6.3). The model can call the graph tools; nothing it writes can.

Letting code compose tools is now a standard feature of production agent harnesses, and it would answer a good share of the tool-feature requests on this forum: edge direction, filters, output size, name resolution (#744577, #745731) all become things a participant writes for themselves.

Could either of these be supported?

1. Mount the task's graph `.json` and embedding `.npz` read-only in the sandbox, at a documented path or env var. Data only, no host code reachable.
2. Let skill scripts call the declared graph tools, budget-gated like the model's calls.

The graph can be rebuilt from the workspace; the embeddings can't (#748801).

Thanks!


---

## Missing FastAPI test dependencies in the evaluation sandbox
/competitions/gemma-4-developer-agent/discussion/745775 | by  | posted 2026-10-04 10:32 | last comment 2026-10-21 21:27 | 8 comments | 8 votes


**** (2026-10-21 19:46, 1 votes)
If it helps anyone calibrating locally: I put the missing test packages (`inline_snapshot`, `dirty_equals`, `annotated-doc` and the rest) in an offline dataset. I also made a notebook that installs them in a scorer-like sandbox.

Result with the gold patch: fastapi goes from **10/67 to 66/67** passing.

Dataset: https://www.kaggle.com/datasets/zbigniewkirchner/gemma-4-agent-local-eval-wheels

Notebook: https://www.kaggle.com/code/zbigniewkirchner/gemma-4-agent-do-gold-patches-pass-locally


**** (2026-10-04 10:32, 8 votes)
## Summary

During local evaluation of the supplied tasks, some FastAPI tests failed during collection because `inline-snapshot` and `dirty-equals` were unavailable in the test container.

These packages are imported by existing tests in the supplied repository snapshots. We want to confirm the official environment requirements before installing a local workaround.

This report describes a local reproduction. It does not establish that the official Kaggle evaluation environment has the same issue.

## Reproduction environment

- Model: `gemma-4-31b-it-qat-w4a16-ct`.
- Evaluation: local evaluation harness with Docker sandbox.
- Sandbox image: `swebench-sandbox:latest`, built from the project's `docker/Dockerfile.sandbox`.
- Container Python: 3.13.
- Tasks and repository snapshots: supplied competition data.

The Dockerfile does not explicitly install either package. Other repository dependencies are installed through the evaluation setup; the question is whether that setup should also provision these test dependencies.

## Example 1: fastapi_14978

Test collection includes `tests/test_tutorial/test_body/test_tutorial001.py` and fails with:

```text
from inline_snapshot import snapshot
ModuleNotFoundError: No module named 'inline_snapshot'
```

The supplied `snapshots/fastapi_14978.tgz` contains a `pyproject.toml` that declares:

```toml
"dirty-equals >=0.9.0",
"inline-snapshot >=0.21.1",
```

The test's import is present in the repository snapshot; it was not introduced by the agent patch.

This task also reports separate implementation errors, such as an unsupported `strict_content_type` argument. Those errors should not be attributed to missing dependencies. Installing the packages alone would not establish that the task is solved.

## Example 2: fastapi_14356

Test collection fails in `tests/test_tutorial/test_header_param_models/test_tutorial003.py`:

```text
from dirty_equals import IsDict
ModuleNotFoundError: No module named 'dirty_equals'
```

This import is also present in the supplied repository snapshot.

## Observed impact

The evaluator cannot complete the selected tests when collection fails on these imports. Missing packages can therefore obscure whether an implementation patch is correct.

A test exit code of 2 is not sufficient to identify a dependency problem: other tasks also fail collection because of incomplete implementations. The examples above are identified by their explicit ModuleNotFoundError messages.

## Questions for the organizers

1. Does the official Kaggle evaluation environment already include these dependencies?
2. Should the harness automatically install each repository's test dependencies? If so, which setup step should we check locally?
3. Is there a supported dependency manifest or wheel bundle for reproducing the official environment?
4. If these packages are also missing in official evaluation, could the environment or setup instructions be updated?

## Workaround status

We have not installed these packages as a workaround for these evaluation runs. We want local evaluation to match the official environment before changing the sandbox.

## Local evidence

These paths are local evidence references, not public download links. Relevant excerpts can be attached to the Kaggle report.

- `results/summary.json`: per-task test output for this experiment.
- `results/logs/tests/`: saved test output files.
- Project `snapshots/fastapi_14978.tgz`: dependency declarations and existing test import.
- Project `snapshots/fastapi_14356.tgz`: existing test import.
- Project `docker/Dockerfile.sandbox`: base sandbox installation.

No credentials or API authentication data are included in this report.


**** (2026-10-09 14:16, 1 votes)
I ran into the same issue on Kaggle notebook with `sandbox='subprocess'`.

In my run using `swegemma==0.2.7`, several final verifications stopped during pytest collection because `dirty_equals` or `inline_snapshot` was missing. I also reproduced the missing `inline_snapshot` error on `fastapi_14953` with `swegemma==0.2.10`.

Looking at the `0.2.10` source, I noticed that `install_test_dependencies()` returns immediately for `SubprocessManager`, so this backend skips that dependency preparation step.


> **** (2026-10-09 15:35, 1 votes)
> Still not fixed in `0.2.11` btw.


**** (2026-10-04 14:04, 2 votes)
Update: 35 tasks were affected by missing test dependencies


> **** (2026-10-07 03:40, 1 votes)
> Has this been fixed or not ?


**** (2026-10-21 21:27, 0 votes)
I am also getting this error local environment. How to fix?
ModuleNotFoundError: No module named 'inline_snapshot'


**** (2026-10-05 17:59, 0 votes)
Confirming this from a local host trial. Initial exploration, not exhaustive.

Run:
four fastapi tasks died in Phase 2 collection with `ModuleNotFoundError: No module named 'inline_snapshot'` (fastapi_14246, fastapi_14262, fastapi_14266, fastapi_14978).

The public `wheels/` set (124 wheels) is missing several test-only deps. I resolved the full test-dependency closure for fastapi/requests/rich into a supplemental wheel directory and verified in a sandbox-like py3.13 venv (install --no-deps, then `pytest --collect-only`):

  fastapi : 2648 tests collected, 0 errors
  requests:  633 tests collected, 0 errors; a real `httpbin` fixture test passes
  rich    :  788 tests collected, 1 error (`pkg_resources`, setuptools 82+ removed it;
            that file is outside the required test nodes)

Missing distributions that had to be added: inline-snapshot, asttokens, executing, typing-extensions, dirty-equals, sqlmodel (+SQLAlchemy, greenlet), flask (+werkzeug, blinker), anyio/trio (+outcome, sortedcontainers), PyJWT, pyyaml, pwdlib (+argon2-cffi, cffi), python-multipart, itsdangerous, ujson, orjson, email-validator (+dnspython), uvicorn[standard] (+uvloop, httptools, watchfiles, websockets, python-dotenv),
fastapi-cli, pydantic-settings, pydantic-extra-types, pytest-httpbin (+httpbin), trustme, PySocks, attrs.

Caveat: initial exploration on a subset of tasks, not an exhaustive audit of all 129.


> **** (2026-10-06 05:54, 1 votes)
> We saw similar collection failures locally, and adding supplemental dependencies helped.
> 
> One additional issue we confirmed is **dependency-version compatibility**, even when collection succeeds. For `rich_3296`, the same model patch and reference patch both passed all 24 syntax tests with Pygments 2.17.2, but failed with 2.13.0 and 2.21.0 because the expected ANSI colors and token highlighting differed.
> 
> It would be helpful if the organizers could publish a validated dependency set, including compatible versions, and clarify how supplemental dependencies should be handled during final evaluation. Your subset caveat is important—we also wouldn't treat these checks as a complete audit of all 129 tasks.


---

## FastApi tasks fail even with the gold patch, typing_inspection seems to be missing
/competitions/gemma-4-developer-agent/discussion/744370 | by  | posted 2026-09-29 15:39 | last comment 2026-10-21 19:49 | 5 comments | 5 votes


**** (2026-10-21 19:49, 2 votes)
I ran into all three issues you list, and they can be fixed locally:
- **fastapi:** missing test wheels + starlette versions that don't match old commits -> 10/67 to **66/67**
- **requests:** the httpbin fixture works with `pytest-httpbin` in a clean sandbox -> 3/13 to **13/13**
- **rich:** color output needs the Pygments of the task's time (pinned per task) -> 39/48 to **47/48**

Overall, gold patches pass on **127/129** in a notebook.

The notebook and a per-task CSV are in my public notebooks: **Gemma 4 Agent: Do Gold Patches Pass Locally?**


**** (2026-09-29 15:39, 5 votes)
Hi all,

I was going through the tasks to see which ones can actually pass in the local harness. For each task I skipped the agent and used the local harness to apply the reference patch that's included in tasks.jsonl in the competition data, then ran the tests.

All **19 fastapi** tasks I have locally failed this way. The tests don't even start. They crash while loading, because **pydantic 2.13.4** is installed but *typing_inspection* (which pydantic 2 needs) isn't in the wheels folder. So **importing pydantic fails, fastapi fails with it, and pytest stops at collection**. As far as I can tell my wheels match the competition data, so I think it's the same on the Kaggle side.

If that's right, nobody can solve the fastapi tasks at the moment, even with a perfect fix. That's around half of the 129 tasks.

I also saw a few other tasks fail with the gold patch. Some of the requests tasks complain about a recursive httpbin fixture. Some rich tasks produce output that doesn't match the expected text in the tests, which looks like a pygments version difference.

A couple of questions for the team:

1. Could you confirm whether the scoring environment has the same problem?  
2. If it does, is there a plan to fix it, or should we treat these tasks as unsolvable?
Also, if an agent notices the missing package and works around it by adding it into its own patch, would that be allowed, or would it count as breaking the rules? I'd rather ask now than find out at the end.

Thanks!


**** (2026-09-29 17:57, 2 votes)
I see the same, and it matches what I found when I ran every gold patch through the official harness (`Evaluator.evaluate_task` with the agent replaced by the patch) on 2026-09-25. Might have been updated.

- In **Docker**: fastapi: 63 tasks fail at import, exactly as you describe: pydantic 2.13.4 arrives without `typing_inspection`. As far as I can tell, the harness unpacks the newest version of each small wheel straight into site-packages without resolving dependencies, which is how pydantic loses one. `dirty_equals` and `inline_snapshot`, which many fastapi tests import, are missing too.

- In **Kaggle's notebook image** with the subprocess sandbox behaves differently. It ships pydantic 2.12.3 with typing-inspection 0.4.2, so fastapi imports work there, and 71 tasks pass with their gold patch (42 rich, 29 fastapi). The remaining fastapi failures there are the missing `inline_snapshot` and `dirty_equals` helpers. requests and httpx can't be tested there because of their src layout.


The leaderboard tasks come from private repositories, so this mainly distorts local CV. But if the scorer stages dependencies the same way, some hidden tasks could fail for the same reason whatever the agent does. It would be great if the hosts could confirm how dependencies are installed for the hidden tasks.


> **** (2026-09-29 18:25, 2 votes)
> I can confirm that the hidden tasks validate at 100% with a "gold patch" submission.


> > **** (2026-09-29 20:56, 3 votes)
> > Could you please fix the training data, inline snapshots are missing in a lot of the fastapi tasks.


> > **** (2026-10-06 22:17, 0 votes)
> > Could you please also verify that the "gold patch" are deducible locally? 
> > 
> > It seems like in the training data, some tests anticipate the model to write function/module under name that is never mentioned, or other edits that are completely not even hinted in the repo or the problem statement.
> > 
> > Also there are cases where the model is given an issue link, but the sandbox is offline.


---

## Calibrating in a notebook? About a third of the fastapi tasks cannot pass there (missing test dependencies)
/competitions/gemma-4-developer-agent/discussion/750345 | by  | posted 2026-10-17 21:01 | last comment 2026-10-21 19:43 | 1 comments | -1 votes


**** (2026-10-21 19:43, 1 votes)
Same here, and it goes further than these two packages. In a plain notebook the gold patch passes on only 10 of 67 fastapi tasks: besides the missing wheels, old commits meet a too-new starlette, and the sandbox sees the notebook's own packages.

I packaged a fix: the missing wheels plus a scorer-like sandbox. Gold patches then pass on **66 of 67 fastapi tasks (127/129 overall)**.

https://www.kaggle.com/code/zbigniewkirchner/gemma-4-agent-do-gold-patches-pass-locally


**** (2026-10-17 21:01, -1 votes)
If you evaluate agents in a Kaggle notebook with the subprocess sandbox and the official data, note that the hidden tests of 21 of the 67 public fastapi tasks import dirty_equals or inline_snapshot, and neither package has a wheel in data/wheels. Those test files fail at collection (pytest exit code 2) regardless of the patch. We saw it as a run of v15e on the 60-task set we use: 17 of 35 fastapi tasks exited with code 2, and 7 of those 16 patches pass in a sandbox that has the two packages installed. The organizers’ task_soundness.csv shows the gold patches passing in the scoring environment, so this is a notebook-calibration floor, not a scorer issue, but it means notebook numbers understate fastapi by roughly a third of its tasks. Workaround for local evaluation: preinstall dirty-equals and inline-snapshot in the sandbox base; it would be good if the wheels dataset included them.

— Domenic Federico


---

## Fine-tuning Gemma 4 31B on 1,500 agent trajectories: LoRA scaling, budgets, and why my adapter lost to the base model
/competitions/gemma-4-developer-agent/discussion/750713 | by  | posted 2026-10-19 16:32 | last comment 2026-10-21 17:44 | 10 comments | 6 votes


**** (2026-10-19 16:32, 6 votes)
**Notebook with all runs, configs and adapter:** [https://www.kaggle.com/code/icfoer/gemma4-developer-agent-lora-200-test]

---

I fine-tuned a LoRA on 1,500 trajectories from the reference agent. On Kaggle it scored 0.0: the model spent four minutes before its first tool call, then repeated the same `git log` command until the budget ran out, and submitted nothing. The cause was the LoRA scaling factor, not the data. The full path, including the part where I benchmarked the wrong model for four hours, is below.

## Why this exists

The competition gives you a 31B Gemma 4 checkpoint, a set of repositories with hidden tests, and a harness that runs an agent against them. LoRA adapters are allowed, which makes the obvious move tempting: take a stronger agent, record what it does, and teach the smaller one to imitate it.

So I did that. This post is the result, including the part where the fine-tune turned out to be worse than the model it was supposed to improve.

If you are planning a LoRA for this competition, the short version is: check your adapter scaling before you check anything else.

## Data

I started from the public tasks that ship with the competition, plus a set of extra tasks from the same repositories that I extracted separately and attached to the local harness. Each task comes with a repository snapshot pinned at the base commit, so a run is reproducible.

For every task I ran the reference agent from the sample submission at five sampling temperatures between 0.2 and 1.0. That produced roughly 1,500 transcripts. Most of them are not usable, and the filtering mattered more than the generation:

- I kept only runs the harness scored as resolved.
- For each task I kept a single trajectory, the shortest by tool-call count. This keeps the context under 32k and, more importantly, avoids teaching the model to wander.
- I dropped repositories where the harness itself misbehaved (networkx snapshots, urllib3, cmd2). Training on a broken verifier teaches noise.

The result was 697 training examples from 99 tasks, plus 60 held-out examples from 11 tasks that do not appear in the training set. Same repositories, different tasks, so the held-out number is optimistic about unseen repositories but honest about unseen issues.

Every example is a message list plus the nine tool schemas. The system prompt is the exact 3,728-character prompt used at inference, not a rewritten one. And there are no thinking traces anywhere in the data: the reference agent's transcripts contain tool calls and short commentary, nothing else. That detail comes back later and bites.

## Training

One practical problem first: PEFT cannot attach to the packaged `gemma-4-31b-it-qat-w4a16-ct` checkpoint. I trained on a dequantized bf16 copy of it instead, which is the closest thing to the scored model that accepts an adapter.

The model I fine-tuned is the full bf16 checkpoint, not a quantized one. The 4-bit setting below only describes how the frozen base was loaded into memory during training. Nothing inside the adapter is quantized.

The recipe:

- the frozen base loaded in 4-bit nf4 with nested quantization (QLoRA)
- the adapter itself is plain bf16: 245 MB, 820 tensors
- rank 16, alpha 32, dropout 0.05
- all seven projections: q, k, v, o, gate, up, down, across all 60 layers
- 410 adapted modules, 122.4M trainable parameters
- FFPA attention kernel, enabled through a small `sitecustomize` shim and `attn_implementation: "ffpa"`
- 3 epochs, learning rate 1e-4 with cosine decay and 20 warmup steps
- batch size 1, gradient accumulation 4, bf16, Liger kernel, packing disabled
- `max_length: 32768`, because a truncated trajectory teaches the model to stop mid-sentence

The hardware was two ASUS GX10 boxes with one GPU each, training across both machines. The planned run was 264 optimizer steps; I stopped at 220 to free the GPUs, so the final learning-rate anneal never finished.

One detail worth spelling out, because it trips people up. TRL's `assistant_only_loss` needs `{% generation %}` markers around the assistant tokens in the chat template, and the stock Gemma 4 template has none. I made a copy of the template and inserted the markers. The token stream itself does not change; only the label mask does. I verified this later by rendering the same conversation with the stock template and with the patched one: 12,602 tokens in both cases, zero divergence. So the template is not a hidden variable here.

The loss curve on the held-out split: 0.6126, 0.5483, 0.5201, 0.5088. Monotone improvement, no sign of overfitting. This is the last number in this post that looks good.

## The adapter in the wild

I deployed with vLLM. On Kaggle that is 4×L4 with vLLM 0.19.1 and the official `-ct` weights. Locally it is two GX10 machines with tensor parallelism 2, MTP speculative decoding and a 32k context, serving the same QAT checkpoint. In both cases the adapter sits on top as a separate bf16 LoRA.

The first submission scored zero. The log told a strange story. The model spent 257 seconds before its first tool call, then started issuing the same command over and over, swapping one keyword at a time:

```
git log --all --oneline | grep -i "release_prep"
git log --all --oneline | grep -i "release_ready"
git log --all --oneline | grep -i "release_now"
```

It burned the entire 24-call budget that way, then emitted a long stream of empty tool calls that the harness rejected with `error (exit 0)`, and submitted nothing. It never made a single edit.

I assumed the harness was at fault. There are two well-known problems in this setup that look plausible: a tool-argument parser that can loop on malformed array arguments, and a context-overflow path that skips the fallback `git diff` capture. Neither applied. The commands were well-formed and the context never overflowed.

## Isolating the cause

The same task, same budgets, same snapshots, run without the adapter: normal behaviour, patch in 15 calls, tests pass. With the adapter: the loop.

Then I went down the list. Chat template: identical rendering, ruled out. Tool schemas: identical to training, ruled out. NaN or infinity in the weights: none. Adapter shape: 410 modules across all 60 layers, exactly as trained. Parser: the array-argument case never fired.

What actually fixed it was the LoRA scaling factor.

## Alpha is a real knob, and it is not obvious

LoRA adds one term to each adapted layer:

```
h = W·x + (alpha / r) · B(A(x))
```

With rank 16 and alpha 32, the scale is 2.0. The adapter's correction is applied at double strength. That is legal, and it is what the training objective was optimized for, but it is also enough to push the model out of distribution.

**Alpha 32, scale 2.0.** Degenerate. Repetition loops, four minutes before the first tool call, empty patches, score zero. Not a subtle degradation either: the model stops behaving like an agent and starts behaving like an n-gram model with a budget.

**Alpha 16, scale 1.0.** The loops disappear entirely. This is the configuration I would call "the model the training intended": the full learnable correction at its nominal strength. The side effect is that it gets slower and more deliberate. Thinking blocks grow from a couple of hundred characters to 2,500–14,700 characters per step, and median time per task went from 163 seconds at alpha 8 to 290 seconds at alpha 16. It solved one task the base model could not, textual-3659, with a clean 1,727-character patch and 61 passing tests. But it also started timing out on tasks it used to finish, because thinking eats the wall clock.

**Alpha 8, scale 0.5.** The safest setting. No loops, fastest of the three (median 163 seconds), and it produces a patch on every single task, even the ones it fails. But it only applies a quarter of the learned correction, so it is really an interpolation halfway between the base model and the fine-tune. It solves a few tasks the base misses and loses a few the base solves.

The important thing is that alpha is not baked into the weights. It is applied at inference, it is one line in `adapter_config.json`, and it requires only a server restart. If your fine-tune behaves like a broken model, sweep alpha from 8 to 32 before you conclude anything about your data. I lost a week because I did not.

## Numbers

These are all on tasks from the training set, so treat them as a sanity check, not as a leaderboard estimate.

| Configuration | Solved | Notes |
|---|---|---|
| Base model, no adapter | 8 / 11 | Reference point |
| LoRA, alpha 32 | 0 / 1 | Repetition loop, no patch |
| LoRA, alpha 8 | 6 / 11 | Always patches, sometimes faster, loses some base wins |
| LoRA, alpha 16, 24 calls / 6 min | 5 / 8 | Loops gone, noticeably more thinking |
| LoRA, alpha 16, 32 calls / 8 min | 7 / 11 | One win the base misses, three losses that are budget artifacts |

Average time per task across all local runs was around 200 seconds, roughly 3.4 minutes at the looser budget. Extrapolated to 129 tasks, that is 7 to 9 hours depending on the machine, which fits the 12-hour GPU limit but without much margin.

## Two findings that generalize

**The budget is part of the prompt.** The system prompt contains a block that states the allowance explicitly:

```
## Task Budget (Session terminates when any budget is exhausted)
- Tool calls allowance: 24 calls
- Time allowance: 6.0 minutes
```

And further down it says, more importantly:

```
Plan by phases, not fixed numbers: locate & read ≈ first third;
first SOURCE edit by ≈ the middle; verify, fix, git diff,
submit_patch in the last third.
```

The plan is proportional to the allowance. That means raising the cap from 24 to 32 does not give the model more room to finish; it gives it more room to explore, in proportion. I watched this happen twice on the same task: at 24 calls it tried to edit on call 24 and was refused, at 32 calls it tried on call 32 and was refused. The bug was found both times. The fix never landed.

If you want the model to edit earlier, the cap is the wrong lever. Either the training data needs shorter exploration phases, or the prompt needs a hard instruction with a fixed number in it, which then diverges from the data the adapter was trained on.

**My training data had no thinking, but inference had it on.** Every training example ends the assistant turn with text and tool calls. There are zero thought tokens in 697 examples. At inference I was running with a thinking budget of 4,096. That is a mismatch I introduced myself, and at alpha 16 it shows up as enormous thought blocks and timeouts. If I retrain, I either generate the trajectories with thinking enabled or turn thinking off at inference. I would not mix.

**And one artifact worth naming:** `error (exit 0)` in the harness log is not a tool failure. It is what the harness prints for tool calls made after the budget is exhausted. Every task where I saw a wall of empty tool calls had already spent its allowance.

## What I would do differently

- Sweep alpha before writing a single line of new training code. It is a ten-minute experiment and it can invalidate an entire week of conclusions.
- Verify the adapter is actually attached. My first local benchmark silently ran the base model for four hours, because `agent.yaml` did not reference the adapter. The submission directory had the weights; the resolver never saw them. Check the traces for the adapter name, not just the server logs: vLLM labels every request with the base model name, so `/metrics` will not tell you.
- Evaluate on held-out tasks from day one. Training-set numbers are reassuring and meaningless.
- Filter trajectories by more than length. The reference agent spends roughly two thirds of its calls exploring, and the adapter learned that habit faithfully. On a 24-call budget, two thirds of the budget is not enough to finish.
- Do not trust the eval loss. 0.5088 is a beautiful number, and it produced a model that repeats itself until the budget runs out.

## Closing

The honest summary: in my setup the LoRA did not beat the base model. It is faster when it works, it always produces something, and it occasionally solves a task the base misses, but the aggregate is a wash. The useful output of this work is not the adapter, it is the diagnosis path: scoring factor first, template second, budget third, and only then the data.

I will be straight with you: I am a bit tired of this project, and I have a day job, so I am not going to keep grinding on it. If someone wants to take it further — retrain with thinking traces in the data, cut the exploration phase out of the trajectories, sweep alpha and rank properly, or throw the whole adapter away and just prompt the base model harder — you are welcome to it. The notebook reproduces every number in this post, including the runs that failed, so you can start from what I have instead of from zero.

If you do find something that beats the base model, I would genuinely like to read about it.
---

**Adapter here:** [https://www.kaggle.com/code/icfoer/gemma4-developer-agent-lora-200-test]


**** (2026-10-20 14:18, 4 votes)
I think LoRA training should focus less on agent trajectories and more on reinforcement learning across different bug-fixing contexts:

Example RL scenarios:

1. Given the problem definition, root cause, and reproduction steps, fix the bug without using any exploration tools (only edit and submit_patch) 
2. Given the problem definition, reproduce the bug without any further exploration.
3. Given the problem definition and sufficient localized evidence, identify the root cause without exploration
4. Given a proposed fix, validate it against the reproduction steps and relevant regression tests.

The goal should be to train specialized capabilities for each context, rather than training on to a single end-to-end agent trajectory. This could make LoRA adapters more effective, composable, and adaptable to different levels of available context and tool access.

What is the basis of above claim? - Because I find Gemma struggling on those areas in my agent pipeline experiments!😀 This is also why skills are not of much use  - but it is not that they don't have these expertise but they dont know how to do it in a precise time constrained way.


> **** (2026-10-21 08:17, 0 votes)
> I agree to this, currently the model is not tuned for these tasks in general, and lora will not help it as long as the dataset is small.


**** (2026-10-21 06:02, 0 votes)
Have you checked the traces, are they clean and simple to reason? What were the hyperparameters? if you have bigger dataset then you need to increase the trainable parameter count with bigger Rank. There was a paper about how many parameters required for given datasets token count.
So if you train on big data with low parameters it won't be able to hold that information, you are trying to compress too much information in too little space.


**** (2026-10-19 21:01, 0 votes)
how did u generate the trajectories ?


> **** (2026-10-21 15:34, 0 votes)
> you can just get them from huggingface, data you use to train the model need to be publicly available anyways from the rules.


> > **** (2026-10-21 15:41, 0 votes)
> > can we use closed source models to generate the data ? like gpt or claude ?


> > **** (2026-10-21 15:57, 0 votes)
> > it needs to be allowed by openai or anthropic by the rules "The use of external data and models is acceptable unless specifically prohibited by the Host."


> > **** (2026-10-21 17:44, 0 votes)
> > can u share the dataset name of the hugging face repo?


**** (2026-10-19 17:48, 0 votes)
just don't train a LoRA rn bro


> **** (2026-10-21 15:42, 0 votes)
> why is that ? @avioon


---

## Has anyone achieved reliable gains from LoRA trajectory SFT on Gemma 4 coding agents?
/competitions/gemma-4-developer-agent/discussion/750961 | by  | posted 2026-10-20 09:47 | last comment 2026-10-21 15:25 | 11 comments | 8 votes


**** (2026-10-20 09:47, 8 votes)
I’ve been experimenting with trajectory-based LoRA SFT for Gemma 4, but haven’t seen improved autonomous issue resolution so far. Looking through related work, I noticed that several prominent success stories use full-parameter fine-tuning for their main agent policies:
- SWE-Gym: the OpenHands policy experiments use full fine-tuning for the 7B, 14B and 32B models.
- SWE-smith: its main trajectory-training recipe uses full fine-tuning.
- SWE-Lego: explicitly uses full-parameter SFT.
- SWE-Protégé: reports that LoRA and QLoRA underperformed full SFT under the same data and evaluation protocol, although it does not provide the adapter configurations or comparison scores.
My own local experiments used Gemma 4 E4B with:
- 170 continuous teacher trajectories covering 62 training issues.
- LoRA rank 16, alpha 32, targeting both attention and MLP projections.
- Peak learning rate of 1e-4, trained through four epochs.
- Complete trajectories, supervising assistant responses while masking user/tool observations.
- Matching QAT-derived weights, tools and inference budgets for the Base/SFT comparison.
Training loss decreased and predictions on recorded training histories improved. However, autonomous execution did not beat Base on my small evaluation panel: Base solved 2/4 training cases and 1/8 development cases, while the best tested SFT checkpoints solved 1/4 and 1/8, respectively.
Observed failures included repeated searches, unsuccessful edits and poor recovery after tool errors. In a separate small overfitting experiment, the model could reproduce the correct teacher actions on two fixed histories, yet still failed when starting autonomously from the original buggy repository.
These are preliminary, small-sample results—not proof that LoRA is the cause. There are also positive LoRA examples, such as TQS. Still, I wonder whether low-rank adaptation can become a bottleneck when learning an entire coding policy, even when the recorded trajectories can be fitted.
Has anyone obtained consistent end-to-end gains over the unchanged Base model using LoRA SFT in this competition? Comparisons across ranks—or matched LoRA versus full fine-tuning—would be particularly useful. Please share training configurations and actual autonomous repair results if available.
I’m also exploring LoRA-based RL separately; the observations above concern SFT.

btw, i'm only interested in training part for this competition


**** (2026-10-20 22:16, 3 votes)
In my experience using lora is making me lower the budget causing bad performance


**** (2026-10-20 13:02, 3 votes)
have been working through it -- not yet closed the gap with the baseline that is to say that lora is degrading performance.


> **** (2026-10-20 22:54, 0 votes)
> same with my case. are the top rankers doing sft or just tuning the prompts ?


> > **** (2026-10-21 03:05, 0 votes)
> > almost closed the gap now. :)


**** (2026-10-20 17:00, 0 votes)
Have you tried larger checkpoints? The E4B would at least need full sft in my opinion to see some gains. I haven't started training yet btw, but I feel like you would be better off tuning larger models.


> **** (2026-10-20 17:09, 1 votes)
> Tried 12b but not gain benifit. So change to 4b for faster iteration. 
> And i have other sft project, for example, for AFLWolrd dataset. In that dataset, i have successfully lora sft qwen 2.5 -1.5b, from 6% success rate for average 16 turn tasks to 68%. So small model can be also tuned for agentic task --- but for this task, it's much more complex. Maybe lora is not enough and need full sft


> **** (2026-10-20 22:53, 0 votes)
> @endotechguyahmawel In your opinion how much people can score if they just tune the prompts, skills and subagents parts ?


> > **** (2026-10-21 03:54, 0 votes)
> > someone has already publish 0.22 baseline without training - and 0.24 i think also without training.


> > **** (2026-10-21 15:25, 0 votes)
> > Yup yup, i guess so too.


---

## Regarding the Compaction threshold
/competitions/gemma-4-developer-agent/discussion/748584 | by  | posted 2026-10-12 16:12 | last comment 2026-10-21 11:57 | 2 comments | 2 votes


**** (2026-10-21 11:57, -1 votes)
Hi @iztanmaymohan, would you be open to a team merger before the 25 Nov deadline? I'm team NP (0.17). I've built a local replica of the scorer that I calibrated against hosted runs (three byte-identical b1 submissions scored 0.15/0.17/0.15). I also have a 63-task fresh-repo set and a paper-track writeup on local grading and noise. Several of your scorer questions (compaction threshold, time budget) are things I've measured. Happy to share results either way.


**** (2026-10-12 16:12, 2 votes)
HARNESS_README section 7.2 says the scorer builds EventsCompactionConfig(compaction_interval=15, overlap_size=2, token_threshold=32768, event_retention_size=5). The Getting Started notebook uses token_threshold=14336. With max_model_len=32768 the first value can never trigger, while the second triggers on most multi-step tasks and adds a summarizer call each time. Which value does the scoring run use today?


**** (2026-10-13 07:42, 0 votes)
this one `token_threshold=14336`.


---

## ServerStartupError: Inference server did not become healthy within 1200s.
/competitions/gemma-4-developer-agent/discussion/751264 | by  | posted 2026-10-21 06:47 | last comment 2026-10-21 10:14 | 3 comments | 2 votes


**** (2026-10-21 06:47, 2 votes)
I committed a notebook with L4x4 GPU configuration and hit this issue. It seems to be transient, yesterday with the same model loading code it started in 6 mins.  It seems to be an infrastructure issue.

If it could happen during commit, I wouldn't rule out this happening during submission too and then we get a vague "Notebook Threw Exception" error. I wonder if this is causing a lot of unexpected submission errors.

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F5256933%2Fa26b2fd853a92cff82178fc326b2d863%2FScreenshot%202026-10-20%20at%2011.45.22PM.png?generation=1792565133900858&alt=media)


**** (2026-10-21 10:14, 0 votes)
Hi [@herbison](https://www.kaggle.com/herbison) [@ryanholbrook](https://www.kaggle.com/ryanholbrook), I encountered a similar issue with my submission **57471486** (2026-10-21 07:24 UTC), which failed with "Notebook Threw Exception" and received no score.

The CLI reports the submission as COMPLETE, but the score is empty and no error message is available.

- The submission failed within approximately 2.6 hours, well below the 12-hour runtime limit.
- The zip passes the official `adk-submission` compiler.
- My previous submission (57390853, 2026-10-19) used essentially the same structure with only minor changes and completed successfully.

I've noticed other participants reporting similar failures recently, including submissions that pass local compilation and testing. This makes me wonder whether there might be a broader issue with the scoring infrastructure rather than individual submission configurations.

Could you please check which stage my submission failed at and share the first exception, if available? Is there any way for participants to access these error logs?

If this turns out to be a scorer-side issue, would it be possible to restore the affected daily submission slots?

Thank you!


**** (2026-10-21 08:05, 0 votes)
Thanks for documenting the transient ServerStartupError and Notebook Threw Exception cases. Has Kaggle identified a recommended diagnostic bundle for distinguishing queue or infrastructure startup failures from model-load failures? Should participants record the model alias, wheelhouse version, server-health timeline, and evaluator logs before retrying? A short checklist would help avoid duplicate submissions and improve reproducibility.


**** (2026-10-21 07:42, 0 votes)
My submission 57452423 passed local validation but failed with "Notebook Threw Exception". This could be another indication of an issue on Kaggle's side


---

## Submission with a skill scored 0.00 with no error
/competitions/gemma-4-developer-agent/discussion/750887 | by  | posted 2026-10-20 02:07 | last comment 2026-10-21 03:14 | 4 comments | 2 votes


**** (2026-10-20 02:07, 2 votes)
the notebook have no problem but Submission with a skill scored 0.00 with no error


**** (2026-10-20 16:11, 0 votes)
same for me just now, but without a skill. Have you been able to figure it out?


> **** (2026-10-21 03:14, 0 votes)
> yea i succeed without skill


**** (2026-10-20 14:41, 0 votes)
Yeah, happened to me too


**** (2026-10-20 02:08, 0 votes)
thanks for everyone i need helppp


---

## Updating the Gemma 4 template to have July 15th fixes
/competitions/gemma-4-developer-agent/discussion/744844 | by  | posted 2026-10-01 06:52 | last comment 2026-10-20 19:40 | 6 comments | 5 votes


**** (2026-10-01 06:52, 5 votes)
The competition model (gemma-4-31b-it-qat-w4a16-ct, version 2, files dated 2026-06-05) ships the
original chat_template.jinja. On 2026-07-15, Google replaced it in the same HF repo (google/gemma-4-31B-it-qat-w4a16-ct, commit 88c0905) with the canonical Gemma 4 template.

Google reports better tool-calling reliability with the refresh.

Submissions can't change the template: the harness starts vLLM without --chat-template and the generation config has no template field. Loops and malformed tool calls are a large share of failures for every agent here, so this would help all teams equally.

Would the organizers consider serving the updated template (or passing --chat-template) for scoring?

Weights are unchanged; it is a single-file swap.


**** (2026-10-20 19:40, 0 votes)
Thanks for investigating. We now have a CPU-only reproduction using the competition model-v2 template and official wheelhouse, including the installed ADK-to-vLLM message-conversion path.

Environment: adk-submission 0.2.12, swegemma 0.2.7, google-adk 1.36.1, vLLM 0.19.1, transformers 5.13.1, litellm 1.82.4. Mounted template SHA256: 94899c0f917d93f6fe81c95744d1e8ddab2d21d39228d2e4aec1fb2a25bff413.

CPU observations:
- For an assistant message containing visible text plus tool_calls, followed by its tool response, the template moves the visible text after the response and closes the model turn without adding a new model header despite add_generation_prompt=True. This reproduces with enable_thinking=True and False. Pure-call and thought-only controls retain an open continuation.
- Across six synthetic histories through the installed ADK _get_completion_inputs and vLLM _postprocess_messages, all six argument dictionaries were preserved. In a separate parser diagnostic, 14/14 well-formed positive comparisons preserved tool names and arguments across non-streaming and token-streaming paths. Intentionally omitted arguments remained omitted.
- Ten attempted public schema overrides (root/generate_content_config placements of chat_template, chat_template_kwargs, extra_body, http_options and extra_args) were rejected. Named model callbacks were schema-accepted, but the installed resolver returned an empty mapping with the stock callback_registry=None; this was a resolver test, not a full callback-enabled agent compilation.

Which exact template correction/revision does the competition support? Is a correction deployed or planned for the official scorer? If participants can supply one, which documented submission field/file does the scorer load? A notebook-only server override would not establish scorer parity. Is there a supported way to capture pre-parser raw generations for diagnosis without changing submitted execution or exposing hidden tasks?

These were synthetic CPU component tests, with no model inference. They establish a rendering issue, not a task-score effect or the cause of historical missing arguments. We have not validated a supported fix or claimed an official-score improvement.


**** (2026-10-11 23:16, 0 votes)
cc @ryanholbrook could you please take a look? Thank you!


> **** (2026-10-12 13:12, 0 votes)
> I will investigate!


**** (2026-10-02 22:48, 0 votes)
The July canonical template still has a turn-boundary bug for OpenAI-format messages where the assistant returns **visible text together with tool calls**.

I reproduced this with commit [`88c090599fb794134cba57e022082043afcc7bf8`](<https://huggingface.co/google/gemma-4-31B-it-qat-w4a16-ct/blob/88c090599fb794134cba57e022082043afcc7bf8/chat_template.jinja>), using `add_generation_prompt=True` and `enable_thinking=False`. No model inference is needed.

Minimal reproduction:

```
from transformers import AutoTokenizer

tok = AutoTokenizer.from_pretrained(
    "google/gemma-4-31B-it-qat-w4a16-ct",
    revision="88c090599fb794134cba57e022082043afcc7bf8",
)

messages = [
    {"role": "user", "content": "Read x.py."},
    {
        "role": "assistant",
        "content": "NOTE_BEFORE_CALL",
        "tool_calls": [{
            "id": "c1",
            "type": "function",
            "function": {
                "name": "read_file",
                "arguments": {"filepath": "x.py"},
            },
        }],
    },
    {"role": "tool", "tool_call_id": "c1", "content": "RESULT"},
]

text = tok.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True,
    enable_thinking=False,
)
print(repr(text[-200:]))
```

The prompt ends with:

```
...RESULT<|"|>}<tool_response|>NOTE_BEFORE_CALL<turn|>\n
```

The model turn has been closed, but **no new `<|turn>model` header is added**. Setting the assistant’s content to `None` instead leaves the turn open at `<tool_response|>`.

The cause appears to be:

- The template renders tool calls, then tool responses, then assistant content.
- Nonempty content triggers `<turn|>`.
- `ns.prev_message_type` remains `tool_response`, so the generation-prompt branch suppresses the new model header.

The updated `continues_into_next` check fixes historical boundaries when another assistant message is already present. At the end of a generation prompt, that next assistant message does not exist yet, so this case remains broken.

There is also a chronology issue: OpenAI assistant content accompanying tool calls can be a note emitted **before** execution, but the template moves it after the tool result.

Could this case be checked alongside the proposed template update? A swap to the July canonical version alone does not resolve this final boundary. This is a reproducible formatting issue; I have not measured its effect on task scores.


> **** (2026-10-03 05:57, 0 votes)
> Some errors are still expected with a 31B model, but at least an update will resolve the bigger ones that are already readily fixed.


> **** (2026-10-12 16:32, 0 votes)
> Thanks for sharing this and for taking the time to reproduce the issue.
> 
> I'm wondering how much this could affect the agents during evaluation, especially when they make several tool calls in a row.
> @ryanholbrook 
> Do we know if the competition harness actually encounters this situation, where an assistant message contains both text and a tool call?
> 
> I've noticed that agents can sometimes get stuck repeating tool calls or producing invalid ones, and I'm trying to understand how much of that comes from the model itself versus the way the conversation is handled.
> 
> It would also be interesting to know whether the organizers plan to check this issue alongside the July template update.
> 
> Has anyone tested whether fixing the template changes the actual success rate of the agents, rather than just the formatting?


---

## Submission stuck in judging
/competitions/gemma-4-developer-agent/discussion/750905 | by  | posted 2026-10-20 04:32 | last comment 2026-10-20 14:38 | 1 comments | -1 votes


**** (2026-10-20 04:32, -1 votes)
My submission has been running for 18 hours.
Is this an error or not?


**** (2026-10-20 14:38, 0 votes)
it is at most an kaggle error, or maybe a code error


---

## Submission with a skill scored 0.00 with no error: do skills still work on the scorer?
/competitions/gemma-4-developer-agent/discussion/750350 | by  | posted 2026-10-17 21:45 | last comment 2026-10-20 10:19 | 6 comments | 1 votes


**** (2026-10-18 10:30, 2 votes)
One more data point, in case it helps narrow this down. My agent has used a skill (stdlib Python scripts under skills/, called with run_skill_script) since early October. The best of those runs scored 0.15. Every later submission that kept the same skill, with other changes, scored between 0.06 and 0.12, but none came back 0.00. So at least on my side, skills were not completely broken on the scorer.

To check for drift, I'm re-submitting my exact 0.15 zip, byte-identical. I'll post the score here.

@ryanholbrook, could you confirm whether skill execution or the harness build changed on the scorer since about Oct 12?


> **** (2026-10-18 11:30, 0 votes)
> I have noticed that skills without scripts are useless, as unless otherwise forced, the model simply ignores using skills altogether! In general, the model assumes that skill based knowledge is already part of the pre-trained knowledge! 
> 
> What is concerning is an additional overhead of much less than 1 minute from basic 0.22 scorer notebook (with just system.md) causes the scoreto nose-dive from 0.18 to 0.05!


> > **** (2026-10-20 06:08, 2 votes)
> > Follow-up: I re-submitted my exact 0.15 zip, byte-identical, with a skill-based agent. It scored 0.10 this time. So skills still run on the scorer for me, and none of my skill-based submissions has scored 0.00. But the same bytes moved by 0.05 between Oct 6 and Oct 19. That fits the run-to-run noise others reported (one artifact got 0.22 / 0.17 / 0.15), though I can’t rule out a harness change in between.


> > **** (2026-10-20 10:19, 0 votes)
> > I tried a sequential agent with skills - 
> > 
> > 32 tool calls and 5 minutes - 0.03
> > 
> > 28 tool calls and 8 minutes - timed out
> > 
> > 28 tool calls and 5 minutes - 0.05 
> > 
> > 32 tool calls and 5 minutes - 0.05 
> > 
> > 32 tool calls  and 5 minutes - 0.08 (with some speed improvement)
> > 
> > 28 tool calls and 7 minutes - timed out


**** (2026-10-17 21:45, 1 votes)
Hi @ryanholbrook and team,

My submission 57285365 (Oct 16, 22:44 UTC) scored 0.00 with no error message.
It differs from my 0.15 submission (57052316) only by one skill on the root agent (a single standard-library Python script under skills/) and prompt lines that mention it.
Model, sampling and budgets are unchanged.

I suspect something failed on the scorer side rather than in the agent. It looks as if almost no task produced a patch. The same zip passes validate_directory and compile_submission on wheelhouse 31.


**** (2026-10-18 18:45, 0 votes)
There were changes to the agent runner between swegemma 2.7 and swegemma 2.11, it handles errors differently. This is the root cause of some similar behavior I was seeing.


**** (2026-10-18 00:27, 0 votes)
I am facing same issue - I get 0.03 or 0.05 - on any thing other than plain main agent with system.md - results in score falling down from 0.18 to 0.05!! 

May be I am doing something wrong in my agent configuration - else a prize money of $65000 won't make sense for a solution that involves just a main agent and system.md - two simple documents - we definitely should do something innovative!! 😀 That leaves LoRA as  the only expected solution!

I think if scorer allows task resolution without time cap, it might get higher score (which means solving smaller number of tasks without notebook timing out). Score metric can then include time taken to solve as a factor.

@ryanholbrook - any comment will be helpful!


---

## Day 1 of doing this competition on 4090 
/competitions/gemma-4-developer-agent/discussion/750933 | by  | posted 2026-10-20 07:04 | last comment 2026-10-20 07:04 | 0 comments | -3 votes


**** (2026-10-20 07:04, -3 votes)
I write some things on twitter. So I have to post it here too because of private sharing. Sorry. 

spent today on SFT, broader evals, and trace analysis. the agent is making more edits, but we haven’t measured a gain in solved tasks. 

some patches touch the wrong code; others only address part of the requirement. 

next: 
test whether providing the relevant code helps, so we can separate search failures from repair failures before spending more GPU hours.


https://x.com/mistyotter_ai?s=11&t=xCz7au8ZFmpaLtriqpSBkQ


---

## Bug Report with 5 Issues
/competitions/gemma-4-developer-agent/discussion/750753 | by  | posted 2026-10-19 18:17 | last comment 2026-10-20 01:20 | 3 comments | -2 votes


**** (2026-10-19 18:17, -2 votes)
# Five reproducible issues in the current Gemma 4 Developer Agent stack (wheelhouse V31) + a compatibility-first fix plan

**Audit date:** October 19, 2026 (UTC)  
**Competition:** [Google - The Gemma 4 Developer Agent Competition](https://www.kaggle.com/competitions/gemma-4-developer-agent)  
**Artifacts reviewed:** official [starter notebook, revision 3](https://www.kaggle.com/code/ryanholbrook/getting-started-gemma-4-developer-agent) and [official wheelhouse, version 31](https://www.kaggle.com/datasets/metric/gemma-4-developer-agent-wheelhouse/versions/31)

## Summary

This report reviews the current published competition setup, traces the relevant code paths in the official wheelhouse, and documents focused source-level reproductions performed during the audit. **Five distinct defects are reproducible in the currently published development stack.** The audit did **not** reproduce these as end-to-end private-scoring failures, and it cannot determine whether the production scorer uses every implicated path.

| ID | Priority | Reproduced behavior | Primary code path |
|---|---|---|---|
| **F1** | High | A different passing JUnit test can satisfy an explicitly required test; an unrelated skipped parameter can reject a required passing test. | `swegemma/harness/verification.py` |
| **F2** | High | An adapter name that collides with a base-model alias can resolve to the **base model**, not the requested adapter. | `adk_submission/server.py`, `swegemma/harness/agent_runner.py` |
| **F3** | Medium | The subprocess sandbox rewrites path-like **literal data** in a shell command, not just filesystem operands. | `swegemma/sandbox/subprocess.py` |
| **F4** | Medium | Accepted `response_mime_type: application/json` is not translated into a request-level JSON constraint. | `adk_submission` generation resolver; `google_adk` LiteLLM converter |
| **F5** | Medium | A Python skill that prints partial output and exits nonzero is returned with `status="warning"`. | `adk_eval_core` sandbox result adapter; `google_adk` skill toolset |

**These are newly identified findings in this audit, not necessarily newly introduced bugs.** The audit screened the available text of **257 discussion threads** across the main and paper competitions (1,075 returned topic/comment records) and found no earlier written report matching these **exact mechanisms**. That is not evidence that the organizers have never heard of them privately. Already reported or repaired historical issues are intentionally excluded.

**Proposed resolution:** one pinned, organizer-owned execution contract; five narrow fixes that preserve existing valid submission formats; a common preflight and regression suite; and a uniform scoring/version policy if a correction changes results. An unconditional promise of "zero breakage" would be misleading without access to the private scorer, but the release gates below specify how to prevent *unexplained* regressions.

---

## 1. Audited setup and boundaries

The current public configuration, as checked against the competition pages and official artifacts, is:

- **Submission:** `submission.zip`, with `agent.yaml` at its root. YAML-driven ADK agents, relative `!include` files, subagents, prompts, sandboxed skills, and optional PEFT LoRA adapters are supported.
- **Allowed base models:** `gemma-4-31b-it-qat-w4a16-ct`, `gemma-4-12b-it-qat-w4a16-ct`, `gemma-4-e4b-it-qat-w4a16-ct`, and `gemma-4-e2b-it-qat-w4a16-ct`. All agents/subagents in one submission must use the same base model; their LoRA adapters can differ. The older "31B only" description is no longer current and is **not** included as a defect.
- **Evaluation:** patch-level PASS/FAIL; aggregate score is the percentage of successfully patched tasks. There is a 12-hour total patch-generation budget including sandbox setup, excluding patch validation.
- **Compute:** the published notice provides L4 x4 notebooks (96 GB aggregate GPU memory), with internet disabled.
- **Data:** the public description specifies 129 local development tasks (FastAPI, Rich, Requests, HTTPX) with reference and test patches, and approximately 120 hidden tasks from private repositories split between public/private evaluation.
- **Competition constraints:** one submission/day, up to two final submissions, maximum team size five. Main entry and merger deadline: November 25, 2026; final submission deadline: December 2, 2026 (both 23:59 UTC). The separate paper track deadline is November 12, 2026 (23:59 UTC).

**Exact published software baseline:**

| Artifact | Version / identity |
|---|---|
| Official starter | Revision 3; last run October 16, 2026; defaults to 12B and selects `sandbox="subprocess"` for local evaluation |
| Official wheelhouse | Dataset version **31**, published October 12, 2026 |
| `swegemma` | `0.2.11` |
| `adk_submission` | `0.2.13` |
| `adk_eval_core` | `0.1.0` |
| `google_adk` | `1.36.1` |
| Included serving stack | vLLM `0.19.1`; Transformers `5.13.1` |
| Starter notebook Python metadata | `3.12.13` |

This is a **public-artifact audit**. The production scorer's exact wheel hashes, container image, test manifests, and configuration were not available. The fact that a bug exists in a published development path does not, alone, demonstrate leaderboard impact.

---

## 2. F1 - Explicitly required tests can be matched to the wrong JUnit results

**Priority:** High for evaluation correctness.  
**Source:** `swegemma 0.2.11`, `swegemma/harness/verification.py`: `_node_matches_requirement`, `_validate_junit_xml`, and the surrounding `verify_task` path. Explicit task identifiers are retained earlier in `models/task.py`.

### Reproduction and result

Take an explicitly required test node:

```text
tests/test_expected.py::TestExpected::test_value[required]
```

Test the reviewed JUnit validation helpers with two independently authored report cases:

| Fixture | Current helper result | Expected result |
|---|---|---|
| Only `tests/test_other.py::TestOther::test_value[other]` is reported as passing | **Accepts** `(True, None)` | Reject: the required identity is absent |
| The exact required parameter passes, but a different parameter of `test_value` is skipped | **Rejects** with "Required test node did not pass..." | Accept the required passing parameter |
| Exact required identity passes (control) | Accepts | Accept |

The reproduction exercised the reviewed helper functions with small synthetic JUnit XML fixtures. The issue is that matching broadens qualified identifiers into candidates including bare function names and parameter-stripped names. Explicit file/class/parameter identity is not preserved when evaluating a requirement.

**Important limitation:** The surrounding verifier still rejects a nonzero pytest exit code and reported JUnit failures/errors. This does *not* show that a failing pytest assertion magically becomes a pass. The proven flaw is in associating otherwise admissible test-result records with a specific required node. Its effect on hidden tasks is unknown.

### Minimal compatible fix

1. For explicitly qualified requirements, compare structured identity: file/module, class, function, parameter, and outcome. Prefer canonical pytest node IDs captured alongside JUnit results where possible.
2. Keep a **separate**, explicitly documented matching mode for intentionally broad bare-function families inferred from patches. Do not turn all matching into literal string equality; that could break legitimate existing fixtures.
3. If an available XML report cannot uniquely establish a required identity, treat the ambiguity explicitly rather than silently substituting a similarly named test.

**Regression gate:** The exact node passes; another file/class/parameter cannot substitute; required skips fail; unrelated skipped siblings do not invalidate a passing required node; legacy family matching and global process/XML failure checks remain intact.

---

## 3. F2 - A valid adapter alias collision can silently select the base model

**Priority:** High for declared model behavior.  
**Sources:** `adk_submission 0.2.13`, `server.py:create_model_registry`; `swegemma 0.2.11`, `harness/agent_runner.py:resolve_swegemma_adapter` and its compile hook.

### Reproduction and result

This is a permitted configuration shape (using the same name for the adapter directory and selected base-model alias):

```yaml
model: gemma-4-31b-it-qat-w4a16-ct
adapter: gemma-4-31b-it-qat-w4a16-ct
```

In the tested registry, the two identities are distinct:

```text
gemma-4-31b-it-qat-w4a16-ct          -> base model target
adapter:gemma-4-31b-it-qat-w4a16-ct  -> LoRA adapter target
```

The custom `resolve_swegemma_adapter` looks up the **bare name first**, and therefore selects the base target instead of the registered adapter target. The official starter builds the relevant registry with `aliases=[declared_model]`.

The reproduction used the actual reviewed registry/resolver logic with a synthetic adapter manifest and distinct model targets. **It tested alias resolution only**: no model weights were loaded and no GPU inference was run. Noncolliding adapter names are not implicated. The generic `adk_submission` resolver already favors the adapter namespace; the problem is specifically the custom resolver path.

### Minimal compatible fix

1. In the custom resolver, prefer the explicit `adapter:<name>` namespace.
2. Retain a bare-name fallback *only* when it unambiguously denotes an adapter in a legacy registry.
3. Preserve base-only agents. Avoid shared mutable client settings leaking from one subagent to another.
4. Expose a preflight receipt with the declared base, requested adapter, selected registry key, and actual served model identifier.

**Do not** force otherwise valid adapter directories to be renamed as the default fix.

**Regression gate:** Base-only, ordinary adapter, colliding-name adapter, and multiagent/multiadapter cases all resolve to their intended served identities; client settings stay independent. Organizers should run real inference smoke tests on the production serving image before enabling the correction.

---

## 4. F3 - The subprocess sandbox modifies literal shell-command data

**Priority:** Medium for development environment fidelity.  
**Source:** `swegemma 0.2.11`, `sandbox/subprocess.py:exec`. The official starter's local evaluation explicitly selects `sandbox="subprocess"`.

### Reproduction and result

Send this harmless command to the current subprocess executor:

```bash
printf '%s\n' '/tmp/cache' '/workspace/api' '/usr/local/bin/tool'
```

**Expected stdout:**

```text
/tmp/cache
/workspace/api
/usr/local/bin/tool
```

**Observed:** those path-like literals are replaced with temporary physical sandbox and virtual-environment prefixes. The reviewed implementation performs whole-command replacements for virtual prefixes (including `/tmp`, `/workspace`, `/usr/local/bin`, and `/wheels`) *before* the shell interprets quotations and argument boundaries.

The reproduction captured the executor's translated subprocess arguments and executed an authored `printf` fixture. This also exposes a mechanism that can alter source text constructed through shell commands, `python -c` strings, here-documents, grep patterns, or assertions.

**Scope:** The dedicated `write_file` and `edit_file` tool paths preserve content bytes; the Docker execution path does not apply this particular raw-text replacement. We cannot assume the private scorer uses the subprocess backend.

### Minimal compatible fix

1. Immediately recommend `write_file`/`edit_file` for generating source that contains literal path-like strings.
2. For a durable repair, separate *internal path mapping* from *agent command bytes*. Ideally provide a filesystem namespace exposing the expected `/workspace`, `/tmp`, and wheel paths, and execute commands without rewriting raw text.
3. If that namespace is unavailable in local subprocess mode, introduce an explicitly versioned execution interface with documented path semantics. Preserve existing internal initialization and dependency-install behavior during migration.

A quote-aware regex is not a safe substitute: quoted strings can be real filesystem operands or literal data. Simply removing all replacements without replacing their path behavior could break setup.

**Regression gate:** Exact command/script/file bytes are preserved for quoted strings, here-documents, embedded Python, spaces, Unicode, and path-like constants. Working directories, virtual/absolute paths, offline wheel installs, task setup, and expected parity with the supported Docker mode continue to work.

---

## 5. F4 - Accepted JSON MIME configuration is dropped in the LiteLLM request path

**Priority:** Medium for configuration fidelity.  
**Sources:** `adk_submission 0.2.13`, `schema.py` and `resolvers/generation.py`; `swegemma/config.py:build_submission_limits`; `google_adk 1.36.1`, `models/lite_llm.py:_get_completion_inputs`.

### Reproduction and result

A supported-looking submission configuration includes:

```yaml
generate_content_config:
  response_mime_type: application/json
```

The submission schema accepts `response_mime_type`; the generation resolver forwards it into a GenAI config. But the installed LiteLLM conversion constructs `response_format` from `response_schema`, **not** from `response_mime_type`. Participant-supplied `response_schema` is separately prohibited by the competition restrictions.

In the isolated conversion fixture, the resulting values are:

```text
response_format = None
generation_params = None
```

Here `generation_params = None` describes a *minimal fixture that supplies only the MIME field*, not all real-world generation configurations. No JSON constraint is emitted by that field. The reproduction tested the reviewed request conversion; it was not a live endpoint generation test.

A model may still output valid JSON due to prompting or ordinary behavior. Tool/function argument handling is a different path. This finding does not mean every JSON response or tool call fails.

### Minimal compatible fix

1. Explicitly map supported `application/json` intent to the response-format capability of the **pinned** serving backend, preserving any internally required schema precedence.
2. Leave omitted MIME fields and standard text generation unchanged.
3. Report unsupported MIME values or unsupported JSON/tools/reasoning combinations at compile/preflight time instead of silently ignoring them.
4. Roll out a warning before changing a setting's semantics: honoring a previously ignored field may legitimately change generated outputs.

**Regression gate:** Check actual serialized requests *and* live endpoint behavior for omitted MIME, text, valid JSON, invalid MIME, JSON with tools, and JSON with reasoning. Do not infer endpoint support only because an SDK accepted the input.

---

## 6. F5 - A failed Python skill with partial output returns `warning`

**Priority:** Medium for agent/tool control flow.  
**Sources:** `adk_eval_core 0.1.0`, `sandbox/base.py:AdkSandboxCodeExecutor`; `google_adk 1.36.1`, `tools/skill_toolset.py` and `code_executors/code_execution_utils.py:CodeExecutionResult`.

### Reproduction and result

Execute this Python skill script:

```python
print("started")
raise SystemExit(7)
```

The underlying sandbox returns a nonzero exit and execution-error state. During conversion into `CodeExecutionResult`, structured status is lost while stdout/stderr are retained; the next Python-skill layer defaults the exit code and infers status from streams.

**Observed returned fields:**

```text
stdout: "started\n"
stderr: "Command failed with status=error, exit_code=7"
status: "warning"
```

**Expected structured status:** execution error, with the partial stdout preserved.

This was reproduced by exercising the reviewed sandbox/skill conversion with a small locally executed script. Failure evidence is still present in stderr: the bug is **misclassification as `warning`, not a false `success` or erased error**. Python failures without stdout and shell-script execution follow somewhat different paths. The issue does not directly change pytest patch grading.

### Minimal compatible fix

1. Preserve authoritative `exit_code`, `timed_out`, and execution state in an additive result field or companion metadata.
2. Classify nonzero exit and timeout **before** applying any stdout/stderr heuristics.
3. Keep existing stdout, stderr, output-file fields, shell status envelopes, and a fallback for legacy executors without structured status.

Do not suppress partial stdout, delete errors, or treat all stderr text as process failure.

**Regression gate:** Test success, success with warnings, nonzero exit with stdout, nonzero exit with only stderr, and timeout after partial output in both Python and shell paths. Existing consumers must still be able to read the old result fields.

---

## 7. One coordinated solution instead of five unrelated patches

These failures share a cause: **meaning is lost or confused at interfaces**.

| Boundary | Information that must survive | Targeted correction |
|---|---|---|
| JUnit report -> test verdict | Full required-test identity and outcome | Canonical identities; explicit legacy family matching |
| Agent config -> served model | Base identity **and** adapter namespace | Adapter namespace first; safe legacy fallback |
| Agent command -> process | User command bytes separate from internal paths | Real path namespace or versioned execution interface |
| GenAI config -> inference request | Supported format/MIME intent | Capability-checked response-format conversion |
| Process result -> skill reply | Exit code, timeout, stdout, stderr | Add structured metadata; classify failures first |

### Recommended rollout

**Phase 0 - Freeze the actual baseline.** Record the precise production scorer build, model artifacts, serving image, wheel hashes, configuration, submitted archive hashes, patches, and scoring receipts. Track production separately from public starter/wheelhouse versions until their equivalence is confirmed.

**Phase 1 - Publish a single execution-contract manifest.** Pin compatible wheel/source hashes, model artifact versions, Python/container identities, tool semantics, supported response formats, archive/schema limits, and budget-accounting boundaries. Keep this **outside** participant `agent.yaml` to avoid adding a required field that would invalidate existing submissions. Starter, preflight, compiler, runtime, and scorer should consume the same contract or generated views of it.

**Phase 2 - Add no-penalty preflight diagnostics.** Check archive structure and relative includes, model/adapter resolution, prohibited or unsupported settings, file limits, and capabilities *before* a full scoring run. Show the resolved base/adapter target, accepted-but-unhonored options, and contract version. Diagnostics should not use a daily submission slot or expose hidden tests.

**Phase 3 - Backport the five small fixes.** Avoid simultaneously migrating ADK, vLLM, Python, model formats, or unrelated dependencies. Keep valid `submission.zip`/`agent.yaml` layouts, allowed adapter names, existing tools, and default behavior compatible. Changes that intentionally alter affected cases must be called out by scoring/runtime version.

**Phase 4 - Shadow-test before release.** Replay a representative set of archived submissions against the previous and candidate contracts. Diff deterministic outputs (test identities/verdicts, model routing, command bytes, request shapes, skill status, and budget accounting). For stochastic GPU inference, compare meaningful behavior and outcomes rather than demanding bit-for-bit identity. Explain every observed change.

**Phase 5 - Use one fair scoring policy.** A correct verifier can change scores; preserving every erroneous score is not the same as preserving fairness. If organizer-side changes affect official results, announce the effective contract and apply a consistent rerun/regrading policy, retaining original timestamps, quotas, and tie-break treatment as appropriate. Do not mix incompatible scorer versions or allow teams to choose an old permissive path.

**Phase 6 - Promote/rollback as a unit.** Treat preflight, compiler, request translation, result handling, sandbox, verifier, and documentation as one coupled release. Retain the baseline and candidate receipts. A partial rollback can recreate the mismatches.

### Release acceptance matrix

| Gate | Must pass before production promotion |
|---|---|
| **F1 verifier** | Explicit node identity cannot be substituted; unrelated skip is harmless; legacy matching and pytest/JUnit failures remain correct |
| **F2 adapters** | Base-only, ordinary, colliding, and multiadapter cases resolve correctly; supported model/adapter inference completes |
| **F3 sandbox** | Literal command bytes preserved *and* setup, filesystem access, wheel installs, and Docker/local behavior stay correct |
| **F4 generation** | Serialized and live-serving tests for text/JSON/tools/reasoning; unsupported settings diagnosed, not ignored |
| **F5 skills** | Real nonzero exit/timeout becomes error while partial output is preserved; legacy result consumers still work |
| **Archive compatibility** | Previously valid submission archives still parse and run without unrelated schema/name/layout changes |
| **Evaluation controls** | Known-good reference patches pass; known failing baselines fail; required tests execute; task isolation and patch protections hold |
| **Budget and fairness** | Same setup/verification accounting, deadlines, timestamps, quotas, and one published effective scoring policy |
| **Operational gate** | Every changed output is explained; scorer and manifest match the tested build; unified rollback works |

**Release criterion:** unchanged controls remain unchanged, the five documented counterexamples change in the intended direction, and **unexplained** differences block promotion. That is a testable compatibility standard; an absolute "nothing can ever break" guarantee is not possible from public inspection.

---

## 8. Verification history, limitations, and reproducibility

### What was checked

- Main competition: **230** topic bodies and **768** comments.
- Separate paper track: **27** topic bodies and **50** comments.
- **257** threads; **1,075** returned records total. Inventories and nested reply counts reconciled; 29 records had no readable text. Image-adjacent text was screened, and seven potentially relevant screenshots were inspected.
- Main overview, rules, evaluation, data description, model/budget announcements, paper track, official starter source/metadata, wheelhouse V31 inventory, and the specific wheel source paths named above.
- Minimal local reproductions using the reviewed functions/classes with synthetic XML, adapter registry, command, generation-config, and Python-exit fixtures. The JUnit test included both negative cases and an exact-match positive control.

No exact earlier **written** report of these five mechanics was found in the reviewed thread text. The review cannot cover private organizer discussions, deleted posts, every embedded image, or other unexamined websites. Generic reports of zero scores, adapters, JSON, or skill failures were *not* treated as reports of these exact code mechanisms without matching evidence. Resolved historical bugs and previously reported unresolved issues have been excluded from the five-finding list.

### What this report does not claim

- No hidden test set, private evaluation manifest, production scorer configuration, or production replay corpus was accessible.
- No GPU inference or official Kaggle submission was performed as part of these reproductions.
- No leaderboard-impact count, affected-team count, or score-change magnitude is established.
- The public data description was reviewed, but competition data-file bytes requiring separate authorization were not independently audited.
- The priority labels express potential consequences of each confirmed code path, not measured competition incident severity.

### Official artifact fingerprints

These SHA-256 receipts identify the exact published wheels reviewed, rather than a mutable dataset slug:

```text
Dataset: metric/gemma-4-developer-agent-wheelhouse
Dataset ID: 12049435
Version: 31 (created 2026-10-12T19:51:31.090Z)

adk_eval_core-0.1.0-py3-none-any.whl
  e614e1b2fe8d886a634871e4c57f9887e1cc66e8c27300f8503a43c6e3ca82f3
adk_submission-0.2.13-py3-none-any.whl
  f156f0bd84580ccb9334726d114d7a5481f16d3a6e2887cc4d276ced0ef8d99d
google_adk-1.36.1-py3-none-any.whl
  1a2f6868c509e3151fb0de3575a7d18b45c338be86f420924dad74e7193631a0
swegemma-0.2.11-py3-none-any.whl
  9ad876581f3acde8ec3c369858f0834e2b9f41a3cffce3ca42f09cb090aea9d3
```

Two directly reproduced source-file receipts:

```text
swegemma/harness/verification.py
  99e2a5fdab2be2b5e0388de29080da9d6e7003cf8b53299cda790464f4ecd2aa
swegemma/sandbox/subprocess.py
  a26e9265d93f0387dd0a820ea451d1c530884bebca41583738f3ab2cc31df1f2
```

### Primary references

1. [Competition overview, evaluation, timeline, and model/budget rules](https://www.kaggle.com/competitions/gemma-4-developer-agent/overview)
2. [Official rules](https://www.kaggle.com/competitions/gemma-4-developer-agent/rules)
3. [Official data description](https://www.kaggle.com/competitions/gemma-4-developer-agent/data)
4. [Official getting-started notebook (revision 3 as audited)](https://www.kaggle.com/code/ryanholbrook/getting-started-gemma-4-developer-agent)
5. [Official metric wheelhouse (version 31)](https://www.kaggle.com/datasets/metric/gemma-4-developer-agent-wheelhouse/versions/31)
6. [Organizer announcement on smaller-model support](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748287)
7. [Separate paper competition](https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/overview)
8. [Main discussion history](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion)

---

## Request to the organizers

Could the organizers please confirm whether the **production scorer** uses these same verification, registry-resolution, and conversion paths? If so, I recommend publishing a pinned execution-contract identifier, adding the focused negative-control fixtures above, and rolling out the corrections as one tested compatibility release with an announced scoring policy.

This report does **not** request rules changes, special treatment, extra submission attempts, or publication of hidden tasks. The goal is to keep valid participant configurations working while making test identity, adapter selection, command behavior, JSON format requests, and skill failure status **accurate and observable**.

If a newer official release already fixes a specific mechanism, a version/hash and a regression test showing that correction would be sufficient to retire that finding.


**** (2026-10-19 22:49, 0 votes)
Thanks for bringing this to our attention! We are working on this.


> **** (2026-10-20 01:19, 3 votes)
> This is just a no effort AI slop…
> 
> F1 is not the case, since Ryan validated each hidden task by running its golden patch through the harness.
> 
> F2 is simply "dont name your adapter like the base model"
> 
> F3, F4, F5 also have little to no effect on either generating a correct patch or scoring


---

## How to format the training data for SFT ?
/competitions/gemma-4-developer-agent/discussion/750270 | by  | posted 2026-10-17 14:31 | last comment 2026-10-19 18:53 | 4 comments | 0 votes


**** (2026-10-17 18:28, 0 votes)
How did you generate data ?


> **** (2026-10-19 15:45, 0 votes)
> I used haiku 5.5 but that was not useful at all.


> > **** (2026-10-19 18:53, 0 votes)
> > What do u mean it was not useful? Did the data have no successful trajectories or something else? Another thing is we can't use other models to generate data afaik


**** (2026-10-17 14:34, 0 votes)
are u guys doing direct GRPO or SFT followed by GRPO?


**** (2026-10-17 14:31, 0 votes)
How are u guys formatting the SFT data and also how much data are u generating which is working for SFT ?


---

## If training Gemma4 31b, which checkpoint are people using: unquantized or the competition checkpoint? 
/competitions/gemma-4-developer-agent/discussion/750597 | by  | posted 2026-10-19 05:47 | last comment 2026-10-19 15:39 | 2 comments | 2 votes


**** (2026-10-19 05:47, 2 votes)
If training Gemma4 31b, which checkpoint are people using: unquantized or the competition checkpoint?


**** (2026-10-19 11:03, 0 votes)
you can't use the competetion checkpoint its unfinetunable, use the same QAT checkpoint just unquantized one.


> **** (2026-10-19 15:39, 0 votes)
> Yeah just checking


---

## Architectural Questions for 0.22 - 0.24+ Single-Agent Configurations
/competitions/gemma-4-developer-agent/discussion/750496 | by  | posted 2026-10-18 15:14 | last comment 2026-10-19 15:34 | 3 comments | 5 votes


**** (2026-10-18 15:14, 5 votes)
Hi everyone,

For teams currently reaching 0.22 - 0.24 on the public leaderboard with single-agent configurations using gemma-4-31b-it-qat-w4a16-ct, I would appreciate community insights on a few architectural trade-offs:

1. Local Verification vs Global Clock Budget
In swegemma, running local targeted pytest suites (e.g., pytest -k with short tracebacks) allows catching simple regressions, but introduces command execution latency. Given the 12-hour global evaluation cap across the private benchmark repositories, have you found that running a local test and single repair loop provides a net positive on the final score, or does the overhead risk timeout starvation on heavier repositories?

2. Context Management under 32k Window
With thinking_budget set around 4096 and max_output_tokens at 8192, multi-turn trajectories (turns 10 to 15) consume significant context. What strategies are you using to prevent context overflow or losing the original issue specification late in the run? Are you strictly limiting shell outputs (e.g., piping to head/tail), or using structured state persistence?

3. First Edit Timing and Tool Budget Allocation
In an 8-minute / 28-call budget, what has proven to be the optimal window for applying the first source edit? Does forcing an early edit by call 8-10 yield better results, or is spending up to call 12 on root-cause analysis more reliable across unseen codebases?

4. Handling Sparse and Non-Standard Issue Prompts
Some benchmark tasks provide minimal context, such as a short title or an issue URL without reproduction snippets. Beyond inspecting recent repository commits via git log, what automated search heuristics have been effective for locating the relevant module without wasting exploration turns?

5. Repository Structure Edge Cases
Certain repositories test examples or tutorial code located in documentation directories rather than internal library modules. How does your agent differentiate between modifying core package internals versus documentation or example files?

Thanks in advance for sharing your thoughts and experiences.


**** (2026-10-18 23:14, 0 votes)
@souvikdbiswas were u able to achieve 0.20 score by optmizing the prompts, subagents and skill configurations only ?


> **** (2026-10-19 15:27, 2 votes)
> No, I didn't use subagents or custom skills. It was mainly iterative prompt adjustments and tuning the standard runtime parameters. Still experimenting with different setups to see what generalizes best!
> Are you experimenting with subagents in your runs? How has turn/time efficiency been for you?


> > **** (2026-10-19 15:34, 0 votes)
> > I experimented with subagent and skill but they are not improving the system. I suspect that is due to context overload. 
> > I am currently using 8 minutes and 30 tool calls setting. 
> > 
> > I am experimenting with SFT currently using smaller models like E4B but nothing good has came till now.


---

## Submission 57367196: Notebook Threw Exception - request for failing stage
/competitions/gemma-4-developer-agent/discussion/750670 | by  | posted 2026-10-19 12:58 | last comment 2026-10-19 12:58 | 0 comments | -1 votes


**** (2026-10-19 12:58, -1 votes)
Hi Kaggle team,

Our Gemma 4 Developer Agent submission 57367196 (2026-10-18 19:54 UTC) ended with “Notebook Threw Exception” and no score. The API provides only: “Your notebook hit an unhandled error while rerunning your code.”

The submitted submission.zip has SHA-256 ff2cf536d2cf1a182bb99eea95416cf4bc34055753250c8d21ee6bc355781ee0. It passes offline package validation with adk_submission 0.2.13 and swegemma 0.2.11, but we cannot reproduce or locate the scored-run exception because its traceback is unavailable to us.

Could you share the failing stage and exception type, or a redacted traceback? We do not need hidden task content. This would help us distinguish a package/configuration issue from a runner issue.

Thank you,
Team Void


---

## Submission 57361964 got “Submission Scoring Error” — is it covered by the queue recovery?
/competitions/gemma-4-developer-agent/discussion/750622 | by  | posted 2026-10-19 07:53 | last comment 2026-10-19 07:53 | 0 comments | -1 votes


**** (2026-10-19 07:53, -1 votes)
Hi @ryanholbrook,

I saw the recent update regarding submissions receiving Kaggle Error after waiting >15h in the L4 queue. Thanks for the clarification.

I think my submission may be a different case, so I wanted to check before resubmitting.

Submission 57361964 (2026-10-18 16:48 UTC) ended with Submission Scoring Error, not Kaggle Error, with:

“Your notebook generated a submission file with incorrect format.”

The complete elapsed period was also under 15 hours, so it doesn't appear to fit the >15h queue-timeout case.

I verified the exact submitted submission.zip locally with the current harness and compiler, and the notebook output SHA matches the frozen artifact.

Could you check whether this submission is also included in the current recovery/re-scoring process, or whether this is a separate scoring issue?

Submission ref: 57361964

Thanks!


---

## Thinking mode drops the model's thoughts between tool calls (vLLM ignores `reasoning_content`). Will the scoring environment be patched?
/competitions/gemma-4-developer-agent/discussion/744354 | by  | posted 2026-09-29 14:05 | last comment 2026-10-19 07:17 | 7 comments | 12 votes


**** (2026-09-29 14:05, 12 votes)
Hi organizers,

With thinking on (the scoring server's default), the thought the model writes before a tool call never reaches the prompt of the next step. The model has to re-derive its reasoning at every tool call. Gemma 4's docs say thoughts must be kept inside a tool-calling turn ("thoughts must NOT be removed between the function calls", [prompt formatting guide](https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4)).

**Cause.** ADK (`google-adk` 1.36.1, `LiteLlm`) sends the previous thought as `reasoning_content`. vLLM 0.19.1 only reads `reasoning` from incoming messages (`vllm/entrypoints/chat_utils.py`, line 1512: `reasoning = message.get("reasoning")`), so the thought is dropped before the chat template sees it. The Gemma 4 template itself accepts both names. This is a known upstream bug: [vllm-project/vllm#38488](https://github.com/vllm-project/vllm/issues/38488), with a fix proposed in [vllm-project/vllm#42664](https://github.com/vllm-project/vllm/pull/42664).

**Reproduction** (scoring vLLM config, `gemma-4-31b-it-qat-w4a16-ct` v2, 4×L4). Render one history (user → assistant tool call with a thought → tool result) through `/tokenize` + `/detokenize`, with the thought under different keys:

```python
import requests
URL = "http://127.0.0.1:8000"
model = requests.get(f"{URL}/v1/models").json()["data"][0]["id"]
tools = [{"type": "function", "function": {"name": "get_time", "description": "Returns the current server time.",
                                           "parameters": {"type": "object", "properties": {}}}}]
thought = "The user wants the time. I will call get_time. My secret word is PAPAYAQUOKKA."

def history(**extra):
    return [{"role": "system", "content": "You are a careful assistant."},
            {"role": "user", "content": "What time is it?"},
            {"role": "assistant", "content": "", **extra,
             "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "get_time", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "call_1", "content": '{"time": "12:34"}'}]

for label, extra in [("no thought", {}), ("reasoning_content", {"reasoning_content": thought}), ("reasoning", {"reasoning": thought})]:
    body = {"model": model, "messages": history(**extra), "tools": tools,
            "add_generation_prompt": True, "chat_template_kwargs": {"enable_thinking": True}}
    toks = requests.post(f"{URL}/tokenize", json=body).json()["tokens"]
    text = requests.post(f"{URL}/detokenize", json={"model": model, "tokens": toks}).json()["prompt"]
    print(f"{label:18s} {len(toks):4d} tokens | thought in prompt: {'PAPAYAQUOKKA' in text}")
```

```
no thought           86 tokens | thought in prompt: False
reasoning_content    86 tokens | thought in prompt: False   <- what ADK sends
reasoning           114 tokens | thought in prompt: True
```

**It happens in real harness runs.** In the 636 public thinking-on baseline runs shared by @zzgtylors, we looked at 3,640 consecutive tool-call steps (no user message in between, before compaction, previous step had a thought and ≥300 completion tokens). The next prompt grew by only a median **0.35×** of the previous reply; if the reply were kept, it would be at least 1×. With thinking off it is 1.1×.

**Fix options (harness side; submissions cannot reach this layer):**
- In vLLM `chat_utils.py`: `reasoning = message.get("reasoning") or message.get("reasoning_content")` (the upstream fix), or
- Have the harness / ADK send the thought as `reasoning`.

**Questions:**
1. Can you confirm this is unintended?
2. Will the scoring environment be patched, and roughly when? We need to know whether to tune submissions for thinking mode before the Dec 2 deadline.
3. If it is patched, will existing submissions be re-scored under the fixed environment?

Thanks!


**** (2026-09-29 16:41, 3 votes)
Thanks for the heads up. Looks like this is a bug/incompatibility in how ADK and vLLM process reasoning tokens. vLLM [fixed](https://github.com/vllm-project/vllm/pull/42664) this in a later version. I'll add a patch accordingly and try to deploy later today. Unfortunately, due to compute constraints, we won't be able to rescore all existing submissions.


> **** (2026-09-30 17:28, 0 votes)
> @ryanholbrook any update on this? Thanks


> > **** (2026-09-30 18:32, 2 votes)
> > It's incoming.


> **** (2026-10-01 21:35, 0 votes)
> Yeah I was wondering why my SFT was rederiving its own reasoning so much.


**** (2026-10-19 07:17, 0 votes)
Thanks for the reproducible report and the staff confirmation. I am treating the reasoning-field fix as a runtime-contract dependency. For anyone validating locally, it would help to record the exact vLLM wheelhouse revision, model instance, thinking flag, and whether the next-turn reasoning field survives a tool response; otherwise local and public scores are difficult to compare. I am keeping my own competition code and results private and will share only clearly licensed, attributed artifacts.


**** (2026-10-01 08:08, 0 votes)
Just to confirm, your intention is to fix it? This will majorly affect how the submission models are configured and trained. With the fix in place the agent hits compaction limits and context limits much earlier.


> **** (2026-10-01 14:46, 2 votes)
> Yes, this is unambiguously a bug. The fix should be in the current wheelhouse.


---

## Notebook threw Exception with 12B model varient?
/competitions/gemma-4-developer-agent/discussion/749259 | by  | posted 2026-10-14 14:34 | last comment 2026-10-19 03:38 | 7 comments | 4 votes


**** (2026-10-14 14:34, 4 votes)
I am facing notebook exception when submit same submission (31B Gemma model)  with 12B Gemma model


**** (2026-10-18 16:03, 1 votes)
Adding another data point: submission 57178131 (2026-10-14) errored with "Notebook Threw Exception" on gemma-4-12b-it-qat-w4a16-ct. The bundle is identical to our 31B submission 57130429 (scored 0.17) except for the model: line: no adapters, no sub-agents, 6 standard tools, thinking_budget 4096. It compiles and validates locally on wheelhouse v31.
@ryanholbrook could you check whether the scorer's 12B path is applying the --hf-overrides and the vision_embedder fix? Several of us are seeing the same failure, so any 12B success would help. Thanks!


> **** (2026-10-18 17:14, 0 votes)
> Wondering; how long until it errored out? i.e. you waited for the whole queue first?


> > **** (2026-10-19 03:38, 0 votes)
> > Submitted 2026-10-14 09:57 UTC; it showed the error by 2026-10-15 07:10 UTC at the latest. Queue delay was ~14h at the time, so it probably failed early in the run (server startup) rather than mid-evaluation, but I don’t have the exact run duration.


**** (2026-10-15 04:30, 1 votes)
Same here: 12B fails, while the identical 31B bundle scores.

Submission 57188236 (2026-10-14 16:06 UTC): status complete, no score, error "Your notebook hit an unhandled error while rerunning your code."
The bundle is our 31B baseline with one change: model set to gemma-4-12b-it-qat-w4a16-ct in the root agent and the single sub-agent. No LoRA, no other config changes.
The same bundle on gemma-4-31b-it-qat-w4a16-ct scored 0.12 (submission 57152300, 2026-10-13), after the wheelhouse update of 2026-10-12 19:51 UTC (dataset version 31).

What we checked offline with the wheels of dataset version 31 (CPU only, no 12B inference):
- the agent request sent through compile_submission + ADK + LiteLLM is identical for the 31B and 12B bundles (the model choice only changes the server side);
- tokenizer.json of gemma-4-12b-it-qat-w4a16-ct/2 is byte-identical to the 31B one;
- its chat_template.jinja only adds image/audio/video branches for tool responses; for our text-only requests both templates render byte-identical prompts;
- the vLLM wheel in version 31 differs from the previous one only by skipping vision_embedder. weights in gemma4.py (the fix mentioned in the 12B announcement thread).

So from our side this looks like the scorer failing to serve 12B rather than a bundle problem, consistent with the reports above.

@ryanholbrook could you check whether the scorer applies the 12B --hf-overrides and runs the version-31 wheelhouse? Any hint from the scorer log (server startup vs. a later stage) would help. Thanks!


> **** (2026-10-18 17:16, 0 votes)
> Backing this up too! vllm 0.19.1 given the same --hf-overrides suggested by Ryan errors too.
> I tried hosting with vllm/vllm-openai:v0.29.0 on the same args given and it works !


**** (2026-10-15 02:18, 0 votes)
Same here. Our 31B bundle scored, but switching it to 12B fails with "Notebook Threw Exception", with or without a LoRA:

- 57049421: 31B, no LoRA → scored (0.18)
- 57106464: same bundle, 12B, no LoRA → Notebook Threw Exception
- 57180129: same bundle, 12B + LoRA (r=16) → Notebook Threw Exception

The 12B runs fine locally with the current wheelhouse.


---

## OOD-45: 45 post-release tasks to check if your agent's local score carries over
/competitions/gemma-4-developer-agent/discussion/750573 | by  | posted 2026-10-18 23:45 | last comment 2026-10-18 23:45 | 0 comments | 4 votes


**** (2026-10-18 23:45, 4 votes)
Tuning on the 129 public tasks tells you little about unseen repositories, so I built a held-out split: 45 bug fixes from 17 Python projects, merged after the Gemma 4 release, in the swegemma format.

Two things I found while validating it that may affect your local numbers:

- In a Kaggle notebook the harness installs no task dependencies: the gold patch resolves only 61 of the 104 public tasks there. The dataset ships a runner that fixes this (gold 44/45 on OOD-45).
- 43 of 45 mined statements carried part of the fix. Each task has the original text and a rewrite as a user report.

Dataset: https://www.kaggle.com/datasets/rodrigospalma/ood45-bugfix-split

Notebook (set `USER_SUBMISSION_DIR` to your submission): https://www.kaggle.com/code/rodrigospalma/ood45-evaluate-your-agent

Feedback and bug reports welcome.


---

## Scorer test environment: published image resolves 0/64 fastapi reference patches
/competitions/gemma-4-developer-agent/discussion/750509 | by  | posted 2026-10-18 16:27 | last comment 2026-10-18 16:27 | 0 comments | 0 votes


**** (2026-10-18 16:27, 0 votes)
Which test environment does the scorer use? On the public tasks, the published image resolves the
reference patch on 0 of 64 fastapi tasks (dirty_equals / typing_inspection missing), while a fully
pinned environment resolves 107/129. Are hidden-task tests run with the repository's pinned test
dependencies?


---

## Notebook threw exception errors 😭😔
/competitions/gemma-4-developer-agent/discussion/750493 | by  | posted 2026-10-18 14:46 | last comment 2026-10-18 14:46 | 0 comments | 0 votes


**** (2026-10-18 14:46, 0 votes)
"My submission failed with 'Notebook Threw Exception'. The zip is byte-identical to my previous successful run. This is a Kaggle backend failure (as confirmed in Discussion 744807). Please rerun my submission or reset my daily allowance. I shouldn't be penalized for a platform outage."


---

## budget warning from harness - can it be given for all tool responses?
/competitions/gemma-4-developer-agent/discussion/750490 | by  | posted 2026-10-18 13:57 | last comment 2026-10-18 13:57 | 0 comments | 0 votes


**** (2026-10-18 13:57, 0 votes)
Currently, there is an automatic budget warning appended to tool responses when 80% of the tool budget is consumed. This is a very thoughtful feature in the harness that helps agents to become time conscious. 

However, the warning is based only on tools consumed and not time. For difficult issues, some times 80% of time is consumed in first 30% of the tool calls but agents does not get a budget warning.

This feature has a tremendous impact that we have to decide on the tool budget so that agents get warning at right time - this is not always easy or feasible or efficient. 

Though get_status is available, even if agents are instructed to invoke get_status periodically, they ignore that instruction most of the time.

@ryanholbrook, is it possible to make the harness give budget warning for every tool response from the very start OR provide also a time-based budget warning at 80% of time budget (apart from tool basis)?


---

## Can we send released task data to DeepSeek's API for training? (Rule 2.4(b))
/competitions/gemma-4-developer-agent/discussion/746251 | by  | posted 2026-10-06 16:12 | last comment 2026-10-18 07:07 | 1 comments | 0 votes


**** (2026-10-18 07:07, 0 votes)
@ryanholbrook on 18 Oct we ran an open-weight model (Qwen3-Coder, Apache 2.0) through OpenRouter on the public tasks in the official harness, restricted to providers that do not retain or train on data. No reference patches or tests were sent. Is this permitted under rule 2.4(b)?
Until we hear back we are not using the resulting trajectories.


**** (2026-10-06 16:12, 0 votes)
Following up on [this topic](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742807) with a question about sending task data.

I'd like to use DeepSeek's API to attempt the released tasks (tasks.jsonl), then train a Gemma LoRA on verified attempts. This means sending task descriptions, harness prompts, repo code and tool outputs to DeepSeek, but no reference patches or verification tests. Is that allowed under rule 2.4(b)? The final submission runs fully offline with Gemma.


---

## Can't submit for more than a day
/competitions/gemma-4-developer-agent/discussion/749090 | by  | posted 2026-10-13 23:43 | last comment 2026-10-18 06:46 | 3 comments | -1 votes


**** (2026-10-13 23:43, -1 votes)
As somehow submission check still ongoing for more than 24 hours, I couldn't submit other predictions. It in worst-case scenario should be abandoned after 12h, isn't it? 
Did anyone else experienced the same problem? Any ideas how it can be solved?


**** (2026-10-18 06:46, 0 votes)
is this issue still going on??


**** (2026-10-14 06:57, 0 votes)
Currently, your submissions will be queued for more than 12 hours.


**** (2026-10-14 01:18, 0 votes)
I have encountered exactly the same thing.


---

## How are the embeddings in embeddings/ generated?
/competitions/gemma-4-developer-agent/discussion/748801 | by  | posted 2026-10-13 05:06 | last comment 2026-10-17 21:02 | 2 comments | 3 votes


**** (2026-10-13 05:06, 3 votes)
The data page describes the .npz files as 256-d “dense semantic vector features” per graph node, used by search_similar_code. Could you share how they were produced, so participants can generate matching embeddings for other repositories ?

Specifically:

Which model or method (a text/code embedding model, or a graph method such as node2vec)?
What input per node (the text field, the name, both, a prompt prefix)?
Any post-processing: truncation to 256 dims, normalization, centring?


**** (2026-10-17 21:02, 0 votes)
Update, for anyone interested in this:

I have tried Gemma embeddings, newest ones too, and I can't get any closer than 50% match on the existing embeddings.


---

## Could the 12 h be one budget for the whole run, instead of a per-task cap?
/competitions/gemma-4-developer-agent/discussion/749597 | by  | posted 2026-10-15 14:59 | last comment 2026-10-17 18:15 | 5 comments | 2 votes


**** (2026-10-15 15:04, 2 votes)
Hi @vaibhavnakrani,

Thanks for bringing this up. Naively setting unfinished tasks to 0 could lead to inconsistent results on the public and private leaderboards. I will try to think of other ways we could allow teams to better utilize the 12 hours, though.


> **** (2026-10-15 19:33, 0 votes)
> Hi @ryanholbrook 
> 
> I think a good way might be adding a tool that will return the remaining time. Hope this helps!


> > **** (2026-10-17 18:15, 0 votes)
> > already exists
> > 
> > https://www.kaggle.com/competitions/gemma-4-developer-agent/overview#:~:text=/workspace.-,get_status,-()%20%2D%3E%20str%20%2D%20Returns%20live


> **** (2026-10-16 07:17, 0 votes)
> Why not change the metric to give also weightage to the time taken to fix an issue while also giving more overall time for the tasks?


> **** (2026-10-17 09:12, 0 votes)
> thanks, appreciate it.


**** (2026-10-15 14:59, 2 votes)
Hi @ryanholbrook ,

Quick idea on the time limit.

Right now the only safe way to stay under 12 h is to give every task about 6 minutes, because each task's clock is independent and going over errors the whole submission. But tasks are very uneven. In our local runs half of them finish in 2–3 minutes and the ones that take 8–15 are often the ones we end up solving. With a 6-minute cap we lose around 45% of our solves, while a lot of the 12 hours sits unused on the easy tasks.

What I'd love is for the 12 h to be the only limit: let the agent spend it however it needs, and if the run doesn't get to the last few tasks, score those as 0. You mentioned in #745805 that you were reconsidering the "unfinished tasks = 0" change. With that in place, teams could drop the per-task cap and just optimize total time, which is also much easier to measure offline (it's a sum of tokens and tool calls, same on any GPU).

Would that be doable?

Thanks for all the work on this.


---

## vLLM Startup Fails with Python 3.13 Binary Incompatibility
/competitions/gemma-4-developer-agent/discussion/745699 | by  | posted 2026-10-03 19:03 | last comment 2026-10-17 13:35 | 3 comments | 4 votes


**** (2026-10-03 19:03, 4 votes)
I’m getting a ServerStartupError when starting the vLLM server in the Gemma 4 Developer Agent competition environment.

Link: https://www.kaggle.com/code/ryanholbrook/getting-started-gemma-4-developer-agent/notebook

The error is:

ImportError: .../vllm/_C.abi3.so: undefined symbol: _ZN3c1013MessageLoggerC1EPKciib

My environment is using Python 3.13.15 and vLLM 0.19.1 from the competition wheelhouse.

It looks like there may be a compatibility issue between the vLLM wheel, PyTorch, and Python 3.13.

Could someone please confirm whether the competition is expected to run on Python 3.12 or lower, and if so, how we can use that Python version in Kaggle?


**** (2026-10-17 13:35, 0 votes)
You should copy the notebook and pin the original environment in your Kaggle session. This will ensure it runs on Python 3.12.13; otherwise, the environment wheels and Gemma won't work correctly.

Make sure to only edit that copied notebook to add your models, datasets, or whatever else you need. If you create a new notebook and manually attach the competition data, it will default to Python 3.13.15, which causes the exact issue you are facing.


**** (2026-10-17 13:28, 0 votes)
I am stuck with same issue, any solution please?


**** (2026-10-16 23:21, 0 votes)
Yes def python 3.12 at least 5 wheels depends on it. 
You won't get past step 1 in the guide notebook otherwise.


---

## [Observation] Pytest 8 Incompatibility with Legacy `httpbin` Fixture in `psf/requests` Tasks
/competitions/gemma-4-developer-agent/discussion/750253 | by  | posted 2026-10-17 13:22 | last comment 2026-10-17 13:22 | 0 comments | 0 votes


**** (2026-10-17 13:22, 0 votes)
Hello everyone (cc: @Ryan Holbrook, @Dustin, @Elan Markowitz, @Ashley Oldacre),

While evaluating my agent's performance on some of the earlier tasks (specifically targeting `psf/requests`, such as `requests_7502`, `requests_7433`, and `requests_7315`), I noticed a recurring evaluation failure that seems to stem from the test environment rather than the agent's generated patch.

I wanted to share this observation in case others are encountering similar false negatives and wondering why their agents are scoring 0.0 despite generating correct code.

### The Observation: Pytest Collection Crash

During Phase 2 verification (Container B), the evaluation harness applies the agent's patch and runs the repository's test suite using **Pytest 8.4.2**.

However, the base commits for several `psf/requests` tasks date back to 2021-2023. In these older versions of the repository, `tests/conftest.py` contains the following fixture definition (around line 34):

```python
@pytest.fixture
def httpbin(httpbin):
    return httpbin
```

While older versions of Pytest permitted a fixture to request a fixture of the same name, **Pytest 8+** throws a fatal collection error when this occurs:
> `E   recursive dependency involving fixture 'httpbin' detected`

Because this crash happens during test collection, the test suite aborts before any of the actual tests can run to verify the agent's patch. Consequently, the evaluator records a non-zero exit code and marks the task as `resolved=False` (`exit_code=1`), even if the agent generated the exact character-for-character Gold Patch.

### Anti-Tampering Reset Constraints

An intuitive workaround might be to instruct the agent to edit `tests/conftest.py` to fix the fixture name collision during its run. 

However, as outlined in the `swegemma` harness documentation (under the "Anti-Tampering Test & Config Reset" section), any modifications made by an agent to protected test files or runner configurations (including `conftest.py`) are forcefully reverted to the `eval_baseline` state via `git checkout HEAD` before Phase 2 verification begins. Therefore, a prompt-engineered fix to the test file cannot survive into the final scoring phase.

### Takeaway

If you are seeing consistent test failures (Exit 1) on older `psf/requests` tasks, it may be worth checking your agent's traces or the `test_outputs/` logs. If your agent is generating the correct code but failing on the `httpbin` dependency, the issue is likely this environment mismatch, not a flaw in your agent's logic.

I hope this saves some troubleshooting time for anyone analyzing their agent's performance on these specific tasks!


---

##  Does patch verification include existing regression tests outside test_patch?
/competitions/gemma-4-developer-agent/discussion/750175 | by  | posted 2026-10-17 04:50 | last comment 2026-10-17 04:50 | 0 comments | 0 votes


**** (2026-10-17 04:50, 0 votes)
On the public task `fastapi_15589`, Gemma 4 31B generated this patch 

```
diff --git a/fastapi/dependencies/utils.py b/fastapi/dependencies/utils.py
index 7c6558c69..aec6209b6 100644
--- a/fastapi/dependencies/utils.py
+++ b/fastapi/dependencies/utils.py
@@ -830,6 +830,8 @@ def request_params_to_args(
     for key in received_params.keys():
         if key not in processed_keys:
             if isinstance(received_params, (ImmutableMultiDict, Headers)):
+                if isinstance(received_params, Headers) and default_convert_underscores and "_" in key:
+                    continue
                 value = received_params.getlist(key)
                 if isinstance(value, list) and (len(value) == 1):
                     params_to_process[key] = value[0]

```

It passes all 7 designated verification tests and receives resolved=True using the grader from `swegemma==0.2.11`. However, running the existing repository suite shows 2 regressions: the original snapshot passes 3,129 tests, while the patched version passes 3,127 and fails 2.

Is verification intentionally limited to the test files selected by `test_patch`, or does hidden-set scoring also run additional regression tests?


---

## Notebook Timeout
/competitions/gemma-4-developer-agent/discussion/750169 | by  | posted 2026-10-17 04:02 | last comment 2026-10-17 04:02 | 0 comments | 0 votes


**** (2026-10-17 04:02, 0 votes)
Two versions of my same notebook got timed out, is this happening with everyone or my notebooks are hitting the 12 hour window? Can anyone help?


---

## How to package and resolve custom Python tools in submission.zip given adk-submission's closed ToolRegistry?
/competitions/gemma-4-developer-agent/discussion/743573 | by  | posted 2026-09-26 08:40 | last comment 2026-10-16 20:38 | 3 comments | 1 votes


**** (2026-09-26 08:40, 1 votes)
Hi everyone and the competition organizers,

The competition overview states:
> *"You must provide a zip archive (submission.zip) that contains your Agent Config, comprising system prompts, **custom tools**, skills, and LoRA adapters. An agent.yaml file must be located at the root of the archive."*

However, in `HARNESS_README.md` (Section 2.1 — Declarative-Only Security Model), it states:
> *"Competitors **do not** submit Python code entrypoints (`agent.py` or `agent_fn`). Standard ADK's `from_config()` permits arbitrary dynamic Python imports; **`adk-submission` replaces it with a sandboxed YAML compiler (`compile_submission`). All agents, sub-agents, workflows, tools, and generation parameters are declared in YAML and resolved against closed host registries (`ToolRegistry`, `ModelRegistry`, `SkillRegistry`, `CallbackRegistry`). `importlib` is never used**."*

Furthermore, Section 6 specifies that `SwegemmaContext.create_tools()` only registers **9 built-in tools** into `ToolRegistry` (`run_command`, `submit_patch`, `read_file`, `edit_file`, `write_file`, `get_status`, and 3 code graph tools).

This creates an important technical question regarding custom tools:

1. **How should a custom Python tool function be packaged and registered?**
   If we write custom tools in Python (for example, AST-based symbol extractors, specialized symmetric diff patchers, or token-capped search utilities) under a `custom_tools/` or `tools/` folder in `submission.zip`, how can they be registered into `ToolRegistry` if `importlib` is disallowed? What is the expected YAML declaration syntax in `agent.yaml` to bind a custom tool file/callable?

2. **Is "custom tools" strictly intended as `AgentTool` (sub-agents)?**
   In the schema, `agent_tool: {config_path: ..., skip_summarization: true}` wraps a sub-agent as a tool. Does the mention of "custom tools" in the rules refer solely to sub-agents wrapped as `AgentTool`, or is there a supported path for standalone Python tool functions?

3. **Running inside Sandbox vs Host:**
   If standalone custom tool functions cannot run on the Host, the only alternative is invoking them inside the sandbox container via `run_command` (e.g. `python3 /path/to/tool.py ...`). However, this incurs substantial token bloat (bash escaping, quoting, and process overhead) compared to direct native tool calling, which heavily impacts the 12-hour evaluation budget.

Could the organizers provide a minimal schema example or demo snippet showing how a custom Python tool is expected to be declared in `agent.yaml` and resolved during evaluation?

Thank you for your support and clarification!


**** (2026-10-16 12:49, 0 votes)
@ryanholbrook 

Quick clarification on the mechanics so we can wire this correctly:
                                                                                                                                                                      
When a skill directory contains a .py script (e.g. skills/test-discovery/find_tests.py), what is the exact absolute path at which it lands inside the sandbox  (Container A), and  **how is the agent expected to discover that path at runtime** — is it a fixed convention (e.g.  skills/<name>/<file>.py), an environment variable set by the harness, or something surfaced via SKILL.md content? A one-line example of the resulting run_command the agent would issue would help understand this.

Thanks!


> **** (2026-10-16 20:38, 0 votes)
> Your agent will discover them automatically per the [ADK skills feature](https://adk.dev/skills/#system-instructions-for-using-skills).


**** (2026-09-26 11:38, 0 votes)
Include them as scripts in a skill. They will be available in the sandbox and your agent can execute them there.


---

## How are you generating high-quality training data
/competitions/gemma-4-developer-agent/discussion/748756 | by  | posted 2026-10-13 01:22 | last comment 2026-10-16 15:28 | 7 comments | 5 votes


**** (2026-10-13 01:22, 5 votes)
Hi everyone!

I’m currently exploring how to generate high-quality training data. One challenge I’ve been thinking about is that having a correct patch doesn’t necessarily tell us how an agent should navigate the repository, select tools, or decide what to do next. I’m considering several approaches:

- LLM-generated trajectories: Using stronger models as teachers.
- Programmatic supervision: Deriving training signals from reference patches, repository graphs, and tests.
- Graph RL: Learning navigation policies through exploration, rewards, or expert feedback.

I’d really appreciate any insights.

Thanks!


**** (2026-10-14 02:13, 4 votes)
I think both rejection-sampled traces from the Gemma model + a few stronger teacher distills can make the model less verbose and self-doubting. Then we do RL on the SFT checkpoint to improve solving accuracy that's our team's plan.


> **** (2026-10-15 14:08, 0 votes)
> Rejection-sampled Gemma trajectories combined with stronger teacher distillation is a solid approach. I'm curious about is trajectory quality. A successful patch doesn't necessarily mean the agent took an efficient path through the repository. Are you planning to use primarily outcome-based rewards (e.g., tests passing), or also process-level rewards for intermediate decisions like file selection and tool usage?


**** (2026-10-13 20:10, 0 votes)
I am also trying to understand this. One thing i thought about is using gemma 31 B  model in the harness and generate the data and obvio for fine tuning i am planing to do all my initial exp on smaller model  but the issue over here is i am unable to get what to do if 31B model doesn't solve a lot of task which is actually possible, also online rl in the provided env is i dont think so possible so afaik there is only one way that is generate trajectories, the rejection and then fine tuning. PLZ enlighten me if I am wrong.


> **** (2026-10-15 14:13, 1 votes)
> I agree that generating trajectories, filtering successful ones, and then doing SFT is a strong baseline. My concern is that this creates a bottleneck, which if the 31B teacher can't solve a task, we may end up wasting training signals. I also think that full online RL inside the competition harness seems difficult, but I think we can optimize a navigation policy offline using graph-based rewards without requiring the 31B model to solve every task first.


> > **** (2026-10-15 15:15, 0 votes)
> > i don't think we would be able to use graph based tools to a large extent. In another discussion i read that a lot of graph tools are not that great, i am also planning to do some experiments to check if graph based tools are good or not. 
> > take a look at this discussion https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742911 
> > Also could you plz explain me how can we optimize graph based trajectories?


> > **** (2026-10-16 15:28, 0 votes)
> > this is a huge take away, worth creating this discussion post, thank you. the optimization i was talking about is to use reference patches as supervision. we can identify the relevant files/functions, generate candidate navigation paths through the repository graph, and reward trajectories that reach those targets with fewer tool calls.


---

## Request: publish top-agent episode/replay datasets (as in Orbit Wars / Pokémon TCG)
/competitions/gemma-4-developer-agent/discussion/749953 | by  | posted 2026-10-16 14:43 | last comment 2026-10-16 15:02 | 1 comments | 0 votes


**** (2026-10-16 15:02, 1 votes)
Hi @astraeusdotdev,

It's an interesting idea! And you're right that while we do publish replays for agents in our simulation competitions, there's nothing similar for traditional competitions. Unfortunately, I don't think this will be possible, at least for this competition, since publishing the replays on the test set would also publish significant parts of the test set itself. (In fact, someone could use published traces to intentionally exfiltrate all or most of the test data.)

I do like the idea though. Perhaps something similar could work with a different setup.


**** (2026-10-16 14:43, 0 votes)
Would the team consider publishing periodic episode/replay datasets for top-performing agents, like the staff-published daily episode datasets in Orbit Wars ("Orbit Wars top-10% daily episode replay datasets") and the Pokémon TCG AI Battle Challenge ("Daily Top Episodes Datasets")?

The public episodes endpoint returns "No episodes found" for leaderboard submissions, so there's currently no way to study how the strongest agents actually solve tasks. Trajectories from top agents would enable imitation learning, strategy analysis, and much stronger post-competition writeups — and there's clear community appetite for it (several threads on training-data generation are active right now).

Even a weekly top-10% snapshot, or a post-competition full dump, would be hugely valuable to everyone working on agent quality here. Thanks for considering!


---

## Distribution of best public score per team, teams that submitted in the last 7 days (n = 1,860)
/competitions/gemma-4-developer-agent/discussion/749955 | by  | posted 2026-10-16 14:46 | last comment 2026-10-16 14:48 | 1 comments | 0 votes


**** (2026-10-16 14:48, 0 votes)
idea from @bgalbraith comment in a discussion


**** (2026-10-16 14:46, 0 votes)
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F14047490%2Fdd403e98fb917feda76f98409206e05d%2Fleaderboard_histogram_last7d.png?generation=1792161798846316&alt=media)


---

## Kaggle Gemma vs Openrouter Gemma
/competitions/gemma-4-developer-agent/discussion/749801 | by  | posted 2026-10-16 02:13 | last comment 2026-10-16 11:29 | 1 comments | 2 votes


**** (2026-10-16 02:13, 2 votes)
The Openrouter Gemma 4 inference is quite fast compared to Kaggle Gemma.

I spent one week working with Openrouter Gemma 4 model fine-tuning the agent deck for time and tool call budget. But all became a waste when I shifted for submission purpose to GPU based Kaggle Gemma - the model is significantly slow that none of the tasks could complete! All my elaborate agent configurations gone waste!😀

The five minute time cap for each task is making it very difficult to explore different techniques. However ,with openrouter based inference, I could test several as evenn a minute matters a lot.

If the competition objective is to create innovative and efficient techniques for small and medium sized models to  provide comparable performance to frontier models, then this time handicap should be addressed. With just 5 minutes, not much can be done, which forces LoRA finetuning as a possible required method which may not be necessary if more time is available for inference per task. 

One way is to allow more time for the 120 tasks but make the metrics take into account the time taken per task. 

For those interested in testing with kaggle vs gemma - here is the notebook:

https://www.kaggle.com/code/murugesann/gemma-4-developer-agent-local-testing


**** (2026-10-16 11:29, 0 votes)
To make progress on the leaderboard, you need a controlled, repeatable experiment. In other words, you need the exact same evaluation system as the organizers. The fact that your tasks run faster on OpenRouter does not mean they will execute with the same speed within the testing system. Essentially, your RFT on such trajectories will be biased  because you won't be filtering out "bad" trajectories that timed out.


---

## Supported isolation backend for Kaggle notebook development
/competitions/gemma-4-developer-agent/discussion/749743 | by  | posted 2026-10-15 21:53 | last comment 2026-10-16 02:14 | 1 comments | 0 votes


**** (2026-10-15 21:53, 0 votes)
I want to run controlled development experiments on Kaggle’s L4×4 GPUs while keeping reference patches, verification tests and held-out tasks inaccessible to the solving agent.

In my tested runtime, Docker and its daemon socket are absent, Bubblewrap is absent, and user namespace creation fails with EPERM.

Is there an officially supported sandbox executor or sanitized development-only notebook template that retains L4×4 access? If so, could you share the exact setup?


---

## Clarification on Using Claude/GPT-Generated Trajectories for Training
/competitions/gemma-4-developer-agent/discussion/749585 | by  | posted 2026-10-15 14:05 | last comment 2026-10-15 15:05 | 1 comments | 0 votes


**** (2026-10-15 15:05, 3 votes)
Even though you are not building a competing model, you would be generating outputs for the purpose of training, which is basically distillation and its against their TOS.


**** (2026-10-15 14:05, 0 votes)
Hi organizers,

I'd like to clarify whether using outputs from models such as Claude or GPT to train Gemma 4 is considered acceptable in this competition.

Specifically, I'm considering generating code-fixing trajectories (e.g., tool calls, reasoning steps, code edits, and patches) using Claude or GPT, and then using them to fine-tune Gemma 4.

I'm aware of the following restrictions and exceptions:

- [Anthropic's Commercial Terms (Section D.4)](https://www.anthropic.com/legal/commercial-terms) prohibit using their services to develop competing products or AI models.
- [Anthropic's official FAQ on training AI models](https://support.claude.com/en/articles/12326764-can-i-use-my-outputs-to-train-an-ai-model) explicitly allows training non-competing specialized models, although it also lists certain uses of outputs as training targets among prohibited activities.
- [OpenAI's Services Agreement (Section 3.3(e))](https://openai.com/policies/services-agreement/) similarly restricts the development of competing AI models, with certain permitted exceptions.

Since this competition focuses on developing a task-specific coding agent rather than a general-purpose LLM, **I'm inclined to think this approach could be permissible**, although I understand that coding agents may overlap with the providers' own products.

Was this type of training approach anticipated by the organizers when designing the competition?

And would using Claude/GPT-generated trajectories for fine-tuning be acceptable under the competition rules, assuming compliance with the respective model providers' terms?

I'd appreciate any official guidance or clarification on this.

Thanks!


---

## Getting Started notebook fails: wheelhouse is cp312 but environment is Python 3.13 / torch 2.11
/competitions/gemma-4-developer-agent/discussion/749505 | by  | posted 2026-10-15 06:43 | last comment 2026-10-15 14:09 | 1 comments | 1 votes


**** (2026-10-15 06:43, 1 votes)
Hi organizers and everyone,

I can't run the official Getting Started notebook in a fresh notebook. Section 1 (wheelhouse install) fails before anything else runs.

What I see:
- Environment setting: "Pin to original environment (2026-10-03)"
- Python: 3.13.15
- torch: 2.11.0+cu128 (preinstalled)
- Competition data, the gemma-4-developer-agent-wheelhouse dataset and the Gemma 4 models are all attached.

Error from the install cell:
ERROR: apache_tvm_ffi-0.1.13.post3-cp312-cp312-manylinux_2_24_x86_64.manylinux_2_28_x86_64.whl is not a supported wheel on this platform.

I checked every wheel in the wheelhouse against this Python. 32 are usable and 9 are cp312-only: apache_tvm_ffi, cbor2, ijson, msgspec, nvidia_cudnn_frontend, outlines_core, pybase64, setproctitle, xgrammar.

Second problem: the vllm wheel in the wheelhouse requires torch==2.10.0 (plus torchvision 0.25.0 and torchaudio 2.10.0), but the image has torch 2.11.0. vllm and swegemma are not installed in the image.

The saved outputs of the official notebook show Python 3.12 paths (/usr/local/lib/python3.12/dist-packages), so it looks like the notebook environment now differs from the one the wheelhouse was built for. The system also has /usr/bin/python3.12 (3.12.3), but it has no pip or torch, so I can't use it.

Questions:
1. Is there an environment setting or notebook version that gives Python 3.12 and torch 2.10 for this competition?
2. Will the wheelhouse be rebuilt for Python 3.13 / torch 2.11, or will the environment be fixed?
3. Is there a recommended way to test submissions locally in the meantime?

Note: I checked this on a session with Accelerator set to None; I haven't confirmed whether the L4 x4 image differs.

Thanks!


**** (2026-10-15 14:09, 0 votes)
Try starting from a direct fork of the Getting Started notebook. It should still be pinned to the original Python 3.12 image.


---

## LoRA adapter loads and is served, but has no effect on outputs (current wheelhouse, 4×L4) – repro inside
/competitions/gemma-4-developer-agent/discussion/749528 | by  | posted 2026-10-15 08:52 | last comment 2026-10-15 13:44 | 1 comments | 1 votes


**** (2026-10-15 08:52, 1 votes)
Hi @ryanholbrook and everyone,

I tested whether a LoRA adapter actually changes the model's output on the current setup, and it looks like it doesn't. Sharing a minimal repro in case it helps others who are planning to train adapters.

Setup
- Kaggle notebook, GPU L4 ×4, latest Gemma 4 Developer Agent Wheelhouse (as of Oct 14), gemma-4-31b-it-qat-w4a16-ct v2
- Server started exactly like the Getting Started notebook: VllmServer + discover_adapters(<submission root>), VllmConfig with tensor_parallel_size=4, max_model_len=32768, gpu_memory_utilization=0.90, enable_lora=True, max_loras=8, max_lora_rank=128

Test
1. Copied sample_submission and replaced BOTH lora_A and lora_B in adapters/main_lora and adapters/tool_lora with random noise ~N(0, 0.5). Keys look like base_model.model.model.language_model.layers.0.self_attn.o_proj.lora_A.weight (rank 4, layer 0 o_proj, same as the sample).
2. /v1/models lists all three: the base model path, main_lora and tool_lora, so the adapters are registered.
3. Sent the same chat request to each model id: "List the first ten prime numbers.", temperature=0, max_tokens=40, logprobs on.

Result
- All three return the identical text: 2, 3, 5, 7, 11, 13, 17, 19, 23, 29
- First-token logprobs only differ at the ~1e-5 level (e.g. base -7.4e-06 vs main_lora -3.7e-05 vs tool_lora -2.3e-05), which looks like numerical noise. With N(0, 0.5) noise in both A and B, a working LoRA path should change the output completely.
- Good news: with the adapters attached, an ~18k-token prompt completed in 13 s, so the earlier KV-cache hang (#744331) seems fixed.

This matches what @Fawad07 reported in #743508 (weights loaded but not used in the forward pass). [I'm also running the same test with a random rank-8 adapter on q_proj + o_proj of ALL 60 layers – will update this post with the result.]

Questions
1. Can you reproduce this? Is the scoring environment using the same vLLM build, and does a LoRA adapter currently change outputs in scored runs?
2. Is there a known-good adapter (or a test notebook) that demonstrably changes outputs, so we can verify our adapter format before spending GPU hours on training?
3. If this is a known issue, is there an ETA for a fix?

This matters a lot because LoRA is the only form of post-training allowed, and the GPU quota makes it expensive to train an adapter that might be ignored at scoring time.

Thanks!


**** (2026-10-15 13:44, 0 votes)
Hi @anantsharma25,

Here is my agent's analysis. tl;dr is that the adapters are being applied correctly. You probably just need to apply an adapter to more layers to see a change in outputs. The sample submission just applies it to layer 0.

---

Good news: **your logprob numbers actually confirm that your LoRA adapters are loaded and active in the forward
  pass**, and the scoring environment uses the exact same patched vLLM 0.19.1 wheelhouse.

Here is why replacing `lora_A` and `lora_B` in `sample_submission` with $\mathcal{N}(0, 0.5)$ (or even
  $\mathcal{N}(0, 100)$) only changes the top-1 logprob from `-7.4e-06` to `-3.7e-05` without changing the greedy
  text:

### 1. Why `-7.4e-06` vs `-3.7e-05` vs `-2.3e-05` is a ~1.6-unit raw logit shift (not numerical noise)
At `temperature=0`, vLLM greedy decoding is bit-for-bit deterministic (`0` difference across runs when weights are unchanged). The reason the shift looks like `~1e-5` on the top token `"2"` is **softmax saturation**:
- `logprobs` returns $\ln \text{softmax}(z)_1$, not the raw logit $z_1$.
 - When $p_1 \approx 1 - 7.4\times 10^{-6} = 0.9999926$, the logit margin between `"2"` and the runner-up token
  is $z_1 - z_2 \approx -\ln(7.4\times 10^{-6}) = \mathbf{11.81}$.
- With `main_lora` ($\ln p_1 = -3.7\times 10^{-5}$), the logit margin drops to $-\ln(3.7\times 10^{-5}) =
  \mathbf{10.20}$ — a **1.61-unit shift in the raw logits** (and a **5×** change in $1 - p_1$).
- With `tool_lora` ($\ln p_1 = -2.3\times 10^{-5}$), the logit margin shifts to $\mathbf{10.68}$ (**1.13 raw
  logit units**).
- Because $\frac{\partial \ln p_1}{\partial z_1} = 1 - p_1 \approx 10^{-5}$ when $p_1 \approx 1$, an $O(1)$ shift in raw logits looks like $O(10^{-5})$ on the top-1 logprob, while the runner-up token logprobs (`top_logprobs=5`) shift by the full ~1.1–1.6 nats.

### 2. Why large random weights in `sample_submission` don't blow up the output
`sample_submission/adapters/main_lora/adapter_config.json` is a minimal 1-layer smoke-test stub with `"layers_to_transform": [0]` and `"target_modules": ["q_proj", "o_proj"]` — it only contains weights for **Layer 0** out of **60 layers**.

Unlike Llama/Qwen (where `o_proj` is added directly to the residual stream, so multiplying Layer 0 `o_proj` by a large number explodes the residual stream), **Gemma 4 uses Sandwich-RMSNorm + Q-RMSNorm**:
1. Immediately after `qkv_proj`, `q` passes through per-head `self.q_norm` (`RMSNorm`).
2. Immediately after `o_proj`, the attention output passes through `self.post_attention_layernorm` (`RMSNorm`)
**before** being added to `residual`:
       ```python
       hidden_states = self.self_attn(positions=positions, hidden_states=hidden_states, **kwargs)
       hidden_states = self.post_attention_layernorm(hidden_states)
       hidden_states = hidden_states + residual
       ```


---

## It's been 3 days since i started i am still doing the pre prep.
/competitions/gemma-4-developer-agent/discussion/749510 | by  | posted 2026-10-15 07:08 | last comment 2026-10-15 07:09 | 1 comments | 0 votes


**** (2026-10-15 07:09, 0 votes)
did 3 trace analysis and prompt engineering runs. minimal gains so far.


**** (2026-10-15 07:08, 0 votes)
wish i started earlier. so measuring what local timings look like on kaggle sub is v imp in this comp. then the data had to be ran through ( many caveats and weird edge cases here ), baseline on my 5090 local ( i can do 3 agents in parallel before it starts diminishing the gains ) and scoping what external gpu's that is the best bang for buck and also available to rent. 

every measure needs 2 runs because run noise is on the higher side so 2 seed. setting up tracing infra so its easier to analyze stuff. 🤡


---

## Notebook threw exception error - LoRa
/competitions/gemma-4-developer-agent/discussion/749501 | by  | posted 2026-10-15 05:44 | last comment 2026-10-15 05:44 | 0 comments | 0 votes


**** (2026-10-15 05:44, 0 votes)
Stuck at a problem when submitting with  LoRa it always shows this error "Notebook Threw Exception". Submissions without lora runs and scores well. Anybody who is submitting LoRa and scoring , can you tell any solution or your setup for LoRa?


---

## Reference patches failing in the starter notebook — is this expected?
/competitions/gemma-4-developer-agent/discussion/749439 | by  | posted 2026-10-14 22:03 | last comment 2026-10-14 22:03 | 0 comments | 1 votes


**** (2026-10-14 22:03, 1 votes)
I've been working on my agent and testing it using the official starter notebook and swegemma evaluator. I noticed some unexpected failures and wanted to check whether I'm missing something in the setup.

To investigate, I ran 12 training tasks using their reference patches , without changing the evaluator or test logic.

**Only 4 out of 12 reference patches passed.** The other 8 failed for reasons that seem related to the evaluation environment rather than the solutions themselves.

Here's findings:

- **FastAPI (2 tasks):** Missing `inline_snapshot` dependency.
- **Requests (2 tasks):** Missing `pytest-httpbin` dependency.
- **Requests (2 tasks):** Tests import the system-installed `requests` instead of the repository code.
- **HTTPX (1 task):** Tests import the system-installed `httpx` instead of the repository code.
- **Rich (1 task):** The installed IPython/Pygments packages affect the expected test result.

I'm using the same subprocess sandbox, Kaggle image and wheelhouse as the official starter notebook. From looking at the swegemma code, it seems the subprocess sandbox skips some package and dependency installation steps that the Docker version handles.

I have a few questions:

1. Does the actual competition scoring use the same environment as the starter notebook?
2. Is it expected that some training tasks fail even with their reference patches?
3. Is there a recommended way to handle these dependency and package import issues while keeping evaluation consistent with official scoring?
4. I also noticed a reference to gemma4swe-wheelhouses but I can't access. Is that dataset supposed to be available to participants?

I want to make sure I'm evaluating my agent correctly rather than spending time trying to fix issues that might just be related to the environment.

Happy to share my diagnostic notebook and logs if that helps.

Thanks


---

## Compaction can't trigger at token_threshold 32,768, and overflow then discards the patch (follow-up to #743456)
/competitions/gemma-4-developer-agent/discussion/744692 | by  | posted 2026-09-30 19:34 | last comment 2026-10-14 17:00 | 5 comments | 3 votes


**** (2026-10-14 11:04, 0 votes)
Following up on the compaction question above — it is still the one thing we cannot
determine from the public artifacts, and it decides whether a solved task can score zero.

What we can verify from our side: the harness README (Sep 25 update) lists
compaction_interval = 5 / token_threshold = 14,336, the notebook template uses
token_threshold = 14,336, and the generation defaults bound max_output_tokens at 32,768
with a default of 16,384 — i.e. HALF the 32,768 context window. Since the compaction
processor compares the PREVIOUS prompt's token count, a single large response can cross
the window before compaction ever gets a chance to fire.

Two narrow questions, one line each:

1) Which token_threshold does the scoring run use — 14,336 or the older 32,768?
   (And is compaction_interval 5 or 15?) One number is enough.

2) When the context window is exceeded, is the fallback `git diff` capture still skipped?
   In other words: does a ContextWindowExceededError really cost the task its patch, or
   was that path fixed? A yes/no is enough.

Why we ask, in one line: one participant in this thread measured ~12% of sessions
overflowing at 14,336 and 17–33% at 32,768 — that is a large fraction of tasks whose work
never reaches the grader, and from our side it is invisible (we see a score, not a cause).

Thanks!


**** (2026-09-30 19:58, 3 votes)
Thanks, I will look into it.


> **** (2026-10-01 00:00, 3 votes)
> Any update? Current harness readme says (since sep 25 update).
> 
> >Compaction (EventsCompactionConfig):
> 
> >compaction_interval = 5
> 
> >token_threshold = 14,336
> 
> Which matches public notebook and that's the value I used in local runs.
> 
> But yeah +1 on confirmation. Would be great if you can tell which value scorer matches, updated 14,336 or still 32,768


> **** (2026-10-01 00:23, 1 votes)
> I got the same issue. Wasted a daily submission 😭


**** (2026-09-30 19:34, 3 votes)
Hi @ryanholbrook, following up on https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743456 with evidence from local runs using the official wheels (swegemma 0.2.7, adk-submission 0.2.11, google-adk 1.36.1, vLLM 0.19.1):

Compaction can't fire before the overflow. ADK's compaction processor checks the previous prompt's token count against token_threshold before each model call. HARNESS_README §7.2 lists 32,768 for scoring, but vLLM rejects any request where prompt + max_output_tokens > 32,768, so the prompt never reaches the threshold and the session ends with ContextWindowExceededError. With the getting-started notebook's 14,336, compaction fires and overflows are rare.
The overflow discards the agent's work. ContextWindowExceededError is caught by the generic except Exception in run_agent_sandbox, which skips the fallback git diff capture (only TimeoutError / LlmCallsLimitExceededError reach it). The task scores 0 even when edits were applied: 44 of 44 overflowed sessions had an empty patch, 14 of them after successful edits.
In our runs: about 12% of sessions overflowed at a threshold of 14,336, and 17–33% at 32,768 (depending on max_output_tokens).Compaction can't trigger at token_threshold 32,768, and overflow then discards the patch (follow-up to #743456)

Could you confirm the scorer's token_threshold?


**** (2026-10-14 17:00, 0 votes)
Yes, this compaction question does seem to be a very important one to get an answer for.


---

## Constantly facing "Notebook threw Exception"
/competitions/gemma-4-developer-agent/discussion/749200 | by  | posted 2026-10-14 09:26 | last comment 2026-10-14 15:09 | 4 comments | 1 votes


**** (2026-10-14 15:05, 1 votes)
Hi @nerdayan,

It looks like your submission is failing because the zip contains a Python bytecode cache file (`.pyc`), which are not files accepted by the scorer.

I apologize for the confusing error message. We'll work on improving these. The "Notebook threw Exception" error you're seeing is from the scoring script, which runs in a Kaggle notebook. It was the scoring script that threw the exception when it encountered the `.pyc` file.


> **** (2026-10-14 15:09, 0 votes)
> Thanks!!! really appreciate your clarification.


**** (2026-10-14 09:26, 1 votes)
@ryanholbrook @kagglestaff @elanlearns @herbison II am repeatedly encountering a 'Notebook Threw Exception' error, despite the fact that I have not submitted any notebooks. My submission consists entirely of a submission.zip file containing only configuration files, prompts, and skills, none of which should trigger an execution error. Additionally, I re-ran a previously successful and scored notebook, and it is now throwing an exception as well. I have been unable to progress for almost the past five days due to this issue. I would appreciate your assistance in resolving this. 

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F37104463%2F0642af7a7a2dd0f83226da5b0945ed27%2FScreenshot%202026-10-14%20135335.png?generation=1791968805573771&alt=media)


**** (2026-10-14 10:30, 0 votes)
I am also facing the same situation.


**** (2026-10-14 09:50, 0 votes)
Hi, I got the same issue here sadly :( 
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F17180946%2F11b705377c748d3c2163cc3d74b19266%2FScreenshot%202026-10-14%20at%2011.48.58.png?generation=1791971384640609&alt=media)


---

## Some training tasks can't be solved from the task text alone
/competitions/gemma-4-developer-agent/discussion/748482 | by  | posted 2026-10-12 08:49 | last comment 2026-10-14 14:23 | 2 comments | 3 votes


**** (2026-10-12 08:49, 3 votes)
Was going through my agent's failures on the public tasks and noticed something.

Out of 43 failed tasks, 12 failed because the hidden tests check for something the task description never mentions. The agent's fix was reasonable, it just couldn't have known the exact name or wording.

Two flavours:

1. Tests need a specific name (8 tasks)
- fastapi_15661: task says "Automate release preparation". Test does `from scripts.prepare_release import ...`. My agent made scripts/release.py. Import fails, done.
- fastapi_15280: the whole task text is "Add support for @app.vibe()". Test calls it with a `prompt=` argument that is never mentioned.
- fastapi_15785: test checks for a class called `RouteContext`. That name isn't in the task.

2. Tests need exact wording (4 tasks)
- fastapi_14479: task says "improve the error message". Test wants exactly "Query parameter 'q' must be one of the supported types". My agent wrote "Query param 'q' must be of one of the supported types". Same behaviour, fails anyway.

Makes sense why it happens: the real fix and the tests were written together, so they match. The agent only gets the description.

This is from one run on the public training tasks, so I can't say how much of this is in the hidden test set. Curious if others see the same, and whether the test set was filtered for this.


**** (2026-10-12 10:39, 1 votes)
https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747248#3535945


> **** (2026-10-14 14:23, 0 votes)
> so this means we can have any arbitrary names for functions/classes/scripts and the tests will test the "functionality" of the solution ??


---

## Does hosted ZIP scoring use our weekly GPU quota?
/competitions/gemma-4-developer-agent/discussion/749224 | by  | posted 2026-10-14 11:30 | last comment 2026-10-14 11:34 | 1 comments | 0 votes


**** (2026-10-14 11:34, 2 votes)
Submissions dont use your personal quota


**** (2026-10-14 11:30, 0 votes)
Hi, I'm trying to budget experiments and wanted to check one point.

If I upload `submission.zip` directly, without running a GPU notebook, does the competition's hosted agent evaluation count against my personal weekly Kaggle GPU quota?

The overview says L4x4 notebooks use quota at 2x, and each submission has a 12-hour agent budget. I couldn't find whether those are separate budgets. Could the organizers confirm how direct ZIP submissions are charged, including setup and patch validation?

Thanks!


---

## Hugginface LoRA Adapters or Datasets
/competitions/gemma-4-developer-agent/discussion/749205 | by  | posted 2026-10-14 09:43 | last comment 2026-10-14 09:43 | 0 comments | 0 votes


**** (2026-10-14 09:43, 0 votes)
Can we use LoRA adapters or Datasets from hf for this competition? Are there any restrictions?


---

## Found, not fixed: 38% of default-prompt tasks never edit a source file; an edit deadline turns most into wrong edits
/competitions/gemma-4-developer-agent/discussion/749198 | by  | posted 2026-10-14 09:03 | last comment 2026-10-14 09:03 | 0 comments | 2 votes


**** (2026-10-14 09:03, 2 votes)
**TL;DR.** We read the traces of two practice runs. With the default prompt, 27 of 71 tasks (38%) never changed a source file and none of them was solved, although in 23 of the 27 the agent had already named a file that the reference patch changes. The public Budget-Fit configuration, whose prompt asks for a source edit by the 12th call, cut that share to 13 of 112 (11.6%). But on the 69 tasks both runs attempted, tasks with no source change fell from 25 to 7 while solved tasks rose only from 26 to 30: of N1's 65 unsolved tasks, 51 had an edit applied, 42 of them to a file the reference patch changes.

**Runs** (one run each, Kaggle 4×L4, official evaluator)
- D4: the default prompt with a 4-minute, 40-call budget, 30 Sep build, on the 71 public tasks whose reference patch passes and empty patch fails in the notebook grading setup.
- N1: verracodeguacas' Budget-Fit configuration unchanged (8 minutes, 28 calls), 9 Oct build, on the 112 tasks that discriminate in our rebuild of the scorer's install path.
- The two runs differ in nine ways (prompt, call cap, minutes, command timeout, turns, output cap, sub-agent, tasks, build), so this compares footprints, not effects.

**Definitions.** A source file counts as changed when the edit tool reported the edit as applied or the file is in the final patch; tests and scripts at the repository root do not count. "Named" = a reference-patch path appears in some tool argument. Call positions are counted the way the harness counts its budget.

**Solved / tasks by the call at which the first source edit was applied**

| Run | by the 12th call | 13th–20th | later | none |
|---|---|---|---|---|
| D4 (default prompt, 71 tasks) | 12/21 | 9/14 | 5/9 | 0/27 |
| N1 (Budget-Fit, 112 tasks) | 31/47 | 11/33 | 4/17 | 1/15 |

"none" = no edit applied through the edit tools (two N1 tasks changed source files through shell commands; one was solved). Earlier edits go with more solves, but this is an association: easier tasks may simply be edited earlier.

**Where the no-edit tasks went**
- D4: 4 of the 27 ended when vLLM refused a prompt that no longer fit beside the default 16,384-token output reservation (as dariushafshar showed); 23 ran out of time.
- N1: 8 of the 13 had tried: six first at the 28th or 29th call, two in loops of rejected edit calls (17 and 13 rejections).
- The harness's only budget warning ("Only N tool call(s) remaining … Finalize your edits") starts when 10 calls remain, for caps of 20 or more: at call 90 under the scorer's default 100, at call 30 in D4 (it reached 14 of 71 tasks), at call 18 under Budget-Fit's 28 (71 of 112). Nothing warns about time.

**What we take from it.** The default agent mostly loses tasks by not changing the code it has found, not by failing to find it. Forcing the change early mostly turns that hesitation into wrong edits in the right file, so the open problem is a correct edit, not just an early one.

**Related.** woochangho's "Where Do Budgeted Local Coding Agents Lose?" classifies the losses of two runs on redacted traces; hitarthjain0's "Can Grep Find the Bug?" expected forced early edits to land in the wrong place where lexical search fails (we did not split tasks that way). This is part of the writeup we are preparing for the paper track; the trace helpers are in our kit notebook: https://www.kaggle.com/code/kimdonggyu1255/gemma-4-agent-instruments-kit


---

## Submissions stuck in queue for a long time
/competitions/gemma-4-developer-agent/discussion/745942 | by  | posted 2026-10-05 11:30 | last comment 2026-10-14 07:00 | 2 comments | 2 votes


**** (2026-10-05 11:30, 2 votes)
It's been few hours now since I tried to submit a baseline, and it's still "queued" is this normal?


**** (2026-10-08 07:15, 0 votes)
any resolution to this ?


---

## Same 314 code-graph queries, four wheelhouse builds: results 82 → 11 → 270 → 270 (a CPU replay)
/competitions/gemma-4-developer-agent/discussion/748323 | by  | posted 2026-10-11 14:49 | last comment 2026-10-14 05:56 | 3 comments | 5 votes


**** (2026-10-11 14:49, 5 votes)
**TL;DR.** We kept a copy of every harness build we ran on and replayed the code-graph tool calls recorded in our practice traces through each build, on CPU. The same 314 calls returned at least one result **82, 11, 270 and 270** times. A prompt rule like "don't use the graph tools, they usually return nothing" was right for the 30 Sep build and stopped being right on 8 Oct.

**Method**
- Builds: the wheelhouse wheels as they were before 30 Sep (swegemma 0.2.7), from 30 Sep (still 0.2.7), from 8 Oct (0.2.10) and from 9 Oct (0.2.11). Compare builds by file checksum, not by version: the 30 Sep build changed 10 swegemma `.py` files, 5 of them in the graph code, without bumping 0.2.7.
- Inputs: every `search_similar_code`, `get_code_neighbors` and `get_code_subgraph` call in the traces of nine of our practice runs: 314 calls on 70 public tasks.
- Replay: a fresh interpreter per build with that build's swegemma first on `sys.path`, then `swegemma.tools.graph.<tool>(ctx, **recorded_args)` with a minimal context (task, repo, graph and embedding folders, the 5,000-character output cap), on the competition's `graphs/` and `embeddings/` (no empty files in our copy).
- Check: replaying each run under the build it actually ran on reproduces the recorded outcome (empty or not) for 314 of 314 calls.

**Results (the same 314 calls under each build)**

| Build (swegemma) | .py files changed from the previous build | Calls with results | With a node from a reference-patch file (in top 3) | Median response, characters |
|---|---|---|---|---|
| before 30 Sep (0.2.7) | — | 82 | 30 (22) | 79 |
| 30 Sep (0.2.7) | 10 | 11 | 2 (1) | 94.5 |
| 8 Oct (0.2.10) | 9 | 270 | 122 (87) | 5,763 |
| 9 Oct (0.2.11) | 4, and 2 removed | 270 | 122 (87) | 5,763 |

"With a node from a reference-patch file" = the answer contains a function or class from a file that the task's reference patch changes (in brackets: how many have one in the top 3). Medians are over all 314 calls, empty answers included. The 9 Oct build answers every call exactly as the 8 Oct build.

**What we take from it**
- The graph tools answer most queries again since 8 Oct. Whether that helps solve tasks is a separate question we have not tested: each answer is now about 5,800 characters, and async functions are still missing from the graphs ([#742911](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742911), [#745998](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/745998)).
- A rule derived from tool behaviour lives as long as the build it was measured on. Replaying your own recorded calls on CPU takes minutes after each update.

**Other changes we found by diffing the archived wheels**
- From 8 Oct, `include_thoughts: false` no longer switches thinking off when a thinking budget is set; it only hides the thoughts (first reported in [#747914](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747914)).
- The 8 Oct build drops edits to test files from the submitted patch and prunes the repository listing in the first prompt.
- The 9 Oct build removed `swegemma/models/discovery.py` (and `models/registry.py`). The official starter notebook, pulled today, still runs `from swegemma.models.discovery import validate_single_declared_model`, so notebooks built from it stop at that line on the current wheelhouse. We wrapped the import in `try/except ImportError` and defined the same check on top of `adk_submission.discovery.discover_declared_models`.
- Not a build change, but measured on the same runs: in our run of the public Budget-Fit configuration (9 Oct build, 112 tasks), 105 of 524 edit_file/write_file calls were rejected with "mandatory input parameters are not present", which ADK returns without running the tool. They came from 15 tasks, 6 of which account for 85, mostly by resending a byte-identical call (up to 14 times in a row). In 47 of the 105, pieces of code appear as argument names, so a long code argument lost its boundaries somewhere between the model's output and the parsed call; our traces cannot tell which side. Only 2 of the 105 contained triple quotes. With the default prompt on the 30 Sep build: 16 of 239 calls in 7 of 71 tasks, 6 of which also appear among the 15. samvalladares' Budget-Fit notebook already warns against docstrings in old_string and against resending a rejected call.

**Limits.** One team's queries (314 calls on 70 tasks); only deterministic tool functions can be replayed without a GPU, so model-side changes need paired runs. This is part of a writeup we are preparing for the paper track; the replay script will be released with the rest of our tooling.


**** (2026-10-14 05:56, 1 votes)
Update (14 Oct): a fifth harness build appeared on 12 Oct 19:51 UTC — swegemma 0.2.11 repackaged under the same version number (5 .py files differ from the 9 Oct build: budget, cli, config, context, harness/verification; the test run now has its own 300 s limit). Replaying our 314 recorded code-graph calls through it gives exactly the same outcome as the 8 Oct and 9 Oct builds (270 of 314 with results, 314/314 identical). The kit notebook now names five archived builds by file checksum, so you can check which one is attached: https://www.kaggle.com/code/kimdonggyu1255/gemma-4-agent-instruments-kit
Also: the 13 Oct data re-upload changed file dates only — all 524 competition files kept their sizes, and tasks.jsonl and HARNESS_README.md hash identical to the earlier copies.


**** (2026-10-12 04:25, 0 votes)
Update: the build fingerprint and the replay now run as a public CPU notebook (about 5 minutes, no GPU): https://www.kaggle.com/code/kimdonggyu1255/gemma-4-agent-instruments-kit. It names the attached wheelhouse build by file checksum and replays the 314 calls through it (270 with results on the 9 Oct build). Apache-2.0.


**** (2026-10-11 18:11, 0 votes)
good run-down... need to download the latest wheel house


---

## Again, my second submission is at 17hr.. no result..
/competitions/gemma-4-developer-agent/discussion/749139 | by  | posted 2026-10-14 02:45 | last comment 2026-10-14 05:19 | 1 comments | -1 votes


**** (2026-10-14 02:45, -1 votes)
Hello, thank you for your attention to this matter. My first submission was successful after roughly 17 hours, my second submission is at the 17hr mark. Is this normal?


**** (2026-10-14 05:19, 0 votes)
Yes, this is very normal


---

## [Fixed] Unable to download data.
/competitions/gemma-4-developer-agent/discussion/748890 | by  | posted 2026-10-13 13:31 | last comment 2026-10-14 01:06 | 3 comments | 0 votes


**** (2026-10-13 16:27, 0 votes)
Please check again. I reuploaded the data, and I think it's working now.


> **** (2026-10-14 01:06, 0 votes)
> Thank you Ryan, it is working now!


**** (2026-10-13 13:44, 0 votes)
The full-bundle endpoint fails for me too, but per-file downloads work (I pulled tasks.jsonl, the harness README and the sample submission this way today):

```
# list files (paginated, ~640 entries)
kaggle competitions files gemma-4-developer-agent --page-size 200
# download one file at a time
kaggle competitions download gemma-4-developer-agent -f tasks.jsonl -p data/
kaggle competitions download gemma-4-developer-agent -f HARNESS_README.md -p data/
```

Note the full dataset is ~22 GB, almost all of it `snapshots/` (~21.5 GB), so unless you need every repo snapshot locally, it's easier to attach the competition data to a Kaggle notebook (Add Input -> Competitions). It mounts at `/kaggle/input/competitions/gemma-4-developer-agent/` with nothing to download.


**** (2026-10-13 13:31, 0 votes)
I tried both Kaggle CLI and the webpage download zip button, and both failed.

Kaggle CLI:

```shell
$ kaggle competitions download -c gemma-4-developer-agent
404 Client Error: Not Found for url: https://api.kaggle.com/v1/competitions.CompetitionApiService/DownloadDataFiles
```

Download zip button will redirect to this page:
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F809190%2F2ed7946b6b6b5b65c51f61d0c5e72ffe%2FScreenshot%20from%202026-10-13%2021-28-48%20exif%20removed.png?generation=1791898259893224&alt=media)

Could anyone help fix data downloading? This issue is blocking multiple participants.


---

## Problem statements with PR descriptions without issue detail
/competitions/gemma-4-developer-agent/discussion/748919 | by  | posted 2026-10-13 15:19 | last comment 2026-10-13 20:02 | 1 comments | 0 votes


**** (2026-10-13 20:02, 0 votes)
Oh, I forgot - even the first task (fastapi_15661) is of that type!😀 (But elsewhere competition hosts has assured that teh private dataset has been fully validated..so, Lets hope tasks are not of this type in private dataset)


**** (2026-10-13 15:19, 0 votes)
I have noticed that some of the tasks in the tasks.jsonl contain problem statement from the github's Pull Request page that closed the issue instead of the actual github issue page. In some cases, it is impossible to get the actual problem based on such PR description. Since the cloned repository at the `base_commit` does not have the GitHub issue data, the agent has no way of knowing what the real problem actually is.

**An Example: Task `rich_3944**`

In the dataset, the problem statement for `rich_3944` is literally just this:

```text
fix fonts #3944

Fixes https://github.com/Textualize/rich/issues/3943

```

The actual issue (#3943) is about character cell width calculations for Nerd Fonts and Unicode codepoints, which requires a fix in `rich/cells.py`.

However, because the agent only sees "fix fonts" and cannot access the URL, it will likely search the codebase for the word "fonts" and fall into a trap—such as modifying Windows legacy "raster font" settings in `table.py` or `box.py`. There is absolutely zero context provided to help the offline agent zero in on the real issue. 

Is this a mistake on how the dataset was scraped, or is there some expected way for the agent to solve these kinds of issues completely offline? Are there other tasks in the dataset that are described in terms of the PR rather than the original issue, in such a way that the issue to be fixed cannot be derived?


---

## A few scoring-setup questions, so we can test offline and lean less on the queue
/competitions/gemma-4-developer-agent/discussion/748428 | by  | posted 2026-10-12 01:48 | last comment 2026-10-13 14:31 | 8 comments | 2 votes


**** (2026-10-12 11:05, 3 votes)
Hi @johnsoliva,

Thanks for the questions. The discussion board has been busy, and I've missed a few posts.

1. A participant's `eval_config.yaml` doesn't affect scoring. The only thing the scorer gets are the submitted patches. The `pytest` run in the scorer gets a timeout of 300 seconds to prevent hung tests from killing the whole submission. The gold patches finish well within this time.
2. It's the same sandbox but different wheels.
3. Yes, fail before gold patch and pass after. There are a variety of repos of varying sizes and domains. Some repos have more tasks than others. The tasks were filtered by running a strong commercial on them with a simple config and keeping only those tasks it either succeeded at or failed by one assertion (typically some solvable edge case).
4. Yes, I will try to be better about this.


> **** (2026-10-12 11:36, 0 votes)
> Thank you, that's very helpful. One small check, if I may: do the `evaluation:` caps in eval_config.yaml still apply during the agent phase, with only the scoring step ignoring them? Thanks again for the version notes.


> > **** (2026-10-12 12:36, 0 votes)
> > Yes, the `eval_config.yaml` applies when the agent is running.


**** (2026-10-12 01:48, 2 votes)
Hi to the host team, thank you for the queue fixes, reruns and steady answers over the past weeks. We know the L4 pool is stretched.

With ~33 h queue waits, many of us want to validate offline as faithfully as possible and submit less often. Anything you can share on the following would help (nothing about hidden task identities):

1. Verification timeout. In https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/745805 (Q3) you mentioned double-checking whether timeout_seconds from eval_config.yaml also bounds the verification pytest on the scorer. Any outcome from that check?
2. Sandbox. Do hidden tasks run in the same sandbox as the published harness (Docker, same image and Python version)? Also asked in https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747704 and https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/745975
3. Task filtering. Could you share rough criteria for how the hidden tasks were "more rigorously filtered" (e.g. tests fail before the gold patch and pass after; repo type or size)? That would let us build representative local sets from public repos.
4. Version notes. When the scorer's harness packages change, could a one-line note be posted here?

In case it's helpful, we are glad to try any local-validation guidance and report back. Thanks again.


**** (2026-10-12 12:05, 0 votes)
Hello to the host team, and thank you, Ryan, for the detailed answers above; they help a lot with offline validation.

May we add three small follow-up questions about the sandbox, from reading the public harness? Nothing here asks about the hidden tasks themselves, and we fully understand if some details cannot be shared.

(1) Does "the same sandbox" include the README's network_mode "none" for the containers? We ask because the public sandbox/setup.py retries the editable install without --no-index when the offline attempt fails, so the answer affects how we budget time against the 12-hour limit.

(2) Does the editable install of /workspace succeed for the hidden repositories in the scoring sandbox, or do some of them import the workspace only through the path file that setup.py --fast-path writes?

(3) Is enable_sandbox_testing left at its default (true) in the scoring run, so that the agent can run pytest inside its sandbox?

Thank you again for your time.


> **** (2026-10-12 13:01, 0 votes)
> 1. There is no network timeout delay during container setup.
> 3. Yes, it can run pytest in its sandbox.


> > **** (2026-10-12 13:55, 0 votes)
> > Thank you for the clear answers. That settles the setup-time and sandbox-testing questions for us. If you are able to say: in the scoring sandbox, can a hidden repository's tests import the package under test in the usual way (e.g. installed in place), or should we not rely on that? No worries at all if this can't be shared. Thanks again.


> > **** (2026-10-12 16:02, 0 votes)
> > Yes, you can rely on the package under test (and its pre-cached test dependencies) being importable in-place in both the agent sandbox and the verification sandbox.


> > **** (2026-10-13 14:31, 0 votes)
> > @ryanholbrook Thank you for these answers. Two short follow-ups, both about matching the scoring run offline. Neither is about the hidden tasks, and one line each would settle them.
> > 
> > **1. Which sandbox manager runs the agent phase?**
> > 
> > You wrote "It's the same sandbox but different wheels." The public harness has two managers, and they prepare a task differently:
> > 
> > - `sandbox='docker'` (`ContainerManager`, the default in `swegemma/config.py`): the image from `docker/Dockerfile.sandbox` (`python:3.13-slim`), `pip install -e /workspace`, then `sandbox/setup.py --fast-path`.
> > - `sandbox='subprocess'` (`SubprocessManager`, what the Getting Started notebook passes): a venv on the notebook's own Python (3.12 on Kaggle); `install_editable_package` and `install_test_dependencies` in `harness/container_setup.py` return early for it.
> > 
> > Does the scoring run use Docker or subprocess while the agent is working? If one fact is easier to give: is `python3` in the agent's sandbox 3.13 or 3.12? (Asked before in https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747704, no answer yet.)
> > 
> > **2. Which compaction threshold?**
> > 
> > `HARNESS_README` 7.2 gives `EventsCompactionConfig(compaction_interval=15, overlap_size=2, token_threshold=32768, event_retention_size=5)`. The Getting Started notebook (current version) passes `token_threshold=14336`. Which value does the scoring run use today: 32768 or 14336? (Asked in https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/748584, no staff answer yet.)
> > 
> > Thanks again.


---

## Not able to download data
/competitions/gemma-4-developer-agent/discussion/743353 | by  | posted 2026-09-25 18:09 | last comment 2026-10-13 08:28 | 4 comments | 1 votes


**** (2026-09-25 18:09, 1 votes)
Running `kaggle competitions download -c gemma-4-developer-agent` gives me `404 Client Error: Not Found for url: https://api.kaggle.com/v1/competitions.CompetitionApiService/DownloadDataFiles`. The same is true when I used 

```
import kagglehub; path = kagglehub.competition_download('gemma-4-developer-agent')
```

Is this known?


**** (2026-09-25 18:25, 0 votes)
Broken from the Data page, too. I will try re-uploading the dataset. Thanks for the heads up.


> **** (2026-09-25 18:28, 0 votes)
> Hi Ryan, is it possible to get RTX PRO 6000 gpus instead of L4x4?


> > **** (2026-09-25 18:34, 0 votes)
> > That's unlikely, unfortunately.


> **** (2026-10-13 08:28, 1 votes)
> Still broken


---

## Follow-up on the 12 h limit: what counts, and are the four fields enforced as hard cuts?
/competitions/gemma-4-developer-agent/discussion/748618 | by  | posted 2026-10-12 17:52 | last comment 2026-10-13 01:18 | 2 comments | 0 votes


**** (2026-10-12 20:44, 0 votes)
My understanding is this way: 

1.  Evaluator runs in two phases - 10 hours for tasks and 2 hours for patch validation - this means max 5 mins per task. 

2. Timeout is per task. I guess it is meant for not getting struck in loop etc

3.  In my experiments, I have found that 8 mins + 28 calls timed out. This means the safer tool for time management is max_time_minutes rather than tool call budget. In local experiments, I now find more tool calls within 5 minutes which depends on task difficult etc. So, restricting on tool call budget is risky

4. We may have to find some way to skip tasks to raise per task max_time else the notebook should be scored for whatever tasks completed in ten hours. I am sure the later will be done which will make the competition more efficient and time management less restrictive on evaluating the effectivness of the agents


> **** (2026-10-13 01:18, 0 votes)
> However, the automatic budget_warning issued by the harness near 80% has a major impact - but the warning is based on max_tool_calls and not max_time!!😀 This makes an impact making max_tool_calls again important. If you give more tool calls, it keeps exhausting the tools calls till budget warning!


**** (2026-10-12 17:52, 0 votes)
Follow-up on the scoring-run questions: what exactly counts toward the 12 h,
and are the four eval_config fields enforced as hard cuts?

Hi hosts — a follow-up on this thread. Two things we cannot determine from the docs, and both
decide how we spend our remaining submissions.

We measured our per-task agent time on 32 evaluations in our own notebook (4xL4, same model):
median 265 s, mean 326 s, p95 644-795 s. If the run is sequential and the 12 h is the wall clock of
the whole notebook, ~120 tasks project to 9-11 h — right at the edge.

But we have the SAME declared budget (50 tool calls / 15 min) completing on 2026-10-05 (0.13) and
returning "Your submission notebook exceeded the allowed runtime" on 2026-10-08 and 2026-10-10.
So something in the accounting differs from our model.

1) What exactly counts toward the 12-hour limit?
   - Is it the wall clock of the whole scoring notebook, including per-task sandbox setup and any
     queue wait — or the sum of the per-task agent time only?
   - Is the effective per-task budget 12 h / n_tasks, where n_tasks is the ACTUAL number of tasks in
     the hidden split? (The error message says the hidden dataset can be larger/smaller/different
     than the public one, so n is not something we can read.)

2) Are the four fields the scorer reads enforced as HARD cuts, or advisory budgets?
   From the earlier answer: "The scorer reads those, and only those, four fields."
   Our difficulty is what "reads" means operationally, specifically for timeout_seconds:
   - we declared timeout_seconds: 240 (4 min) while our measured per-task median is 265 s. If that
     field is a hard per-task cut, most of our tasks would be truncated BEFORE the agent produces a
     patch — and no prompt or tool budget could compensate;
   - in our own harness the declared ceilings were NOT obeyed (sessions ran well above
     timeout_seconds), so we cannot tell from our side whether the scorer enforces them.
   Narrow question: is timeout_seconds a hard kill on the task (per task, or for the whole run)?
   And is max_time_minutes counted inside the same 12 h — i.e. do the fields multiply
   (n_tasks x max_time_minutes), or are they independent caps?

We are choosing between REDUCING our per-task budget and RAISING timeout_seconds (our arithmetic
says 300 s keeps 120 tasks under 12 h with ~17% margin) — and those two point in opposite
directions. Any pointer helps. Thanks!


---

## Scoring runs now take 22–46 h with a 6-min agent cap. Does the 12 h limit include queue time?
/competitions/gemma-4-developer-agent/discussion/748443 | by  | posted 2026-10-12 04:07 | last comment 2026-10-12 19:32 | 6 comments | 2 votes


**** (2026-10-12 04:07, 2 votes)
Hi @ryanholbrook, a question about how long scoring takes, since one pending submission per team means grading time decides how many daily slots we can use.

**Our setup** (identical apart from the noted changes):
- `max_time_minutes: 6`, `max_tool_calls: 45`, `max_turns: 40`;
- `timeout_seconds: 300`, except the last one at 600.

In swegemma 0.2.7, the agent session is wrapped in `asyncio.timeout(max_time_minutes*60)` (`agent_runner.py`), so each task's agent phase is at most 6 min. The grading pytest runs once per task, bounded by `timeout_seconds`.

**Observed, submit time → scored:**

| ref | timeout_seconds | submitted (UTC) | time to score |
|---|---|---|---|
| 56864122 | 300 | 10-06 00:00 | ~13 h |
| 56893958 | 300 | 10-07 00:02 | < 24 h |
| 56924966 | 300 | 10-08 00:02 | < 24 h |
| 56979096 | 300 | 10-09 00:00 | **~46 h** (COMPLETE 10-10 ~22:15) |
| 57053652 | 600 | 10-10 22:22 | still PENDING at 23 h+ |

With ~120 sequential tasks, 6 min of agent time plus a 300 s test cap, the run can't exceed roughly 22–24 h even if every test hits its timeout. So 56979096 spent at least ~22 h on something other than running our agent and tests.

**Our local measurement:** we ran the wheel's own `verify_task` on all 129 public snapshots, with the gold patch and with no patch.
- Grading costs ~5 s of setup plus ~1–40 s of pytest per task.
- 3 no-patch runs hang to the cap: infinite-loop bugs, with `-o timeout=0`.
- That predicts a full run of ~13 h, which matches our 10-06 run. It can't produce 46 h.

**Questions:**
1. Does the clock we see (submission → COMPLETE) include time queued before the run starts? Is there a queue shared across teams, and did it grow around Oct 9?
2. Does the 12 h limit count from run start or from submission? A participant in #743063 reported runs past 12 h that still scored and another that errored; queue time would explain that.
3. Are runs ever restarted after an infrastructure failure, so a submission is scored twice end to end?
4. There's no cancel in the UI ("dismiss" on the active-events popup only hides the notice). Could teams cancel a PENDING submission, or could the one-pending limit allow a second submission to queue behind it?

Thanks!


**** (2026-10-12 17:47, -1 votes)
I'm experiencing the same issue. My submission has been stuck in PENDING for an unusually long time, preventing me from submitting new experiments.

With only one pending submission allowed per team, these delays significantly reduce our ability to test and improve our solutions.

Could the organizers please clarify whether queue time is included in the 12-hour limit and whether there is any way to cancel a stuck submission?

Thanks for raising this issue!


> **** (2026-10-12 19:31, 0 votes)
> No, queue time is NOT included in the 12-hour limit, it consists of only the run and as far as I know there is NO way to cancel a stuck submission


**** (2026-10-12 06:08, -2 votes)
Please @ryanholbrook confirm the statement if actually can get score even if the time on submession exced the 12h, I 've done submession and it's exced the 24h and still, no response, at all.


> **** (2026-10-12 19:32, 0 votes)
> yes, it can get score if you see it exceeding 12 hours, as it doesn't include the queue time which can take few hours. Mine scored after 2+ days of run


**** (2026-10-12 17:56, 0 votes)
It took me 2 days to see the score, and while scoring I could not submit other :(


**** (2026-10-12 08:43, 0 votes)
As far as I know, currently:
1) Yes
2) From run start
3) Not sure
4) No


---

## Submission ended with "Notebook Threw Exception": could you check what raised?
/competitions/gemma-4-developer-agent/discussion/744800 | by  | posted 2026-10-01 01:25 | last comment 2026-10-12 16:24 | 6 comments | 5 votes


**** (2026-10-01 01:25, 5 votes)
Hi @ryanholbrook, my submission from notebook notebook35c2b989ac (version DMV4, submitted on 1 Oct) ended with "Notebook Threw Exception" and no score. Its commit run succeeded (91 s), and in that run validate_directory, validate_single_declared_model and compile_submission (wheelhouse v25) all passed. The same notebook design scored on 28, 29 and 30 Sep; this version only changed prompt text.

Could you check what raised in this run, and whether it was on the scorer side (for example during today's patches)? If so, a rerun would be much appreciated. Thanks!!


**** (2026-10-12 16:24, -1 votes)
@ryanholbrook I am facing "notebook threw an exception" for previous 2 submission approx 3 days. but the problem is I didn't submitted a notebook I submitted a .zip directly. I don't think anything there can throw any exception. Could you please check what caused this.


**** (2026-10-01 01:56, 1 votes)
Same here: submission 56729291 (2026-10-01 00:07 UTC) ended with "Your notebook hit an unhandled error while rerunning your code". No adapters. It's a self-contained notebook (bundle embedded, no input datasets) that writes /kaggle/working/submission.zip. The notebook run completes normally, and the zip is valid (agent.yaml at the root; it passes validate_directory and compile_submission with wheelhouse v25). The failure came about 4–7 min after submitting, likely before vLLM had finished starting. The same bundle is running fine through the official Evaluator on Kaggle 4×L4. Could you check what raised, and rerun it or restore the allowance if it was on the scorer side? Thanks!


**** (2026-10-12 16:21, 0 votes)
@ryanholbrook +1 same here.


**** (2026-10-05 10:12, 0 votes)
+1 same here


**** (2026-10-05 06:27, 0 votes)
+1 Same here for submitting the submission.zip


---

## Contest standstill
/competitions/gemma-4-developer-agent/discussion/748500 | by  | posted 2026-10-12 10:21 | last comment 2026-10-12 15:58 | 6 comments | 1 votes


**** (2026-10-12 14:26, 5 votes)
In my opinion, the contest is not at a standstill. 
I think the following might be true:

1. The competition is really hard, and I don't think anyone is going to win by just tweaking a few prompts.
2. Everybody faces these same issues, including a limit to how many submissions they can get through and how many Kaggle resources they can use. I also don't think further appeals or piling on will change this or be productive.
3. I think many may have realised by now that this is a "pay-to-win" competition. If you don't own or hire GPUs for your own offline experimentation, you can't hope to get very far.
4. And even if we can do daily submissions again, they still take 12 hours to run and score and, honestly, give very little usable feedback, plus the statistical noise makes it even less useful (too few tasks), so you can't actually use it as a training signal unless you manage to make big leaps.

PS. I don't claim to be some kind of self-proclaimed expert, and my LB score sucks. So this is purely my opinion based on what I have seen since the competition started; take it with a grain of salt.


> **** (2026-10-12 14:37, 0 votes)
> ​I appreciate your candor and agree with parts of your response, though I also place a high value on transparency. Had the competition been intended specifically for those with resources beyond the average participant—rather than an accessible competition for everyone—it would have been helpful to know this in advance.
> 
> ​Nevertheless, like most participants, I will make the effort for the sheer enjoyment and the challenge itself.
> 
> ​Thank you for taking the time to reply.
> 
> ​Best regards


> **** (2026-10-12 14:51, 0 votes)
> very good points. 
> 
> Regarding your 3rd point. I think it's unlikely to end up in the top-5 or maybe even in the top-10 without some nice amount of compute. I guess ~$1000 or access to a permanent cluster is a prerequisite. 
> 
> But who knows... We are allowed to tune smaller models now. Maybe some good techniques can help small models compete successfully with big ones


> > **** (2026-10-12 15:37, 1 votes)
> > I would not presume to match the Masters or participants with far greater resources and capabilities than my own, but I will certainly try! :-]


> > **** (2026-10-12 15:54, 0 votes)
> > Does your submission currently use LoRa? If so, do you own hardware sufficient for the 31b training runs? Or are you renting?


> > **** (2026-10-12 15:58, 0 votes)
> > And if you own, do you want a teammate 🤣


**** (2026-10-12 10:21, 1 votes)
Dear Competition Managers,

​I greatly appreciate your hard work and dedication in addressing the recent technical challenges facing the competition. That being said, I would be most grateful for your perspective on a few ongoing issues.

​Currently, submissions take up to two days to be scored, during which time further submissions are blocked. Furthermore, GPU usage hours are being recorded at double the actual rate, causing participants to hit their limits and wait a full week for the counter to reset. Consequently, our ability to actively participate has slowed to a virtual standstill.

​Given that we are currently unable to make progress without your guidance, I would truly appreciate any update or clarification you could provide on these matters.

​With highest regards


---

## Looking for a Team / Team Up? (Solo dev looking to join 2-3 member teams)
/competitions/gemma-4-developer-agent/discussion/748572 | by  | posted 2026-10-12 15:17 | last comment 2026-10-12 15:17 | 0 comments | -2 votes


**** (2026-10-12 15:17, -2 votes)
Hi everyone,
I have been participating in this competition as a Solo Developer, but due to the recent Kaggle server queues and submission delays, it's becoming highly inefficient to test and iterate alone.
I am looking to join an existing team of 2 or 3 members so we can pool our daily submission limits and collaborate effectively.
About my approach:
• Currently working on optimizing the Gemma 4 agent setup.
• Focused on local testing to avoid the long Kaggle queue issues.
If you have an open slot in your team and want to collaborate, please comment below or send me a team invitation on Kaggle. Let's team up and tackle this together!
Thanks!


---

## Local Environment Evaluation Issue
/competitions/gemma-4-developer-agent/discussion/748400 | by  | posted 2026-10-11 20:00 | last comment 2026-10-11 20:00 | 0 comments | 0 votes


**** (2026-10-11 20:00, 0 votes)
Hello, I am trying to set up the environment locally (not on Kaggle infra). I am not using docker and instead running using subprocess sandbox. Firstly, unlike the docker sandbox the harness is using the same parent environment for all tasks in the subprocess setting. Secondly, after adding a fix for that, I tried running all 129 tasks and a lot of them were having dependency issues with the wheels provided and the way the tasks are set up. They pytests weren't passing even after applying the gold patch.

One thing I am trying to do is to fix the harness and the dependency issues myself. Am I doing something wrong? For people who have faced similar issues, what did you end up doing?

To the moderators, could these issues please be fixed or have they already been addressed some where else?

Any insights would be really helpful so that I can start putting my efforts in agent development instead. Thank you!


---

## Submission "Scoring" for 2 days, haven't been able to submit anything else due to "pending submission"
/competitions/gemma-4-developer-agent/discussion/748266 | by  | posted 2026-10-11 10:10 | last comment 2026-10-11 13:13 | 3 comments | -4 votes


**** (2026-10-11 10:15, 2 votes)
First of all not much can be done, everyone has the same problems as you do.
Second of all this has been an ongoing issue that has been covered in many discussions.


**** (2026-10-11 10:10, -4 votes)
I only have one submission being scored. But it has been that way for 2 days, and I can't submit anything. This has seriously impacted the speed at which I can experiment. Yes, I did do local evaluations, but they seem to have sped up the GPU utilization speed for 4 x L4, so it burns quota faster. 
At this point, it seems like the competition is actively trying to fight you as you try to compete.
It's getting frustrating, Kaggle Staff, would be grateful if something was done about this...


---

## Wheelhouse v29/v30: include_thoughts: false no longer disables thinking (thinking_budget: 0 does)
/competitions/gemma-4-developer-agent/discussion/747914 | by  | posted 2026-10-09 22:56 | last comment 2026-10-11 11:40 | 4 comments | 1 votes


**** (2026-10-10 12:31, 2 votes)
This was intended. My apologies. I'll post an update on Monday and update the readme. This change was meant to have `include_thoughts` manage what's carried in the chat template from call to call, more consistent with the Gemini API.


**** (2026-10-09 22:56, 1 votes)
Our submission has used thinking_config: {include_thoughts: false} 
  since day one, following the README (section 2.4 says to "use 0 or 
  include_thoughts: false to disable thinking"). After the wheelhouse 
  moved to v29/v30 our local runs got a lot slower, so we compiled the 
  same bundle with both harness versions and compared what actually gets
  sent to vLLM.

  With adk_submission 0.2.12 the request carries "chat_template_kwargs":
  {"enable_thinking": false}. With 0.2.13 the same bundle carries 
  "enable_thinking": true plus "thinking_token_budget": 4096. As far as 
  we can tell the 4096 is the runner's default budget being merged into 
  our config, and 0.2.13's apply_thinking_config_to_model now checks the
  budget before it checks include_thoughts. On 4x L4 with the scorer's 
  flags that turned one of our tasks from about 90 seconds of agent time
  into 316 seconds, with the model thinking on most calls.

  Setting thinking_budget: 0 explicitly turns it off again under both 
  versions, so there is an easy workaround. I wanted to check whether 
  this is intended, though. If include_thoughts: false is no longer the 
  off switch, it would be worth saying so in the README, since anyone 
  relying on it has been scored with thinking on since Oct 8.


**** (2026-10-11 05:47, 0 votes)
Thank you for the Wheelhouse v29/v30 info @andrewmcadoo


**** (2026-10-11 03:02, 0 votes)
Same regression, but on the harness's own default backend it is a hard failure, not a slowdown.

We hit this on 2026-10-10 and can add one data point. We serve the model through
`transformers serve` — the backend `adk_submission.server.spawn_transformers_server`
defaults to for `backend="transformers"` — and there the two fields you identified do
not merely cost time: they make every request fail.

What the request carries (observed at the server, adk_submission 0.2.13):

    'chat_template_kwargs', 'thinking_token_budget'

What the server answers:

    HTTP 422
    {"detail":"Unexpected fields in the request: {'chat_template_kwargs', 'thinking_token_budget'}"}

That validation is unconditional and has no opt-out flag:

    transformers/cli/serving/utils.py:1109
      raise HTTPException(status_code=422, detail=f"Unexpected fields in the request: {unexpected}")

Net effect: with the wheelhouse as shipped, `sample_submission` plus the default
`TransformersServer` backend fails on the **first** model call. The layers of reporting
all point away from the cause:

- LiteLLM surfaces it as a `None` response
- ADK raises `AttributeError: 'NoneType' object has no attribute 'get'` inside its own
  response handler (`google/adk/models/lite_llm.py:1655`)
- the harness records the task as `Sandbox execution error: ...` with
  `total_llm_calls: 0` and `duration_seconds ≈ 5`

Three misleading labels for one 422. If anyone else is debugging "sandbox execution
error" with zero LLM calls, this is worth checking first.

Your `thinking_budget: 0` workaround is correct, and it also removes both fields from
the emitted body (we verified end to end: with it, neither `chat_template_kwargs` nor
`thinking_token_budget` appears).

Two things we could not determine from our side and would like to know:

1. Is `thinking_token_budget` being merged in from the runner default (4096) intended to
   outrank an explicit `include_thoughts: false`? Your 0.2.12-vs-0.2.13 comparison
   suggests a behavior change, and `adk_submission/resolvers/generation.py:407-417` reads
   as if the budget branch was placed above the `include_thoughts` branch by accident.
2. The workaround depends on a user-supplied `0` beating a runner default. If that default
   changes, does `include_thoughts: false` become meaningful again, or is `thinking_budget`
   now the only supported switch?

Scope, so the claim is not read as broader than it is: one deployment, one served model
(a small stand-in rather than the 31B), one backend (`transformers serve`), one harness
version (0.2.13). We have not tested vLLM, where your measurement shows the same fields
costing time rather than failing.


> **** (2026-10-11 11:40, 0 votes)
> Thanks for the heads up. I haven't tested the change yet with `transformers serve`. It should work with vLLM, though. I'll investigate.


---

## [10.0 Gold Resource] Gemma 4 TFD-Agentic Trajectories & SWE-bench Evaluation Suite
/competitions/gemma-4-developer-agent/discussion/748227 | by  | posted 2026-10-11 06:51 | last comment 2026-10-11 06:51 | 0 comments | 2 votes


**** (2026-10-11 06:51, 2 votes)
Hello Gemma Developers!

Evaluating autonomous coding agents requires structured multi-turn action traces. We have published a dedicated benchmark dataset to assist teams developing and fine-tuning developer agents with Gemma 4:

### 🌟 Resource Highlights:
- **Dataset:** [Gemma 4 TFD Agentic Trajectories & Benchmark](https://www.kaggle.com/datasets/rajrajak99/gemma-4-tfd-agentic-trajectories)
- **Usability Rating:** 10.0 / 10.0 (Gold Tier Standard)
- **Contents:** Multi-turn bug localization, test-feedback reproduction runs, and file graph navigation steps.
- **Companion Agent:** [TFD-Agent SWE-bench Resolution Kernel](https://www.kaggle.com/code/rajrajak99/tfd-agent-autonomous-swe-bench-resolution-with-ge)

Designed specifically for offline trajectory analysis and agentic alignment. Check out the dataset, download for your validation pipelines, and leave an upvote if it helps your experiments!


---

## Title: Submission pending for 37+ hours, is scoring backlogged?
/competitions/gemma-4-developer-agent/discussion/748165 | by  | posted 2026-10-10 22:55 | last comment 2026-10-11 00:48 | 1 comments | -1 votes


**** (2026-10-10 22:55, -1 votes)
Hi all and Kaggle staff,

My submission from 2026-10-09 09:27 UTC has been in Pending for over 37 hours. It uses a per-task budget of 8 min / 28 tool calls with a 240 s command timeout. Earlier submissions with the same budget took about 24 hours to score.

Is there currently a scoring backlog, or could this submission be stuck? While it's pending I can't submit anything else, since only one pending submission is allowed.

Has anyone else seen unusually long scoring times this week? Thanks!


**** (2026-10-11 00:48, -2 votes)
Same situation, I just got it now with "Unhandled error".


---

## Some settings and Scores
/competitions/gemma-4-developer-agent/discussion/748168 | by  | posted 2026-10-10 23:43 | last comment 2026-10-10 23:43 | 0 comments | 4 votes


**** (2026-10-10 23:43, 4 votes)
Here are the scores I got for various settings till now:

Note: Scores could have been impacted by my own agent structure / instructions but I guess it is less impactful -  as of now, these are meant to find right tuning for my agent deck. 

If you have got different scores for the same settings, do report. It would help me understand the impact due to agent instructions. 

I guess temp=0.2 gives +/- 0.02 difference, but has not tested this.

**submission 1 - scored 0.08 - basic starter - thinking false**

temperature: 0.2
top_p: 0.95
top_k: 40
max_output_tokens: 16384
thinking_config:
  thinking_budget: 4096
  include_thoughts: false


**submission 2 - timed out with no score - with skills and thinking true - no eval yaml**

temperature: 0.2
top_p: 0.95
top_k: 40
max_output_tokens: 8192
thinking_config:
  thinking_budget: 4096
  include_thoughts: true

**Submission 3 - scored 0.05 - with skills but thinking false**

temperature: 0.2
top_p: 0.95
top_k: 40
max_output_tokens: 4096
thinking_config:
  thinking_budget: 3072
  include_thoughts: false


**Submisson 4 - scored 0.10 - with skills and thinking true  but with eval config**

temperature: 0.2
top_p: 0.95
top_k: 40
max_output_tokens: 8192
thinking_config:
  thinking_budget: 4096
  include_thoughts: true 

evaluation:
  timeout_seconds: 90
  max_tool_calls: 60
  max_time_minutes: 4
  max_turns: 80


**submission 5 - timed out with no score - because of eval config high time**

temperature: 0.2
top_p: 0.95

max_output_tokens: 8192
thinking_config:
  thinking_budget: 4096
  include_thoughts: true 

evaluation:
  timeout_seconds: 240
  max_tool_calls: 32
  max_time_minutes: 8
  max_turns: 80


**submission 6 - scored 0.13 - because reduced time and tools in eval**

temperature: 0.2
top_p: 0.95

max_output_tokens: 8192
thinking_config:
  thinking_budget: 4096
  include_thoughts: true 
  

evaluation:
  timeout_seconds: 240
  max_tool_calls: 24
  max_time_minutes: 5
  max_turns: 80

**submission 7 - scored 0.15**

 temperature: 0.2
top_p: 0.95

max_output_tokens: 8192
thinking_config:
  thinking_budget: 4096
  include_thoughts: true 
  

evaluation:
  timeout_seconds: 240
  max_tool_calls: 28
  max_time_minutes: 5
  max_turns: 80


**submission 8 - ? - in progress**

temperature: 0.2
top_p: 0.95

max_output_tokens: 8192
thinking_config:
  thinking_budget: 4096
  include_thoughts: true 
  

evaluation:
  timeout_seconds: 240
  max_tool_calls: 28
  max_time_minutes: 8
  max_turns: 80

Update:

Some  additional insights:

1. Thinking True might be important if you have several agents and skills
2. Controlling 12-hour time-out can be achieved through either max_tool_calls or max_time_minute in eval_config. By reducing max_tool_calls, you can indirectly reduce the time allowed, making max_time_out irrelevant
3. If you are exceeding 28-32 calls, then you should restrict time to 5 minutes (10 hr eval + 2 hours patch time implies just 5 mins available for a single task - assuming 120 tasks in private dataset)
4. Think level HIGH - leads to 60% more time and tokens. You may resort to HIGH thinking for some agents. I have not tested independent eval _config for each agent. The table below gives a sample comparison for a sample 3 tasks in local official harness.
  

| Run | Thinking | Time | Prompt tokens | Completion tokens | Total tokens | Steps |
|---|---|---:|---:|---:|---:|---:|
| No-thinking, high | false | **94s** | 373,841 | **2,289** | 376,130 | 39 |
| Thinking, default | true | 362s | **227,882** | 9,426 | **237,308** | 25 |
| Thinking, high | true | **458s** | 370,435 | 12,124 | **382,559** | 36 |

* Thinking/default is 3.85× slower than no-thinking.
* Thinking/high is 4.87× slower.
* Thinking/high uses 5.3× the completion tokens of no-thinking.
* Thinking/high is also about 6× the thinking/agent-generated reasoning volume implied by the trace.
* Interestingly, the default-thinking run has fewer total prompt tokens than the other two, but still takes almost 4× as long.


---

## Suggestion: Temporarily Pause Gemma 4 for 24 Days to Address the L4x4 Shortage
/competitions/gemma-4-developer-agent/discussion/747915 | by  | posted 2026-10-09 23:05 | last comment 2026-10-10 22:41 | 3 comments | 30 votes


**** (2026-10-09 23:05, 30 votes)
Background : https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747519

Thanks to the Kaggle team for working on this!

Would it make sense to temporarily pause the **Google Gemma 4 Developer Agent Competition** for 24 days, let **ARC-AGI-2** finish, and then resume Gemma 4 with its deadline extended accordingly?

This could allow both competitions to have sufficient L4x4 capacity, rather than having both struggle with extremely long queues and limited or reduced submissions.

I think staggering the two competitions would be a better solution for everyone.

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F22938014%2F26b886070638ee267ce8d789bab6a787%2F1.png?generation=1791587119497012&alt=media)


**** (2026-10-10 03:35, 3 votes)
We don't know their other obligations or constraints, but I like the idea too if it's possible!


**** (2026-10-10 07:27, 1 votes)
or atleast make 1 submission per 3 days (as ssuggested by [1](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747519#3536017) ) till the arc 2 completes


**** (2026-10-10 22:41, 1 votes)
I agree with this idea, we can rent GPUs for experiment, but we can't see the correlation between local improvement and LB improvement if we can't get the LB result promptly. This slows our iteration.


---

## Submission running for 2 days
/competitions/gemma-4-developer-agent/discussion/747961 | by  | posted 2026-10-10 03:30 | last comment 2026-10-10 14:56 | 7 comments | 3 votes


**** (2026-10-10 03:30, 3 votes)
One of my submission is running for 2 days.i thought there was a time limit of 12 hours.


**** (2026-10-10 05:45, 1 votes)
For me its running for a day now and no clue what is happening.


**** (2026-10-10 14:56, 0 votes)
they eventually pass and you get a score. happened twice so far with me.


**** (2026-10-10 10:35, 0 votes)
same here!


**** (2026-10-10 06:53, 0 votes)
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F37170011%2F17858502a9447bd9cb902270263f9ad1%2F2026-10-10-135228_hyprshot.png?generation=1791615168068421&alt=media)

LOL same I'm gonna die from old age


**** (2026-10-10 06:33, 0 votes)
The limit was extended due to the high demand and it should be done in 2 days (that isn't a promise just an estimation)


---

## Submission stuck in Pending for 35+ hours, which blocks the next submission
/competitions/gemma-4-developer-agent/discussion/748044 | by  | posted 2026-10-10 10:55 | last comment 2026-10-10 14:54 | 4 comments | -1 votes


**** (2026-10-10 10:55, -1 votes)
Hi all and hosts,

One of our submissions (ref 56979858) has been in Pending since 2026-10-09 00:05 UTC, which is about 35 hours now. Our earlier submissions usually finished within 11–15 hours.

Because a team can only have one pending submission at a time, every new submission since then has been rejected with "400 FAILED_PRECONDITION: Your team already has 1 pending submissions". We're losing a daily slot each day this continues.

Two more things we've noticed this week:
- Two earlier submissions (refs 56894307 and 56925310) first showed Kaggle Error after about 15 hours. Then, a day or two later, they received normal scores without any change on our side.
How long a submission takes to score seems to vary a lot from day to day.

Questions:
1. Is anyone else seeing submissions stay pending for a day or more, or errors that later turn into scores?
2. Hosts: could you check whether ref 56979858 is stuck in the queue? We're happy to have it cancelled so our next submission can run.
3. Is there an expected maximum scoring time we should plan around before the deadline?

Thanks!


**** (2026-10-10 14:54, -2 votes)
>Is anyone else seeing submissions stay pending for a day or more, or errors that later turn into scores?

We have like 100+ messages on a forum about that for 3-4 days. You clearly use discussions, since you posted this. Please, can you just read them~~~

>Hosts: could you check whether ref 56979858 is stuck in the queue? We're happy to have it cancelled so our next submission can run.

What is the point? Why bother submitting at all? If you know that your current submission is certainly better, it means that you have set some sort of a decent validation. 

The reason we got this queue is mostly because ppl do not care in general. They have the right to submit once a day and they use it. Most of the submissions are not well thought or not being used to test some diverse ideas — I have been doing that in a lot of competitions. If we, as a community, will care more about our subs, we wont have queues like that


**** (2026-10-10 14:31, -2 votes)
Same here my submission has been running for 44 hours


**** (2026-10-10 12:46, -2 votes)
Same here. @ryanholbrook -- our submission 56971184 (submission.zip, 2026-10-08 20:14:58Z) has been PENDING ~40.5h with no score and no error, and the pending-limit now rejects every new submission ("Your team already has 1 pending submissions; please wait for one to finish scoring.") even though today's daily allowance is unused.

It is a resubmission of 56926696, which already COMPLETED at 0.15, so cancelling/resetting 56971184 costs us nothing and we keep our best score. Could you please cancel it and release the pending slot, or include it in the next mass rescore?

Thanks!


**** (2026-10-10 11:09, -2 votes)
yes same here almost 30hrs.


---

## How often does the first grep hit find the file the fix touches? (all 129 public tasks)
/competitions/gemma-4-developer-agent/discussion/747980 | by  | posted 2026-10-10 05:01 | last comment 2026-10-10 05:01 | 0 comments | 1 votes


**** (2026-10-10 05:01, 1 votes)
Every strong public bundle here tells the agent some version of "grep for the most specific string, read the hit, edit by call 12". I wanted to know how often that first hit is actually the right file, so I checked it against the reference patches without running the model.

On the 128 tasks that edit an existing source file:

- The top identifier-grep hit is a file the gold patch edits 30% of the time.
- Fusing grep with plain BM25 over the issue text gets 34% at top-1, 61% in the top 5, 74% in the top 10.
- 35 of 128 issues contain no code identifier at all. A lot of them are merged-PR titles plus a link the sandbox can't open. rich_4077 is the whole of "proxy isatty / Fixes #4041".
- requests is easy (92% top-5). rich is the hard one (48%).

The practical bit: listing candidates before reading any (git grep -c across a few tokens, sorted) covers roughly twice as many tasks as reading the first hit. And on the ~40% where no lexical shortlist contains the gold file, a hard "edit by call 12" rule is probably forcing edits into the wrong place. I haven't scored a bundle built on this yet, so treat that part as a hypothesis.

Caveat: the scored tasks come from other repos, and the gold file isn't the only place a passing fix can go.

Notebook with the code and per-repo numbers: https://www.kaggle.com/code/hitarthjain0/gemma-4-agent-can-grep-find-the-bug

If anyone has run a "list candidates first" step locally, I'd like to know if it moved your resolve rate.


---

## Submission stuck in "Pending/Running" for 26+ hours, blocking new submissions (pending limit)
/competitions/gemma-4-developer-agent/discussion/747740 | by  | posted 2026-10-09 13:25 | last comment 2026-10-10 02:54 | 9 comments | 7 votes


**** (2026-10-09 13:25, 7 votes)
Hi @ryanholbrook and the Kaggle team,

I have a submission that has been stuck in "Pending / Scoring" for over 26 hours, and due to the pending submission limit, our team is completely blocked from making any new submissions.

### Details:
- **Team Name / Account**: `kkm121121`
- **Submission ID**: `56950980`
- **Submitted**: `2026-10-08 11:15:33 UTC` (26+ hours ago)
- **Status in API**: `PENDING` (totalBytes: `0`)
- **API Error when resubmitting**:
  `FAILED_PRECONDITION: Submission not allowed: Your team already has 1 pending submissions; please wait for one to finish scoring.`

Could you please look into this submission and fix it so our team's pending submission slot can be released?

Thank you for your help and support with the competition queue!
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F31682962%2Fc68372c0056205ccdfa0edaacc3f769e%2FScreenshot%202026-10-09%20185426.png?generation=1791552458051102&alt=media)


**** (2026-10-10 00:16, 2 votes)
Submission is effectively suspended for all of us until they resolve the GPU shortage issue : (


**** (2026-10-10 01:39, 1 votes)
Same, I've pending for 2 days :(


**** (2026-10-10 02:54, 0 votes)
Same here. I've been stuck for two days.


**** (2026-10-10 02:29, 0 votes)
Same, I've pending for 2 days


**** (2026-10-10 02:04, 0 votes)
Same for me it is now running for more than 2 days


**** (2026-10-10 01:56, 0 votes)
Yep, me too. I guess that's one way to enforce the "one submission per day" restriction -- make each submission take >1 day to run.


**** (2026-10-10 00:38, 0 votes)
Would it be possible to share a bit more status info? At least let us know whether we're currently queued or running. If we're queued, how many are ahead of us? If it's running, roughly how much longer will it take? A lot of people have been waiting for over 24 hours, so any update would really help.


**** (2026-10-09 23:51, 0 votes)
Same
(◡︵◡)


**** (2026-10-09 14:02, 0 votes)
I am facing the same problem


---

## When the wheel will be stable and the reference patches of  the train data will be corrected ?
/competitions/gemma-4-developer-agent/discussion/747928 | by  | posted 2026-10-10 00:46 | last comment 2026-10-10 00:46 | 0 comments | 1 votes


**** (2026-10-10 00:46, 1 votes)
Currently what's happening here is that wheel house is changing and also the reference patches for the task actaully is not solving the issue in significant number of cases. 

When these things will be fixed so that we can start working seriously without going unessesary back and forth actions.


---

## Reference patches fail for most FastAPI tasks in the public sandbox: are hidden tasks filtered?
/competitions/gemma-4-developer-agent/discussion/744259 | by  | posted 2026-09-29 05:51 | last comment 2026-10-10 00:33 | 2 comments | 2 votes


**** (2026-09-29 05:51, 2 votes)
Hi @elanlearns 
In the public sandbox (Dockerfile.sandbox plus the public wheel cache, with typing_inspection, h11, blinker and greenlet added), the reference patch passes only 18 of our 40 TRAIN tasks (3 of 23 FastAPI). swegemma injects the newest cached wheels (e.g. Starlette 1.6.0), so older FastAPI commits fail collection, and inline_snapshot, dirty_equals and attrs are missing from the cache. We reproduced this on two hosts. Also, one public task (rich_3468) passes with an empty patch. Are hidden tasks filtered to those whose reference patch passes, and whose empty patch fails, in the scoring environment?


**** (2026-09-29 14:06, 1 votes)
The tasks in the test set have been more rigorously filtered. I can confirm that a submission with "gold patches" validates at 100%. We will work on improving the training set.


> **** (2026-10-10 00:33, 0 votes)
> is this updated ?


---

## robust-edit: a drop-in skill that makes file edits reliable on Gemma 4 31B (and keeps edited tests out of your patch)
/competitions/gemma-4-developer-agent/discussion/747923 | by  | posted 2026-10-10 00:15 | last comment 2026-10-10 00:15 | 0 comments | 4 votes


**** (2026-10-10 00:15, 4 votes)
**Dataset:** [magicsword001/robust-edit](https://www.kaggle.com/datasets/magicsword001/robust-edit) · **Notebook (31B A/B):** [robust-edit: reliable edits for Gemma 4 agents](https://www.kaggle.com/code/magicsword001/robust-edit-reliable-edits-for-gemma-4-agents) · Apache 2.0

While reading 31B traces we kept seeing the agent lose tool calls to editing rather than to reasoning. A lot of
that comes from the harness, not the model, and a submission can route around it. robust-edit is the result:
a skill you copy into your submission, plus a one-call setup step.

## What goes wrong today (swegemma 0.2.7, wheelhouse 2026-09-30)

1. **`edit_file` loses arguments on 31B.** The model sometimes closes a string argument with a backtick
   (`"filepath": "src/x.py\`,old_string:"`), and `old_string` / `new_string` disappear. Across three runs of
   16 tasks, 107 of 246 `edit_file` calls (43%) failed, most of them this way, often in streaks of the same
   broken call.
   Tools with a single string argument (`run_command`) did not lose arguments in our runs.
2. **Copied escapes.** Tool results reach the model as one level of JSON, so code appears with `\n` and `\"`.
   Models copy them into `old_string`, often as a backslash followed by a real line break, which the
   `unescaped` fallback in `adk_eval_core` does not undo (very common on our 12B proxy, rare on 31B).
3. **Repeated identical calls** after a failed edit (up to 24 in a row in our traces).
4. **Edited test files sink correct fixes.** The reset of agent-edited test files before the hidden test patch
   is a no-op ([744825](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744825)), so one
   edited test file makes the test patch fail to apply. We saw this on 31B too.

## What robust-edit does

A setup step (one `run_skill_script` call) installs a small editor at `.git/agent/edit.py` (invisible to the
patch) and marks test/config files `skip-worktree`. The agent edits with one `run_command`:

```
python3 .git/agent/edit.py path/to/file.py <<'EOF'
<<<<<<< SEARCH
lines currently in the file
=======
new lines
>>>>>>> REPLACE
EOF
```

- matches exact text first, then ignoring whitespace/indentation, then with copied escapes undone (and applies
  the same repair to the replacement);
- refuses an edit that would leave a Python file that does not compile, and shows the error in context;
- on a miss, returns the closest lines with line numbers (and `--lines A-B` to replace by line numbers);
  says so when nothing would change or the same edit already failed;
- standard library only; works in the Docker and the subprocess sandbox.

## Results (31B, 4×L4, 16 training tasks, 40 calls / 20 min, three runs)

Each run compares two agents that differ only in robust-edit, alternately on the same tasks. The public notebook
reruns the comparison with the generic agent shipped in the dataset.

| | without robust-edit | with robust-edit |
| --- | --- | --- |
| `edit_file` failures | 107 of 246 (43%) | 19 of 66 (29%) |
| editor failures | – | 8 of 75 (11%) |
| setup step ran | – | 47 of 48 |
| tasks lost to an edited test file | 3 | 0 |
| resolved | 6/16 in every run | 6/16 in every run |

The editor never lost arguments or failed on copied escapes; its non-applied edits are mostly correct refusals
(a syntax-breaking edit, SEARCH text that really is not in the file, a budget stop). The agent still chooses
`edit_file` for part of its edits (from 16% to 70% depending on the prompt), and those fail as usual.
**It did not change the number of resolved tasks in these samples**; it removes wasted calls and turns and a class
of silent losses (broken files, edited tests — one of the three tasks lost that way was resolved with robust-edit).

Two things we learned on the way that may save you time:

- **Skill scripts must not hard-code `/workspace`.** In the subprocess sandbox the repository is a temporary
  directory, and ADK runs skill scripts after `chdir` into a temporary copy of the skill. Our first version
  silently did nothing on Kaggle. `setup.py` shows how to find the repository.
- **"First, call X" in the prompt is not reliable.** 31B skipped such a setup instruction in 11 of 16 tasks.
  A `SequentialAgent` with a one-call setup step in front of the solver ran it in 47 of 48 tasks. Give that step the same
  tool list as the solver (an unknown tool call is fatal in ADK, and the harness's task prompt mentions all
  tools) and keep thinking on with a small budget.

## Using it

Copy `skills/robust-edit/` into your submission, put the setup step in front of your agent (`example/` is a
complete submission), put the editor into the fix step of your prompt as in `example/prompts/solver.md` (where
it is mentioned changes how often the agent uses it), and keep
`edit_file` in the tool list. Details and limitations are in the README.

Feedback and failure cases are welcome — if the editor refuses or mangles something it should not, a trace
excerpt will help us fix it.


---

## Do we have to lose a day because of Kaggle problems?
/competitions/gemma-4-developer-agent/discussion/747906 | by  | posted 2026-10-09 22:28 | last comment 2026-10-09 22:28 | 0 comments | 1 votes


**** (2026-10-09 22:28, 1 votes)
Hello!

My Oct 8 submission is pending for 24h by now and I am not allowed to submit Oct 9 one (I get  FAILED_PRECONDITION error)!

if Oct 8 will not be scored within next 1h 40m, I will lose a day. Why do I have to lose a day?

It doesn't feel like a fair play when teams are randomly disadvantaged.


---

## Gemma 4 follow-up: Kaggle runtime calibration, command timeouts, and empty-prompt ablations
/competitions/gemma-4-developer-agent/discussion/747857 | by  | posted 2026-10-09 19:19 | last comment 2026-10-09 19:19 | 0 comments | 10 votes


**** (2026-10-09 19:19, 10 votes)
In my [previous post](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/746250), I shared ablations on sampling, thinking, time limits, and tools. Before continuing, we needed to calibrate our CoreWeave setup against Kaggle’s scoring environment.

**Our current operating pair is 4.5 minutes locally and 5.5 minutes on Kaggle.** This applies to our sequential setup: one active agent per B40 replica. The measured conversion is approximately **5.5 Kaggle minutes = 4.38 local minutes**; we chose 4.5 as the nearest tested setting.

With that calibration in place, we ran six more experiments: three command timeouts, each with our existing system prompt and an empty system prompt. The interesting result was that **the empty prompt consistently used fewer tokens, but produced more test-patch conflicts.**

All accuracy results below are from the **129 public tasks**, with one stochastic run per condition. These are local evaluation results, not leaderboard scores.

**1. Calibration: serving load changed the conclusion**

Our earlier B40 evaluations allowed several agents to share each inference server. Kaggle ran one agent at a time. That difference mattered enough to reverse the apparent speed comparison.

We selected a 12-task panel across four repositories, covering quick successes, failures, tool-limit cases, and long-running tasks. This was a diagnostic panel, not a random sample for estimating accuracy.

We first tested on Modal 4×L4, then directly on Kaggle using the official starter’s serving setup: vLLM 0.19.1, tensor parallelism 4, and a 32K context.

| Serving setup, same 12 task IDs | Model tokens | Estimated LLM time | Seconds per million model tokens |
|---|---:|---:|---:|
| B40 with multiple concurrent agents | 4.25M | 82.96 min | 1,170.6 |
| Kaggle 4×L4, sequential agent | 5.55M | 83.37 min | 900.8 |
| B40, one sequential agent per replica | 5.00M | 59.86 min | 718.0 |

The loaded B40 comparison produced the provisional recommendation of approximately **7 local minutes for 5.5 Kaggle minutes** in the previous post.

After removing competition between agents on each B40 server, the conversion became:

```text
Kaggle / sequential-B40 LLM time per token
= 900.8 / 718.0
≈ 1.2547

5.5 Kaggle minutes / 1.2547 ≈ 4.38 local minutes
4.5 local minutes × 1.2547 ≈ 5.65 Kaggle minutes
```

**The 7-minute local recommendation therefore belongs to the old, concurrently loaded setup.** For the sequential setup used in the new experiments, we use 4.5 minutes.

A few qualifications matter:

- These are reported **prompt + completion tokens**, including repeated context. The effective token rate is not output-generation speed.
- Tool execution can dominate individual tasks, so this is an approximate model-time conversion rather than an exact wall-clock mapping.
- The initial Modal environment had missing test dependencies. We corrected it and confirmed that gold-patch verification passed all 12 tasks before rerunning the agent.
- Our scored 5.5-minute Kaggle submission completed, and its non-evaluation agent files match the local 4.5-minute artifact. That supports this operating pair, but does not guarantee completion for every future configuration.

For roughly 120 tasks, a 5.5-minute cap allows up to 11 hours of agent time, leaving about one hour for setup and other overhead. This is our chosen budget, not a competition-mandated per-task limit.

**2. Full-set time-budget results**

We then evaluated all 129 tasks with **32 independent B40 replicas, one active agent per replica**, processing tasks consecutively on each GPU.

| Local time cap | Resolved | Resolution rate | Session timeouts | Total model tokens |
|---|---:|---:|---:|---:|
| 7 min | 43/129 | 33.3% | 21 | 51.76M |
| 4.5 min | 47/129 | 36.4% | 53 | 42.81M |
| 4 min | 43/129 | 33.3% | 66 | 39.18M |

The 4.5-minute run had the highest observed count, but this does **not** establish that a shorter cap improves accuracy.

The controlled 4.5-versus-4-minute comparison illustrates the sampling noise. After excluding one infrastructure failure from both conditions:

| Paired outcome | Tasks |
|---|---:|
| Passed both | 38 |
| Passed only at 4.5 minutes | 8 |
| Passed only at 4 minutes | 5 |
| Failed both | 77 |

That gives **46/128 versus 43/128**, with an exact paired McNemar **p=0.58**. The shorter run used 8.5% fewer tokens, but we did not detect a pass-rate difference.

These are independently sampled trajectories at temperature 1.0. The four-minute run is not simply the longer run stopped 30 seconds earlier.

**3. Command timeout × system prompt**

For the next sweep, we held these settings constant:

```yaml
max_time_minutes: 4.5
max_tool_calls: 50
max_turns: 80
```

We also retained temperature 1.0, top-p 0.95, a 4,096-token thinking budget, and the same tools and skills. Local serving used `max_num_seqs=128` and `max_num_batched_tokens=4096`.

We compared:

- **F:** `finalize.md`, our existing system prompt, including instructions to run patch hygiene immediately before submission.
- **N:** an empty `no_system.md`, with the task instructions, tools, and skills still available.

`timeout_seconds` is the **individual command timeout**, distinct from the total agent-session budget.

| Run | Command timeout | Resolved | Pass rate | Model tokens | Session timeouts | Test-patch conflicts |
|---|---:|---:|---:|---:|---:|---:|
| F300, existing control | 300s | 47/129 | 36.4% | 42.81M | 53 | 2 |
| F100 | 100s | 43/129 | 33.3% | 43.58M | 61 | 4 |
| F150 | 150s | 44/129 | 34.1% | 42.47M | 65 | 2 |
| F250 | 250s | 40/129 | 31.0% | 42.67M | 58 | 3 |
| N100 | 100s | 35/129 | 27.1% | 36.26M | 60 | 9 |
| N150 | 150s | 43/129 | 33.3% | 35.86M | 50 | 8 |
| N250 | 250s | 35/129 | 27.1% | 35.11M | 53 | 11 |

N100 had two infrastructure failures; excluding them gives **35/127, or 27.6%**. N250 had one invalid-tool error.

**Did command timeouts actually bind?**

Rarely:

| Run | Timed-out commands / all commands | Tasks affected |
|---|---:|---:|
| F300 | 2 / 1,956 | 2 |
| F100 | 3 / 1,996 | 3 |
| F150 | 4 / 1,976 | 4 |
| F250 | 3 / 1,944 | 3 |
| N100 | 8 / 1,701 | 5 |
| N150 | 1 / 1,707 | 1 |
| N250 | 3 / 1,691 | 3 |

Only approximately **0.06–0.47% of commands** timed out. This gives limited evidence that command termination explains the aggregate pass-count differences. Repeated runs are needed to distinguish timeout effects from sampling variation.

We are treating **150 seconds as a candidate operational default**, while retaining the existing prompt. F150 had 44 passes and two conflicts, compared with F300’s 47 passes and two conflicts. Their paired comparison gave **p=0.68**, which does not establish equivalence or make 150 seconds a proven optimum.

**4. The empty prompt saves tokens—but finalization matters**

At matched command timeouts, the empty prompt used approximately **15–18% fewer total model tokens**.

The 150-second pair was particularly interesting:

| Metric | Existing prompt, F150 | Empty prompt, N150 |
|---|---:|---:|
| Resolved | 44 | 43 |
| Model tokens | 42.47M | 35.86M |
| Median tool calls | 32 | 26 |
| Median LLM calls | 34 | 27 |
| Tasks invoking patch hygiene | 54 | 0 |
| Tasks calling `submit_patch` | 55 | 70 |
| Test-patch conflicts | 2 | 8 |

The empty-prompt run submitted on more tasks and used **15.6% fewer tokens**, but it never invoked the patch-hygiene finalizer.

That finalizer removes protected test changes and validates the workspace patch before submission. Across all three matched comparisons, the instructed prompt had **2–4 conflicts**, versus **8–11** with the empty prompt.

This is consistent with the finalization instruction providing useful submission hygiene. It does not isolate hygiene’s causal contribution: removing the whole system prompt also changes other behavior.

The task-level prompt comparisons also show why aggregate scores can hide substantial variation:

| Timeout | Passed both | Existing prompt only | Empty prompt only | Exact McNemar p |
|---|---:|---:|---:|---:|
| 100s | 31 | 11 | 4 | 0.118 |
| 150s | 32 | 12 | 11 | 1.000 |
| 250s | 27 | 13 | 8 | 0.383 |

The 100-second comparison excludes the two infrastructure failures. None of these single-run comparisons establishes a prompt-level accuracy difference.

I hope this comes in handy for those planning next iteration of their experiments.

PS: here "we" is me + codex.
PSS: Feel free to point out any discrepancies -- note that all the experiments are best of 1 so the noise is real and the fact I am running with temp=1.0 it just adds.


---

## Can the harness compact and retry on context-window overflow?
/competitions/gemma-4-developer-agent/discussion/747791 | by  | posted 2026-10-09 16:27 | last comment 2026-10-09 16:27 | 0 comments | 2 votes


**** (2026-10-09 16:27, 2 votes)
Hi! We encountered a context-window overflow during local evaluation with the published settings:

```python
# vLLM context window
max_model_len = 32768

# ADK compaction threshold
token_threshold = 14336

# Agent output limit
max_output_tokens = 16384
```

This leaves only **2,048 tokens of headroom** for growth between model calls:

```text
32768 - 14336 - 16384 = 2048
```

ADK normally checks the threshold using the **last reported prompt-token count**, which does not yet include the assistant content and tool results added afterward. If this growth crosses the remaining headroom, the next request can exceed the window before compaction triggers.

In our captured case, the previous prompt count was **13,498**, while the next input was reconstructed as approximately **17,540** tokens. With **16,384** output tokens requested, vLLM rejected the request.

Could the competition harness **compact history and retry after a context-window error**, instead of ending the agent’s attempt on the task? Is this recovery already supported in the scoring environment?

This occurred in the root agent with compaction configured, so it appears separate from [ADK #7397](https://github.com/google/adk-python/issues/7397).

Happy to provide a reproduction.


---

## Titre : Request for evaluation logs and clarification of low submission score (0.05)
/competitions/gemma-4-developer-agent/discussion/747763 | by  | posted 2026-10-09 14:46 | last comment 2026-10-09 14:46 | 0 comments | -2 votes


**** (2026-10-09 14:46, -2 votes)
Hello Kaggle Competition Team,

I am participating in the Google - The Gemma 4 Developer Agent Competition.
My submission, submission.zip, completed successfully and received a score of 0.05. However, I cannot determine why the score is so low because the submission details page does not provide task-level evaluation results or diagnostic logs.
I also tried downloading the submitted ZIP file using the download icon in the Submission Details page, but clicking the icon produces no response.
I would appreciate your help with the following questions:
Could you provide access to the evaluation logs or task-level results showing which tasks passed, which failed, and why?
Could you confirm whether my submitted archive was correctly extracted and whether agent.yaml, the prompt files, configuration files, and adapters were loaded as expected?
Could you clarify whether the score of 0.05 reflects the agent's actual performance or whether any configuration or evaluation issue may have affected the result?
Is there an alternative way to download the exact archive that was evaluated?
I would like to diagnose the problem before making further changes to my agent or using another submission attempt.
Thank you for your time and assistance.


---

## Submission Scoring Going on for 24+ hours
/competitions/gemma-4-developer-agent/discussion/747752 | by  | posted 2026-10-09 14:02 | last comment 2026-10-09 14:02 | 0 comments | 3 votes


**** (2026-10-09 14:02, 3 votes)
I am writing because my submission pipeline is currently completely blocked due to a backend synchronization glitch on my account. I cannot submit my new version, or even the old is not being stopped.
- Username: spiritofvishwakarma
- Link to page for version: https://www.kaggle.com/code/spiritofvishwakarma/gemma4-agent?scriptVersionId=356286952
So provide possible help for this.


---

## Time questionTime problem😅 
/competitions/gemma-4-developer-agent/discussion/747750 | by  | posted 2026-10-09 13:56 | last comment 2026-10-09 13:56 | 0 comments | 1 votes


**** (2026-10-09 13:56, 1 votes)
As far as I can see, I am not the only one, there are a few other people whose time has passed a long time

I'm not worried because my code is protected against time error, but other friends are victims🥲


---

##  Is anything kept between tasks in the scorer's sandbox, and may a submission rely on it?
/competitions/gemma-4-developer-agent/discussion/745975 | by  | posted 2026-10-05 15:41 | last comment 2026-10-09 12:59 | 1 comments | -1 votes


**** (2026-10-05 15:41, -1 votes)
Hi @ryanholbrook  -  could you clarify how container reuse works in the actual scorer?

The Overview describes a “persistent Docker container”, while HARNESS_README describes warm pooling with reuse_containers=True: after a task, /workspace, /tmp and /var/tmp are wiped before the container is returned to the pool. In swegemma 0.2.7, ContainerManager.stop also wipes /root, and reuse_containers defaults to False.

A few things that are not clear to us:
1. Does the scorer actually run with reuse_containers=True, so the same container may be used for multiple tasks?
2. If it does, should we nevertheless assume that every task starts from a completely clean environment? In particular, could anything written outside the directories being wiped survive into the next task?
3. Most importantly, are submissions allowed to make use of any state that happens to survive between tasks, or should submissions be designed not to rely on this at all?

We don’t want to build around behavior that is merely an implementation detail — or that would be considered outside the intended rules.
Thanks!
Mugur B.


**** (2026-10-09 12:59, 0 votes)
Have the same question


---

## Submission stuck for over a day
/competitions/gemma-4-developer-agent/discussion/747732 | by  | posted 2026-10-09 12:56 | last comment 2026-10-09 12:56 | 0 comments | 0 votes


**** (2026-10-09 12:56, 0 votes)
My submission has been stuck on "Notebook Running" for over a day, and I can't submit a new one.


---

## submission stuck since a day
/competitions/gemma-4-developer-agent/discussion/747718 | by  | posted 2026-10-09 12:13 | last comment 2026-10-09 12:50 | 2 comments | 2 votes


**** (2026-10-09 12:13, 2 votes)
submission stuck since a day


**** (2026-10-09 12:50, 0 votes)
Same here for more that 30Hrs


**** (2026-10-09 12:46, 0 votes)
same. mine is running for 21 hours


---

## stuck submission
/competitions/gemma-4-developer-agent/discussion/747714 | by  | posted 2026-10-09 12:07 | last comment 2026-10-09 12:12 | 1 comments | 1 votes


**** (2026-10-09 12:07, 1 votes)
My submission has been going for a day and now i cant do new submission![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F23041763%2Fe5b24c360a0c8eb2e46d25751d0c3e5c%2Fsubfail.png?generation=1791547644823349&alt=media)

Any admin can help?


**** (2026-10-09 12:12, 0 votes)
Me too, 30h


---

## Questions on sandbox/competition setup
/competitions/gemma-4-developer-agent/discussion/747704 | by  | posted 2026-10-09 11:33 | last comment 2026-10-09 11:33 | 0 comments | 1 votes


**** (2026-10-09 11:33, 1 votes)
Hi all, few questions about scoring and the competition harness:
1. Sandbox backend: does inference run task sandboxes with the subprocess backend or with Docker?
2. Filesystem: may an agent write files outside its task workspace (e.g. /tmp), and do such files persist across tasks?

Thanks!


---

## Time, Budget, and Thinking: Gemma 4 Coding-Agent Experiments
/competitions/gemma-4-developer-agent/discussion/747696 | by  | posted 2026-10-09 11:03 | last comment 2026-10-09 11:03 | 0 comments | 8 votes


**** (2026-10-09 11:03, 8 votes)
My local setup uses four Alibaba PPU cards. I am sharing experiments on time limits, tool-call budgets, thinking, and coding-task resolution.

The frozen-version Gemma experiments use the competition base model without LoRA; older, unrecovered configurations are flagged separately. Resolved counts are raw local test passes; Public LB is reported separately. Historical runs used different card counts and concurrency. Time limits are configured/charged local minutes with simulated competition timing.

## Public v19 Code

- [Original scored v19 Code - Public LB 0.17, Version 1](https://www.kaggle.com/code/yiyu0716/g4-pack-yiyu-v19-fixed-trace-t7p5?scriptVersionId=356344238)
- [Complete v19 source Notebook - all 11 harness files](https://www.kaggle.com/code/yiyu0716/g4-v19-complete-harness-source)

The 0.17 score belongs to the original 7.5-minute submission. The source Notebook displays the complete files and exports the unchanged ZIP; it is not a separately scored submission.

## Version Changes

v6.2-v6.6 hard guards are local-only; v22's added clock correction is also local-only. v23 inherits its evaluation.

| Version | Based On | One-Sentence Change | Public LB |
| --- | --- | --- | --- |
| v2 | Original baseline | Use native editing tools with an analyzer subagent. | 0.13 |
| v3 | v2 | Remove the analyzer's three graph tools. | 0.08 |
| v4 | v2 | Replace native editing with a two-stage safe-edit skill. | - |
| v4.1 | v4 | Clarify the skill's outer argument format. | - |
| v5 | v2 | Add a prompt-driven protected-file check before submission. | - |
| v6 | v2 | Put analysis and editing into a shared Runner workflow. | - |
| v6.1 | v6 | Make the editor the root agent so continuation retains editing tools. | 0.13 |
| v6.2 | v6.1 | Limit analysis calls and reserve call allowances for editing. | - |
| v6.3 | v6.1 | Reject unknown tool arguments before execution. | - |
| v6.4 | v6.1 | Enforce workflow transitions and termination after submission. | - |
| v6.5 | v6.4 | Fix synthetic transfer IDs in the workflow guard. | - |
| v6.4-fixed | v6.4 | Repeat the same transfer-ID fix used in v6.5. | - |
| v6.6-a | v6.1 + v6.3 + fixed workflow | Combine argument validation with corrected workflow guards. | - |
| v6.6-b | v6.1 + v6.3 + fixed workflow | Repeat the same combined implementation as v6.6-a. | - |
| v6.4-fixed-lb | v6.1 | Replace host workflow guards with skills and completion receipts. | - |
| v6.4-fixed-lb2 | v6.4-fixed-lb | Fix path-glob matching. | - |
| v6.4-fixed-lb3 | v6.4-fixed-lb2 | Improve recovery when a written plan lacks its completion receipt. | - |
| v6.6-lb | v6.1 | Rebuild the local combination through submission-supported skills. | - |
| v6.6-lb2 | v6.6-lb | Fix path-glob matching. | - |
| v6.6-lb3 | v6.6-lb2 | Improve recovery when a written plan lacks its completion receipt. | - |
| v7 | v2 | Request checked Shell recovery after the first editing failure. | - |
| v8 | v2 | Replace native editing entirely with run_command. | - |
| v9 | v2 | Replace the analyzer's read_file with Shell-based reading. | - |
| v10 | v6.1 | Add native-command checks and recovery for protected-file changes. | - |
| v11 | v6.1 | Shorten the prompt while retaining native editing and Shell recovery. | 0.13 |
| v12 | v6.1 | Introduce single-string SEARCH/REPLACE editing through g4edit. | - |
| v13 | v12 | Increase temperature from 0.2 to 1.0 and top-k from 40 to 64. | - |
| v14 | v12 | Make the analyzer tool-free and responsible only for planning. | - |
| v15 | v13 | Strengthen installation, edit checks, and repeated-error feedback. | - |
| v16 | v13 | Use sed in analysis and reduce the root output cap to 2,048. | - |
| v17 | v15 | Apply the same reading and output-cap changes on the v15 base. | - |
| v18 | v17 | Restore explicit verification and add optional execution tracing. | 0.10 |
| v19 | v18 | Make tracing a prescribed localization step in both prompts. | 0.17 |
| v19th | v19 | Enable 4,096-token thinking in both agents and raise output caps to 6,144. | - |
| v19ta | v19 | Enable 512-token thinking only in the analyzer and raise its output cap to 2,560. | - |
| v20 | v19 | Remove the analyzer workflow and move localization to the root agent. | - |
| v20t | v20 | Enable 4,096-token thinking and increase the root output cap to 6,144. | - |
| v21 | v19 | Add elapsed-time feedback and reminders to edit and finish. | - |
| v22 | v21 | Correct time feedback using locally recorded uncharged inference delays. | - |
| v23 | Public Budget-Fit | Register the unchanged single-agent package and inherit its evaluation. | - |
| v24 | v23 | Increase temperature to 1.0 and explicitly set top-k to 64. | - |

## Results: 31-Task Validation Set

Public LB checked with my Kaggle account on 2026-10-09 17:17:29 China Standard Time (UTC+8). A dash means no verified score, not zero. v19 is shown as one version with its best verified Public LB of 0.17, obtained from the 7.5-minute submission; local evaluation budgets remain listed separately.

Comma-separated values are separate attempts. P = partial; a dash means no separate result, not zero. The exact denominator is retained for interrupted runs.

| Version | Minutes/Task | Resolved by Attempt | Session Timeouts | Empty Patches | Public LB |
| --- | --- | --- | --- | --- | --- |
| v2 | 15 | 13/31, 11/31 | 2, 3 | 4, 5 | 0.13 |
| v3 | 8 | 13/31, 11/31 | 9, 7 | 5, 5 | 0.08 |
| v4 | 15 | 11/31 | 0 | 10 | - |
| v4.1 | 15 | 10/31 | 1 | 10 | - |
| v5 | 15 | 9/31, 13/31 | 1, 1 | 7, 6 | - |
| v6 | 15 | 11/31, 15/31 | 3, 1 | 7, 1 | - |
| v6.1 | 15 | 13/31 | 3 | 3 | 0.13 |
| v6.2 | 15 | 13/31, 12/31 | 3, 3 | 4, 8 | - |
| v6.3 | 15 | 15/31, 13/31 | 1, 0 | 3, 2 | - |
| v6.4 | 15 | 4/31 | 0 | 21 | - |
| v6.5 | 15 | 14/31, 12/31 | 4, 1 | 4, 2 | - |
| v6.4-fixed | 15 | 16/31 | 1 | 2 | - |
| v6.6-a | 15 | 14/31, 16/31 | 3, 1 | 1, 3 | - |
| v6.6-b | 15 | 14/31, 16/31 | 3, 0 | 2, 3 | - |
| v6.4-fixed-lb | 15 | 4/4 P | 0 | 0 | - |
| v6.4-fixed-lb2 | 15 | 7/30 P | 0 | 18 | - |
| v6.4-fixed-lb3 | 15 | 7/31, 8/31 | 5, 3 | 17, 15 | - |
| v6.6-lb | - | - | - | - | - |
| v6.6-lb2 | - | - | - | - | - |
| v6.6-lb3 | 15 | 7/31, 8/22 P | 3, 3 | 19, 10 | - |
| v7 | 15 | 13/31, 9/31 | 0, 3 | 7, 7 | - |
| v8 | 15 | 9/31 | 4 | 8 | - |
| v9 | 15 | 10/31, 14/31 | 1, 1 | 6, 2 | - |
| v10 | 15 | 11/31, 15/30 P | 4, 1 | 4, 2 | - |
| v11 | 15 | 13/31, 12/31 | 1, 1 | 1, 7 | 0.13 |
| v12 | 15 | 13/31, 13/31 | 1, 0 | 5, 5 | - |
| v13 | 15 | 17/31, 17/31 | 1, 1 | 1, 2 | - |
| v14 | 15 | 15/31, 12/31 | 0, 0 | 3, 2 | - |
| v15 | 15 | 15/31, 14/31 | 1, 1 | 1, 2 | - |
| v16 | 15 | 13/31, 16/31 | 3, 2 | 2, 0 | - |
| v17 | 15 | 14/31, 13/31 | 0, 0 | 2, 1 | - |
| v18 | 15 | 16/31, 16/31 | 0, 0 | 0, 2 | 0.10 |
| v19 | 15 | 14/31, 18/31 | 1, 1 | 1, 1 | 0.17 |
| v24 | 8 | 15/31 | 7 | 3 | - |

v6.5 and v6.4-fixed are the same corrected workflow; v6.6-a and v6.6-b are also equivalent implementations. Do not interpret their labels as independent strategies.

v6.4 includes a protocol failure, not a clean strategy comparison. v6.1's initial 13/31 is a standalone run; v19's 31-task rows are phases of the 129-task runs, not extra rounds.

## Results: 129 Public Tasks

The 31-task column is a subset of each 129-task run, not an additional evaluation. Budget-prefixed entries retain separate local conditions within one version row. Versions not listed have no complete 129-task Gemma result in the archived evidence.

| Version | Minutes/Task | Tool-Call Cap | Thinking Budget | Resolved by Run | 31-Task Subset | Session Timeouts | Empty Patches | Public LB |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| v6.1 | 15 | 100 | Off | 41/129, 39/129 | 16/31, 13/31 | 5, 10 | 15, 16 | 0.13 |
| v19 | 15; 8 | 100 | Off | 15m: 44/129, 49/129; 8m: 44/129 | 15m: 14/31, 18/31; 8m: 16/31 | 15m: 3, 7; 8m: 28 | 15m: 9, 15; 8m: 20 | 0.17 |
| v19th | 15 | 100 | Both agents: 4,096 | 47/129 | 17/31 | 49 | 28 | - |
| v19ta | 15 | 100 | Analyzer only: 512 | 47/129 | 18/31 | 40 | 28 | - |
| v20 | 8 | 100 | Off | 37/129 | 13/31 | 32 | 34 | - |
| v20t | 8 | 100 | Root: 4,096 | 37/129 | 15/31 | 75 | 57 | - |
| v21 | 8 | 100 | Off | 45/129, 42/129 | 17/31, 15/31 | 10, 16 | 14, 20 | - |
| v23 I | 8 | 28 | Root: 4,096 | 47/129 | 18/31 | 30 | 14 | - |

v19's 15-minute totals combine a 31-task phase and a separate 98-task phase. v23 inherits one evaluation of the byte-identical [Budget-Fit baseline](https://www.kaggle.com/code/verracodeguacas/gemma-4-agent-budget-fit-single-agent); it was not rerun as an independent v23 evaluation.

## Other Results

v19 harness, the same 129 public tasks, and a configured 15-minute budget per task.

| Model | Runs | Resolved by Run | Pass Rate by Run |
| --- | --- | --- | --- |
| Gemma 4 | 2 | 44/129, 49/129 | 34.11%, 37.98% |
| DeepSeek API (requested model: deepseek-flash) | 1 | 66/129 | 51.16% |

DeepSeek's result combines the two-task smoke test and the remaining 127 tasks once. API decoding and latency differ from local Gemma, so this is a backend reference comparison, not a controlled model-only ablation or an LB result.

## Discussion Questions

The inference-time limit feels very tight to me. Competitive experimentation may require substantial compute, but generating teacher-model traces through paid APIs is also too expensive for my budget. I see this competition as a production-grade, end-to-end challenge spanning compute, inference, harness design, modeling, data construction, and training.

I would like to hear how others approach these questions:

- Inference time: how do you balance thinking, tool use, editing, and verification under the deadline?
- Harness design: which workflows help agents produce correct repairs reliably within the budget?
- Modeling and training: which solutions are practical with limited compute?
- Data construction: how do you build useful, budget-aligned training trajectories affordably?
- Teacher selection: which models offer the best trace quality per dollar, and when do local teachers make more sense?


---

##  Submission 56947406 stuck in PENDING for 20+ hours and previous submissions throw kaggle error.
/competitions/gemma-4-developer-agent/discussion/747641 | by  | posted 2026-10-09 07:14 | last comment 2026-10-09 08:33 | 1 comments | 6 votes


**** (2026-10-09 07:14, 6 votes)
Issue Summary:
 
1. 20+ Hours Stuck in PENDING: Submission 56947406 has been in SubmissionStatus.PENDING for over 20 hours.
2. Prior Ingestion Failures: My two prior submissions also failed:

 • 56896526 (2026-10-07 01:28 UTC) – "A system error. Please try resubmitting to resolve the error..."

 • 56917263 (2026-10-07 17:17 UTC) – "A system error. Please try resubmitting to resolve the error..."

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F31442040%2F2c70b4e3685c8b21d01a562b33649d06%2FScreenshot_20261009_124211.png?generation=1791530125109778&alt=media)

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F31442040%2Fdaf83785d8bf804a72f15125d5620755%2FScreenshot_20261009_123018.png?generation=1791530137590364&alt=media)


**** (2026-10-09 08:33, 0 votes)
https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747519?_gl=1*1wculy1*_ga*MjEzNzUzODU3NC4xNzg5MTUxMTM0*_ga_T7QHS60L4Q*czE3OTE1MzIwMDMkbzQwJGcxJHQxNzkxNTM0NTQ1JGo0MyRsMCRoMA Is it included in the error?


---

## Local evaluation failure report: Gemma 4 baseline
/competitions/gemma-4-developer-agent/discussion/745882 | by  | posted 2026-10-05 04:17 | last comment 2026-10-09 08:26 | 2 comments | 2 votes


**** (2026-10-05 04:17, 2 votes)
## Summary

We evaluated all 129 supplied tasks locally. The run resolved 31 tasks (24.03%) and did not resolve 98 (75.97%).

Some failures include test-environment errors. These results must not be interpreted as 98 confirmed model implementation failures. This report does not establish that Kaggle's official environment has the same problems.

## Run configuration

| Setting | Value |
| --- | --- |
| Model | gemma-4-31b-it-qat-w4a16-ct |
| Agent | Local sample_submission agent and its two sample adapters |
| Time limit per task | 60 minutes |
| Tool-call limit | 100 |
| Turn limit | 500 |
| Command timeout | 300 seconds |
| Concurrency | 32 tasks across six model endpoints |
| Model context window | 65,536 tokens |
| Container Python | 3.13 |
| Test environment | Local Docker sandbox |

The agent prompt and adapters were copied from the local sample_submission. Their identity with the published originals has not been independently verified. This is not a controlled reproduction of all official evaluation settings.

## Observed failure markers

Counts are task counts, not individual test failures or API attempts. Each task is counted once within a row. A task can occur in multiple rows. Percentages therefore must not be added.

| Observed marker | Tasks | % of all 129 tasks | % of 98 unresolved tasks |
| --- | ---: | ---: | ---: |
| Any package installation/import marker | 37 | 28.68% | 37.76% |
| Missing inline-snapshot | 27 | 20.93% | 27.55% |
| Missing dirty-equals | 9 | 6.98% | 9.18% |
| python-multipart installation/detection error | 6 | 4.65% | 6.12% |
| Missing attr | 1 | 0.78% | 1.02% |
| Recursive httpbin fixtures | 7 | 5.43% | 7.14% |
| Network unreachable | 7 | 5.43% | 7.14% |
| 60-minute session timeout | 12 | 9.30% | 12.24% |
| Test comparisons/assertions failed | 41 | 31.78% | 41.84% |
| Test-output errors (selected exception types) | 18 | 13.95% | 18.37% |
| Agent patch modified tests/ | 3 | 2.33% | 3.06% |
| Evaluation test-patch application failure | 1 | 0.78% | 1.02% |
| Context-window overflow | 1 | 0.78% | 1.02% |
| Test-command timeout | 1 | 0.78% | 1.02% |
| Test process exit 137 (cause unconfirmed) | 2 | 1.55% | 2.04% |

“Test-output errors” groups SyntaxError, NameError, AttributeError, TypeError, ImportError, FileNotFoundError, IndexError, and MissingStyle. The labels describe output markers, not verified root causes. Exception text can appear in an expected-error test, so this row is a diagnostic signal, not an automatic attribution of blame.

## Environment concerns for organizer confirmation

### FastAPI test packages

Existing tests import inline_snapshot and dirty_equals. The supplied fastapi_14978 snapshot declares dirty-equals >=0.9.0 and inline-snapshot >=0.21.1 in pyproject.toml. The packages were unavailable during some local test runs.

Six tasks report that python-multipart must be installed. This message can indicate an installation, version, or detection problem. We have not confirmed package absence in each affected container. One task cannot import attr.

We have not installed these packages as a workaround for this run. We want to confirm the intended setup first.

### Requests test fixtures and network

Seven tasks report both recursive httpbin/httpbin_secure fixture dependencies and network errors, including Errno 101 (Network is unreachable). These are the same seven tasks; they are not 14 separate affected tasks.

Fixture-provider setup and network requirements need confirmation. We have not established whether the cause is a missing plugin, plugin loading, sandbox policy, or another setup issue.

## Other observed failures

- Some patches omit required project modules, symbols, parameters, or fields. A missing project module is not necessarily an external dependency issue.
- Some patches produce incorrect error messages, route behavior, dependency scopes, Unicode widths, or terminal output.
- Syntax-highlight color snapshots differ in several cases. Package-version effects have not been ruled out.
- Twelve tasks reached the 60-minute limit. Some also have environment errors.
- One request exceeded the 65,536-token context limit: at least 49,153 input tokens plus 16,384 requested output tokens.
- One task modified tests/test_highlighter.py and then could not apply the evaluator test patch.
- Two test processes returned exit code 137. No system evidence was collected to confirm an out-of-memory cause.

## Questions for the organizers

1. Which repository test dependencies are installed automatically, and at which setup step?
2. Does the official environment supply inline-snapshot, dirty-equals, python-multipart, and attrs?
3. How should local evaluation configure the httpbin fixtures and required network access?
4. Is there a pinned dependency manifest or supported image that reproduces the official environment?
5. How does the official evaluator distinguish environment failures from implementation failures?

## Evidence and limitations

The report is based on final task_results.jsonl and the per-task test output in summary.json. Per-task logs and traces are retained locally. The detailed table of all 98 unresolved tasks is in TROUBLESHOOTING.md.

No evaluation tests or scores were changed for this report. No hidden-test feedback was added to the agent. Fixing an environment problem would not establish that the affected patch passes. Other errors can occur in the same task.

## Affected task IDs by marker

### Any package installation/import marker

`fastapi_11194`, `fastapi_11355`, `fastapi_12942`, `fastapi_13207`, `fastapi_13537`, `fastapi_13713`, `fastapi_13786`, `fastapi_14099`, `fastapi_14186`, `fastapi_14246`, `fastapi_14262`, `fastapi_14266`, `fastapi_14297`, `fastapi_14303`, `fastapi_14349`, `fastapi_14356`, `fastapi_14360`, `fastapi_14361`, `fastapi_14371`, `fastapi_14430`, `fastapi_14455`, `fastapi_14459`, `fastapi_14482`, `fastapi_14485`, `fastapi_14512`, `fastapi_14583`, `fastapi_14605`, `fastapi_14616`, `fastapi_14791`, `fastapi_14953`, `fastapi_14962`, `fastapi_14964`, `fastapi_14978`, `fastapi_15023`, `fastapi_15030`, `fastapi_15745`, `rich_3472`

### Missing inline-snapshot

`fastapi_11355`, `fastapi_13207`, `fastapi_14099`, `fastapi_14186`, `fastapi_14246`, `fastapi_14262`, `fastapi_14266`, `fastapi_14297`, `fastapi_14349`, `fastapi_14361`, `fastapi_14371`, `fastapi_14430`, `fastapi_14455`, `fastapi_14459`, `fastapi_14482`, `fastapi_14485`, `fastapi_14512`, `fastapi_14583`, `fastapi_14605`, `fastapi_14791`, `fastapi_14953`, `fastapi_14962`, `fastapi_14964`, `fastapi_14978`, `fastapi_15023`, `fastapi_15030`, `fastapi_15745`

### Missing dirty-equals

`fastapi_12942`, `fastapi_13713`, `fastapi_13786`, `fastapi_14303`, `fastapi_14356`, `fastapi_14360`, `fastapi_14371`, `fastapi_14605`, `fastapi_14791`

### python-multipart installation/detection error

`fastapi_11194`, `fastapi_13537`, `fastapi_14297`, `fastapi_14616`, `fastapi_14791`, `fastapi_14953`

### Missing attr

`rich_3472`

### Recursive httpbin fixtures

`requests_6589`, `requests_6592`, `requests_6629`, `requests_7328`, `requests_7433`, `requests_7502`, `requests_7505`

### Network unreachable

`requests_6589`, `requests_6592`, `requests_6629`, `requests_7328`, `requests_7433`, `requests_7502`, `requests_7505`

### 60-minute session timeout

`fastapi_12942`, `fastapi_14246`, `fastapi_14258`, `fastapi_14303`, `fastapi_14430`, `fastapi_14459`, `fastapi_14482`, `fastapi_14605`, `rich_3063`, `rich_3064`, `rich_3471`, `rich_4079`

### Test comparisons/assertions failed

`fastapi_13920`, `fastapi_14258`, `fastapi_14306`, `fastapi_14419`, `fastapi_14448`, `fastapi_14479`, `fastapi_14487`, `fastapi_14851`, `fastapi_14986`, `fastapi_15588`, `fastapi_15763`, `fastapi_15800`, `fastapi_5624`, `requests_7427`, `rich_3052`, `rich_3061`, `rich_3063`, `rich_3064`, `rich_3130`, `rich_3180`, `rich_3296`, `rich_3468`, `rich_3469`, `rich_3470`, `rich_3506`, `rich_3521`, `rich_3535`, `rich_3675`, `rich_3676`, `rich_3777`, `rich_3782`, `rich_3934`, `rich_3935`, `rich_3938`, `rich_3942`, `rich_3944`, `rich_3953`, `rich_4070`, `rich_4076`, `rich_4077`, `rich_4079`

### Test-output errors (selected exception types)

`fastapi_14186`, `fastapi_14262`, `fastapi_14306`, `fastapi_14448`, `fastapi_14978`, `fastapi_15030`, `fastapi_15280`, `fastapi_15745`, `fastapi_15785`, `fastapi_15800`, `requests_6757`, `rich_3061`, `rich_3471`, `rich_3486`, `rich_3930`, `rich_3938`, `rich_3942`, `rich_4070`

### Agent patch modified tests/

`fastapi_13537`, `fastapi_13786`, `rich_3454`

### Evaluation test-patch application failure

`rich_3454`

### Context-window overflow

`rich_3105`

### Test-command timeout

`rich_4006`

### Test process exit 137 (cause unconfirmed)

`rich_3480`, `rich_3772`


**** (2026-10-09 08:26, 0 votes)
😅 30 I did DKK, I think I noticed the shortcomings in the 13 hour cycle.


**** (2026-10-09 07:55, 0 votes)
What did you end up doing about this?


---

## Submission PENDING for over 27 hours
/competitions/gemma-4-developer-agent/discussion/747635 | by  | posted 2026-10-09 06:53 | last comment 2026-10-09 07:12 | 2 comments | 2 votes


**** (2026-10-09 06:53, 2 votes)
Submission __56931486__ in __gemma-4-developer-agent__, submitted on __2026-10-08 at 03:18:23 UTC__, has remained __PENDING for over 27 hours__, with no score or error message. It also blocks new submissions with “Your team already has 1 pending submissions; please wait for one to finish scoring,” despite an available daily quota. Could you check whether this evaluation job is stuck and advise how to proceed?


**** (2026-10-09 07:05, 0 votes)
I'm also experiencing the same problem 
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F26719890%2F6bec88907c404ff466465f5811155fd9%2FScreenshot%202026-10-09%20200354.png?generation=1791529472617585&alt=media)


> **** (2026-10-09 07:12, 1 votes)
> Haha, I'm not alone anymore!


---

## submission is running for 15h. is this due to evaluation ?
/competitions/gemma-4-developer-agent/discussion/746480 | by  | posted 2026-10-07 08:06 | last comment 2026-10-09 06:39 | 37 comments | 21 votes


**** (2026-10-07 08:06, 21 votes)
since the time limit is 12h why the notebook is running for 15h. 
is this normal?


**** (2026-10-07 10:00, 4 votes)
same, and it shows 'kaggle error'


**** (2026-10-07 08:50, 3 votes)
it finished and now its saying kaggle error. 
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F12607271%2F264adbc40a1b54b0d3822932300e6de6%2FScreenshot%202026-10-07%20at%202.19.51PM.png?generation=1791363007003992&alt=media)


**** (2026-10-08 15:21, 2 votes)
Someone please look into this. I'm not even sure what I'm doing wrong. My submission failed the last two times (different configs). Can the error message at least be a bit more descriptive?


**** (2026-10-07 13:07, 2 votes)
It happened with me too, the kegel error stuff.


**** (2026-10-07 13:06, 2 votes)
me too. 15h, then kaggle error.


**** (2026-10-07 09:24, 2 votes)
it's the same for me 15h then 'Kaggle error'


**** (2026-10-08 12:36, 1 votes)
Same issue here, three in a row, each ending with "A system error. Please try resubmitting…" after running well past 12 hours:

56862128 (Oct 5, 21:27 UTC)

56892091 (Oct 6, 22:27 UTC)

56919417 (Oct 7, 18:53 UTC, a resubmit of 56892091)

They are config-only bundles (no adapters or skills) with 4.0–4.5-minute task caps. Our earlier submissions with the same structure scored normally. @ryanholbrook, could you check these and rerun them or restore the slots? This is really messing up the competition deadline. Thanks!


**** (2026-10-07 09:26, 1 votes)
Same here


> **** (2026-10-07 11:15, 0 votes)
> update i see that my submissio is still scoring


> > **** (2026-10-07 15:17, 0 votes)
> > did error appeared ?


> > **** (2026-10-07 15:25, 0 votes)
> > it was already there when i go to my submissions


**** (2026-10-09 06:39, 0 votes)
I am facing the same issue (mine is running for 22 hrs )


**** (2026-10-08 22:05, 0 votes)
Please see: https://kaggle.com/competitions/gemma-4-developer-agent/discussion/747519


**** (2026-10-08 19:04, 0 votes)
Just pushing a bit more here https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/747369#3535426

Do you think I should delete my topic?


**** (2026-10-08 15:13, 0 votes)
Same here, twice: 56890546 (Oct 6, 20:43 UTC) and 56918840 (Oct 7, 18:26 UTC). Both ended with "A system error" after about 15 hours. Its the same config submitted twice.


**** (2026-10-08 14:23, 0 votes)
This is the second day in a row that this has happened to me, though I did get a grade yesterday.


**** (2026-10-08 13:50, 0 votes)
@ryanholbrook I get an error twice and lost my right to submit again, what I should do


**** (2026-10-08 13:22, 0 votes)
+1 Same here with 7th Oct submission


**** (2026-10-08 12:05, 0 votes)
Same here I got kaggle error twice and submission ran about 16 hours. I think as too many people have the submission running for more than 12 hours, there might be an issue on Kaggle's side.


**** (2026-10-08 11:03, 0 votes)
Same for us, twice in a row. 56891825 (Oct 6, 22:08 UTC) and 56918880 (Oct 7, 18:28 UTC) both ended with "A system error" after about 16-20 hours. Our Oct 5 submission 56844046 scored fine (0.08). Both new archives compile with the released wheelhouse and run end to end in our L4x4 notebook with the official Evaluator. Our worst-case estimate for the scorer is under 11 hours. @ryanholbrook is this on the platform side? Will these submissions be re-run?


**** (2026-10-08 10:40, 0 votes)
Kaggle Error

lost 15 hours. :)


**** (2026-10-08 08:11, 0 votes)
Same issue , Already happen two times-- after 15 h it shows kaggle error


**** (2026-10-08 08:08, 0 votes)
same issue, happen two times in a row. @ryanholbrook


**** (2026-10-08 07:54, 0 votes)
I also have the same issue.


**** (2026-10-08 07:36, 0 votes)
same issue. there are no error logs ?


**** (2026-10-07 21:32, 0 votes)
I've had this for 21 hours now, can I get some help, please?


**** (2026-10-07 17:58, 0 votes)
Same , I’m stuck at 15 hours but no error yet. Will these be automatically retried? I’m guessing it’s an error server side and not with the harness. @ryanholbrook would you be able to help debug please ?


**** (2026-10-07 17:57, 0 votes)
same here.


**** (2026-10-07 17:57, 0 votes)
My yesterday submission ended this way as well


**** (2026-10-07 17:24, 0 votes)
same here, it's over 17hr...


**** (2026-10-07 16:28, 0 votes)
I had the same: my Oct 6 submission ran for many hours and then ended with "Kaggle error".


**** (2026-10-07 15:23, 0 votes)
Same for me 😔


**** (2026-10-07 15:19, 0 votes)
what time limits u guys were using ?


**** (2026-10-07 13:47, 0 votes)
Same

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F523715%2Faca18d106c89994e70400aab2ddfd375%2F2026-10-07%20224711.png?generation=1791380859909620&alt=media)


**** (2026-10-07 13:20, 0 votes)
Had the same kaggle error issue, anyone able to fix it?


> **** (2026-10-07 13:40, 0 votes)
> nope, at least so far and there has been no response from anyone


---

## Kaggle Error — submission ID 56913370
/competitions/gemma-4-developer-agent/discussion/747101 | by  | posted 2026-10-08 05:37 | last comment 2026-10-09 02:01 | 5 comments | 0 votes


**** (2026-10-08 23:39, 0 votes)
Same here, @ryanholbrook. My last three submissions all ended with “A system error” after roughly 15 hours: 56889914 (Oct 6), 56895480 (Oct 7) and 56925429 (Oct 8). I don’t think I hit the 12-hour limit: my notebook runs take about 2 minutes per task on 4×L4, and the latest submission caps every task at 3 minutes, so 120 tasks should finish in about 6 hours plus setup. Like others in this thread and in “submission is running for 15h”, I can’t tell from the error whether the problem is on my side or the platform’s, which makes it hard to know whether to keep submitting. Any update on the cause, or guidance on how to proceed, would be much appreciated. Thanks!


**** (2026-10-08 07:56, 0 votes)
Same here.


**** (2026-10-08 07:50, 0 votes)
Same here, @ryanholbrook. Two submissions of the same archive failed with "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists.":

56891430, submitted 2026-10-06 21:49 UTC
56915152, submitted 2026-10-07 15:42 UTC (a byte-identical resubmit, same sha256)

Our previous archive (56845285, 5 Oct) scored normally. The new one changes only prompt text and drops two tools (read_file and edit_file) from agent.yaml. eval_config.yaml and sampling.yaml are byte-identical.

The archive validates and compiles with the released wheelhouse. It also ran all 57 trusted tasks end to end in a Kaggle notebook (L4x4, same model and wheels) without a single harness error.

Could you check whether these failed on the platform side or on something in our archive? If it's our archive, any hint at which stage failed (compile, inference or scoring) would let us fix it rather than spend submissions bisecting. And if it was platform-side, could the submissions be re-run? Thanks!


**** (2026-10-08 05:55, 0 votes)
in my submission also yesterday cause  kaggle error


**** (2026-10-08 05:37, 0 votes)
Hi @ryanholbrook, my submission **56913370** failed with "Kaggle Error", showing only "A system error." Could you please explain what exactly happened and why this submission failed? Thanks!


---

## HELP: Infra ERROR Kaggle
/competitions/gemma-4-developer-agent/discussion/747369 | by  | posted 2026-10-08 16:57 | last comment 2026-10-08 23:38 | 6 comments | 2 votes


**** (2026-10-08 16:57, 2 votes)
Hi @ryanholbrook, my two submissions ended in ERROR with “A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists.” after about 15 hours each, the same pattern reported in #746480:

* 56897000 (Oct 7, 01:50 UTC): prompt and config bundle with the two sample adapters, 10-minute task cap
* 56927643 (Oct 8, 01:27 UTC): prompt and config bundle with one rank-16 LoRA adapter, 8-minute task cap

Both archives compile with the current wheelhouse (adk-submission 0.2.12). The same adapter loads and serves normally in our 4×L4 notebook with vLLM 0.19.1, and the full runs there fit well within 12 hours. 
Could you check whether these were infrastructure failures and, if so, include them in the rerun or restore the slots? 

Thanks!


**** (2026-10-08 23:28, 0 votes)
Hi it seems that this is a problem that everyone has. I could see for my part that projects note error received a note 48 hours after . The best of things and not to touch the notebook and wait for the note in green.


> **** (2026-10-08 23:38, 0 votes)
> I really though that was me, but I could deploy in Colab without trouble. Thanks!


> > **** (2026-10-08 23:38, 0 votes)
> > Let's hope is fixed soon.


**** (2026-10-08 17:47, 0 votes)
Many of us experiencing the same, https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/746480 - no word from organizers yet.


> **** (2026-10-08 19:03, 0 votes)
> Where you able to submit before the errors? Is it something new?


> > **** (2026-10-08 19:07, 1 votes)
> > Yes, I think its an issue on kaggles side. I had many scored submissions before.


---

## vLLM's Gemma 4 tool-argument parser can loop forever on some malformed array arguments
/competitions/gemma-4-developer-agent/discussion/745138 | by  | posted 2026-10-02 13:30 | last comment 2026-10-08 18:43 | 2 comments | 0 votes


**** (2026-10-08 18:43, 0 votes)
Adding source-identified nested-array examples to D A M’s existing report. Thanks for reporting the non-advancing-index problem. @ryanholbrook: could the hosts check the additional case below against the pinned scoring runtime?

The competition wheelhouse contains `vllm-0.19.1-cp38-abi3-manylinux_2_31_x86_64.whl`. Its `vllm/tool_parsers/gemma4_tool_parser.py` member has SHA-256:

`682b2152b76c031df9c58c3ffbb5b243945be5d8957ebdce00faef1b9de6b889`

The following two synthetic argument strings reach a problematic branch of `_parse_gemma4_args`:

```text
args:[[<|"|>a]<|"|>,<|"|>b<|"|>]]
args:[[<|"|>replace<|"|>,<|"|>--path<|"|>,<|"|>rich/highlighter.py<|"|>,<|"|>--old<|"|>,<|"|>~]*)<|"|>,<|"|>--new<|"|>,<|"|>~@]*)<|"|>]]
```

These are argument strings for the parser, not model requests or reference solutions. In isolated CPU children, parsing each exceeded a two-second wall limit. Use a separate child process with a timeout when reproducing; no model or GPU is needed for this pure-function path.

At lines 256–266 of this exact member, the nested-array depth scanner counts square brackets inside the `<|"|>` string delimiter instead of skipping string contents. A `]` inside the string can therefore close the nested slice early. The later bare-value branch (lines 271–276) can encounter a closing bracket without advancing its index. The corresponding nested-object scanner already skips delimited strings (lines 240–244). Source reference: [vLLM v0.19.1 Gemma parser](https://github.com/vllm-project/vllm/blob/v0.19.1/vllm/tool_parsers/gemma4_tool_parser.py).

Could the hosts check whether the pinned scoring runtime contains this same implementation, and whether a parser correction or guard is appropriate? The harness README documents `tool_call_parser='gemma4'`, so this seems relevant to the scoring environment.

Scope: this report is a source-bound, synthetic parser reproduction. It does not identify the completion responsible for any historical service outage, prove a real-service failure, or assume all scoring tasks share one server process. No private competition outcomes, traces, Agent patches or scores are included.


**** (2026-10-08 15:59, 0 votes)
Correction to the count above: with the string generator seeded (seed 7, 60,000 strings), `_parse_gemma4_args` never returns on 74 strings, not 85. The two parsers agree on the other 59,926. The minimal examples and the cause are unchanged. The corrected numbers are also in the kit README: https://github.com/damsolanke/gemma4-swe-kit


**** (2026-10-02 13:30, 0 votes)
Hi @ryanholbrook,

While building a local stand-in for the scoring server, we compared vLLM 0.19.1's Gemma 4 tool parser (the `gemma4_tool_parser.py` from the competition wheel) against a reimplementation on 60,000 fuzzed call strings. On 74 of them (string generator seeded with 7), `_parse_gemma4_args` never returns. All 74 are array arguments where a string delimiter breaks the bracket matching. Minimal examples (run in a subprocess with a timeout):

```
x:[a<|"|>]
x:[a<|"|>]<|"|>]
x:[btrue<|"|>-1]1<|"|>:\n{
```

`x:[<|"|>a]b<|"|>]` parses fine (`{'x': ['a]b']}`), so the trigger is a delimiter that opens inside an array item and never closes before the bracket. The loop sits in the array branch: an item position whose next character is `]` never advances the index.

Why it might matter on the scorer: the parser runs inside the API server, so a single generation like this could stall that request until the task's time limit, or longer if the server's event loop is blocked. None of our own runs has produced such a call (our tools take no array arguments), but agents that expose array-typed tools, such as lists of symbols for the code-graph tools, could hit it.

A guard that raises on a non-advancing index (or a timeout around tool parsing) would turn it into an ordinary parse failure. Repro script: a few lines, happy to share.

Edited Oct 12: the count was 85 in the first version of this post; with the seeded generator it is 74, as in the comment below.


---

## LoRA adapters are silently wiped in the patched vLLM 0.19.1 (Gemma4 decoder layers registered twice)
/competitions/gemma-4-developer-agent/discussion/743508 | by  | posted 2026-09-26 06:03 | last comment 2026-10-08 18:10 | 6 comments | 5 votes


**** (2026-09-26 06:03, 5 votes)
Tested with the patched vllm 0.19.1 from `metric/gemma-4-developer-agent-wheelhouse` (uploaded 2026-09-25). This is the build whose `gemma4.py` / `gemma4_mm.py` add `SupportsLoRA` to `Gemma4ForConditionalGeneration`. With it, `--enable-lora --lora-modules name=path` starts fine and the adapter is reported as loaded. **But the adapter has no effect on the outputs.**

**Cause**

Gemma4Model registers every decoder layer twice:
- once as `language_model.model.layers.N`;
- once through the YOCO alias `language_model.model.self_decoder.decoder_layers.N`. `Gemma4SelfDecoderLayers` keeps a slice of the same `ModuleList` as a submodule, and it is built even when `kv_sharing_fast_prefill` is off.

`LoRAModelManager.activate_adapter` iterates over both names:
1. Under `layers.N` it finds the adapter weights and calls `set_lora`.
2. Under the alias name the adapter has no weights, so it calls `module.reset_lora(index)` on the same layer object. This wipes the weights it has just set.

**Repro**

1. Take any adapter for `gemma-4-31b-it-qat-w4a16-ct` and set every `lora_B` to large random values (std 1.0).
2. Serve it with the patched vLLM and `--enable-lora`.
3. Compare the top logprobs for the base model name and the adapter name on the same prompt at temperature 0. They are identical.
4. With `VLLM_LOGGING_LEVEL=DEBUG`, the log shows 240 lines of `Successfully loaded LoRA weights for module language_model.model.layers.N...`, followed by 240 lines of `No LoRA weights found for module language_model.model.self_decoder.decoder_layers.N..., skipping.`
5. Inspecting the LoRA layers afterwards shows that every `lora_b_stacked` slot is zero.

**Possible fixes**

- Store `decoder_layers` in `Gemma4SelfDecoderLayers` / `Gemma4CrossDecoderLayers` without registering them as submodules. The patch already does this for `embed_tokens` and the other shared modules via `self.__dict__[...]`.
- Or skip `reset_lora` for a module object that already received weights under another name.

This affects any submission that ships an adapter, because it would score exactly like the base model. It is separate from the earlier "does not support LoRA yet" startup error discussed in https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743213.


**** (2026-10-08 18:10, 0 votes)
Thanks for the fixes. I re-tested on the current wheelhouse (`adk_submission` 0.2.12 and the patched vLLM 0.19.1 wheel from 2026-09-30). The memory problem is solved, but the adapter weights still don't change the model's output. The cause now looks different from the double registration.

**Setup.** Kaggle 4× L4, the Getting Started image, `VllmServer` + `discover_adapters(<submission root>)` with the scorer values (`gpu_memory_utilization=0.80`, `max_model_len=32768`). The submission has two adapters, both built from the sample `main_lora` (rank 4, `q_proj`/`o_proj`, layer 0) with `lora_B` replaced by noise: `test_lora` N(0, 1e-3) and `loud_lora` N(0, 1).

**What now works:**
- LoRA is sized from the submission (`max_loras=2`, `max_lora_rank=8`). Model loading takes 6.06 GiB/GPU, the KV cache is 27,696 tokens, and the server starts.
- `/v1/models` lists both adapters, and harness requests are routed to the adapter.
- With `VLLM_LOGGING_LEVEL=DEBUG`, activating `loud_lora` logs `Successfully loaded LoRA weights for module language_model.model.layers.0.self_attn.qkv_proj` and `...o_proj`, and `No LoRA weights found ..., skipping` for every other module. There are no `self_decoder` lines any more, so the reset-after-set described in this thread is gone.

**What's still broken:** at temperature 0 with thinking off, the base model, `test_lora` and `loud_lora` all answer "List the first ten prime numbers" with the identical `2, 3, 5, 7, 11, 13, 17, 19, 23, 29`, and their per-token logprobs agree within 1e-6. It's the same with `--enforce-eager` (no CUDA graphs): within 7e-7. With `lora_B ~ N(0, 1)` on layer 0, a working LoRA path should change the output completely, so the weights seem to be set but not used in the forward pass.

Can you reproduce this on your side, and does the scorer run the same build? Happy to share the notebook.


**** (2026-09-29 10:55, 0 votes)
Following up with a reproduction on the current Wheelhouse, in case it helps.

**Setup:** Kaggle notebook, GPU L4 x4, Internet off · Wheelhouse dataset version [N] (vLLM 0.19.1) · gemma-4-31b-it-qat-w4a16-ct v2 · adapter = the `sample_submission/adapters/[main_lora]` adapter with its `lora_B` weights replaced by N(0, 1) noise, so any working LoRA path should visibly change the output.

**1. Through `adk_submission.VllmServer`** (`enable_lora=True, max_loras=8, max_lora_rank=128`, adapter passed via `discover_adapters` → `adapter_manifest`): `/v1/models` lists only the base model, no LoRA entry. With `VLLM_ALLOW_RUNTIME_LORA_UPDATING=True` set before startup, `POST /v1/load_lora_adapter` returns 404.

**2. Directly in vLLM, bypassing the server:**

```python
llm = LLM(model=MODEL_PATH, tensor_parallel_size=4, max_model_len=4096,
          enable_lora=True, max_loras=1, max_lora_rank=128)
sp = SamplingParams(temperature=0, max_tokens=40, logprobs=3)
base = llm.chat(PROMPT, sp)
lora = llm.chat(PROMPT, sp, lora_request=LoRARequest("loud_lora", 1, ADAPTER_PATH))
```

Base and LoRA outputs are identical: same text ("2, 3, 5, 7, 11, 13, 17, 19, 23, 29") and same logprobs. vLLM does handle the request (it logs its LoRA-tokenizer warning), so the adapter seems to load but have no effect.

Caveat: I only randomised `lora_B`. If the sample adapter's `lora_A` is all zeros, that alone would explain it. I'll re-run with both A and B randomised and post the result.

Two questions:
1. Is the zeroing fix meant to be in the current Wheelhouse, or only on the scorer?
2. Should the harness server list the adapter in `/v1/models` when it's in `adapter_manifest`?

Thanks!


> **** (2026-09-30 14:34, 0 votes)
> 1. The zeroing fix landed in v23 of the wheelhouse dataset (now on v25). You might check that your notebook has the most recent version.
> 2. Yes, it should. `discover_adapters` expects the submission root, so make sure you're passing that and not the adapter directory.


**** (2026-09-26 11:19, 0 votes)
Thanks for the report. I will address.


> **** (2026-09-30 12:53, 0 votes)
> Is there an update on this @ryanholbrook? Appreciate all the help but I think this is a serious bug for anyone attempting to use adapters.


> > **** (2026-09-30 14:34, 0 votes)
> > It should be fixed in the most recent wheelhouse version, but please let me know if it seems otherwise.


---

## gemma4-swe-kit: open-source local evaluation tools that behave like the scorer's vLLM
/competitions/gemma-4-developer-agent/discussion/745143 | by  | posted 2026-10-02 13:56 | last comment 2026-10-08 16:51 | 1 comments | 2 votes


**** (2026-10-02 13:56, 2 votes)
I have published the tools we use to test agents locally before spending a submission: https://github.com/damsolanke/gemma4-swe-kit (Apache 2.0). I am posting it here because the rules ask that publicly shared competition code also be shared on this forum.

What is in it:

- **g4kit-proxy**: an OpenAI-compatible endpoint over Ollama (raw mode) or MLX that renders requests with the Gemma 4 chat template the way vLLM 0.19 does and parses calls with vLLM's gemma4 parser. A malformed call stays in the content, so the harness nudges exactly as on the scorer. A prompt plus max_tokens over 32,768 is rejected as vLLM rejects it, so a sub-agent overflow empties the patch locally too. thinking_budget is enforced as a hard cap.
- **g4kit-fake-llm**: a scripted model that walks every agent and the core harness tools of a submission through the real harness in seconds, without a GPU.
- **g4kit-scorer-time**: projects scorer hours for about 120 tasks from the per-call token counts of a local run.
- **g4kit-replay** and **g4kit-log-stats**: resend logged decision points under prompt or sampling changes with paired tests, and count loops, failed edits, malformed calls and overflows in proxy logs.
- **g4kit-convert-openhands** and **g4kit-render-distill**: turn nebius/SWE-rebench-openhands-trajectories (CC BY 4.0, attribution in NOTICE) into training windows rendered as the scorer would render them.

The kit does not ship the chat template or vLLM's parser file. g4kit-assets downloads and fingerprints both. The README lists what we measured with these tools. One example: with shell commands written as examples in the prompt, 31% of replayed calls at known failure points came out as malformed tool names, against 5% with the commands described in prose. The vLLM parser hang from topic 745138 is detected by the proxy.

Bug reports and pull requests are welcome.


**** (2026-10-08 16:51, 0 votes)
Update: kit v0.2.0 and the data behind it, both public today.

Data, as a Kaggle dataset under CC BY 4.0: the converted SWE-rebench trajectories in the harness's tool format (3,586), the curated subset (1,427) and every trajectory's curation score. https://www.kaggle.com/datasets/adesolanke/gemma4-swe-agent-trajectories. It is derived from SWE-rebench OpenHands trajectories by Nebius (CC BY 4.0), generated by Qwen3-Coder-480B-A35B-Instruct; the dataset card lists the changes.

New in [gemma4-swe-kit](https://github.com/damsolanke/gemma4-swe-kit):
- `g4kit-curate`: deterministic scoring and selection of converted trajectories (rebuilds the curated file byte for byte)
- `g4kit-render-distill --mask-error-turns`: no loss on turns whose call hit a tool error
- `g4kit-train-mlx`, `g4kit-mlx-to-peft`, `g4kit-check-peft`: LoRA on Apple Silicon, exported in the layout vLLM loads
- `examples/tpu`: a LoRA trainer for the free Kaggle TPU v5e-8
- `g4kit-canary`: checks that a LoRA adapter served by vLLM actually changes the logits
- `tools/fuzz_vllm_parser.py`: reproduces the 74 parser hangs


---

## Submission errors after the Sep 30 wheelhouse update
/competitions/gemma-4-developer-agent/discussion/744807 | by  | posted 2026-10-01 02:01 | last comment 2026-10-08 16:31 | 22 comments | 21 votes


**** (2026-10-01 02:01, 21 votes)
Hello @ryanholbrook, 

My submission, 56722615, stopped after about 20 minutes with "Your notebook hit an unhandled error while rerunning your code." It's my first upload since the September 30 wheelhouse update. My earlier submissions scored normally, and this one validates and runs fine locally. Any idea what went wrong?


**** (2026-10-01 10:33, 5 votes)
Yes this is an issue. My submission id: 56747946

Also I think if the daily submission limit is 1, we should only count it towards a successful submission. Anything that's infra related should not be counted towards a submission.

2ndly It would be nice to know what's the underlying stack that's running:
- does inference recover itself in case it goes down?
- does sandboxes have retries as well?

I think a bit more clarity on how the infrastructure is designed/wired together will help.


**** (2026-10-01 03:57, 3 votes)
Same here: submission 56726945 (2026-10-01 00:06 UTC) ended with "Your notebook hit an unhandled error while rerunning your code" and no score. It validates locally with the Sep 30 wheelhouse.

@ryanholbrook could you check what raised, and let us know when it is safe to resubmit? Thanks!


**** (2026-10-01 14:45, 2 votes)
We had a GPU outage overnight. Resolved now, and submissions should be working again.


> **** (2026-10-01 16:37, 6 votes)
> would be great if the failed runs are started again or the daily limit be reset!


> **** (2026-10-03 01:43, 0 votes)
> Hi @ryanholbrook, same issue on Oct 3. Both notebooks ran COMPLETE (344s / 679s, local validator passed, model `gemma-4-31b-it-qat-w4a16-ct`), but both submissions ended as `SubmissionStatus.ERROR` with only the generic "A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists." and no score:
> - 56784230 (Getting Started notebook, 2026-10-03T00:00:13Z)
> - 56785158 (Gemma 4 SuperAgent, 2026-10-03T00:16:03Z)
> Bundles validate locally (UTF-8 clean, no BOM, agent.yaml at zip root). Could you please check if these were hit by the same backend issue, and rerun them / restore the daily slot if so? Thanks!


**** (2026-10-01 03:09, 2 votes)
Same here — submission 56739457 (Oct 1, 00:30 UTC): a prompt-only bundle (no adapters), validated locally against the official harness + wheelhouse on all 129 public tasks. It died with "Notebook Threw Exception". Our previous prompt-only submission (Sep 30, 04:21 UTC) scored normally (0.10), so nothing on our side changed except the scoring environment. Thanks for looking into it!


**** (2026-10-01 02:49, 2 votes)
Same error here. Submission 56741570 (Oct 1, 02:33 UTC) failed about 7 minutes after submitting with "Your notebook hit an unhandled error while rerunning your code". The notebook only writes a 4-file submission.zip (agent.yaml, prompts/system.md, configs/sampling.yaml, eval_config.yaml; no adapters or skills) from strings embedded in the notebook, and reads nothing from /kaggle/input. The same agent files ran without errors on 40 public tasks in an eval notebook on the 4x L4 machine, with the wheelhouse dataset attached on Oct 1. Our earlier submission 56719705 (Sep 30, 21:57 UTC) failed with the same message.


**** (2026-10-01 02:19, 2 votes)
Similar issues with submission 56740906. Previous uploads before the wheelhouse update was all working fine


> **** (2026-10-02 08:01, 0 votes)
> The submission was made with the kaggle CLI uploading a submission.zip containing an agent.yaml, subagents and role divisions, configs,.yaml files, no lora adapters yet. other participants are seeing the same issue, this might not be isolated.


**** (2026-10-01 10:02, 1 votes)
Same here.

I re-uploaded a byte-identical submission for rescoring: same four files, verified by sha256 per file against the archive that scored normally on 25 Sep. Nothing changed on my side.

Since you offered to rerun the affected submissions in #743683 so people wouldn't lose a slot, would the same apply to these? 

Happy to supply submission ids or anything else useful.


**** (2026-10-01 09:55, 1 votes)
@ryanholbrook, could you check what broke? If it’s on the scorer side, could 56745031 be rerun or the daily allowance restored? And please let us know when it’s safe to resubmit. Thanks!


**** (2026-10-01 09:44, 1 votes)
Same here: submission 56732762 (2026-10-01 00:17 UTC) ended with "Notebook Threw Exception" about 5 minutes after submitting, with no score.

It is byte-identical to our submission 56574678 (same zip, sha256 e4e62d2d…), which scored 0.10 on 2026-09-26. The packaging notebook is a CPU script that writes an embedded 4-file zip (agent.yaml, prompt, sampling, eval_config; no adapters or skills) and reads nothing from /kaggle/input.

The same zip runs fine on 4x L4 with the current wheelhouse (adk-submission 0.2.12): vLLM 0.19.1 starts with the new --reasoning-config and --no-scheduler-reserve-full-isl flags in about 340 s, and the agent jobs complete. So the failure seems to happen earlier in the scoring pipeline.

@ryanholbrook could you check what raised, rerun it or restore the daily allowance, and let us know when it is safe to resubmit? Thanks!


**** (2026-10-01 08:10, 1 votes)
Same issue: submission 56746524 (2026-10-01 07:39 UTC) ended after ~12 minutes with "Notebook Threw Exception". The same zip ran cleanly in an offline 4xL4 notebook with the current wheelhouse a few hours earlier.
@ryanholbrook could you check what raised and, if it's on the scorer side, rerun it or restore the allowance? Thanks!


**** (2026-10-01 07:28, 1 votes)
Hi @ryanholbrook, I am also experiencing this issue with submission 56740062, submitted on Oct 1 at 01:04:37 UTC. It ended with “Notebook Threw Exception” and no score.

My packaging notebook (version 10) completed normally. I downloaded the actual submitted ZIP and confirmed that it is byte-identical to the bundle tested with the official Evaluator on Kaggle 4×L4. Both public development cases passed verification, with 40 tests passing in total.

The bundle uses the required Gemma model and no LoRA adapters. The packaging notebook only writes an embedded ZIP; it does not run inference or read task data. It uses CPU and a 300-second session timeout. I have not established the root cause of the scoring failure.

Could you inspect the underlying exception for submission 56740062? If this was a scoring infrastructure issue, could the submission be rerun or the daily allowance restored? This failed submission used my only allowance today.

Please also let us know when it is safe to resubmit. Thank you!


**** (2026-10-01 06:52, 1 votes)
Hi, my submission also failed with "Notebook Threw Exception" today (submitted around 04:45 UTC on 1 Oct). The same agent.yaml and prompt scored 0.05 on 30 Sep. Only eval_config.yaml values changed (max_time_minutes 10, max_tool_calls 60).

Two questions:

Is the wheelhouse issue fixed now, so new submissions will run normally?
Will daily submission slots lost to this error be restored?


**** (2026-10-01 05:29, 1 votes)
hello @ryanholbrook,
Same issue facing with my latest submission `id:56741974`, getting status as failed. It is passing in local bench like previous submission.


**** (2026-10-01 05:29, 1 votes)
It happened to me too, and it cancelled my submission.


**** (2026-10-01 02:28, 1 votes)
Same issue with submission 56722759. The only change from my previous submission, which scored normally before the wheelhouse update, was the time budget in eval_config.yaml.


**** (2026-10-08 16:31, 0 votes)
Same "A system error. Please try resubmitting…" on two consecutive submissions: 56909631 (2026-10-07 11:41 UTC) and 56925838 (2026-10-08 00:18 UTC). 56925838 is the unchanged public 0.18 budget-fit bundle (4 files, prompt-only, no adapters), verified against the official 0930 harness with real-model request traces. @ryanholbrook could these be rerun or the allowance restored? Thanks!


**** (2026-10-01 17:59, 0 votes)
Hi @ryanholbrook, thanks for confirming the GPU outage was resolved.

Our submission 56747846 (2026-10-01 08:52 UTC, prompt-only bundle, no adapters, same Gemma model) ended after about 5 minutes with "Your notebook hit an unhandled error while rerunning your code" and no score. The same archive ran 20 public tasks cleanly on a 4×L4 notebook with the current wheelhouse a few hours earlier, so we believe the failure was the overnight outage, not the submission.

That failure used our daily allowance (a retry today is refused: "daily Submission allowance (1) used"). Could it be rerun, or the allowance restored for the affected submissions? Thanks!


**** (2026-10-01 13:04, 0 votes)
Same here, and it was my first submission :/


**** (2026-10-01 12:59, 0 votes)
Same. My submission 56740087 (2026-10-01 01:06 UTC) ended with "Notebook Threw Exception" and no score. It's a prompt-only bundle (no adapters) that differs from my previous submission 56691354 only in max_output_tokens


---

## Max 1 Submission/day is too low
/competitions/gemma-4-developer-agent/discussion/746541 | by  | posted 2026-10-07 14:39 | last comment 2026-10-08 14:44 | 10 comments | 10 votes


**** (2026-10-07 14:39, 10 votes)
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F2384691%2F0b3c668eb124ef04b1d472a88c49b78c%2FScreenshot%202026-10-07%20200637.png?generation=1791383828340086&alt=media)
For constant experimentation, 1 submission per day is a productivity breaker....
Before I thought the evaluation happened for only 60 tasks (so I did 12 or 10 mins/task), and thus 2 days wasted...
I reduced to 8 mins/task and still couldn't happen, and now the 7mins/task could had worked, but it may error out as it is running for almost 15 hours, and for others it lead to error


**** (2026-10-07 15:19, 3 votes)
I think 5 mins or 5 mins and 30 seconds are safe margins: https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/746250#3534191

Also yes 1 submission/day especially when it errors out is frustrating.


> **** (2026-10-07 17:56, 1 votes)
> yes it seems.... not even 6 mins per task is possible as safe...
> And all these timeouts prevented me to know how well my agent would perform in a specific time...


> > **** (2026-10-08 13:12, 1 votes)
> > You are right. My last submission used 5.5 mins and it errored -- even though it was system error but the eval was still running for 15 hours.


> > **** (2026-10-08 13:15, 0 votes)
> > weird.... my submission ran for 19 hours.... but then I woke up in morning to see it accepted


**** (2026-10-08 08:32, 1 votes)
I'm a little confused about why exceptions, especially those caused by the Kaggle platform, also count toward the daily submission limit.


> **** (2026-10-08 13:11, 0 votes)
> yes true... but ig they are also restrained/forced to do this due to compute problem


**** (2026-10-07 20:30, 1 votes)
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F37170011%2Ff47a71b3f54308ddaa5c57c3f437ddf1%2F2026-10-08-032611_hyprshot.png?generation=1791404787596642&alt=media)

Hello, I'm new to this competition from my screenshot i have to wait for my queue right? If my notebook is running it will show something like 7mins/task or something? I'm to excited to see the result haha.

and do you guys try eval local or not? I only have 16GB vram hit OOM try to offloading but not working yet plus I see many people say that the eval is like 12 hours long so it is not worth it i think.


> **** (2026-10-08 13:28, 1 votes)
> Hey! I don't know if there is a queue system for submissions, but there is not any separate indicator for running mode as you said....
> Yes, we do they evals, but not locally.... it's always mostly through cloud, the easiest being through kaggle notebooks - gives free 4xL4 GPUs


> > **** (2026-10-08 14:15, 0 votes)
> > ![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F37170011%2F5d7c6a6da663e8263c4f5725953e913b%2F2026-10-08-211154_hyprshot.png?generation=1791468746531675&alt=media)
> > 
> > Actually there is! :) I use swegemma but the speed is slow, yes i should use it on cloud. I'm new to kaggle notebook might have to give it a try now!


> > **** (2026-10-08 14:44, 0 votes)
> > I see... Ok then!


---

## How are URL-pointer-only tasks (e.g. rich_3471) meant to be solved in the air-gapped sandbox?
/competitions/gemma-4-developer-agent/discussion/746944 | by  | posted 2026-10-07 23:07 | last comment 2026-10-08 10:23 | 1 comments | 6 votes


**** (2026-10-07 23:07, 6 votes)
I'm analyzing harness and hit a consistent failure class that looks like a misunderstanding of the input contract on my side. Could you confirm the intended information flow for tasks whose problem_statement is just a title + a GitHub link?

Evidence from the published tasks (129 in tasks.jsonl):

- No task has hints: 129/129 tasks have an empty hints_text field.
- 18/129 task statements carry no spec beyond a short title and one or more URLs — e.g. rich_3471 is 86 chars total: "Fixed exception in append_tokens\n\nFixes https://github.com/Textualize/rich/issues/3014". Another example rich_4077 is 66 chars: "proxy isatty" plus the link.
- This concentrates in one repo: 17 of those 18 are rich, 1 is fastapi.
- 55/129 statements are under 300 chars overall.

Per HARNESS_README §4.1 the agent sandbox is network_mode="none", and §5.2 shows the initial prompt = problem_statement + hints (empty) + budget/env/instructions + workspace layout.

So, is the expectation that the model reconstructs the issue spec purely from the code snapshot + its own knowledge of the repo when the statement is a bare URL pointer, or is there a mechanism (e.g., an issue-body field, an offline issue cache, or hints) that these 18 tasks are supposed to get but currently don't? 

Is this the intentional benchmark design?


**** (2026-10-08 10:23, 2 votes)
@ryanholbrook could you take a look at this one? We see the same in the public set: about 20 of the 129 statements (almost all rich) are a short title plus a GitHub link, hints_text is empty for every task, and the sandbox has no network, so the issue body is never available to the agent. Is that intended, and is the hidden set built the same way? If the issue/PR body was dropped by accident, adding it (or filling hints_text) would make these tasks solvable.


---

## Request: let submissions set the compaction summary prompt (ADK already supports it)
/competitions/gemma-4-developer-agent/discussion/747186 | by  | posted 2026-10-08 09:14 | last comment 2026-10-08 09:14 | 0 comments | 5 votes


**** (2026-10-08 09:14, 5 votes)
Hi @ryanholbrook, a request about context compaction.

The scorer compacts the context at 14,336 tokens (interval 5, overlap 2, retention 5) with ADK's default `LlmEventSummarizer`. Two things make the summary weak for a coding agent:

1. `_format_events_for_prompt` keeps only `part.text`. Function calls and function responses are dropped, so the summarizer never sees which files were read or edited, or what the tests printed. Gemma-4 rarely writes text next to its tool calls, so a long run is often summarized as if nothing had been done, and the agent starts over or repeats its last call.
2. The default prompt is a generic chat summary ("focusing on key information and decisions made..."). It has no slot for what a coding agent needs to continue: the goal, the files changed so far, the last test result, the next step.

ADK already has the hook: `LlmEventSummarizer(llm, prompt_template=...)`, where the template contains `{conversation_history}`, set through `EventsCompactionConfig.summarizer`. Could you:

- let a submission pass its own summary prompt template (for example `compaction: {summary_prompt: ...}` in the root `agent.yaml`)? The scorer would still control the thresholds and the model; only the instruction text changes.
- and/or include function calls and (truncated) function responses in the history given to the summarizer?

If neither is possible, publishing the exact summarizer settings used by the scorer would let us design around them. This follows up on #744794 ("I'll look into the compaction issue"). Thanks!


---

## Six immediate "Kaggle Error" submissions in Gemma 4 Developer Agent
/competitions/gemma-4-developer-agent/discussion/745766 | by  | posted 2026-10-04 08:58 | last comment 2026-10-08 07:48 | 3 comments | 1 votes


**** (2026-10-04 08:58, 1 votes)
My Kaggle username is eswincha. On October 4, 2026, six submissions to gemma-4-developer-agent failed immediately with "Kaggle Error". Each shows:
"A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists."

These were notebook Versions 3-8: five submissions of my V4 agent archive and one of V7. The latest attempt was Version 8 at 14:14 IST. No score was produced. The submission dialog still shows 1 submission remaining today.

I rebuilt the V4 submission.zip from scratch. ZIP integrity, root-level agent.yaml, include paths, YAML configuration and compilation with the installed competition tool registry passed. V7 also passed a structural compilation check. These checks do not establish that hidden evaluation succeeds, and I have not identified the cause.

Latest failed version:
https://www.kaggle.com/code/eswincha/eswincha-gemma-agent-development-validation?scriptVersionId=355115263

The notebook is private. Can you check whether these failures indicate a submission-processing issue, or point me to the next diagnostic step? I can provide the archive and audit if needed.


**** (2026-10-08 05:58, 0 votes)
I have same issue, were you able to resolve this. Thanks.


> **** (2026-10-08 06:28, 0 votes)
> Not fully. Two later submissions succeeded, but another has since ended with the same "Kaggle Error", so I don't have a confirmed fix or cause. The archive and CPU compilation checks passed, but those don't establish that hidden evaluation succeeds. I'll update this thread if I get a reliable diagnosis.


> **** (2026-10-08 07:48, 0 votes)
> I also have that issue, if you find a solution please share it here. Thanks in advance.


---

## Failed submissions
/competitions/gemma-4-developer-agent/discussion/747066 | by  | posted 2026-10-08 04:16 | last comment 2026-10-08 06:53 | 1 comments | 0 votes


**** (2026-10-08 06:53, 0 votes)
Kaggle actually validates against 120 tasks(60 Public tasks and 60 private tasks) . I use 3.5-4.5minutes for max_minutes, so it would take around 9-10hours max.


**** (2026-10-08 04:16, 0 votes)
Hi everyone, my last 2 submissions failed so i wanna know what is the max_minutes for each task. Kaggle validates against 65 tasks if i am correct and my max minutes is 7. That would take approx. 7:30 hours and the limit is 12h. Is there a bug or my math is wrong?


---

## local agent
/competitions/gemma-4-developer-agent/discussion/747118 | by  | posted 2026-10-08 06:27 | last comment 2026-10-08 06:27 | 0 comments | 0 votes


**** (2026-10-08 06:27, 0 votes)
Hi everyone again, i would like to know if anyone has figured out a way to build the agent locally, with a smaller model of course. I feel like the hours we get on kaggle are not enough even though i have colab pro.


---

## Has anyone confirmed a LoRA adapter actually taking effect in a scored run?
/competitions/gemma-4-developer-agent/discussion/745364 | by  | posted 2026-10-03 04:09 | last comment 2026-10-08 03:21 | 1 comments | 0 votes


**** (2026-10-08 03:21, 1 votes)
update: submitted v5 + a zero lora adapter (rank 16, one q_proj module, peft format) to check if the scorer can load adapters at all. it failed with "Kaggle Error", same bundle without the adapter scores 0.13. @ryanholbrook is lora loading on the scorer known to hit the vllm sampler warmup oom (256 dummy requests) on 4xL4? happy to share the submission id


**** (2026-10-03 04:09, 0 votes)
Before investing in training, I'd like to confirm that a trained adapter works end to end in the scoring environment. Two things reported on the forum would each make one useless:

That adapters are silently dropped in the patched vLLM 0.19.1 — the submission runs, but the adapter never loads.
That enabling LoRA shrinks the KV cache to around 7.6k tokens. Our agent uses the full 32k context, so that would truncate long tasks.

Has anyone verified an adapter taking effect in a scored submission, and is there a way to confirm from the submission log that it loaded?

Separately, on training: I've been unable to fit gemma-4-31b QLoRA on 2× T4 (16GB each). Sharding with device_map='auto' fails on device mismatch, and single-GPU OOMs. Is a single 80GB card the practical minimum, or has anyone trained this on less?

@ryanholbrook


---

## How far did you get with prompts and config alone, before fine-tuning?
/competitions/gemma-4-developer-agent/discussion/746502 | by  | posted 2026-10-07 10:43 | last comment 2026-10-07 21:51 | 1 comments | 0 votes


**** (2026-10-07 21:51, 0 votes)
I found some good details here: https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/746250
I found also that you have to tell it how to use some tools. Saying "dont X" will often make X more likely to happen, quotes and newlines for example.


**** (2026-10-07 10:43, 0 votes)
Curious where people think the ceiling is without post-training. With prompt and budget changes only (no adapters), we've been stuck at about 0.12 on the public LB across several variants.

For those who've tried both:
- What was your best score from prompt/config only (no LoRA)?
- Did fine-tuning give a clear jump over that, and roughly how much?
- Or did you find that budget and pace (tool-call limits, time caps, forcing early edits) mattered more than anything else?

Even rough numbers would help others decide when it's worth moving to post-training. Thanks!


---

## ERROR OR STILL SCORING ?
/competitions/gemma-4-developer-agent/discussion/746658 | by  | posted 2026-10-07 17:00 | last comment 2026-10-07 20:16 | 4 comments | 3 votes


**** (2026-10-07 17:00, 3 votes)
WHY IS IT SHOWING SCORING AFTER THE ERROR IS THIS ALSO ONE MORE ERROR ? 
AND THE ERROR APPEARED AFTER THE 15 HOURS


**** (2026-10-07 20:16, 0 votes)
still scrolling 15 hrs


**** (2026-10-07 19:45, 0 votes)
i submitted one today and its running for more than 14 hours!


**** (2026-10-07 18:29, 0 votes)
I had the same issue, and other competitions too, there seem to be a general Kaggle bug, and with being only able to submit once, it's very penalizing. 

In other competitions, I am ok wasting 1/5 submission, but here it means no submit for 24h


> **** (2026-10-07 18:53, 0 votes)
> same here


---

## Aggregated questions from what has generally been asked on the forum : HOSTS ANSWER PLEASE
/competitions/gemma-4-developer-agent/discussion/745805 | by  | posted 2026-10-04 14:19 | last comment 2026-10-07 15:57 | 2 comments | 2 votes


**** (2026-10-07 15:57, 3 votes)
1. I'm reconsidering this request. The trouble is that we run both the public and the private tasks in the same 12 hour evaluation, and it's not clear to me yet how to assign 0 to unanswered tasks in a way that's fair and consistent.
2. I will likely make this configurable in a future update.
3. I will double check this and fix if necessary. Patch verification generally shouldn't timeout.
4. I didn't observe any significant command overhead compared to a plain container.
5. Both public and private tasks are evaluated during the same 12 hour run.
6. Yes.
7. Probably not. Information like this makes it too easy to extract information about the test set through probing.
8. I'm working on support for other models. We will retain the restriction to one model type per submission however (no main 31b agent and 12b subagent, for instance). Memory management on the L4x4s is too complex trying to support multiple models per run.
9. The test-file reset fix will be live soon.
10. A fix for bad tool calls will also be live soon.


**** (2026-10-04 14:19, 2 votes)
Answers to the following questions will clear up most uncertainties me and a lot of other participants have been facing. @ryanholbrook Is it possible to get accurate answers to these questions soon? I'll really appreciate it.

1) Is the fix that scores unfinished tasks as 0 at the 12-hour limit live now? If a submission exceeds 12 hours today, does the whole submission still error?

2) Which EventsCompactionConfig does the scorer use today (token_threshold, compaction_interval, overlap, retention)? Do you plan to change it before the final deadline, for example to keep tool results in the summary?

3) In swegemma/harness/verification.py the verification pytest call uses timeout=config.harness.command_timeout_seconds, which is the submission's eval_config.yaml timeout_seconds. Does the scorer apply our timeout_seconds to the hidden verification run? If so, a correct patch on a task whose test files are slow could be scored as failing. Is that intended?

4)Does the scorer's Docker sandbox run under gVisor (runsc) or runc? Is there a rough figure for command overhead compared with a plain container?

5)Is the private leaderboard score taken from the same scoring run as the public score, or are the two selected final submissions re-run (the code mentions a rerun/ layout)?

6) Does the 12-hour limit include vLLM server start-up?

7)Would you consider publishing per-submission aggregate counts (tasks that hit the time limit, context-overflow errors, sandbox errors), with no task identities, so that participants can budget time without guessing?

8)You mentioned possibly supporting other Gemma 4 variants. Will any of them be allowed as sub-agent models before the deadline, or is the 31B QAT model final?


**** (2026-10-05 16:02, 0 votes)
//-- answers to 1 (is the 12-hour overrun now scored as 0 for unfinished tasks?), 2 (which compaction settings does the scorer use?) and 3 (does our `timeout_seconds` apply to the hidden verification run?) decide how every team sets its limits. --//

Two more status questions, if you can confirm them in the same reply:

- Is the fix for the test-file reset (#744825, edits to existing test files making `test_patch` fail to apply) live on the scorer?
- Is the fix for an undeclared or misnamed tool call ending the task (#745028) live on the scorer?

Thanks for the work on this,
Mugur B.


---

## Scoring-run questions: task concurrency, eval_config keys, and the 12 h limit 
/competitions/gemma-4-developer-agent/discussion/743063 | by  | posted 2026-09-24 19:22 | last comment 2026-10-07 15:49 | 9 comments | 7 votes


**** (2026-09-24 19:22, 7 votes)
Hi hosts, thanks for releasing the wheelhouse! Three questions about the scoring run that affect how we budget time per task:

1. Are hidden tasks evaluated sequentially or with some concurrency? If concurrent, how many tasks can run at once, and is that configurable?

2. Which fields of `eval_config.yaml` does the scorer actually read? In particular, are `timeout_seconds`, `max_tool_calls`, `max_time_minutes`, and `max_turns` all supported, and what defaults apply when the file or individual fields are omitted?

3. If a submission reaches the 12-hour global limit, how are unfinished tasks handled? Are they scored as failures, or does the submission itself terminate/error?


**** (2026-09-24 19:48, 6 votes)
1. Sequentially.
2. The scorer reads those, and only those, four fields. The default is no limit.
3. Currently, hitting the 12-hour limit will error, but I'm planning on a fix that will score unfinished tasks as 0. You may want to set `max_time_minutes` to something moderate as a failsafe.


> **** (2026-09-28 17:05, 2 votes)
> Hi @ryanholbrook , a follow-up on this:
> 
> >Currently, hitting the 12-hour limit will error, but I'm planning on a fix that will score unfinished tasks as 0.
> 
> Is this fix live yet? I'd also like to raise a side effect that concerns me.
> 
> Right now, going over 12 hours errors the whole submission, and I've hit that couple days ago. So every team has to fit all ~120 tasks into the limit. And part of my research in this competition so far has been about this optimization. With unfinished tasks scored as 0, a submission could instead spend most of the 12 hours on say the first 30-40 tasks and never start the rest. The tasks are clearly hard for the model, so a lot more time per task might solve more of those early tasks than a run that gives every task an equal share.
> 
> - Is "solve as many tasks as possible within 12 hours, however the time is split" the intended goal, or should a good submission attempt every task?
> - Do tasks run in the same order every time, and are public and private tasks mixed through that order? If the public tasks come first, a submission that only reaches the early tasks could look strong on the public leaderboard and then collapse on the private one.
> - If this isn't intended, would you consider a required per-task time cap, or some other way to reward attempting every task? For example, instead of giving 0 to unattempted tasks they receive some negative score.


> > **** (2026-10-05 17:02, 0 votes)
> > this is a valid argument but even if there is a situation where one decided to spend time on fewer tasks and let rest go to zero, the winning chances are lower in that case.


> **** (2026-09-29 12:23, 0 votes)
> hi @ryanholbrook, do you have any update on scoring unfinished tasks as 0?


> **** (2026-09-29 12:38, 0 votes)
> Hey @ryanholbrook 
> Scoring unfinished tasks as 0 and accepting the submission would be a great fix!
> Please do provide an update


> **** (2026-10-03 09:34, 0 votes)
> > 2. The scorer reads those, and only those, four fields. The default is no limit.
> > 3. Currently, hitting the 12-hour limit will error, but I'm planning on a fix that will score unfinished tasks as 0. You may want to set `max_time_minutes` to something moderate as a failsafe.
> 
> I have made a couple of submissions for which the time taken to evaluate crossed the 12h limit and still scored successfully(IDs 56667603 and 56701670). The submission I made yesterday, however, ended in an error after crossing 12hrs. Can you fix this bug?


> **** (2026-10-04 15:29, 0 votes)
> Hi @ryanholbrook , following up on this thread, since several of us are planning our time budgets around the 12-hour limit:
> 
> 1. Has the change to score unfinished tasks as 0, rather than erroring the entire submission, been deployed? If so, from what date or scorer version does it apply? If not, is it still planned?
> 
> 2. A participant reported two submissions that ran past 12 hours and still received scores, and another that errored after 12 hours. Is that expected under the current system? Could differences in how elapsed time is measured or the submissions are processed explain these outcomes?
> 
> 3. Are hidden tasks run in the same order for every submission? Are public- and private-leaderboard tasks interleaved or grouped?
> 
> Until we hear back, we'll plan for the entire run to finish within 12 hours and attempt every task. Thanks!


> > **** (2026-10-07 15:49, 0 votes)
> > I'm reconsidering this request. The trouble is that we run both the public and the private tasks during the same 12 hour evaluation, and it's not clear to me yet how to support assigning 0 to unfinished tasks in a way that's fair and consistent.


**** (2026-10-01 23:23, 1 votes)
@ryanholbrook do we have control on adaptive budget like out of 12 hours, i wnat 1 task to take 8 minutes, otehr to take 4 minte. This adaptive control in our hand extremely crucial or do you have your own time. Please answer this as soon as possible.


---

## Two data issues: half the graph/embedding files download empty, and the graphs contain no async functions
/competitions/gemma-4-developer-agent/discussion/742911 | by  | posted 2026-09-24 03:08 | last comment 2026-10-07 15:28 | 6 comments | 10 votes


**** (2026-09-24 03:08, 10 votes)
1) Empty files in the download (affects local runs)

The graphs and embeddings are described as task-named files hard-linked to commit-named files. Zip archives can't store hard links, and in the downloaded data one side of each linked group arrives as a 0-byte file:

  graphs: 129 of 256 files are empty
  embeddings: 129 of 256 files are empty

Exactly one readable copy survives per commit, but it can sit under any name in the group, including a different task's name where two tasks share a commit (requests_6589 and requests_6629; rich_3882 and rich_3894).

HARNESS_README says the code intelligence tools are only enabled when the graph and embedding files exceed 100 bytes. If that holds, local swegemma runs on the downloaded data will silently lose get_code_neighbors, get_code_subgraph and search_similar_code on many tasks. The fix is to copy each commit's readable file over its empty siblings before running; every commit has a readable source.

2) No async functions in the graphs

For each of the 129 training tasks, I parsed every non-test .py file the reference patch touches (from the base_commit snapshot) with Python's ast module and checked whether each top-level function, method and class exists as a node ID in the task's graph. Coverage across those files:

  sync functions and methods: 4,739 of 4,740 present
  classes: 855 of 857 present
  async functions and methods: 0 of 305 present

By repo: fastapi library 0/232 async present, fastapi docs_src 0/27, httpx 0/46. rich and requests have no async definitions in the audited files.

Examples with no node: fastapi.routing.serialize_response, fastapi.dependencies.utils.solve_dependencies, fastapi.dependencies.utils.request_body_to_args. Agents using the graph tools therefore can't reach async code paths. In 16 of the 121 training tasks whose reference fix lands in function or class bodies, at least one changed function is async and absent from the graph.

The graphs also contain a single edge type, calls, in all four repos (no import or containment edges), and no module-level nodes.

Questions for the hosts:
1. Is the async omission intended?
2. The data description says the test set uses identical graph generation. Does the hidden test set share it?
3. Are the embedding archives keyed to the same node set, so search_similar_code also can't surface async code?
4. Does the scoring environment use real hard links, so the empty-file issue only affects the public download?

Happy to share the audit and repair scripts as a public notebook.


**** (2026-09-24 10:39, 0 votes)
Hi @jasonwold,

Thanks for the report. We will investigate and get back to you.


> **** (2026-09-26 10:48, 0 votes)
> Has this issue been fixed now? Do we need to re-download the dataset? Thanks!


> > **** (2026-09-26 11:37, 0 votes)
> > The embeddings are no longer empty; that has been fixed. The missing `async` functions are still missing. I don't have an ETA on that yet.


> > **** (2026-10-07 15:28, 0 votes)
> > Thanks @ryanholbrook for the quick fix on the embeddings, and for confirming the async status.
> > 
> > Two things still open, in case they're useful to others:
> > 
> > 1. Were the 129 empty graph files fixed along with the embeddings, or only the embeddings? Anyone running swegemma locally needs both, since the code intelligence tools are only enabled when the graph and embedding files exceed 100 bytes.
> > 2. Does the hidden test data mounted during scoring carry the same empty files? If it did before the fix, some scored runs may have had the graph tools withheld.
> > 
> > For anyone weighing the async gap: in 16 of the 121 training tasks whose reference fix lands in function or class bodies, at least one changed function is async and absent from the graph (15 fastapi, 1 httpx). Agents leaning on the graph tools for those tasks will need a text-search fallback.


**** (2026-09-24 04:40, 0 votes)
Thanks @jasonwold , I think I have answers to 2 of your questions. I am still verifying some things with my submission that I've pushed recently. In the meantime:

>Does the scoring environment use real hard links, so the empty-file issue only affects the public download?

It's not only the download. My notebook run showed Kaggle's own mounted copy has the same 129 + 129 empty files.

For local runs I replaced each empty file with a hard link to its group's readable copy rather than a copy, which restores the documented layout without extra disk. Whether the scoring environment with the hidden test set is affected is still a question for the hosts.

> Are the embedding archives keyed to the same node set, so search_similar_code also can't surface async code?

Yes. For all 127 commits, the embedding archive's keys are exactly the graph's node IDs, no more and no less. So `search_similar_code` cannot surface async code either.


> **** (2026-10-07 15:28, 0 votes)
> Thanks @zhukovoleksiy, that's a careful pair of checks. Confirming the empty files exist in Kaggle's own mounted copy settles that it wasn't a download artifact, and the embedding-key result means all three graph tools share the async gap, not just the two graph traversal tools. The hard-link repair is a nicer fix than copying, too.


---

## 60 tasks or 120 tasks
/competitions/gemma-4-developer-agent/discussion/746008 | by  | posted 2026-10-05 18:05 | last comment 2026-10-07 14:45 | 11 comments | 2 votes


**** (2026-10-05 18:05, 2 votes)
The data page says this:

> There are about 120 tasks in the test set, evenly divided between the public and private splits. The test set was curated from a set of private repositories.

Which I am reading as 60 in the public LB and 60 in the private LB. So do we design the sampling config and importantly the evaluation config such that the 12 hour deadline is to solve 60 private tasks?

Also this is a bit frustrating to make a submission and see it error out without any info other than the fact that the notebook timed out. I think most of us are flying blind here.

Yes we can always make a submission by going defensive but at least a base/default configuration to start off of or some verbose stdout from the submission will go a very long way in ensuring healthy participation. :)


**** (2026-10-05 19:32, 0 votes)
The 12 hours cover all ~120 tasks, public and private together.


> **** (2026-10-05 19:36, 0 votes)
> but the shown score on LB is just public, right? so if the agent say resolves 10/60 tasks in public set and say 20/60 in private, we will get a score of 1/6 i.e, 0.16. 
> 
> Why then waste compute on the private set?
> 
> assuming I am understanding it right. :)


> > **** (2026-10-05 19:47, 0 votes)
> > > Why then waste compute on the private set?
> > 
> > ![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F13977249%2Fc1a269383fd41393174d9c7174dff6b2%2F1111.jpg?generation=1791229651384368&alt=media)


> > **** (2026-10-05 20:13, 0 votes)
> > Yes I know but why run the 50% for every submission when the compute is limited. 
> > 
> > Won’t it be better if the 50% is evaluated at the end with the best submitted agents? Maybe do an average of 3 to factor in the deterministic behaviour of the systems.


> > **** (2026-10-05 20:34, 1 votes)
> > Oh yea it’s a good question. 
> > 
> > Simple answer: thats just how Kaggle competitions with fixed data are being hosted.
> > 
> > You cant guarantee that your selected submission wont time out / errored out on a new data. Also when you run it both on a private/public data, then the results can be revealed instantly. Try to come up with more reasons on why this design could be a good option


> > **** (2026-10-05 20:38, 0 votes)
> > That is the standard Kaggle setup for hidden test sets. Each submission is scored once on the whole set in one environment, the private half's score stays hidden until the deadline, and the final ranking uses the private scores of the submissions you select. 
> > 
> > Scoring both halves at submission time means the result is exactly what your agent did then, with no rerun in a changed environment, and the hosts don't have to rerun every team's agent at the end of competition because everything has been run already


> > **** (2026-10-06 04:58, 1 votes)
> > I agree to all the points above -- I think my argument is more of a feature request. Kaggle has been running eval on the entirety of the split since forever but back in the day it was just quicker and less compute dependent. They should consider optionality/control over how to run evals today. 
> > 
> > Maybe run only public LB's eval in the first half of the competition and then run on the entirety as and when they have more compute to throw at it. I remember when orbit wars was running, PTCG was facing issue running the LB but once orbit wars was done, the compute to diverted to PTCG and all was good.
> > 
> > Wishful thinking I guess.


> > **** (2026-10-07 14:45, 3 votes)
> > We considered this here and have done so in the past (e.g., AIMO 3). We opted for the full evaluation during submission time here because of the complexity of the tasks and the increased risk of submission errors. What we don't want to happen is a lot of submissions that succeed on the public split, but error on the private split. Running  submissions on all of the tasks each time means that if your submission succeeds at all (you get a public LB score), you know that it succeeded on the private split too.


**** (2026-10-05 19:06, 0 votes)
There are 129 tasks in the snapshots directory.

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F217864%2F69ef358bd6969a33e2fbd4b72b90dd84%2FSkjermbilde%20fra%202026-10-05%2021-04-32.png?generation=1791227136159893&alt=media)


> **** (2026-10-05 19:09, 1 votes)
> I was talking about the test set and not the training set. :)


> > **** (2026-10-05 19:56, 0 votes)
> > Your right. Sorry, I misunderstood.


---

## What timeout per task does not give the notebook timeout issue? 8 min, 6min or 5 min
/competitions/gemma-4-developer-agent/discussion/746469 | by  | posted 2026-10-07 07:27 | last comment 2026-10-07 14:34 | 1 comments | 0 votes


**** (2026-10-07 14:34, 0 votes)
Around 5 mins 30 secs is the average distributed time per task (~120)


**** (2026-10-07 07:27, 0 votes)
10 minutes was definately a timeout beucase of 120 test tasks.


---

## How are you guys dealing with infinite agentic loops?
/competitions/gemma-4-developer-agent/discussion/746523 | by  | posted 2026-10-07 13:09 | last comment 2026-10-07 14:31 | 3 comments | 0 votes


**** (2026-10-07 13:55, 1 votes)
I tried putting hard caps on iterations , also if caching is working fine it shouldn't do the  same tool again.


**** (2026-10-07 13:33, 1 votes)
I'd imagine you could increase the temperature to fix that.


**** (2026-10-07 14:31, 0 votes)
- Outsource some of the commands run to watched sub-agents
- Create a skill, or a watchdog script which flags such things


**** (2026-10-07 13:09, 0 votes)
Is there a way here that we can overcome agents calling same tool again and again over 10 times? In some cases, over 30 times and getting the same result and yet not changing their tool call without fine-tuning?


---

## lora adapter oom in vllm warmup with scorer settings?
/competitions/gemma-4-developer-agent/discussion/746503 | by  | posted 2026-10-07 11:01 | last comment 2026-10-07 11:01 | 0 comments | 1 votes


**** (2026-10-07 11:01, 1 votes)
tried a rank 16 lora (peft format, all linear layers) with the official VllmServer on the 4xL4 notebook, exact scorer settings (gpu util 0.8, max_model_len 32768, tp 4). base model starts fine, but with the adapter it dies with "CUDA out of memory occurred when warming up sampler with 256 dummy requests". same adapter works if i pass --max-num-seqs 8 through extra_args. does the scorer set max-num-seqs or something similar, or will lora submissions hit this? has anyone gotten a lora submission scored?


---

## Solutions to the tasks
/competitions/gemma-4-developer-agent/discussion/746252 | by  | posted 2026-10-06 16:25 | last comment 2026-10-06 20:48 | 2 comments | 0 votes


**** (2026-10-06 20:48, 0 votes)
The reference-patch pointer is helpful. Is there also a documented command for running a task's tests against an agent-generated patch locally? For debugging, I'd like to compare the test outcomes as well as the code diff, especially when the agent takes a different approach from the reference.


**** (2026-10-06 16:47, 0 votes)
tasks.jsonl includes a reference patch


**** (2026-10-06 16:25, 0 votes)
Is there a place where i can find solutions to the tasks given to the coding agent?


---

## Can I Omit Unused Tools from `agent.yaml`?
/competitions/gemma-4-developer-agent/discussion/746235 | by  | posted 2026-10-06 14:46 | last comment 2026-10-06 15:38 | 1 comments | 0 votes


**** (2026-10-06 15:38, 0 votes)
yes you can omit those.


**** (2026-10-06 14:46, 0 votes)
I’m simplifying my agent config and don’t plan to use:

`search_similar_code`, 
`get_code_neighbors`, 
`get_code_subgraph. 

Is it okay to omit these three tools from `agent.yaml`, or must every organizer-provided tool be listed?

because my submission completed faster under 30 minutes maybe but the time limit per task was 3 minutes.


---

## Welcome to the Gemma 4 Developer Agent Competition
/competitions/gemma-4-developer-agent/discussion/743007 | by  | posted 2026-09-24 15:59 | last comment 2026-10-06 14:58 | 9 comments | 12 votes


**** (2026-09-24 15:59, 12 votes)
Hello Kagglers,

Today’s most capable software engineering agents rely on massive, closed-source models running in the cloud, leaving advanced autonomous development tools out of reach for many developers.

With Gemma 4, we want to change that.

Our challenge to you is to push the boundaries of open-source models and post-train Gemma 4 into an autonomous coding agent capable of navigating real-world repositories and reliably resolving software engineering tasks on consumer-grade hardware. To help you get started, we’ve provided a [starter submission](https://www.kaggle.com/competitions/gemma-4-developer-agent/data?select=sample_submission), [development tasks](https://www.kaggle.com/competitions/gemma-4-developer-agent/data?select=tasks.jsonl), and a corresponding dataset of structured [code graphs](https://www.kaggle.com/competitions/gemma-4-developer-agent/data?select=graphs) with [pre-computed embeddings](https://www.kaggle.com/competitions/gemma-4-developer-agent/data?select=embeddings) for repository-level retrieval.

Whether you explore parameter-efficient fine-tuning, novel reinforcement learning approaches, or graph-based code reasoning, we want to see how far you can take local, open models. 

We can't wait to see the agents you build and the solutions you invent!

Google Research and The Gemma Team


**** (2026-09-28 14:08, 1 votes)
L4 ×4 session is queued for very long time.


> **** (2026-10-06 09:32, 0 votes)
> yea dude like its painfully slow


**** (2026-10-06 14:58, 0 votes)
Excited to participate in this challenge! We've been experimenting with an AST-based semantic skeletonization pipeline to overcome the 32k context bottleneck on massive SWE-bench repositories
(compressing structural token footprints by ~95% while preserving full class hierarchies and function
signatures).
Combining this with a 3-agent hierarchical triad (Scout, Synthesizer, Sandbox Verifier) running across 4x NVIDIA L4 GPUs via vLLM has shown great promise for surgical unified diff patches. Looking forward to
learning from the community's approaches! Best of luck to everyone.


**** (2026-10-05 08:01, 0 votes)
here i have a doubt that can we make agents work in parallel to solve tasks so we can increase time for solving each task and eval_config.yaml has no concurrency key so we can implement it as we what or you will decide it


**** (2026-09-26 18:37, 0 votes)
Good skills


**** (2026-09-26 12:18, 0 votes)
it's the best choice for deepmind to let developers to show their skills


**** (2026-09-24 18:02, 0 votes)
Or post train model with api and that can be implemented for better accuracy


**** (2026-09-24 18:01, 0 votes)
Train gama offline?


---

## Max sampling/eval configs folks have been able to use
/competitions/gemma-4-developer-agent/discussion/746219 | by  | posted 2026-10-06 13:42 | last comment 2026-10-06 14:43 | 1 comments | 0 votes


**** (2026-10-06 14:43, 0 votes)
max_time_minutes: 60
 60 minutes per task is too much try 5-10 others are fine


**** (2026-10-06 13:42, 0 votes)
Over the last few days I have tried unsuccessful submissions -- they all timed out. I am wondering what configs were able to make successful submissions?

For instance my last unsuccessful submission was using:

```
evaluation:
  timeout_seconds: 300
  max_tool_calls: 50
  max_time_minutes: 60
  max_turns: 80
```

```
temperature: 0.2
top_p: 0.95
max_output_tokens: 8192
thinking_config:
  thinking_budget: 4096
  include_thoughts: true
```


---

## notebook exception
/competitions/gemma-4-developer-agent/discussion/746220 | by  | posted 2026-10-06 13:52 | last comment 2026-10-06 13:52 | 0 comments | -1 votes


**** (2026-10-06 13:52, -1 votes)
After an hour got a message notebook threw exception


---

## Clarification on wheelhouse v28 dependency conflicts
/competitions/gemma-4-developer-agent/discussion/746212 | by  | posted 2026-10-06 13:06 | last comment 2026-10-06 13:06 | 0 comments | 0 votes


**** (2026-10-06 13:06, 0 votes)
Hi Kaggle team, Hi @ryanholbrook . Could you please clarify how the current Gemma 4 Developer Agent Wheelhouse v28 is intended to be installed in the scoring environment?

Specifically:

Is it installed as a delta over the Kaggle base environment, rather than as a standalone environment?

Are its wheels installed with dependency resolution disabled (for example, --no-deps)?

Are packages such as FastAPI and Starlette expected to come from the base environment?

Is the current public wheelhouse sufficient to reproduce the serving environment, or are additional base-image dependencies/pins applied during scoring?

I want to make sure local validation follows the intended scoring setup without introducing arbitrary dependency changes.

Thanks!


---

## Waiting 12 hours just for notebook timeout -> maybe they should show a bit more logs? Also 60 or 120 Tasks?
/competitions/gemma-4-developer-agent/discussion/746169 | by  | posted 2026-10-06 09:21 | last comment 2026-10-06 12:12 | 6 comments | 3 votes


**** (2026-10-06 09:21, 3 votes)
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F2384691%2F6b8115aa0876b3128cd1c8d2cf3719c8%2FScreenshot%202026-10-06%20144847.png?generation=1791278357606799&alt=media)

As the title says.... by the way, how many tasks are ran at 1 submission during the 12 hours? 60 or 120?


**** (2026-10-06 12:07, 1 votes)
same issue is this an issue from the oraganizers ?


> **** (2026-10-06 12:10, 0 votes)
> no, this is our own agent taking more than the set limit of 120 hours for the 120 tasks


**** (2026-10-06 10:00, 1 votes)
120 tasks


> **** (2026-10-06 12:11, 0 votes)
> that's weird.... i all this time thought, it ran on only 50% (60 of them).... that's why I was giving 12mins/task to my agent...


**** (2026-10-06 09:29, 1 votes)
i think maybe around 120 tasks


> **** (2026-10-06 12:12, 0 votes)
> yes, i think its 120 tasks, which seems weird... i thought it did on only 60 tasks (50%)


---

## LoRA Adapters
/competitions/gemma-4-developer-agent/discussion/745904 | by  | posted 2026-10-05 07:06 | last comment 2026-10-06 05:41 | 4 comments | -1 votes


**** (2026-10-05 07:06, -1 votes)
Hi everyone, is it allowed to finetune LoRA adapters or i should leave as they are?


**** (2026-10-05 11:10, 0 votes)
a sub part of this competition is to post train the base gemma model using PEFT (lora) -- so yes it is allowed.


> **** (2026-10-05 18:07, 0 votes)
> for data can i use the golden patches that everyone is talking about?


> > **** (2026-10-05 19:08, 0 votes)
> > can you please point me to a link or something to take a look so I can comment on it?


> > **** (2026-10-06 05:41, 0 votes)
> > i cannot find it, do they provide the dataset for finetuning or that is something we have to find?


---

## include_thoughts currently disables reasoning instead of only hiding it [adk_submission 0.2.12]
/competitions/gemma-4-developer-agent/discussion/745059 | by  | posted 2026-10-02 00:48 | last comment 2026-10-05 23:29 | 2 comments | 4 votes


**** (2026-10-05 23:29, 3 votes)
We tested `include_thoughts: true` with `thinking_budget: 2048` locally against the current wheelhouse, using the same vLLM server flags HARNESS_README documents (--tool-call-parser gemma4 --reasoning-parser gemma4, no --reasoning-config). Every one of 24 tasks failed immediately (0 tool calls) with:

litellm.BadRequestError: OpenAIException - thinking_token_budget is set but reasoning_config is not configured. Please set --reasoning-config to use thinking_token_budget.

Traced it to apply_thinking_config_to_model() in adk_submission/resolvers/generation.py (the function cited above): once enable_thinking is true and thinking_budget>0, it sends extra_body["thinking_token_budget"]=<budget> to vLLM's OpenAI-compatible endpoint, and vLLM itself rejects that unless the server process was started with --reasoning-config. That's a server-launch argument, not something agent.yaml or generate_content_config can reach, and it isn't among the VllmServer flags HARNESS_README documents (tool_call_parser, reasoning_parser, max_model_len).

If the scorer's own VllmServer doesn't pass --reasoning-config either, then even with the include_thoughts/enable_thinking decoupling proposed above, setting thinking_budget>0 with thinking enabled would crash every task on the scorer too, not just locally -- the two fixes may need to land together. Would appreciate confirmation either way: right now there's no way for a submission to find this out except by risking a full submission on it.


**** (2026-10-02 00:48, 4 votes)
Hi organizers,

Thanks for fixing reasoning persistence and `thinking_budget` forwarding. I found a remaining semantic mismatch in `adk_submission 0.2.12`.

Google’s [`ThinkingConfig`](https://googleapis.github.io/js-genai/release_docs/interfaces/types.ThinkingConfig.html) defines:

- `thinking_budget`: controls the reasoning-token budget.
- `include_thoughts`: controls whether generated thoughts are included in the response.

vLLM separately uses `enable_thinking` to control whether Gemma 4 generates reasoning at all.

However, the current bridge maps:

```text
include_thoughts: false
        ↓
enable_thinking: false
        ↓
no reasoning generated
```

Therefore, this configuration does not provide private reasoning:

```yaml
thinking_config:
  thinking_budget: 4096
  include_thoughts: false
```

Because thinking is disabled, the positive budget is effectively unused. Competitors can currently choose between:

1. No reasoning.
2. Reasoning generated, returned, and retained during tool-call continuations.

There is no mode that generates reasoning for the current inference while omitting it from subsequent request context.

## Why this matters

[Gemma’s prompt-formatting documentation](https://ai.google.dev/gemma/docs/core/prompt-formatting-gemma4#managing-thought-context-between-turns) recommends preserving thoughts within a function-calling turn, so stripping them is not necessarily better. However, long coding-agent tool chains can accumulate reasoning and approach the 32K context limit. Separate controls would let competitors evaluate that tradeoff.

Could the harness expose separate controls for:

- Whether reasoning is generated.
- Whether reasoning is returned by the inference server.
- Whether returned reasoning is retained in subsequent ADK requests.

At minimum, could `include_thoughts: false` avoid setting `enable_thinking: false`, so that the configuration above means “generate reasoning, but do not return it”?

## Potential implementation

A minimal fix appears possible in the `adk-submission` package, primarily in:

`adk_submission/resolvers/generation.py`

1. In `apply_thinking_config_to_model()`, derive vLLM’s `enable_thinking` only from `thinking_budget` or `thinking_level`. Do not use `include_thoughts` to disable generation:

   - `thinking_budget > 0` → `enable_thinking: true`
   - `thinking_budget <= 0` or `thinking_level: none` → `enable_thinking: false`

2. In `install_litellm_reasoning_patch()`, handle `include_thoughts` independently on the response path:

   - `include_thoughts: true` → preserve reasoning parts.
   - `include_thoughts: false` → remove `Part(thought=True)` before the response enters ADK session history.
   - Always preserve visible text, function calls, usage metadata, errors, and final-response metadata.

This would support all three configurations:

```yaml
# 1. No reasoning
thinking_config:
  thinking_budget: 0
  include_thoughts: false

# 2. Reasoning generated and retained
thinking_config:
  thinking_budget: 4096
  include_thoughts: true

# 3. Reasoning generated but not retained
thinking_config:
  thinking_budget: 4096
  include_thoughts: false
```

Thanks!


**** (2026-10-03 09:08, 1 votes)
Thanks for reporting this, I also found this issue this afternoon when I was reviewing "metric/gemma-4-developer-agent-wheelhouss/adk_submission-0.2.12-py3-none-any.whl/adk_submission/resolvers/generation.py", hope your suggestion can be supported promptly.


---

## Allowed training data for LoRA adapters: trajectories from other open models?
/competitions/gemma-4-developer-agent/discussion/746046 | by  | posted 2026-10-05 20:30 | last comment 2026-10-05 21:59 | 1 comments | 0 votes


**** (2026-10-05 21:59, 2 votes)
Both cases are permitted.


**** (2026-10-05 20:30, 0 votes)
The rules allow external data if it is "freely and equally accessible to everyone",
and an earlier answer here confirmed that fine-tuning on agent trajectories generated
by gemma-4-31b-it itself is allowed. Could you clarify two cases that are not covered
by that?

1. Trajectories generated by a different open-weight model (for example a permissively
   licensed coding model run locally), used as SFT data for a LoRA adapter that is then
   served on gemma-4-31b-it-qat-w4a16-ct.

2. Existing public SWE-bench-style trajectory datasets on Hugging Face, where the
   trajectories were produced by models whose own licences permit redistribution but
   which are not Gemma.

Both would be freely available to every participant, which seems to satisfy the
external-data rule, but neither is Gemma output, so I would rather ask than assume.

A yes or no on each would be enough.


---

## Official sample_submission scores FAILED — are submitted adapters meant to be registered as named LoRA modules?
/competitions/gemma-4-developer-agent/discussion/743213 | by  | posted 2026-09-25 08:40 | last comment 2026-10-05 20:15 | 14 comments | 4 votes


**** (2026-09-25 08:40, 4 votes)
The official `sample_submission`, submitted byte-for-byte as-is (submission `56539111`, 2026-09-25 03:46 UTC): **FAILED, no score.** The only message is the generic `Your notebook hit an unhandled error while rerunning your code.`

I could not reproduce the failure locally, and ruled three explanations out with the same pins as the official wheelhouse (`google-adk 1.36.1`, `adk-submission 0.2.11`, `swegemma 0.2.7`):

- the package **compiles clean** — `compile_submission()` returns the full `LlmAgent` tree, so this is not a YAML/assembly bug;
- `discover_adapters()` returns `main_lora` / `tool_lora` exactly as declared in `agent.yaml`, so it is not an adapter-name collision;
- all 9 tools are registered unconditionally (`create_tools()` in `swegemma/tools/__init__.py`) — the `has_g`/`has_e` file-size check in `agent_runner.py` only gates prompt *prose*, not tool registration — so it is not the empty graph/embedding files either.

The part that matters: **the adapter never goes through local PEFT loading.** In `swegemma/models/registry.py` (`resolve_swegemma_adapter`, and `_make_adapter_model` inside `setup_gemma_model_registry`), `adapter: <name>` rewrites the agent's model into a LiteLLM id of `openai/<adapter-name>` — i.e. it asks the inference endpoint to serve a LoRA **already registered under that name** (vLLM `--lora-modules <name>=<path>`). For this submission the compiled root agent's model string is literally `openai/main_lora`. `swegemma` itself never starts the inference server (the endpoint comes from `MODEL_PROXY_URL` / `LITELLM_API_BASE` / `LOCAL_INFERENCE_URL` / `OPENAI_BASE_URL`), so that registration step appears to live entirely on the scoring side.

Supporting observation: I read the packaging cells of both public notebooks whose scores are known — `nursrijan`'s starter kit (0.05) and `romanrozen`'s baseline (0.12) — and **neither writes an `adapters/` directory into its bundle**; `romanrozen`'s notebook mentions LoRA only in a validator check and in a roadmap line reading "LoRA adapter (*if the rules allow*)". So as far as I can tell **no public submission has exercised this path at all**, which is consistent with the failure above rather than with a bug in my packaging.

Two questions, if the organizers have a moment:

1. Is the scoring server expected to register submitted adapters as named LoRA modules (`--lora-modules main_lora=...`), or to merge them into the base model first?
2. If they are meant to be addressable, is there a required naming convention, or a constraint on `base_model_name_or_path` in `adapter_config.json` relative to the served model?

For context, an earlier participant topic here reported that the pinned `vllm 0.19.1` refuses to start with `--enable-lora` for `Gemma4ForConditionalGeneration` ("does not support LoRA yet"), and that topic has since been deleted — so I can't tell whether the server-side refusal or the unregistered model id is what we are hitting. The distinction matters, because a non-empty `adapters/` directory changes how the model is addressed at all: if this is the cause, then **any** submission carrying an adapter fails regardless of its rank or quality, and the LoRA route is closed rather than merely unhelpful.

I can run the single-variable check on my next submission — the identical official package with `adapters/` and the two `adapter:` lines removed, nothing else touched — and report back either way.


**** (2026-09-25 10:55, 3 votes)
Hi @dominicjamil,

I have a fix incoming. Will try to post a demo notebook later today.


> **** (2026-09-25 18:56, 0 votes)
> Confirming this is still happening as of just now (2026-09-26). I submitted the sample_submission/ bundle completely unmodified (byte-for-byte copy, adapters/main_lora and adapters/tool_lora included, no edits at all) and it also failed with the generic Kaggle Error, same as @dominicjamil reported ~8 hours ago. I also tried several of our own bundles beforehand (no adapters, various tool/sub-agent configurations, with and without eval_config.yaml) and every single one failed identically before this test, so it does not look specific to adapters or to any particular bundle structure on our end. Wanted to flag that the fix does not appear to be live yet, in case that's useful. Happy to share exact repro steps if it helps.


> > **** (2026-09-25 19:31, 0 votes)
> > I'll check again. There might have been a data bundle that didn't catch the update. It's working in the Getting Started notebook, at least.


> > **** (2026-09-26 11:29, 0 votes)
> > Are you referring to this notebook? https://www.kaggle.com/code/ryanholbrook/getting-started-gemma-4-developer-agent/notebook because I downloaded and submitted the submission.zip file to the leaderboard 2hrs ago and it crashed with this error just now: ![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F31268718%2Fb53344e9ed5ab42942b31fbe8ff68922%2FScreenshot%202026-09-26%20165754.png?generation=1790422130716964&alt=media)


**** (2026-09-26 06:00, 2 votes)
Same failure here, but a different error text. Submission 56565084 (2026-09-26 00:53 UTC; a plain YAML bundle, no adapters) completed with no score and the message "Your notebook has requested more CPU, GPU or TPU resources than are available." It still used the daily allowance: resubmitting the identical zip is rejected with "Your team has used its daily Submission allowance (1) today". The same bundle structure (only the prompt text and max_turns differ) scored normally the day before, and my Kaggle GPU quota is untouched. @ryanholbrook, could the slot be restored when a submission fails on this platform-side resource error?

Separately, once the server starts with the patched vLLM, LoRA adapters are silently wiped (no effect on outputs). I opened a separate topic with the cause and a repro: https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743508


> **** (2026-09-26 06:38, 3 votes)
> I got the same error "Your notebook has requested more CPU, GPU or TPU resources than are available." this morning. If possible, I would also be happy to get my slot back in case that's an error on Kaggle side.


> **** (2026-09-26 10:46, 0 votes)
> I got the same error today; the notebook stopped after 4 hours... I assume it's happening to everyone, right?


**** (2026-09-26 11:06, 1 votes)
Adding another one to the list: submission 56573423 (submitted today at 07:47 UTC, plain YAML bundle, no adapters) also failed with "Your notebook has requested more CPU, GPU or TPU resources than are available." Ran for around 2 hours.

@ryanholbrook could our team's daily slot also be restored once the platform fix is deployed? Thanks!


> **** (2026-09-26 11:36, 0 votes)
> Thanks for the report. I think I've resolved this one, but please let me know.


**** (2026-09-26 10:22, 1 votes)
Same resource error here: submission 56563379 (2026-09-26 00:01 UTC, plain YAML bundle, no adapters) completed with no score, error_description "Your notebook has requested more CPU, GPU or TPU resources than are available." Our previous submission from the same pipeline scored 0.10. @ryanholbrook, could the slot be restored for submissions that failed with this platform-side error?

One note for anyone testing adapters locally: the PyPI vllm 0.19.1 wheel still fails at startup with "Gemma4ForConditionalGeneration does not support LoRA yet" (we reproduced this on 2x H100 with the competition checkpoint and the sample main_lora). Only the patched vllm 0.19.1 in metric/gemma-4-developer-agent-wheelhouse adds SupportsLoRA, so local LoRA tests must install that exact wheel. With the patched wheel, see the separate report in 743508 that adapters load but are reset to zero.


**** (2026-09-26 09:23, 1 votes)
Same here. Submission 56563939 (2026-09-26 00:08 UTC, plain YAML bundle, no adapters) completed with no score; error_description: "Your notebook has requested more CPU, GPU or TPU resources than are available." My previous bundle from the same pipeline (differing only in the thinking settings in sampling.yaml and timeout_seconds in eval_config.yaml) scored 0.13 the day before, so this looks platform-side. The failed run still used the daily submission slot. @ryanholbrook, could slots be restored for submissions that failed with this resource error? Thanks!


**** (2026-10-05 20:15, 0 votes)
i am getting competition submission failed error again and again.why?


**** (2026-09-26 11:52, 0 votes)
Same resource error here. Submission 56566212 (2026-09-26 01:49 UTC): a plain YAML bundle, no adapters and no LoRA, one model (gemma-4-31b-it-qat-w4a16-ct). It completed with no score, and the error_description was "Your notebook has requested more CPU, GPU or TPU resources than are available." Earlier bundles from the same pipeline, with the same structure, were scored normally. The bundle passes validate_directory and compile_submission locally. It still used the daily submission slot.

Thanks for looking into it, @ryanholbrook. I'll resubmit the same bundle when the next slot opens and report back here. Could the slot be restored for submissions that failed with this error before the fix?


**** (2026-09-26 11:34, 0 votes)
Same here: submission 56571006 (2026-09-26 06:11 UTC, a plain YAML bundle with no adapters, ~3 KB zip) completed with no score and the message "Your notebook has requested more CPU, GPU or TPU resources than are available." (UI: "Notebook Exceeded Allowed Compute"). @ryanholbrook, if slots are being restored for this platform-side error, we'd be grateful for ours too. Thanks!


---

## The baseline agent repeats the same command up to 69 times (local eval, 10 tasks)
/competitions/gemma-4-developer-agent/discussion/745774 | by  | posted 2026-10-04 10:19 | last comment 2026-10-05 19:38 | 4 comments | 4 votes


**** (2026-10-04 10:19, 4 votes)
Ran the official evaluator on Kaggle (L4 x4) on 10 spread-out tasks from `tasks.jsonl`, with a 10-minute / 100-tool-call budget per task and the public analyzer+coder bundle.

- 4 of 10 tasks used 92-97 of 100 tool calls.
- In one, the same `python3 -c` command ran 69 times; in another, the same `grep` ran 46 times. 0-2 edits, no test runs.
- The system prompt already says "never run the same command twice unchanged". The model ignores it once it's in a loop.
- Temp 0.7 made it worse (5/10 tasks looped, 66 calls on average vs 36). Temp 0.7 + thinking_budget 4096 resolved 3/10 but within noise.
- Re-running the same baseline resolved 3/10, then 1/10. Treat small score differences as noise.

The harness's registries are closed, so custom callbacks can't break loops from the bundle. Has anyone found a prompt or sub-agent structure that actually stops repetition?


**** (2026-10-05 19:06, 0 votes)
Adding a data point. Initial exploration, not exhaustive.

Two local runs, same backend, temperature 0.2:
  run_01:  9 tasks -> 317 tool calls total,  89 min wall
  run_02: 13 tasks -> 711 tool calls total, 198 min wall

Three tasks hit the 100-call ceiling (fastapi_14262, fastapi_14266, rich_3063) and one reached 95 (rich_3064). Two failure shapes:
  - repeated identical commands (same `python3 -c` / `grep` over and over), and
  - edit thrashing: one task made 18 `edit_file` calls on the same file; another used
    62 calls with 16 harness "continuation nudge" prompts.

One task that had resolved in run_01 regressed in run_02 because the submitted patch did not even compile (escaped quotes written into the source by an edit), i.e. no compile check ran before submit.

The prompt already says "never repeat an identical command or search"; the model ignores it once it is looping, which matches the OP. Reducing the per-task call budget helped contain the blast radius more than any prompt wording we tried.

Caveat: small sample and high run-to-run variance (OP reports 3/10 then 1/10 on reruns).


> **** (2026-10-05 19:20, 0 votes)
> Useful data point, thanks. The temperature spread is the part I find most telling: you're at 0.2 and still hitting the ceiling on three tasks, I was at 0.7 and saw it get worse (5/10 looped, 66 calls on average vs 36). So looping isn't a sampling-temperature artifact, it shows up across the range.
> 
> The edit thrashing is a shape I didn't see. My looping tasks were read-heavy: same python3 -c 69 times, same grep 46 times, 0-2 edits, no test runs. Yours burned 18 edit_file calls on one file. Those may want different fixes. The read loop is the agent not noticing it already has the answer; the edit loop is it not verifying the edit landed.
> 
> The compile regression is the one I'd act on first, because it's separable from the loop problem. A patch that doesn't compile is a free loss, and checking it doesn't need the closed registries, it can just be the last step in the bundle before submit. I haven't wired that up yet.
> 
> Agreed that lowering the call budget beat prompt wording. It doesn't stop the loop, it caps what the loop costs, which given how little "never run the same command twice unchanged" seems to bind may be the honest trade.
> 
> And yes, noise. 3/10 then 1/10 on identical reruns, so I'm treating anything under a couple of tasks as unmeasurable.


> > **** (2026-10-05 19:28, 0 votes)
> > Correcting myself: I said I hadn't wired up a pre-submit compile check. I had. It's already in the bundle I ran. Workflow step 4 of the system prompt is `python -m py_compile <file> && python -m pytest <closest test path> -x -q`, with a git diff review in step 5 before submit_patch().
> > 
> > That makes your compile regression more interesting, not less. The instruction was present and the model skipped it anyway, which is the same shape as it skipping "never run the same command twice unchanged" once it's looping. Two different instructions, one failure mode: they hold until the run goes sideways, then they stop binding.
> > 
> > And it can't be promoted from a request to a guarantee. From HARNESS_README, adk-submission compiles the submission "without executing arbitrary competitor Python code (importlib is never used)", and the tool/model/callback registries are closed. So there's no pre-submit hook to hang a hard compile gate on. Prompt wording is the only lever available, and it's the lever we have both now watched fail.
> > 
> > Which is why I think your budget result is the right read. If you can't make the agent reliably verify, capping what it can spend before submitting is the only remaining thing that changes the outcome.


> > **** (2026-10-05 19:38, 0 votes)
> > Thanks, and thanks for the correction — that matches our experience exactly.
> > 
> > We also have the pre-submit compile step wired in (a verification-before-submit skill plus a prompt rule), and in one run the agent still submitted a patch that did not compile (escaped quotes written into the source by an edit). So we agree: having the step in the prompt does not make it run.
> > 
> > On the two shapes: our read-loop rule ("never repeat an identical command") is in the prompt and does not bind. The edit loop is the one we had not covered; we are going to try a shape-specific rule — after every edit, re-read the changed region (or re-run the reproduction) before editing again, so the agent confirms the edit
> > landed instead of stacking another one.
> > 
> > Question: have you found any wording that actually binds the read loop, or is capping the call budget the only thing that reliably limits it?


---

## The first task in the list (fastapi_15661) seems unsolvable from the prompt alone: hidden tests import names that appear nowhere in the task
/competitions/gemma-4-developer-agent/discussion/745855 | by  | posted 2026-10-04 22:19 | last comment 2026-10-05 19:08 | 2 comments | 8 votes


**** (2026-10-04 22:19, 8 votes)
Hi all,

I'd like to check whether others are seeing the same thing, or whether I'm missing something.

The task: fastapi_15661, the first task in the list, so it's the first one every agent tries. The whole problem statement is the title "👷 Automate release preparation", followed by the empty PR template. The only extra hint is a link in the AI disclaimer to a PR in a different repo, which can't be opened because the sandbox is offline.

What the hidden tests require: The test_patch imports a specific module path, a specific set of function and class names, specific CLI subcommands and options, specific environment variable names, and exact error message strings. I'm not going to list them here, but none of them appear in the task text or anywhere in the repo.

What my agent did: It explored the repo, found an existing related script, and wrote a reasonable new script that worked when run. The result:

resolved=False, exit_code=2, patch_chars=3246, tool_calls=27

My understanding is that exit code 2 is pytest stopping at collection, because the module the tests import doesn't exist under that name. I haven't confirmed this inside the harness, so please correct me if that's wrong.

Why this bothers me: Nothing in the prompt or the repo tells the agent what the file, the classes, or the env var prefix must be called. I don't think any prompt or model can get this right except by luck. A correct, working solution with different names scores the same as an empty patch.

Questions:

Have you seen other tasks where the names the tests need appear nowhere in the task text?

Is the benchmark meant to reward guessing names, or is this a gap in the task?

Has anyone found a good way to handle these cases?

Side note: the 5-minute limit was also tight. About 295 s went to 27 tool calls, mostly model generation time.

Thanks!


**** (2026-10-05 02:02, 3 votes)
You're reading it right: exit code 2 is pytest stopping at collection on the missing module.

It is not only this task. I checked all 129 public tasks for the same pattern: the tests import a module or name that (a) exists nowhere in the repo at the base commit, (b) is introduced by the reference patch, and (c) is never mentioned in the problem statement.

6 of 129 tasks match:
- fastapi_15661: module scripts.prepare_release and six names in it
- fastapi_15030: module fastapi.sse (EventSourceResponse, ServerSentEvent)
- rich_3930: module rich._unicode_data, plus private names such as _parse_version
- fastapi_14609: PydanticV1NotSupportedError
- fastapi_15785: RouteContext
- fastapi_15745: three private names (e.g. _IncludedRouter)

If I also count identifiers the tests use without importing them (new methods, constants), it is 16 of 129. That count is looser.

In my runs Gemma solved none of the hidden import tasks I can verify locally (0 of 4), against 41 of the other 109. So for local validation I now leave these out: they only add zeros. In a scored run the practical answer is to not spend the time budget on them.

Some names are guessable from convention (fastapi.sse), others are not (a private helper name). The check is static, so treat the list as a lower bound.


**** (2026-10-05 19:08, 0 votes)
Agreeing, with two concrete cases. Initial exploration, not exhaustive.

- fastapi_15661: the hidden test requires exact names/signatures that appear nowhere in the problem statement, hints, snapshot git history, or existing scripts. The agent finds the right file but with a different API. Not winnable without seeing the test.

- fastapi_14301: fails before the agent can matter. Phase 2 collection raises `TypeError: Router.__init__() got an unexpected keyword argument 'on_startup'` at fastapi/routing.py — a base-snapshot vs installed-starlette incompatibility, not an agent failure.

Several public tasks are also known-broken offline (missing test deps; VERIFY_X509_STRICT on py3.13 breaking https tests). Suggest filtering a "winnable" subset before comparing any change, otherwise the measured rate is dominated by noise.

Caveat: initial exploration, not an exhaustive audit of all 129 tasks.


---

## Note on Code Graphs for Async Functions
/competitions/gemma-4-developer-agent/discussion/745998 | by  | posted 2026-10-05 17:37 | last comment 2026-10-05 17:37 | 0 comments | 7 votes


**** (2026-10-05 17:37, 7 votes)
There have been a number of discussion posts pointing out that `async def` functions are not included in the code graph tools. This is true and is an issue for some of the public tasks in fastapi and httpx. 

However, it is not an issue for any of the private repo tasks. 

None of the private repo tasks touch any functions defined with `async def`. Additionally, `async def` functions are rare within the private repos as a whole, at most 1.8% of functions. 

As a result, we will not be doing an update to the private tasks' code graphs.


---

## inline_snapshot wheel missing for notebook environment but required by tasks
/competitions/gemma-4-developer-agent/discussion/745850 | by  | posted 2026-10-04 21:27 | last comment 2026-10-05 15:57 | 1 comments | 0 votes


**** (2026-10-05 15:57, 0 votes)
Same as me.

I found dependency issues in my local baseline environment. Tests could not import `inline-snapshot`, `dirty-equals`, or `attrs`, and some reported multipart validation errors or recursive `httpbin` fixture dependencies.

I built a separate sandbox image with the required packages and test plugins, keeping the original official image unchanged. Those errors disappeared in the completed results.

I also checked package versions after harness setup, because setup can overwrite packages installed in the image. This revealed a remaining issue: `httpcore` requires `h11`, but `h11` is missing. I confirmed that it breaks `httpcore` imports and default `httpx.Client` initialization; I haven’t fixed that yet.

Some apparent “dependency errors” were actually incomplete model patches. I tested five cases with the same environment: the model patches failed, while the reference source fixes passed without adding packages.

These findings are from my local setup. I haven’t confirmed whether the official Kaggle environment has the same issues.


**** (2026-10-04 21:27, 0 votes)
In the starter notebook, tests that import inline_snapshot fail at collection with ModuleNotFoundError (e.g. fastapi tasks where tests/ use from inline_snapshot import snapshot). The wheels/ folder has no inline-snapshot wheel. Is this expected in the scoring environment too, or does the scorer env have it installed?


---

##     Can the agent sandbox run the repository's own tests?
/competitions/gemma-4-developer-agent/discussion/745980 | by  | posted 2026-10-05 15:56 | last comment 2026-10-05 15:56 | 0 comments | -3 votes


**** (2026-10-05 15:56, -3 votes)
Hi @ryanholbrook,  
we’d like to clarify whether the environment where the agent works is expected to be able to run the repository’s own tests.

You mentioned in #742882 that the private grading sandbox uses a different dependency set from the public one, and that the hidden tasks validate 100% with gold patches. So we understand that the final validation environment can run a correct solution.

*What we’re less clear about is the environment where the agent actually investigates and develops that solution.*

In the public data, all FastAPI tasks currently get Starlette 1.6.0. But the FastAPI snapshots themselves require Starlette below 1.0; 38 of the 67 tasks specify <0.51.0.

With Starlette 1.6.0, even creating FastAPI() fails with:

Router.__init__() got an unexpected keyword argument 'on_startup'

That means the agent can’t run the project’s tests to evaluate its own changes, regardless of whether its patch is correct. When we keep Starlette below 1.0, the reference fixes work again; we’ve checked this on eight FastAPI tasks in Docker.

Pls, could you clarify two things?
1. In the actual scorer, does the agent’s working sandbox use dependencies compatible with the task repository, like the final validation environment does?
2. Could the public wheels/ selection be adjusted to respect the dependency constraints of each repository snapshot, so results on the public FastAPI tasks are representative?

Thanks!
Mugur B.


---

## Context overflow can discard an already-correct patch
/competitions/gemma-4-developer-agent/discussion/745977 | by  | posted 2026-10-05 15:51 | last comment 2026-10-05 15:51 | 0 comments | -4 votes


**** (2026-10-05 15:51, -4 votes)
Hi @ryanholbrook - we ran into a context-window failure that seems to discard work the agent has already completed.

On Kaggle (L4 x4, swegemma 0.2.7, adk-submission 0.2.12, vLLM 0.19.1), while running public task requests_7309, the agent had already made the correct edit. After 20 tool calls, however, the next model request failed with:
'This model's maximum context length is 32768 tokens. However, you requested 8192 output
tokens and your prompt contains at least 24577 input tokens, for a total of at least 32769 tokens.'

The harness then reported ContextWindowExceededError, followed by Error during sandbox execution, and the task finished with exit=-1 and an empty patch.

We were using the compaction settings from the Getting Started notebook (token_threshold: 14336), but the prompt still reached 24,577 tokens.

The practical problem is that with max_output_tokens: 8192, anything above 24,576 input tokens cannot be sent to the model — and if that happens, an otherwise valid working-tree change is lost.

Could the scorer handle this by either:

1. compacting and retrying (or reducing the available output-token budget to what still fits), or
2. collecting the current working-tree patch when a model error terminates the session, in the same spirit as the timeout fallback?

Also, does the scorer use the same compaction settings as the Getting Started notebook?

This seems related to the failure mode discussed in #745028, where an exception can terminate the task before the working-tree fallback gets a chance to run.

Thanks!
Mugur B.


---

## Clarification request: external LLMs as training-data teachers
/competitions/gemma-4-developer-agent/discussion/745961 | by  | posted 2026-10-05 14:19 | last comment 2026-10-05 15:33 | 1 comments | 0 votes


**** (2026-10-05 15:33, 0 votes)
https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742807#3530102

This should answer it


**** (2026-10-05 14:19, 0 votes)
Are competitors permitted to use commercially available proprietary LLMs such as OpenAI Codex/GPT or Anthropic Claude during development to generate or label supervised fine-tuning/distillation data for LoRA adapters applied to the required Gemma 4 model? The scored submission itself would contain and run only gemma-4-31b-it-qat-w4a16-ct agents/subagents and competition-permitted adapters; no external LLM or API would be called during inference. If permitted, are there disclosure, accessibility/reasonableness, or redistribution requirements for the generated training data?


---

## What happens when a submission reaches the 12-hour limit?
/competitions/gemma-4-developer-agent/discussion/743162 | by  | posted 2026-09-25 04:19 | last comment 2026-10-05 13:52 | 2 comments | 0 votes


**** (2026-10-05 13:52, 0 votes)
how many submissions are allowed in total and is there a daily limit?


**** (2026-09-25 06:00, 0 votes)
@whisperlast
https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743063#3527819

Kaggle staff answered your questions nearly in this thread so check it out 🙋


**** (2026-09-25 04:19, 0 votes)
Hi organizers,

The Evaluation section says the agent has 12 hours to submit patches for all tasks, including sandbox setup, and that per-task limits in `eval_config.yaml` are optional. To pick a sensible per-task budget, it would help to know how the scoring run behaves at the limit:

1. If the 12 hours run out before every task has been attempted, are the patches that were already produced still scored (and the remaining tasks counted as unresolved), or does the whole submission fail with an error?
2. Are the hidden tasks run one at a time (concurrency 1, as in the `swegemma eval` default) on the 4x L4 machine, or several in parallel?
3. If `eval_config.yaml` is omitted, is the per-task limit the 60-minute default from HARNESS_README, or is there another cap in the scoring run?

Thanks!


---

## Why official starter notebook fails in second with no specific error msg
/competitions/gemma-4-developer-agent/discussion/745320 | by  | posted 2026-10-03 02:10 | last comment 2026-10-05 13:29 | 4 comments | 1 votes


**** (2026-10-03 02:10, 1 votes)
Easy step to reproduce: 
1) Copy and Run from [ryanholbrook](https://www.kaggle.com/code/ryanholbrook/getting-started-gemma-4-developer-agent)
2) You see immediate fail

I am assuming this is part of GPU issue that people talked about? But GPU issue for immediate failure? really? Appreciate your help in advance. 

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F5578954%2F342551f690c65838c3609b43f4309642%2FScreenshot%202026-10-03%20at%2011.06.23AM.png?generation=1790993244280411&alt=media)


**** (2026-10-03 07:26, 0 votes)
Hi Shoto! To submit your work you need to wait till your notebook will be finished, dont cancel it. After that you go to submissions section and press submit prediction,then notebook part. Select exact notebook and press submit. So after this procedure your submission will have score, you just need to wait for 10-12 hours`


> **** (2026-10-04 14:47, 0 votes)
> @kozykappa 
> Hi, thanks for the suggestion. I followed those steps, which I let the notebook finish, submitted the completed notebook version from the Submissions page, and did not cancel it. However, my submission has now been waiting for about 13 hours without getting a score. At this point, I suspect this may be related to the competition GPU queue rather than the submission procedure itself.  
> If anyone else is seeing the same behavior, please let me know!! It would also be helpful if the organizers could clarify whether this is expected at the moment. 
> 
> ![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F5578954%2F31ce5d4de8a24cce01c200acf9ec05b1%2FScreenshot%202026-10-04%20at%2011.43.52PM.png?generation=1791125049795083&alt=media)


> > **** (2026-10-04 17:06, 1 votes)
> > Oh, you just need to wait till it comes to your order to use GPU, most of the users are utilizing L4 x4, dont worry competition author will solve this problem asap, wait and your notebook will run, after full run you can submit your notebook to score, score will run without queue


> > **** (2026-10-05 13:29, 0 votes)
> > @kozykappa 
> > thank you, you are the best.


---

## Discussion : Are you guys seeing gains with distillation? What's your setup?
/competitions/gemma-4-developer-agent/discussion/745274 | by  | posted 2026-10-02 21:16 | last comment 2026-10-05 05:10 | 1 comments | 0 votes


**** (2026-10-05 05:10, 0 votes)
please are you also participating in casmi competition


**** (2026-10-02 21:16, 0 votes)
As the title suggests, I want to know if any of you have had moderate success refining gemma 4's own trajectories to use as training material for a LoRA adapter, or if you have been using an opensource model as a teacher. On my local evals, using Deepseek V4.1 Flash yielded barely any returns (solved 5 more tasks than my own agent) when put under the same constraints of max time per task and my multi-agent harness setup.
Given that literature seems to suggest that you can hope to recover at best 30-50% of the gap between student and teacher, I wanted to understand what sort of strategies people who've found success with distillation have been employing - I've already wasted around 20 dollars worth of api on barely useable results.


---

## CuriosIT: Autonomous Bare-Metal Diagnostics with Gemma 4 on Android (100% Offline & Air-Gapped)
/competitions/gemma-4-developer-agent/discussion/745818 | by  | posted 2026-10-04 15:44 | last comment 2026-10-04 15:44 | 0 comments | 0 votes


**** (2026-10-04 15:44, 0 votes)
The competition prompt poses a great question: 
> *"What if every developer could rely on an autonomous agent equally capable offline, on consumer hardware?"*

We took this challenge directly to bare-metal hardware and End User Computing (EUC) field diagnostics. 

Meet **CuriosIT** — an autonomous hardware-assisted diagnostic copilot that operates 100% offline with zero cloud data exfiltration.

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F14281703%2F8e9b618f9570f4f9498406e8645d6643%2FScreenshot_20261004-142322.png?generation=1791129424497129&alt=media)

### 🛠️ The Architecture
1. **Neural Core:** Google **Gemma 4B** running 100% locally on a mobile device (Google Pixel) using **Google LiteRT-LM** with INT4 quantization on the Tensor NPU/GPU.
2. **Physical Hardware Bridge:** A compact **ESP32-S3** USB dongle running custom dual-mode firmware (simultaneous USB HID keystroke injection + CDC virtual serial loopback) with hardware SPI telemetry on an IPS LCD.
3. **Air-Gap Compliance:** The target machine (which may be broken, offline, or in a restricted environment like healthcare/finance) has NO internet connection. All telemetry streams locally over an encrypted BLE NUS link to the phone.

---

### ⚡ Live Field Test Example
During a live terminal troubleshooting session on a bare-metal Linux host:
- The technician asked Gemma on the phone: *"i need to find all attached usb"*.
- Gemma reasoned locally on GPU and prepared the diagnostic action: `[ ⚡ INJECT TO PC: lsusb ]`.
- With a single tap, the dongle typed `(lsusb) 2>&1 | tee /dev/ttyACM0` into the host bash terminal and streamed the raw bus output back to the phone.
- Next prompt from technician: *"whats for keyboard?"*
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F14281703%2F3ffc42fc48f8a99a8dc6a9b356affbb0%2FScreenshot_20261004-142734.png?generation=1791129469122347&alt=media)

![![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F14281703%2F2263a14c1bc2e035f8caae31c1017d89%2FPXL_20261004_132746974.jpg?generation=1791129508420659&alt=media)](url to embed)
- **Gemma on GPU response:**
  > *"Sorted mate, you've got a Corsair K55 CORE RGB Gaming Keyboard attached there."*

No cloud calls, no external API keys, sub-second reasoning, and accurate hardware identification at the physical terminal!

---

### 💡 Why This Matters for Autonomous Agents
- **Democratizing Enterprise IT:** A $20 USB dongle and a consumer mobile phone replace a bulky $2,500 rugged technician workstation.
- **Strict Air-Gap Safety:** Ideal for hospitals (NHS), defense, and banking where uploading system logs or internal network topologies to public cloud LLMs is strictly prohibited.
- **Enterprise MCP Ready:** Architected to link with Active Directory (LAPS) and PDQ Deploy via Model Context Protocol.

We'd love to hear your thoughts, feedback, and ideas from the DeepMind team and the community!


---

## Validating locally: how representative are the public tasks, and can we see per-task outcomes?
/competitions/gemma-4-developer-agent/discussion/745800 | by  | posted 2026-10-04 13:33 | last comment 2026-10-04 13:33 | 0 comments | 1 votes


**** (2026-10-04 13:33, 1 votes)
Hi, a few questions about testing against the hidden set:

Are the public tasks in the dataset drawn from the same distribution as the ~120 hidden tasks: similar repo size, patch size and test setup? Our local resolve rate on public tasks is far above our leaderboard score, so we suspect the hidden set differs in some systematic way.

Is there any way to see a breakdown for a submission, even just counts: tasks that errored, tasks that ended with an empty patch, tasks whose tests failed, tasks that hit the time limit? Without it, a score can't tell us whether a failure comes from the agent or the environment.

Is the agent's sandbox during scoring the same as in the walkthrough notebook? In particular: is /tmp writable, is python3 on PATH, are shell heredocs supported in run_command, and does the scorer use the same wheel set and Python version as the notebook?

Would the hosts consider releasing a small validation subset of private-style tasks, or a local script that matches the scorer exactly, so we can check that a submission behaves the same before we use a daily slot?

Thanks!


---

## Expected domain shift between the provided repositories and hidden evaluation
/competitions/gemma-4-developer-agent/discussion/745796 | by  | posted 2026-10-04 13:22 | last comment 2026-10-04 13:22 | 0 comments | 6 votes


**** (2026-10-04 13:22, 6 votes)
Hi organizers,

Could you clarify how representative the four provided repositories—FastAPI, HTTPX, Rich, and Requests—are of the hidden evaluation distribution? In particular, I’m interested in the potential for domain shift along two dimensions:

1. **Programming languages:** According to GitHub’s language breakdown, all four provided repositories are over 99% Python. Should we expect the hidden evaluation repositories to be similarly Python-dominated, or could they contain substantial code in other languages?

2. **Application domains:** The provided repositories cover web frameworks, HTTP clients, and terminal formatting. Will the hidden evaluation draw from broadly similar domains, or could it include substantially different types of projects, such as machine learning or scientific computing libraries like PyTorch?

More generally, is the evaluation intended to measure generalization within a similar set of software domains, or across a broader range of repositories and ecosystems?

Any high-level guidance on the intended scope would help participants understand which assumptions about the provided data are reasonable when developing their agents.

Thank you!


---

## Expose ADK `exit_loop` as an allowed tool for LoopAgent submissions
/competitions/gemma-4-developer-agent/discussion/745792 | by  | posted 2026-10-04 12:32 | last comment 2026-10-04 12:32 | 0 comments | 2 votes


**** (2026-10-04 12:32, 2 votes)
I am building a declarative ADK submission with a `SequentialAgent` containing a `LoopAgent` (`max_iterations`) whose children are a `Worker` and a `Solver`.

In `google-adk==1.36.1`, the built-in `exit_loop` tool sets `tool_context.actions.escalate = True`, and `LoopAgent` checks that flag to stop early. However, when I add `tools: [exit_loop]` to the Solver YAML, the local `adk-submission==0.2.12` compiler rejects it because `exit_loop` is not in the tool registry. As a result, the Solver cannot request an early exit through this tool, and the loop runs until `max_iterations`.

Could `exit_loop` be registered in the submission tool allowlist, with an example of how the Solver should declare and call it? A CPU-only harness check could verify both paths: the Solver escalates and the loop exits early; without escalation, the loop runs to `max_iterations`.


---

## One of my test notebooks with GPU queued for 3+ hours.... is there really so much demand?
/competitions/gemma-4-developer-agent/discussion/745625 | by  | posted 2026-10-03 12:18 | last comment 2026-10-04 12:25 | 4 comments | 3 votes


**** (2026-10-03 12:18, 3 votes)
![Queued/Stuck Notebook Run](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F2384691%2Ffa6ca490c5723edd0aeea50deb31230c%2FScreenshot%202026-10-03%20174711.png?generation=1791029860864236&alt=media)

One of my test notebooks with GPU queued for 3+ hours.... is there really so much demand?
For context: I am trying to compare frontier agents vs my Gemma Agent for solving the tasks....


**** (2026-10-04 10:58, 1 votes)
@ryanholbrook im also facing same issue, mine one is queued since 4 hrs.


> **** (2026-10-04 12:00, 1 votes)
> sadly it is a problem. but you need to wait and soon enough it will start to run. mine were sometimes queued for 5+ hours then started running


**** (2026-10-04 12:25, 0 votes)
:-( pareille plus de 3h


---

## How to get started + Competition's Official Discord
/competitions/gemma-4-developer-agent/discussion/742815 | by  | posted 2026-09-23 16:34 | last comment 2026-10-04 12:01 | 2 comments | 8 votes


**** (2026-09-23 16:34, 8 votes)
### Information for newbies

Welcome! 
**New to machine learning and data science?** No question is too basic or too simple. Feel free to start your own thread, or use this thread as a place to post any first-timer clarifying questions for the Kaggle community to help you with!

**New to Kaggle?** Take a look at a few videos to learn a bit more about [site etiquette](https://www.youtube.com/watch?v=aIus8si_Et0), [Kaggle lingo](https://www.youtube.com/watch?v=sEJHyuWKd-s), and [how to enter a competition using Kaggle Notebooks](https://www.youtube.com/watch?&v=GJBOMWpLpTQ). Publish and share your [models on Kaggle Models](https://www.kaggle.com/docs/models#publishing-a-model)!

**Participants under 18 years old:** If you are under 18 years old and want to participate in this competition, you need to submit a couple of forms:
- Form #1: [Parent/Guardian consent for minor's use of kaggle.com](https://www.kaggle.com/guardian-consent-minor-use). You only have to fill this out once, and it is valid for any competitions on Kaggle. If you already filled this out in the past, you can move on to the next form. 
- Form #2: [Parent/Guardian consent for minor's participation in Kaggle competition](https://www.kaggle.com/consent-minors-process). You have to fill out form #2 for this and any future competitions you want to join. 
Kids under 13 years of age are not allowed to participate on Kaggle. If you have any questions, please leave a comment and we'll follow up with you!

**Looking for a team?** Express your interest in joining a team through our [Team Up](https://www.kaggle.com/discussions/product-feedback/341195) feature.

**Remember**: Kaggle is for everyone. Whether you're teaming up or sharing tips in the competition forum, we expect everyone to follow our Kaggle community guidelines.

### Competition's Official Discord
In addition to this competition forum, you can continue the discussion in our official Kaggle Discord Server here:
# [discord.gg/kaggle](http://discord.gg/kaggle)
 
The Discord is a great place to ask getting started questions, chat about the nuances of this competition, and connect with potential team mates. Learn more about Discord at our [announcement here](https://www.kaggle.com/discussions/general/429933). Here are a few things to keep in mind though:

**1. Discord Competition Channels are 'Public' - Don't Share Private Information**

Discord channels for specific competitions are considered 'public' spaces where you are allowed to talk about competition details. Please remember that private sharing of competition code or data outside of your team is, as always, not permitted. Code sharing must always be done publicly through the Kaggle forums/notebooks.

**2. Discord Competition Channels are Not Monitored by Staff - Keep Important Information on the Kaggle Forums**

Kaggle Staff and Hosts running competitions will not monitor Discord or be available to answer questions in Discord. This is intended to be a more casual space to discuss competitions and help each other. Please keep important questions, insights, writeups, and other valuable conversation on the Kaggle forums. 

Happy modeling!


**** (2026-10-04 12:01, 1 votes)
Please review this discussion https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/745775


**** (2026-09-28 15:13, 0 votes)
I get invalid invite error in discord, is it a problem in my side or others have the same problem as well?


---

## With LoRA enabled, the 4xL4 KV cache shrinks to ~7.6k tokens; requests longer than that hang
/competitions/gemma-4-developer-agent/discussion/744331 | by  | posted 2026-09-29 12:28 | last comment 2026-10-04 11:22 | 4 comments | 5 votes


**** (2026-09-29 12:28, 5 votes)
Hi @ryanholbrook,

We measured this on a Kaggle notebook with the L4x4 accelerator, using the getting-started notebook's install cell and its exact VllmConfig (TP=4, max_model_len 32768, gpu_memory_utilization 0.90, enable_lora=True, max_loras=8, max_lora_rank=128), launched via VllmServer.build_cmd():

- No adapters in the submission (no LoRA flags emitted): GPU KV cache = 46,048 tokens.
- Only the sample main_lora adapter (rank 4): GPU KV cache = 7,600 tokens (1.74 GiB free per GPU). vLLM preallocates LoRA buffers for max_loras x max_lora_rank, so the adapter's own size doesn't matter, and build_cmd() passes --max-loras max(8, number of adapters) and --max-lora-rank 128, so a submission cannot lower them.
- With that server, a ~6.9k-token prompt completes, but a ~20.7k-token prompt never starts (vLLM logs "Running: 0 reqs, Waiting: 1 reqs" for 600 s). This happens for both the base model name and the adapter name.

Agent conversations routinely exceed 7.6k tokens, so any submission that carries an adapter would stall on most tasks.

1. Does the scoring environment use these same LoRA settings?
2. If so, could the scorer use smaller values (e.g. max_loras = the number of adapters actually submitted, and/or a lower max_lora_rank), or otherwise reserve more KV cache?

Thanks!


**** (2026-10-04 11:22, 0 votes)
Here's what Claude has to say, below. I hope that it helps.

> With wheelhouse v28 on 4xL4 (util 0.80, TP 4, vllm 0.19.1), a single rank-16 adapter now loads and serves. Prompts of 28k
> tokens complete and agent runs reach 25k-token prompts, so the 744331 hang is fixed. The KV cache still drops from 36,432 to
> 27,712 tokens (0.76x, 8.34 -> 6.34 GiB per GPU). Almost all of the loss is CUDA-graph specialization: with LoRA, vLLM
> captures every graph twice (PIECEWISE 51 -> 102, FULL 35 -> 70; graph memory 2.19 -> 4.07 GiB estimated). The rank-16
> buffers themselves cost about 0.1 GiB. A bundle with an adapter sends every request to that adapter, so the no-LoRA graphs
> are never used. Could the scorer pass `compilation_config={"cudagraph_specialize_lora": False}` when `--enable-lora` is set?
> We measured this on the same 4xL4 stack, adding the flag through `VllmConfig.extra_args`. The adapter run then keeps 34,288
> of the base's 36,432 tokens (0.94x, 7.85 vs 8.34 GiB), with 51/35 graphs instead of 102/70. The 16k and 28k prompts and an
> agent task through the adapter run normally.

I can share logs if needed. Just let me know.


**** (2026-09-30 16:30, 0 votes)
Thanks for the report. I will patch to set the `loras` parameters based on the submission. It looks like a bug in our vLLM version is causing the hang, but I think I have a workaround.


> **** (2026-09-30 23:12, 0 votes)
> A related data point: our adapter submission 56719837 (sent 2026-09-30 22:04 UTC) completed after about 30 minutes with no score and "Your notebook hit an unhandled error while rerunning your code." The bundle is identical to our submission 56659914, which scored 0.06, plus adapters/trained_lora/ (PEFT LoRA, r=64, lora_alpha=64, target_modules q/k/v/o/gate/up/down_proj, 980 MB safetensors). It's referenced as adapter: trained_lora on the root agent and on both AgentTool sub-agents. It is within the HARNESS_README limits, and it compiles with the v25 wheels. An adapter of the same shape loaded and served ~4K-token prompts through VllmServer in a Kaggle 4xL4 notebook. Could you check what raised in this run, and whether it's related to the loras patch? If it was on the scorer side, a rerun once the fix is live would be much appreciated.


**** (2026-09-30 14:13, 0 votes)
Independent confirmation with a trained rank-64 adapter, same setup (Kaggle L4x4, wheelhouse v25, the getting-started `VllmConfig` launched through `VllmServer.build_cmd()`: `--enable-lora --max-loras 8 --max-lora-rank 128`, `--max-model-len 32768`, `--gpu-memory-utilization 0.9`, TP 4).

Startup log with the adapter mounted:
- `Available KV cache memory: 1.74 GiB` (per GPU)
- `GPU KV cache size: 7,600 tokens`
- `Maximum concurrency for 32,768 tokens per request: 1.43x` (misleading, see below)

Chat completions, 64 output tokens:
- ~4,000-token prompt: served by the base model (7.9 s) and by the adapter (5.4 s).
- ~14,000-token prompt: **never returns**, for the base model name and the adapter name alike (900 s read timeout each). No error; the request stays in the waiting queue. With `scheduler_reserve_full_isl` (default true) the scheduler waits for KV space that can never be freed, so the request hangs until `max_time_minutes` ends the task.

This narrows your bound: the limit sits between ~4K and ~14K, consistent with the 7,600-token figure. The arithmetic also matches: this model stores ~246 kB of KV per token per GPU at TP 4 (16 KV heads x 256 head_dim x 60 layers, bf16), so 1.74 GiB holds 7,600 tokens and 46,048 tokens need ~10.5 GiB. Mounting one adapter under the defaults removes ~8.8 GiB of KV per GPU, while a single rank-64 adapter's weights are ~0.2 GB per GPU.

In our evaluation runs under the notebook's compaction settings, 99% of episodes exceed 7,600 prompt tokens, so a submission that ships an adapter would time out on nearly every task regardless of the adapter's quality. Submissions without an adapter never get `--enable-lora` and are unaffected.

Two changes on the scoring side would fix it:
1. Size the LoRA slots to the submission: `max_loras=1` and `max_lora_rank` equal to the shipped adapter's rank (or a higher `gpu_memory_utilization`), which restores the KV cache.
2. Fail fast on requests that cannot fit (or disable `scheduler_reserve_full_isl` for this hybrid-attention model), so an oversized prompt returns an error instead of consuming the whole task time limit.

@ryanholbrook could you confirm which `VllmConfig` the private scorer uses when an adapter is present? If it is the notebook default, LoRA submissions are currently scored under a 7,600-token context.


---

## Repeated “Kaggle Error” on agent submissions — where can I find evaluation diagnostics?
/competitions/gemma-4-developer-agent/discussion/745780 | by  | posted 2026-10-04 10:56 | last comment 2026-10-04 10:56 | 0 comments | 1 votes


**** (2026-10-04 10:56, 1 votes)
Hello everyone,

I am participating with my tAilorCode agent. Four of my submissions have been marked “Kaggle Error”, with this message:

“A system error. Please try resubmitting to resolve the error and contact Kaggle Support if it persists.”

Latest affected notebook: tAilorCode - First Evaluation Optimize, Version 11
https://www.kaggle.com/code/aracelifradejasmunoz/tailorcode-first-evaluation-optimize?scriptVersionId=353365357

Submission time: September 27, 2026, 17:18:58 UTC.

The notebook successfully created /kaggle/working/submission.zip during interactive execution. That archive was 1,683 bytes and contained:
- agent.yaml at the archive root
- eval_config.yaml
- sub_agents/code_analyzer.yaml

The notebook embeds these configurations and needs no network access to create the ZIP. The submission details listed submission.zip under Uploaded Files, but showed no score or specific diagnostic.

Additional checks on the current local baseline:
- The self-contained packaging notebook runs successfully and its generated archive matches the source configurations.
- The official adk-submission 0.2.11 compiler, with google-adk 1.36.1, successfully constructed the agent and AgentTool sub-agent using inert tool bindings and no model inference.

These checks do not establish that Version 11 ran successfully in the evaluation harness or identify the cause of the error. The current packaging uses deterministic ZIP metadata, so its size and hash may differ from the archive reported above.

Kaggle Support replied on September 28 and recommended asking in the competition forum.

Has anyone encountered the same error? Is there a participant-visible evaluation log or traceback? Are there any additional configuration or submission checks recommended before another attempt?

I am continuing development separately in Colab while investigating this, and would appreciate guidance from participants or the competition team.

Thank you,
Araceli


---

## [Multi-Agent SWE Architecture] Separating Bug Investigation from Surgical Patching with Gemma 4
/competitions/gemma-4-developer-agent/discussion/745691 | by  | posted 2026-10-03 18:27 | last comment 2026-10-04 09:27 | 1 comments | 0 votes


**** (2026-10-04 09:27, 0 votes)
and what was your score on the leaderboard with this setup?


**** (2026-10-03 18:27, 0 votes)
Hi Kagglers!

While exploring the Google Gemma 4 Developer Agent Competition, we observed a common failure pattern in naive single-agent setups: when a single model tries to read large repositories, design the architecture, and edit files simultaneously, it often exceeds context budgets or makes broad changes that break existing test suites.

To tackle this, we implemented a Hierarchical Multi-Agent Architecture following Google ADK's declarative standard:

Architectural Overview:

1.code_analyzer (The Investigator - Read-Only):
-Never modifies files.
-Leverages precomputed embeddings and fast AST symbol search (repo-scout) to extract the exact file, lines, and root cause without polluting the context window.
-Outputs a strict structured fix plan (LOCATION, ROOT CAUSE, FIX PLAN).

2.swe_coder (The Surgeon):
-Receives the plan from code_analyzer.
-Executes atomic edit_file replacements preserving existing APIs and backward compatibility.
-Verifies syntax and targeted test sanity in the sandbox before concluding with submit_patch().

3.Deterministic Packaging & ADK Compliance:
-100% declarative YAML tree (agent.yaml, configs/sampling.yaml, eval_config.yaml).
-Adheres to Google's single base model constraint (gemma-4-31b-it-qat-w4a16-ct) and fits cleanly under the size ceiling.

Full code and packaging notebook is available here:
https://www.kaggle.com/code/aryangupta85/gemma-4-developer-agent-swe-architecture

Would love to hear how other teams are handling context management and multi-agent coordination under the 4x L4 GPU constraints! Any feedback or thoughts are welcome. If you find the approach interesting, please consider dropping an upvote!


---

## Hidden test set
/competitions/gemma-4-developer-agent/discussion/744951 | by  | posted 2026-10-01 15:00 | last comment 2026-10-04 08:22 | 2 comments | 1 votes


**** (2026-10-01 15:04, 2 votes)
No, the test set draws from private repositories not available publicly.


> **** (2026-10-04 08:22, 0 votes)
> Does this mean that the test set will contain completely different topics from the training tasks, or will it be fastapi, rich, requests and httpx, but in a different proportion?


**** (2026-10-01 15:00, 1 votes)
same repositories as the training tasks?

The training set covers fastapi, rich, requests and httpx. Does the hidden test set draw from the same four repositories (roughly similar proportions?), or does it include additional repositories?


---

## [Resource & Benchmark] 50 Multi-Turn Gemma 4 SWE-bench Trajectories + Closed-Loop TFD-Agent Framework
/competitions/gemma-4-developer-agent/discussion/745748 | by  | posted 2026-10-04 05:24 | last comment 2026-10-04 05:24 | 0 comments | 1 votes


**** (2026-10-04 05:24, 1 votes)
Hi everyone,

To contribute to the Gemma 4 Developer Agent community and support reproducibility, we have released an open-source trajectory benchmark dataset alongside our research notebook.

### 🌟 Key Open-Source Artifacts:
* 📦 **Dataset (50 Clean Trajectories):** [Gemma 4 TFD Agentic Trajectories & Benchmark](https://www.kaggle.com/datasets/rajrajak99/gemma-4-tfd-agentic-trajectories)
* 📓 **Research Notebook / Architecture:** [TFD-Agent: Autonomous SWE-bench Resolution with Gemma 4](https://www.kaggle.com/code/rajrajak99/tfd-agent-autonomous-swe-bench-resolution-with-ge)
* 💻 **Open-Source Code:** [GitHub Repository](https://github.com/rajrajak99/gemma4-tfd-agent)

---

### 🔍 What is in this Resource?
1. **50 Granular Agentic Trajectories:** Contains multi-turn tool invocations (`search_similar_code`, `get_code_neighbors`, `edit_file`, and isolated bash reproduction) across real-world Python repositories.
2. **Closed-Loop Verification Signals:** Full test-feedback loops showing how the agent detects regression failures and refines patches dynamically.
3. **Graph Tool Diagnostics:** Case studies comparing direct string-search localization against AST code-graph traversal (`networkx` dependency subgraphs).

### 💡 Why this helps competitors:
* **LoRA & SFT Fine-Tuning:** If you are fine-tuning Gemma 4 31B, standard instruction pairs often lack multi-turn agent coherence. These trajectories provide end-to-end multi-turn demonstrations formatted for SFT.
* **Failure Mode Analysis:** Review where agents stall or exceed step limits to tune your `thinking_budget` and turn ceilings.

We would love to hear feedback from fellow competitors and researchers. Feel free to explore the dataset and fork the notebook! 

**Let us know in the comments: what context window and thinking budget configuration is giving you the best stability on the hidden split?**


---

## Notes on the graph tools from auditing all 127 graphs
/competitions/gemma-4-developer-agent/discussion/745731 | by  | posted 2026-10-04 01:14 | last comment 2026-10-04 01:14 | 0 comments | 0 votes


**** (2026-10-04 01:14, 0 votes)
I went through all 127 released code graphs and the tool code in the harness wheel (swegemma 0.2.7), then checked the graphs against calls recorded while fastapi, rich, requests and httpx ran their own test suites. The data page says the hidden set uses identical graph generation, so I expect all of this to hold at scoring time too.

Some of it is already known. Jason Wold reported the missing async defs ([thread 742911](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742911)), and Tarun Singhal found that the tools only match exact names and that the examples in their help return nothing ([thread 745220](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/745220)). Reading the code explains why, and turns up a few more things.

**What the tools do**

- `get_code_neighbors` returns an empty list unless the id matches exactly. The README describes a four-step resolver (exact, suffix, case-insensitive, substring), but 0.2.7 only does the exact step. Ids are full paths like `fastapi.routing.APIRoute`.
- `edge_type` is compared as an exact string, and every stored edge has the type `calls`, lowercase. `CALLS`, `DEFINED_IN` and `IMPORTS` all come back empty.
- The neighbour list doesn't say which way an edge goes. It's sorted alphabetically and cut at `max_neighbors` (50 by default), so the first 50 are just the first 50 names alphabetically.
- `search_similar_code` can't embed free text. It looks up a stored vector by node id or node source, so any other query returns an empty list.

**What the graphs hold**

- Every edge is stored in both directions, and each class is linked to its members with a `calls` edge too. A neighbour can be a caller, a callee or the enclosing class.
- None of the 10,321 `self.m()` calls I could resolve from the node sources are in the graphs, and no graph has a single async def.
- Against the recorded calls (leaving out framework dispatch), the released graphs hold 14 to 21 percent of 6,432 pairs in fastapi, rich and requests. httpx is at 2 percent, since almost all of its calls go to methods.
- The node embeddings follow graph distance much more than code text (Spearman -0.28 to -0.34 with graph distance, 0.06 to 0.18 with TF-IDF similarity of the source).

**What I'd change in an agent**

1. Don't ask the graph who calls a method. Grep for it with `run_command`.
2. Pass the full id, and use `edge_type="calls"` in lowercase or leave it out. An empty list can mean a bad lookup or a missing def, not "nobody calls this".
3. Treat `search_similar_code` as "near this symbol in the graph", not "looks like this code".
4. Start with text search on the issue. On the 122 public tasks that change a non-test def, plain TF-IDF over def names and source puts a changed def in the top 10 for 52 percent of tasks. The embeddings alone manage 9 percent.
5. Skills can ship Python scripts. If one runs in your sandbox, the builder in the notebook makes a fuller graph of the workspace in seconds (I haven't tested that inside the harness). On a fuller graph, ask for more than 50 neighbours, because the alphabetical cut starts dropping real callers.

I also rebuilt every graph in the same format with Python's `ast` module: async defs included, methods kept in their class, and calls through `self` and `super()` resolved. It holds 62 to 69 percent of the same recorded pairs. The notebook has the builder code, rebuilds all 127 graphs from the competition snapshots and reproduces every number above in about eight minutes on CPU. The code and traces are Apache 2.0.

- Notebook: https://www.kaggle.com/code/akhilchinta1505/code-graph-audit
- Call traces: https://www.kaggle.com/datasets/akhilchinta1505/code-graph-call-traces

If a newer wheel changes any of this, I'd like to know.


---

## What Results Did You Get with Representative Submissions?
/competitions/gemma-4-developer-agent/discussion/743140 | by  | posted 2026-09-25 02:09 | last comment 2026-10-03 18:43 | 6 comments | 13 votes


**** (2026-09-25 02:09, 13 votes)
Since this competition allows only **one submission per day**, I’d like to leverage the community to compare results.

I’ll share a couple of examples from my side as well.

### Gemma 4 SWE Agent: Complete EDA & ADK Starter Kit

https://www.kaggle.com/code/nursrijan/gemma-4-swe-agent-complete-eda-adk-starter-kit

I submitted the output as-is and got **LB = 0.05**.

### GEMMA: EDA, Baseline for a start | LB TOP 1

https://www.kaggle.com/code/romanrozen/gemma-eda-baseline-for-a-start-lb-top-1

This notebook currently shows **LB = 0.12**, which appears to be the best score among the publicly available notebooks.

If anyone has submitted this notebook, **what result did you get? Did you get the same score of 0.12?**

Also, in the organizers' discussion titled **"Welcome to the Gemma 4 Developer Agent Competition,"** they mention that:

> we’ve provided a [starter submission](https://www.kaggle.com/competitions/gemma-4-developer-agent/data?select=sample_submission)

**What score did this starter submission achieve on the leaderboard?**

That's all from me. **Please share your results in the comments!** It would be great to compare everyone's findings.


**** (2026-10-03 18:43, 1 votes)
I submitted the sample_submission given in the competition data to the leaderboard today, it gave a score of 0.01


**** (2026-09-25 07:17, 2 votes)
Answering your last question: the **official `sample_submission`, submitted byte-for-byte as-is** (submission `56539111`, 2026-09-25 03:46 UTC) → **FAILED, no score**. Only message: `Your notebook hit an unhandled error while rerunning your code.`

It still contains both `adapters/main_lora` and `adapters/tool_lora`, so my current suspicion is the adapter path. What I mean by that: `adapter: <name>` never goes through local PEFT loading — in `swegemma/models/registry.py` (`resolve_swegemma_adapter`, and `_make_adapter_model` inside `setup_gemma_model_registry`) it rewrites the agent's model into a LiteLLM id of `openai/<adapter-name>`, i.e. the run asks the inference endpoint to serve a LoRA **already registered under that name** (vLLM `--lora-modules <name>=<path>`). For this package the compiled root agent's model string is literally `openai/main_lora`, and `swegemma` itself never starts the server, so that registration lives entirely on the scoring side. I verified locally with the pinned wheels (`google-adk 1.36.1`, `adk-submission 0.2.11`, `swegemma 0.2.7`) that the package compiles clean, that `discover_adapters()` returns both names, and that all 9 tools register unconditionally — so it is not a YAML/assembly bug and not the empty graph/embedding files. This is a hypothesis about the failure, not a confirmed diagnosis.

Worth adding, because it changes how useful your two numbers are: I read the packaging cells of both notebooks — `nursrijan`'s starter-kit bundle writes `configs/ prompts/ sub_agents/ agent.yaml`, and `romanrozen`'s bundle likewise contains no `adapters/` (LoRA appears there only in a validator check and in a roadmap line saying "LoRA adapter, *if the rules allow*"). So neither the 0.05 nor the 0.12 exercises the adapter path, and as far as I can tell **no public submission has**. That is consistent with the failure above being LoRA-related rather than a bug in my packaging.

Next step: same official package with `adapters/` and the two `adapter:` lines removed, nothing else touched. If it scores, the adapter path is the trigger; if it fails the same way, it isn't. I'll report whichever happens.


**** (2026-09-28 02:32, 1 votes)
Are the results deterministic -  I see `"temperature": 0.2` which could have some variation.  Not sure what else could cause non deterministic results


**** (2026-09-25 21:21, 1 votes)
direct fork of https://www.kaggle.com/code/romanrozen/gemma-eda-baseline-for-a-start-lb-top-1 

LB: 0.08
Scoring Time: 14.5 hours
GPU: 4x L4


**** (2026-09-25 14:26, 1 votes)
I have a bare bones submission that got 0.08 https://www.kaggle.com/code/twangygarlic449/gemma-super-basic


**** (2026-09-25 05:54, 1 votes)
GEMMA: EDA, Baseline for a start | LB TOP 1
@isakatsuyoshi as it earned ,stated score 0.12 
So no need to test it using your submission 🙋


---

## Hidden filename requirement in `fastapi_15661` (“Automate release preparation”)
/competitions/gemma-4-developer-agent/discussion/745695 | by  | posted 2026-10-03 18:43 | last comment 2026-10-03 18:43 | 0 comments | 0 votes


**** (2026-10-03 18:43, 0 votes)
Hello @ryanholbrook 

I’m investigating the `fastapi_15661` task at base commit [`1990ecb` (https://github.com/fastapi/fastapi/tree/1990ecb446d4db044e8f2be26758aa42b2c62fa8)](<https://github.com/fastapi/fastapi/tree/1990ecb446d4db044e8f2be26758aa42b2c62fa8>). The visible request is “Automate release preparation” and refers to [Asyncer PR \#608 (https://github.com/fastapi/asyncer/pull/608)](<https://github.com/fastapi/asyncer/pull/608>), but the agent environment is offline.

The base commit contains a release-date script, release notes, and publishing workflows. It does **not** contain `scripts/prepare_release.py` or `tests/test_prepare_release.py`. After my agent submitted a workflow-based patch, verification failed during test collection:

```
from scripts.prepare_release import (...)
ModuleNotFoundError: No module named 'scripts.prepare_release'
```

The [original FastAPI PR \#15661 (https://github.com/fastapi/fastapi/pull/15661)](<https://github.com/fastapi/fastapi/pull/15661>) did add `scripts/prepare_release.py`, but that exact module name is not specified in the visible request or present in the base repository. An agent could guess it from the title; it cannot establish that the hidden tests require it from local evidence.

Is this task intended to require reproducing the referenced PR’s file-level interface? If so, could the task include the required module or command name, or make the relevant reference available offline? That would let agents work toward the behavior the tests actually check without revealing the tests themselves.


---

## Is the swegemma harness available for local evaluation?
/competitions/gemma-4-developer-agent/discussion/742882 | by  | posted 2026-09-23 21:47 | last comment 2026-10-03 11:42 | 12 comments | 16 votes


**** (2026-09-23 21:47, 16 votes)
HARNESS_README.md section 9 shows a local CLI command:

 swegemma eval --tasks ... --submission-dir starter_kit/sample_submission --sandbox docker
 But the dataset has no swegemma, adk-submission, or adk-eval-core package, and no starter_kit folder. It only has docker/, sandbox/setup.py, and wheels/.

1. Will these packages be released (pip, GitHub, or a Kaggle dataset)?
2. If not, what is the recommended way to test a submission locally before submitting?
 Thanks!


**** (2026-09-24 10:45, 11 votes)
Hi @shimondanziger,

Here is a wheelhouse with the packages: [Gemma 4 Developer Agent Wheelhouse](https://www.kaggle.com/datasets/metric/gemma-4-developer-agent-wheelhouse/data).

I'll post a notebook later today illustrating how to run everything on Kaggle.


**** (2026-09-25 09:59, 0 votes)
Hi @ryanholbrook, thanks for the wheelhouse! Is the "how to run everything on Kaggle" notebook still coming? Specifically:

Test dependencies: the public wheelhouse lacks some packages the task tests import (e.g. typing-inspection, inline-snapshot, dirty-equals, pytest-httpbin), so gold patches for many FastAPI and Requests tasks can't pass locally. Will the sandbox wheels from the scoring data be published, or should we supply these ourselves?
Sandbox mode: Docker isn't available in Kaggle notebooks. Is --sandbox subprocess the intended way to run swegemma eval there?
Server settings: which vLLM flags does the scorer use (tool/reasoning parser, --default-chat-template-kwargs, kv-cache dtype)?
Thanks!


> **** (2026-09-25 18:42, 0 votes)
> I’m equally waiting. Let me know when you have it


> > **** (2026-09-25 18:42, 1 votes)
> > It's here: https://www.kaggle.com/code/ryanholbrook/getting-started-gemma-4-developer-agent


> > **** (2026-09-25 20:39, 0 votes)
> > @ryanholbrook 
> > We're validating the public tasks with `swegemma==0.2.7` using the official Docker verification path and the public competition `wheels/`.
> > 
> > We've hit two environment issues and wanted to confirm whether the private scorer differs:
> > 
> > 1. FastAPI tasks cannot import because the public wheel set includes Pydantic 2 but not `typing-inspection`. Several tasks also require packages such as `pytest-httpbin`, `inline-snapshot`, or `dirty-equals`, which aren't present in the public wheels.
> > 
> > 2. `_ensure_container_site_packages` can inject the repository's own released package (for example `requests` or `httpx`) into site-packages. In our checks, that package can shadow `/workspace`; for some Requests tasks the released wheel already contains the fix, so the test passes before applying the gold patch.
> > 
> > Does the private scoring wheel set contain the missing test dependencies? And in scoring, is the task repository's own released package also injected into site-packages, or is `/workspace` expected to take precedence?
> > 
> > We're asking because the task data and gold patches themselves validate cleanly, but these environment differences prevent the public verifier from providing a reliable gold-patch positive control.


> > **** (2026-09-26 11:49, 0 votes)
> > Hi @irfanparaniya,
> > 
> > Thanks for the report. I will look into it (likely on Monday). For now, I can verify at least that the evaluation metric correctly validates a gold-patch submission at 100%.


> > **** (2026-09-26 21:00, 2 votes)
> > @ryanholbrook — follow-up with a completed Kaggle reproduction of the public evaluation environment problems.
> > 
> > Thank you for confirming that the evaluation metric validates a gold-patch submission at 100%. We are trying to reproduce reliable reference-patch validation with the released tooling before using it to compare agents.
> > 
> > We ran a **private Kaggle CPU notebook**, using the **unchanged installation cell from your current Getting Started notebook**, with the competition data and official wheelhouse attached. The notebook used the released `verify_task` and subprocess sandbox, with no agent, model calls, inference, or competition submission. We ran fresh unpatched/reference controls for six public development tasks without changing patches, verification tests, pytest flags, or scoring expectations.
> > 
> > All 12 controls completed. **Only 2 of the 6 reference controls passed:**
> > 
> > | Public task | Reference result |
> > |---|---|
> > | `fastapi_14786` | Pass: 9 tests |
> > | `rich_3043` | Pass: 96 tests |
> > | `fastapi_14356` | Collection fails: missing `dirty_equals` |
> > | `fastapi_15745` | Collection fails: missing `inline_snapshot` |
> > | `requests_7309` | 6 failures; the failing traceback executes `/usr/local/lib/python3.12/dist-packages/requests/utils.py`, rather than the patched workspace source |
> > | `httpx_3672` | Collection fails because imported `httpx` has no `Stream`; the import probe resolves installed HTTPX rather than workspace source |
> > 
> > The returned snapshot hashes for all six tasks, task-data hash, all 124 task-wheel hashes, and the verification/setup source hashes match our local copies. The notebook environment has Python 3.12.13, pytest 8.4.2, Pydantic 2.12.3, Starlette 0.52.1, Requests 2.32.4 and HTTPX 0.28.1. This was the public CPU/subprocess path; we are **not claiming the private scorer or the GPU notebook has the same failures**.
> > 
> > These failures prevent trustworthy comparisons in the public development environment: a correct reference patch can fail because a package is missing or because the verifier executes an installed distribution instead of the patched repository.
> > 
> > Could you clarify:
> > 
> > 1. Which supported environment/setup reproduces the successful reference-patch validation you reported? Could its sandbox image digest and complete dependency lock or wheel manifest be provided?
> > 2. Should the released setup ensure workspace source (including `src/` layouts) takes precedence over installed repository packages, and supply the missing test dependencies?
> > 3. Does private scoring use a different sandbox backend or dependency setup from the released notebook flow?
> > 
> > We can provide the diagnostic script, package/import inventories and hashes. No reference patch text, test bodies, credentials or raw verification logs need to be posted.


> > **** (2026-09-27 11:12, 0 votes)
> > This may be a problem with the subprocess sandbox. I don't recall seeing these failures using the Docker sandbox. The private Docker sandbox uses the same base image but installs a different set of dependencies because the test issues come from a different set of repos.
> > 
> > I'll look into getting a more reliable setup going in the notebook environment.


> > **** (2026-09-28 19:16, 0 votes)
> > @ryanholbrook - Did you get a chance to look at this?


---

##  fastapi_15661 validation stops at ImportError during test collection
/competitions/gemma-4-developer-agent/discussion/745601 | by  | posted 2026-10-03 11:10 | last comment 2026-10-03 11:10 | 0 comments | 0 votes


**** (2026-10-03 11:10, 0 votes)
The agent submitted a patch for “Automate release preparation,” but
validation stopped while collecting tests/test_prepare_release.py:

ModuleNotFoundError: No module named 'scripts.prepare_release'

In another run, after that module existed, collection stopped with:

ImportError: cannot import name 'RELEASE_NOTES_HEADER' from
'scripts.prepare_release'

The task’s problem statement does not mention the module path or constant
name. These names appear in test_patch, which the agent does not see during
patch generation. Since pytest stops at collection, it never checks the
behavior of an implementation using a different interface.

Is this expected for the public training task, or could its validation be
adjusted to test the required behavior without depending on names absent
from the issue description? I’m trying to understand how a generic agent
should handle this case.


---

## Can TPU be used?
/competitions/gemma-4-developer-agent/discussion/745575 | by  | posted 2026-10-03 09:41 | last comment 2026-10-03 09:41 | 0 comments | 0 votes


**** (2026-10-03 09:41, 0 votes)
Can one use TPU end-to-end, including for submission in this competition?

Thanks.


---

## Googel Gemma and ARC AGI 2 have same problem of queue
/competitions/gemma-4-developer-agent/discussion/745543 | by  | posted 2026-10-03 07:28 | last comment 2026-10-03 07:28 | 0 comments | 0 votes


**** (2026-10-03 07:28, 0 votes)
all notebooks related to GPU L4 x4 are in long queue?


---

##  undeclared tool ends the task and discards the patch
/competitions/gemma-4-developer-agent/discussion/745028 | by  | posted 2026-10-01 20:37 | last comment 2026-10-03 01:43 | 4 comments | 3 votes


**** (2026-10-01 20:37, 3 votes)
Hi @ryanholbrook 

Currently when the model calls a tool that the submission does not declare, ADK's `_get_tool` raises `ValueError("Tool '...' not found ...")` (`google/adk/flows/llm_flows/functions.py`, google-adk 1.36.1). So the error propagates, the session ends through the `except Exception` path and the task scores 0 even if the agent had already made a correct edit.

The task message advertises tools regardless of what the submission declares: it always lists the `read_file` limits, and on tasks with graph data it recommends `search_similar_code`, `get_code_neighbors` and `get_code_subgraph` "for fast, targeted navigation". A submission that leaves those out, for example to save context, will still face the same issue since harness advertises tools to model and tested negative prompts won't stop it completely.

Also hallucinated tool name hits the same error, and quantized models invent tool names more often: one study I found measured AWQ 4-bit Gemma 4 31B inventing tool names about 2.5 times as often as full precision [arXiv 2607.27275](https://arxiv.org/abs/2607.27275). 

One possible fix I propose is to return the error to the model as a tool result, which ADK supports through an `on_tool_error_callback` in the harness's plugin list, so the agent can correct itself. 

Also possible to build the task message's tool sections from the tools the submission actually declares in agent.yaml.

Would you consider either for the scorer?


**** (2026-10-01 20:52, 1 votes)
Yes, let me look into it and I'll implement something.


**** (2026-10-03 01:43, 0 votes)
Hi @ryanholbrook, a quick follow-up: is a fix for this live on the scorer yet? The public wheelhouse is still the 09-30 build (adk_submission 0.2.12), so we can't tell from it. A data point in case it helps: on all 129 public tasks with the graph tools declared and the default task message, Gemma called `search_similar_code` 142 times in 91 tasks and 140 of those calls returned nothing (see also #745220), so the advertised section matters even for submissions that do declare the tools. Building the tool sections from the tools a submission declares, and returning an unknown-tool call to the model as a tool error instead of ending the task, would fix both. Thanks!


**** (2026-10-02 01:59, 0 votes)
A second trigger for the same failure class, seen in local runs of a skills-based submission with the official wheels (google-adk 1.36.1; swegemma 0.2.7 and adk-submission 0.2.12 from wheelhouse v28; same code in v25):

1. Gemma sometimes calls run_skill_script with file_path as a JSON list, e.g. {"skill_name": "...", "file_path": ["scripts/x.py"], "args": [...]}.
2. google/adk/tools/skill_toolset.py L838 (run_async) then calls file_path.startswith("scripts/") on the list and raises AttributeError: 'list' object has no attribute 'startswith'.
3. The exception is not turned into a tool error for the model. It escapes to swegemma/harness/agent_runner.py L799-801 (except Exception -> "Sandbox execution error: 'list' object has no attribute 'startswith'"), which ends the task.
4. agent_patch keeps its initial '' (L209). The submitted-patch and working-tree fallback at L758-776 only runs on a normal end, a time-out or the call limit (L741), so the task is scored with an empty patch, even if submit_patch already succeeded.

In our local runs this ended about 3% of task-runs (33 of 960), most at the first skill call, and more often at higher sampling temperature. All 33 occurrences happened on the first skill call of a run, or on the first call after a context compaction; with the model's own earlier correct call in context it never happened (0 of 214). A one-line coercion (a single-element list to its string), or returning a validation error to the model as for other bad arguments, would keep the task alive. Thanks!


---

## Question: training an adapter on Colab with the Kaggle-hosted checkpoint
/competitions/gemma-4-developer-agent/discussion/745269 | by  | posted 2026-10-02 20:58 | last comment 2026-10-02 20:58 | 0 comments | 0 votes


**** (2026-10-02 20:58, 0 votes)
Hi,
I would like to fine-tune a LoRA adapter for my entry, and i want to be sure i am following the rules before i  spend any time on it. Could you help with three quick questions?

1. Training outside Kaggle: Can we train the adapter on Google Colab? That would mean downloading the Gemma 4 31B model from Kaggle, training there, and then putting the finished adapter in our submission. Is that okay, or does the model have to stay on Kaggle?

2. Where the training data comes from: I read that training on Gemma 4 31B's own outputs is fine. I would run our my agent on issues from public GitHub projects, and keep only the attempts where the tests pass. Is that okay? i know the hidden tasks come from private repositories, so i just want to check that practising on public ones is allowed.

3. Sharing: Do i have to publish my  training data, code or adapter at some point? And if so, when?

Appreciate your response as the responses to the above questions will help us move forward.


---

## Supported authorization, skill-startup and patch-recovery hooks
/competitions/gemma-4-developer-agent/discussion/745267 | by  | posted 2026-10-02 20:48 | last comment 2026-10-02 20:48 | 0 comments | 0 votes


**** (2026-10-02 20:48, 0 votes)
Thanks for clarifying that custom Python tools should be packaged as sandbox
skill scripts. For adk-submission 0.2.12 and swegemma 0.2.7, is there a supported
submission configuration for any of the following?

1. A trusted approval check before each exact built-in tool or skill operation.
2. Isolated Python startup for skills before workspace modules can be imported.
3. Automatic patch recovery restricted to an explicitly selected candidate,
   including on timeout.

Please point to the supported configuration/hooks, or confirm which items
require an organizer runtime change. We want development and official scoring
to use the same supported interface.


---

## Missing python-multipart dependency in the FastAPI task environment
/competitions/gemma-4-developer-agent/discussion/745249 | by  | posted 2026-10-02 19:56 | last comment 2026-10-02 19:56 | 0 comments | 0 votes


**** (2026-10-02 19:56, 0 votes)
Is omitting python-multipart from the provided wheels intentional or an oversight? FastAPI task fastapi_14616 uses Form(), but the offline sandbox has no python-multipart wheel, so the reproduction fails.


---

## Task prompt: "Workspace Layout" omits the source package in 115/129 tasks, and "Code Intelligence Tools" tells the model to search by keyword (which always returns 0 results)
/competitions/gemma-4-developer-agent/discussion/745220 | by  | posted 2026-10-02 18:23 | last comment 2026-10-02 18:23 | 0 comments | 0 votes


**** (2026-10-02 18:23, 0 votes)
Hi @ryanholbrook ,

Two small issues in the task prompt that swegemma/harness/agent_runner.py builds for every task. Submissions can't change this text, and both points actively mislead the model.

1. "Workspace Layout" is cut off before the source code

The tree is built with:

cd /workspace && find . -maxdepth 3 -not -path "./.git/*" -not -name "*.pyc" -not -name "__pycache__" | sort | head -150

Because of the alphabetical sort plus head -150, ./.github, ./benchmarks, ./docs and ./docs_src fill the 150 lines before the package directory is reached. We rebuilt this listing for all 129 public tasks at their base commits: in 115/129 tasks (all 67 fastapi, all 48 rich) neither the file changed by the reference patch nor its folder appears in the listing. Example: in fastapi_15588 the listing is 149 lines of .github/ and docs_src/ tutorials, and fastapi/ and fastapi/sse.py never appear. In our traces the agent then opens docs_src/.../tutorial001.py files looking for the code.

Possible fixes: exclude .github/, docs/ and docs_src/ (and tests/) from the tree, list .py files of the package directories first, or raise the line limit.

2. "Code Intelligence Tools" describes search_similar_code as "by keyword"

The section, added whenever graph data exists, says:
search_similar_code(query): Find semantically similar functions/classes by keyword.

But embedding_utils.embed() is an exact dictionary lookup over the stored node keys, with no text encoder. Only an exact full dotted node name returns results. Tested on requests_6644 with the official functions:

query	results
requests.models.RequestEncodingMixin.path_url	5
RequestEncodingMixin.path_url	0
path_url	0
path separator leading /	0

get_code_neighbors behaves the same way (exact full name only), and its docstring's examples ('parse_request', edge_type='CALLS') return nothing, since all edges are stored as lowercase calls. In our runs the model follows the prompt and sends keyword queries, which all return 0 results (7 of 7 graph calls across 8 tasks in one run).

Possible fixes: describe the input as "the full dotted name of an existing node, e.g. pkg.module.Class.method", fix the docstring examples, and/or make the lookup accept short names or name suffixes.

Since this section is added regardless of which tools agent.yaml declares, it also feeds the undeclared-tool crash reported in #745028.

Thanks!


---

## Adapters / LoRA
/competitions/gemma-4-developer-agent/discussion/745154 | by  | posted 2026-10-02 14:36 | last comment 2026-10-02 14:36 | 0 comments | 0 votes


**** (2026-10-02 14:36, 0 votes)
Are adapters placed in the adapters/ directory definitely loaded and applied to the Gemma 4 checkpoint during official evaluation?
If yes, are there any restrictions on adapter architecture, rank, size, or training method?


---

## Failed patches and retry behavior
/competitions/gemma-4-developer-agent/discussion/745151 | by  | posted 2026-10-02 14:34 | last comment 2026-10-02 14:34 | 0 comments | 0 votes


**** (2026-10-02 14:34, 0 votes)
When an agent applies a patch and the validation/test fails, does the agent receive the actual test output, including the failing assertion, traceback, expected/actual values, and relevant error messages?
If so, is this output exactly the same information that is available during official evaluation?


---

## Several harness issues make results hard to trust: request for fixes and a status update
/competitions/gemma-4-developer-agent/discussion/744794 | by  | posted 2026-10-01 00:38 | last comment 2026-10-02 12:38 | 2 comments | 3 votes


**** (2026-10-01 00:38, 3 votes)
Several harness issues make results hard to trust: request for fixes and a status update

While testing locally with the official wheels, we ran into several problems that come from the scoring environment, not from the agent:

1. Compaction loses tool results. The ADK summary keeps only text parts, and Gemma-4 rarely writes text next to its tool calls. So after compaction the model loses its context, and it often repeats its last call until it times out.
2. LoRA on 4×L4. Enabling LoRA reduces the KV cache a lot, and long requests hang (#744331). This makes any adapter risky to submit.
3. Double-encoded tool output (#744272). This makes many edit_file calls fail with "old_string not found".
4. Thoughts dropped between tool calls (#744354), and thinking_budget / seed not sent (#744566).
5. No way to measure speed. We cannot measure the scorer's real speed, so choosing max_time_minutes is a guess. A wrong guess either cuts solvable tasks or risks the 12-hour limit.

What we are asking for:
- Include tool calls and short tool results in the compaction summary, or keep the last few tool results as they are.
- Fix the KV-cache drop with LoRA, or tell us it will stay as it is.
- Confirm which of the fixes above are live in the scorer now, and whether earlier submissions will be re-scored.
- Share the approximate time per model call on 4×L4, so we can set time limits safely.

Thanks for the work on the competition.


**** (2026-10-01 14:51, 1 votes)
- I'll look into the compaction issue.
- The KV-cache drop with LoRA should be addressed. Now vLLM will set its LoRA params dynamically based on what you actually submit. Submitting fewer adapters with lower rank (or no adapters) leaves more memory for KV-cache.
- KV-cache, double-encoded tool output, thoughts dropped, and thinking_budget / seed not sent are all fixed in the latest wheelhouse.
- Hard to estimate as it depends on the tool and how the model responds. You could experiment in a notebook on the training set to try to get estimates.


> **** (2026-10-02 12:38, 0 votes)
> Hi Ryan, 
> Is there a way to higher the compaction threshold ? like reduce max output. For now it's 14k on starter submission, I guess same setup on eval. 
> Thank you


---

## [Paper Track] Making a Legacy PHP Monolith Verifiable for a Gemma 4 Bug-Fixing Agent
/competitions/gemma-4-developer-agent/discussion/745027 | by  | posted 2026-10-01 20:35 | last comment 2026-10-01 20:35 | 0 comments | 1 votes


**** (2026-10-01 20:35, 1 votes)
---

## Feedback We Are Seeking From the Community

We would greatly appreciate feedback on the following methodological aspects:

1. **Hidden Browser Oracles vs. Unit Tests:** For legacy monoliths without unit suites, does Dockerized MariaDB snapshotting + Playwright E2E testing feel like a convincing paradigm for SWE benchmarking?
2. **Statistical Transparency:** At $N=33$, detecting a +6.8 pt lift requires $N \ge 95$ for $\alpha = 0.05$. We reported $p \approx 0.11$ honestly rather than claiming statistical significance. How can we best present this trade-off between costly E2E verification depth and statistical sample size?
3. **Reward Hacking Guards:** Has anyone else observed 30%+ verifier gaming when bootstrapping agents with model-generated tests? What programmatic guards do you recommend?

*All code, docker environments, traces, and datasets are open-source under Apache-2.0.*


---

## old_string issue
/competitions/gemma-4-developer-agent/discussion/745003 | by  | posted 2026-10-01 19:21 | last comment 2026-10-01 19:50 | 1 comments | 0 votes


**** (2026-10-01 19:50, 0 votes)
it's an issue with prefix numbers, whitespaces and indentation are already handled automatically

prompt works for this, something along the lines like - "strip any line-number prefixes" (there could be other optimal ways)

there are other causes as well, like - the model is hallucinating if the context grows big enough (a fix can be like - a fresh read before every edit), will need testing for each case


**** (2026-10-01 19:21, 0 votes)
hello everyone whenever my agent tries to use edit_file i get the: {'status': 'error', 'error_type': 'FileEditError', 'error_message': "Failed to replace: old_string not found.

Its the only tool that my agent fails to use, all the others seem to work fine except for that one. Is there an issue with the harness or the tools that i dont know about?


---

## Test-file reset before test_patch is a no-op (git checkout aborts on missing pathspecs)
/competitions/gemma-4-developer-agent/discussion/744825 | by  | posted 2026-10-01 04:44 | last comment 2026-10-01 18:06 | 1 comments | 2 votes


**** (2026-10-01 18:06, 2 votes)
Addressing now.


**** (2026-10-01 04:44, 2 votes)
Hello @ryanholbrook 

**Summary**
`verify_task` should reset agent-modified test/config files before applying `test_patch` (HARNESS_README, "Anti-Tampering Test & Config Reset"). In practice nothing gets reset.

**Cause**
swegemma 0.2.7 (wheelhouse v28), `harness/verification.py` ~L389-412:
```
git checkout HEAD -- <files_to_reset> 2>/dev/null || true
```
- `files_to_reset` always includes `sitecustomize.py`, `usercustomize.py` and `_swegemma_stubs.py`. These live in site-packages, not in `/workspace` HEAD.
- `git checkout` aborts the whole command if any pathspec doesn't match, and the error is swallowed.
- `git clean -f` still runs, so only added files are removed. Edits to existing test files survive.

**Effect**
If the agent edits an existing test file, `test_patch` fails to apply. The task is then scored as failed even when the source fix is correct:
```
Failed to apply test_patch: ... Reversed (or previously applied) patch detected
```
Seen locally on public tasks, e.g. fastapi_14077 and fastapi_14492. Re-verifying the same patches with the test-file hunks stripped makes them resolve. The Docker path runs the same code.

**Repro**
```
git init -q r && cd r && echo a > t.py && git add t.py && git commit -qm init
echo b > t.py
git checkout HEAD -- t.py sitecustomize.py; echo $?   # error: pathspec 'sitecustomize.py' did not match ...; 1
cat t.py                                              # b (not restored)
```

**Suggested fix**
Check out only the paths that exist in HEAD:
```
cd /workspace && git ls-tree -r -z --name-only HEAD -- <files_to_reset> | xargs -0 -r git checkout HEAD --
```

Thanks!


---

## Test on a Small Public Sample and Share Full Logs
/competitions/gemma-4-developer-agent/discussion/744924 | by  | posted 2026-10-01 13:19 | last comment 2026-10-01 17:14 | 3 comments | 2 votes


**** (2026-10-01 13:19, 2 votes)
My first submission today failed. Kaggle showed only:  **“Notebook Threw Exception.”** 
I had no clue what went wrong or how to fix it.
I understand why Kaggle limits logs from private test data: detailed logs could reveal information about that data. 

Could Kaggle first run each submission on **a small sample of public data and show the full log?**
If a submission fails on private data, Kaggle could still show only a general error message. This would help me tell whether the problem is in my notebook or in Kaggle’s system, while keeping the private data safe.


**** (2026-10-01 13:42, 1 votes)
same thing happened with me. maybe wait for them to provide more information


**** (2026-10-01 13:27, 1 votes)
yes, same happened with me. They should provide the exact error logs


**** (2026-10-01 17:14, 0 votes)
Also it doesn't make sense to loose daily submission limit when the problem happens before the task actually started.


---

## "'>' not supported between instances of 'int' and 'str'". Is this same for everyone?
/competitions/gemma-4-developer-agent/discussion/744678 | by  | posted 2026-09-30 18:50 | last comment 2026-10-01 17:02 | 4 comments | 2 votes


**** (2026-09-30 18:50, 2 votes)
`read_file` tool call with line ranges always fail.

Is anyone else is facing this ?


**** (2026-09-30 20:33, 0 votes)
Fix incoming.


> **** (2026-10-01 15:18, 0 votes)
> @ryanholbrook is this because of adk or vllm?


> **** (2026-10-01 15:22, 0 votes)
> @ryanholbrook I have setup this whole repo locally, sicen the repo deps are changing can u recommend how to patch these issues in my local after the fix is done?


> > **** (2026-10-01 17:02, 0 votes)
> > The fix should be in the current wheelhouse. I recommend just updating the packages.


---

## gpu outage causing submission failure 
/competitions/gemma-4-developer-agent/discussion/744965 | by  | posted 2026-10-01 16:42 | last comment 2026-10-01 16:42 | 0 comments | 2 votes


**** (2026-10-01 16:42, 2 votes)
so are we getting a reset for our troubles or are we just sol?


---

## Public code sharing via a Notebook or Dataset linked from a paper-track Writeup
/competitions/gemma-4-developer-agent/discussion/744941 | by  | posted 2026-10-01 14:38 | last comment 2026-10-01 14:38 | 0 comments | 0 votes


**** (2026-10-01 14:38, 0 votes)
The rules say publicly shared Competition Code must be shared on this competition's forum or notebooks. If a team's paper-track Writeup (public after 12 November) links agent analysis code, does it satisfy the rule to publish that code as a public Kaggle Notebook attached to this competition and post the link here the same day? Is a public Kaggle Dataset also acceptable?


---

## Submission 56722466 (2026-10-01 00:00 UTC) also ended with "Notebook Threw Exception" and no score. 
/competitions/gemma-4-developer-agent/discussion/744813 | by  | posted 2026-10-01 02:48 | last comment 2026-10-01 12:57 | 1 comments | 3 votes


**** (2026-10-01 02:48, 3 votes)
Submission 56722466 (2026-10-01 00:00 UTC) also ended with "Notebook Threw Exception" and no score. It's an agent with no LoRA adapters that passed the official compiler and ran cleanly in a 4×L4 lab with the official harness, on the wheelhouse before yesterday's update. Could you check what raised and, if it was on the scorer side, rerun it or restore the allowance?


**** (2026-10-01 12:57, 0 votes)
I have just made my first submission and it failed with the same error, your note restored my confidence!


---

## Same submission failed twice with "Notebook Threw Exception" within minutes (Sep 30 and Oct 1), no adapters
/competitions/gemma-4-developer-agent/discussion/744861 | by  | posted 2026-10-01 08:10 | last comment 2026-10-01 12:44 | 1 comments | 2 votes


**** (2026-10-01 08:10, 2 votes)
Hi @ryanholbrook,

Our submission failed twice with "Notebook Threw Exception", both times within a few minutes, well before vLLM could have finished loading. The API reports both as COMPLETE with no score:

- 2026-09-30 20:41 UTC (ID: <id 1>): failed about 3 minutes in.
- 2026-10-01 07:42 UTC (ID: <id 2>): the exact same zip from the same notebook version, failed about 1 minute in.

Both come from notebook darovalos/g4-agent-submit, version 2.

What we checked on our side:
- The notebook only decodes an embedded submission.zip, verifies its sha256 and writes /kaggle/working/submission.zip. It runs without accelerator or internet. Its code and kernel metadata are identical to version 1, which scored normally on Sep 28.
- The bundle differs from that scored one only in prompt text and YAML comments. It ships no adapters, and eval_config.yaml sets only the four supported keys.
- The same zip compiles with adk-submission and ran 40 public tasks end to end with swegemma's Evaluator in a 4x L4 notebook on Sep 30.

The first failure matches the timing of the scorer changes you mentioned that day (wheelhouse v25, LoRA parameters sized per submission, the reasoning_content fix). Since our bundle has no adapters, could the LoRA sizing produce an invalid vLLM config when there are none? Only a guess.

Could you check the logs and, if the cause is on the scoring side, rerun them? Is a CPU-only submission notebook like ours still supported? And is the change that scores unfinished tasks as 0 at the 12 h limit already live?

Thanks!


**** (2026-10-01 12:44, 0 votes)
Same here, is there any way to find out what is behine "Notebook Threw Exception"?


---

## Local Models (E4B/E2B) possible? Separate LB likely?
/competitions/gemma-4-developer-agent/discussion/743531 | by  | posted 2026-09-26 06:45 | last comment 2026-10-01 09:04 | 5 comments | 6 votes


**** (2026-09-26 06:45, 6 votes)
Hello, since the 31B model is too chonky to likely run on most local machines out there, and since there does seem to be a big interest in the smaller more efficient models...

It might be possible to have 2 LBs, although idk how prize money split will work lmao


**** (2026-09-27 07:21, 2 votes)
lmao all the losers from the shitty small seed funded AI labs downvoting this... tell me... what justification do you have? A good coding agent that runs locally on almost every laptop is literally the pinnacle of local AI. Why not have a fair competition with actual tangible benefits for the environment and independent developers instead of focusing on a model that basically only runs on a server or needs a minimum 5k euro investment to run locally?


**** (2026-09-26 08:20, 2 votes)
I think having a separate leaderboard for E2B/E4B would be a great idea.

The 31B model is quite demanding for many participants, especially those working with local hardware. A smaller-model track could make the competition more accessible and encourage more developers to experiment with local/edge deployment.

It would also be interesting to compare the trade-off between model size, agent performance, inference speed, and hardware requirements.

Hopefully the organizers can consider a separate E2B/E4B leaderboard if the competition rules allow it.


**** (2026-10-01 06:57, 1 votes)
Not ideal, but since many seem to struggle locally (as did I), you can use it via HuggingFace Inference, I have been able to run a lot of tests with the exact model, less than 10$.


> **** (2026-10-01 09:04, 0 votes)
> My original comment was not about GPU cost (indeed Kaggle gives a decent quota there) but more about the utility of the coding agent that is the final outcome of the competition.


**** (2026-09-27 08:47, 0 votes)
Yeah ... I can't run it in my PC (8GB VRAM only) so I can't check my model first ...


---

## Does patch validation import the edited src/ package for Requests tasks?
/competitions/gemma-4-developer-agent/discussion/744889 | by  | posted 2026-10-01 09:03 | last comment 2026-10-01 09:03 | 0 comments | 0 votes


**** (2026-10-01 09:03, 0 votes)
I am trying to make sure local validation reflects the code that the agent actually edits. In the published swegemma 0.2.7 wheel, install_editable_package() returns early for SubprocessManager/SubprocessSandbox. The subprocess environment sets PYTHONPATH to /workspace, while Requests task snapshots place the package under /workspace/src/requests. The official getting-started notebook uses sandbox='subprocess' for its sample evaluation.

On the public task requests_7315, I ran the unmodified verify_task test and a separate diagnostic test process in the same sandbox. Both failed the same assertion. The diagnostic process imported the system Requests package rather than /workspace/src/requests; with PYTHONPATH=src, a minimal probe imported the edited workspace code. This observation is from a local Kaggle CPU evaluation, not a claim about the hidden final scoring environment.

Could the organizers clarify: (1) which sandbox/backend final patch validation uses; (2) how src-layout packages are made importable from the patched workspace; and (3) whether participants should take any supported action, or whether final scoring handles this? I want to avoid optimizing an agent against a local validation path that may not match final scoring.


---

## Submission 56740049: Notebook Threw Exception, no score, prompt-text-only change
/competitions/gemma-4-developer-agent/discussion/744805 | by  | posted 2026-10-01 01:57 | last comment 2026-10-01 01:57 | 0 comments | 9 votes


**** (2026-10-01 01:57, 9 votes)
Hi @ryanholbrook, our submission 56740049 (2026-10-01 01:04 UTC) ended with "Notebook Threw Exception" and no score. The only change from our previous submission (which scored normally on 29/30 Sep) was prompt text in agent.yaml's included system prompt -- no config, model, adapter or tool changes. Given the reports in this thread and others today (e.g. the read_file line-range type error acknowledged with a fix incoming), this looks like it may be platform-side rather than caused by our submission. If so, could it be rerun, or the daily allowance restored? Happy to share more detail if useful. Thanks!


---

## Submission 56739788: Notebook Threw Exception after successful official-harness smoke
/competitions/gemma-4-developer-agent/discussion/744802 | by  | posted 2026-10-01 01:35 | last comment 2026-10-01 01:35 | 0 comments | 4 votes


**** (2026-10-01 01:35, 4 votes)
Submission 56739788 (2026-10-01 00:48:59 UTC) failed with "Notebook Threw Exception" and no score. The API reports COMPLETE but includes the generic notebook error_description. Could the team inspect the underlying scorer exception?

The submitted ZIP has agent.yaml at the root, uses gemma-4-31b-it-qat-w4a16-ct and the official sample LoRA adapters, and passed the official compiler plus a two-task smoke in an offline Kaggle notebook on 4 L4 GPUs. One task passed verification and one did not; both finished within 300 seconds. Downloading the uploaded ZIP from the submission page confirmed it is byte-identical to the tested package.

The failed submission used today's only allowance. If the failure is platform-side, could it be rerun or the allowance restored? I have not established the root cause and am not assuming this is an infrastructure bug.


---

## How are you running local evaluations?
/competitions/gemma-4-developer-agent/discussion/744611 | by  | posted 2026-09-30 14:27 | last comment 2026-10-01 01:13 | 1 comments | 3 votes


**** (2026-09-30 14:27, 3 votes)
Hi everyone,

I’m curious how others are evaluating their agents before submitting.

My current workflow is to run the agent in a Kaggle Notebook with 4× L4 GPUs, then grade the generated patches locally using the official verifier in Docker. I use 4× L4 for generation to keep the hardware close to the competition setup, since execution speed affects what the agent can do before a timeout.

For now, my evaluation set is limited to 38 tasks from the Rich repository where the none/gold controls behave as expected: no patch is marked unresolved, while the reference patch is marked resolved. I’ve had trouble getting reliable reference-patch validation for other repositories, including FastAPI, in my local grading setup.

I’ve read the related discussions:
- [Local evaluation setup and differences between the public and private environments](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742882)
- [Gold-patch failures and missing dependencies in the public environment](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743973)
- [Docker vs. Kaggle Notebook results, and the hosts’ confirmation that hidden tasks pass with gold patches](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/744370)

Rather than repeating those bug reports, I’d like to hear what practical evaluation workflow people are using in the meantime:

- What hardware and sandbox setup are you using for generation and grading?
- If you use different GPUs, how do you account for execution-speed differences when setting timeouts?
- Are you evaluating on a subset of tasks that pass none/gold checks, or have you found a reliable setup covering more repositories?

I’d appreciate hearing what has worked for you. Thanks!


**** (2026-10-01 01:13, 1 votes)
I use llama.cpp instead vllm, I use two setups, 2x3060 and 4x3090. In most cases my 4x3090 is busy with my local agent that's the reason to use 2x3060 for Kaggle models.


---

## Get an error trying to submit a zip
/competitions/gemma-4-developer-agent/discussion/744153 | by  | posted 2026-09-28 20:05 | last comment 2026-10-01 00:53 | 1 comments | 3 votes


**** (2026-09-28 20:05, 3 votes)
I keep getting this error when I try to submit a zip. Is it somehow related to [this issue]( https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743683)?

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F8213790%2Fdc0aeea3d8b2d4b8a9e15f78f470ea6d%2FScreenshot%202026-09-28%20at%2023.02.55.png?generation=1790625951140196&alt=media)


**** (2026-10-01 00:53, 0 votes)
very first submission. and just ran into the same problem.


---

## ONLY ONE search_similar_code call can blow your context up
/competitions/gemma-4-developer-agent/discussion/744577 | by  | posted 2026-09-30 11:02 | last comment 2026-09-30 19:06 | 2 comments | 1 votes


**** (2026-09-30 11:02, 1 votes)
While going through our local runs (official swegemma 0.2.7 + vLLM 0.19.1) we found that a single `search_similar_code` call can end a task on the spot. Sharing it here in case it saves someone a few lost tasks, plus a small question for the organizers at the end.

**What happens**

`run_command` and `read_file` cut their output at 5,000 characters, but `search_similar_code` returns the full source of each of its k (default 10) nodes with no limit. On FastAPI a few nodes are huge because the parameter docs live in the code: `fastapi.applications.FastAPI` is about 130,000 characters and `fastapi.routing.APIRouter` about 110,000. If one of them lands in the top 10, the tool response alone is bigger than the 32,768-token context, and the next model request fails with `ContextWindowExceededError`, which ends the task.

Across 246 `search_similar_code` calls in our runs:

| response size | calls |
|---|---|
| > 5,000 chars | 107 |
| > 20,000 chars | 21 |
| > 50,000 chars | 11 |
| > 100,000 chars | 6 |

All 6 calls above 100k characters ended their task with `ContextWindowExceededError` (queries `APIRoute`, `FastAPI`, `APIRouter`, and `Body` three times). Note that the query does not have to name the big class: `Body` returned `APIRouter` first.

**If you use the graph tools**

- Query specific function or method names rather than broad class names (`FastAPI`, `APIRouter`, `Body`, ...).
- `k` only limits the number of results, not the size of one node, so a smaller `k` does not fully protect you.
- `get_code_neighbors` returns node names only, without code (in our few calls the responses stayed under 400 characters), so it looks like a safer first step.

**Question for the organizers**

Would it fit the design to cap the `code` field per result (say the first 1,500-2,000 characters, with a note that it was cut) or to apply the same `max_stdout_chars` limit as the other tools? We don't know whether the hidden repositories contain classes of this size, so it may matter more or less there. @ryanholbrook 

Thanks for the tools - the graph neighbours in particular have been handy.


**** (2026-09-30 18:33, 0 votes)
Thanks for the heads up. I will limit to `max_stdout_chars` like other tools. Glad you're liking the graph tools!


> **** (2026-09-30 19:06, 0 votes)
> How we can limit in our local setup ?


---

## Suggestions on infra for post training, SFT, and RL?
/competitions/gemma-4-developer-agent/discussion/743186 | by  | posted 2026-09-25 06:08 | last comment 2026-09-30 19:03 | 2 comments | 4 votes


**** (2026-09-25 06:08, 4 votes)
How exactly are we supposed to post train? Do we have to do it on our own GPUs (of which I have 64 gb of VRAM, which can't load the full gemma-4-31B-it-qat-q4_0-unquantized model for post-training, which is ~63 gigs of VRAM just to sit on disk), or can we use Kaggle notebooks for it. Furthermore, if we aren't supposed to use Kaggle notebooks for training, can we use QLoRA feasibly without severe degradation, and if we are, are 4x L4's considered sufficient for post training purposes or could more/higher quality compute be provided later on?


**** (2026-09-30 19:03, 0 votes)
Usually I would say Google Colab, and Kaggle. 

Guide from unsloth : https://unsloth.ai/docs/models/gemma-4/qat 

You can also test it out without training, helping you optimize quite a bit, on HuggingFace inference endpoints, there's several hosts for this model.


---

## How well do your CV and LB correlate?
/competitions/gemma-4-developer-agent/discussion/744319 | by  | posted 2026-09-29 11:32 | last comment 2026-09-30 14:38 | 4 comments | 11 votes


**** (2026-09-29 11:32, 11 votes)
I plotted my CV against the public LB.

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F5927283%2Fc28f1df91e7bc0d065076a6698da889b%2Fcv_lb_public.png?generation=1790681365420102&alt=media)

| CV | LB |
|---|---|
| 0.18 | 0.05 |
| 0.19 | 0.06 |
| 0.23 | 0.12 |
| 0.24 | 0.10 |

Higher CV does not seem to translate into a higher LB. How well do your CV and LB correlate?


**** (2026-09-30 14:38, 2 votes)
I'm seeing a similar mismatch: in my small set of experiments, the configuration with the highest CV score actually had the lowest public LB score.

**Dataset**
- 38 tasks from the Rich repository (not the full public dataset)
- Only tasks where the none/gold controls behave as expected
- Limited to Rich for now, since I couldn't get reliable controls for other repositories in my local grading environment

**Setup**
- Generation: Kaggle Notebook with 4× L4 GPUs
- Grading: official verifier in Docker (ARM64), run locally

**Scores**

| CV | Public LB |
|---|---|
| 0.211 | 0.10 |
| 0.237 | 0.08 |
| 0.316 | 0.03 |
| 0.289 | 0.05 |


**** (2026-09-29 12:22, 2 votes)
Congrats to your good correlation!
Which data did you use to calculate CV?


> **** (2026-09-29 12:26, 2 votes)
> Thanks! Just the official dataset.


**** (2026-09-30 02:34, 1 votes)
My agent reached ~0.2 in the local validation, but when it came to LB, it dropped to < 0.12. Haven't made any progress for a week.


---

## is the harness compatible with TPU build ?
/competitions/gemma-4-developer-agent/discussion/744589 | by  | posted 2026-09-30 12:25 | last comment 2026-09-30 12:25 | 0 comments | 1 votes


**** (2026-09-30 12:25, 1 votes)
since the free tier 2*t4 GPUs are not good memory and architecture wise , I was thinking to use TPUs to run the harness , does the harness support tpu jax ?


---

## We can submit skills correct ?
/competitions/gemma-4-developer-agent/discussion/744133 | by  | posted 2026-09-28 18:58 | last comment 2026-09-30 07:53 | 3 comments | 0 votes


**** (2026-09-28 19:19, 1 votes)
Yes. See www.kaggle.com/competitions/gemma-4-developer-agent/overview/evaluation

Each skill is a folder under skills/ containing a SKILL.md.


**** (2026-09-30 01:58, 0 votes)
whats stopping someone from putting up a whole submission bloated with skills


> **** (2026-09-30 07:53, 2 votes)
> Nothing stops it: the harness allows up to 1,000 skills, 50 MiB each, within the 3 GiB limit. That said, the ADK puts every skill's name and description into each model call, so a large library will eat through the 32k context window fast and trigger compaction sooner.


**** (2026-09-28 18:58, 0 votes)
can anyone answer this question?


---

## Official images per task?
/competitions/gemma-4-developer-agent/discussion/744355 | by  | posted 2026-09-29 14:13 | last comment 2026-09-29 14:13 | 0 comments | 2 votes


**** (2026-09-29 14:13, 2 votes)
I am writing to see if the hosts of this competition would like to release official public images per tasks. This might be easier to use with sandboxes.


---

## Does one scoring run cover both hidden partitions (~240 tasks) in the 12-hour window?
/competitions/gemma-4-developer-agent/discussion/744258 | by  | posted 2026-09-29 05:46 | last comment 2026-09-29 14:04 | 1 comments | 0 votes


**** (2026-09-29 14:04, 2 votes)
There are ~120 tasks in the test set, or about 60 in each of the public and private splits. They are scored during the same 12-hour run.


**** (2026-09-29 05:46, 0 votes)
Hi @elanlearns,
I have following query related to scoring. 
Does one scoring run cover both hidden partitions (~240 tasks) within the 12-hour window, or is each partition a separate run? It decides the safe per-task time limit: about 4.5 minutes for 120 tasks, 2 minutes for 240.


---

## Is this a python only competition for bug fixes and feature requests?
/competitions/gemma-4-developer-agent/discussion/744020 | by  | posted 2026-09-28 09:39 | last comment 2026-09-29 09:05 | 2 comments | 1 votes


**** (2026-09-28 09:39, 1 votes)
As per the data tab - "This competition evaluates AI software engineering agents on their ability to solve real-world Python bug fixes and feature requests."


**** (2026-09-28 10:23, 0 votes)
seems like. also hello. :)


> **** (2026-09-29 09:05, 0 votes)
> Oh hey!! :) Good to see you here :)


---

## Request to Organizers to provide GPU access to fine-tune model
/competitions/gemma-4-developer-agent/discussion/744256 | by  | posted 2026-09-29 05:45 | last comment 2026-09-29 08:12 | 2 comments | 2 votes


**** (2026-09-29 05:45, 2 votes)
Since the accepted model is relatively large(31B Parameters), The organizers are requested to provide limited GPU access, so that everyone can run the model and participate.


**** (2026-09-29 06:37, 2 votes)
They are providing GPU access for us already, You can access it in kaggle notebook, 30 hours/week is the quota . You can train or test there.4 x GPU L4 are provided


**** (2026-09-29 08:12, -2 votes)
You should ask for a RTX Pro 6000 instead. It’s way quicker than the L4 x 4 setup we have now.


---

## Embeddings for search_similar_code appear near-collapsed
/competitions/gemma-4-developer-agent/discussion/744040 | by  | posted 2026-09-28 11:39 | last comment 2026-09-29 03:24 | 1 comments | 2 votes


**** (2026-09-28 11:39, 2 votes)
Hi @ryanholbrook , One data issue: in the current embeddings, random node pairs have mean cosine similarity 0.78 (fastapi) to 0.90 (rich), and 8–19% of random pairs are ≥ 0.99. Querying the exact name of a task's gold function returns unrelated test functions, all at similarity 1.0. Across 129 training tasks, the gold file appears in the top 10 for 35 tasks, versus 67 for a plain grep on the issue's identifiers.

1. Is this expected (e.g., a model that embeds mostly boilerplate), or could the embedding step be regenerated?
2. Does the hidden test set use the same embeddings pipeline?
3. **search_similar_code** only accepts an existing node name. Is a text query encoder planned, or is node-name lookup the intended use?


**** (2026-09-29 03:24, 0 votes)
Independent check on our side, consistent with yours: on fastapi_14246 the node embeddings give a mean random-pair cosine of 0.78 (7% of pairs >= 0.99; 2,635 distinct vectors among 3,619 nodes), and on rich_3905 0.90 (11% >= 0.99).

A related coverage issue in the graphs themselves (one commit per repo checked): every edge has type `calls`, and no `async def` function appears as a node: 0 of 57 async functions in fastapi's package (e.g. routing.run_endpoint_function, routing.serialize_response, dependencies.utils.solve_dependencies) and 0 of 100 in httpx's async client (src/ahttpx). rich and requests have no async code, so they are unaffected.

@ryanholbrook: does the hidden test set use the same graph/embedding pipeline, and could async functions (and ideally import/containment edges) be included? Also, which embedding model produced the 256-d vectors?


---

## Gold patches fail offline for most FastAPI and requests tasks (missing test dependencies in the grading environment?
/competitions/gemma-4-developer-agent/discussion/743973 | by  | posted 2026-09-28 04:02 | last comment 2026-09-29 02:58 | 3 comments | 7 votes


**** (2026-09-28 04:02, 7 votes)
Evidence notebook for a forum report to the organisers. Everything here is produced by the organisers' own code from the official wheelhouse (swegemma 0.2.7, adk_submission 0.2.11) with the competition's wheels/ directory and the swebench-sandbox image, network off. No model is involved: each task is graded with its reference (gold) patch and with no patch.

Kindly adress the questions in the notebook


**** (2026-09-28 08:41, 2 votes)
Same. I pulled everything directly from the data tab. 

Here's everything I found, sorted:

These are definite dataset bugs, and gold patch cannot pass on py3.13

8× requests tasks — `6589, 6592, 6629, 6757, 7328, 7433, 7502, 7505`
 - Python 3.13 enables `VERIFY_X509_STRICT` by default; pytest-httpbin's bundled cert has no Authority Key Identifier → every https test fails with `SSLCertVerificationError: Missing Authority Key Identifier`. Since resolution requires the whole touched test file to exit 0, these are unresolvable for everyone. (Verified: gold patches produce 315+ passed but the same 7–10 inherent SSL/timeout failures.)

3× version-gated required tests — `fastapi_14186`, `fastapi_15745`, `rich_3486`
 - The `test_patch` adds tests decorated `@needs_py_lt_314` (which is `skipif(sys.version_info > (3,13))` → **skips on every 3.13.x**, including 3.13.0, because `(3,13,0) > (3,13)` tuple-compares True) and `skip if(minor >= 11)`. On the 3.13 runtime they can never run — only skip. If the scorer counts extracted test names as required-and must-pass, these are unresolvable; if it precomputed FAIL_TO_PASS on the same env, they're excluded and just noise.

1× Python-behavior drift — `rich_3472`
 - `test_attrs_broken_310` expects `'Foo' object has no attribute 'bar'`; on 3.13 CPython emits the full `__qualname__` (`'tests.test_pretty.<locals>.Foo'`). No patch can fix a Python-version difference in the error string. Dead task.


**** (2026-09-29 02:58, 0 votes)
I think there are two problems:

1. Missing wheels (pytest collection fails for every fastapi task, gold patch included)

With swegemma 0.2.7, the published `sandbox/wheels/` and the image from `docker/Dockerfile.sandbox`, every fastapi task exits pytest with code 2 at collection:

```
E   ModuleNotFoundError: No module named 'typing_inspection'
```

Cause: the wheelhouse ships `pydantic-2.13.4`, whose METADATA declares `Requires-Dist: typing-inspection>=0.4.2` (every pydantic >= 2.11 needs it), but no `typing_inspection` wheel is included. The offline install in `container_setup.py` silently skips it, so `import fastapi -> import pydantic` fails regardless of the patch. Also absent from the wheelhouse but imported directly by the tests: `inline-snapshot` (+ `asttokens`, `executing`) – needed by 22 of the 67 public fastapi tasks; `dirty-equals` – 9 tasks; `ujson`/`orjson` – 2; `python-multipart` – 1.

2. Starlette version selection

After adding those wheels locally, a gold-patch control over the 67 non-dev public fastapi tasks resolves only 13/67. The wheelhouse contains 60 starlette versions (0.19.0 … 0.52.1, 1.3.1, 1.6.0), but `container_setup._deduplicate_wheels` keeps the *highest* version per package and `_ensure_container_site_packages` unpacks that set into site-packages before `sandbox/setup.py` runs; `setup.py` is called with `--fast-path`, which installs nothing (its slow path also strips version constraints). So every fastapi commit runs against **starlette 1.6.0**. Starlette 1.0 removed `Router(on_startup=...)`, hence 48 tasks fail with:

```
TypeError: Router.__init__() got an unexpected keyword argument 'on_startup'
```

Only commits that happen to be compatible with starlette 1.x can pass. As such, 54/67 public fastapi tasks are automatically failed with the shipped harness, gold patch or not.


**** (2026-09-28 06:06, 0 votes)
I'm also facing the same, I've reproduced it using the getting started kernel. I've patched the Evaluator to bypass the model call and return the ground truth directly.
https://www.kaggle.com/code/bharat0/eval-errors-gemma-4-developer-agent


---

## Clarifications on 12h overrun, ParallelAgent concurrency, LoRA loading, and self-generated training data
/competitions/gemma-4-developer-agent/discussion/743964 | by  | posted 2026-09-28 01:37 | last comment 2026-09-29 02:46 | 3 comments | 1 votes


**** (2026-09-28 10:32, 1 votes)
- 12h overrun: Not yet. Budget per task using `eval_config.yaml`.
- Parallel: I we don't support parallel calls.
- LoRA: I applied a fix for LoRA loading yesterday. You can see the limits on rank and size in the getting started notebook and also in the `HARNESS_README.md`. There's also a total submission limit of 3GB.
- Training data: Training on gemma-4-31b itself is fine. We'll try to have an answer for outputs from other models soon.


> **** (2026-09-28 23:39, 0 votes)
> Hi @ryanholbrook , thanks for the earlier answers. Two follow-up questions about the agent schema:
> 
> Callbacks: SandboxedLlmAgentConfig accepts before_model_callbacks, after_model_callbacks, before_tool_callbacks and after_tool_callbacks (resolved by name from CallbackRegistry), but the registry seems to be empty in adk-submission 0.2.11. Are any callbacks registered in the scoring environment, or planned? For example, a pre-approved callback that stops an agent after N identical consecutive tool calls, or one that restarts the agent with a fresh context. In our traces, the most common failure of gemma-4-31b is repeating the same tool call many times until the time budget runs out.
> Forcing tool calls: a model reply without a function call ends an LlmAgent. Is there a supported way to require a tool call on every turn (like tool_config / function-calling mode ANY in ADK), or is that intentionally not exposed?


**** (2026-09-28 01:37, 1 votes)
Hi @ryanholbrook , a few clarifications that affect how we budget submissions:

12h overrun: Has the fix landed? If a run hits 12h, will the already-finished tasks be scored (the rest counted as failed), or does the whole submission still error?
Parallel sub-agents: If a submission uses a ParallelAgent (e.g., 3 attempts per task), are those LLM calls actually served concurrently by vLLM on the 4×L4 scoring machine? Is there any limit on concurrent requests that could trigger "Notebook Exceeded Allowed Compute"?
LoRA: Is there an ETA for adapter loading on the scorer, and any limits on rank, target modules or adapter size?
Training data: Is it allowed to fine-tune a LoRA on trajectories generated by gemma-4-31b itself (self-generated and filtered by our own tests)? Is there any update on using outputs from other open-weight models?


**** (2026-09-29 02:46, 0 votes)
I'm very curious whether the Notebook Timeout is caused by exceeding the upper limit of the inference budget. In other words, could this potentially be resolved by reducing the inference budget for each individual task?


---

## L4 ×4 session queued for 13 hours—still hasn’t started
/competitions/gemma-4-developer-agent/discussion/744054 | by  | posted 2026-09-28 13:02 | last comment 2026-09-28 21:48 | 9 comments | 5 votes


**** (2026-09-28 13:02, 5 votes)
My L4 ×4 session has been queued for over 13 hours and still hasn’t started. This is extremely frustrating and makes me wonder whether it’s realistic to participate in this competition using only the resources Kaggle provides.


**** (2026-09-28 13:08, 4 votes)
I'm pretty sure that's the issue will everyone. And going on at this rate for 2 months sounds pretty unrealistic tbh, its very frustrating. Hopefully they do something about this


**** (2026-09-28 13:11, -2 votes)
No it isn't realistiic to participate in kaggle competitions using only kaggle resources. I would recommend renting RTX-PRO-6000-MAX-Q from [vast.ai](https://vast.ai/pricing/gpu/RTX-PRO-6000-MAX-Q). I do this for this competition and rent it for two months for nonstop training and experimenting, its only about 1000$ usd a month for nonstop training. So if ur competative i would invest at least 2k usd.


> **** (2026-09-28 14:14, 0 votes)
> I have 4x3090 locally that I use for training / evaluating.  However for my workflow I submit my latest notebook with a very small target task set to ensure that it executes properly before submitting my full notebook against the competition.  It's been in queue for the last 12 hours, lol.


> **** (2026-09-28 15:11, 0 votes)
> is this a promo for vast.ai or are you being serious? I estimated I'd need $300 for renting GPU if I wanted to do the training myself. Almost gave up until realized we have 4xL4 for this competition.


> > **** (2026-09-28 16:54, -1 votes)
> > bro its not promo, just i asked gemini and it told me they have cheapest gpus. So iam unbiased.


**** (2026-09-28 21:48, 0 votes)
Same here, queued for 24 hours without starting


**** (2026-09-28 15:07, 0 votes)
how do I know for when it's queued? I only see it as queued in active events, not for when


> **** (2026-09-28 18:29, 0 votes)
> It doesn't tell you. You just queue until you don't


**** (2026-09-28 14:07, 0 votes)
facing the same issue


---

## Prize payout eligibility for participants residing in Russia
/competitions/gemma-4-developer-agent/discussion/743297 | by  | posted 2026-09-25 14:50 | last comment 2026-09-28 17:25 | 1 comments | 1 votes


**** (2026-09-25 14:50, 1 votes)
Hello,

Could the Competition Host please clarify the rules for receiving monetary prizes for participants residing in the Russian Federation?

Suppose a participant:

- is a legal resident of the Russian Federation;
- is not located in Crimea, DNR, LNR, or another excluded territory;
- is not subject to U.S. sanctions or U.S. export controls;
- otherwise fully complies with the competition rules.

Would such a participant be able to actually receive the monetary prize if they win?

In particular:

1. Can monetary prizes currently be paid to residents of Russia?
2. Which payment provider or payout method is used?
3. If the standard payment provider cannot serve residents of Russia, is an alternative payout method available?

I am asking specifically about the ability to actually receive the monetary prize, not only about eligibility to enter or participate in the competition.

Thank you.


**** (2026-09-28 17:25, 0 votes)
Hi, just following up on this question.

A clarification from the Competition Host would be greatly appreciated, as the answer affects whether participants residing in Russia can reasonably commit time and compute to the competition.

Thank you.


---

## Does the time between submitting and the scoring include queue time?
/competitions/gemma-4-developer-agent/discussion/744099 | by  | posted 2026-09-28 16:59 | last comment 2026-09-28 16:59 | 0 comments | 1 votes


**** (2026-09-28 16:59, 1 votes)
Hi, hosts. I got two timing questions, since many of us plan our per-task budgets around the 12-hour limit.

1. When a submission takes many hours to show a score, is part of that time spent waiting in a queue, or is almost all of it the scoring run itself? Several threads mention long waits for the 4x L4 machines. Some of my submissions took close to 12 hours from Submit to score, much longer than I expected, so I can't tell how close they came to the limit.


2. Does the 12-hour limit start when the scoring run starts, or when we click Submit? In other words, can a long queue wait count against the limit?

Thanks!


---

## Possible mismatch between published task base commits and snapshots
/competitions/gemma-4-developer-agent/discussion/744078 | by  | posted 2026-09-28 15:16 | last comment 2026-09-28 15:16 | 0 comments | 0 votes


**** (2026-09-28 15:16, 0 votes)
Hi,

I downloaded tasks.jsonl and the individual archives snapshots/requests_7309.tgz and snapshots/requests_7315.tgz. For requests_7309, the task’s base_commit is 7407309c8a8a73aa2f4337184025d440bbedab7a, but the archive’s main points to 9c4881dc9e15b24186eb7d542752e6c554156222. For requests_7315, the task specifies 6360477c52303c9445b45fa8744b02d05a2f0905, while the archive points to ff2b582d029a3d50ea7bcf39744d2766b7aa99c1. Neither specified commit is present in its archive’s Git objects. The harness guide states that snapshots are built through base_commit. 

Could the organizers confirm whether these archives are expected to match those commits, or whether another reconstruction step or corrected snapshot set is required?  Thanks.


---

## Can the scoring server load Gemma 4 LoRA adapters?
/competitions/gemma-4-developer-agent/discussion/744070 | by  | posted 2026-09-28 14:36 | last comment 2026-09-28 14:48 | 1 comments | 1 votes


**** (2026-09-28 14:48, 1 votes)
We're using a patched version of vLLM 0.19, updated in the wheelhouse recently. You might try re-downloading or updating your wheelhouse dataset if you haven't recently. The [getting started](https://www.kaggle.com/code/ryanholbrook/getting-started-gemma-4-developer-agent) notebook appears to show it working.


**** (2026-09-28 14:36, 1 votes)
The rules explicitly permit PEFT LoRA adapters on `gemma-4-31b-it-qat-w4a16-ct`, but the published wheelhouse contains vLLM 0.19.1. Starting that required model with the sample's `adapter: main_lora` produces `ValueError: Gemma4ForConditionalGeneration does not support LoRA yet` before inference. vLLM's tagged 0.19.1 implementation does not implement `SupportsLoRA` for this class. Does the private scoring service use a different vLLM build or another adapter-serving path? Could you confirm a minimal adapter-bearing sample can be scored, or publish a compatible wheelhouse? This determines whether LoRA training is usable for this track.


---

## swegemma 0.2.7: unpacked-wheel cache ignores the wheel set, so added wheels have no effect locally
/competitions/gemma-4-developer-agent/discussion/744029 | by  | posted 2026-09-28 10:23 | last comment 2026-09-28 10:23 | 0 comments | 0 votes


**** (2026-09-28 10:23, 0 votes)
If you add wheels to your local wheels directory (for example `typing_inspection`, `inline_snapshot` or `dirty_equals`, which the public `wheels/` folder lacks and which many FastAPI tests import), a local `swegemma` run may keep failing with the same `ModuleNotFoundError` as before. The cause is the cache that `swegemma` uses for unpacked wheels.

The code is in `swegemma/harness/container_setup.py`, `_build_unpacked_wheels_tar()`:

```python
cache_dir = Path(tempfile.gettempdir()) / 'swegemma_sp_cache_v8'
tar_path = cache_dir / f'{cache_name}.tar'
if tar_path.exists() and tar_path.stat().st_size > 0:
    return tar_path
```

It is called with `cache_name='sp_base'` for all small wheels and `f'sp_whl_{pkg_norm}'` for each large one. Neither key depends on the wheels directory, on which wheels were selected, or on their versions. After the first run, every later run in the same `$TMPDIR` reuses the old tar, whatever `wheels_dir` you pass.

To reproduce:

1. Run a gold-patch check on a FastAPI task, e.g. `fastapi_15588`, with the public `wheels/`. Collection fails with `ModuleNotFoundError: No module named 'typing_inspection'`.
2. Copy `wheels/` to a new folder, add `typing_inspection-0.4.4-py3-none-any.whl`, and rerun with `wheels_dir` pointing to the new folder. Same error.
3. `rm -rf "$TMPDIR/swegemma_sp_cache_v8"` and rerun. The gold patch passes (24 tests) and the empty patch now fails for the right reason (exit 1 instead of a collection error).

Workaround: clear `$TMPDIR/swegemma_sp_cache_v8` whenever you change the wheel set, or run each wheel set with its own `TMPDIR`. A fix on the harness side could put a digest of the selected wheel file names and sizes into `cache_name`, e.g. `sp_base_<sha1>`.


---

## Onboarding notebook: what the 129 public fixes look like (+ a Kaggle survival kit)
/competitions/gemma-4-developer-agent/discussion/743957 | by  | posted 2026-09-28 00:22 | last comment 2026-09-28 00:22 | 0 comments | 4 votes


**** (2026-09-28 00:22, 4 votes)
I put together an onboarding notebook for anyone starting out: https://www.kaggle.com/code/osama133/gemma-4-dev-agent-task-anatomy-survival-kit

Task anatomy: 57% of the public tasks are single-file fixes of 20 lines or fewer; in ~76% the issue names neither the file nor the function to change; about 1 in 6 fixes touch async code; and issue length does not predict fix size.

What it means: research framing (SWE-bench, SWE-agent, Agentless, IR-based bug localisation) and design alternatives for localise / repair / validate / budget.

Survival kit: finding where inputs are mounted, getting files out of an interactive GPU session, delivering submission.zip from a CPU notebook, and GPU queue notes.

Runs on CPU in under a minute. Feedback welcome!


---

## L4 x4 sessions stuck in "Queued" for 8+ hours
/competitions/gemma-4-developer-agent/discussion/743901 | by  | posted 2026-09-27 16:14 | last comment 2026-09-27 16:49 | 1 comments | 6 votes


**** (2026-09-27 16:14, 6 votes)
Two notebooks (Version #1 and #2) with GPU L4 x4 have been queued for about 8 hours without starting. Is anyone else seeing long L4 queue times, or is there a known capacity issue? Any guidance on expected wait times before the deadline would help. Thanks


**** (2026-09-27 16:49, 1 votes)
my tpu run did start after 9 hrs. L4x4 are still on queue. so yeah the capacity is bad 😓.

![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F14027805%2F916147fdf286b6f0842733e45f0284d2%2FScreenshot%202026-09-27%20at%208.44.35PM.png?generation=1790527715925123&alt=media)


---

## Getting gpu l4*4 queued and system errror
/competitions/gemma-4-developer-agent/discussion/743600 | by  | posted 2026-09-26 09:13 | last comment 2026-09-27 15:55 | 4 comments | 11 votes


**** (2026-09-26 09:13, 11 votes)
![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F15559822%2F728686c1b4eed76e32d0b7bdd5cbf8ef%2FScreenshot%202026-09-26%20144147.png?generation=1790413923245395&alt=media)

As soon as i hit submit, submission fails with system error+ gpu l4 are being queued for a long time. 

is it just me or other people are also experiencing simialr issue??


**** (2026-09-27 15:06, 3 votes)
Adding a data point: two 4x L4 batch sessions (script kernels, competition + wheelhouse + model attached) have been queued for about 4 hours without starting, and an earlier one sat queued for ~5 hours before I cancelled it. CPU sessions start immediately.

Could the hosts share whether 4x L4 capacity is currently constrained, and whether there's a recommended way to run local evaluation in the meantime? Thanks!


> **** (2026-09-27 15:13, 0 votes)
> yeah the capacity for L4x4 and TPUs are bad.
> all my runs are still queued
> 
> ![](https://www.googleapis.com/download/storage/v1/b/kaggle-forum-message-attachments/o/inbox%2F14027805%2F94ff6e1b309ae96a18e4f0de1d592093%2FScreenshot%202026-09-27%20at%208.44.35PM.png?generation=1790522112646557&alt=media)


**** (2026-09-27 15:55, 2 votes)
same, I have been waiting in queue for 4+ hours <br>
I had previously suggested providing RTX PROs for this competition, those gpus would be much much better


**** (2026-09-26 09:24, 1 votes)
yeah my l4x4 and tpu runs are in queue for 3 hrs now, altho it doesnt fail


---

## Which google-adk versions and YAML features does the official evaluator support?
/competitions/gemma-4-developer-agent/discussion/743800 | by  | posted 2026-09-27 06:28 | last comment 2026-09-27 11:05 | 2 comments | 1 votes


**** (2026-09-27 11:05, 2 votes)
1. I would take the set of packages in the wheelhouse dataset as the authoritative set of packages for this competition.
2. We do not support for ADK 2.x features for this competition (maybe for future competitions). The scoring environment has a fixed set of packages installed which cannot be modified.
3. The `HARNESS_README.md` has some of this information. Almost any kind of ADK 1.x configuration is allowed, as described in the [Agent Config spec](https://adk.dev/api-reference/agentconfig/). We block anything that allows arbitrary code execution.


**** (2026-09-27 06:28, 1 votes)
Thanks for releasing the competition harness. I am trying to identify the right ADK version to learn and use for a competition submission.

The current official wheelhouse (v22) includes google-adk 1.36.1 and adk-submission 0.2.11. The latter declares google-adk>=1.34.0,<2.0 as a dependency. In a small Kaggle preflight, installing the official PyPI wheel for google-adk 2.9.2 over that wheelhouse succeeded, but pip check reported that version conflict and several incompatible dependencies. Importing LlmAgent then failed in the mixed environment, before config validation or model inference. This only shows that replacing the ADK wheel alone is insufficient; it does not establish whether a fully compatible 2.x environment could be supported.

Could the organizers clarify:

1. Which google-adk version and Agent Config schema are used to compile and score submission.zip? Is the wheelhouse's 1.x version an intentional requirement for this competition, or expected to change?
2. Are ADK 2.x features, especially graph Workflow/edges in YAML, supported in a competition agent.yaml? If so, how should participants provide compatible dependencies in the internet-disabled scoring environment? Does the scorer use a participant's Notebook package overrides?
3. Is there an authoritative list of supported YAML fields and pinned harness dependencies that we should target when building agents?

This determines whether we should focus on the competition's ADK 1.x subset or invest in ADK 2.x architecture. Thank you for clarifying.


---

## Task Verification Question
/competitions/gemma-4-developer-agent/discussion/743817 | by  | posted 2026-09-27 08:11 | last comment 2026-09-27 10:58 | 1 comments | 1 votes


**** (2026-09-27 10:58, 1 votes)
We did much more extensive reviewing and editing of the test tasks than the training tasks. "Impossible" tasks like you've described are one of the things we checked for. We also checked that a failing test case for the frontier model's patch was something it could have gotten correct with the information given. Unfortunately, time and resource constraints meant that we weren't able to do the same kind of review for the training set.


**** (2026-09-27 08:11, 1 votes)
It says in `Data > Dataset Generation & Verification Pipeline` that:
> Near Completion with Frontier Models: For the test set, we check that a larger frontier model can pass the case or get within a single test case of passing.

One of the training tasks is [fastapi/fastapi#15661](https://github.com/fastapi/fastapi/pull/15661). This task essentially requires the model to guess the exact file name and API surface that the tests require. Given the competition restrictions, there's no reasonable way for this task to be completed successfully. Without the ability to see the test imports or the referenced PR from [fastapi/asyncer#608](https://github.com/fastapi/asyncer/pull/608) it's not possible to know what the test is expecting.

Were frontier models run using the same harness and restrictions when doing task validation? Could the tasks be re-reviewed for feasibility in case other, similar issues exist in the train/val/test sets?


---

## Past Competition Reference ? (Anyone)
/competitions/gemma-4-developer-agent/discussion/743275 | by  | posted 2026-09-25 13:53 | last comment 2026-09-27 07:41 | 3 comments | 4 votes


**** (2026-09-25 13:53, 4 votes)
Hi I am new to this Agentic-AI world and still going through its early phase of learning. Can anyone know Past competitions similar to this one so I can take reference from it. 

Thanks in advance.!!


**** (2026-09-26 10:35, 1 votes)
Hi! Welcome to the exciting field of Agentic-AI and Autonomous Software Engineering!
The **Google - The Gemma 4 Developer Agent Competition** is actually a landmark event because it is the **first official Kaggle competition that evaluates full-lifecycle coding agents on real-world SWE-bench benchmarks** in an air-gapped container environment using local quantized models.
Here are the most relevant historical benchmarks, research open-source projects, and papers with direct links to help you get started:
### 1. Direct Benchmarks & Prior Art
* **SWE-bench / SWE-bench Verified**: The gold standard benchmark created by Princeton & Stanford that this competition is built upon. Check their official leaderboard and paper:
  * Website: [swebench.com](https://www.swebench.com/)
  * GitHub: [princeton-nlp/SWE-bench](https://github.com/princeton-nlp/SWE-bench)
  * Paper: *"SWE-bench: Can Language Models Resolve Real-World GitHub Issues?"* ([arXiv:2310.06770](https://arxiv.org/abs/2310.06770))
* **SWE-agent (Princeton NLP)**: One of the pioneering autonomous agents running inside Docker containers with a specialized Agent-Computer Interface (ACI).
  * GitHub: [princeton-nlp/SWE-agent](https://github.com/princeton-nlp/SWE-agent)
* **Agentless (UIUC)**: A brilliant open-source project by Prof. Lingming Zhang's group that challenges complex multi-turn agent loops. It uses a clean 2-phase approach (Localization -> Repair) and achieves competitive solve rates at a fraction of the cost.
  * GitHub: [OpenAutoCoder/Agentless](https://github.com/OpenAutoCoder/Agentless)
  * Paper: *"Agentless: Demystifying LLM-based Software Engineering Agents"* ([arXiv:2407.01489](https://arxiv.org/abs/2407.01489))
### 2. Similar Competitive Environments on Kaggle
* **Kaggle AI Mathematical Olympiad (AIMO)**: Great reference for tool-augmented multi-step reasoning under strict memory and hardware timeouts.
* **Kaggle LLM Science Exam**: Excellent reference for handling air-gapped inference and packaging custom libraries without internet access.
### 3. Vital Tips for Beginners (To Avoid Burning Your Evaluation Quota)
Since Kaggle enforces strict runtime budgets (e.g., total 12-hour limit across all tasks, 4GB RAM/2 vCPUs per container), here are a few golden rules:
1. **Token Economy is King**: Avoid letting the model output massive thinking blocks or full-file rewrites. The context window can easily saturate. Keeping generation lean and focused directly saves you from Out-Of-Memory (OOM) or token limit errors.
2. **Micro-Surgical Edits Over Refactoring**: In real software bugs, over 70% of fixes require fewer than 15 lines of code (e.g., adding a None check, stripping whitespace, or fixing parameter types). Avoid having the agent refactor surrounding code, as it almost always breaks pre-existing unit tests.
3. **Fail-Fast Strategy**: Don't let your agent burn 30 minutes on a single broken or unsolvable issue. Set a tight timeout/turn cap so it moves on quickly to solvable tasks.
If you ever want to discuss agent architectures, toolsets, or evaluation setups in more depth, feel free to reach out via email at: **maplemagilabsvn@protonmail.com**.
Best of luck on your competition journey! 🚀


**** (2026-09-26 21:56, 1 votes)
You may also want to check out the Nemotron Reasoning Challenge (https://www.kaggle.com/competitions/nvidia-nemotron-model-reasoning-challenge). Kinda similar in that you're adding a LoRA adapter to an existing model, albeit with a different target.


**** (2026-09-27 07:41, 0 votes)
Kowinski prize: https://www.kaggle.com/competitions/konwinski-prize


---

## The $65k prize is cheaper than the GPUs you need to win it...
/competitions/gemma-4-developer-agent/discussion/743316 | by  | posted 2026-09-25 16:31 | last comment 2026-09-26 23:47 | 5 comments | 0 votes


**** (2026-09-25 16:42, 10 votes)
Hi @lordfirlefans,

Thanks for your feedback. We're working on adding support for the other Gemma 4 dense variants (e2b, e4b, and 12b) and possibly the 26b MoE and diffusion models as well. Those should hopefully be working early next week. We're also providing 4xL4 GPU (4x24GB) machines for competition participants. I hope you'll participate!


> **** (2026-09-26 05:00, 0 votes)
> Is QLora feasible? I have a 64gb vram rig


**** (2026-09-25 16:31, 0 votes)
The $65k prize is cheaper than the GPUs you need to win it.

I run a fully local AI stack at home: coding agent, document agent, the whole thing, on a single 16 GB GPU. Exactly the kind of setup this competition claims to be about. So I read the overview with real interest: agents "offline, on consumer hardware." Then I read the rules, and started laughing.

Only one model is allowed: gemma-4-31b-it-qat-w4a16-ct. Not the small Gemma 4 variants that actually run at home. Only 31B.

Here is what that means for someone like me:

I can't run it. 16–17 GB of weights, even in 4-bit. My card can't even load the only allowed model, let alone run an agent with real context on it. And 16 GB is already more than most home GPUs have.
I can't train it. LoRA or RL on 31B means 48–80 GB datacenter GPUs or multi-GPU clusters. Nobody I know has those at home. You rent them.
I can't measure it. One submission per day, 60 public tasks, one task is worth 1.7 points. Without my own GPU farm for local evaluation, I'd be guessing.

So who wins? Teams with cloud budgets, RL pipelines and datacenter GPUs. That's not "democratizing coding agents." It's a compute contest with a consumer-friendly label on it.

And the winners pay twice: first for the compute, then by releasing everything under an open-source license. For $65k, the sponsor gets a crowd-sourced research program on SWE agents.

If "consumer hardware" is more than a slogan, prove it:

A real consumer track with a hard VRAM cap (8GB / 16 GB brackets) and the small lobotimized Gemma 4 variants.
Compute credits or hosted training for everyone, not just for those who can pay.
Rank efficiency (time, tokens, memory), not just raw solve rate.

...

Or just call it what it is: a GPU-budget competition.


**** (2026-09-25 16:49, 1 votes)
1. Kaggle provides free L4x4 and you can also use the TPUs.
2. 5090 is a consumer GPU.
3. Competing in this competition does not break your GPU.
4. You can literally buy like 10 5090s with $65k.


**** (2026-09-26 06:21, -2 votes)
The organizers are backed by Google DeepMind, and Google’s HQ is in Mountain View, California. California is, of course, the homeland of startups. And in surveys of startup/Big Tech developers, macOS often takes the majority. A Mac with 48–64 GB of unified memory can comfortably run gemma-4-31b-it-qat-w4a16-ct with an agent around it. So maybe that’s what “consumer hardware” means in the fine print. 😄


**** (2026-09-26 23:47, 0 votes)
1) Well, at least you have a single 16GB GPU! I'm crying over here being GPU-poor. 

2) The more challenging, the better. 

3) Small models will be supported. The goal of the competition is to have a setup that works for inference on consumer hardware, not about how to train it.


---

## Query regarding scorer config
/competitions/gemma-4-developer-agent/discussion/743752 | by  | posted 2026-09-26 19:39 | last comment 2026-09-26 19:39 | 0 comments | 1 votes


**** (2026-09-26 19:39, 1 votes)
Hi Ryan, two quick questions about the scoring run, because the README and the Getting Started notebook differ:
1. Events compaction: HARNESS_README §7.2 says `metric/scoring.py` uses `EventsCompactionConfig(compaction_interval=15, overlap_size=2, token_threshold=32768, event_retention_size=5)`; the Getting Started notebook uses `token_threshold=14336`. Which value does the scorer use today? Also, does it pass `default_chat_template_kwargs` (e.g. `{'enable_thinking': True}`) to vLLM, as the notebook does?
2. Sandbox: does the scorer run tasks in the Docker backend (and under gVisor/runsc?) or the subprocess backend the notebook uses?


---

## Needs clarifications on Agent Architecture + Graph/Embeddings
/competitions/gemma-4-developer-agent/discussion/743751 | by  | posted 2026-09-26 19:32 | last comment 2026-09-26 19:32 | 0 comments | 1 votes


**** (2026-09-26 19:32, 1 votes)
A.Agent architecture
1)can a custom skill carry substantial precomputed repository metadata?(what it should not carry list can be pretty useful)
2)how many LLM sub-agents can be invoked?
3)are sub-agent calls counted against the same global task time?
4)re parallel sub-agents actually useful given sequential task execution?
5)is there a limit on nested agent depth?
6)are custom tools limited to deterministic code?

B.Graph/embedding resources
1)Is the graph built from AST only or AST + semantic dependencies or how in which basis?
2)what exactly does embedding similarity represent?
3)are embeddings indexed per snapshot/commit?
4)are the zero-byte graph files a known release bug?
5)will corrected graph files be released?how soon?
6)will corrected embedding files be released?how soon?
7)are async functions intentionally missing or a preprocessing bug?


---

## computing resources
/competitions/gemma-4-developer-agent/discussion/743715 | by  | posted 2026-09-26 14:58 | last comment 2026-09-26 19:07 | 10 comments | 0 votes


**** (2026-09-26 18:06, 0 votes)
Is there a supported way to use the competition's four L4 GPUs in a private research notebook with no competition data source mounted, or with an official sanitized development-only resource instead?

We want to use only the permitted Gemma model, approved wheelhouse and development tasks while keeping reference fixes, verification tests and held-out tasks inaccessible during generation. Standard sanitized-only notebooks currently offer T4 x2, while attaching the competition source enables L4 x4. Does Kaggle provide an entitlement-only competition association, an approved private template, or a sanitized resource that grants L4 x4 access? Please also clarify the applicable free quota and notebook storage limits.

This is an access/configuration question; no solution code, model output, private data or credentials will be included.


> **** (2026-09-26 18:22, 0 votes)
> Competition source has to be attached. Notebook can be private, but it needs to be attached. Of course, don’t abuse it for something outside this competition, since Kaggle staff can eject you by their discretion.


**** (2026-09-26 16:02, 0 votes)
You probably can’t post train locally. You may be able to run the model for inference and A/B, but probably need cloud for SFT and RL.


> **** (2026-09-26 16:15, 0 votes)
> Thank you John. That leaves me out. Unfortunately I don't have resources for online computing. 
> The people likely to win this competition do! 
> Thanks again John.


> > **** (2026-09-26 18:21, 0 votes)
> > Yeah MLX would probably be slow for inference anyways. Of course, CUDA is always preferred, with tensor cores, but you could post train on the Kaggle GPUs, and run the customized harness with your own laptop to improve it, but in my experience even with my 128gb m4 MacBook, it’ll probably overheat and shut off (which would stop your iterations), so I have my own 64gb rig of Nvidia GPUs. I also was using oMLX, which is essentially one of the most optimized inference stacks for Metal.


> > **** (2026-09-26 18:30, 0 votes)
> > Modal offers $30 of free credits a month. I typically have run SFT/RL on their systems costing about $5-8 per a run. Caveat being it is cost beneficial once you have all the setup kinks figured out. Ping me on here I'll share my open source work on Modal and using Gemma and Qwen based models on Modal which should save you a few days of pain if you want! I'm working on my setup for this competition on Modal right now and if it's not to much of a giveaway I can open source those scripts for this competition as well. 
> > 
> > Having your SFT/RL regime and data organized and ready to go will save you compute cost and resources.


> > **** (2026-09-26 18:59, 0 votes)
> > Lowkey could I get your setup? I still need resources for post training.


> > **** (2026-09-26 19:02, 0 votes)
> > [LLM Tuning](https://github.com/jscott3201/llm-tuning) [Gemma Tuning](https://github.com/jscott3201/Model-Tuning)
> > 
> > This should be enough to get past the hard part with Modal. For the sake of the competition I won't dive into my data mix and overall setup but this should make getting into Modal and going with Gemma pretty much out the box easier. I've built MLX/Metal inference engines around the Gemma models (Hyperion Project) so seeing this competition was a fun one to get into for me haha


> > **** (2026-09-26 19:06, 0 votes)
> > Thanks John. Will wait for another competition!


> > **** (2026-09-26 19:07, 0 votes)
> > Thank you so much for your offer Justin. I'll defo hit u up in another competition.


**** (2026-09-26 14:58, 0 votes)
i have a macbook m1 pro. is that enough for this competition? so my only free resources are kaggle gpu and people are getting timed out. do i need to us cloud computing? ree
thank you in advance


---

## You can run Gemma 4 31B QAT locally with llama.cpp
/competitions/gemma-4-developer-agent/discussion/743743 | by  | posted 2026-09-26 18:55 | last comment 2026-09-26 18:55 | 0 comments | 0 votes


**** (2026-09-26 18:55, 0 votes)
If you're struggling to run Gemma 4 31B locally due to VRAM requirements, llama.cpp is worth trying.
The QAT model is available as GGUF, and llama.cpp lets you offload part of the model to system RAM when it doesn't fully fit in VRAM. This makes it possible to experiment locally without consuming Kaggle GPU quota.

You can also run it with llama-server, which exposes an OpenAI-compatible API, making it easy to plug into your own agent harness.

Links:
- https://huggingface.co/unsloth/gemma-4-31B-it-qat-GGUF
- https://github.com/ggml-org/llama.cpp

Has anyone else tried this setup for the competition?


---

## VRAM to run Gemma locally
/competitions/gemma-4-developer-agent/discussion/743308 | by  | posted 2026-09-25 16:08 | last comment 2026-09-26 18:24 | 2 comments | 1 votes


**** (2026-09-25 16:08, 1 votes)
Hello!

What's the minimal amount of memory needed to run inference on a single GPU? Has anyone managed to run it successfully with full context length on 24GB?


**** (2026-09-26 18:24, 0 votes)
Depends. Sometimes you can do some RAM offloading. But for 24g, post training is off the table.


**** (2026-09-25 18:19, 0 votes)
I'm only figuring things out myself right now, but my 1 day tests are:

On Mac: 26-29 for one agent task at the full 32k context. Local but Kaggle style (4 tasks in parallel) - 70-76 GB.


---

## Clima e vida cotidiana
/competitions/gemma-4-developer-agent/discussion/743687 | by  | posted 2026-09-26 12:22 | last comment 2026-09-26 12:22 | 0 comments | -5 votes


**** (2026-09-26 12:22, -5 votes)
O Clima

O clima está presente em nosso dia a dia e influencia diretamente a vida das pessoas, dos animais e das plantas. Ele é determinado pelas condições atmosféricas de uma região ao longo de muitos anos, como temperatura, umidade, chuvas e ventos.

Atualmente, as mudanças climáticas são uma preocupação em todo o mundo. O aumento das temperaturas, as secas prolongadas, as fortes chuvas e outros eventos extremos podem causar impactos no meio ambiente e na sociedade.

Por isso, é importante preservar a natureza e utilizar os recursos naturais de maneira consciente. Pequenas atitudes, como economizar água, reduzir o desperdício, reciclar e preservar as árvores, podem contribuir para um planeta mais equilibrado.

Cuidar do clima é cuidar da vida e garantir melhores condições para as futuras gerações.


---

## Rules: Only LORA allowed?
/competitions/gemma-4-developer-agent/discussion/743383 | by  | posted 2026-09-25 20:22 | last comment 2026-09-26 11:46 | 5 comments | 1 votes


**** (2026-09-25 20:33, 2 votes)
Our evaluation system in this competition is only able to accept LoRA adapters.


> **** (2026-09-25 20:38, 0 votes)
> So If I pre-train and post-train a 120B coder variant of gemma 4 you would not allow it into the competition?


> > **** (2026-09-26 00:16, 1 votes)
> > I'm a competitor but here are the [Gemma Docs](https://ai.google.dev/gemma/docs/tune) on tuning. Using Lora with swappable heads is likely the best path.


> > **** (2026-09-26 04:22, 0 votes)
> > I have my own methods ive been working on for about a year now. I can provide weights.


> > **** (2026-09-26 11:46, 1 votes)
> > It's not against the rules per se, it's just that our system isn't configured to run it. For one, we don't have the GPUs. The system is configured to accept LoRA adapters, so if you tried to submit it, the script would just throw an error. We chose to accept LoRA adapters to allow some amount of finetuning while also keeping submission file sizes moderate and for being more accessible under the hardware people are likely to have access to.


**** (2026-09-25 20:22, 2 votes)
Hello! I was curious whether the rules allow only LoRA adapters, or whether we can use other methods as long as the base model is the correct one?

thanks


---

## How much of the submission runtime is excluded as patch validation?
/competitions/gemma-4-developer-agent/discussion/743663 | by  | posted 2026-09-26 10:43 | last comment 2026-09-26 11:29 | 2 comments | 2 votes


**** (2026-09-26 10:43, 2 votes)
I understand that the runtime shown for a Kaggle submission is the total wall-clock time, while the 12-hour agent limit includes sandbox setup but excludes patch validation.  
Is there any estimate of how much time patch validation typically takes across the full test set? I’m trying to understand roughly how much of the total submission runtime does not count toward the 12-hour limit, so I can estimate what total wall-clock runtime is still safe.


**** (2026-09-26 11:24, 1 votes)
IIRC, patch validation takes around two hours if a patch is submitted for every task. If no patch is submitted for a task, then validation is skipped and that task just scores 0. A "no patch" submission only takes about ten minutes.


> **** (2026-09-26 11:29, 0 votes)
> Thanks, that’s very helpful!


---

##  Anyone else getting "Notebook Exceeded Allowed Compute" ~2 hours into evaluation?
/competitions/gemma-4-developer-agent/discussion/743661 | by  | posted 2026-09-26 10:41 | last comment 2026-09-26 11:00 | 2 comments | 3 votes


**** (2026-09-26 10:41, 3 votes)
Hey everyone 👋

I ran my first submission today and after roughly 2–2.5 hours of evaluation, it failed with:

> Notebook Exceeded Allowed Compute
> "Your notebook has requested more CPU, GPU or TPU resources than are available."

I understand that this is a general compute/constraint error, but I'm trying to understand what specifically might have triggered it in this competition.

My submission.zip was structured as an Agent Config and used:

- Model: gemma-4-31b-it-qat-w4a16-ct
- LoRA adapters: None
- Thinking: include_thoughts: false
- Architecture: Root agent.yaml + one code_analyzer sub-agent via agent_tool
- Sub-agent model: gemma-4-31b-it-qat-w4a16-ct

Per-task budget:

```yaml
timeout_seconds: 300
max_tool_calls: 35
max_time_minutes: 12
max_turns: 30


Has anyone else encountered this error with a submission containing an agent_tool sub-agent?


**** (2026-09-26 11:00, 0 votes)
same error after 5 hours of running


**** (2026-09-26 10:58, 0 votes)
Yes, I got this too despite testing on Kaggle GPU first last night after a few hours.


---

## Local eval with docker sandbox, Error Module not found
/competitions/gemma-4-developer-agent/discussion/743566 | by  | posted 2026-09-26 08:23 | last comment 2026-09-26 08:23 | 0 comments | 1 votes


**** (2026-09-26 08:23, 1 votes)
I'm trying to run the swegemma eval in local. I'm using ollama(cloud) for inference.
I've created the docker image using the Dockefile.public

`docker build -t swebench-sandbox:latest -f Dockerfile.public .`

When I ran the eval, for fastapi tasks it is giving 

`ModuleNotFoundError: No module named 'typing_inspection'`

and the whl is not there for typing_inspection. So I've to add the wheels manually and run it.

Did anyone face the same issue?


---

## First scored run on the board 🎉
/competitions/gemma-4-developer-agent/discussion/743457 | by  | posted 2026-09-26 04:46 | last comment 2026-09-26 07:29 | 1 comments | 0 votes


**** (2026-09-26 07:29, 0 votes)
congrats! my first run failed with no score as failing the 12 hr ceiling just results in an error 😑. hope they fix it!


**** (2026-09-26 04:46, 0 votes)
Hi everyone,

Just wanted to share a small milestone. After a first submission that errored out, my second attempt went through and scored 0.08 on the public leaderboard. It's great to see an agent built on a 4-bit Gemma 4 31B actually fix real bugs on its own, offline, on L4 GPUs.

A lot of the early work went into making the run itself reliable rather than into the model: the scorer runs tasks sequentially with a 12-hour ceiling, so pacing matters as much as smarts. If your submission errored, check that your budget fits the whole run.

Thanks to the hosts for the harness, the wheelhouse and the quick answers on the forum. Good luck to everyone, see you further up the leaderboard!


---

## The public leaderboard has exactly 58 tasks
/competitions/gemma-4-developer-agent/discussion/743506 | by  | posted 2026-09-26 06:00 | last comment 2026-09-26 06:00 | 0 comments | 20 votes


**** (2026-09-26 06:00, 20 votes)
Observing the current LB distribution:

```
0.00, 0.01, 0.03, 0.05, 0.06, 0.08, 0.10, 0.12, 0.13
```

and since Kaggle has always rounded down LB scores, there is only one **test set size** that could lead to exactly this distribution

```python
# Displayed scores expressed in hundredths.
observed = {0, 1, 3, 5, 6, 8, 10, 12, 13}

def compatible(n):
    possible = {100 * k // n for k in range(n + 1)}
    return observed <= possible

print([n for n in range(1, 79) if compatible(n)])
# [58]
```

| Tasks solved | Score before truncation | Displayed score |
|---:|---:|---:|
| 0 | 0.000000 | 0.00 |
| 1 | 0.017241… | 0.01 |
| 2 | 0.034482… | 0.03 |
| 3 | 0.051724… | 0.05 |
| 4 | 0.068965… | 0.06 |
| 5 | 0.086206… | 0.08 |
| 6 | 0.103448… | 0.10 |
| 7 | 0.120689… | 0.12 |
| 8 | 0.137931… | 0.13 |

which is close to the ~60 described in the data description

> There are about 120 tasks in the test set, evenly divided between the public and private splits.


---

## Does events compaction ever trigger before the context limit?
/competitions/gemma-4-developer-agent/discussion/743456 | by  | posted 2026-09-26 04:45 | last comment 2026-09-26 04:45 | 0 comments | 1 votes


**** (2026-09-26 04:45, 1 votes)
Hi team, quick question on HARNESS_README §7.2 — EventsCompactionConfig sets token_threshold = 32,768, which matches max_model_len. Since every request already has to fit prompt + max_output_tokens inside that same 32,768-token window, is there a code path where compaction fires before a session hits ContextWindowExceededError? Or is the threshold measured against something narrower (e.g. just the events history, not the full request)? Trying to understand whether long agent sessions are expected to self-compact or just need to stay well under the limit on their own. Thanks!


---

## Budgeting the 12-hour run
/competitions/gemma-4-developer-agent/discussion/743365 | by  | posted 2026-09-25 18:40 | last comment 2026-09-25 18:40 | 0 comments | 0 votes


**** (2026-09-25 18:40, 0 votes)
**Topics: max_time_minutes, thinking, and what the harness code does**

Hey everyone,

I'd love to compare notes and see your ideas as well since limited resources and number of submissions make it harder to make all experiments on your own. 

We know tasks run one after another, and a run that passes 12 hours currently errors (confirmed Ryan's answer in [743063](https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/743063#3527819). So the per-task budget matters as much as the prompt. Here is what I have so far:

**My runs so far**

Currently I am running them public in this [notebook](https://www.kaggle.com/code/zhukovoleksiy/gemma-4-walkthrough-first-submission/notebook?scriptVersionId=352770658)

| Run | Per-task budget | Thinking | Result |
| :--- | :--- | :--- | :--- |
| Starter kit, adapters removed | `max_time_minutes: 5` | on (`thinking_level: high`, as the sample had it then) | 0.00, scored about 80 minutes after submitting |
| Own agent: coder plus read-only analyzer | none (no `eval_config.yaml`) | off (`include_thoughts: false`) | 0.10, no error |
| Same agent plus memory handling and fixes: issue repeated in both agents' instructions, tail-first logs, notes as text, 4,096 output tokens | `max_time_minutes: 12`, `timeout_seconds: 300` | off (`include_thoughts: false`) | Queued: waiting for submission slot to reset |

- The first run averaged well under a minute per task. Since the hosts have removed `thinking_level` from the sample, I suspect many of those tasks failed early rather than used their time.
- The second run had no cap and did not error, so ~120 sequential tasks averaged under about 6 minutes each, including sandbox setup.
- The third run: TBD

[Gemma 4 Developer Agent Wheelhouse] (https://www.kaggle.com/datasets/metric/gemma-4-developer-agent-wheelhouse)
was released a couple hours ago. 

**What the released code does** (swegemma 0.2.7, adk_submission 0.2.11; the scoring script itself isn't in the wheelhouse, so this is the `Evaluator` path the hosts' [notebook](https://www.kaggle.com/code/ryanholbrook/getting-started-gemma-4-developer-agent) uses)

- `include_thoughts: false` sends `enable_thinking: false`, so thinking is fully off; `include_thoughts: true` or any `thinking_level` turns it on.
- `thinking_budget` is never forwarded to vLLM, so with thinking on, only `max_output_tokens` (16,384 by default) limits each turn's reasoning. That's where I'd expect time per task to grow significantly.
- The per-task time limit cancels the model call in flight, and each command's timeout shrinks to the time left, so a task overshoots its cap only slightly.
- `EvalConfig` defaults are 60 minutes, unlimited tool calls and 500 model calls per task; Ryan says the scorer's default is no limit. Either way, nothing stops one runaway task from eating all the budget so safeguards are important.
- The Phase 2 verification pytest uses the same command timeout as `timeout_seconds` (`swegemma/harness/verification.py`), so the sample's 60 seconds could fail a correct patch whose tests run longer.

**What I'm trying next:** `max_time_minutes: 12` as a failsafe, `timeout_seconds: 300`, thinking still off.

**Questions**
- Has anyone timed tasks with thinking on versus off, or are you planning to do so and willing to share results? Either locally or from submission timing?
- What caps are you using, and has anyone hit the 12-hour error?
- Any per-task time distributions from local runs (median, long tail)?


---

## Title: 13-year-old participant eligibility with parental consent
/competitions/gemma-4-developer-agent/discussion/743263 | by  | posted 2026-09-25 12:42 | last comment 2026-09-25 14:18 | 1 comments | 0 votes


**** (2026-09-25 12:42, 0 votes)
Hi! I am 13 years old and live where the legal majority age is 18. I would like to participate in the Gemma 4 Developer Agent Competition and potentially the Paper Track. The Rules state that a minor above 13 is  eligible with Parental Consent and if the Competition Sponsor agrees. So I would like to Contact the Competition Sponsor regarding this.

Thank you.


**** (2026-09-25 14:18, 0 votes)
check this: https://www.kaggle.com/competitions/gemma-4-developer-agent/discussion/742815


---

## Gemma4 allowed variant
/competitions/gemma-4-developer-agent/discussion/743056 | by  | posted 2026-09-24 19:01 | last comment 2026-09-25 13:37 | 4 comments | 0 votes


**** (2026-09-24 20:27, 0 votes)
It says in www.kaggle.com/competitions/gemma-4-developer-agent/overview/model-selection-budget-and-harness-rules :
>At present, we only support the gemma-4-31b-it-qat-w4a16-ct Gemma 4 model variant. You must choose this model for every agent and subagent.

The idea is not that you upload your own model/checkpoint. You must upload a LoRA that is applied to this model.


> **** (2026-09-25 11:37, 0 votes)
> Harness file says, any one of the below variants can be used. We can't use 2 different variants.
> 
> "All agents in a submission must declare at most ONE unique base model (len(models) == 1). Declaring two different base models (e.g., gemma-4-31b-it in the root agent and gemma-4-9b-it in a sub-agent) raises ParticipantVisibleError."
> 
> gemma-4-31b-it-qat-w4a16-ct (Starter Kit default)
> gemma-4-31b-it, gemma-4-31b
> gemma-4-27b-it, gemma-4-27b
> gemma-4-26b-a4b-it, gemma-4-26b-a4b, diffusiongemma-26b-a4b-it
> gemma-4-12b-it, gemma-4-12b
> gemma-4-9b-it, gemma-4-9b
> gemma-4-e4b-it, gemma-4-e4b
> gemma-4-e2b-it, gemma-4-e2b


> > **** (2026-09-25 11:39, 0 votes)
> > I'm also not sure now. Is the overview section correct or the Harness md file? @elanlearns


> > **** (2026-09-25 13:37, 3 votes)
> > It's only the one model listed in the Overview. We're working on supporting others.


**** (2026-09-24 19:01, 0 votes)
Hello! Are all Gemma 4 variants allowed in this competition, including E2B and E4B, or must participants use a specific version?
I have a laptop with an RTX 4050 and 16 GB of RAM. Does the competition provide any free GPU/TPU resources or training credits?
Are quantized models and LoRA/QLoRA fine-tuning allowed?
Thank you!


---

## Accessibility request: direct email contact with competition organizers — Support #261909
/competitions/gemma-4-developer-agent/discussion/743241 | by  | posted 2026-09-25 10:36 | last comment 2026-09-25 10:36 | 0 comments | 0 votes


**** (2026-09-25 10:36, 0 votes)
Dear Competition Organizers,

My name is Said Sucu, founder of SCalmora Digital Systems in Türkiye. As a participant with a disability, I would like to request an accessible way to communicate directly with the team organizing the Google – The Gemma 4 Developer Agent Competition.

Email is the most accessible and manageable communication channel for me. Could you please provide an official organizer email address, or ask Kaggle Support to forward my existing correspondence to the appropriate team and arrange a reply by email?

My Kaggle Support case number is #261909.

At SCalmora, I am developing an approach to AI-supported task completion, workflow continuity, and cognitive load reduction to help people participate more independently in digital work and economic opportunities. I would appreciate guidance on participation and any available accessibility support.

Thank you for your understanding and assistance.

Kind regards,
Said Sucu
Founder | SCalmora Digital Systems
Türkiye


---

## GPU Access
/competitions/gemma-4-developer-agent/discussion/743106 | by  | posted 2026-09-24 22:52 | last comment 2026-09-25 03:24 | 2 comments | 0 votes


**** (2026-09-24 23:13, 2 votes)
You select them in a notebook under session options.


> **** (2026-09-25 03:24, 0 votes)
> Yeah + gotta attach comp dataset. Otherwise won't work.


**** (2026-09-24 22:52, 0 votes)
Hi, could the organisers clarify how participants are expected to access the GPU environment for local evaluation? The harness documentation mentions running Gemma 4 with vLLM on 4× NVIDIA L4 GPUs. Are these GPUs available to participants through Kaggle Notebooks/competition sessions, or are we expected to provision our own GPU infrastructure?
