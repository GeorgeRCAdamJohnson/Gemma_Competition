"""Locate-numeral arm: run the 46-task cohort on the parity rig.

Single variable: ca5 prompt with line 26's numeral changed 3-4 -> 10-12
(baseline sha b08b32a2438d -> arm sha 4123e8047797). Everything else byte-identical.

Caps are passed explicitly (28 calls / 8 min / 120 turns / 300 s) to mirror the board;
the older driver omitted them and silently ran the library default of 60 min / no cap.

Env: CONC (default 3), ARM (default agent_ctrl_12b_locate), URL, REP
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
CONC = os.environ.get("CONC", "3")
REP = os.environ.get("REP", "0")
ARM = os.environ.get("ARM", "agent_ctrl_12b_locate")
URL = os.environ.get("M1_URL", "http://host.docker.internal:8082/v1")
CAP_CALLS = os.environ.get("CAP_CALLS", "28")
CAP_MIN = os.environ.get("CAP_MIN", "8")
CAP_TURNS = os.environ.get("CAP_TURNS", "120")

COHORT = RIG / "m1_locate" / os.environ.get("COHORT", "cohort.json")
OUT = RIG / os.environ.get("OUT_DIR", "m1_locate") / f"{ARM}_r{REP}"
OUT.mkdir(parents=True, exist_ok=True)

cohort = json.loads(COHORT.read_text(encoding="utf-8"))
ALL = cohort["all"]


def missing_ids():
    done = set()
    f = OUT / "task_results.jsonl"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["instance_id"])
    return [t for t in ALL if t not in done]


def main():
    todo = missing_ids()
    print(f"arm={ARM} cohort={len(ALL)} todo={len(todo)} conc={CONC} caps={CAP_CALLS}/{CAP_MIN}/{CAP_TURNS}",
          flush=True)
    if not todo:
        print("nothing to do")
        return
    cmd = [
        "docker", "run", "--rm", "--add-host=host.docker.internal:host-gateway",
        "-v", f"{BASE}/Gemma/local_eval/parity_rig:/rig",
        "-v", f"{BASE}/Gemma/harness_src/x:/x",
        "-v", f"{BASE}/Gemma/comp_files:/data",
        "-v", f"{BASE}/Gemma/local_eval/snapshots:/snaps",
        "-v", f"{OUT}:/out",
        "-e", "PYTHONPATH=/x",
        "-e", f"OPENAI_BASE_URL={URL}",
        "-e", "OPENAI_API_KEY=EMPTY",
        "-w", "/rig", "gemma-parity-rig:latest",
        "python", "-m", "swegemma", "eval",
        "--tasks", "/data/tasks.jsonl",
        "--snapshots-dir", "/snaps",
        "--results-dir", "/out",
        "--submission-dir", f"/rig/{ARM}",
        "--sandbox", "subprocess",
        "--concurrency", CONC,
        "--display", "quiet",
        "--max-tool-calls", CAP_CALLS,
        "--max-time-minutes", CAP_MIN,
        "--max-turns", CAP_TURNS,
    ]
    for t in todo:
        cmd += ["--task-id", t]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"[docker] rc={p.returncode} {time.time()-t0:.0f}s", flush=True)
    if p.returncode != 0:
        print("tail:", ((p.stdout or "") + (p.stderr or ""))[-800:], flush=True)

    rows = []
    f = OUT / "task_results.jsonl"
    if f.exists():
        rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
    k = sum(int(bool(r.get("resolved"))) for r in rows)
    print(f"done {len(rows)}/{len(ALL)} | solved {k}")
    ctrl = set(cohort["controls"])
    got = {r["instance_id"] for r in rows if r.get("resolved")}
    print("controls solved %d/%d" % (len(ctrl & got), len(ctrl)))
    print("defect solved   %d/%d" % (len(got - ctrl), len(cohort["defect"])))


if __name__ == "__main__":
    main()
