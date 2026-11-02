export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/lib/wsl/lib
source ~/vllm-kaggle/bin/activate
cd ~
# Kaggle VllmServer.build_cmd() output (tp=1) + local-only memory flags: --kv-cache-memory-bytes 2G --max-num-seqs 4
exec python -m vllm.entrypoints.openai.api_server --model /home/biges/models/gemma-4-E4B-it-qat-w4a16-ct --host 0.0.0.0 --port 8081 --max-model-len 32768 --dtype bfloat16 --gpu-memory-utilization 0.9 --enable-auto-tool-choice --tool-call-parser gemma4 --reasoning-parser gemma4 --reasoning-config '{"reasoning_start_str": "<|channel>", "reasoning_end_str": "<channel|>"}' --no-scheduler-reserve-full-isl --hf-overrides '{"architectures": ["Gemma4ForCausalLM"], "model_type": "gemma4"}' \
  --kv-cache-memory-bytes 2G --max-num-seqs 4 > ~/vllm_e4b.log 2>&1