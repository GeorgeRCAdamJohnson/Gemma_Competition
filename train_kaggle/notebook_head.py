# Gemma 4 Developer Agent — TRACK A: 31B localization-LoRA training (1 epoch, low-rank QLoRA)
# PURPOSE: fit a LoRA that teaches the 31B agent to LOCALIZE (grep the problem's concrete tokens, then
#   read the gold file) WITHOUT re-deriving it each run — the learned-weights counterpart of the v7/
#   SKILL.md text-search lever. Trains on 48 symptom-DERIVABLE localization trajectories (leakage-checked:
#   100% of queries are extractable from the metadata-stripped symptom; see _check_traj_leak.py).
#
# CRITICAL BASE CHOICE (GEMMA_EXPERIMENT_LOG "TRACK A UNBLOCK"): the SCORED base
#   gemma-4-31b-it-qat-w4a16-ct is a vLLM serving artifact with NO trainable forward path. We therefore
#   train on the UNQUANTIZED QAT bf16 twin  gemma-4-31b-it-qat-q4_0-unquantized  (attach:
#   google/gemma-4/Transformers/gemma-4-31b-it-qat-q4_0-unquantized/2) and SERVE the adapter over the
#   w4a16 model at score time (same architecture/shapes -> adapter loads; the task-4 probe VERIFIES this).
#
# QAT-aware knobs (ghchinoy gemma-qat-tuning guidance, rephrased for compliance): conservative rank
#   (r=16) so the fit leans on the pre-conditioned base; conservative LR (1e-4). 1 EPOCH = standing
#   default (Rasmus/theprint shipped 2B experts at 1 epoch; our own over-training produced the `1`-collapse).
#
# RESUMABLE (RULE A): checkpoints the adapter after each epoch to /kaggle/working/adapters/localizer_v1/
#   with progress.json; a re-run resumes. 31B over 4xL4 fits via bnb nf4 (device_map="auto" shards it).
# INTERNET ON (this is a TRAINING kernel, not the submission) to pip-install peft/bitsandbytes/accelerate.
# OUTPUT: adapters/localizer_v1/{adapter_config.json, adapter_model.safetensors} (<<3GiB), zipped.

# ===== CELL 1: install training deps (internet ON; keep the image's gemma-4-aware transformers) =====
import os
# OOM FIX (run 1 died at step 16/48 on T4x2 14.56GiB): fight fragmentation on the first shard. The run-1
# error message itself recommended this exact flag. Set BEFORE torch/cuda init.
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"
import subprocess, sys
# bitsandbytes + peft + accelerate are the training-only deps; the Kaggle image already ships a
# transformers that recognizes the gemma-4 architecture (it serves the comp base), so we do NOT pin/
# downgrade transformers. --no-deps on peft/bnb avoids pulling an incompatible transformers.
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "bitsandbytes", "accelerate"], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U", "--no-deps", "peft"], check=True)
import torch, transformers, peft, bitsandbytes
print("transformers", transformers.__version__, "| peft", peft.__version__,
      "| bitsandbytes", bitsandbytes.__version__)
print("torch", torch.__version__, "| cuda", torch.cuda.is_available(),
      "| gpus", torch.cuda.device_count() if torch.cuda.is_available() else 0)
