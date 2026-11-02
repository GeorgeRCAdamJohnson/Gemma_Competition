"""Official 12B (vLLM w4a16, port 8082) x 3 reps on the 7-task cohort.
New bank m1_batch_multi/off12 (never touches b12/ca5). Base URL overridable via
M1_URL env; default stays 8081 so the driver is inert for other servers."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
COHORT = ["rich_3006", "rich_3454", "rich_3518", "rich_3905", "rich_4077", "rich_3777", "rich_3882"]
ARMS = {"off12": "agent_ctrl_12b"}
REPS = 13
BASE = "C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE"
BASE_URL = os.environ.get("M1_URL", "http://host.docker.internal:8081/v1")


def run_one(arm, rep):
    out = RIG / "m1_batch_multi" / arm / f"r{rep}"
    out.mkdir(parents=True, exist_ok=True)
    if (out / "summary.json").exists():
        print(f"[skip] {arm} r{rep}", flush=True)
        return
    mount = f"{BASE}/Gemma/local_eval/parity_rig/m1_batch_multi/{arm}/r{rep}:/out"
    assert f"m1_batch_multi/{arm}/r{rep}" in mount, "mount must name THIS arm"
    cmd = [
        "docker", "run", "--rm", "--add-host=host.docker.internal:host-gateway",
        "-v", f"{BASE}/Gemma/local_eval/parity_rig:/rig",
        "-v", f"{BASE}/Gemma/harness_src/x:/x",
        "-v", f"{BASE}/Gemma/comp_files:/data",
        "-v", f"{BASE}/Gemma/local_eval/snapshots:/snaps",
        "-v", mount,
        "-e", "PYTHONPATH=/x",
        "-e", f"OPENAI_BASE_URL={BASE_URL}",
        "-e", "OPENAI_API_KEY=EMPTY",
        "-w", "/rig", "gemma-parity-rig:latest",
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
            "--timeout-seconds", "300", "--max-time-minutes", "8", "--display", "quiet"]
    t0 = time.time()
    print(f"[start] {arm} r{rep} url={BASE_URL}", flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"[done] {arm} r{rep} rc={p.returncode} {time.time()-t0:.0f}s", flush=True)
    if p.returncode != 0 and not (out / "task_results.jsonl").exists():
        print("[err] " + (p.stderr or p.stdout or "")[-800:], flush=True)


def agg(arm):
    k = n = 0
    per = {}
    for rep in range(REPS):
        f = RIG / "m1_batch_multi" / arm / f"r{rep}" / "task_results.jsonl"
        if not f.exists():
            continue
        for l in open(f, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                n += 1
                ok = int(bool(r.get("resolved")))
                k += ok
                per[r["instance_id"]] = per.get(r["instance_id"], 0) + ok
    return k, n, per


def main():
    t0 = time.time()
    for rep in range(REPS):
        for arm in ARMS:
            run_one(arm, rep)
    import collections
    ref = {}
    for bank in ("ca5", "b12"):
        c = collections.Counter()
        for rep in range(0, 20):
            f = RIG / "m1_batch_multi" / bank / f"r{rep}" / "task_results.jsonl"
            if f.exists():
                for l in open(f, encoding="utf-8"):
                    if l.strip():
                        d = json.loads(l)
                        if d.get("resolved"):
                            c[d["instance_id"]] += 1
        ref[bank] = c
    print("\n=== OFFICIAL 12B (vLLM :8082) vs BASE 12B (gguf :8081) vs ca5 E4B ===")
    for bank in ("ca5", "b12"):
        tk = sum(ref[bank].values())
        tn = sum(1 for _ in range(0)) or None
        print(f"{bank} ref resolves (count only): {tk}")
    for arm in ARMS:
        k, n, per = agg(arm)
        print(f"{arm}: {k}/{n} rate={k/n if n else 0:.3f}")
        for t in COHORT:
            print(f"  {t:14s} off12={per.get(t,0)}  ca5={ref['ca5'].get(t,0)}/19  b12={ref['b12'].get(t,0)}/21")
    print("\nwall: %.1f min" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
