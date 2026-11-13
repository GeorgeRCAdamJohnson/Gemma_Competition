"""Free offline test (existing Colab A/B logs): how much can ANY file locator help E4B, and what kind?
Per run of every task with both outcomes: gold files (+++ b/ of the gold patch) vs the files the fixer edited.
  1. how often the first edited source file is a gold file, solved vs failed  -> ceiling for a file locator
  2. failed runs that edited a WRONG file: had the agent already opened/grepped the gold file before that edit?
     yes = it SAW the right file and chose another (a choosing/verification problem, a search tool won't fix it)
     no  = it never found it (a search problem, a locator can fix it)
  3. failed runs whose first edit WAS a gold file -> the failure is inside the file (hunk / logic), not localization
  4. self-consistency: majority vote of the first-edit file over a task's runs vs a single run's accuracy
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
ACT = re.compile(r"\] \S+ (read_file|run_command|edit_file|write_file|run_skill_script)\s*\(?([^\n]{0,200})")
FILE = re.compile(r"([\w./-]+\.py)")
gold = {}
for line in Path("Outputs/e4b_variance3/tasks.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        r = json.loads(line)
        gold[r["instance_id"]] = {f for f in re.findall(r"^\+\+\+ b/(\S+)", r["patch"], re.M) if "test" not in f}


def norm(f):
    return f.replace("/workspace/", "").lstrip("./")


runs = defaultdict(list)
for tr in Path("Outputs/ab_logs").rglob("task_results.jsonl"):
    for l in tr.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        t = r["instance_id"]
        lp = tr.parent / "logs" / f"{t}.log"
        if t not in gold or not lp.exists():
            continue
        fixer = "\n".join(x for x in ANSI.sub("", lp.read_text(encoding="utf-8", errors="replace")).splitlines()
                          if "(verifier)" not in x)
        seen, first_edit, seen_before = [], None, set()
        for m in ACT.finditer(fixer):
            tool, arg = m.group(1), m.group(2)
            fs = [norm(f) for f in FILE.findall(arg) if "test" not in f]
            if tool in ("edit_file", "write_file") and fs and first_edit is None:
                first_edit, seen_before = fs[0], set(seen)
            seen += fs
        runs[t].append(dict(ok=bool(r["resolved"]), first=first_edit, saw_gold_before=bool(seen_before & gold[t]),
                            saw_gold_ever=bool(set(seen) & gold[t])))

mixed = {t: rs for t, rs in runs.items() if any(r["ok"] for r in rs) and not all(r["ok"] for r in rs)}
allr = [r for rs in runs.values() for r in rs]
print(f"{len(allr)} runs over {len(runs)} tasks; {len(mixed)} tasks have both solved and failed runs")


def tally(rs, label):
    e = [r for r in rs if r["first"]]
    g = [r for r in e if r["first"] in gold[r["t"]]]
    print(f"  {label:26s} runs {len(rs):5d} | edited {len(e) / max(len(rs), 1):5.1%} | first edit = gold "
          f"{len(g) / max(len(e), 1):5.1%}")


for t, rs in runs.items():
    for r in rs:
        r["t"] = t
mx = [r for rs in mixed.values() for r in rs]
print("\n1. first edited source file vs gold (mixed tasks = where a lever can matter)")
tally([r for r in mx if r["ok"]], "solved runs")
tally([r for r in mx if not r["ok"]], "failed runs")
bad = [r for r in mx if not r["ok"] and r["first"]]
wrong = [r for r in bad if r["first"] not in gold[r["t"]]]
right = [r for r in bad if r["first"] in gold[r["t"]]]
none_ = [r for r in mx if not r["ok"] and not r["first"]]
print(f"\n2. failed runs: wrong file {len(wrong)} | gold file {len(right)} | no edit {len(none_)}")
if wrong:
    sb = sum(r["saw_gold_before"] for r in wrong)
    se = sum(r["saw_gold_ever"] for r in wrong)
    print(f"   wrong-file runs that had ALREADY opened/grepped the gold file before editing: {sb}/{len(wrong)} "
          f"({sb / len(wrong):.0%}); ever in the run: {se}/{len(wrong)}")
print(f"\n3. failed runs whose first edit WAS gold: {len(right)}/{len(bad)} ({len(right) / max(len(bad), 1):.0%})"
      " -> failure is inside the right file")
print("\n4. per mixed task: solve rate | single-run first-edit-gold | majority-vote file is gold? | wrong-file fails "
      "(saw gold first?)")
for t in sorted(mixed, key=lambda t: sum(r["ok"] for r in mixed[t]) / len(mixed[t])):
    rs = mixed[t]
    e = [r for r in rs if r["first"]]
    maj = Counter(r["first"] for r in e).most_common(1)
    w = [r for r in rs if not r["ok"] and r["first"] and r["first"] not in gold[t]]
    print(f"   {t:15s} {sum(r['ok'] for r in rs) / len(rs):4.0%} (n {len(rs):3d}) | "
          f"{sum(r['first'] in gold[t] for r in e) / max(len(e), 1):4.0%} | "
          f"{'yes' if maj and maj[0][0] in gold[t] else 'NO '} {maj[0][0][:34] if maj else '':34s} | "
          f"{len(w):3d} ({sum(r['saw_gold_before'] for r in w)})")
