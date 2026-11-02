"""FULL 129-TASK RUN on ca5 (the pre-submission gate the user requested).

- All tasks from tasks.jsonl (no --task-id filter); RESUME-SAFE: computes missing
  task-ids from out/task_results.jsonl on every invocation, so a crash/rerun continues.
- --concurrency 2 (llama-server has 3 slots; subprocess sandboxes are per-task).
- Aggregate reports PER REPO because the 31B reference (v10 129-run, 34/129) splits
  fastapi 18 / rich ~15 / requests 1 - raw totals are only comparable per repo, since
  local fastapi test-deps are unverified (see warning printed at the end).
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
BASE = "C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE"
OUT = RIG / "m1_full129" / "ca5"
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
    print(f"missing: {len(todo)}/129", flush=True)
    if not todo:
        print("nothing to do")
    else:
        cmd = [
            "docker", "run", "--rm", "--add-host=host.docker.internal:host-gateway",
            "-v", f"{BASE}/Gemma/local_eval/parity_rig:/rig",
            "-v", f"{BASE}/Gemma/harness_src/x:/x",
            "-v", f"{BASE}/Gemma/comp_files:/data",
            "-v", f"{BASE}/Gemma/local_eval/snapshots:/snaps",
            "-v", f"{BASE}/Gemma/local_eval/parity_rig/m1_full129/ca5:/out",
            "-e", "PYTHONPATH=/x",
            "-e", "OPENAI_BASE_URL=http://host.docker.internal:8081/v1",
            "-e", "OPENAI_API_KEY=EMPTY",
            "-w", "/rig", "gemma-parity-rig:latest",
            "python", "-m", "swegemma", "eval",
            "--tasks", "/data/tasks.jsonl",
            "--snapshots-dir", "/snaps",
            "--results-dir", "/out",
            "--submission-dir", "/rig/agent_ctrl_v5",
            "--sandbox", "subprocess",
            "--concurrency", "2",
            "--display", "quiet",
        ]
        for t in todo:
            cmd += ["--task-id", t]
        t0 = time.time()
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        tail = ((p.stdout or "") + (p.stderr or ""))[-600:]
        print(f"[docker] rc={p.returncode} {time.time()-t0:.0f}s :: {tail}", flush=True)

    # aggregate
    rows = []
    f = OUT / "task_results.jsonl"
    if f.exists():
        for l in open(f, encoding="utf-8"):
            if l.strip():
                rows.append(json.loads(l))
    k = sum(int(bool(r.get("resolved"))) for r in rows)
    print("\n=== ca5 FULL POOL ===")
    print(f"resolved {k}/{len(rows)}  ({k/len(rows):.3f} overall)" if rows else "no rows")
    by = {}
    for r in rows:
        repo = r["repo"] if "repo" in r else r["instance_id"].split("_")[0]
        d = by.setdefault(repo, [0, 0, 0])
        d[1] += 1
        d[0] += int(bool(r.get("resolved")))
        if r.get("error"):
            d[2] += 1
    ref = {"Textualize/rich": 15, "fastapi/fastapi": 18, "psf/requests": 1, "encode/httpx": 0}
    print("%-20s %9s %10s %7s" % ("repo", "ca5 local", "31B-v10 ref", "errors"))
    for repo, (kk, n, errs) in sorted(by.items()):
        print("%-20s %4d/%-4d %6d/%-4d %7d" % (repo, kk, n, ref.get(repo, 0), 129 - 0 if False else {"Textualize/rich": 48, "fastapi/fastapi": 67, "psf/requests": 13, "encode/httpx": 1}.get(repo, 0), errs))
    print("\n31B v10 reference total: 34/129 (fastapi 18 / rich 15 / requests 1) - "
          "MODEL DIFFERS (31B vs E4B): compare per-repo, not totals.")
    # worst offenders for triage
    errs = [r["instance_id"] for r in rows if r.get("error")]
    if errs:
        print("rows with error field: %d -> %s%s" % (len(errs), errs[:8], " ..." if len(errs) > 8 else ""))


if __name__ == "__main__":
    main()
