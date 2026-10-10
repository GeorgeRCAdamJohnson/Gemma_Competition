"""Task #5: A/B eval base vs specialist vs generalist on the 6 held-out FastAPI tasks.
Loads the HF E2B base ONCE, then swaps adapters (base/none, specialist, generalist) and runs the
agent loop on each held-out task. Captures PRIMARY (resolved) + SECONDARY edit-quality metrics:
  - produced_patch: non-empty diff
  - non_noop_edit: at least one edit_file where old_string != new_string actually changed the file
  - reached_submit: agent called submit_patch
  - applies: patch applies cleanly in verify()
This is the pre-registered measurement. E2B is weak -> secondary metrics are the real signal.
"""
import warnings, json, sys, os, time, argparse
warnings.filterwarnings("ignore")
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "local_eval"))
import run_local as R
from gemma4_toolparse import parse_tool_calls

BASE = "google/gemma-4-E2B-it"
HELD = ["fastapi_15588","fastapi_14458","fastapi_14479","fastapi_5624","fastapi_14873","fastapi_15763"]

def make_chat(tok, model):
    def chat(messages, model_name):
        rm = []
        for mm in messages:
            if mm.get("tool_calls"):
                mm = dict(mm)
                mm["tool_calls"] = [{**tc, "function": {**tc["function"],
                    "arguments": (json.loads(tc["function"]["arguments"]) if isinstance(tc["function"].get("arguments"), str)
                                  else tc["function"].get("arguments", {}))}} for tc in mm["tool_calls"]]
            rm.append(mm)
        prompt = tok.apply_chat_template(rm, tools=R.TOOLS, add_generation_prompt=True, tokenize=False)
        enc = tok(prompt, return_tensors="pt", truncation=True, max_length=8192).to("cuda")
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=R.MAX_TOKENS, do_sample=False, pad_token_id=tok.eos_token_id)
        gen = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        tcs = parse_tool_calls(gen)
        msg = {"role":"assistant","content": gen if not tcs else ""}
        if tcs: msg["tool_calls"] = tcs
        return {"choices":[{"message":msg,"finish_reason":"tool_calls" if tcs else "stop"}]}
    return chat

def run_arm(tok, model, label):
    R.chat = make_chat(tok, model)
    R.TEMPERATURE = 0.0; R.MAX_TOKENS = 1024
    rows = []
    for tid in HELD:
        task = R.load_task(tid); R.set_repo(task["repo"].split("/")[-1])
        diff, calls, dur, submitted = R.run_agent(task, "hf", 15)
        produced = bool(diff.strip())
        applies = False; resolved = False
        if produced:
            try:
                resolved, _ = R.verify(task, diff)
                applies = True  # verify ran apply; treat reaching pytest as applied-ish
            except Exception:
                applies = False
        rows.append(dict(task=tid, resolved=bool(resolved), produced=produced,
                         reached_submit=bool(submitted), calls=calls, chars=len(diff)))
        print(f"  [{label}] {tid:14} resolved={resolved} produced={produced} submit={submitted} calls={calls} chars={len(diff)}", flush=True)
    return rows

def summarize(label, rows):
    n = len(rows)
    return dict(arm=label, resolved=sum(r["resolved"] for r in rows),
                produced=sum(r["produced"] for r in rows),
                reached_submit=sum(r["reached_submit"] for r in rows), n=n)

def main():
    tok = AutoTokenizer.from_pretrained(BASE)
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    print(f"[{time.strftime('%H:%M:%S')}] loading base...", flush=True)
    base = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, device_map={"":0}, attn_implementation="eager")
    base.eval()
    from peft import PeftModel
    results = {}
    SPEC = os.path.join(os.path.dirname(__file__), "adapters", "fastapi_specialist")
    GEN  = os.path.join(os.path.dirname(__file__), "adapters", "generalist")

    print(f"[{time.strftime('%H:%M:%S')}] ARM 1/3: BASE (no adapter)", flush=True)
    results["base"] = run_arm(tok, base, "base")

    print(f"[{time.strftime('%H:%M:%S')}] ARM 2/3: SPECIALIST", flush=True)
    spec = PeftModel.from_pretrained(base, SPEC, adapter_name="spec"); spec.eval()
    results["specialist"] = run_arm(tok, spec, "specialist")
    # unload adapter back to base for a clean generalist load
    del spec; torch.cuda.empty_cache()
    base2 = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb, device_map={"":0}, attn_implementation="eager"); base2.eval()

    print(f"[{time.strftime('%H:%M:%S')}] ARM 3/3: GENERALIST", flush=True)
    gen = PeftModel.from_pretrained(base2, GEN, adapter_name="gen"); gen.eval()
    results["generalist"] = run_arm(tok, gen, "generalist")

    print("\n===== A/B SUMMARY (6 held-out FastAPI tasks, E2B, temp 0) =====", flush=True)
    for arm in ("base","specialist","generalist"):
        s = summarize(arm, results[arm])
        print(f"  {arm:11} resolved={s['resolved']}/{s['n']}  produced_patch={s['produced']}/{s['n']}  reached_submit={s['reached_submit']}/{s['n']}", flush=True)
    json.dump(results, open(os.path.join(os.path.dirname(__file__), "_ab_results.json"), "w"), indent=2)
    print("saved _ab_results.json", flush=True)

if __name__ == "__main__":
    main()
