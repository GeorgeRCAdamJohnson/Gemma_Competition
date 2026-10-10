"""Investigate WHY the specialist kills `produced`. Read the RAW generations, don't count.

For each failure-type task, run base (scale 0) and specialist (scale 1) and dump the FULL
raw assistant text of every turn + whether a tool call was parsed. The question: when the
adapter is on, what does the model emit instead of a valid edit_file tool call?
"""
import json, os, sys, time, urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "local_eval"))
import run_local as R

SERVER = "http://127.0.0.1:8081"
LOG = open(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\train\_diag_specialist.log", "w", encoding="utf-8")
def p(*a):
    print(*a, file=LOG, flush=True)

def set_scale(s):
    body = json.dumps([{"id": 0, "scale": float(s)}]).encode()
    req = urllib.request.Request(SERVER + "/lora-adapters", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req, timeout=30).read()

# representative failure types:
#  14479 = base PRODUCED here, specialist did NOT (the cleanest "what did the adapter break")
#  15763 = specialist submitted EMPTY (degenerate submit)
#  14873 = specialist early-stopped in 3 calls
TASKS = ["fastapi_14479", "fastapi_15763"]
R.TEMPERATURE = 0.0
R.MAX_TOKENS = 2048

def run_traced(task, arm, scale, max_calls=12):
    set_scale(scale)
    p(f"\n{'='*70}\n{task}  ARM={arm}  scale={scale}\n{'='*70}")
    R.reset_repo(task_obj["base_commit"])
    msgs = [
        {"role": "system", "content": R.SYSTEM_PROMPT},
        {"role": "user", "content": f"Repository: {task_obj['repo']}\n\nProblem:\n{task_obj['problem_statement'][:4000]}\n\nFix the bug. Locate fast, edit, submit_patch."},
    ]
    calls = 0
    for turn in range(max_calls):
        resp = R.chat(msgs, "gpt")
        m = resp["choices"][0]["message"]
        msgs.append(m)
        tcs = m.get("tool_calls") or []
        fr = resp["choices"][0].get("finish_reason")
        content = (m.get("content") or "").strip()
        p(f"\n--- turn {turn} finish_reason={fr} n_tool_calls={len(tcs)} ---")
        if content:
            p(f"  TEXT ({len(content)} chars): {content[:600]!r}")
        if tcs:
            for tc in tcs:
                fn = tc["function"]["name"]
                raw = tc["function"].get("arguments")
                p(f"  TOOLCALL {fn}  args_raw={str(raw)[:300]!r}")
        if not tcs:
            # feed the same nudge the real loop uses, but only twice, to see if it recovers
            if turn >= 3:
                p("  [would stop: repeated no-tool]")
                break
            msgs.append({"role": "user", "content": "You have NOT made a tool call. Call edit_file now or submit_patch. You MUST call a tool."})
            continue
        # execute tools so the loop can proceed realistically
        stop = False
        for tc in tcs:
            calls += 1
            fn = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except Exception:
                args = {}
            try:
                if fn == "submit_patch":
                    res = {"status": "ok", "submitted": True}; stop = True
                elif fn == "read_file":
                    res = R.tool_read_file(**args)
                elif fn == "search_code":
                    res = R.tool_search_code(**args)
                elif fn == "edit_file":
                    res = R.tool_edit_file(**args)
                elif fn == "run_command":
                    res = R.tool_run_command(**args)
                else:
                    res = {"status": "error", "error": f"unknown {fn}"}
            except Exception as e:
                res = {"status": "error", "error": f"{type(e).__name__}: {e}"}
            p(f"    -> result: {json.dumps(res)[:300]}")
            msgs.append({"role": "tool", "tool_call_id": tc.get("id", str(calls)), "content": json.dumps(res)[:3000]})
        if stop:
            break
    diff = R.git(["diff", task_obj["base_commit"]]).stdout
    p(f"\n  >>> produced={bool(diff.strip())} diff_chars={len(diff)}")

for t in TASKS:
    task_obj = R.load_task(t)
    R.set_repo(task_obj["repo"].split("/")[-1])
    run_traced(t, "base", 0.0)
    run_traced(t, "specialist", 1.0)

LOG.close()
print("done")
