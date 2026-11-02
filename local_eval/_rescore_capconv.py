"""Pinned-rescore every capconv run (gate flags are unusable this era: canary rich_4077
flagged False in both arms despite its 24/24 pinned history). Drives rescore_pinned.py
once per run tag: <name>_A3_r0_<task>. Serial, ~20s/run."""
import glob, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs")

for name in ("capconv_ctrl", "capconv_raised"):
    tasks = []
    for l in open(os.path.join(HERE, "capkill77.txt"), encoding="utf-8"):
        if l.strip():
            tasks.append(l.strip())
    n_ok = n_fail = n_err = 0
    t0 = time.time()
    for i, task in enumerate(tasks, 1):
        tag = "%s_A3_r0_%s" % (name, task)
        p = subprocess.run([sys.executable, "rescore_pinned.py", "--tag", tag, "--timeout", "600"],
                           cwd=HERE, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        line = ""
        for ln in (p.stdout or "").splitlines():
            if "pinned resolved" in ln or "pinned_resolved" in ln or "VALID" in ln:
                line = ln.strip()
        if p.returncode == 0:
            n_ok += 1
        else:
            n_err += 1
        print("[%s %3d/%d] %s rc=%d %s" % (name, i, len(tasks), task, p.returncode, line[:90]), flush=True)
    print("[%s] DONE rescoring: ok=%d err=%d elapsed=%.1fmin" % (name, n_ok, n_err, (time.time()-t0)/60), flush=True)

# aggregate pinned results
import re
summary = {}
for name in ("capconv_ctrl", "capconv_raised"):
    pins = {}
    for p in glob.glob(os.path.join(RUNS, "%s_*.pinned.jsonl" % name)):
        base = os.path.basename(p)[:-len(".pinned.jsonl")]
        m = re.match(r"%s_A3_r0_(\S+)$" % name, base)
        if not m:
            continue
        for l in open(p, encoding="utf-8"):
            if l.strip():
                d = json.loads(l)
                if d.get("gold_validity") in ("VALID-HARNESS-LIKE", "VALID-GOLD-RELATIVE"):
                    pins[m.group(1)] = bool(d.get("pinned_resolved"))
    summary[name] = pins
    k = sorted(t for t, v in pins.items() if v)
    print("\n%s PINNED: %d/%d  tasks: %s" % (name, len(k), len(pins), k))

ctrl, raised = summary["capconv_ctrl"], summary["capconv_raised"]
cap44 = set()
solved33 = set()
# reproduce the split from the 129-run
G = os.path.join(HERE, "pull_31ba3hard_out", "run_rows.jsonl")
rows = [json.loads(l) for l in open(G, encoding="utf-8", errors="replace") if l.strip()]
for r in rows:
    tid = r["id"]
    if tid.split("_")[0] not in ("rich", "fastapi"):
        continue
    if not r.get("resolved") and ((r.get("tool_calls") or 0) >= 28 or (r.get("duration_s") or 0) >= 470):
        cap44.add(tid)
    elif r.get("resolved"):
        solved33.add(tid)

conv = sorted(t for t in raised if raised.get(t) and not ctrl.get(t) and t in cap44)
reg_on_solved = sorted(t for t in ctrl if ctrl.get(t) and not raised.get(t) and t in solved33)
anti = sorted(t for t in ctrl if ctrl.get(t) and not raised.get(t) and t in cap44)
net = len(conv) - len(reg_on_solved)
print("\n=== PINNED CONVERSION ANALYSIS ===")
print("cap-killed conversions (raised-only solves on the 44): %d %s" % (len(conv), conv))
print("cap-killed anti-conversions (ctrl-only on the 44):    %d %s" % (len(anti), anti))
print("regressions on the solved-33 (ctrl-only):             %d %s" % (len(reg_on_solved), reg_on_solved))
print("NET = %d" % net)
print("canary rich_4077 pinned: ctrl=%s raised=%s" % (ctrl.get("rich_4077"), raised.get("rich_4077")))
