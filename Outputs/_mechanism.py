"""WHY does fresh retry beat plain ca5? Trace-level decomposition on the 39 ever-solved tasks.

Sources: pack1/pack2 validation logs (score39 passes 1-2 per node; node0 run1 = runtime90, excluded), control =
plain ca5 (e4b-cap-ab run_1, 4 nodes). For every pack run: the sequence of gate verdicts (one per attempt), whether
the final patch was an ACCEPTED attempt or a restore, and the scorer verdict.
"""
import glob
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

A = re.compile(r"\x1b\[[0-9;]*m")
O = Path("Outputs")
IDS = set(json.load(open(O / "_solvable85.json"))["ever"])
TASKS = {json.loads(l)["instance_id"]: json.loads(l) for l in open("kaggle_pkg/taskdefs/tasks.jsonl", encoding="utf-8") if l.strip()}


def verdict_class(s):
    if s.startswith("ACCEPTED"):
        if "GATE_ERROR" in s:
            return "ACC:gate_error"
        if "cannot be collected" in s:
            return "ACC:tests_uncollectable"
        if "no existing test file covers" in s:
            return "ACC:no_tests_found"
        if "no tests/ directory" in s:
            return "ACC:no_tests_dir"
        return "ACC:tests_pass"
    if "only non-source" in s:
        return "REJ:non_source_only"
    if "existing test(s) fail" in s:
        return "REJ:breaks_tests"
    if "syntax error" in s:
        return "REJ:syntax"
    if "no change in the repo" in s:
        return "REJ:no_change"
    if "breaks import" in s:
        return "REJ:breaks_import"
    return "REJ:other"


def runs(root, score_only=True):
    for rf in sorted(glob.glob(str(root / "results" / "node*" / "run_*" / "task_results.jsonl"))):
        node, run = re.search(r"node(\d)[\\/]run_(\d+)", rf).groups()
        if score_only and node == "0" and run == "1" and "pack" in str(root):
            continue  # runtime90 pass
        for l in open(rf):
            if not l.strip():
                continue
            r = json.loads(l)
            if r["instance_id"] not in IDS:
                continue
            lp = Path(rf).parent / "logs" / (r["instance_id"] + ".log")
            log = A.sub("", lp.read_text(encoding="utf-8", errors="replace")) if lp.exists() else ""
            yield r, log


def parse_pack(log):
    v = [verdict_class(m) for m in re.findall(r'"stdout": "([^"]{0,200})', log)]
    submitted = "submit_patch: {\"status\": \"ok\"" in log
    retry_lines = re.findall(r"Agent finished: RETRY: (.{0,90})", log)
    edits = re.findall(r"edit_file \(([^)]+)\)", log) + re.findall(r"write_file \(([^,)]+)", log)
    return v, submitted, retry_lines, edits


# ---------------- per-task solve rates ----------------
ctrl = defaultdict(lambda: [0, 0])
for r, _ in runs(O / "e4b_cap_ab", score_only=False):
    ctrl[r["instance_id"]][0] += bool(r.get("resolved")); ctrl[r["instance_id"]][1] += 1
pack = defaultdict(lambda: [0, 0])
rows = []
for name in ("e4b_pack1_val", "e4b_pack2_val"):
    for r, log in runs(O / name):
        v, sub, rl, ed = parse_pack(log)
        res = bool(r.get("resolved"))
        pack[r["instance_id"]][0] += res; pack[r["instance_id"]][1] += 1
        rows.append(dict(task=r["instance_id"], pack=name[4:9], res=res, v=v, sub=sub, retry=rl, edits=ed,
                         ovf="ContextWindow" in str(r.get("error") or ""), calls=r.get("tool_calls"),
                         dur=r.get("duration_seconds")))
print(f"runs parsed: control {sum(n for _, n in ctrl.values())} | pack {len(rows)} (pack1+pack2, score39 passes 1-2)")
print(f"solve rate: control {sum(k for k,_ in ctrl.values())/sum(n for _,n in ctrl.values()):.3f} | "
      f"pack {sum(k for k,_ in pack.values())/sum(n for _,n in pack.values()):.3f}")

# ---------------- 1. how many attempts, and where do solves come from ----------------
print("\n1. SOLVES BY THE ATTEMPT THAT PRODUCED THE SUBMITTED PATCH")
by = Counter(); tot = Counter()
for x in rows:
    n_att = len(x["v"])
    if x["ovf"] and not x["sub"]:
        key = "overflow (no submit)"
    elif n_att == 0:
        key = "no gate run"
    elif x["v"][-1].startswith("ACC"):
        key = f"accepted on attempt {n_att}"
    else:
        key = f"3 rejects -> restore (best of {n_att})"
    tot[key] += 1; by[key] += x["res"]
for k in sorted(tot):
    print(f"   {k:34s} runs {tot[k]:4d}  solved {by[k]:4d}  rate {by[k]/tot[k]:.2f}")
first_acc = sum(1 for x in rows if x["v"] and x["v"][0].startswith("ACC") and len(x["v"]) == 1 and x["res"])
later = sum(1 for x in rows if len(x["v"]) > 1 and x["res"])
print(f"   => solves from attempt 1 accepted: {first_acc} | solves that needed >=1 rejection first: {later} "
      f"({100*later/max(1,first_acc+later):.0f}% of solves)")

# ---------------- 2. what the gate says, and how right it is ----------------
print("\n2. GATE VERDICTS ON EVERY ATTEMPT")
vc = Counter(c for x in rows for c in x["v"])
for k, n in vc.most_common():
    print(f"   {k:28s} {n:4d}")
print("   final-verdict -> scorer outcome (is an ACCEPT trustworthy?)")
fv = defaultdict(lambda: [0, 0])
for x in rows:
    if x["v"]:
        fv[x["v"][-1]][0] += x["res"]; fv[x["v"][-1]][1] += 1
for k, (a, n) in sorted(fv.items(), key=lambda z: -z[1][1]):
    print(f"   final {k:28s} runs {n:4d}  resolved {a:4d} ({a/n:.2f})")

# ---------------- 3. what a rejection makes the fixer do differently ----------------
print("\n3. AFTER A REJECTION: does the next attempt change file / approach?")
chg = Counter()
for x in rows:
    if len(x["v"]) < 2:
        continue
    # attempt boundaries: split edits by 'Agent finished: DONE' order is lost; approximate with retry reasons
    for reason in x["retry"]:
        rr = reason.lower()
        if "test" in rr and ("fail" in rr or "broke" in rr or "break" in rr):
            chg["retry reason: broke existing tests"] += 1
        elif "source" in rr or "non-source" in rr:
            chg["retry reason: edited non-source file"] += 1
        elif "syntax" in rr:
            chg["retry reason: syntax"] += 1
        elif "no change" in rr or "did not land" in rr:
            chg["retry reason: edit did not land"] += 1
        else:
            chg["retry reason: other"] += 1
for k, n in chg.most_common():
    print(f"   {k:40s} {n}")

# ---------------- 4. per-task: where the gain is and what mechanism moved it ----------------
print("\n4. PER-TASK (control rate -> pack rate), with the dominant pack mechanism on that task")
lines = []
for t in sorted(IDS):
    c = ctrl[t][0] / ctrl[t][1] if ctrl[t][1] else None
    p = pack[t][0] / pack[t][1] if pack[t][1] else None
    if c is None or p is None:
        continue
    xs = [x for x in rows if x["task"] == t]
    solved = [x for x in xs if x["res"]]
    mech = Counter()
    for x in solved:
        if not x["v"]:
            mech["no-gate"] += 1
        else:
            mech["acc@1" if len(x["v"]) == 1 else ("acc-after-reject" if x["v"][-1].startswith("ACC") else "restore")] += 1
    rej = Counter(c2 for x in xs for c2 in x["v"] if c2.startswith("REJ"))
    lines.append((p - c, t, c, p, dict(mech), dict(rej.most_common(2)), sum(x["ovf"] for x in xs), len(xs)))
for d, t, c, p, m, rj, ov, n in sorted(lines, reverse=True):
    if abs(d) >= 0.2:
        print(f"   {t:15s} {c:.2f} -> {p:.2f} ({d:+.2f}) | solves {m} | top rejects {rj} | overflow {ov}/{n}")

# ---------------- 5. gold-patch files of tasks hit by the non-source rule ----------------
print("\n5. TASKS WHERE THE GATE REJECTED 'non_source_only': does the GOLD patch edit non-.py files?")
ns = Counter(x["task"] for x in rows for c2 in x["v"] if c2 == "REJ:non_source_only")
for t, n in ns.most_common(12):
    files = re.findall(r"^diff --git a/(\S+)", TASKS[t]["patch"], re.M)
    print(f"   {t:15s} rejected {n:3d}x | gold files: {files[:5]}")
json.dump(rows, open(O / "_mechanism_rows.json", "w"), indent=0)

# ---------------- 6. why is attempt-1 WORSE than plain ca5? ----------------
print("\n6. ATTEMPT-1 vs PLAIN ca5 - where first-attempt quality is lost")
c_runs = list(runs(O / "e4b_cap_ab", score_only=False))
c_ovf = sum("ContextWindow" in str(r.get("error") or "") for r, _ in c_runs)
c_calls = sorted(r.get("tool_calls") or 0 for r, _ in c_runs)
print(f"   control: overflow {c_ovf}/{len(c_runs)} ({100*c_ovf/len(c_runs):.1f}%), median tool calls {c_calls[len(c_calls)//2]}")
p_ovf = sum(x["ovf"] for x in rows)
print(f"   pack   : overflow {p_ovf}/{len(rows)} ({100*p_ovf/len(rows):.1f}%), all overflow runs solved 0")
# overflow split: before any gate verdict (fixer attempt 1 itself) vs after >=1 verdict (retries)
o0 = sum(1 for x in rows if x["ovf"] and len(x["v"]) == 0)
o1 = sum(1 for x in rows if x["ovf"] and len(x["v"]) >= 1)
print(f"   pack overflows: during attempt 1 (no verdict yet) {o0} | after >=1 verdict {o1}")
# false-reject proxy: attempt 1 rejected 'breaks_tests'/'non_source' on tasks control solves >= 50%
easy = {t for t, (k, n) in ctrl.items() if n and k / n >= 0.5}
fr = Counter()
for x in rows:
    if x["task"] in easy and x["v"] and x["v"][0].startswith("REJ"):
        fr[(x["v"][0], x["res"])] += 1
print(f"   on tasks control solves >=50% ({len(easy)} tasks), attempt 1 REJECTED (verdict, final resolved): {dict(fr)}")
# DONE-stop: control self-verifies? count control runs that ran tests / python before submit
c_test = sum(1 for _, log in c_runs if re.search(r"run_command (python3? -m pytest|pytest|python3? /tmp)", log))
p_test = sum(1 for x in rows if x["task"])  # placeholder count
print(f"   control runs that executed tests/repro themselves: {c_test}/{len(c_runs)}")
