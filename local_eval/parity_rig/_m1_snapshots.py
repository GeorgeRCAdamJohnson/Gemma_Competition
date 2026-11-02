"""Build snapshot tarballs for the M1 batch cohort (LF-exact clone, contents at tar root).
Skips tasks whose snapshot already exists (rich_4077 was built earlier)."""
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
G = Path(r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma")
COHORT = ["rich_3006", "rich_3454", "rich_3518", "rich_3905", "rich_4077", "rich_3777", "rich_3882"]
snaps = G / "local_eval" / "snapshots"
snaps.mkdir(exist_ok=True)

tasks = {}
for l in open(G / "comp_files" / "tasks.jsonl", encoding="utf-8"):
    if l.strip():
        d = json.loads(l)
        tasks[d["instance_id"]] = d

for tid in COHORT:
    out = snaps / f"{tid}.tgz"
    if out.exists():
        print("skip (exists):", tid)
        continue
    t = tasks[tid]
    sha = t["base_commit"]
    repo_name = t["repo"].split("/")[-1]
    repo = G / "local_eval" / "repos" / repo_name
    if not repo.is_dir():
        print("MISSING REPO:", repo_name, "for", tid)
        continue
    tmp = G / "local_eval" / "_snap_build" / tid
    if tmp.exists():
        shutil.rmtree(tmp)
    t0 = time.time()
    r = subprocess.run(
        ["git", "clone", "-c", "core.autocrlf=false", "-c", "core.eol=lf",
         "--no-hardlinks", str(repo), str(tmp)],
        capture_output=True, text=True)
    if r.returncode != 0:
        print("clone failed:", tid, r.stderr[-200:])
        continue
    r = subprocess.run(["git", "-C", str(tmp), "checkout", "-q", "--detach", sha],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("checkout failed:", tid, sha, r.stderr[-200:])
        shutil.rmtree(tmp, ignore_errors=True)
        continue
    st = subprocess.run(
        ["git", "-C", str(tmp), "-c", "core.autocrlf=false", "status", "--porcelain"],
        capture_output=True, text=True)
    if st.stdout.strip():
        print("WARNING dirty status:", tid, repr(st.stdout[:120]))
    with tarfile.open(out, "w:gz") as tar:
        for entry in os.listdir(tmp):
            tar.add(tmp / entry, arcname=entry)
    shutil.rmtree(tmp)
    print("built: %-14s %s  %.0fs  %.1f MB" % (tid, sha[:10], time.time() - t0,
                                                out.stat().st_size / 1e6))
print("done")
