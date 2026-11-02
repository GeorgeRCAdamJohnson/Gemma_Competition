"""Monitor the A21 kernel; cancel the session once rep 4's A21 block completes.

Detection: count '-> resolved=' lines appearing AFTER the 'block rep=4 arm=A21'
header in the kernel logs. When 5 results are seen (block complete), cancel
session 362220492 via the SDK. Also exits if the session dies on its own.

Polls every 60s. Logs progress to stdout.
"""
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KERNEL = "comfyops/gemma-sibling-conform-31b-a21-arm"
SESSION_ID = 362220492
POLL_S = 60
MARKER = "block rep=4 arm=A21"


def get_logs():
    r = subprocess.run([sys.executable, "-m", "kaggle", "kernels", "logs", KERNEL],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (r.stdout or "") + (r.stderr or "")


def get_status():
    code = (
        "import sys\n"
        "sys.stdout.reconfigure(encoding='utf-8', errors='replace')\n"
        "from kaggle.api.kaggle_api_extended import KaggleApi\n"
        "from kagglesdk.kernels.services.kernels_api_service import ApiGetKernelSessionStatusRequest\n"
        "api = KaggleApi(); api.authenticate()\n"
        "with api.build_kaggle_client() as k:\n"
        "    req = ApiGetKernelSessionStatusRequest()\n"
        "    req.kernel_slug = 'gemma-sibling-conform-31b-a21-arm'\n"
        "    req.user_name = 'comfyops'\n"
        "    print(k.kernels.kernels_api_client.get_kernel_session_status(req))\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    for s in ("RUNNING", "QUEUED", "COMPLETE", "FAILED", "CANCELLED"):
        if s in out:
            return s
    return "UNKNOWN: " + out[-200:]


def cancel():
    code = (
        "import sys\n"
        "sys.stdout.reconfigure(encoding='utf-8', errors='replace')\n"
        "from kaggle.api.kaggle_api_extended import KaggleApi\n"
        "from kagglesdk.kernels.services.kernels_api_service import ApiCancelKernelSessionRequest\n"
        "api = KaggleApi(); api.authenticate()\n"
        "with api.build_kaggle_client() as k:\n"
        "    req = ApiCancelKernelSessionRequest()\n"
        "    req.kernel_session_id = %d\n"
        "    print('cancel result:', k.kernels.kernels_api_client.cancel_kernel_session(req))\n" % SESSION_ID
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print("CANCEL:", (r.stdout or "") + (r.stderr or ""))


def count_rep4_a21(logs):
    # primary: 5 results after the rep-4 A21 header
    i = logs.find(MARKER)
    if i >= 0:
        n = logs[i:].count("-> resolved=")
        if n >= 5:
            return 5
    # fallback: rep 5 header visible means rep 4 fully finished (tail may have scrolled)
    if "block rep=5" in logs:
        return 5
    return 0


print("[monitor] watching for '%s' completion (5 results), poll every %ds" % (MARKER, POLL_S))
t0 = time.time()
while True:
    try:
        status = get_status()
        if status not in ("RUNNING", "QUEUED"):
            print("[monitor] session status=%s after %.0f min -- exiting without cancel"
                  % (status, (time.time() - t0) / 60))
            break
        logs = get_logs()
        n = count_rep4_a21(logs)
        print("[monitor] t=%.0fmin status=%s rep4-A21 results=%d/5" % ((time.time() - t0) / 60, status, n))
        if n >= 5:
            print("[monitor] rep 4 complete -- CANCELING session %d" % SESSION_ID)
            cancel()
            time.sleep(10)
            print("[monitor] final status:", get_status())
            break
    except Exception as e:
        print("[monitor] error: %r -- continuing" % e)
    time.sleep(POLL_S)
print("[monitor] done")
