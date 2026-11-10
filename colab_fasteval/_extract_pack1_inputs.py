"""Extract the EXACT inputs the Kaggle pack-1 validation kernel ran with (embedded in its notebook): tasks.jsonl
and the ARM_P1_retry_fresh agent bundle. Writes colab_fasteval/_smoke_inputs/{tasks.jsonl, agent_pack1/...} and
prints the bundle fingerprint computed the same way as the kernel (sha1 over sorted file bytes)."""
import base64
import gzip
import hashlib
import json
import re
import shutil
from pathlib import Path

NB = Path("kaggle_pkg/push_e4b_pack1_val/e4b-pack1-val.ipynb")
OUT = Path("colab_fasteval/_smoke_inputs")
nb = json.loads(NB.read_text(encoding="utf-8"))
c2 = "".join(nb["cells"][2]["source"])
arms = json.loads(re.search(r'ARMS = json\.loads\("""(.*?)"""\)', c2, re.S).group(1))
print("arms:", list(arms))
files = arms["ARM_P1_retry_fresh"]
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)
(OUT / "tasks.jsonl").write_bytes(gzip.decompress(base64.b64decode(files["tasks.jsonl_gz"])))
n = sum(1 for l in (OUT / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip())
print("tasks:", n, "| sha1", hashlib.sha1((OUT / "tasks.jsonl").read_bytes()).hexdigest()[:12])
a = OUT / "agent_pack1"
for rel, b64 in files.items():
    if rel == "tasks.jsonl_gz":
        continue
    d = a / rel
    d.parent.mkdir(parents=True, exist_ok=True)
    d.write_bytes(base64.b64decode(b64))
# same method as kaggle_pkg/_check_pack_ab.py: sha1 over file bytes ordered by relative-path STRING
fs = {p.relative_to(a).as_posix(): p.read_bytes() for p in a.rglob("*") if p.is_file()}
sha = hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12]
print("agent files:", sorted(fs))
print("agent bundle sha:", sha, "OK" if sha == "84f904c63afd" else "MISMATCH want 84f904c63afd")
