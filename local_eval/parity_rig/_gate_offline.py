"""Offline test of skills/submit-gate/scripts/check.py: for one task, apply each candidate patch to a fresh
snapshot mounted at /workspace and record the gate verdict. Candidates = gold patch + every recorded E4B
patch for the task (resolved and unresolved) from the 129-task runs. Runs inside the rig image (no model).

Usage: python _gate_offline.py <task_id> [<task_id> ...]
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
G = RIG.parents[1]
BASE = "C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE"
GATE = RIG / "agent_ctrl_e4b_gated" / "skills" / "submit-gate" / "scripts" / "check.py"
RUNS = {
    "L-ca5": RIG / "m1_full129" / "ca5", "L-ca5v2": RIG / "m1_full129" / "ca5_v2",
    "L-r0": RIG / "m1_capped" / "agent_ctrl_e4b_r0", "L-r1": RIG / "m1_capped" / "agent_ctrl_e4b_r1",
    "L-fa": RIG / "m1_faithful" / "agent_ctrl_e4b_r0",
    "K-1": G / "kaggle_pkg" / "out_e4b" / "results", "K-2": G / "kaggle_pkg" / "out_e4b_r2" / "results",
}
TASKS = {json.loads(l)["instance_id"]: json.loads(l)
         for l in (G / "comp_files" / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}

INNER = r'''
set -e
mkdir -p /workspace && cd /workspace && tar xzf /snaps/$TID.tgz -C /workspace
if [ ! -d .git ]; then git init -q && git add -A && git -c user.email=a@b -c user.name=a commit -qm base; fi
git -c user.email=a@b -c user.name=a tag -f _swegemma_baseline >/dev/null 2>&1 || true
git apply --whitespace=nowarn /cand.patch || git apply --3way --whitespace=nowarn /cand.patch
python3 /check.py
'''


def results(d):
    f = d / "task_results.all.jsonl"
    if not f.exists():
        f = d / "task_results.jsonl"
    return {json.loads(l)["instance_id"]: json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()}


def run(tid, patch_text):
    with tempfile.NamedTemporaryFile("w", suffix=".patch", delete=False, encoding="utf-8", newline="\n") as fh:
        fh.write(patch_text if patch_text.endswith("\n") else patch_text + "\n")
        pp = fh.name
    cmd = ["docker", "run", "--rm", "-e", f"TID={tid}",
           "-v", f"{BASE}/Gemma/local_eval/snapshots:/snaps:ro",
           "-v", f"{pp}:/cand.patch:ro", "-v", f"{GATE.as_posix()}:/check.py:ro",
           "--entrypoint", "bash", "gemma-parity-rig:latest", "-c", INNER]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    Path(pp).unlink(missing_ok=True)
    out = (p.stdout or "") + (p.stderr or "")
    line = next((l for l in out.splitlines() if l.startswith(("ACCEPTED", "REJECTED"))), out.strip()[-200:])
    return line


for tid in sys.argv[1:]:
    print(f"=== {tid}")
    print(f"  gold          -> {run(tid, TASKS[tid]['patch'])[:230]}")
    seen = set()
    for name, d in RUNS.items():
        r = results(d).get(tid)
        pf = d / "patches" / f"{tid}.patch"
        if not r or not pf.exists():
            continue
        txt = pf.read_text(encoding="utf-8", errors="replace")
        if not txt.strip() or txt in seen:
            continue
        seen.add(txt)
        print(f"  {name:<6} resolved={str(r['resolved']):<5} -> {run(tid, txt)[:230]}")
