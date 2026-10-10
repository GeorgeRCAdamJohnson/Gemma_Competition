"""Fast A/B eval over the running llama-server (12B GGUF + fastapi_specialist_12b LoRA).

Toggles the adapter scale at runtime (POST /lora-adapters) so BASE (scale 0.0) and
SPECIALIST (scale 1.0) run against the SAME loaded model process - no reload, ~64 tok/s.

Pre-registered (rule 2):
  held-out = 6 fastapi tasks never trained on
  metrics  = produced (non-empty diff), reached_submit, resolved (hidden test_patch pytest)
  null     = E2B specialist produced 0/6
  BAR      = 12B specialist produced >= 1/6 AND >= 12B base produced
             (capacity hypothesis: 12B has the capacity E2B lacked to emit APPLYING edits)

Usage:
  python eval_server_ab.py                 # runs both arms (base then specialist)
  python eval_server_ab.py --arms base     # one arm
"""
import argparse, json, os, sys, time, urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "local_eval"))
import run_local as R

SERVER = "http://127.0.0.1:8081"
MODEL = "gpt"  # llama-server ignores the id; any string works
HELD = ["fastapi_15588", "fastapi_14458", "fastapi_14479", "fastapi_5624", "fastapi_14873", "fastapi_15763"]
MAX_TOOL_CALLS = 20


def set_lora_scale(scale):
    """Set adapter id 0 to the given scale (0.0 = base/off, 1.0 = specialist/on)."""
    body = json.dumps([{"id": 0, "scale": float(scale)}]).encode()
    req = urllib.request.Request(SERVER + "/lora-adapters", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()
    # verify
    with urllib.request.urlopen(SERVER + "/lora-adapters", timeout=30) as r:
        got = json.loads(r.read())
    return got


def run_arm(arm, scale):
    print(f"\n=== ARM {arm} (lora scale={scale}) ===", flush=True)
    state = set_lora_scale(scale)
    print(f"  adapters now: {[{'id':a['id'],'scale':a['scale']} for a in state]}", flush=True)
    R.TEMPERATURE = 0.0
    R.MAX_TOKENS = 2048
    R.QUIET = True
    rows = []
    for tid in HELD:
        task = R.load_task(tid)
        R.set_repo(task["repo"].split("/")[-1])
        t0 = time.time()
        diff, calls, dur, submitted = R.run_agent(task, MODEL, MAX_TOOL_CALLS)
        produced = bool(diff.strip())
        resolved = False
        if produced:
            try:
                resolved, _ = R.verify(task, diff)
            except Exception as e:
                print(f"    verify err {tid}: {e}", flush=True)
        rows.append(dict(task=tid, resolved=bool(resolved), produced=produced,
                         reached_submit=bool(submitted), calls=calls, chars=len(diff),
                         secs=round(time.time() - t0, 1)))
        print(f"  [{arm}] {tid:14} resolved={resolved} produced={produced} "
              f"submit={submitted} calls={calls} chars={len(diff)} {rows[-1]['secs']}s", flush=True)
    outp = os.path.join(os.path.dirname(__file__), f"_ab12b_{arm}.json")
    json.dump(rows, open(outp, "w"), indent=2)
    r = sum(x["resolved"] for x in rows)
    p = sum(x["produced"] for x in rows)
    s = sum(x["reached_submit"] for x in rows)
    print(f"[{arm}] resolved={r}/6 produced={p}/6 reached_submit={s}/6 -> {outp}", flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="+", default=["base", "specialist"],
                    choices=["base", "specialist"])
    args = ap.parse_args()
    scales = {"base": 0.0, "specialist": 1.0}
    summary = {}
    for arm in args.arms:
        rows = run_arm(arm, scales[arm])
        summary[arm] = dict(
            produced=sum(x["produced"] for x in rows),
            reached_submit=sum(x["reached_submit"] for x in rows),
            resolved=sum(x["resolved"] for x in rows),
        )
    print("\n=== A/B SUMMARY (12B, 6 held-out fastapi) ===", flush=True)
    for arm, s in summary.items():
        print(f"  {arm:11} produced={s['produced']}/6 submit={s['reached_submit']}/6 resolved={s['resolved']}/6", flush=True)
    if "base" in summary and "specialist" in summary:
        bp, spd = summary["base"]["produced"], summary["specialist"]["produced"]
        print(f"\nCAPACITY BAR: specialist produced {spd}/6 vs base {bp}/6 vs E2B-specialist 0/6", flush=True)
        verdict = "PASS" if (spd >= 1 and spd >= bp) else "FAIL"
        print(f"VERDICT (pre-registered): {verdict}", flush=True)


if __name__ == "__main__":
    main()
