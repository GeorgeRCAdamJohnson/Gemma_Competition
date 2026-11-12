# Runs ON a GPU VM in its own kernel: keep the kernel ACTIVE (Colab reclaims runtimes whose kernels sit idle; two VMs were
# lost mid-prep on 2026-11-11/12) from VM creation through prep AND the A/B run. Stays alive while: prep is running or not
# yet started (up to PREP_MAX_MIN), or a driver is alive, or a started batch has no ALL_DONE. Stops when every started batch
# is done, or after STALL_MIN without a finished pass (a hung driver must not keep a GPU billing), or at HARD_MAX_H.
import glob
import os
import time
from pathlib import Path

PREP_MAX_MIN, STALL_MIN, HARD_MAX_H = 40, 75, 12
T0 = time.time()


def alive(f):
    try:
        return os.path.exists(f"/proc/{Path(f).read_text().strip()}")
    except Exception:
        return False


while True:
    el = (time.time() - T0) / 60
    prepping = not Path("/content/prep.done").exists() and el < PREP_MAX_MIN
    pids = [f for f in glob.glob("/content/ab*.pid") if alive(f)]
    outs = [Path(p) for p in glob.glob("/content/ab*") if Path(p).is_dir()]
    pending = [o for o in outs if (o / "progress.json").exists() and not (o / "ALL_DONE").exists()]
    newest = max([(o / "progress.json").stat().st_mtime for o in outs if (o / "progress.json").exists()] or [0])
    stalled = bool(newest) and (time.time() - newest) / 60 > STALL_MIN
    launched_recently = Path("/content/prep.done").exists() and not outs and el < PREP_MAX_MIN + 30
    if el / 60 > HARD_MAX_H or stalled or not (prepping or pids or pending or launched_recently):
        print(time.strftime("%H:%M:%S"), f"stop: prepping {prepping} drivers {len(pids)} pending {len(pending)} "
              f"stalled {stalled} elapsed {el:.0f}m", flush=True)
        break
    print(time.strftime("%H:%M:%S"), f"keep: prepping {prepping} drivers {len(pids)} pending {[o.name for o in pending]}",
          flush=True)
    time.sleep(60)
