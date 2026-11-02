"""E4B main-agent thinking-budget sweep: t1024 + t2048 x 3 reps (control = ca5 @4096, 133 runs).
Mount-safe by construction: one explicit mount string per arm, byte-asserted before launch."""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
COHORT = ["rich_3006", "rich_3454", "rich_3518", "rich_3905", "rich_4077", "rich_3777", "rich_3882"]
ARMS = {"b12": "agent_ctrl_12b"}
REPS = 3
BASE = "C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE"


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
        "-e", "OPENAI_BASE_URL=http://host.docker.internal:8081/v1",
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
    print(f"[start] {arm} r{rep}", flush=True)
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"[done] {arm} r{rep} rc={p.returncode} {time.time()-t0:.0f}s", flush=True)


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
    print("\n=== E4B MAIN-AGENT THINKING SWEEP (7 tasks x 3 reps) ===")
    ck, cn, cper = 67, 133, {}
    for t in COHORT:
        cper[t] = None
    # ca5 reference from its bank
    import collections
    ca5per = collections.Counter()
    for rep in range(1, 20):
        f = RIG / "m1_batch_multi" / "ca5" / f"r{rep}" / "task_results.jsonl"
        if f.exists():
            for l in open(f, encoding="utf-8"):
                if l.strip():
                    d = json.loads(l)
                    if d.get("resolved"):
                        ca5per[d["instance_id"]] += 1
    rows = [("ca5 @4096 (ref)", 67, 133, ca5per)]
    for arm in ARMS:
        k, n, per = agg(arm)
        rows.append((f"{arm}", k, n, per))
    print("%-18s %8s %7s" % ("arm", "score", "rate"))
    for name, k, n, _p in rows:
        print("%-18s %3d/%-3d %7.3f" % (name, k, n, k / n if n else 0))
    print()
    hdr = ["task", "ca5@4096"] + [a for a in ARMS]
    print("%-14s %10s %8s %8s %8s %8s" % tuple(hdr))
    for t in COHORT:
        vals = [t, "%d/19" % ca5per.get(t, 0)] + [rows[i + 1][3].get(t, 0) for i in range(len(ARMS))]
        print("%-14s %10s %8d %8d %8d %8d" % tuple(vals))
    print("\nwall: %.1f min" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
