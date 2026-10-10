"""Diagnose training throughput: measure sec/step for E2B QLoRA under different settings,
so we fix the slow trainer with DATA not guesses. Tests: checkpointing on/off, seq 512 vs 1024."""
import warnings, time, torch
warnings.filterwarnings("ignore")
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
import bitsandbytes.nn as bnn

BASE="google/gemma-4-E2B-it"
tok=AutoTokenizer.from_pretrained(BASE)
bnb=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type="nf4",bnb_4bit_compute_dtype=torch.bfloat16,bnb_4bit_use_double_quant=True)

def build(gradckpt):
    m=AutoModelForCausalLM.from_pretrained(BASE,quantization_config=bnb,device_map={"":0},attn_implementation="eager")
    m=prepare_model_for_kbit_training(m,use_gradient_checkpointing=gradckpt)
    tgt=[n for n,mod in m.named_modules() if isinstance(mod,bnn.Linear4bit)
         and n.endswith(("self_attn.q_proj","self_attn.v_proj")) and "language_model" in n and "vision" not in n and "audio" not in n]
    m=get_peft_model(m,LoraConfig(r=16,lora_alpha=32,target_modules=tgt,lora_dropout=0.05,bias="none",task_type="CAUSAL_LM"))
    return m

txt="def example():\n    "+("x = 1\n    "*300)  # ~ filler to hit target length
for gradckpt in (True, False):
    for seqlen in (512, 1024):
        try:
            m=build(gradckpt); m.train()
            opt=torch.optim.AdamW([p for p in m.parameters() if p.requires_grad],lr=2e-4)
            enc=tok(txt,return_tensors="pt",truncation=True,max_length=seqlen).to("cuda"); enc["labels"]=enc["input_ids"].clone()
            # warmup
            o=m(**enc); o.loss.backward(); opt.step(); opt.zero_grad()
            torch.cuda.synchronize(); t=time.time(); N=5
            for _ in range(N):
                o=m(**enc); o.loss.backward(); opt.step(); opt.zero_grad()
            torch.cuda.synchronize(); dt=(time.time()-t)/N
            free=torch.cuda.mem_get_info()[0]/1e9
            print(f"gradckpt={gradckpt} seqlen={enc['input_ids'].shape[1]:4d}  {dt:.2f}s/step  VRAM free {free:.1f}GB")
            del m, opt; torch.cuda.empty_cache()
        except Exception as e:
            print(f"gradckpt={gradckpt} seqlen={seqlen}  OOM/ERR: {type(e).__name__} {str(e)[:50]}")
            torch.cuda.empty_cache()
