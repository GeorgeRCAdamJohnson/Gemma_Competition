"""Edit-tool outcomes across all Kaggle ATIF traces: status / strategy / error text.  CPU only."""
import collections, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
strat = collections.Counter()
errs = collections.Counter()
per_ver = collections.defaultdict(collections.Counter)
examples = {}
n_calls = 0
for p in sorted(ROOT.glob("**/results/traces/trace_*.json")):
    if "local_eval" in p.parts:
        continue
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception:
        continue
    ver = p.parts[len(ROOT.parts)]
    for s in d.get("steps", []):
        for tc in s.get("tool_calls") or []:
            if tc.get("function_name") != "edit_file":
                continue
            n_calls += 1
            obs = (s.get("observation") or {}).get("content") or ""
            try:
                o = json.loads(obs)
            except Exception:
                o = {"status": "unparsed", "raw": obs[:120]}
            st = o.get("status")
            if st == "ok":
                strat[o.get("strategy")] += 1
                per_ver[ver]["ok:" + str(o.get("strategy"))] += 1
            else:
                msg = (o.get("error") or o.get("message") or o.get("raw") or str(o))[:110]
                errs[msg] += 1
                per_ver[ver]["err"] += 1
                examples.setdefault(msg, (str(p.relative_to(ROOT)), json.dumps(tc.get("arguments"))[:300], obs[:300]))
print("edit_file calls:", n_calls)
print("success strategies:", dict(strat))
print("errors:")
for k, v in errs.most_common(12):
    print(f"  {v:3d}  {k}")
print()
for k, (pth, args, obs) in list(examples.items())[:4]:
    print("EX:", pth)
    print("   args:", args)
    print("   obs :", obs)
print()
for v, c in per_ver.items():
    print(f"{v[:26]:28}", dict(c))
