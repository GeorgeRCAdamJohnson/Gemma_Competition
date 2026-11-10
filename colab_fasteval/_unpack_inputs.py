# Runs ON the GPU VM: unpack tasks.jsonl + agent_pack1 + gpu_smoke_run.py into /content/work and re-verify the
# bundle fingerprint (must be 84f904c63afd = validated/submitted pack 1).
import hashlib
import tarfile
from pathlib import Path

W = Path("/content/work")
W.mkdir(parents=True, exist_ok=True)
with tarfile.open("/content/smoke_inputs.tar") as t:
    t.extractall(W)
a = W / "agent_pack1"
fs = {p.relative_to(a).as_posix(): p.read_bytes() for p in a.rglob("*") if p.is_file()}
sha = hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12]
print("bundle", sha, "OK" if sha == "84f904c63afd" else "MISMATCH")
print("tasks sha1", hashlib.sha1((W / "tasks.jsonl").read_bytes()).hexdigest()[:12], "(want f9b38bb5075c)")
print("work:", sorted(p.name for p in W.iterdir()))
