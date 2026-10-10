
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
