"""Run all 129 tasks through _skilltest.py (one docker invocation, resume-safe by re-running only missing ids).
Usage: SKILLTEST_CAPS=15,8,120 SKILLTEST_CONC=3 python _run129.py <arm> <agent_dir> <rep>
"""
import json
import subprocess
import sys
from pathlib import Path

RIG = Path(__file__).resolve().parent
G = RIG.parents[1]
arm, agent, rep = sys.argv[1:4]
ALL = [json.loads(l)["instance_id"] for l in (G / "comp_files" / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
out = RIG / "m1_skilltest" / f"{arm}_r{rep}" / "task_results.jsonl"
done = set()
if out.exists():
    done = {json.loads(l)["instance_id"] for l in out.read_text(encoding="utf-8").splitlines() if l.strip()}
todo = [t for t in ALL if t not in done]
print(f"todo {len(todo)}/129", flush=True)
if todo:
    subprocess.run([sys.executable, str(RIG / "_skilltest.py"), arm, agent, rep] + todo)
