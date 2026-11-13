# Runs ON a GPU VM via `colab exec --timeout 0` (the CLI holds ONE long connection; Colab reclaims VMs after a few
# minutes with no client connection, whatever the kernel is doing -- the API exec stream is cut at ~5 min, which is how
# e4bloc2 was lost on 2026-11-12). Same stop rules as _keepalive.py, plus: once prep SUCCEEDED (log has PREP DONE and
# IMPORTS) and no driver/out dir exists, launch the driver from /content/launch.json (via /content/launch_if_ready.py).
import glob
import os
import runpy
import time
from pathlib import Path

PREP_MAX_MIN, STALL_MIN, HARD_MAX_H = 40, 75, 12
T0 = time.time()
cfg_out = None


def alive(f):
    try:
        return os.path.exists(f"/proc/{Path(f).read_text().strip()}")
    except Exception:
        return False


def prep_ok():
    log = Path("/content/prep.log")
    t = log.read_text(errors="replace") if log.exists() else ""
    return Path("/content/prep.done").exists() and "PREP DONE" in t and "IMPORTS" in t


launched = False
while True:
    el = (time.time() - T0) / 60
    prepping = not Path("/content/prep.done").exists() and el < PREP_MAX_MIN
    pids = [f for f in glob.glob("/content/ab*.pid") if alive(f)]
    outs = [Path(p) for p in glob.glob("/content/ab*") if Path(p).is_dir()]
    if not launched and prep_ok() and not pids and outs:
        launched = True  # re-attached after a dropped connection: the driver already ran here; never relaunch it
    if not launched and prep_ok() and not pids:
        try:
            runpy.run_path("/content/launch_if_ready.py")
        except SystemExit:
            pass
        launched = True
        time.sleep(5)
        continue
    if Path("/content/prep.done").exists() and not prep_ok() and not pids:
        print(time.strftime("%H:%M:%S"), "stop: prep finished but FAILED -- see /content/prep.log", flush=True)
        break
    pending = [o for o in outs if (o / "progress.json").exists() and not (o / "ALL_DONE").exists()]
    newest = max([(o / "progress.json").stat().st_mtime for o in outs if (o / "progress.json").exists()] or [0])
    stalled = bool(newest) and (time.time() - newest) / 60 > STALL_MIN
    booting = launched and bool(pids) and not pending  # driver up, vLLM booting / first pass running
    if el / 60 > HARD_MAX_H or stalled or not (prepping or pids or pending or booting):
        print(time.strftime("%H:%M:%S"), f"stop: prepping {prepping} drivers {len(pids)} pending {len(pending)} "
              f"stalled {stalled} elapsed {el:.0f}m", flush=True)
        break
    print(time.strftime("%H:%M:%S"), f"keep: prepping {prepping} drivers {len(pids)} pending {[o.name for o in pending]}",
          flush=True)
    time.sleep(60)
