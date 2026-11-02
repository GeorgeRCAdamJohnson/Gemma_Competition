"""CPU-only: when does the real harness start attaching budget_warning?  python atif_budget_warning.py"""
import collections, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
pat = re.compile(r"Only (\d+) tool call\(s\) remaining \((\d+)/(\d+) used\)")
seen = collections.Counter()
first = []
no_warn_after = []
for p in sorted(ROOT.glob("**/trace_rich_*.json")):
    if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
        continue
    t = json.loads(p.read_text(encoding="utf-8"))
    used_calls = 0
    first_w = None
    max_used_seen_without = []
    for s in t.get("steps", []):
        if s.get("source") != "agent":
            continue
        c = (s.get("observation") or {}).get("content") or ""
        tcs = s.get("tool_calls") or []
        for tc in tcs:
            if tc.get("function_name") not in ("get_status", "submit_patch"):
                used_calls += 1
        m = pat.search(c)
        if m:
            rem, used, tot = map(int, m.groups())
            seen[(rem, used, tot)] += 1
            if first_w is None:
                first_w = (rem, used, tot, used_calls)
        elif tcs and tcs[0].get("function_name") not in ("get_status",) and "tool_calls_remaining" not in c:
            max_used_seen_without.append(used_calls)
    if first_w:
        first.append(first_w)
print("distinct (remaining, used, total) warning pairs seen:")
for k, n in sorted(seen.items()):
    print("  ", k, n)
print("earliest warning per run: min used =", min(f[1] for f in first), "max remaining =", max(f[0] for f in first), "runs with warnings:", len(first))
print("(rem,used,tot,calls_counted_by_me) for first 10 runs:", first[:10])
