"""CPU-only: per-run behaviour features from the real Kaggle ATIF traces (28-call regime), joined to outcomes.
python atif_null_mechanisms.py [--versions v6w,v6x,...] [--all]
"""
import argparse, collections, glob, json, re, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = json.loads((ROOT / "local_eval" / "runs" / "kaggle_outcomes.json").read_text())
OUTCOME = {(r["version"], r["task"]): r for r in OUT}

WRITE_CMD = re.compile(r"(sed\s+-i|>\s*[\w./-]+\.py|cat\s*>|tee\s|python3?\s+-\s*<<|python3?\s+-c|git\s+apply|patch\s+-p|perl\s+-pi|open\([^)]*['\"]w)")
READ_CMD = re.compile(r"^\s*(sed\s+-n|cat\s|head\s|tail\s|grep\s|rg\s|nl\s|ls\b|find\s|wc\s|awk\s)")


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
    seq = []                     # counted calls, in order
    n_missing = n_status = 0
    budget_hit = False
    asst_msgs = 0
    max_msg = 0
    for s in steps:
        if s.get("source") == "agent":
            asst_msgs += 1
            max_msg = max(max_msg, len(s.get("message") or ""))
        obs = s.get("observation")
        tcs = s.get("tool_calls") or []
        if not obs or not tcs:
            continue
        tn = (obs.get("extra") or {}).get("tool_name") or tcs[0].get("function_name")
        c = obs.get("content") or ""
        if tn == "get_status":
            n_status += 1
            continue
        if "mandatory input parameters" in c:
            n_missing += 1
            continue
        if "BudgetExceeded" in c or ("budget" in c.lower() and "exhausted" in c.lower()):
            budget_hit = True
        args = tcs[0].get("arguments") or {}
        kind = tn
        if tn == "run_command":
            cmd = str(args.get("command", ""))
            kind = "run:write" if WRITE_CMD.search(cmd) else ("run:read" if READ_CMD.search(cmd) else "run:other")
        ok = None
        if tn in ("edit_file", "write_file"):
            ok = ('"strategy"' in c) or ('\\"strategy\\"' in c) or tn == "write_file" and '"error' not in c
        seq.append((kind, ok))
    edits_ok = [i for i, (k, ok) in enumerate(seq, 1) if k in ("edit_file", "write_file") and ok]
    first_edit_attempt = next((i for i, (k, _) in enumerate(seq, 1) if k in ("edit_file", "write_file", "run:write")), None)
    submitted = any(k == "submit_patch" for k, _ in seq)
    return dict(calls=len([1 for k, _ in seq if k != "submit_patch"]), missing=n_missing, status=n_status, budget=budget_hit,
                first_edit_attempt=first_edit_attempt, first_edit_ok=(edits_ok[0] if edits_ok else None),
                run_write=sum(1 for k, _ in seq if k == "run:write"), submitted=submitted,
                kinds=collections.Counter(k for k, _ in seq), max_msg=max_msg, steps=len(steps))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", default="v6w,v6x,v6y,v6c,v6t,v6b")
    ap.add_argument("--all", action="store_true")
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
        o = OUTCOME.get((v, task))
        r.update(version=v, task=task, tag=(o or {}).get("tag", "?"), dur=(o or {}).get("dur"), chars=(o or {}).get("chars"),
                 kcalls=(o or {}).get("calls"))
        rows.append(r)
    print(f"runs analysed: {len(rows)}")
    print(f"{'version':16}{'task':11}{'tag':18}{'calls':>6}{'kcall':>6}{'miss':>5}{'1stEditTry':>11}{'1stEditOK':>10}{'run:w':>6}{'subm':>5}{'budg':>5}  kinds")
    for r in sorted(rows, key=lambda r: (r["version"], r["task"])):
        k = ",".join(f"{a}={b}" for a, b in sorted(r["kinds"].items()))
        print(f"{r['version'][:15]:16}{r['task']:11}{r['tag']:18}{r['calls']:>6}{str(r['kcalls']):>6}{r['missing']:>5}"
              f"{str(r['first_edit_attempt']):>11}{str(r['first_edit_ok']):>10}{r['run_write']:>6}{str(r['submitted'])[0]:>5}{str(r['budget'])[0]:>5}  {k}")
    # aggregate: where do the calls go in runs that never wrote anything?
    nulls = [r for r in rows if r["first_edit_attempt"] is None]
    print(f"\nruns with NO edit attempt at all: {len(nulls)}/{len(rows)}")
    for r in nulls:
        print("  ", r["version"], r["task"], r["tag"], "calls", r["calls"], dict(r["kinds"]), "miss", r["missing"])
    late = [r["first_edit_attempt"] for r in rows if r["first_edit_attempt"]]
    if late:
        print("first-edit-attempt call index: median", statistics.median(late), "p75", sorted(late)[int(len(late) * .75)], "max", max(late))
    res = [r for r in rows if r["tag"] == "RESOLVED"]
    wrong = [r for r in rows if r["tag"] == "wrong-patch"]
    for name, grp in (("RESOLVED", res), ("wrong-patch", wrong)):
        xs = [r["first_edit_attempt"] for r in grp if r["first_edit_attempt"]]
        if xs:
            print(f"{name}: n={len(grp)} first-edit-attempt median={statistics.median(xs)} mean={statistics.mean(xs):.1f}")


if __name__ == "__main__":
    main()
