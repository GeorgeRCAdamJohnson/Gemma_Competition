"""CPU-only: does the real 31B change behaviour after the harness's budget_warning (first shown at call 18/28)?
python atif_warn_reaction.py [--all]

Per 28-call-regime Kaggle ATIF trace: counted-call index of the first budget_warning, counted-call index of the first
edit attempt (edit_file / write_file / run_command that writes), outcome tag from kaggle_outcomes.json.
"""
import argparse, collections, json, re, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = json.loads((ROOT / "local_eval" / "runs" / "kaggle_outcomes.json").read_text())
OUTCOME = {(r["version"], r["task"]): r for r in OUT}
WARN = re.compile(r"Only (\d+) tool call\(s\) remaining \((\d+)/(\d+) used\)")
WRITE_CMD = re.compile(r"(sed\s+-i|>\s*[\w./-]+\.py|cat\s*>|tee\s|python3?\s+-\s*<<|python3?\s+-c|git\s+apply|patch\s+-p|perl\s+-pi|open\([^)]*['\"]w)")


def version_of(p):
    rel = p.relative_to(ROOT).parts
    if rel[0].startswith("submit_"):
        if len(rel) > 3 and rel[2] == "out":
            return f"{rel[0][7:]}/{rel[1]}"
        return rel[0][7:]
    return "/".join(rel[:-1]) or rel[0]


def analyse(p):
    t = json.loads(p.read_text(encoding="utf-8"))
    steps = t.get("steps", [])
    first_user = next((s.get("message") for s in steps if s.get("source") == "user"), "") or ""
    if "Tool calls allowance: 28 calls" not in first_user:
        return None
    n = 0
    first_warn = None
    first_edit = None
    edits_after_warn = 0
    calls_after_warn = 0
    prev = None
    max_streak = streak = 0
    for s in steps:
        obs = s.get("observation")
        tcs = s.get("tool_calls") or []
        if s.get("source") != "agent" or not obs or not tcs:
            continue
        tn = (obs.get("extra") or {}).get("tool_name") or tcs[0].get("function_name")
        c = obs.get("content") or ""
        if tn in ("get_status", "submit_patch") or "mandatory input parameters" in c:
            continue
        n += 1
        args = tcs[0].get("arguments") or {}
        sig = (tn, json.dumps(args, sort_keys=True))
        streak = streak + 1 if sig == prev else 1
        prev = sig
        max_streak = max(max_streak, streak)
        is_edit = tn in ("edit_file", "write_file") or (tn == "run_command" and WRITE_CMD.search(str(args.get("command", ""))))
        if is_edit and first_edit is None:
            first_edit = n
        m = WARN.search(c)
        if m and first_warn is None:
            first_warn = n
        if first_warn is not None and n > first_warn:
            calls_after_warn += 1
            edits_after_warn += 1 if is_edit else 0
    return dict(calls=n, first_warn=first_warn, first_edit=first_edit, calls_after=calls_after_warn,
                edits_after=edits_after_warn, max_streak=max_streak)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--versions", default="v6b,v6c,v6s,v6t,v6v,v6w,v6x,v6y")
    a = ap.parse_args()
    want = set(a.versions.split(","))
    rows = []
    for p in sorted(ROOT.glob("**/trace_rich_*.json")):
        if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
            continue
        v = version_of(p)
        if not a.all and v.split("/")[0] not in want:
            continue
        try:
            r = analyse(p)
        except Exception as e:
            print("skip", p, e)
            continue
        if r is None:
            continue
        task = re.search(r"trace_(rich_\d+)\.json", p.name).group(1)
        o = OUTCOME.get((v, task)) or {}
        r.update(version=v, task=task, tag=o.get("tag", "?"))
        rows.append(r)
    print(f"28-call-regime runs analysed: {len(rows)}")
    reached = [r for r in rows if r["first_warn"] is not None]
    print(f"runs that ever showed a budget_warning: {len(reached)}  first_warn counted-call index values: "
          f"{collections.Counter(r['first_warn'] for r in reached).most_common()}")
    print("max identical-call streak across all runs:", max(r["max_streak"] for r in rows),
          " distribution:", sorted(collections.Counter(r["max_streak"] for r in rows).items()))
    print()
    print(f"{'version':12}{'task':11}{'tag':14}{'calls':>6}{'warn@':>6}{'edit@':>6}{'callsAfter':>11}{'editsAfter':>11}")
    for r in sorted(rows, key=lambda r: (r["version"], r["task"])):
        if r["first_warn"] is None:
            continue
        print(f"{r['version'][:11]:12}{r['task']:11}{r['tag']:14}{r['calls']:>6}{str(r['first_warn']):>6}{str(r['first_edit']):>6}"
              f"{r['calls_after']:>11}{r['edits_after']:>11}")
    print()
    # groups among warned runs: edited before the warning, first edited after it, never edited
    groups = collections.defaultdict(list)
    for r in reached:
        if r["first_edit"] is None:
            groups["never edited"].append(r)
        elif r["first_edit"] <= r["first_warn"]:
            groups["edited at/before first warning"].append(r)
        else:
            groups["first edit AFTER warning"].append(r)
    for k, rs in groups.items():
        c = collections.Counter(r["tag"] for r in rs)
        print(f"{k:34} n={len(rs):2}  {dict(c)}")
    no_warn = [r for r in rows if r["first_warn"] is None]
    c = collections.Counter(r["tag"] for r in no_warn)
    print(f"{'never reached a warning':34} n={len(no_warn):2}  {dict(c)}")


if __name__ == "__main__":
    main()
