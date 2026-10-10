# Gemma 4 Developer Agent — Competition Work

Declarative-YAML agent for the Kaggle **Gemma 4 Developer Agent** competition: the agent fixes Python
bugs in hidden repos, scored by hermetic pytest resolution rate on 129 hidden tasks. Fixed model is
`gemma-4-31b-it-qat-w4a16-ct` (W4A16, served on 4×L4). Submissions are declarative YAML only (agent.yaml,
prompts, configs, optional LoRA adapters) — no arbitrary Python entrypoint.

## What's here

- `GEMMA_EXPERIMENT_LOG.md` — the full append-only research log: every version's pre-registered bar,
  measured result, and verdict. The honest trail (nulls included).
- `submit_vN/` — each agent version. `notebook_src.py` is the source; `_assemble.py` builds the
  `.ipynb` that Kaggle runs; `kernel-metadata.json` is the kernel config. The agent definition
  (agent.yaml / prompts/system.md / configs/sampling.yaml / eval_config.yaml) is written inline by the
  notebook and is the scored artifact inside `submission.zip`.
- `local_eval/` — a local warm-server harness (llama.cpp) that runs the agent loop + gold-test verify
  for fast, free iteration (weaker stand-in model; mechanics/ranking only).
- `colab_fasteval/` — a Colab warm-server harness that runs the REAL 31B w4a16 off Kaggle quota and
  loops config variants against one warm server (the fast dev gate).
- `train/`, `train_kaggle/` — LoRA (QLoRA) training scaffolding for a loop-discipline adapter.
- `probe_*.py` — model-free analyses of the 129 gold patches (sibling-conformance, mistake shapes,
  localization signal, etc.).
- `comp_files/` — competition reference: `HARNESS_README.md` (the authoritative harness spec) + sample
  agent configs. Large data (graphs/embeddings/snapshots/model/wheels) is gitignored.

## Key findings (see the log for the measured detail)

- **Localization word-traps**: the problem's symptom word often points at the WRONG file (e.g. "inline
  table" → `markdown.py`, not `table.py`). An anti-word-trap localization rule reliably reaches the right
  file on the 31B.
- **Trajectory length is the hidden lever**: the harness compacts history (retain ~5 events) and (per a
  confirmed vLLM/ADK bug) drops reasoning between tool calls, so LONG runs lose coherence and loop. SHORT
  runs that finish before compaction stay coherent.
- **Edit-guillotine**: `edit_file` is budget-gated; the agent that localizes correctly often runs out of
  calls before landing the edit. Budget too tight (12) guillotines; too loose (40) wanders/times out.
- **Prompt rules decay in the long zone**: edit-early / anti-loop instructions get ignored past ~call 10-15
  — pointing at a weights-level (LoRA) fix for loop discipline.
- **fastapi has an `inline_snapshot` dependency gap** affecting ~18 tasks (collection failures); rich is
  unaffected — one reason this work is rich-focused.

## Author
George / Adam Johnson (Kaggle: comfyops, HF: bigesta)
