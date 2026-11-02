"""CPU-only: share of counted tool calls per tool in the real 31B runs (28-call regime), and what the graph/search
tools return. python atif_tool_mix.py [--versions ...]
"""
import argparse, collections, json
import atif_behavior_outcomes as B

ROOT = B.ROOT


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", default="v6b,v6c,v6s,v6t,v6v,v6w,v6x,v6y")
    a = ap.parse_args()
    want = set(a.versions.split(","))
    tools = collections.Counter()
    runs_using = collections.Counter()
    runs = 0
    samples = collections.defaultdict(list)
    for p in sorted(ROOT.glob("**/trace_rich_*.json")):
        if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
            continue
        if B.version_of(p).split("/")[0] not in want:
            continue
        t = json.loads(p.read_text(encoding="utf-8"))
        runs += 1
        used = set()
        for s in t.get("steps", []):
            obs = s.get("observation")
            tcs = s.get("tool_calls") or []
            if s.get("source") != "agent" or not obs or not tcs:
                continue
            tn = (obs.get("extra") or {}).get("tool_name") or tcs[0].get("function_name")
            c = obs.get("content") or ""
            if tn in ("get_status", "submit_patch") or B.MALFORMED in c:
                continue
            tools[tn] += 1
            used.add(tn)
            if tn in ("get_code_neighbors", "search_similar_code", "get_code_subgraph") and len(samples[tn]) < 3:
                samples[tn].append((json.dumps(tcs[0].get("arguments"))[:120], c[:200].replace("\n", " ")))
        for u in used:
            runs_using[u] += 1
    total = sum(tools.values())
    print(f"runs={runs} counted calls={total}")
    for tn, n in tools.most_common():
        print(f"  {tn:22s} calls={n:4d} ({100*n/total:4.1f}%)  runs using={runs_using[tn]}/{runs}")
    for tn, rows in samples.items():
        print(f"--- {tn} samples")
        for args, res in rows:
            print(f"   args={args}\n   -> {res}")


if __name__ == "__main__":
    main()
