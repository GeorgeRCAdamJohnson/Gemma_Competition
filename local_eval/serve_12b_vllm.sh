#!/bin/bash
# official 12B vLLM serve for parity rig - port 8082, built-in gemma4 parsers (tutorial cell 8 flags)
# PATH sanitized: the inherited systemprofile WindowsApps entry makes execvp return EACCES for any lookup (killed nvcc searches x3)
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$HOME/.local/bin
# flashinfer sampler JITs CUDA source at boot (needs nvcc; no Linux toolkit, no sudo); torch sampler is equivalent
export VLLM_USE_FLASHINFER_SAMPLER=0
exec ~/vllmenv/bin/vllm serve ~/models/gemma-4-12b-it-qat-w4a16-ct-v2 \
  --host 0.0.0.0 --port 8082 \
  --served-model-name gemma-4-12b-it-qat-w4a16-ct \
  --tool-call-parser gemma4 --reasoning-parser gemma4 --enable-auto-tool-choice \
  --max-model-len 32768 \
  --max-num-batched-tokens 2048 \
  --max-num-seqs 8 \
  --limit-mm-per-prompt '{"video": {"count": 1, "num_frames": 1}}' \
  --gpu-memory-utilization 0.75 \
  --dtype bfloat16 \
  --compilation-config '{"inductor_compile_config": {"combo_kernels": false, "benchmark_combo_kernel": false}}'