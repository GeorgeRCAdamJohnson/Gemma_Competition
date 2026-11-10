# Runs ON the GPU VM: why did prep fail? Drive visibility + the uploaded inputs archive.
import os
import subprocess
from pathlib import Path

print("mount:", os.path.ismount("/content/drive"), "| MyDrive:", Path("/content/drive/MyDrive").exists())
for p in ("/content/drive/MyDrive/gemma_fasteval/colab_env", "/content/drive/MyDrive/gemma-4-developer-agent-cache/models"):
    print(p, "->", sorted(os.listdir(p))[:6] if os.path.isdir(p) else "MISSING")
a = Path("/content/ab_inputs.tar")
print("ab_inputs.tar:", a.stat().st_size if a.exists() else "MISSING")
print(subprocess.run("file /content/ab_inputs.tar; head -c 300 /content/ab_inputs.tar | od -c | head -5; tar -tf /content/ab_inputs.tar 2>&1 | head -5",
                     shell=True, capture_output=True, text=True).stdout)
