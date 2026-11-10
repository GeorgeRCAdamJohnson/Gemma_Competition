# Runs ON the Colab runtime: did the bootstrap cell write Kaggle creds? Names/sizes only, never contents.
import os
import socket
from pathlib import Path

print("hostname", socket.gethostname())
m = Path("/content/_bootstrap_ok")
print("bootstrap marker:", m.exists())
kd = Path.home() / ".kaggle"
print("~/.kaggle:", sorted((f.name, f.stat().st_size, oct(f.stat().st_mode & 0o777)) for f in kd.iterdir()) if kd.exists() else "missing")
