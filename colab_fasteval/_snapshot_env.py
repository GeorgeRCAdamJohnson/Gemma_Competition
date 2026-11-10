# Runs ON the Colab VM: save the Kaggle-matched env (venv + uv-managed CPython 3.12 it links to) to Drive, plus a
# full freeze for the record. Restore on another VM with _restore_env.py (same absolute paths). Background job.
import subprocess
from pathlib import Path

SCRIPT = r'''
set -u
T0=$(date +%s)
D=/content/drive/MyDrive/gemma_fasteval/colab_env
mkdir -p $D
/content/venv/bin/python -m pip --version >/dev/null 2>&1 || true
uv pip freeze --python /content/venv/bin/python > $D/freeze_colab_env.txt 2>/dev/null || /content/venv/bin/python -m pip freeze > $D/freeze_colab_env.txt
PYDIR=$(readlink -f /content/venv/bin/python | sed 's#/bin/python.*##')
echo "python home: $PYDIR"
echo "$PYDIR" > $D/python_home.txt
# the venv links to the image's own /usr/bin/python3.12 (present on every Colab VM), so archive the venv only
if [ "$PYDIR" = "/usr" ]; then tar -cf /content/colab_env.tar /content/venv; else tar -cf /content/colab_env.tar /content/venv "$PYDIR"; fi
ls -l /content/colab_env.tar
cp /content/colab_env.tar $D/colab_env.tar.partial && mv $D/colab_env.tar.partial $D/colab_env.tar
ls -l $D
echo "elapsed $(( $(date +%s) - T0 ))s"
echo 0 > /content/snapshot.done
'''
Path("/content/snapshot.sh").write_text(SCRIPT)
Path("/content/snapshot.done").unlink(missing_ok=True)
subprocess.Popen("nohup bash /content/snapshot.sh > /content/snapshot.log 2>&1 &", shell=True)
print("started snapshot job")
