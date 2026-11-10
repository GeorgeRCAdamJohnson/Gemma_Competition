# Runs ON the GPU VM in its own kernel: keep the kernel active (Colab keeps a runtime alive while a kernel is busy)
# for as long as the A/B driver lives. The API call will hit its 600 s streaming deadline; execution continues server-side.
import os
import time
from pathlib import Path

pid = Path("/content/ab.pid").read_text().strip()
while os.path.exists(f"/proc/{pid}"):
    print(time.strftime("%H:%M:%S"), "driver alive", flush=True)
    time.sleep(120)
print("driver exited", flush=True)
