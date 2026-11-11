# Runs ON a GPU VM: (re)arm a chain that, once the currently running driver (/content/ab.pid) exits, cleans the GPU and
# launches the driver for CHAIN_ARMS (written to /content/<CHAIN_OUT>, Drive tag CHAIN_TAG). Kills any earlier waiter.
# Unpacks /content/abN_inputs.tar into /content/work first (arms*, driver) if present.
import hashlib
import os
import signal
import subprocess
import tarfile
from pathlib import Path

ARMS, OUT, TAG = "arms3", "ab3", "e4b_ab3_20261110"
w = Path("/content/ab2_waiter.pid")
if w.exists():
    try:
        os.killpg(int(w.read_text().strip()), signal.SIGKILL)
        print("killed previous waiter", w.read_text().strip())
    except Exception as e:
        print("previous waiter not running:", type(e).__name__)
src = Path("/content/abN_inputs.tar")
if src.exists():
    with tarfile.open(src) as t:
        t.extractall("/content/work", filter="data")
    print("unpacked", src)
for a in sorted(Path(f"/content/work/{ARMS}").iterdir()):
    fs = {p.relative_to(a).as_posix(): p.read_bytes() for p in a.rglob("*") if p.is_file()}
    print("arm", a.name, hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12])
print("driver has AB_PORT:", "AB_PORT" in Path("/content/work/gpu_ab_run.py").read_text())
pid1 = Path("/content/ab.pid").read_text().strip()
script = f"""
while [ -e /proc/{pid1} ]; do sleep 30; done
echo "$(date +%H:%M) previous driver exited; cleaning GPU" >> /content/{OUT}.log
pkill -f 'vllm' ; sleep 10
for i in $(seq 1 60); do
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
  [ "$used" -lt 1500 ] && break
  pkill -9 -f 'vllm' ; sleep 5
done
cd /content/work
AB_ARMS={ARMS} AB_OUT=/content/{OUT} AB_TAG={TAG} /content/venv/bin/python /content/work/gpu_ab_run.py 10 20 >> /content/{OUT}.log 2>&1 &
echo $! > /content/{OUT}.pid
wait
"""
Path("/content/chain.sh").write_text(script)
p = subprocess.Popen(["bash", "/content/chain.sh"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
w.write_text(str(p.pid))
print(f"chain waiter pid {p.pid}: after driver {pid1} exits -> {ARMS} into /content/{OUT}")
