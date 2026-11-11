# Runs ON a prepped GPU VM: start one A/B driver detached, configured by /content/launch.json
#   {"arms": "arms3", "out": "/content/ab3", "tag": "e4b_ab3_20261111", "rounds": 8, "round_from": 1, "deadline_h": 11}
import json
import os
import subprocess
from pathlib import Path

c = json.loads(Path("/content/launch.json").read_text())
assert "ALL_DONE" in Path("/content/work/gpu_ab_run.py").read_text(), "driver is not the fixed version"
name = Path(c["out"]).name
pidf = Path(f"/content/{name}.pid")
if pidf.exists() and os.path.exists(f"/proc/{pidf.read_text().strip()}"):
    print("driver already running, pid", pidf.read_text().strip())
else:
    env = dict(os.environ, AB_ARMS=c["arms"], AB_OUT=c["out"], AB_TAG=c["tag"], AB_ROUND_FROM=str(c.get("round_from", 1)))
    p = subprocess.Popen(["/content/venv/bin/python", "/content/work/gpu_ab_run.py", str(c["rounds"]), str(c["deadline_h"])],
                         cwd="/content/work", stdout=open(f"/content/{name}.log", "a"), stderr=subprocess.STDOUT,
                         env=env, start_new_session=True)
    pidf.write_text(str(p.pid))
    print("driver started", c, "pid", p.pid)
