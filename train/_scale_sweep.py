"""Decisive falsifier: is the specialist's argument-collapse an OVER-STRENGTH problem?
Sweep adapter scale and measure (a) produced, (b) whether the `1`-collapse / malformed-arg
degeneration appears. If a mid scale restores fidelity -> over-strength (scalable fix).
If NO scale recovers -> baked into weights -> data/training problem.

Floor: scale=0 is base. We watch argument fidelity in the RAW tool-call args, not just produced.
"""
import json, os, sys, re, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "local_eval"))
import run_local as R

SERVER = "http://127.0.0.1:8081"
LOG = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_scale_sweep.log", "w", encoding="utf-8")
def p(*a): print(*a, file=LOG, flush=True)

def set_scale(s):
    body = json.dumps([{"id": 0, "scale": float(s)}]).encode()
    req = urllib.request.Request(SERVER + "/lora-adapters", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req, timeout=30).read()

SCALES = [0.0, 0.25, 0.5, 0.75, 1.0]
TASKS = ["fastapi_14479", "fastapi_15588"]
R.TEMPERATURE = 0.0
R.MAX_TOKENS = 2048
MAX_CALLS = 14

def is_degenerate_arg(raw):
    """True if the tool-call argument shows the collapse signature (bare int, non-str query/path)."""
    try:
        a = json.loads(raw or "{}")
    except Exception:
        return True  # unparseable args = degenerate
    for k in ("query", "path", "old_string", "new_string", "command"):
        if k in a and not isinstance(a[k], str):
            return True
    return False

def run(task_obj, scale):
    set_scale(scale)
    R.reset_repo(task_obj["base_commit"])
    msgs = [
        {"role": "system", "content": R.SYSTEM_PROMPT},
        {"role": "user", "content": f"Repository: {task_obj['repo']}\n\nProblem:\n{task_obj['problem_statement'][:4000]}\n\nFix the bug. Locate fast, edit, submit_patch."},
    ]
    calls = 0; degen = 0; length_overflows = 0; made_edit = False; strikes = 0; submitted = False
    for turn in range(MAX_CALLS):
        try:
            resp = R.chat(msgs, "gpt")
        except Exception as e:
            p(f"      chat err: {e}"); break
        m = resp["choices"][0]["message"]; msgs.append(m)
        tcs = m.get("tool_calls") or []
        if resp["choices"][0].get("finish_reason") == "length":
            length_overflows += 1
        if not tcs:
            strikes += 1
            if strikes >= 4: break
            msgs.append({"role":"user","content":"You have NOT made a tool call. Call edit_file now or submit_patch. You MUST call a tool."})
            continue
        strikes = 0
        for tc in tcs:
            calls += 1
            fn = tc["function"]["name"]; raw = tc["function"].get("arguments")
            if is_degenerate_arg(raw):
                degen += 1
            try: args = json.loads(raw or "{}")
            except Exception: args = {}
            try:
                if fn == "submit_patch": res = {"status":"ok","submitted":True}; submitted = True
                elif fn == "read_file": res = R.tool_read_file(**args)
                elif fn == "search_code": res = R.tool_search_code(**args)
                elif fn == "edit_file":
                    res = R.tool_edit_file(**args)
                    if res.get("status") == "ok": made_edit = True
                elif fn == "run_command": res = R.tool_run_command(**args)
                else: res = {"status":"error","error":f"unknown {fn}"}
            except Exception as e:
                res = {"status":"error","error":f"{type(e).__name__}: {e}"}
            msgs.append({"role":"tool","tool_call_id":tc.get("id",str(calls)),"content":json.dumps(res)[:3000]})
            if submitted: break
        if submitted: break
    diff = R.git(["diff", task_obj["base_commit"]]).stdout
    produced = bool(diff.strip())
    return dict(scale=scale, calls=calls, degen_args=degen, length_overflows=length_overflows,
                made_edit=made_edit, produced=produced, chars=len(diff))

for t in TASKS:
    to = R.load_task(t); R.set_repo(to["repo"].split("/")[-1])
    p(f"\n{'='*60}\n{t}\n{'='*60}")
    p(f"{'scale':>6} {'calls':>6} {'degen':>6} {'len_of':>7} {'edit':>5} {'produced':>9} {'chars':>6}")
    for s in SCALES:
        r = run(to, s)
        p(f"{r['scale']:>6} {r['calls']:>6} {r['degen_args']:>6} {r['length_overflows']:>7} "
          f"{str(r['made_edit']):>5} {str(r['produced']):>9} {r['chars']:>6}")
LOG.close()
print("done")
