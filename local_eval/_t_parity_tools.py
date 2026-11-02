"""Throwaway check of the PARITY-mode tool shapes in run_local.py against the real traces. Uses repos\\rich_v only."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import run_local as R

R.set_tools_mode("kaggle")
R.REPO = R.REPOS_DIR / "rich_v"
task = R.load_task("rich_4077")
base = task["base_commit"]
R.reset_repo(base)


def show(label, res, keys_only=False):
    s = json.dumps(res)
    if keys_only:
        print(f"{label}: keys={list(res.keys())}")
    else:
        print(f"{label}: {s[:260]}{' ...' if len(s) > 260 else ''}")


print("== read_file ==")
r = R.tool_read_file(path="rich/console.py", start_line=10, end_line=20)
show("explicit end 10-20", {k: v for k, v in r.items() if k != "content"})
r = R.tool_read_file(path="rich/console.py")
show("default (no end)", {k: v for k, v in r.items() if k != "content"})
r = R.tool_read_file(path="rich/console.py", start_line=1, end_line=400)
show("explicit end 400 (cap 150)", {k: v for k, v in r.items() if k != "content"})
r = R.tool_read_file(path="rich/nope.py")
show("not found", r)
r = R.tool_read_file(path="rich/console.py", start_line=99999)
show("start beyond total", r)
r = R.tool_read_file(path="../secret.txt")
show("dotdot", r)
r = R.tool_read_file(path="/workspace/rich/console.py", start_line=1, end_line=3)
show("/workspace prefix", {k: v for k, v in r.items() if k != "content"})

print("== write_file ==")
show("/tmp/x.py", R.tool_write_file(filepath="/tmp/x.py", content="print(1)\n"))
show("a/../../b.py", R.tool_write_file(filepath="a/../../b.py", content="x=1\n"))
show("notes.py", R.tool_write_file(filepath="notes.py", content="x = 1\n"))
show("tests/test_probe.py", R.tool_write_file(filepath="tests/test_probe.py", content="def test_x():\n    pass\n"))
show("test_root.py", R.tool_write_file(filepath="test_root.py", content="def test_x():\n    pass\n"))
show("conftest.py", R.tool_write_file(filepath="conftest.py", content="# c\n"))

print("== edit_file ==")
r = R.tool_edit_file(path="rich/console.py", old_string="import inspect\n", new_string="import inspect\nimport inspect as _insp  # probe\n")
show("edit ok", {k: (v if k != "diff" else v[:60]) for k, v in r.items()}, keys_only=False)
print("   key order:", list(r.keys()))
show("edit identical", R.tool_edit_file(path="rich/console.py", old_string="import inspect\n", new_string="import inspect\n"))
show("edit ../", R.tool_edit_file(path="../x.py", old_string="a", new_string="b"))

print("== final_patch ==")
p = R.final_patch(base)
heads = [l for l in p.splitlines() if l.startswith("diff --git")]
print("   sections:", heads)
print("   protected stripped:", not any("test_root" in h or "tests/test_probe" in h or "conftest" in h for h in heads))
R.reset_repo(base)
st = R.git(["status", "--porcelain"]).stdout
print("   status after reset_repo (expect empty):", repr(st))

print("== run_command ==")
show("ok", R.tool_run_command("echo hello; echo err 1>&2"))
show("fail", R.tool_run_command("echo out; echo bad 1>&2; exit 3"))
show("grep no match", R.tool_run_command("grep -n zzzzqqqq rich/console.py"))
show("ws cd/pwd", R.tool_run_command("cd /workspace && pwd && ls | head -3"))
show("ws grep path", R.tool_run_command("grep -n 'import inspect' /workspace/rich/console.py"))
r = R.tool_run_command("python3 -c \"print('x'*7000)\"")
print("   long stdout len:", len(r.get("stdout", "")), "tail:", repr(r.get("stdout", "")[-5:]))
t = time.time()
show("cat (stdin closed)", R.tool_run_command("cat"))
print("   cat took %.1fs" % (time.time() - t))
R.CMD_TIMEOUT = 3
t = time.time()
show("timeout", R.tool_run_command("python3 -c 'import time; time.sleep(30)'"))
print("   timeout call took %.1fs" % (time.time() - t))
R.CMD_TIMEOUT = 240
show("python3 isatty", R.tool_run_command("python3 -c \"import sys; print(sys.stdout.fileno())\""))
R.reset_repo(base)
print("done")
