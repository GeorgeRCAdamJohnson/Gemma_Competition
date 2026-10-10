"""DECISIVE: does the r16 adapter (the one that showed the 9x `1`-collapse via GGUF) produce the SAME
`1`-collapse via the HF+PEFT path? Force past early eos with min_new_tokens so a collapse has room to
appear. If HF r16 ALSO collapses to `1` -> the collapse is real (conversion faithful). If HF r16 does
NOT collapse -> the `1`-attractor is a GGUF-path artifact and the 12B verdict is confounded.
"""
import warnings, sys, os, time
warnings.filterwarnings("ignore")
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

OUT = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_hf_r16_probe.log", "w", encoding="utf-8")
def p(*a): print(*a, file=OUT, flush=True)

BASE = "google/gemma-4-12B-it"
ADAPTER = r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\adapters\fastapi_specialist_12b"  # the r16 one
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "local_eval"))
import run_local as R

tok = AutoTokenizer.from_pretrained(BASE)
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                         bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
base = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, device_map={"":0},
                                            attn_implementation="eager")
model = PeftModel.from_pretrained(base, ADAPTER); model.eval()
p("r16 adapter loaded; alpha/r = 32/16 = 2.0 (same effective scale as r8's 16/8)")

task = R.load_task("fastapi_14479"); R.set_repo("fastapi")
user = f"Repository: {task['repo']}\n\nProblem:\n{task['problem_statement'][:3500]}\n\nFix the bug. Locate fast, edit, submit_patch."
prompt = tok.apply_chat_template(
    [{"role":"system","content":R.SYSTEM_PROMPT},{"role":"user","content":user}],
    tools=R.TOOLS, add_generation_prompt=True, tokenize=False)
enc = tok(prompt, return_tensors="pt", truncation=True, max_length=8192).to("cuda")
p(f"prompt tokens: {enc['input_ids'].shape[1]}")

# force past early eos so a collapse has room: min_new_tokens high, eos suppressed via min length
with torch.no_grad():
    out = model.generate(**enc, max_new_tokens=400, min_new_tokens=250, do_sample=False,
                         pad_token_id=tok.eos_token_id)
gen = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
ones = gen.count(':1}') + gen.count(':1,') + gen.count('"1"') + gen.count('query:1') + gen.count('path:1')
p(f"\n===== HF r16 forced-long gen: {len(gen)} chars =====")
p("  `1`-collapse markers: " + str(ones))
p("  RAW GEN (first 2000 chars):")
p("  " + gen[:2000].replace("\n","\n  "))
OUT.close(); print("done")
