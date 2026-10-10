"""Ground-truth check: does the r8 adapter produce the `1`-collapse via the HF+PEFT path (NO GGUF
conversion), or only via the GGUF+llama-server path? If HF also collapses -> conversion is faithful,
finding stands. If HF is clean where GGUF collapses -> the GGUF conversion broke things.

HF path = exactly what we trained: BitsAndBytes NF4 base + PEFT adapter, greedy decode.
We feed a long tool-call-style prompt (the regime where the collapse appeared) and dump raw gen.
"""
import warnings, json, sys, os, time
warnings.filterwarnings("ignore")
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

OUT = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_hf_probe.log", "w", encoding="utf-8")
def p(*a): print(*a, file=OUT, flush=True)

BASE = "google/gemma-4-12B-it"
ADAPTER = r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\adapters\fastapi_spec12b_r8"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "local_eval"))
import run_local as R

tok = AutoTokenizer.from_pretrained(BASE)
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                         bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
base = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, device_map={"":0},
                                            attn_implementation="eager")
model = PeftModel.from_pretrained(base, ADAPTER)
model.eval()
p(f"loaded base+adapter; effective lora scale alpha/r = {16/8}")

# a realistic long fastapi locate prompt (the regime where GGUF collapsed) + the tool schema the model
# must answer in. We ask it to make tool calls over a long context.
task = R.load_task("fastapi_14479")
R.set_repo("fastapi")
sysmsg = R.SYSTEM_PROMPT
user = f"Repository: {task['repo']}\n\nProblem:\n{task['problem_statement'][:3500]}\n\nFix the bug. Locate fast, edit, submit_patch."
prompt = tok.apply_chat_template(
    [{"role":"system","content":sysmsg},{"role":"user","content":user}],
    tools=R.TOOLS, add_generation_prompt=True, tokenize=False)
enc = tok(prompt, return_tensors="pt", truncation=True, max_length=8192).to("cuda")
p(f"prompt tokens: {enc['input_ids'].shape[1]}")

for scale in [1.0, 0.5]:
    # set PEFT adapter scale by scaling the lora weights' contribution: PeftModel supports
    # setting scaling via model.base_model but simplest is to compare at native (1.0) and
    # a down-scaled variant via set_adapter scaling if available; else just report native.
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=400, do_sample=False, pad_token_id=tok.eos_token_id)
    gen = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
    dt = time.time()-t0
    # count degenerate "1" tokens / repetition
    ones = gen.count('"1"') + gen.count(":1}") + gen.count(":1,")
    p("\n===== HF PEFT native (adapter on, alpha/r=2.0), gen " + str(len(gen)) + " chars in " + f"{dt:.0f}" + "s =====")
    p("  bare-int-arg (collapse) markers: " + str(ones))
    p("  RAW GEN (first 1500 chars):")
    p("  " + gen[:1500].replace("\n","\n  "))
    break  # native only; scaling PEFT at runtime needs extra plumbing, native is the ground truth

OUT.close()
print("done")
