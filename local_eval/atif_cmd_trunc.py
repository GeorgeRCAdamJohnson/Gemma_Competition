"""CPU-only: how does the REAL run_command mark truncated stdout/stderr?  python atif_cmd_trunc.py"""
import collections, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
lens = collections.Counter()
shown = 0
for p in sorted(ROOT.glob("**/trace_rich_*.json")):
    if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
        continue
    t = json.loads(p.read_text(encoding="utf-8"))
    for s in t.get("steps", []):
        if s.get("source") != "agent":
            continue
        calls = s.get("tool_calls") or []
        c = (s.get("observation") or {}).get("content")
        if len(calls) != 1 or not isinstance(c, str) or calls[0].get("function_name") != "run_command":
            continue
        try:
            d = json.loads(c)
        except Exception:
            continue
        if not isinstance(d, dict):
            continue
        so = d.get("stdout")
        if so is None and isinstance(d.get("details"), dict):
            so = d["details"].get("stdout")
        if so is None:
            continue
        n = len(so)
        lens[min(n // 1000, 9)] += 1
        if n >= 4900 and shown < 5:
            shown += 1
            print("len", n, "tail repr:", repr(so[-90:]), "| head repr:", repr(so[:50]))
print(sorted(lens.items()))
