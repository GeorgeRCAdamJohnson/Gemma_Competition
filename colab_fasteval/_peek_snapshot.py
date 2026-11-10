# Runs ON the Colab VM: sizes of the env snapshot locally and on Drive.
import subprocess

print(subprocess.run("du -sh /content/venv; ls -l /content/colab_env.tar 2>/dev/null; "
                     "ls -l /content/drive/MyDrive/gemma_fasteval/colab_env/ 2>/dev/null; pgrep -fa 'tar -cf|cp /content' | cut -c1-120",
                     shell=True, capture_output=True, text=True).stdout)
