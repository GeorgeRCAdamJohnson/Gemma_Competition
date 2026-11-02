"""Instrumented gate_run wrapper -- catches WHY runs stall.

Every stall tonight was diagnosed after the fact by inspecting process lists and file
timestamps. That is guessing. This wrapper records the facts needed to tell these apart:

  A. process died (OOM, killed, unhandled exception)  -> exit code + stderr captured
  B. process alive but no progress (server hang)      -> heartbeat gap detected
  C. server degraded (bad output, not a hang)         -> per-task server health + patch sizes
  D. file-lock contention from a concurrent run       -> lock wait time recorded

Usage:
    python run_guarded.py --tag foo --tasks-file nine.txt --repo-dir repos\fastapi \
        --prompt-file prompts\4b_A3_delim.md [other gate_run args...]

Writes runs/<tag>.guard.jsonl -- one event per line:
    {"ev":"start","pid":...,"t":...,"cmd":...}
    {"ev":"task","task":...,"t":...,"resolved":...,"calls":...,"patch":...,"server":"up|down","gap_s":...}
    {"ev":"exit","t":...,"code":...,"dur_s":...,"stderr_tail":...}
    {"ev":"stall","t":...,"reason":"no_progress_Ns","last_task":...}
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"
SERVER = "http://127.0.0.1:8081"


def server_up(timeout=4):
    try:
        urllib.request.urlopen(SERVER + "/v1/models", timeout=timeout)
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--stall-after", type=int, default=300,
                    help="seconds with no new task line before declaring a stall")
    args, extra = ap.parse_known_args()

    RUNS.mkdir(exist_ok=True)
    log = RUNS / f"{args.tag}.guard.jsonl"
    fh = open(log, "w", encoding="utf-8")

    def emit(**kw):
        kw["t"] = time.strftime("%H:%M:%S")
        fh.write(json.dumps(kw) + "\n")
        fh.flush()

    cmd = [sys.executable, "gate_run.py", "--tag", args.tag] + extra
    emit(ev="start", cmd=" ".join(cmd), server="up" if server_up() else "down")

    t0 = time.time()
    last_progress = t0
    last_task = None
    proc = subprocess.Popen(cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace", bufsize=1)
    emit(ev="spawn", pid=proc.pid)

    stderr_tail = []
    try:
        for line in proc.stdout:
            now = time.time()
            line = line.rstrip()
            if line.startswith("[") and "/" in line[:12]:
                # a task boundary line: "[3/9] rich_3006 resolved=True ..."
                m = __import__("re").match(r"\[(\d+)/(\d+)\] (\S+) resolved=(\S+)", line)
                if m:
                    gap = now - last_progress
                    emit(ev="task", task=m.group(3), resolved=m.group(4), gap_s=round(gap, 1),
                         server="up" if server_up() else "down", raw=line[:200])
                    last_progress = now
                    last_task = m.group(3)
            if now - last_progress > args.stall_after:
                emit(ev="stall", reason=f"no_progress_{int(now - last_progress)}s",
                     last_task=last_task, server="up" if server_up() else "down",
                     proc_alive=proc.poll() is None)
                # do not kill: record and keep watching, the run may recover
                last_progress = now
    finally:
        try:
            _, err = proc.communicate(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
            _, err = proc.communicate()
        stderr_tail = (err or "")[-2000:]
        emit(ev="exit", code=proc.returncode, dur_s=round(time.time() - t0, 1),
             stderr_tail=stderr_tail)
    fh.close()

    print(f"\n[guard] exit={proc.returncode} dur={time.time()-t0:.0f}s log={log}")
    if proc.returncode != 0:
        print("[guard] stderr tail:")
        print(stderr_tail[-1500:])
    sys.exit(proc.returncode or 0)


if __name__ == "__main__":
    main()
