# Runs ON the CPU VM: construct the smoke run's VllmConfig/VllmServer in the Kaggle-matched venv (no GPU needed)
# so any argument error shows up before GPU time is spent.
import subprocess

code = r'''
from adk_submission import VllmConfig, VllmServer, discover_adapters
cfg = VllmConfig(model="/content/model", port=8000, host="127.0.0.1", tool_call_parser="gemma4",
                 reasoning_parser="gemma4", dtype="bfloat16", enable_auto_tool_choice=True, enable_lora=False,
                 tensor_parallel_size=1, startup_timeout=60*25, max_model_len=32768, gpu_memory_utilization=0.85,
                 extra_args=["--served-model-name", "gemma-4-e4b-it-qat-w4a16-ct", "2"])
s = VllmServer(cfg, adapter_manifest=None)
print("VllmConfig OK; build_env callable:", callable(getattr(s, "build_env", None)),
      "| has stop:", hasattr(s, "stop"), "| base_url attr:", hasattr(s, "base_url"))
import yaml; print("yaml OK")
'''
r = subprocess.run(["/content/venv/bin/python", "-c", code], capture_output=True, text=True)
print(r.stdout, r.stderr[-1500:])
