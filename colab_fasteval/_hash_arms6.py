# Runs ON the VM: sha1[:12] of every arm under /content/work/arms6 (same recipe as prep) + the task list.
import hashlib
import json
import pathlib

for a in sorted(pathlib.Path("/content/work/arms6").iterdir()):
    fs = {p.relative_to(a).as_posix(): p.read_bytes() for p in a.rglob("*") if p.is_file()}
    print("arm", a.name, hashlib.sha1(b"".join(fs[n] for n in sorted(fs))).hexdigest()[:12])
print("tasks", json.load(open("/content/work/ab_tasks.json")))
