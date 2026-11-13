"""Counterfactual, free: apply candidate `locate` decision rules to every logged run's FIRST-EDIT file choice and count
file-level gains (wrong -> gold) and losses (gold -> wrong). Uses locate v3's offline top-5 for each task (query =
problem statement; the live model writes its own query, so this approximates). File-level only: a gained file is
necessary, not sufficient, for a solve; a lost file almost surely loses the solve.
Rules:
  R_now   (batch 6): if your file is NOT in locate's list -> switch to #1 (modelled as switching; really "reconsider")
  R_top1  always edit locate #1
  R_seen  if locate #1 differs from your file AND you already opened #1 -> switch to #1
  R_in2   if your file is not in locate's top 2 -> switch to #1
"""
import json
import re
from collections import defaultdict
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
ACT = re.compile(r"\] \S+ (read_file|run_command|edit_file|write_file|run_skill_script)\s*\(?([^\n]{0,200})")
FILE = re.compile(r"([\w./-]+\.py)")
loc = {r["id"]: [f for f in r["full"] if "test" not in f] for r in json.load(open("Outputs/locate_offline/locate_offline.json"))}
gold = {}
for line in Path("Outputs/e4b_variance3/tasks.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line)
        gold[r["instance_id"]] = {f for f in re.findall(r"^\+\+\+ b/(\S+)", r["patch"], re.M) if "test" not in f}
norm = lambda f: f.replace("/workspace/", "").lstrip("./")

runs = defaultdict(list)
for tr in Path("Outputs/ab_logs").rglob("task_results.jsonl"):
    for l in tr.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        t = r["instance_id"]
        lp = tr.parent / "logs" / f"{t}.log"
        if t not in gold or t not in loc or not lp.exists():
            continue
        fixer = "\n".join(x for x in ANSI.sub("", lp.read_text(encoding="utf-8", errors="replace")).splitlines()
                          if "(verifier)" not in x)
        seen, first = [], None
        for m in ACT.finditer(fixer):
            fs = [norm(f) for f in FILE.findall(m.group(2)) if "test" not in f]
            if m.group(1) in ("edit_file", "write_file") and fs and first is None:
                first, before = fs[0], set(seen)
            seen += fs
        if first:
            runs[t].append(dict(ok=bool(r["resolved"]), first=first, before=before))


def apply(rule, f, L, before):
    if not L:
        return f
    if rule == "R_now":
        return f if f in L else L[0]
    if rule == "R_top1":
        return L[0]
    if rule == "R_seen":
        return L[0] if L[0] != f and L[0] in before else f
    if rule == "R_in2":
        return f if f in L[:2] else L[0]


print(f"{sum(map(len, runs.values()))} runs with a first edit over {len(runs)} tasks\n")
print(f"{'rule':7s} {'gain':>5s} {'loss':>5s} {'net':>5s} | net per 26-task pass | biggest movers")
for rule in ("R_now", "R_top1", "R_seen", "R_in2"):
    gain = loss = 0
    per = defaultdict(int)
    for t, rs in runs.items():
        for r in rs:
            was = r["first"] in gold[t]
            now = apply(rule, r["first"], loc[t], r["before"]) in gold[t]
            gain += (not was) and now
            loss += was and not now
            per[t] += int(now) - int(was)
    npass = sum(map(len, runs.values())) / 26
    movers = sorted(per.items(), key=lambda kv: -abs(kv[1]))[:5]
    print(f"{rule:7s} {gain:5d} {loss:5d} {gain - loss:+5d} | {(gain - loss) / npass:+5.2f} files/pass | "
          + ", ".join(f"{t} {v:+d}" for t, v in movers if v))
