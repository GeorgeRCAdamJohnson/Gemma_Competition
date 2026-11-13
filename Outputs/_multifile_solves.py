"""Multi-file gold tasks: which were EVER solved (E4B and 31B, every local result file), and did the solving patch touch
one file or several? Gold source files = +++ b/ of the gold patch, tests excluded."""
import json
import re
from collections import defaultdict
from pathlib import Path

gold = {}
for l in Path("Outputs/e4b_variance3/tasks.jsonl").read_text(encoding="utf-8").splitlines():
    if l.strip():
        t = json.loads(l)
        gold[t["instance_id"]] = [f for f in re.findall(r"^\+\+\+ b/(\S+)", t["patch"], re.M) if "test" not in f]
multi = {t for t, fs in gold.items() if len(fs) > 1}
runs = defaultdict(lambda: defaultdict(lambda: [0, 0]))   # task -> source -> [solved, runs]
touched = defaultdict(list)                              # task -> files in solving patches
for tr in Path("Outputs").rglob("task_results.jsonl"):
    src = tr.relative_to("Outputs").parts[0]
    model = "31B" if "31b" in str(tr).lower() else "E4B"
    for l in tr.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(l)
        except Exception:
            continue
        t = r.get("instance_id")
        if t not in multi:
            continue
        k = runs[t][f"{model}:{src}"]
        k[1] += 1
        if r.get("resolved"):
            k[0] += 1
            for p in (tr.parent / "patches" / f"{t}.patch", tr.parent / f"{t}.patch"):
                if p.exists():
                    fs = [f for f in re.findall(r"^\+\+\+ b/(\S+)", p.read_text(errors="replace"), re.M) if "test" not in f]
                    touched[t].append(tuple(sorted(fs)))
                    break
print(f"{len(multi)} multi-file gold tasks of {len(gold)}")
ever = {t for t in multi if any(v[0] for v in runs[t].values())}
print(f"ever solved (any model, any run): {len(ever)}")
for t in sorted(ever):
    tot = [sum(v[0] for v in runs[t].values()), sum(v[1] for v in runs[t].values())]
    by = {s: f"{v[0]}/{v[1]}" for s, v in runs[t].items() if v[0]}
    print(f"\n  {t:15s} solved {tot[0]}/{tot[1]} runs | gold files {gold[t]}")
    print(f"     where: {by}")
    if touched[t]:
        from collections import Counter
        for fs, n in Counter(touched[t]).most_common(3):
            cover = sum(f in fs for f in gold[t])
            print(f"     solving patch touched {list(fs)} x{n} -> covers {cover}/{len(gold[t])} gold files")
never_runs = sum(sum(v[1] for v in runs[t].values()) for t in multi - ever)
print(f"\nnever solved: {len(multi - ever)} tasks ({never_runs} runs)")
