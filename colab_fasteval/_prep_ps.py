# Runs ON the VM: what is prep doing? processes, apt log, copy sizes, Drive reachability.
import subprocess

for c in ["ps -eo pid,etimes,stat,cmd | grep -E 'apt|dpkg|cp |tar |prep' | grep -v grep | cut -c1-150",
          "tail -5 /tmp/apt_venv.log 2>&1", "du -sh /content/model /content/colab_env.tar 2>&1",
          "ls -la /content/drive/MyDrive/gemma_fasteval/colab_env/ 2>&1 | head", "df -h /content | tail -1"]:
    print("$", c); print(subprocess.run(c, shell=True, capture_output=True, text=True, timeout=60).stdout)
