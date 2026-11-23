"""Generate colab_fasteval/run_side_status.ipynb: a second notebook to open on the SAME Colab server while a run
notebook is busy (its own kernel on the same VM, like a terminal). Cell 1 starts the live-status writer if it is not
running; cell 2 prints the current status; cell 3 runs any shell command. Read-only on the run.
usage: python colab_fasteval/_build_side_notebook.py"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def code(i, src):
    return {"cell_type": "code", "id": f"side-{i:02d}", "metadata": {}, "execution_count": None, "outputs": [],
            "source": src.strip("\n").splitlines(keepends=True)}


cells = [
    {"cell_type": "markdown", "id": "side-00", "metadata": {}, "source": [
        "# Side panel for a running Colab A/B\n",
        "Open this while the run notebook is busy and select the **same Colab server** (Select Kernel > Colab > the\n",
        "server already in use, not a new one). It runs in its own kernel on the same VM. Set `TAG` to the run's tag.\n"]},
    code(1, """
TAG = '31b_ca5lora_20261123'
import shutil, subprocess
from pathlib import Path
running = subprocess.run("pgrep -f live_status.py", shell=True, capture_output=True, text=True).stdout.split()
if running:
    print('live status already running, pid', running)
else:
    src = Path(f'/content/drive/MyDrive/gemma_fasteval/launch/{TAG}/_live_status.py')
    shutil.copyfile(src, '/content/live_status.py')
    subprocess.Popen(f'nohup /content/venv/bin/python /content/live_status.py {TAG} 120 > /content/live_status.log 2>&1 &',
                     shell=True)
    print('live status started; Drive ab_runs/' + TAG + '/live_status.txt every 2 min')
"""),
    code(2, """
# current status: driver, per-arm progress, vLLM speed, log tail (returns immediately; rerun any time)
import json, time
from pathlib import Path
live = Path(f'/content/drive/MyDrive/gemma_fasteval/ab_runs/{TAG}/live_status.txt')
print(live.read_text() if live.exists() else 'live status not written yet')
prog = Path('/content/ab/progress.json')
print('passes on record:', [(p['arm'], p['round'], p['solved']) for p in json.loads(prog.read_text())['passes']]
      if prog.exists() else 'none yet')
"""),
    code(3, """
# any shell command on the VM, e.g. tail of the driver log or GPU state
!tail -n 5 /content/ab.log; nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
"""),
]
nb = {"cells": cells,
      "metadata": {"kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"},
                   "language_info": {"name": "python", "pygments_lexer": "ipython3", "version": "3.12"}},
      "nbformat": 4, "nbformat_minor": 5}
out = ROOT / "colab_fasteval" / "run_side_status.ipynb"
out.write_text(json.dumps(nb, indent=1) + "\n", encoding="utf-8", newline="\n")
print("wrote", out)
