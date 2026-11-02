"""Why does `import requests` resolve to /workspace/src in `broken` mode?"""
import io
import json
import os
import subprocess
import tempfile

RUN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "kaggle_pkg", "out_e4b")

task = None
for line in io.open(os.path.join(RUN, "tasks.jsonl"), encoding="utf-8"):
    r = json.loads(line)
    if r["instance_id"] == "requests_7309":
        task = r
        break

stage = tempfile.mkdtemp(prefix="dbg2_")
io.open(os.path.join(stage, "test.patch"), "w", encoding="utf-8",
        newline="\n").write(task["test_patch"].rstrip("\n") + "\n")
ap = os.path.join(RUN, "results", "patches", "requests_7309.patch")
io.open(os.path.join(stage, "agent.patch"), "w", encoding="utf-8",
        newline="\n").write(io.open(ap, encoding="utf-8", errors="replace").read().rstrip("\n") + "\n")

script = """
cd /workspace
git clone -q https://github.com/{repo}.git . || exit 9
git checkout -q {commit} || exit 9
echo "=== root listing ==="
ls -a | head -25
echo "=== pip install site-packages copy ==="
pip install -q urllib3 certifi idna charset_normalizer requests==2.31.0 2>&1 | tail -3
echo "rc=$?"
echo "=== pip show ==="
pip show requests 2>&1 | head -6
echo "=== import without any patches ==="
python -c "import requests, sys; print('LOC', requests.__file__); print('PATH', sys.path[:5])"
echo "=== root conftest.py? ==="
ls -l conftest.py 2>&1
echo "=== setup.cfg / pyproject ==="
ls -l setup.py setup.cfg pyproject.toml 2>&1
""".format(repo=task["repo"], commit=task["base_commit"])

win = stage.replace("\\", "/")
p = subprocess.run(["docker", "run", "--rm", "-v", win + ":/patches", "gemma-verify:latest",
                    "bash", "-lc", script], capture_output=True, text=True, timeout=600)
print(p.stdout)
print(p.stderr[-1500:])
