"""v2 ablation sweep on rich held-out: adapters r8 (id0) and r8_long (id1) at scales {0,0.25,1.0}.
scale=0 on BOTH = base. Tracks degen (collapsed-arg count) + produced + reached_submit.

Pre-registered bars:
 1. r8 degen=0 at scale 1.0  -> strength fix (r16 collapsed: degen 9/3)
 2. some (adapter,scale) degen=0 AND produced > base produced -> capitalize on fix-knowledge
 3. r8_long > r8 on produced at matched scale -> arg-length lever matters
"""
import json, os, sys, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "local_eval"))
import run_local as R

SERVER = "http://127.0.0.1:8081"
LOG = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_sweep_v2.log", "w", encoding="utf-8")
def p(*a): print(*a, file=LOG, flush=True)

RICH_HELD = ["rich_3718","rich_3934","rich_3953","rich_3944","rich_3942",
             "rich_3938","rich_3882","rich_3894","rich_3935","rich_3930"]
ADAPTERS = {"r8": 0, "r8_long": 1}
R.TEMPERATURE = 0.0; R.MAX_TOKENS = 2048; R.QUIET = True
MAX_CALLS = 16

def set_scales(active_id, scale):
    """Set active_id to `scale`, all others to 0. active_id=None => all 0 (base)."""
    body = [{"id": i, "scale": (float(scale) if i == active_id else 0.0)} for i in ADAPTERS.values()]
    req = urllib.request.Request(SERVER + "/lora-adapters", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req, timeout=30).read()

def is_degen(raw):
    try: a = json.loads(raw or "{}")
    except Exception: return True
    for k in ("query","path","old_string","new_string","command"):
        if k in a and not isinstance(a[k], str): return True
    return False

def run_task(task_obj):
    R.reset_repo(task_obj["base_commit"])
    msgs = [{"role":"system","content":R.SYSTEM_PROMPT},
            {"role":"user","content":f"Repository: {task_obj['repo']}\n\nProblem:\n{task_obj['problem_statement'][:4000]}\n\nFix the bug. Locate fast, edit, submit_patch."}]
    calls=0; degen=0; made_edit=False; strikes=0; submitted=False
    for _ in range(MAX_CALLS):
        try: resp = R.chat(msgs, "gpt")
        except Exception: break
        m = resp["choices"][0]["message"]; msgs.append(m)
        tcs = m.get("tool_calls") or []
        if not tcs:
            strikes += 1
            if strikes >= 4: break
            msgs.append({"role":"user","content":"You have NOT made a tool call. Call edit_file now or submit_patch. You MUST call a tool."}); continue
        strikes=0
        for tc in tcs:
            calls += 1; fn = tc["function"]["name"]; raw = tc["function"].get("arguments")
            if is_degen(raw): degen += 1
            try: args = json.loads(raw or "{}")
            except Exception: args = {}
            try:
                if fn=="submit_patch": res={"status":"ok","submitted":True}; submitted=True
                elif fn=="read_file": res=R.tool_read_file(**args)
                elif fn=="search_code": res=R.tool_search_code(**args)
                elif fn=="edit_file":
                    res=R.tool_edit_file(**args)
                    if res.get("status")=="ok": made_edit=True
                elif fn=="run_command": res=R.tool_run_command(**args)
                else: res={"status":"error","error":f"unknown {fn}"}
            except Exception as e: res={"status":"error","error":f"{type(e).__name__}: {e}"}
            msgs.append({"role":"tool","tool_call_id":tc.get("id",str(calls)),"content":json.dumps(res)[:3000]})
            if submitted: break
        if submitted: break
    diff = R.git(["diff", task_obj["base_commit"]]).stdout
    return dict(calls=calls, degen=degen, made_edit=made_edit, produced=bool(diff.strip()),
                submit=submitted, chars=len(diff))

def arm(label, active_id, scale):
    set_scales(active_id, scale)
    rows=[]
    for tid in RICH_HELD:
        to = R.load_task(tid); R.set_repo(to["repo"].split("/")[-1])
        r = run_task(to); r["task"]=tid; rows.append(r)
        p(f"  [{label}] {tid:11} degen={r['degen']} edit={r['made_edit']} produced={r['produced']} submit={r['submit']} calls={r['calls']}")
    prod=sum(x["produced"] for x in rows); dg=sum(x["degen"] for x in rows); ed=sum(x["made_edit"] for x in rows)
    p(f"[{label}] produced={prod}/{len(rows)} total_degen={dg} made_edit={ed}/{len(rows)}")
    json.dump(rows, open(os.path.join(os.path.dirname(__file__), f"_sweepv2_{label}.json"),"w"), indent=2)
    return dict(produced=prod, degen=dg, made_edit=ed)

RUNS = [("base", None, 0.0),
        ("r8@0.25", 0, 0.25), ("r8@1.0", 0, 1.0),
        ("r8long@0.25", 1, 0.25), ("r8long@1.0", 1, 1.0)]
summ={}
for label, aid, sc in RUNS:
    p(f"\n=== {label} ===")
    summ[label] = arm(label, aid, sc)
p("\n=== V2 SWEEP SUMMARY (rich held-out, n=%d) ===" % len(RICH_HELD))
for k,v in summ.items():
    p(f"  {k:14} produced={v['produced']} made_edit={v['made_edit']} total_degen={v['degen']}")
LOG.close(); print("done")
