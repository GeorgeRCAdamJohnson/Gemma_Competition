"""Investigate the specialist null: dump RAW generations for base vs specialist on one task,
every turn, so we see exactly what the specialist emits that fails to parse/act.
Task fastapi_14458: base produced+submitted (calls=5); specialist did not (calls=5). Same task,
opposite outcome -> compare the actual text."""
import warnings, json, sys, os
warnings.filterwarnings("ignore")
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "local_eval"))
import run_local as R
from gemma4_toolparse import parse_tool_calls

BASE="google/gemma-4-E2B-it"
TASK="fastapi_14458"
SPEC=os.path.join(os.path.dirname(__file__),"adapters","fastapi_specialist")

tok=AutoTokenizer.from_pretrained(BASE)
bnb=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type="nf4",bnb_4bit_compute_dtype=torch.bfloat16,bnb_4bit_use_double_quant=True)
base=AutoModelForCausalLM.from_pretrained(BASE,quantization_config=bnb,device_map={"":0},attn_implementation="eager").eval()

def gen_once(model, label):
    """Run ONE agent turn-sequence manually, printing raw gen each turn, up to 6 turns."""
    task=R.load_task(TASK); R.set_repo(task["repo"].split("/")[-1]); R.reset_repo(task["base_commit"])
    msgs=[{"role":"system","content":R.SYSTEM_PROMPT},
          {"role":"user","content":f"Repository: {task['repo']}\n\nProblem:\n{task['problem_statement'][:4000]}\n\nFix the bug. Locate fast, edit, submit_patch."}]
    print(f"\n########## {label} on {TASK} ##########")
    for turn in range(6):
        rm=[]
        for mm in msgs:
            if mm.get("tool_calls"):
                mm=dict(mm); mm["tool_calls"]=[{**tc,"function":{**tc["function"],"arguments":(json.loads(tc["function"]["arguments"]) if isinstance(tc["function"].get("arguments"),str) else tc["function"].get("arguments",{}))}} for tc in mm["tool_calls"]]
            rm.append(mm)
        prompt=tok.apply_chat_template(rm,tools=R.TOOLS,add_generation_prompt=True,tokenize=False)
        enc=tok(prompt,return_tensors="pt",truncation=True,max_length=8192).to("cuda")
        with torch.no_grad():
            out=model.generate(**enc,max_new_tokens=400,do_sample=False,pad_token_id=tok.eos_token_id)
        gen=tok.decode(out[0][enc["input_ids"].shape[1]:],skip_special_tokens=True)
        tcs=parse_tool_calls(gen)
        print(f"\n--- turn {turn} | parsed {len(tcs)} tool_calls ---")
        print("RAW GEN:", repr(gen[:500]))
        if not tcs:
            print(">>> NO PARSEABLE TOOL CALL (this is the failure point)")
            msgs.append({"role":"assistant","content":gen})
            msgs.append({"role":"user","content":"You have NOT made a tool call. Call a tool now."})
            continue
        # execute first tool call to advance state
        tc=tcs[0]; fn=tc["function"]["name"]; args=json.loads(tc["function"]["arguments"])
        print(f">>> would exec: {fn}({ {k:str(v)[:40] for k,v in args.items()} })")
        msgs.append({"role":"assistant","content":"","tool_calls":[tc]})
        try:
            if fn=="submit_patch": res={"status":"ok","submitted":True}; print(">>> SUBMIT reached"); 
            elif fn=="read_file": res=R.tool_read_file(**args)
            elif fn=="search_code": res=R.tool_search_code(**args)
            elif fn=="edit_file": res=R.tool_edit_file(**args)
            elif fn=="run_command": res=R.tool_run_command(**args)
            else: res={"status":"error","error":"unknown"}
        except Exception as e:
            res={"status":"error","error":str(e)}
        msgs.append({"role":"tool","tool_call_id":tc.get("id","0"),"content":json.dumps(res)[:1500]})
        if fn=="submit_patch": break

gen_once(base,"BASE")
spec=PeftModel.from_pretrained(base,SPEC); spec.eval()
gen_once(spec,"SPECIALIST")
