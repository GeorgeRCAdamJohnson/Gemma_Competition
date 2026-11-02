"""Small-batch driver for the submit-gate / skill experiments (local E4B llama-server :8081).

Usage: python _skilltest.py <arm_name> <agent_dir> <rep> <task_id> [<task_id> ...]
Writes to m1_skilltest/<arm_name>_r<rep>/ (task_results.jsonl, traces/, patches/, test_outputs/).
Board caps passed explicitly (28 tool calls / 8 min / 120 turns), concurrency 2, same image as m1_capped.
"""
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
BASE = "C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE"


def main():
    arm, agent, rep, tasks = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
    out_rel = f"m1_skilltest/{arm}_r{rep}"
    (RIG / out_rel).mkdir(parents=True, exist_ok=True)
    cmd = [
        "docker", "run", "--rm", "--add-host=host.docker.internal:host-gateway",
        "-v", f"{BASE}/Gemma/local_eval/parity_rig:/rig",
        "-v", f"{BASE}/Gemma/harness_src/x:/x",
        "-v", f"{BASE}/Gemma/comp_files:/data",
        "-v", f"{BASE}/Gemma/local_eval/snapshots:/snaps",
        "-v", f"{BASE}/Gemma/local_eval/parity_rig/{out_rel}:/out",
        "-e", "PYTHONPATH=/x",
        "-e", "OPENAI_BASE_URL=http://host.docker.internal:8081/v1",
        "-e", "OPENAI_API_KEY=EMPTY",
        "-w", "/rig", "gemma-parity-rig:latest",
        *(["python", "/rig/_compact_main.py", "eval"] if __import__("os").environ.get("SKILLTEST_COMPACT") == "1"
          else ["python", "-m", "swegemma", "eval"]),
        "--tasks", "/data/tasks.jsonl", "--snapshots-dir", "/snaps",
        "--results-dir", "/out", "--submission-dir", f"/rig/{agent}",
        "--sandbox", "subprocess", "--concurrency", "2", "--display", "quiet",
    ]
    import os
    calls, minutes, turns = (os.environ.get("SKILLTEST_CAPS", "28,8,120").split(",") + ["", "", ""])[:3]
    cmd += ["--max-tool-calls", calls, "--max-time-minutes", minutes, "--max-turns", turns]
    if os.environ.get("SKILLTEST_CONC"):
        cmd[cmd.index("--concurrency") + 1] = os.environ["SKILLTEST_CONC"]
    for t in tasks:
        cmd += ["--task-id", t]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"[{arm} r{rep}] rc={p.returncode} wall={time.time() - t0:.0f}s", flush=True)
    if p.returncode != 0:
        print((p.stdout or "")[-1500:], (p.stderr or "")[-2500:], flush=True)


if __name__ == "__main__":
    main()
