# Runs ON a GPU VM in its own kernel: keep the kernel active (Colab keeps a runtime alive while a kernel is busy) ONLY
# while A/B work is genuinely pending. Stops when every batch that was started has its ALL_DONE marker, when no driver
# is alive, or when no pass has finished for STALL_MIN minutes (a hung driver must not keep an idle GPU billing).
import glob
import os
import time
from pathlib import Path

STALL_MIN = 75  # a pass takes 13-21 min; 75 min without a finished pass = hung


def alive(f):
    try:
        return os.path.exists(f"/proc/{Path(f).read_text().strip()}")
    except Exception:
        return False


while True:
    pids = [f for f in glob.glob("/content/ab*.pid") if alive(f)]
    outs = [Path(p) for p in glob.glob("/content/ab*") if Path(p).is_dir()]
    pending = [o for o in outs if (o / "progress.json").exists() and not (o / "ALL_DONE").exists()]
    newest = max([(o / "progress.json").stat().st_mtime for o in outs if (o / "progress.json").exists()] or [0])
    stalled = newest and (time.time() - newest) / 60 > STALL_MIN
    if not pids or (not pending and outs) or stalled:
        print(time.strftime("%H:%M:%S"), f"stop keep-alive: drivers alive {len(pids)}, pending {len(pending)}, "
              f"stalled {bool(stalled)}", flush=True)
        break
    print(time.strftime("%H:%M:%S"), f"alive: drivers {len(pids)}, pending batches {[o.name for o in pending]}", flush=True)
    time.sleep(120)
