"""FULL 129-TASK SWEEP: official-12B (vLLM :8082, ca5 prompt) x N reps.
Pairs against existing m1_full129/ca5 (15/129) and ca5_v2 (10/129) and the
historical 31B-v10 reference (34/129). Resume-safe: recomputes missing task-ids
from each rep's task_results.jsonl on every invocation.
Env: REP (int, default 0), CONC (default 3 -- vLLM max_num_seqs=8, PAR=3 proven safe)
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
BASE = "C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE"
REP = os.environ.get("REP", "0")
CONC = os.environ.get("CONC", "3")
URL = os.environ.get("M1_URL", "http://host.docker.internal:8082/v1")
AGENT = os.environ.get("M1_AGENT", "agent_ctrl_12b")   # ca5 prompt + official 12B model line
OUT = RIG / "m1_full129" / f"off12_r{REP}"
OUT.mkdir(parents=True, exist_ok=True)

ALL = [json.loads(l)["instance_id"]
       for l in open(BASE + "/Gemma/comp_files/tasks.jsonl", encoding="utf-8") if l.strip()]


def missing_ids():
    done = set()
    f = OUT / "task_results.jsonl"
    if f.exists():
        for l in open(f, encoding="utf-8"):
            if l.strip():
                done.add(json.loads(l)["instance_id"])
    return [t for t in ALL if t not in done]


def main():
    todo = missing_ids()
    print(f"rep {REP}: missing {len(todo)}/{len(ALL)} (concurrency {CONC}, {AGENT}, {URL})", flush=True)
    if todo:
        cmd = [
            "docker", "run", "--rm", "--add-host=host.docker.internal:host-gateway",
            "-v", f"{BASE}/Gemma/local_eval/parity_rig:/rig",
            "-v", f"{BASE}/Gemma/harness_src/x:/x",
            "-v", f"{BASE}/Gemma/comp_files:/data",
            "-v", f"{BASE}/Gemma/local_eval/snapshots:/snaps",
            "-v", f"{BASE}/Gemma/local_eval/parity_rig/m1_full129/off12_r{REP}:/out",
            "-e", "PYTHONPATH=/x",
            "-e", f"OPENAI_BASE_URL={URL}",
            "-e", "OPENAI_API_KEY=EMPTY",
            "-w", "/rig", "gemma-parity-rig:latest",
            "python", "-m", "swegemma", "eval",
            "--tasks", "/data/tasks.jsonl",
            "--snapshots-dir", "/snaps",
            "--results-dir", "/out",
            "--submission-dir", f"/rig/{AGENT}",
            "--sandbox", "subprocess",
            "--concurrency", CONC,
            "--display", "quiet",
        ]
        for t in todo:
            cmd += ["--task-id", t]
        t0 = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(f"[docker] rc={p.returncode} {time.time()-t0:.0f}s", flush=True)
        if p.returncode != 0:
            print("tail:", ((p.stdout or "") + (p.stderr or ""))[-500:], flush=True)

    rows = []
    f = OUT / "task_results.jsonl"
    if f.exists():
        for l in open(f, encoding="utf-8"):
            if l.strip():
                rows.append(json.loads(l))
    k = sum(int(bool(r.get("resolved"))) for r in rows)
    print(f"\n=== off12_r{REP} FULL POOL: {k}/{len(rows)}"
          + (f" = {k/len(rows):.3f}" if rows else "") + " ===")
    print("refs: ca5(E4B) 15/129 & 10/129 | 31B-v10 34/129")
    by = {}
    for r in rows:
        repo = r.get("repo") or r["instance_id"].split("_")[0]
        d = by.setdefault(repo, [0, 0])
        d[0] += int(bool(r.get("resolved")))
        d[1] += 1
    for repo, (kk, n) in sorted(by.items()):
        print(f"  {repo:<22} {kk:>3}/{n:<3}")
    errs = [r["instance_id"] for r in rows if r.get("error")]
    if errs:
        print(f"  rows with error field: {len(errs)}")


if __name__ == "__main__":
    main()
