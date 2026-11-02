"""Debug why a test_patch fails to apply."""
import io
import json
import os
import subprocess
import tempfile

RUN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "kaggle_pkg", "out_e4b")
TID = "requests_7309"

task = None
for line in io.open(os.path.join(RUN, "tasks.jsonl"), encoding="utf-8"):
    r = json.loads(line)
    if r["instance_id"] == TID:
        task = r
        break

stage = tempfile.mkdtemp(prefix="dbg_")
io.open(os.path.join(stage, "test.patch"), "w", encoding="utf-8",
        newline="\n").write(task["test_patch"])
ap = os.path.join(RUN, "results", "patches", TID + ".patch")
io.open(os.path.join(stage, "agent.patch"), "w", encoding="utf-8",
        newline="\n").write(io.open(ap, encoding="utf-8", errors="replace").read())

script = """
cd /workspace
git clone -q https://github.com/{repo}.git . || exit 9
git checkout -q {commit} || exit 9
echo "HEAD=$(git rev-parse --short HEAD)"
echo "base_commit={commit}"
git status --porcelain | head -5
echo "--- apply --check ---"
git apply --check -v /patches/test.patch 2>&1 | head -20
echo "--- try 3way ---"
git apply --3way /patches/test.patch 2>&1 | head -20
echo "--- head of file at that region ---"
sed -n '585,600p' tests/test_utils.py
""".format(repo=task["repo"], commit=task["base_commit"])

win = stage.replace("\\", "/")
p = subprocess.run(["docker", "run", "--rm", "-v", win + ":/patches", "gemma-verify:latest",
                    "bash", "-lc", script], capture_output=True, text=True, timeout=600)
print(p.stdout)
print(p.stderr[-2000:])
