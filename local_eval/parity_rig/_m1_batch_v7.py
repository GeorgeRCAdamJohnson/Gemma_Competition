"""Panel continuation: v7 (thinking 512, 2 reps) + v5 rep-3 confirmation (1 run set).
Jobs interleaved: v7 r0, v5 r2, v7 r1 - 21 runs total. Resume-safe per (arm, rep)."""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
COHORT = ["rich_3006", "rich_3454", "rich_3518", "rich_3905", "rich_4077", "rich_3777", "rich_3882"]
ARMS = {"v4": "agent_router_v4", "v5": "agent_router_v5", "v6": "agent_router_v6", "v7": "agent_router_v7"}
JOBS = [("v7", 0), ("v5", 2), ("v7", 1)]
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


def agg2(path, reps):
    k = n = 0
    per = {}
    for rep in range(reps):
        f = RIG / path / f"r{rep}" / "task_results.jsonl"
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


def mech(arm):
    cap = disp = multi = empt = 0
    for rep in range(3):
        base = RIG / "m1_batch_multi" / arm / f"r{rep}"
        f = base / "task_results.jsonl"
        if f.exists():
            for l in open(f, encoding="utf-8"):
                if l.strip():
                    r = json.loads(l)
                    if (r.get("tool_calls") or 0) >= 28:
                        cap += 1
        import re as _re
        td = base / "traces"
        if td.exists():
            for tr in td.glob("trace_*.json"):
                c = len(_re.findall(r'"function_name":\s*"(code_locator|logic_analyst)"',
                                    tr.read_text(encoding="utf-8", errors="replace")))
                if c:
                    disp += 1
                    if c > 1:
                        multi += 1
        ld = base / "logs"
        if ld.exists():
            for lg in ld.glob("*.log"):
                empt += lg.read_text(encoding="utf-8", errors="replace").count('"raw": ""')
    return cap, disp, multi, empt


def main():
    t0 = time.time()
    for j in JOBS:
        run_one(*j)

    print("\n=== PANEL + v7(512) + v5-rep3 ===")
    panel = [
        ("ctrl", agg2("m1_batch/ctrl", 3)),
        ("v1", agg2("m1_batch/router", 3)),
        ("v3", agg2("m1_batch_v3/router_v3", 3)),
        ("v4-1024", agg2("m1_batch_multi/v4", 2)),
        ("v5-anchor", agg2("m1_batch_multi/v5", 3)),
        ("v6-oracle", agg2("m1_batch_multi/v6", 2)),
        ("v7-512", agg2("m1_batch_multi/v7", 2)),
    ]
    for name, (k, n, _p) in panel:
        extra = ""
        if name.startswith("v"):
            arm = name.split("-")[0]
            cap, disp, multi, empt = mech(arm)
            extra = "   [cap28=%d disp=%d multi=%d empties=%d]" % (cap, disp, multi, empt)
        print("%-12s %2d/%2d  rate=%.2f%s" % (name, k, n, (k / n) if n else 0, extra))
    print()
    permap = {n: p for n, (_k, _n, p) in panel}
    names = ["ctrl", "v1", "v3", "v4-1024", "v5-anchor", "v6-oracle", "v7-512"]
    print("%-14s" % "task" + "".join("%9s" % x for x in names))
    for t in COHORT:
        print("%-14s" % t + "".join("%9d" % permap[n].get(t, 0) for n in names))
    k5, n5, _ = permap["v5-anchor"]
    print("\nv5 full (3 reps): %d/%d %s" % (k5, n5, "-> CONFIRMED >=5/14 and best-rate" if k5 / max(n5, 1) >= 0.5 else "-> regressed"))
    print("total wall: %.1f min" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
