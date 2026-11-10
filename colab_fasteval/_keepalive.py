# Runs ON the GPU VM in its own kernel: keep the kernel active (Colab keeps a runtime alive while a kernel is busy)
# while ANY A/B work is pending: the batch-1 driver, the batch-2 waiter, or the batch-2 driver.
# The API call hits its 600 s streaming deadline; execution continues server-side.
import os
import time
from pathlib import Path


def alive(f):
    p = Path(f)
    return p.exists() and os.path.exists(f"/proc/{p.read_text().strip()}")


while any(alive(f) for f in ("/content/ab.pid", "/content/ab2_waiter.pid", "/content/ab2.pid")):
    print(time.strftime("%H:%M:%S"), "A/B work alive", flush=True)
    time.sleep(120)
print("all A/B work finished", flush=True)
