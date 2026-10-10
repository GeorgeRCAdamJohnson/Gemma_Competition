"""Decisive: our-base-GGUF + --lora (r16) on the SAME fastapi_14479 prompt. Compare to HF ground truth
(which gave a valid call:read_file{path:...,start_line:480}, no `1`-collapse). If our-base GGUF is clean
-> base-mismatch (Ollama blob) was the whole problem, fast path validated. If still collapses -> runtime
--lora-over-quantized-base numerics are the culprit."""
import json, os, sys, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "local_eval"))
import run_local as R
OUT = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_ourbase_probe.log","w",encoding="utf-8")
def p(*a): print(*a, file=OUT, flush=True)

task = R.load_task("fastapi_14479")
user = f"Repository: {task['repo']}\n\nProblem:\n{task['problem_statement'][:3500]}\n\nFix the bug. Locate fast, edit, submit_patch."
body = {"messages":[{"role":"system","content":R.SYSTEM_PROMPT},{"role":"user","content":user}],
        "tools":R.TOOLS,"temperature":0,"max_tokens":400,"stream":False}
req = urllib.request.Request("http://127.0.0.1:8081/v1/chat/completions",
     data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
r = json.loads(urllib.request.urlopen(req, timeout=180).read())
m = r["choices"][0]["message"]
tcs = m.get("tool_calls") or []
content = (m.get("content") or "")
p("finish_reason: " + str(r["choices"][0].get("finish_reason")))
p("n_tool_calls: " + str(len(tcs)))
for tc in tcs:
    p("  TOOLCALL " + tc["function"]["name"] + "  args=" + str(tc["function"].get("arguments"))[:300])
blob = json.dumps(tcs) + content
ones = blob.count(':1}') + blob.count(':1,') + blob.count('"1"') + blob.count('query":1') + blob.count('path":1') + blob.count('query:1') + blob.count('path:1')
p("`1`-collapse markers: " + str(ones))
if content.strip():
    p("CONTENT: " + content[:600])
OUT.close(); print("done")
