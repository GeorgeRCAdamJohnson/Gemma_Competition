"""Prove the EVAL PATH: train -> load adapter -> run the agent loop -> score, all in-process via HF.
No server, no GGUF conversion. Monkeypatches run_local.chat() to generate from a HF Gemma-4 base
(optionally + LoRA adapter) and parse Gemma-4 tool-calls into the OpenAI shape the harness expects.

Purpose: confirm the FULL train->eval cycle works end-to-end. E2B is tiny/weak at tool-calling, so a
no-resolve result is ACCEPTABLE here - we are testing PLUMBING, not resolve rate.

Usage:
  python eval_hf_adapter.py --task rich_4077               # base only
  python eval_hf_adapter.py --task rich_4077 --adapter train/_smoke_adapter_g4e2b
"""
import warnings, json, re, sys, argparse, time, os
warnings.filterwarnings("ignore")
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

sys.path.insert(0, os.path.dirname(__file__))  # for gemma4_toolparse
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "local_eval"))
import run_local as R

BASE = "google/gemma-4-E2B-it"

def load(base, adapter=None):
    tok = AutoTokenizer.from_pretrained(base)
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    print(f"[{time.strftime('%H:%M:%S')}] loading 4-bit base {base} ...")
    model = AutoModelForCausalLM.from_pretrained(base, quantization_config=bnb, device_map={"": 0},
                                                 attn_implementation="eager")
    if adapter:
        from peft import PeftModel
        print(f"  attaching adapter {adapter}")
        model = PeftModel.from_pretrained(model, adapter)
    model.eval()
    return tok, model

from gemma4_toolparse import parse_tool_calls  # torch-free, unit-tested gemma4 dialect parser

def make_chat(tok, model):
    def chat(messages, model_name):
        # HF chat template wants tool_calls[].function.arguments as a DICT, not a JSON string
        # (run_local stores OpenAI-style JSON strings). Normalize a copy before rendering.
        render_msgs = []
        for mm in messages:
            if mm.get("tool_calls"):
                mm = dict(mm)
                mm["tool_calls"] = [
                    {**tc, "function": {**tc["function"],
                        "arguments": (json.loads(tc["function"]["arguments"])
                                      if isinstance(tc["function"].get("arguments"), str)
                                      else tc["function"].get("arguments", {}))}}
                    for tc in mm["tool_calls"]
                ]
            render_msgs.append(mm)
        # render with the model's chat template + our tool schema described in the system text
        prompt = tok.apply_chat_template(render_msgs, tools=R.TOOLS, add_generation_prompt=True, tokenize=False)
        enc = tok(prompt, return_tensors="pt", truncation=True, max_length=8192).to("cuda")
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=R.MAX_TOKENS, do_sample=(R.TEMPERATURE>0),
                                  temperature=max(R.TEMPERATURE,1e-5), top_p=0.95,
                                  pad_token_id=tok.eos_token_id)
        gen = tok.decode(out[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        tcs = parse_tool_calls(gen)
        msg = {"role": "assistant", "content": gen if not tcs else ""}
        if tcs: msg["tool_calls"] = tcs
        return {"choices": [{"message": msg, "finish_reason": "tool_calls" if tcs else "stop"}]}
    return chat

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", default="rich_4077")
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--max-tool-calls", type=int, default=15)
    ap.add_argument("--temp", type=float, default=0.0)
    args = ap.parse_args()
    R.TEMPERATURE = args.temp; R.MAX_TOKENS = 1024
    tok, model = load(BASE, args.adapter)
    R.chat = make_chat(tok, model)  # monkeypatch the harness's model call
    task = R.load_task(args.task); R.set_repo(task["repo"].split("/")[-1])
    print(f"[{time.strftime('%H:%M:%S')}] running agent on {args.task} (adapter={args.adapter})")
    diff, calls, dur, submitted = R.run_agent(task, "hf", args.max_tool_calls)
    print(f"agent: calls={calls} dur={dur:.0f}s submitted={submitted} patch_chars={len(diff)}")
    if not diff.strip():
        print("EVAL PATH PROVED (loop ran); RESULT: no patch (fine for a plumbing test)"); return
    passed, log = R.verify(task, diff)
    print(f"EVAL PATH PROVED (loop ran). VERDICT: {'RESOLVED' if passed else 'not resolved'}")

if __name__ == "__main__":
    main()
