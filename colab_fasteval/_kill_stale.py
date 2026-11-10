# Runs ON the Colab VM: kill stale uv installs (and any source builds under them) except the newest --no-build one.
import os
import signal
import subprocess

out = subprocess.run(["pgrep", "-fa", "uv pip install"], capture_output=True, text=True).stdout.splitlines()
keep = [l for l in out if "--no-build" in l]
for l in out:
    pid = int(l.split()[0])
    if l in keep:
        continue
    try:
        os.killpg(os.getpgid(pid), signal.SIGKILL)
    except Exception:
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception as e:
            print("could not kill", pid, e)
    print("killed", l[:120])
subprocess.run("pkill -9 -f 'cmake|ninja|dlib' ", shell=True)
print(subprocess.run("pgrep -fa 'uv pip|cmake' | cut -c1-140", shell=True, capture_output=True, text=True).stdout)
