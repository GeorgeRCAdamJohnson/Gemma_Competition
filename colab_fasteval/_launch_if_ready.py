# Runs ON a GPU VM: if prep finished, launch the driver configured by /content/launch.json (detached); else report.
import json
import os
import subprocess
from pathlib import Path

if not Path("/content/prep.done").exists():
    log = Path("/content/prep.log")
    print("PREP NOT DONE:", log.read_text(errors="replace").splitlines()[-3:] if log.exists() else "no prep.log")
    raise SystemExit
c = json.loads(Path("/content/launch.json").read_text())
assert "ALL_DONE" in Path("/content/work/gpu_ab_run.py").read_text(), "driver is not the fixed version"
assert Path(f"/content/work/{c['arms']}").is_dir(), f"missing /content/work/{c['arms']}"
name = Path(c["out"]).name
pidf = Path(f"/content/{name}.pid")
if pidf.exists() and os.path.exists(f"/proc/{pidf.read_text().strip()}"):
    print("already running, pid", pidf.read_text().strip())
else:
    env = dict(os.environ, AB_ARMS=c["arms"], AB_OUT=c["out"], AB_TAG=c["tag"], AB_ROUND_FROM=str(c.get("round_from", 1)))
    p = subprocess.Popen(["/content/venv/bin/python", "/content/work/gpu_ab_run.py", str(c["rounds"]), str(c["deadline_h"])],
                         cwd="/content/work", stdout=open(f"/content/{name}.log", "a"), stderr=subprocess.STDOUT,
                         env=env, start_new_session=True)
    pidf.write_text(str(p.pid))
    print("LAUNCHED", c, "pid", p.pid)
