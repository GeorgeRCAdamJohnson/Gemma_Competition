"""Multi-arm tuning batch: v4/v5/v6 x 2 reps x 7 tasks = 42 runs, sequential.
References from earlier batches are aggregated alongside: ctrl (batch1), v1 (batch1), v3 (batch3).
Prereg decision rules are in _build_router_variants.py's docstring."""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
COHORT = ["rich_3006", "rich_3454", "rich_3518", "rich_3905", "rich_4077", "rich_3777", "rich_3882"]
ARMS = {"v4": "agent_router_v4", "v5": "agent_router_v5", "v6": "agent_router_v6"}
REPS = 2
BASE = "C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE"


def run_one(arm, rep):
    out = RIG / "m1_batch_multi" / arm / f"r{rep}"
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
        "-v", f"{BASE}/Gemma/local_eval/parity_rig/m1_batch_multi/{arm}/r{rep}:/out",
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


def agg(d, arm, reps, subdir=None):
    k = n = 0
    per = {}
    root = RIG / d if subdir is None else RIG / d / subdir
    for rep in range(reps):
        f = root / arm / f"r{rep}" / "task_results.jsonl" if subdir is None else root / f"r{rep}" / "task_results.jsonl"
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

    print("\n=== MULTI-ARM TUNING PANEL (goal: landing consistency) ===")
    refs = [
        ("ctrl",) + agg("m1_batch", "ctrl", 3, subdir=None) if False else None,
    ]
    rows = []
    # references: read known dirs directly
    def agg2(path, reps):
        k = n = 0; per = {}
        for rep in range(reps):
            f = RIG / path / f"r{rep}" / "task_results.jsonl"
            if not f.exists(): continue
            for l in open(f, encoding="utf-8"):
                if l.strip():
                    r = json.loads(l); n += 1
                    ok = int(bool(r.get("resolved"))); k += ok
                    per[r["instance_id"]] = per.get(r["instance_id"], 0) + ok
        return k, n, per
    c = agg2("m1_batch/ctrl", 3)
    v1 = agg2("m1_batch/router", 3)
    v3 = agg2("m1_batch_v3/router_v3", 3)
    v4 = agg2("m1_batch_multi/v4", REPS)
    v5 = agg2("m1_batch_multi/v5", REPS)
    v6 = agg2("m1_batch_multi/v6", REPS)
    panel = [("ctrl", c), ("v1", v1), ("v3", v3), ("v4-depth", v4), ("v5-anchor", v5), ("v6-testoracle", v6)]
    for name, (k, n, _p) in panel:
        print("%-14s %2d/%2d  rate=%.2f" % (name, k, n, (k / n) if n else 0))
    print()
    print("%-14s %5s %5s %5s %5s %5s %5s %5s" % ("task", "ctrl", "v1", "v3", "v4", "v5", "v6", ""))
    permap = {n: p for n, (_k, _n, p) in panel}
    for t in COHORT:
        vals = [permap[n].get(t, 0) for n in ("ctrl", "v1", "v3", "v4-depth", "v5-anchor", "v6-testoracle")]
        print("%-14s %5d %5d %5d %5d %5d %5d" % (t, *vals))
    print()
    for name, (k, n, _p) in panel[3:]:
        verdict = "ADVANCE (>=5/14)" if k >= 5 else ("dead (<=2/14)" if k <= 2 else "inconclusive (3-4/14)")
        print("%-14s %2d/%2d -> %s" % (name, k, n, verdict))
    print("total wall: %.1f min" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
