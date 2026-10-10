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

# ===== CELL 2: decode the embedded 48 localization trajectories (gzip+base64, self-contained) =====
import gzip, base64, json as _json
_DATA_B64GZ = (
    "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"
)
_raw = gzip.decompress(base64.b64decode(_DATA_B64GZ))
DATA = [_json.loads(l) for l in _raw.decode('utf-8').splitlines() if l.strip()]
print('loaded', len(DATA), 'localization trajectories')
assert all('messages' in r for r in DATA), 'bad data shape'
print('sample assistant turn:\n', DATA[0]['messages'][1]['content'][:200])

# ===== CELL 3: load base (bf16 twin, nf4 4-bit, sharded over all GPUs) + attach fresh/resumed LoRA =====
import os, json, time, random
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training, PeftModel
import bitsandbytes.nn as bnn

# the UNQUANTIZED QAT bf16 twin — attached read-only by Kaggle at this path (framework=transformers).
BASE = "/kaggle/input/gemma-4/transformers/gemma-4-31b-it-qat-q4_0-unquantized/2"
if not os.path.isdir(BASE):
    # fall back to the lowercased-framework path variant Kaggle sometimes mounts
    import glob
    cands = glob.glob("/kaggle/input/**/gemma-4-31b-it-qat-q4_0-unquantized/**/config.json", recursive=True)
    assert cands, f"base model not mounted; searched /kaggle/input. Found: {glob.glob('/kaggle/input/*')}"
    BASE = os.path.dirname(cands[0])
print("[base]", BASE)

OUT = "/kaggle/working/adapters/localizer_v1"
CKPT = os.path.join(OUT, "ckpt")
os.makedirs(CKPT, exist_ok=True)
# OOM FIX (run 1 died at step 16/48): MAXLEN 1024->512 (trajectories are short grep+read turns, 512 is
# ample and ~halves activation memory). r/alpha/LR/epochs unchanged (loss was descending healthily).
R, ALPHA, MAXLEN, LR, EPOCHS = 16, 32, 512, 1e-4, 1   # 1 epoch standing default; conservative r/LR for QAT

tok = AutoTokenizer.from_pretrained(BASE)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token

# OOM FIX: cap per-GPU weight placement so device_map leaves HEADROOM on each shard for activations+grads
# during backward (run 1 OOM'd on GPU0 which also carries embed+loss). Reserve ~3GiB/GPU of headroom; spill
# the rest to CPU RAM. Computed from the ACTUAL devices present (T4x2=14.56GiB each, not the planned L4x4).
n_gpu = torch.cuda.device_count()
per_gpu_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)
cap_gib = max(6, int(per_gpu_total - 3))                      # leave ~3GiB headroom per GPU
max_memory = {i: f"{cap_gib}GiB" for i in range(n_gpu)}
max_memory["cpu"] = "40GiB"                                   # spill overflow weights to host RAM
print(f"[mem] {n_gpu} GPUs x {per_gpu_total:.1f}GiB; cap {cap_gib}GiB/GPU + CPU spill")

bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                         bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(
    BASE, quantization_config=bnb, device_map="auto", max_memory=max_memory,
    attn_implementation="eager", torch_dtype=torch.bfloat16,
)
# OOM FIX: pin use_reentrant=True (run-1 warned the default is changing; reentrant checkpointing frees
# activation memory more aggressively, which is what we need on the 14.56GiB cards).
model = prepare_model_for_kbit_training(
    model, use_gradient_checkpointing=True,
    gradient_checkpointing_kwargs={"use_reentrant": True})
model.config.use_cache = False

def pick_targets(m):
    # text-decoder q/v self-attn Linear4bit modules; exclude any vision/audio tower.
    allqv = [n for n, mod in m.named_modules()
             if isinstance(mod, bnn.Linear4bit)
             and n.endswith(("q_proj", "v_proj"))
             and "vision" not in n and "audio" not in n and "mm" not in n]
    tgt = [n for n in allqv if "language_model" in n] or allqv
    assert tgt, "no q/v Linear4bit targets found"
    return tgt

prog_path = os.path.join(CKPT, "progress.json")
# progress tracks epochs done AND the step within the current epoch (finer-grained resume after run-1 OOM).
progress = json.load(open(prog_path)) if os.path.exists(prog_path) else {"done": 0, "step": 0}
progress.setdefault("step", 0)
resumed = os.path.exists(os.path.join(CKPT, "adapter_config.json"))
if resumed:
    print(f"[resume] loading adapter from {CKPT}; epochs done={progress['done']}")
    model = PeftModel.from_pretrained(model, CKPT, is_trainable=True)
else:
    tgt = pick_targets(model)
    print(f"[fresh] {len(tgt)} LoRA targets; sample: {tgt[:2]}")
    lcfg = LoraConfig(r=R, lora_alpha=ALPHA, target_modules=tgt, lora_dropout=0.05,
                      bias="none", task_type="CAUSAL_LM")
    model = get_peft_model(model, lcfg)
model.print_trainable_parameters()

# ===== CELL 4: assistant-masked encode + resumable 1-epoch train loop (checkpoint each epoch) =====
def encode(rec):
    msgs = rec["messages"]
    full = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
    prompt = tok.apply_chat_template(msgs[:-1], tokenize=False, add_generation_prompt=True)
    full_ids = tok(full, return_tensors="pt", truncation=True, max_length=MAXLEN)["input_ids"][0]
    prompt_ids = tok(prompt, return_tensors="pt", truncation=True, max_length=MAXLEN)["input_ids"][0]
    labels = full_ids.clone()
    labels[: min(len(prompt_ids), len(labels))] = -100   # learn ONLY the assistant (localization) turn
    return full_ids.unsqueeze(0), labels.unsqueeze(0)

opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=LR)
optp = os.path.join(CKPT, "optimizer.pt")
if resumed and os.path.exists(optp):
    try:
        opt.load_state_dict(torch.load(optp)); print("[resume] optimizer restored")
    except Exception as e:
        print("[resume] opt restore skipped:", e)

def save_ckpt(step_in_epoch, epochs_done):
    model.save_pretrained(CKPT)
    torch.save(opt.state_dict(), optp)
    progress["done"] = epochs_done
    progress["step"] = step_in_epoch
    json.dump(progress, open(prog_path, "w"))

CKPT_EVERY = 12   # mid-epoch checkpoint cadence (RULE A, finer-grained so an OOM/timeout resumes cleanly)
dev0 = next(model.parameters()).device
model.train()
for ep in range(progress["done"], EPOCHS):
    order = list(range(len(DATA))); random.Random(ep).shuffle(order)
    start = progress["step"] if ep == progress["done"] else 0   # resume mid-epoch after an OOM/timeout
    if start:
        print(f"[resume] epoch {ep+1}: skipping to step {start}")
    run, nz, t0 = 0.0, 0, time.time()
    for j in range(start, len(order)):
        i = order[j]
        ids, labels = encode(DATA[i])
        ids, labels = ids.to(dev0), labels.to(dev0)
        if (labels != -100).sum() == 0:
            continue
        loss = model(input_ids=ids, labels=labels).loss
        loss.backward(); opt.step(); opt.zero_grad()
        run += loss.item(); nz += 1
        del loss, ids, labels
        if j % 8 == 0:
            print(f"  e{ep+1} step {j}/{len(order)} loss={run/max(nz,1):.3f} {time.time()-t0:.0f}s", flush=True)
        if (j + 1) % CKPT_EVERY == 0:
            save_ckpt(j + 1, ep)                     # resumable mid-epoch
            torch.cuda.empty_cache()                 # OOM FIX: fight fragmentation between checkpoints
            print(f"  [ckpt] mid-epoch step {j+1} saved", flush=True)
    save_ckpt(0, ep + 1)                             # epoch complete -> reset step, bump epoch
    torch.cuda.empty_cache()
    print(f"[ckpt] epoch {ep+1}/{EPOCHS} mean_loss={run/max(nz,1):.4f} -> saved to {CKPT}", flush=True)

# clean final adapter at OUT root (what gets shipped)
model.save_pretrained(OUT)
print("[done] final adapter ->", OUT)

# ===== CELL 5: verify adapter artifacts + size, zip for download =====
import shutil
cfg = json.load(open(os.path.join(OUT, "adapter_config.json")))
print("adapter_config r=", cfg.get("r"), "alpha=", cfg.get("lora_alpha"),
      "n_targets=", len(cfg.get("target_modules", [])))
has_weights = os.path.exists(os.path.join(OUT, "adapter_model.safetensors"))
sz = sum(os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)
         if os.path.isfile(os.path.join(OUT, f)))
print("adapter_model.safetensors present:", has_weights, "| adapter size:", round(sz/1e6, 1), "MB")
assert has_weights, "no adapter weights saved!"
assert sz < 3 * 1024**3, "adapter exceeds 3GiB harness cap"
zp = shutil.make_archive("/kaggle/working/localizer_v1_adapter", "zip", root_dir=OUT)
print("zipped ->", zp, round(os.path.getsize(zp)/1e6, 1), "MB")
