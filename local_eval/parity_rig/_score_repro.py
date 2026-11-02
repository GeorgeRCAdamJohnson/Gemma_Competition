"""Score E4B-written reproduction tests (good_test_rate, Konwinski-style).

For each task in m1_skilltest/<run>/patches: extract repro_issue.py from the captured patch, then run it
  (a) on the ORIGINAL snapshot            -> want "Issue reproduced"
  (b) on snapshot + GOLD patch             -> want "Issue resolved"
  (c) on snapshot + each recorded WRONG E4B patch (unresolved in the 7 ca5 runs) -> want "Issue reproduced" (= catches it)
good test = (a) and (b). Also flags tests that never import the real package (mocked).
Usage: python _score_repro.py <run_dir_name> [...]
"""
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
G = RIG.parents[1]
BASE = "C:/Users/Biges/OneDrive/Documents/Desktop/kAGGLE"
TASKS = {json.loads(l)["instance_id"]: json.loads(l)
         for l in (G / "comp_files" / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
RUNS = [RIG / "m1_full129" / "ca5", RIG / "m1_full129" / "ca5_v2", RIG / "m1_capped" / "agent_ctrl_e4b_r0",
        RIG / "m1_capped" / "agent_ctrl_e4b_r1", RIG / "m1_faithful" / "agent_ctrl_e4b_r0",
        G / "kaggle_pkg" / "out_e4b" / "results", G / "kaggle_pkg" / "out_e4b_r2" / "results"]
INNER = r'''
mkdir -p /workspace && cd /workspace && tar xzf /snaps/$TID.tgz -C /workspace
if [ -s /cand.patch ]; then git apply --whitespace=nowarn /cand.patch 2>/dev/null || git apply --3way --whitespace=nowarn /cand.patch 2>/dev/null || echo PATCH_FAIL; fi
cp /repro.py /workspace/repro_issue.py
cd /workspace && PYTHONPATH=/workspace timeout 60 python3 repro_issue.py 2>&1 | tail -5
'''


def repro_from_patch(text):
    m = re.search(r"diff --git a/repro_issue.py b/repro_issue.py\n(?:.*\n)*?@@[^\n]*\n((?:[+ \\].*\n?)*)", text)
    if not m:
        return None
    lines = []
    for l in m.group(1).splitlines():
        if l.startswith("\\"):
            continue
        if l.startswith("+"):
            lines.append(l[1:])
        elif l.startswith(" "):
            lines.append(l[1:])
    return "\n".join(lines) + "\n"


def run(tid, repro, patch):
    with tempfile.TemporaryDirectory() as td:
        rp, pp = Path(td) / "repro.py", Path(td) / "cand.patch"
        rp.write_text(repro, encoding="utf-8", newline="\n")
        pp.write_text((patch or "") if not patch or patch.endswith("\n") else patch + "\n", encoding="utf-8", newline="\n")
        cmd = ["docker", "run", "--rm", "-e", f"TID={tid}", "-v", f"{BASE}/Gemma/local_eval/snapshots:/snaps:ro",
               "-v", f"{rp.as_posix()}:/repro.py:ro", "-v", f"{pp.as_posix()}:/cand.patch:ro",
               "--entrypoint", "bash", "gemma-parity-rig:latest", "-c", INNER]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    out = (p.stdout or "") + (p.stderr or "")
    if "PATCH_FAIL" in out:
        return "patch_fail"
    for k, v in (("Issue resolved", "resolved"), ("Issue reproduced", "reproduced"), ("Other issues", "other")):
        if k in out:
            return v
    return "error"


def wrong_patches(tid):
    seen, out = set(), []
    for d in RUNS:
        f = d / "task_results.all.jsonl"
        f = f if f.exists() else d / "task_results.jsonl"
        rows = {json.loads(l)["instance_id"]: json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()}
        pf = d / "patches" / f"{tid}.patch"
        if tid in rows and not rows[tid]["resolved"] and pf.exists():
            t = pf.read_text(encoding="utf-8", errors="replace")
            if t.strip() and t not in seen:
                seen.add(t)
                out.append(t)
    return out


summary = {"tasks": 0, "has_test": 0, "real_import": 0, "base_reproduced": 0, "gold_resolved": 0, "good": 0,
           "wrong_total": 0, "wrong_caught": 0}
for run_name in sys.argv[1:]:
    for pf in sorted((RIG / "m1_skilltest" / run_name / "patches").glob("*.patch")):
        tid = pf.stem
        summary["tasks"] += 1
        repro = repro_from_patch(pf.read_text(encoding="utf-8", errors="replace"))
        if not repro:
            print(f"{tid:<16} NO repro_issue.py")
            continue
        summary["has_test"] += 1
        pkg = TASKS[tid]["repo"].split("/")[-1]
        real = bool(re.search(r"^\s*(from|import)\s+%s\b" % re.escape(pkg), repro, re.M))
        summary["real_import"] += real
        a = run(tid, repro, "")
        b = run(tid, repro, TASKS[tid]["patch"])
        good = a == "reproduced" and b == "resolved"
        summary["base_reproduced"] += a == "reproduced"
        summary["gold_resolved"] += b == "resolved"
        summary["good"] += good
        caught = []
        if good:
            for wp in wrong_patches(tid):
                r = run(tid, repro, wp)
                summary["wrong_total"] += 1
                caught.append(r)
                summary["wrong_caught"] += r in ("reproduced", "other", "error")
        print(f"{tid:<16} real_import={str(real):<5} base={a:<11} gold={b:<11} GOOD={str(good):<5} wrong_patches->{caught}")
print("SUMMARY", json.dumps(summary))
