"""Step A: prove the FULL QLoRA loop runs on this Blackwell box, on the CORRECT architecture (Gemma-4).
Load gemma-4-E2B-it with on-the-fly 4-bit NF4 -> attach a tiny rank-8 LoRA -> real optimizer steps -> save.
E2B is the smallest Gemma-4 = cheap dev base; the SAME recipe/data pipeline scales up to the 31B ship base.
This is a scaffold test (does the loop run + fit VRAM?), NOT a method experiment yet."""
import warnings, time, os
warnings.filterwarnings("ignore")
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

MODEL = "google/gemma-4-E2B-it"
print(f"[{time.strftime('%H:%M:%S')}] loading tokenizer: {MODEL}")
tok = AutoTokenizer.from_pretrained(MODEL)

bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                         bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
print(f"[{time.strftime('%H:%M:%S')}] loading 4-bit base (NF4)...")
t0 = time.time()
model = AutoModelForCausalLM.from_pretrained(MODEL, quantization_config=bnb, device_map={"": 0},
                                             torch_dtype=torch.bfloat16, attn_implementation="eager")
print(f"  loaded in {time.time()-t0:.1f}s; VRAM free {torch.cuda.mem_get_info()[0]/1e9:.1f}GB")

model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
# Gemma-4 wraps attn projections in Gemma4ClippableLinear; the real Linear4bit is the inner `.linear`.
# E2B is MULTIMODAL (vision_tower/audio_tower also have q_proj.linear) -> scope to the TEXT decoder only.
# Use a regex target: language_model ... self_attn.(q|v)_proj.linear, excluding vision/audio towers.
import bitsandbytes.nn as _bnn
# TEXT decoder (language_model) uses BARE Linear4bit at self_attn.q_proj/v_proj (no .linear wrapper).
# The Gemma4ClippableLinear wrapper is ONLY in vision/audio towers, which we must NOT touch.
# Target exact text-side q/v proj module names, scoped to language_model.
cand = [n for n,mod in model.named_modules()
        if isinstance(mod, _bnn.Linear4bit)
        and n.endswith(("self_attn.q_proj","self_attn.v_proj"))
        and "language_model" in n and "vision" not in n and "audio" not in n]
print(f'  LoRA target count: {len(cand)}; sample: {cand[:2]}')
assert cand, "no text-side q/v targets found"
lcfg = LoraConfig(r=8, lora_alpha=16, target_modules=cand, lora_dropout=0.0, bias="none", task_type="CAUSAL_LM")
model = get_peft_model(model, lcfg)
model.print_trainable_parameters()

text = ("### Issue: FastAPI ServerSentEvent 'event' field accepts multi-line content.\n"
        "### Fix: add AfterValidator(_check_single_line) rejecting \\n, \\r, \\r\\n with message \"SSE 'event' must be a single line\".\n")
enc = tok(text, return_tensors="pt", truncation=True, max_length=256).to("cuda")
enc["labels"] = enc["input_ids"].clone()

opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4)
model.train()
print(f"[{time.strftime('%H:%M:%S')}] running 3 optimizer steps...")
for step in range(3):
    t = time.time()
    out = model(**enc); out.loss.backward(); opt.step(); opt.zero_grad()
    print(f"  step {step}: loss={out.loss.item():.4f}  {time.time()-t:.2f}s  VRAM free {torch.cuda.mem_get_info()[0]/1e9:.1f}GB")

outdir = os.path.join(os.path.dirname(__file__), "_smoke_adapter_g4e2b")
model.save_pretrained(outdir)
sz = sum(os.path.getsize(os.path.join(outdir,f)) for f in os.listdir(outdir) if os.path.isfile(os.path.join(outdir,f)))
print(f"[{time.strftime('%H:%M:%S')}] saved adapter to {outdir} ({sz/1e6:.1f} MB)")
print("GEMMA-4 QLORA LOOP: WORKS")
