"""ca5 +10 reps (r2..r11): the winning no-router anchor arm gets 70 more runs so the
submission decision rests on ~84 observations instead of 14. Simple final aggregate."""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
COHORT = ["rich_3006", "rich_3454", "rich_3518", "rich_3905", "rich_4077", "rich_3777", "rich_3882"]
ARMS = {"cX": "agent_ctrl_v5", "kX": "agent_ctrl"}
JOBS = [("cX", r) for r in range(12, 20)] + [("kX", r) for r in range(3, 11)]
BASE = "C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE"


def run_one(arm, rep):
    out = (RIG / "m1_batch_multi" / "ca5" / f"r{rep}") if arm == "cX" else (RIG / "m1_batch" / "ctrl" / f"r{rep}")
    out.mkdir(parents=True, exist_ok=True)
    if (out / "summary.json").exists():
        print(f"[skip] {arm} r{rep}", flush=True)
        return
    cmd = [
        "docker", "run", "--rm", "--add-host=host.docker.internal:host-gateway",
        "-v", f"{BASE}/Gemma/local_eval/parity_rig:/rig",
        "-v", f"{BASE}/Gemma/harness_src/x:/x",
        "-v", f"{BASE}/Gemma/comp_files:/data",
        "-v", f"{BASE}/Gemma/local_eval/snapshots:/snaps",
        "-v", f"{BASE}/Gemma/local_eval/parity_rig/" + (f"m1_batch_multi/ca5/r{rep}" if arm == "cX" else f"m1_batch/ctrl/r{rep}") + ":/out",
        "-e", "PYTHONPATH=/x",
        "-e", "OPENAI_BASE_URL=http://host.docker.internal:8081/v1",
        "-e", "OPENAI_API_KEY=EMPTY",
        "-w", "/rig", "gemma-parity-rig:latest",
        "python", "-m", "swegemma", "eval",
        "--tasks", "/data/tasks.jsonl",
        "--snapshots-dir", "/snaps",
        "--results-dir", "/out",
        "--submission-dir", "/rig/" + ("agent_ctrl_v5" if arm == "cX" else "agent_ctrl"),
        "--sandbox", "subprocess",
    ]
    for t in COHORT:
        cmd += ["--task-id", t]
    cmd += ["--max-tool-calls", "28", "--max-turns", "120",
            "--timeout-seconds", "300", "--max-time-minutes", "8", "--display", "quiet"]
    t0 = time.time()
    print(f"[start] {arm} r{rep}", flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"[done] {arm} r{rep} rc={p.returncode} {time.time()-t0:.0f}s", flush=True)


def main():
    t0 = time.time()
    for arm, rep in JOBS:
        run_one(arm, rep)
    # aggregate: ca5 across ALL reps present + references
    import collections
    per = collections.Counter()
    k = n = 0
    for rep in range(12):
        f = RIG / "m1_batch_multi" / "t0" / f"r{rep}" / "task_results.jsonl"
        if not f.exists():
            continue
        for l in open(f, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                n += 1
                ok = int(bool(r.get("resolved")))
                k += ok
                per[r["instance_id"]] += ok
    print("\n=== T0 (ca5 + temp 0) TOTAL ===")
    print(f"t0: {k}/{n}  rate={k/n:.3f}" if n else "no rows")
    for t in COHORT:
        reps_done = sum(1 for rep in range(12)
                        if (RIG / "m1_batch_multi" / "t0" / f"r{rep}" / "task_results.jsonl").exists())
        print("  %-14s %d  (per-rep max %d)" % (t, per.get(t, 0), reps_done))
    # reference 95% CI for the rate (Wilson)
    import math
    if n:
        p = k / n
        z = 1.96
        denom = 1 + z * z / n
        center = (p + z * z / (2 * n)) / denom
        half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
        print(f"95% Wilson CI: [{center-half:.3f}, {center+half:.3f}]  (ctrl ref point: 0.429)")
    print("wall: %.1f min" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()

