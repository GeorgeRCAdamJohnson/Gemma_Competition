# Runs ON the GPU VM: (re)arm the batch-2 chain. Kills any earlier waiter, then starts a detached waiter that, once the
# batch-1 driver exits: kills leftover vLLM, waits for GPU memory to free, launches the batch-2 driver, writes its pid.
import hashlib
import os
import signal
import subprocess
import tarfile
from pathlib import Path

w = Path("/content/ab2_waiter.pid")
if w.exists():
    try:
        os.killpg(int(w.read_text().strip()), signal.SIGKILL)
        print("killed previous waiter", w.read_text().strip())
    except Exception as e:
        print("previous waiter not running:", type(e).__name__)
if not Path("/content/work/arms2").exists():
    with tarfile.open("/content/ab2_inputs.tar") as t:
        t.extractall("/content/work", filter="data")
for a in sorted(Path("/content/work/arms2").iterdir()):
    fs = {p.relative_to(a).as_posix(): p.read_bytes() for p in a.rglob("*") if p.is_file()}
    print("arm", a.name, hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12])
pid1 = Path("/content/ab.pid").read_text().strip()
script = f"""
while [ -e /proc/{pid1} ]; do sleep 30; done
echo "$(date +%H:%M) batch-1 driver exited; cleaning GPU" >> /content/ab2.log
pkill -f 'vllm.entrypoints' ; pkill -f 'vllm serve' ; sleep 10
for i in $(seq 1 60); do
  used=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)
  [ "$used" -lt 1500 ] && break
  pkill -9 -f 'vllm' ; sleep 5
done
echo "$(date +%H:%M) GPU memory used: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)" >> /content/ab2.log
cd /content/work
AB_ARMS=arms2 AB_OUT=/content/ab2 AB_TAG=e4b_ab2_20261110 /content/venv/bin/python /content/work/gpu_ab_run.py 10 20 >> /content/ab2.log 2>&1 &
echo $! > /content/ab2.pid
wait
"""
Path("/content/chain2.sh").write_text(script)
p = subprocess.Popen(["bash", "/content/chain2.sh"], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
w.write_text(str(p.pid))
print("batch-2 waiter pid", p.pid, "| waits on batch-1 driver pid", pid1)
