"""CPU-only: show the real result JSON shapes of Kaggle run_command / read_file / edit_file / submit_patch.  python atif_result_shapes.py"""
import collections, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
shape = collections.Counter()
examples = {}
for p in sorted((ROOT / "submit_v6w" / "out_v6w" / "results" / "traces").glob("trace_rich_*.json")):
    t = json.loads(p.read_text(encoding="utf-8"))
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
            key = (fn, "NONJSON")
            shape[key] += 1
            examples.setdefault(key, (c[:300], json.dumps(calls[0].get("arguments"))[:160]))
            continue
        if isinstance(d, dict):
            key = (fn, tuple(sorted(d.keys())), d.get("status"))
            if isinstance(d.get("details"), dict):
                key += (tuple(sorted(d["details"].keys())),)
            shape[key] += 1
            examples.setdefault(key, (c[:400], json.dumps(calls[0].get("arguments"))[:160]))
        else:
            key = (fn, type(d).__name__)
            shape[key] += 1
            examples.setdefault(key, (c[:300], json.dumps(calls[0].get("arguments"))[:160]))
for k, n in sorted(shape.items(), key=lambda kv: -kv[1]):
    print(n, k)
    ex = examples.get(k)
    if ex:
        print("     e.g.", ex[0].replace("\n", "\\n")[:400])
        print("     args", ex[1])
