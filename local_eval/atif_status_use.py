"""CPU-only: how the real 31B uses the free get_status call, and how much of the 8-minute wall clock runs use.
python atif_status_use.py [--versions v6b,v6c,...]

Uses per-step extra.elapsed_s from the Kaggle ATIF traces (28-call regime only). A step's cost is its elapsed_s minus
the previous step's, so it includes the model's generation time plus the tool call.
"""
import argparse, collections, json, re, statistics as st
import atif_behavior_outcomes as B

ROOT = B.ROOT


def timing(p):
    t = json.loads(p.read_text(encoding="utf-8"))
    prev = 0.0
    turns = n_status = 0
    status_s = 0.0
    status_tok = 0
    total_s = 0.0
    for s in t.get("steps", []):
        e = (s.get("extra") or {}).get("elapsed_s")
        if e is None:
            continue
        e = float(e)
        dt = e - prev
        prev = e
        total_s = e
        tcs = s.get("tool_calls") or []
        if s.get("source") != "agent" or not tcs:
            continue
        turns += 1
        if tcs[0].get("function_name") == "get_status":
            n_status += 1
            status_s += dt
            status_tok += int(((s.get("metrics") or {}).get("completion_tokens")) or 0)
    return dict(turns=turns, n_status=n_status, status_s=status_s, status_tok=status_tok, total_s=total_s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", default="v6b,v6c,v6s,v6t,v6v,v6w,v6x,v6y")
    a = ap.parse_args()
    want = set(a.versions.split(","))
    rows = []
    for p in sorted(ROOT.glob("**/trace_rich_*.json")):
        if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
            continue
        v = B.version_of(p)
        if v.split("/")[0] not in want:
            continue
        r = B.analyse(p)
        if r is None:
            continue
        task = re.search(r"trace_(rich_\d+)\.json", p.name).group(1)
        o = B.OUTCOME.get((v, task))
        if o is None:
            continue
        r.update(timing(p))
        r.update(version=v, task=task, resolved=bool(o["resolved"]))
        rows.append(r)
    n = len(rows)
    print(f"runs={n} resolved={sum(r['resolved'] for r in rows)}")
    ns = [r["n_status"] for r in rows]
    tu = [r["turns"] for r in rows]
    print(f"get_status calls per run: mean={st.mean(ns):.1f} median={st.median(ns)} max={max(ns)}  "
          f"runs with 0: {sum(1 for x in ns if x == 0)}")
    print(f"agent turns per run: mean={st.mean(tu):.1f}; get_status share of turns = {100*sum(ns)/sum(tu):.1f}%")
    ss = sum(r["status_s"] for r in rows)
    ts = sum(r["total_s"] for r in rows)
    print(f"wall time on get_status turns = {100*ss/ts:.1f}% of {ts/n:.0f}s mean run; "
          f"mean seconds per get_status turn = {ss/max(1,sum(ns)):.1f}; mean completion tokens = "
          f"{sum(r['status_tok'] for r in rows)/max(1,sum(ns)):.0f}")
    el = sorted(r["total_s"] for r in rows)
    print(f"run elapsed seconds: min={el[0]:.0f} median={st.median(el):.0f} p90={el[int(0.9*(n-1))]:.0f} max={el[-1]:.0f}; "
          f"runs >= 420s: {sum(1 for x in el if x >= 420)}, >= 480s: {sum(1 for x in el if x >= 480)}")
    ends = collections.Counter()
    for r in rows:
        if r["total_s"] >= 470:
            ends["time cap (>=470s)"] += 1
        elif r["calls"] >= 28:
            ends["28-call cap"] += 1
        elif r["submitted"]:
            ends["submitted early"] += 1
        else:
            ends["other"] += 1
    print("how runs ended:", dict(ends))
    print("\nper version: runs, resolved, mean elapsed s, mean get_status calls, mean counted calls")
    byv = collections.defaultdict(list)
    for r in rows:
        byv[r["version"]].append(r)
    for v, rs in sorted(byv.items()):
        print(f"  {v:10s} n={len(rs):2d} resolved={sum(x['resolved'] for x in rs):2d} "
              f"elapsed={st.mean(x['total_s'] for x in rs):4.0f}s status={st.mean(x['n_status'] for x in rs):4.1f} "
              f"calls={st.mean(x['calls'] for x in rs):4.1f}")
    print("\nWithin-task (Mantel-Haenszel) leads only; reverse causality possible:")
    for name, pred in (("no get_status at all", lambda r: r["n_status"] == 0),
                       ("get_status >= 3", lambda r: r["n_status"] >= 3),
                       ("get_status >= 5", lambda r: r["n_status"] >= 5),
                       ("elapsed >= 420s", lambda r: r["total_s"] >= 420)):
        m = B.mh(rows, pred)
        z = m["z"]
        print(f"  {name:22s} exposed n={m['n_e']:2d} rate={m['r_e']:.2f} | unexposed n={m['n_u']:2d} rate={m['r_u']:.2f} "
              f"| z={'n/a' if z is None else f'{z:+.2f}'} informative strata={m['inform']}")


if __name__ == "__main__":
    main()
