"""Eval ONE arm (RULE B: one model per process = clean 16GB, parallelizable, resumable).
Runs base OR a single adapter over the 6 held-out FastAPI tasks, writes _ab_<arm>.json.
Run three times (base / specialist / generalist) - each gets a fresh full-VRAM process.

Usage:
  python eval_arm.py --arm base
  python eval_arm.py --arm specialist --adapter adapters/fastapi_specialist_traj
  python eval_arm.py --arm generalist --adapter adapters/generalist_traj
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", required=True)
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--base", default=BASE, help="base model (match the adapter's base)")
    args = ap.parse_args()
    R.TEMPERATURE = 0.0; R.MAX_TOKENS = 1024
    base_model = args.base
    tok = AutoTokenizer.from_pretrained(base_model)
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(base_model, quantization_config=bnb, device_map={"":0}, attn_implementation="eager")
    if args.adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, os.path.join(os.path.dirname(__file__), args.adapter))
    model.eval()
    R.chat = make_chat(tok, model)
    rows = []
    for tid in HELD:
        task = R.load_task(tid); R.set_repo(task["repo"].split("/")[-1])
        diff, calls, dur, submitted = R.run_agent(task, "hf", 15)
        produced = bool(diff.strip()); resolved = False
        if produced:
            try: resolved, _ = R.verify(task, diff)
            except Exception: pass
        rows.append(dict(task=tid, resolved=bool(resolved), produced=produced,
                         reached_submit=bool(submitted), calls=calls, chars=len(diff)))
        print(f"  [{args.arm}] {tid:14} resolved={resolved} produced={produced} submit={submitted} calls={calls} chars={len(diff)}", flush=True)
    outp = os.path.join(os.path.dirname(__file__), f"_ab_{args.arm}.json")
    json.dump(rows, open(outp, "w"), indent=2)
    r = sum(x["resolved"] for x in rows); p = sum(x["produced"] for x in rows); s = sum(x["reached_submit"] for x in rows)
    print(f"\n[{args.arm}] resolved={r}/6 produced={p}/6 reached_submit={s}/6 -> {outp}", flush=True)

if __name__ == "__main__":
    main()
