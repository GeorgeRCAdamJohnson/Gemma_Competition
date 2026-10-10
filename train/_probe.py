import json, time, urllib.request

BASE = "http://127.0.0.1:8081"

def get(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        return json.loads(r.read())

def post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read())

out = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_probe.log", "w", encoding="utf-8")
def p(*a): print(*a, file=out, flush=True)

# 1. Is a LoRA adapter registered?
try:
    la = get("/lora-adapters")
    p("LORA-ADAPTERS:", json.dumps(la))
except Exception as e:
    p("lora-adapters err:", e)

# 2. Generation + throughput, adapter at full scale (default scale from --lora is 1.0)
msg = [{"role": "user", "content": "Write a Python function that adds two numbers. Code only."}]
t0 = time.time()
r = post("/v1/chat/completions", {"messages": msg, "max_tokens": 150, "temperature": 0})
dt = time.time() - t0
ct = r.get("usage", {}).get("completion_tokens", 0)
p(f"GEN seconds={dt:.1f} completion_tokens={ct} tok/s={ct/dt:.1f}")
p("CONTENT:")
p(r["choices"][0]["message"]["content"])
out.close()
