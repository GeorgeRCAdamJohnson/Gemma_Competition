"""Which never/rarely-solved tasks are NEAR MISSES for E4B, and which multi-file tasks are effectively single-file?
Sources: every local run with a saved hidden-test output (test_outputs/<task>.log) and patch (patches/<task>.patch).
Per task:
  solve      solved / runs
  best_fail  fewest hidden-test failures in any UNSOLVED run (1 = one test away)  + share of unsolved runs within 1 failure
  pass_frac  best passed/(passed+failed) in an unsolved run
  gold_edit  share of runs whose patch touches a gold source file
  multi-file: gold source files the hidden test_patch IMPORTS (from fastapi.x import / import rich.x / module paths)
"""
import json
import re
import statistics as st
from collections import defaultdict
from pathlib import Path

T = {}
for l in Path("Outputs/e4b_variance3/tasks.jsonl").read_text(encoding="utf-8").splitlines():
    if l.strip():
        t = json.loads(l)
        T[t["instance_id"]] = t
gold = {k: [f for f in re.findall(r"^\+\+\+ b/(\S+)", t["patch"], re.M) if "test" not in f] for k, t in T.items()}
# new/changed test functions in the hidden test_patch ~ the fail-to-pass tests
NEW = {k: set(re.findall(r"^\+\s*(?:async\s+)?def (test_\w+)", t["test_patch"], re.M)) for k, t in T.items()}
SUM = re.compile(r"=+ (?:(\d+) failed)?(?:, )?(?:(\d+) passed)?(?:, )?(?:(\d+) errors?)?.* in [\d.]+s")

R = defaultdict(list)
for tr in Path("Outputs").rglob("task_results.jsonl"):
    if "31b" in str(tr).lower():
        continue
    for l in tr.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(l)
        except Exception:
            continue
        t = r.get("instance_id")
        if t not in T:
            continue
        rec = dict(ok=bool(r.get("resolved")), failed=None, passed=None, files=None, colerr=False, new_failed=None)
        to = tr.parent / "test_outputs" / f"{t}.log"
        if to.exists():
            lines = [x for x in to.read_text(errors="replace")[-4000:].splitlines() if re.search(r"\bin [\d.]+s\b", x)
                     and re.search(r"\d+ (failed|passed|errors?)", x)]
            if lines:
                s = lines[-1]
                g = lambda k: sum(int(x) for x in re.findall(rf"(\d+) {k}", s))
                rec["failed"] = g("failed") + g("errors?")
                rec["passed"] = g("passed")
                txt = to.read_text(errors="replace")
                rec["colerr"] = bool(re.search(r"ERROR collecting|ImportError|ModuleNotFoundError|errors? during collection", txt))
                # failing test NAMES that belong to the task's NEW tests (the fail-to-pass set, approx.)
                fails = set(re.findall(r"^(?:FAILED|ERROR) \S+::(\w+)", txt, re.M))
                rec["new_failed"] = len(fails & NEW[t])
        pp = tr.parent / "patches" / f"{t}.patch"
        if pp.exists():
            rec["files"] = {f for f in re.findall(r"^\+\+\+ b/(\S+)", pp.read_text(errors="replace"), re.M) if "test" not in f}
        R[t].append(rec)


def imported(t):
    """gold source files whose module the hidden test imports or references"""
    tp = T[t]["test_patch"]
    out = []
    for f in gold[t]:
        mod = f[:-3].replace("/", ".") if f.endswith(".py") else f
        parts = mod.split(".")
        pkg, leaf = ".".join(parts[:-1]), parts[-1]
        if (mod in tp or re.search(rf"from\s+{re.escape(pkg)}\s+import\s+[^\n]*\b{re.escape(leaf)}\b", tp)
                or (leaf == "__init__" and re.search(rf"\b{re.escape(pkg)}\b", tp)) or Path(f).name in tp):
            out.append(f)
    return out


print("\nA2. STRICT near misses: unsolved run with NO collection error, where some of the task's new tests PASSED")
print("    (new tests = test functions added by the hidden test_patch; partial = fewer of them failed than exist)")
strict = []
for t, rs in R.items():
    n_new = len(NEW[t])
    uns = [r for r in rs if not r["ok"] and r["failed"] is not None and not r["colerr"] and r["new_failed"] is not None]
    part = [r for r in uns if n_new >= 2 and r["new_failed"] < n_new]
    if part and sum(r["ok"] for r in rs) / len(rs) < 0.10:
        strict.append((t, len(part), len(uns), n_new, min(r["new_failed"] for r in part), sum(r["ok"] for r in rs), len(rs)))
for t, p, u, n, mn, s, n_ in sorted(strict, key=lambda x: (x[4] / x[3], -x[1])):
    print(f"    {t:15s} solved {s}/{n_}: {p}/{u} unsolved runs passed some new tests; best: {mn} of {n} new tests failing"
          f"{'  [multi-file gold]' if len(gold[t]) > 1 else ''}")
print(f"    -> {len(strict)} tasks")

rows = []
for t, rs in R.items():
    if not gold[t]:
        continue
    uns = [r for r in rs if not r["ok"] and r["failed"] is not None]
    withp = [r for r in rs if r["files"] is not None]
    rows.append(dict(
        id=t, n=len(rs), solved=sum(r["ok"] for r in rs),
        best_fail=min((r["failed"] for r in uns), default=None),
        within1=st.mean(r["failed"] <= 1 for r in uns) if uns else None,
        pass_frac=max((r["passed"] / max(r["passed"] + r["failed"], 1) for r in uns), default=None),
        gold_edit=st.mean(bool(r["files"] & set(gold[t])) for r in withp) if withp else None,
        multi=len(gold[t]) > 1, imp=imported(t) if len(gold[t]) > 1 else None))

pr = lambda x, f="{:.0%}": "  -  " if x is None else f.format(x)
print(f"{len(rows)} tasks with E4B runs | runs with test output: {sum(r['failed'] is not None for rs in R.values() for r in rs)}")
rare = [r for r in rows if r["solved"] / r["n"] < 0.10 and r["best_fail"] is not None]
print(f"\nA. NEAR MISSES: solve rate < 10% and an unsolved run was ONE hidden-test failure away ({sum(r['best_fail'] <= 1 for r in rare)} tasks)")
print("   task            solved      best fail  runs<=1 fail  best pass frac  edits gold file  multi(test imports)")
for r in sorted(rare, key=lambda r: (r["best_fail"], -(r["within1"] or 0))):
    if r["best_fail"] > 1:
        continue
    mf = f"{len(gold[r['id']])} files ({len(r['imp'])} imported)" if r["multi"] else ""
    print(f"   {r['id']:15s} {r['solved']:3d}/{r['n']:<4d}  {r['best_fail']:5d}      {pr(r['within1']):>6s}       "
          f"{pr(r['pass_frac']):>6s}        {pr(r['gold_edit']):>6s}     {mf}")
print(f"\n   rare tasks never within 1 failure: {sum(r['best_fail'] > 1 for r in rare)}")

print("\nB. multi-file gold tasks: how many gold files does the hidden test import?")
ms = [r for r in rows if r["multi"]]
for k in sorted({len(r["imp"]) for r in ms}):
    q = [r for r in ms if len(r["imp"]) == k]
    print(f"   imports {k} gold file(s): {len(q):2d} tasks | ever solved {sum(r['solved'] > 0 for r in q)} | "
          f"edits a gold file {pr(st.mean(r['gold_edit'] for r in q if r['gold_edit'] is not None) if any(r['gold_edit'] is not None for r in q) else None)}")
one = [r for r in ms if len(r["imp"]) == 1]
print("   effectively single-file (test imports exactly 1 gold file):")
for r in sorted(one, key=lambda r: (r["best_fail"] if r["best_fail"] is not None else 99)):
    print(f"     {r['id']:15s} solved {r['solved']}/{r['n']} best fail {r['best_fail']} edits gold {pr(r['gold_edit'])} "
          f"| needed {r['imp'][0]} of {gold[r['id']]}")
Path("Outputs/_near_miss.json").write_text(json.dumps(rows, indent=1, default=list))
