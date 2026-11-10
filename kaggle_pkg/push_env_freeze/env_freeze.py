# CPU-only Kaggle kernel (no GPU quota): capture the exact host environment our E4B/31B validation kernels ran
# tasks in. swegemma --sandbox subprocess runs task code, the agent's commands and pytest grading in a per-task
# venv over the LAUNCHING interpreter's site-packages, so this image + wheelhouse IS the task environment.
import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path

OUT = Path("/kaggle/working")
print("python", sys.version)
print("executable", sys.executable)
for tool in ("git", "pigz", "patch", "tar"):
    print("tool", tool, shutil.which(tool))
(OUT / "python_version.txt").write_text(sys.version + "\n" + sys.executable + "\n")


def freeze(name):
    r = subprocess.run([sys.executable, "-m", "pip", "freeze", "--all"], capture_output=True, text=True)
    (OUT / name).write_text(r.stdout)
    print(name, len(r.stdout.splitlines()), "packages")


freeze("freeze_image.txt")
# same wheelhouse install as cell 1 of the validation kernels
cands = [Path("/kaggle/input/datasets/metric/gemma-4-developer-agent-wheelhouse"),
         Path("/kaggle/input/gemma-4-developer-agent-wheelhouse")]
wh = next((p for p in cands if p.is_dir()), None)
if wh is None:
    wh = next((Path(p) for p in glob.glob("/kaggle/input/**/gemma-4-developer-agent-wheelhouse", recursive=True)), None)
print("wheelhouse", wh)
for pat in ("/usr/local/lib/python*/dist-packages/*cutlass*.pth", "/usr/local/lib/python*/site-packages/*cutlass*.pth"):
    for pth in glob.glob(pat):
        try:
            os.unlink(pth)
        except OSError:
            pass
tmp = Path("/tmp/wheelhouse")
shutil.rmtree(tmp, ignore_errors=True)
tmp.mkdir(parents=True)
for w in wh.glob("*.whl"):
    if "cutlass" in w.name.lower():
        continue
    name = w.name.replace("cu128", "+cu128") if ("cu128" in w.name and "+" not in w.name) else w.name
    os.symlink(w, tmp / name)
wheels = sorted(str(w) for w in tmp.glob("*.whl"))
print("wheels", len(wheels))
r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "--force-reinstall", *wheels],
                   capture_output=True, text=True)
print("pip rc", r.returncode, (r.stderr or "")[-1500:])
freeze("freeze_after_wheelhouse.txt")
# what a task venv actually sees: site-packages dirs the harness writes into _host_env.pth
sp = [p for p in sys.path if "site-packages" in p and Path(p).is_dir()]
(OUT / "host_site_packages.txt").write_text("\n".join(sp) + "\n")
print("host site-packages:", sp)
for mod in ("pytest", "pydantic", "starlette", "httpx", "anyio", "fastapi", "rich", "requests"):
    try:
        m = __import__(mod)
        print("task-visible", mod, getattr(m, "__version__", "?"))
    except Exception as e:
        print("task-visible", mod, "MISSING", type(e).__name__)
