"""CPU-only: do FREE tools (get_status / submit_patch) carry budget_warning in the real harness?  python atif_status_warning.py"""
import collections, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cnt = collections.Counter()
ex = {}
for p in sorted(ROOT.glob("**/trace_rich_*.json")):
    if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
        continue
    t = json.loads(p.read_text(encoding="utf-8"))
    used = 0
    total = None
    for s in t.get("steps", []):
        if s.get("source") != "agent":
            continue
        calls = s.get("tool_calls") or []
        c = (s.get("observation") or {}).get("content")
        if len(calls) != 1 or not isinstance(c, str):
            continue
        fn = calls[0].get("function_name")
        try:
            d = json.loads(c)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        if fn == "get_status" and "max_tool_calls" in d:
            total = d["max_tool_calls"]
            u = d.get("tool_calls_used")
            rem = d.get("tool_calls_remaining")
            has = "budget_warning" in d
            key = (fn, "warn" if has else "nowarn", "late(rem<=10,total>=20)" if (rem is not None and rem <= 10 and total >= 20) else "early")
            cnt[key] += 1
            ex.setdefault(key, c[:330])
        elif fn == "submit_patch":
            has = "budget_warning" in d
            key = (fn, "warn" if has else "nowarn", d.get("status"))
            cnt[key] += 1
            ex.setdefault(key, c[:330])
for k, n in sorted(cnt.items()):
    print(n, k)
    print("    e.g.", ex[k].replace("\n", "\\n"))
