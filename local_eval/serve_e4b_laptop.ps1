# Serve the official Gemma-4 E4B QAT GGUF on this 6GB RTX 4050 laptop for the local find-def rig.
# run_local.py / gate_run.py expect an OpenAI-compatible server on 127.0.0.1:8081 with --jinja tool-calling.
#
# Memory notes (6141 MiB card, ~4.6 GB free): Q4_0 weights ~5.15 GB on disk. We offload as many layers as
# fit and spill the rest to CPU (-ngl auto-tuned by llama.cpp if too high; start at 28 of ~34 and lower if OOM).
# ctx 16384 keeps the run_local compaction threshold (14336) meaningful while holding KV cache small.
# This is a MECHANISM-DEBUG rig (does find-def fire, does the agent edit the definition file); resolve counts
# are score-noisy vs Kaggle per the 2026-10-17 parity study, so trust BEHAVIOR not absolute solves.

$LLAMA = "C:\Users\biges\.docker\bin\inference\llama-server.exe"
$MODEL = "C:\Users\biges\models\gemma4-e4b-qat\gemma-4-E4B_q4_0-it.gguf"

if (-not (Test-Path $MODEL)) { Write-Error "model not downloaded yet: $MODEL"; exit 1 }

& $LLAMA `
  --model $MODEL `
  --host 127.0.0.1 --port 8081 `
  --ctx-size 16384 `
  --n-gpu-layers 28 `
  --jinja `
  --temp 0.2 --top-p 0.95 `
  --parallel 1 `
  --no-webui
