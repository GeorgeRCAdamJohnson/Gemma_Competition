"""Build snapshots for ALL 129 tasks (fastest path): clone each repo ONCE, then per task
`checkout --detach <base_commit>` + tar the contents (incl .git), exactly the LF-safe
recipe validated for the 7-task cohort. Skips existing snapshots. Also clones missing
repos (psf/requests, encode/httpx) from GitHub first."""
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
REPOS = G / "local_eval" / "repos"
SNAPS = G / "local_eval" / "snapshots"
SNAPS.mkdir(exist_ok=True)

tasks = {}
for l in open(G / "comp_files" / "tasks.jsonl", encoding="utf-8"):
    if l.strip():
        d = json.loads(l)
        tasks[d["instance_id"]] = d

# 1) ensure repos exist
for repo in sorted({t["repo"] for t in tasks.values()}):
    name = repo.split("/")[1]
    local = REPOS / name
    if not local.is_dir():
        print("cloning https://github.com/%s -> %s" % (repo, local), flush=True)
        r = subprocess.run(["git", "clone", "--no-hardlinks", "https://github.com/%s.git" % repo, str(local)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print("CLONE FAILED:", r.stderr[-300:], flush=True)
        else:
            print("cloned", name, flush=True)

# 2) build missing snapshots, shared working clone per repo
by_repo = {}
for tid, t in tasks.items():
    out = SNAPS / f"{tid}.tgz"
    if out.exists():
        continue
    by_repo.setdefault(t["repo"].split("/")[1], []).append((tid, t["base_commit"]))

t_all = time.time()
for name, items in sorted(by_repo.items()):
    work = G / "local_eval" / "_snap_build" / ("shared_" + name)
    if work.exists():
        shutil.rmtree(work)
    src = REPOS / name
    if not src.is_dir():
        print("SKIP repo %s (missing) - %d tasks unbuilt" % (name, len(items)), flush=True)
        continue
    # worktree-style standalone copy: plain clone (object copy) once
    r = subprocess.run(["git", "clone", "-c", "core.autocrlf=false", "-c", "core.eol=lf",
                        "--no-hardlinks", str(src), str(work)], capture_output=True, text=True)
    if r.returncode != 0:
        print("clone failed for", name, r.stderr[-200:], flush=True)
        continue
    ok = bad = 0
    for tid, sha in items:
        t0 = time.time()
        c = subprocess.run(["git", "-C", str(work), "checkout", "-q", "--detach", sha],
                           capture_output=True, text=True)
        if c.returncode != 0:
            # maybe shallow history: fetch the sha
            subprocess.run(["git", "-C", str(work), "fetch", "--all", "--tags"], capture_output=True)
            c = subprocess.run(["git", "-C", str(work), "checkout", "-q", "--detach", sha],
                               capture_output=True, text=True)
            if c.returncode != 0:
                print("checkout FAILED", tid, sha[:10], c.stderr[-160:], flush=True)
                bad += 1
                continue
        st = subprocess.run(["git", "-C", str(work), "-c", "core.autocrlf=false", "status", "--porcelain"],
                            capture_output=True, text=True)
        if st.stdout.strip():
            print("WARN dirty", tid, repr(st.stdout[:80]), flush=True)
        out = SNAPS / f"{tid}.tgz"
        with tarfile.open(out, "w:gz") as tar:
            for entry in os.listdir(work):
                tar.add(work / entry, arcname=entry)
        ok += 1
        if ok % 10 == 0:
            print("%s: %d/%d built (%.0fs avg last)" % (name, ok, len(items),
                  (time.time() - t0)), flush=True)
    print("%s DONE: ok=%d bad=%d" % (name, ok, bad), flush=True)
    shutil.rmtree(work, ignore_errors=True)

n = len(list(SNAPS.glob("*.tgz")))
print("SNAPSHOTS TOTAL: %d/129  (%.1f GB, %.1f min)" % (
    n, sum(f.stat().st_size for f in SNAPS.glob('*.tgz')) / 1e9, (time.time() - t_all) / 60), flush=True)
