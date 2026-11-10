# Runs ON the Colab runtime. Reports only existence/length of candidate secrets, never values.
import os
import platform
import shutil
import sys

print("python", sys.version.split()[0], "|", platform.platform())
print("disk free GB", round(shutil.disk_usage("/content" if os.path.exists("/content") else "/").free / 1e9, 1))
print("nvidia-smi", bool(shutil.which("nvidia-smi")), "| docker", bool(shutil.which("docker")))
try:
    from google.colab import userdata
except Exception as e:
    print("userdata import failed:", type(e).__name__, e)
    userdata = None
if userdata is not None:
    for name in ("KAGGLE_USERNAME", "KAGGLE_KEY", "KAGGLE_API_TOKEN", "KAGGLE_JSON", "kaggle", "KAGGLE"):
        try:
            v = userdata.get(name)
            print(f"secret {name}: present, len {len(v)}")
        except Exception as e:
            print(f"secret {name}: {type(e).__name__}: {str(e)[:120]}")
print("env KAGGLE_*:", sorted(k for k in os.environ if k.startswith("KAGGLE")))
print("~/.kaggle exists:", os.path.exists(os.path.expanduser("~/.kaggle")))
