# Runs ON the Colab VM: stop a running overlay job (and its uv children) before restarting it.
import subprocess

print(subprocess.run("pkill -f overlay.sh; pkill -f 'uv pip install'; pkill -f 'dlib|cmake|ninja'; sleep 2; "
                     "pgrep -fa 'overlay.sh|uv pip|cmake' || echo stopped",
                     shell=True, capture_output=True, text=True).stdout)
