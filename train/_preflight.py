import json, os, sys, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "local_eval"))
import run_local as R

SERVER = "http://127.0.0.1:8081"
out = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_preflight.log", "w", encoding="utf-8")
def p(*a): print(*a, file=out, flush=True)

def post_scale(s):
    body = json.dumps([{"id": 0, "scale": float(s)}]).encode()
    req = urllib.request.Request(SERVER + "/lora-adapters", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req, timeout=30).read()
    g = json.loads(urllib.request.urlopen(SERVER + "/lora-adapters", timeout=30).read())
    return [(a["id"], a["scale"]) for a in g]

# 1. scale swap works?
p("scale->0.0:", post_scale(0.0))
p("scale->1.0:", post_scale(1.0))

# 2. held-out tasks load + repo present?
HELD = ["fastapi_15588","fastapi_14458","fastapi_14479","fastapi_5624","fastapi_14873","fastapi_15763"]
for tid in HELD:
    try:
        t = R.load_task(tid)
        p(f"  {tid}: repo={t['repo']} base={t['base_commit'][:10]} prob_len={len(t['problem_statement'])}")
    except Exception as e:
        p(f"  {tid}: LOAD ERR {e}")

# 3. repo checkout path
R.set_repo("fastapi")
p("REPO path:", str(R.REPO), "exists:", R.REPO.exists())
# can we reach a base commit?
t = R.load_task("fastapi_15588")
rr = R.git(["cat-file", "-t", t["base_commit"]])
p("base commit reachable:", rr.stdout.strip(), rr.stderr.strip()[:120])
out.close()
