"""M1 batch: run the REAL harness on known-E4B-resolvable tasks, both arms, 3 reps.

Parity question: the lightweight local harness historically resolved these tasks on E4B.
If the real swegemma harness + LiteLlm + llama-server also resolves them, the rig is
faithful. If none resolve, there is a fidelity gap to find before trusting local arm tests.

42 runs (7 tasks x 3 reps x 2 arms), sequential docker invocations, one results dir per
(arm, rep). Resume-safe: skips a run whose summary.json already exists.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
LE = RIG.parent
COHORT = ["rich_3006", "rich_3454", "rich_3518", "rich_3905", "rich_4077", "rich_3777", "rich_3882"]
ARMS = {"ctrl": "agent_ctrl", "router": "agent_router"}
REPS = 3
BASE = "C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE"


def run_one(arm, rep):
    out = RIG / "m1_batch" / arm / f"r{rep}"
    out.mkdir(parents=True, exist_ok=True)
    if (out / "summary.json").exists():
        print(f"[skip] {arm} r{rep} already done", flush=True)
        return
    cmd = [
        "docker", "run", "--rm", "--add-host=host.docker.internal:host-gateway",
        "-v", f"{BASE}/Gemma/local_eval/parity_rig:/rig",
        "-v", f"{BASE}/Gemma/harness_src/x:/x",
        "-v", f"{BASE}/Gemma/comp_files:/data",
        "-v", f"{BASE}/Gemma/local_eval/snapshots:/snaps",
        "-v", f"{BASE}/Gemma/local_eval/parity_rig/m1_batch/{arm}/r{rep}:/out",
        "-e", "PYTHONPATH=/x",
        "-e", "OPENAI_BASE_URL=http://host.docker.internal:8081/v1",
        "-e", "OPENAI_API_KEY=EMPTY",
        "-w", "/rig",
        "gemma-parity-rig:latest",
        "python", "-m", "swegemma", "eval",
        "--tasks", "/data/tasks.jsonl",
        "--snapshots-dir", "/snaps",
        "--results-dir", "/out",
        "--submission-dir", f"/rig/{ARMS[arm]}",
        "--sandbox", "subprocess",
    ]
    for t in COHORT:
        cmd += ["--task-id", t]
    cmd += ["--max-tool-calls", "28", "--max-turns", "120",
            "--timeout-seconds", "300", "--max-time-minutes", "8",
            "--display", "quiet"]
    t0 = time.time()
    print(f"[start] {arm} r{rep} ({len(COHORT)} tasks)", flush=True)
    print("[cmd] " + " ".join(cmd), flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = ((p.stdout or "") + (p.stderr or ""))[-500:]
    print(f"[done] {arm} r{rep} rc={p.returncode} {time.time()-t0:.0f}s :: {tail}", flush=True)


def main():
    t0 = time.time()
    for rep in range(REPS):
        for arm in ("ctrl", "router"):
            run_one(arm, rep)

    # aggregate
    hist = {"rich_3006": "high", "rich_3905": "high", "rich_3454": "mid",
            "rich_3518": "mid", "rich_4077": "high(historic)/0-of-2-late",
            "rich_3777": "low", "rich_3882": "low"}
    print("\n=== M1 BATCH AGGREGATE (real harness, E4B) ===")
    tot = {}
    per_task = {t: {"ctrl": 0, "router": 0, "n": 0} for t in COHORT}
    for arm in ARMS:
        k = n = 0
        for rep in range(REPS):
            f = RIG / "m1_batch" / arm / f"r{rep}" / "task_results.jsonl"
            if not f.exists():
                continue
            for l in open(f, encoding="utf-8"):
                if l.strip():
                    d = json.loads(l)
                    n += 1
                    k += int(bool(d.get("resolved")))
                    if d["instance_id"] in per_task:
                        per_task[d["instance_id"]][arm] += int(bool(d.get("resolved")))
                        if arm == "ctrl":
                            per_task[d["instance_id"]]["n"] += 1
        tot[arm] = (k, n)
        print(f"{arm:6s}: {k}/{n}")
    print()
    print("%-14s %-16s %s" % ("task", "E4B history", "ctrl | router (of 3 reps)"))
    for t in COHORT:
        r = per_task[t]
        print("%-14s %-16s  %d  |  %d" % (t, hist[t], r["ctrl"], r["router"]))
    print(f"\ntotal wall: {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
