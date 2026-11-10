# Runs ON the Colab VM: hard-kill every snapshot/tar process by PID (pattern-based pkill missed them), remove the
# corrupt partial archive.
import os
import signal
import subprocess
import time

out = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True).stdout.splitlines()[1:]
me = os.getpid()
for l in out:
    pid, args = l.strip().split(None, 1)
    pid = int(pid)
    if pid != me and ("snapshot.sh" in args or "colab_env.tar" in args):
        os.kill(pid, signal.SIGKILL)
        print("killed", pid, args[:100])
time.sleep(1)
for f in ("/content/colab_env.tar", "/content/drive/MyDrive/gemma_fasteval/colab_env/colab_env.tar.partial"):
    if os.path.exists(f):
        os.remove(f)
        print("removed", f)
left = [l for l in subprocess.run(["ps", "-eo", "pid,args"], capture_output=True, text=True).stdout.splitlines()
        if "colab_env.tar" in l or "snapshot.sh" in l]
print("remaining:", left or "none")
