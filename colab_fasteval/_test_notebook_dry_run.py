"""Run the notebook's dry-run cells locally against Drive for Desktop (G:\\My Drive), so the CPU path is tested before
anyone connects a runtime. Paths are remapped; bash -n goes through WSL. Writes nothing to Drive.
usage: python colab_fasteval/_test_notebook_dry_run.py"""
import json
import tempfile
from pathlib import Path

nb = json.loads(Path("colab_fasteval/run_31b_lb022_v3.ipynb").read_text(encoding="utf-8"))
code = ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]
tmp = Path(tempfile.mkdtemp(prefix="lb022_dry_"))
remap = [("/content/drive/MyDrive", "G:/My Drive"), ("/tmp/lb022_dry", tmp.as_posix()),
         ("shutil.disk_usage('/content')", "shutil.disk_usage('C:/')"),
         ("['bash', '-n', str(BASE / 'prep.sh')]",
          "['wsl', '-d', 'Ubuntu', '--', 'bash', '-n', '/mnt/' + str(BASE / 'prep.sh').replace(chr(92), '/').replace(':', '', 1).lower()[0] + str(BASE / 'prep.sh').replace(chr(92), '/')[2:]]"),
         ("['python3', str(BASE / '_verify_model_dir.py')", "['python', str(BASE / '_verify_model_dir.py')")]
env = {}
for i, src in enumerate(code):
    for a, b in remap:
        src = src.replace(a, b)
    if i == 0:
        src = src.replace('DRIVE_CONSENT = ""', 'DRIVE_CONSENT = "ready"')
    print(f"===== code cell {i}")
    exec(compile(src, f"cell{i}", "exec"), env)
print("local dry-run harness finished; temp dir", tmp)
