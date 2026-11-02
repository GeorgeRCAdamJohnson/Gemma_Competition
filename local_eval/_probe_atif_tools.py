import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
p = ROOT / "submit_v6w" / "out_v6w" / "results" / "traces" / "trace_rich_4079.json"
d = json.load(open(p, encoding="utf-8"))
print("top keys:", list(d.keys()))
ag = d.get("agent") or {}
print("agent keys:", list(ag.keys()))
td = ag.get("tool_definitions") or d.get("tool_definitions")
print("tool_definitions:", type(td).__name__, (len(td) if td else None))
if td:
    for t in td:
        print(json.dumps(t, ensure_ascii=False)[:900])
        print("---")
st = d.get("steps", [])
print("n steps", len(st))
for s in st[:2]:
    print({k: (str(v)[:160]) for k, v in s.items()})
