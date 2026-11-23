# Runs ON the Colab VM as a detached background process next to a gpu_ab_run.py driver. Every INTERVAL seconds it
# writes MyDrive/gemma_fasteval/ab_runs/<tag>/live_status.json and live_status.txt: finished tasks and solves per
# arm/round (from the pass result folders as tasks complete), driver alive, the log tail, and vLLM load and decode
# speed from /metrics. Read-only on the run; exits when the driver's ALL_DONE appears or the driver is gone.
#   nohup /content/venv/bin/python /content/live_status.py <tag> > /content/live_status.log 2>&1 &
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

TAG = sys.argv[1]
INTERVAL = int(sys.argv[2]) if len(sys.argv) > 2 else 120
RATE = float(sys.argv[3]) if len(sys.argv) > 3 else None      # entered CU/h, for outcome.json
STARTED = float(sys.argv[4]) if len(sys.argv) > 4 else None   # epoch seconds the notebook started the job
OUT = Path("/content/ab")
DRIVE = Path("/content/drive/MyDrive/gemma_fasteval/ab_runs") / TAG
LOG = Path("/content/ab.log")
PID = Path("/content/ab.pid")


def metrics():
    try:
        text = urllib.request.urlopen("http://127.0.0.1:8000/metrics", timeout=10).read().decode()
    except Exception as e:  # noqa: BLE001
        return {"error": type(e).__name__}
    get = lambda k: sum(float(x) for x in re.findall(rf"^{k}(?:{{[^}}]*}})? ([0-9.e+]+)$", text, re.M))
    return {"running": get("vllm:num_requests_running"), "waiting": get("vllm:num_requests_waiting"),
            "gen_tokens_total": get("vllm:generation_tokens_total")}


def pass_progress(folder):
    """Finished tasks = traces written; solves from any per-task result json/jsonl that records `resolved`."""
    traces = list(folder.rglob("trace_*.json"))
    solved, seen = 0, set()
    for f in list(folder.rglob("*.jsonl")) + [p for p in folder.rglob("*.json") if not p.name.startswith("trace_")]:
        try:
            lines = f.read_text(errors="replace").splitlines() if f.suffix == ".jsonl" else [f.read_text(errors="replace")]
            for line in lines:
                row = json.loads(line) if line.strip().startswith("{") else None
                for r in (row.get("results") if isinstance(row, dict) and isinstance(row.get("results"), list) else [row]):
                    if isinstance(r, dict) and "resolved" in r:
                        key = r.get("instance_id") or r.get("id") or r.get("task_id") or id(r)
                        if key not in seen:
                            seen.add(key)
                            solved += bool(r["resolved"])
        except Exception:  # noqa: BLE001
            continue
    newest = max((t.stat().st_mtime for t in traces), default=0)
    return {"finished": len(traces), "solved_so_far": solved if seen else None,
            "newest_trace": time.strftime("%H:%M:%S", time.gmtime(newest)) if newest else None}


prev = None
while True:
    now = time.time()
    m = metrics()
    if prev and "gen_tokens_total" in m and "gen_tokens_total" in prev[1]:
        dt = now - prev[0]
        rate = (m["gen_tokens_total"] - prev[1]["gen_tokens_total"]) / dt
        m["gen_tok_per_s"] = round(rate, 1)
        m["per_sequence_tok_per_s"] = round(rate / max(m["running"], 1), 1)
    prev = (now, m)
    arms = {}
    if OUT.is_dir():
        for arm in sorted(p for p in OUT.iterdir() if p.is_dir()):
            for rnd in sorted(p for p in arm.iterdir() if p.is_dir() and p.name.startswith("round_")):
                arms[f"{arm.name}/{rnd.name}"] = pass_progress(rnd)
    alive = PID.exists() and Path(f"/proc/{PID.read_text().strip()}").exists()
    status = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "driver_alive": alive,
              "all_done": (OUT / "ALL_DONE").exists(), "passes": arms, "vllm": m,
              "log_tail": LOG.read_text(errors="replace").splitlines()[-5:] if LOG.exists() else []}
    lines = [f"{status['utc']}  driver alive {alive}  ALL_DONE {status['all_done']}"]
    lines += [f"  {k:28s} finished {v['finished']:3d}/85  solved so far {v['solved_so_far']}  newest {v['newest_trace']}"
              for k, v in arms.items()]
    lines += [f"  vLLM {json.dumps(m)}"] + [f"  log: {l}" for l in status["log_tail"]]
    DRIVE.mkdir(parents=True, exist_ok=True)
    for name, text in (("live_status.json", json.dumps(status, indent=1)), ("live_status.txt", "\n".join(lines) + "\n")):
        tmp = DRIVE / (name + ".tmp")
        tmp.write_text(text)
        tmp.replace(DRIVE / name)
    # prep runs before the driver exists; stop only after a driver that existed has exited
    if status["all_done"] or (PID.exists() and not alive):
        break
    time.sleep(INTERVAL)

# the run is over: outcome.json (the notebook no longer blocks on a monitor loop to write it)
prog = OUT / "progress.json"
outcome = {"status": "all_done" if (OUT / "ALL_DONE").exists() else "driver_exited_without_all_done",
           "all_done": (OUT / "ALL_DONE").read_text() if (OUT / "ALL_DONE").exists() else None,
           "passes": len(json.loads(prog.read_text())["passes"]) if prog.exists() else 0}
if STARTED:
    outcome["elapsed_seconds"] = round(time.time() - STARTED)
    if RATE:
        outcome["estimated_cu_at_entered_rate"] = round(outcome["elapsed_seconds"] * RATE / 3600, 2)
(DRIVE / "outcome.json").write_text(json.dumps(outcome, indent=2) + "\n")
print("OUTCOME", outcome, flush=True)
