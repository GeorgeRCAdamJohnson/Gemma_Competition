"""Re-verify agent patches for the 14 src/-layout tasks in a correct sandbox.

Zero model runs: we take the patches the agent already produced and ask whether
they pass, under two verification modes.

  mode=install : pip install -e /workspace   (what the harness intends, with /wheels present)
  mode=path    : PYTHONPATH=/workspace/src   (no install at all)

Verdict follows swegemma's own rule (_validate_junit_xml): resolved requires
zero failures AND zero errors across the run, plus every test function named in
the test_patch present as a passing testcase.
"""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(os.path.dirname(HERE), "kaggle_pkg", "out_e4b")
IMAGE = os.environ.get("VERIFY_IMAGE", "gemma-verify:latest")

BASH = r"""
set -u
cd /workspace
git clone -q https://github.com/{{repo}}.git . 2>/tmp/clone.err || { echo "CLONE_FAIL"; cat /tmp/clone.err; exit 9; }
git checkout -q {{commit}} 2>/tmp/co.err || { echo "CHECKOUT_FAIL"; cat /tmp/co.err; exit 9; }

src_dir={{srcdir}}

mode={{mode}}
if [ "$mode" = "install" ]; then
  pip install -q -e "/workspace[all]" 2>/tmp/pip.err || pip install -q -e /workspace 2>/tmp/pip.err
  echo "PIP_RC=$?"
  tail -3 /tmp/pip.err 2>/dev/null
elif [ "$mode" = "broken" ]; then
  # Faithful to the old rig: a site-packages copy exists, the editable install
  # silently did not happen. This is what made the "phantoms" possible.
  pip install -q urllib3 certifi idna charset_normalizer {{pypiname}}=={{oldver}} 2>/tmp/pip.err
  echo "SITEPKG_ONLY rc=$?"
else
  export PYTHONPATH=/workspace/{{srcdir}}:/workspace
fi

if [ "$mode" != "broken" ]; then
  for rf in requirements-tests.txt requirements_test.txt requirements-dev.txt; do
    if [ -f "$rf" ]; then
      pip install -q -r "$rf" 2>/tmp/req.err && echo "REQ_OK $rf" || { echo "REQ_FAIL $rf"; tail -3 /tmp/req.err; }
    fi
  done
fi

git apply -q /patches/test.patch 2>/tmp/tp.err || git apply --recount -q /patches/test.patch 2>/tmp/tp.err || { echo "TEST_PATCH_FAIL"; cat /tmp/tp.err; exit 9; }
if [ -s /patches/agent.patch ]; then
  git apply -q /patches/agent.patch 2>/tmp/ap.err || git apply --recount -q /patches/agent.patch 2>/tmp/ap.err || { echo "AGENT_PATCH_FAIL"; cat /tmp/ap.err; exit 9; }
fi

echo "IMPORT_CHECK=$(python -c 'import {{mod}}; print({{mod}}.__file__)' 2>&1)"

{{shim}}if [ -f /workspace/conftest.py ]; then echo "SHIM_PRESENT"; fi

python -m pytest {{tests}} -q -p no:cacheprovider -p no:asyncio \
  --junitxml=/tmp/j.xml -o addopts="" 2>&1 | tail -15
echo "---JUNIT---"
python - <<'PY'
import xml.etree.ElementTree as ET
try:
    r = ET.parse('/tmp/j.xml').getroot()
except Exception as e:
    print('NO_JUNIT', e); raise SystemExit
s = [r] if r.tag == 'testsuite' else r.findall('.//testsuite')
t = sum(int(x.attrib.get('tests', 0)) for x in s)
f = sum(int(x.attrib.get('failures', 0)) for x in s)
e = sum(int(x.attrib.get('errors', 0)) for x in s)
k = sum(int(x.attrib.get('skipped', 0)) for x in s)
print('JUNIT tests=%d failures=%d errors=%d skipped=%d' % (t, f, e, k))
for tc in r.findall('.//testcase'):
    bad = tc.find('failure') if tc.find('failure') is not None else tc.find('error')
    if bad is not None:
        msg = (bad.attrib.get('message') or '').strip().replace('\n', ' ')[:110]
        print('  BAD %s :: %s' % (tc.attrib.get('name', '?')[:60], msg))
PY
"""


def test_files(test_patch):
    return sorted({m for m in re.findall(r"^\+\+\+ b/(.+)$", test_patch, re.M)
                   if m.startswith("tests/") or "/test" in m})


def required_nodes(test_patch):
    """Approximation of _extract_test_functions_from_patch."""
    nodes = set()
    for line in test_patch.splitlines():
        m = re.match(r"^\+\s*(?:async\s+)?def\s+(test_\w+)", line)
        if m:
            nodes.add(m.group(1))
    return sorted(nodes)


SHIM = """cat > /workspace/conftest.py <<'CONFTEST'
import os
import sys

_root = os.path.dirname(os.path.abspath(__file__))
_src = os.path.join(_root, "src")
if os.path.isdir(_src) and _src not in sys.path:
    sys.path.insert(0, _src)
CONFTEST
"""


def run_task(tid, task, agent_patch, mode):
    if mode.endswith("-noagent"):
        agent_patch = ""
        mode = mode[: -len("-noagent")]
    use_shim = "+shim" in mode
    if use_shim:
        mode = mode.replace("+shim", "")
    pkg = task["repo"].split("/")[1]
    stage = tempfile.mkdtemp(prefix="rev_")
    try:
        io.open(os.path.join(stage, "test.patch"), "w", encoding="utf-8",
                newline="\n").write(task["test_patch"].rstrip("\n") + "\n")
        io.open(os.path.join(stage, "agent.patch"), "w", encoding="utf-8",
                newline="\n").write(agent_patch.rstrip("\n") + "\n" if agent_patch.strip() else "")
        tfs = test_files(task["test_patch"])
        script = BASH
        for k, v in {
            "repo": task["repo"], "commit": task["base_commit"], "srcdir": "src",
            "mode": mode, "mod": pkg,
            "tests": " ".join(tfs) if tfs else "tests",
            "shim": SHIM if use_shim else "",
            "pypiname": pkg,
            "oldver": "0.27.0" if pkg == "httpx" else "2.31.0",
        }.items():
            script = script.replace("{{" + k + "}}", v)
        win = stage.replace("\\", "/")
        cmd = ["docker", "run", "--rm", "-v", "%s:/patches" % win, IMAGE, "bash", "-lc", script]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        out = (p.stdout or "") + (p.stderr or "")
        m = re.search(r"JUNIT tests=(\d+) failures=(\d+) errors=(\d+)", out)
        if not m:
            verdict = "NO_JUNIT"
        elif int(m.group(2)) or int(m.group(3)):
            verdict = "FAIL"
        else:
            verdict = "PASS?"
        imp = re.search(r"IMPORT_CHECK=(\S+)", out)
        label = mode + ("+shim" if use_shim else "")
        return {"task": tid, "repo": task["repo"], "mode": label, "verdict": verdict,
                "import_from": imp.group(1) if imp else "?", "raw": out[-2500:]}
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    mode = sys.argv[2] if len(sys.argv) > 2 else "path"
    tasks = {}
    for line in io.open(os.path.join(RUN, "tasks.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        tasks[r["instance_id"]] = r
    if only and only != "all":
        keep = set(only.split(","))
        tasks = {k: v for k, v in tasks.items() if k in keep}
    else:
        tasks = {k: v for k, v in tasks.items()
                 if k.startswith(("requests_", "httpx_"))}
    results = []
    for tid in sorted(tasks):
        if only and "," not in only and only != "all" and tid != only:
            continue
        ap = os.path.join(RUN, "results", "patches", tid + ".patch")
        agent = io.open(ap, encoding="utf-8", errors="replace").read() if os.path.exists(ap) else ""
        r = run_task(tid, tasks[tid], agent, mode)
        results.append(r)
        print("%-16s %-9s %-8s import=%s" % (r["task"], r["mode"], r["verdict"], r["import_from"]))
        if r["verdict"] != "PASS?":
            tail = "\n".join(r["raw"].strip().splitlines()[-8:])
            print("   " + tail.replace("\n", "\n   "))
    io.open(os.path.join(HERE, "reverify_src_layout_%s.json" % mode), "w",
            encoding="utf-8").write(json.dumps(results, indent=1))
    print()
    print("verdicts:", {v: sum(1 for r in results if r["verdict"] == v)
                        for v in ("PASS?", "FAIL", "NO_JUNIT")})


if __name__ == "__main__":
    main()
