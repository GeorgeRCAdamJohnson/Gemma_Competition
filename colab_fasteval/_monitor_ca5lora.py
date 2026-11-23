"""Watch the 31B six-arm A/B from this machine (the connector UI froze): every 5 minutes read progress.json on Drive and
`colab usage`, append a line to Outputs/ca5lora_monitor.log, and when all six passes are recorded print the summary.
Read-only; stops itself after 6 passes or 14 h. usage: python colab_fasteval/_monitor_lb022.py"""
import json
import subprocess
import time
from pathlib import Path

RUN = Path(r"G:\My Drive\gemma_fasteval\ab_runs\31b_ca5lora_20261123")
LOG = Path("Outputs/ca5lora_monitor.log")
ARMS = ["A_ca5", "G_ca5_ayush"]  # x 2 rounds
t_end = time.time() + 14 * 3600


def write(line):
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def usage():
    try:
        out = subprocess.run(["wsl", "-d", "Ubuntu", "--", "bash", "-c", "~/colabw usage 2>&1"],
                             capture_output=True, text=True, timeout=90).stdout
        keep = [l.split(":", 1)[1].strip() for l in out.splitlines()
                if l.startswith(("Current balance", "Usage rate", "Active assignments"))]
        return " | ".join(keep) or "usage unavailable"
    except Exception as e:  # noqa: BLE001
        return f"usage error {type(e).__name__}"


seen = 0
while time.time() < t_end:
    try:
        passes = json.loads((RUN / "progress.json").read_text(encoding="utf-8"))["passes"]
    except Exception as e:  # noqa: BLE001
        passes = []
        write(f"{time.strftime('%H:%M:%S')} progress.json unreadable: {type(e).__name__}")
    done = [p["arm"] for p in passes]
    for p in passes[seen:]:
        write(f"{time.strftime('%H:%M:%S')} PASS DONE {p['arm']}: solved {p['solved']}/{p['n']} in {p['seconds'] / 60:.0f} min")
    seen = len(passes)
    nxt = f"{len(passes) + 1} of 4"
    write(f"{time.strftime('%H:%M:%S')} passes {len(passes)}/4 | running {nxt or '-'} | {usage()}")
    if len(passes) >= 4:
        write("ALL FOUR PASSES ON DRIVE. Delete the Colab runtime now (it keeps billing).")
        print(subprocess.run(["python", "Outputs/_ca5lora_summary.py"], capture_output=True, text=True).stdout)
        break
    time.sleep(300)
