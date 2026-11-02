"""M1 batch v2: router_v3 x 3 reps (21 runs). ctrl data is REUSED from batch1 m1_batch/ctrl/*
(agent_ctrl is byte-identical; same image, same server, same day). Resume-safe per rep."""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
COHORT = ["rich_3006", "rich_3454", "rich_3518", "rich_3905", "rich_4077", "rich_3777", "rich_3882"]
REPS = 3
BASE = "C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE"
ARM_DIR = "agent_router_v3"


def run_one(rep):
    out = RIG / "m1_batch_v3" / "router_v3" / f"r{rep}"
    out.mkdir(parents=True, exist_ok=True)
    if (out / "summary.json").exists():
        print(f"[skip] router_v3 r{rep} already done", flush=True)
        return
    cmd = [
        "docker", "run", "--rm", "--add-host=host.docker.internal:host-gateway",
        "-v", f"{BASE}/Gemma/local_eval/parity_rig:/rig",
        "-v", f"{BASE}/Gemma/harness_src/x:/x",
        "-v", f"{BASE}/Gemma/comp_files:/data",
        "-v", f"{BASE}/Gemma/local_eval/snapshots:/snaps",
        "-v", f"{BASE}/Gemma/local_eval/parity_rig/m1_batch_v3/router_v3/r{rep}:/out",
        "-e", "PYTHONPATH=/x",
        "-e", "OPENAI_BASE_URL=http://host.docker.internal:8081/v1",
        "-e", "OPENAI_API_KEY=EMPTY",
        "-w", "/rig",
        "gemma-parity-rig:latest",
        "python", "-m", "swegemma", "eval",
        "--tasks", "/data/tasks.jsonl",
        "--snapshots-dir", "/snaps",
        "--results-dir", "/out",
        "--submission-dir", f"/rig/{ARM_DIR}",
        "--sandbox", "subprocess",
    ]
    for t in COHORT:
        cmd += ["--task-id", t]
    cmd += ["--max-tool-calls", "28", "--max-turns", "120",
            "--timeout-seconds", "300", "--max-time-minutes", "8",
            "--display", "quiet"]
    t0 = time.time()
    print(f"[start] router_v3 r{rep} ({len(COHORT)} tasks)", flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = ((p.stdout or "") + (p.stderr or ""))[-400:]
    print(f"[done] router_v3 r{rep} rc={p.returncode} {time.time()-t0:.0f}s :: {tail}", flush=True)


def agg_block(d, arm, reps):
    k = n = 0
    per = {}
    for rep in range(reps):
        f = d / arm / f"r{rep}" / "task_results.jsonl"
        if not f.exists():
            continue
        for l in open(f, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                n += 1
                k += int(bool(r.get("resolved")))
                per[r["instance_id"]] = per.get(r["instance_id"], 0) + int(bool(r.get("resolved")))
    return k, n, per


def main():
    t0 = time.time()
    for rep in range(REPS):
        run_one(rep)
    print("\n=== V3 COMPARISON (ctrl / router-v1 / router-v2 / router-v3) ===")
    ck, cn, cper = agg_block(RIG / "m1_batch", "ctrl", REPS)
    ok, on, oper = agg_block(RIG / "m1_batch", "router", REPS)   # v1 router
    k2, n2, p2 = agg_block(RIG / "m1_batch_v2", "router_v2", REPS)  # v2 router
    vk, vn, vper = agg_block(RIG / "m1_batch_v3", "router_v3", REPS)  # v3 router
    print(f"ctrl (batch1):        {ck}/{cn}")
    print(f"router v1 (batch1):   {ok}/{on}")
    print(f"router v2 (batch2):   {k2}/{n2}")
    print(f"router v3 (batch3):   {vk}/{vn}")
    print()
    print("%-14s %6s %8s %8s %8s" % ("task", "ctrl", "router-v1", "router-v2", "router-v3"))
    for t in COHORT:
        print("%-14s %6d %8d %8d %8d" % (t, cper.get(t, 0), oper.get(t, 0),
                                         p2.get(t, 0), vper.get(t, 0)))
    # dispatch + empty-return readout for v2
    disp_tasks = empty = traces = 0
    for rep in range(REPS):
        for tr in (RIG / "m1_batch_v3" / "router_v3" / f"r{rep}" / "traces").glob("trace_*.json") if (RIG / "m1_batch_v3" / "router_v3" / f"r{rep}" / "traces").exists() else []:
            traces += 1
            txt = tr.read_text(encoding="utf-8", errors="replace")
            if '"function_name": "code_locator"' in txt or '"function_name": "logic_analyst"' in txt:
                disp_tasks += 1
    print(f"\nv2 dispatch rate: {disp_tasks}/{traces} tasks (real function_name calls in traces)")
    print(f"total wall: {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()

