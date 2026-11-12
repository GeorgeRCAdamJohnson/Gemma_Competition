"""Where do solved and failed runs of the SAME task split? For each swing task, over every logged run (Colab A/B logs):
  - first source file opened/grepped/edited, the file the patch finally touched
  - number of reads before the first edit, edit failures, whether the agent ran a test, retries used, overflow
  - the earliest action (by position) whose distribution differs most between solved and failed runs
Input: Outputs/ab_logs/<tag>/<arm>/round_<n>/{task_results.jsonl, logs/<task>.log}
"""
import json
import re
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
ROOT = Path("Outputs/ab_logs")
SWING = ["fastapi_14492", "rich_2943", "fastapi_9425", "fastapi_14463", "fastapi_14873", "rich_3894", "fastapi_9753",
         "rich_4077", "rich_3067", "rich_2725"]
ONLY = sys.argv[1:] or SWING
ACT = re.compile(r"\] \S+ (read_file|run_command|edit_file|write_file|get_status|run_skill_script)\s*\(?([^\n]{0,160})")


def target(tool, arg):
    """normalize an action to a comparable token: tool + the repo file it touches (if any)."""
    m = re.search(r"([\w./-]+\.(?:py|md|toml|cfg|yaml|yml|txt|cff|rst))", arg)
    f = m.group(1).lstrip("./") if m else ""
    if tool == "run_command":
        kind = "grep" if "grep" in arg else "sed" if "sed -n" in arg else "pytest" if "pytest" in arg else \
               "python" if "python" in arg else "cmd"
        return f"{kind}:{f}"
    return f"{tool}:{f}"


runs = defaultdict(list)
for tr in ROOT.rglob("task_results.jsonl"):
    for l in tr.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        if r["instance_id"] not in ONLY:
            continue
        lp = tr.parent / "logs" / f"{r['instance_id']}.log"
        if not lp.exists():
            continue
        log = ANSI.sub("", lp.read_text(encoding="utf-8", errors="replace"))
        fixer = "\n".join(x for x in log.splitlines() if "(verifier)" not in x)
        acts = [target(m.group(1), m.group(2)) for m in ACT.finditer(fixer)]
        first_edit = next((i for i, a in enumerate(acts) if a.startswith(("edit_file", "write_file")) or a.startswith("python:")), None)
        runs[r["instance_id"]].append(dict(
            ok=bool(r["resolved"]), arm=tr.parent.parent.name, acts=acts,
            first_src=next((a.split(":", 1)[1] for a in acts if a.split(":", 1)[1].endswith(".py") and "test" not in a), ""),
            edited=[a.split(":", 1)[1] for a in acts if a.startswith("edit_file") and a.split(":", 1)[1]],
            reads_before_edit=first_edit if first_edit is not None else len(acts),
            edit_fail=len(re.findall(r"edit_file[^\n]*\n[^\n]*\u274c", fixer)),
            ran_test="pytest" in fixer or "python -m pytest" in fixer,
            retries=len(re.findall(r"RETRY:", log)), overflow="ContextWindow" in str(r.get("error"))))

for t in ONLY:
    rs = runs.get(t, [])
    ok, bad = [r for r in rs if r["ok"]], [r for r in rs if not r["ok"]]
    if not ok or not bad:
        print(f"\n## {t}: {len(ok)} solved / {len(bad)} failed -- need both to compare")
        continue
    print(f"\n## {t}: {len(ok)} solved / {len(bad)} failed")
    for k in ("reads_before_edit", "edit_fail", "retries"):
        print(f"   {k:18s} solved median {st.median(r[k] for r in ok):4.1f} | failed {st.median(r[k] for r in bad):4.1f}")
    for k in ("ran_test", "overflow"):
        print(f"   {k:18s} solved {st.mean(r[k] for r in ok):4.0%} | failed {st.mean(r[k] for r in bad):4.0%}")
    print("   first source file  solved", Counter(r["first_src"] for r in ok).most_common(3))
    print("                      failed", Counter(r["first_src"] for r in bad).most_common(3))
    print("   edited files       solved", Counter(f for r in ok for f in set(r["edited"])).most_common(3))
    print("                      failed", Counter(f for r in bad for f in set(r["edited"])).most_common(3))
    # earliest position where the action distribution separates solved vs failed (total-variation distance)
    best = None
    for i in range(8):
        a = Counter(r["acts"][i] if i < len(r["acts"]) else "<end>" for r in ok)
        b = Counter(r["acts"][i] if i < len(r["acts"]) else "<end>" for r in bad)
        keys = set(a) | set(b)
        tv = 0.5 * sum(abs(a[k] / len(ok) - b[k] / len(bad)) for k in keys)
        top = max(keys, key=lambda k: a[k] / len(ok) - b[k] / len(bad))
        if best is None or tv > best[1] + 0.05:
            best = (i, tv, top, a[top] / len(ok), b[top] / len(bad))
    i, tv, top, pa, pb = best
    print(f"   split point: action #{i + 1} (TV {tv:.2f}); '{top}' in {pa:.0%} of solved vs {pb:.0%} of failed")
