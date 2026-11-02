"""Find fastapi's declared test dependencies at a task base commit."""
import io
import json
import os
import subprocess
import sys

RUN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "kaggle_pkg", "out_e4b")
WANT = sys.argv[1:] or ["fastapi_14301"]

tasks = {}
for line in io.open(os.path.join(RUN, "tasks.jsonl"), encoding="utf-8"):
    r = json.loads(line)
    if r["instance_id"] in WANT:
        tasks[r["instance_id"]] = r

for tid, task in tasks.items():
    script = """
cd /workspace
git clone -q https://github.com/{repo}.git . || exit 9
git checkout -q {commit} || exit 9
echo "=== requirements files ==="
ls -1 | grep -i -E 'require|setup|pyproject|tox' || true
echo "=== requirements-tests.txt ==="
cat requirements-tests.txt 2>/dev/null | head -40 || echo "(absent)"
echo "=== pyproject project.optional-dependencies ==="
sed -n '/optional-dependencies/,/^\\[/p' pyproject.toml 2>/dev/null | head -40
echo "=== scripts/ or requirements dir ==="
ls -1 requirements* scripts/requirements* 2>/dev/null || true
""".format(repo=task["repo"], commit=task["base_commit"])
    print("#" * 70)
    print(tid, task["base_commit"])
    p = subprocess.run(["docker", "run", "--rm", "gemma-verify:latest", "bash", "-lc", script],
                       capture_output=True, text=True, timeout=600)
    print(p.stdout)
    if p.stderr.strip():
        print("STDERR:", p.stderr[-500:])
