"""CPU-only: how many counted calls do the real 31B runs (28-call regime) spend on read_file calls that return little new
information: (a) 'head' reads = no start_line on a file longer than 150 lines (returns lines 1-150 only), (b) re-reads =
a read_file whose line span overlaps an earlier read of the same file in the same run.
python atif_read_waste.py [--versions ...]
"""
import argparse, collections, json, re, statistics
import atif_behavior_outcomes as B

ROOT = B.ROOT


def analyse(p):
    t = json.loads(p.read_text(encoding="utf-8"))
    n = 0
    seen = collections.defaultdict(list)
    head = rereads = reads = 0
    for s in t.get("steps", []):
        obs = s.get("observation")
        tcs = s.get("tool_calls") or []
        if s.get("source") != "agent" or not obs or not tcs:
            continue
        tn = (obs.get("extra") or {}).get("tool_name") or tcs[0].get("function_name")
        c = obs.get("content") or ""
        if tn in ("get_status", "submit_patch") or B.MALFORMED in c:
            continue
        n += 1
        if tn != "read_file":
            continue
        reads += 1
        try:
            j = json.loads(c)
        except Exception:
            continue
        if j.get("status") != "ok":
            continue
        fp, a, b = j.get("filepath"), j.get("start_line"), j.get("end_line")
        args = tcs[0].get("arguments") or {}
        if not args.get("start_line") and (j.get("total_lines") or 0) > 150:
            head += 1
        elif any(not (b < x or a > y) for x, y in seen[fp]):
            rereads += 1
        seen[fp].append((a, b))
    return dict(calls=n, reads=reads, head=head, rereads=rereads)


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
        w = analyse(p)
        w.update(task=task, version=v, resolved=bool(o["resolved"]), first_edit=r["first_edit"])
        rows.append(w)
    N = len(rows)
    tot = sum(r["calls"] for r in rows)
    print(f"runs={N} counted calls={tot}")
    for k in ("reads", "head", "rereads"):
        print(f"{k:8} total={sum(r[k] for r in rows):4}  mean/run={statistics.mean(r[k] for r in rows):.2f}  share of calls={sum(r[k] for r in rows) / tot:.1%}")
    print("runs with >=2 head reads:", sum(r["head"] >= 2 for r in rows), " with >=1:", sum(r["head"] >= 1 for r in rows))
    print()
    print("per task: mean head reads / mean rereads / mean first_edit (None counted as 29)")
    by = collections.defaultdict(list)
    for r in rows:
        by[r["task"]].append(r)
    for t, rs in sorted(by.items()):
        print(f"  {t}: n={len(rs):2} head={statistics.mean(x['head'] for x in rs):.2f} rereads={statistics.mean(x['rereads'] for x in rs):.2f} "
              f"first_edit={statistics.mean((x['first_edit'] or 29) for x in rs):.1f} resolved={sum(x['resolved'] for x in rs)}/{len(rs)}")
    for name, pred in (("head>=2", lambda r: r["head"] >= 2), ("head>=1", lambda r: r["head"] >= 1),
                       ("head+rereads>=3", lambda r: r["head"] + r["rereads"] >= 3)):
        m = B.mh(rows, pred)
        zs = "n/a" if m["z"] is None else f"{m['z']:+.2f}"
        print(f"{name:18} n_exp={m['n_e']:3} rate={m['r_e']:.2f}  n_unexp={m['n_u']:3} rate={m['r_u']:.2f}  MH OR={m['or_mh']:.2f} z={zs} RDstrat={m['rd']:+.2f} strata={m['inform']}")


if __name__ == "__main__":
    main()
