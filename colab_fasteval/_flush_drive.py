# Runs ON the Colab VM: block until Drive has uploaded everything written to /content/drive, then unmount.
import time

from google.colab import drive

t = time.time()
drive.flush_and_unmount()
print(f"flushed and unmounted in {time.time() - t:.0f}s")
