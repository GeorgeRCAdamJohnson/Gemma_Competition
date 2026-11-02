"""rich_4077 x100 single-task burst (official 12B, :8082) for flip-rate precision + forensics corpus.
Parallel waves (vLLM max_num_seqs=8). New arm dir off4077 -- never touches other banks."""
import json
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
REPS = int(os.environ.get("M1_REPS", "100"))
PAR = int(os.environ.get("M1_PAR", "5"))
ARM = "off4077"
BASE_URL = os.environ.get("M1_URL", "http://host.docker.internal:8082/v1")


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
        "--submission-dir", "/rig/agent_ctrl_12b",
        "--sandbox", "subprocess",
        "--task-id", TASK,
        "--max-tool-calls", "28", "--max-turns", "120",
        "--timeout-seconds", "300", "--max-time-minutes", "8", "--display", "quiet",
    ]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    line = f"[done] r{rep} rc={p.returncode} {time.time()-t0:.0f}s"
    if p.returncode != 0 and not (out / "task_results.jsonl").exists():
        line += " ERR:" + (p.stderr or p.stdout or "")[-300:]
    return line


def main():
    t0 = time.time()
    k = n = 0
    with ThreadPoolExecutor(max_workers=PAR) as ex:
        for msg in ex.map(run_one, range(REPS)):
            print(msg, flush=True)
            if msg.startswith("[done]"):
                n += 1
    for rep in range(REPS):
        f = RIG / "m1_batch_multi" / ARM / f"r{rep}" / "task_results.jsonl"
        if f.exists():
            for l in open(f, encoding="utf-8"):
                if l.strip():
                    k += int(bool(json.loads(l).get("resolved")))
    # Wilson 95% CI
    import math
    N = sum(1 for rep in range(REPS) if (RIG / "m1_batch_multi" / ARM / f"r{rep}" / "summary.json").exists())
    ph = k / N if N else 0
    z = 1.96
    z2 = z**2
    denom = 1 + z2 / N if N else 1
    center = (ph + z2 / (2 * N)) / denom if N else 0
    half = (z * math.sqrt(ph * (1 - ph) / N + z2 / (4 * N * N)) / denom) if N else 0
    print(f"\n=== 4077 BURST: {k}/{N} rate={ph:.3f}  Wilson95=[{center-half:.3f},{center+half:.3f}]")
    print("refs: ca5(E4B) 3/19=.158 | b12 0/21=0 | off12-cohort 1/13=.077")
    print("wall: %.1f min" % ((time.time() - t0) / 60))


if __name__ == "__main__":
    main()
