"""rich_4077 cap-relaxation burst v2 (official 12B, :8082).
Hypothesis: 4077 failures at 1/13 were STARVED (28-tool cap + 8-min wall), not capability-limited.
Single-variable change vs the cohort arm: caps lifted, prompt unchanged (system.md b08b32a2438d).
New arm name (off4077t) so contaminated PAR=5 data in off4077 is never mixed in.
Env: M1_REPS, M1_PAR, M1_MAXTIME (session minutes), M1_TOOLS, M1_ARM, M1_URL
"""
import json
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
BASE = "C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE"
TASK = "rich_4077"
REPS = int(os.environ.get("M1_REPS", "16"))
PAR = int(os.environ.get("M1_PAR", "2"))
MAXTIME = os.environ.get("M1_MAXTIME", "15")       # session minutes -> get_status oracle
TOOLS = os.environ.get("M1_TOOLS", "45")           # tool-call cap (was 28)
ARM = os.environ.get("M1_ARM", "off4077t")
BASE_URL = os.environ.get("M1_URL", "http://host.docker.internal:8082/v1")
AGENT = os.environ.get("M1_AGENT", "agent_ctrl_12b")   # ca5 prompt by default


def run_one(rep):
    out = RIG / "m1_batch_multi" / ARM / f"r{rep}"
    out.mkdir(parents=True, exist_ok=True)
    if (out / "summary.json").exists():
        return f"[skip] r{rep}"
    mount = f"{BASE}/Gemma/local_eval/parity_rig/m1_batch_multi/{ARM}/r{rep}:/out"
    assert f"m1_batch_multi/{ARM}/r{rep}" in mount, "mount must name this arm+rep"
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
        "--submission-dir", f"/rig/{AGENT}",
        "--sandbox", "subprocess",
        "--task-id", TASK,
        "--max-tool-calls", TOOLS,
        "--max-turns", "200",
        "--timeout-seconds", "300",           # per shell command, NOT the task
        "--max-time-minutes", MAXTIME,        # session wall clock + get_status oracle
        "--display", "quiet",
    ]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    dt = time.time() - t0
    return f"[done] r{rep} rc={p.returncode} {dt:.0f}s"


def main():
    t0 = time.time()
    print(f"arm={ARM} task={TASK} reps={REPS} par={PAR} maxtime={MAXTIME}m tools={TOOLS} agent={AGENT}", flush=True)
    with ThreadPoolExecutor(max_workers=PAR) as ex:
        for msg in ex.map(run_one, range(REPS)):
            print(msg, flush=True)

    k = n = 0
    durs, cap_hits, tool_hits, patches = [], 0, 0, []
    cap_s = float(MAXTIME) * 60.0
    for rep in range(REPS):
        f = RIG / "m1_batch_multi" / ARM / f"r{rep}" / "task_results.jsonl"
        if not f.exists():
            continue
        for line in open(f, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            n += 1
            ok = bool(r.get("resolved"))
            k += int(ok)
            d = float(r.get("duration_seconds") or 0)
            durs.append(d)
            if d >= cap_s - 45:
                cap_hits += 1
            if int(r.get("tool_calls") or 0) >= int(TOOLS) - 1:
                tool_hits += 1
            patches.append(int(r.get("agent_patch_size") or 0))

    print(f"\n=== 4077 CAP-RELAXED: {k}/{n} rate={k/n if n else 0:.3f} ===")
    if durs:
        durs_sorted = sorted(durs)
        print(f"duration: mean={sum(durs)/len(durs):.0f}s median={durs_sorted[len(durs)//2]:.0f}s max={max(durs):.0f}s")
        print(f"hit {MAXTIME}m wall-cap: {cap_hits}/{n}   hit {TOOLS}-tool cap: {tool_hits}/{n}")
        print(f"patch size: mean={sum(patches)/len(patches):.0f} max={max(patches)} zero-patch={sum(1 for p in patches if p==0)}/{n}")
    if n:
        ph = k / n
        z = 1.96
        denom = 1 + z * z / n
        center = (ph + z * z / (2 * n)) / denom
        half = (z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n))) / denom
        print(f"Wilson95=[{center-half:.3f},{center+half:.3f}]")
    print("refs: ca5(E4B,8min/28tools) 3/19=.158 | b12 0/21 | off12 cohort(8min/28) 1/13=.077")
    print("wall: %.1f min" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
