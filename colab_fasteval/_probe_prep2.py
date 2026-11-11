# Runs ON a GPU VM: state of a prep that never printed PREP DONE.
import os
import subprocess
from pathlib import Path

print(subprocess.run("pgrep -fa 'prep.sh|tar -xf|cp .*colab_env' | cut -c1-120; ls -l /content/colab_env.tar 2>&1; "
                     "du -sh /content/venv 2>&1 | tail -1; ls /content/venv/bin/python 2>&1; df -h /content | tail -1",
                     shell=True, capture_output=True, text=True).stdout)
print("prep.done:", Path("/content/prep.done").exists())
