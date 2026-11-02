"""CPU-only: how does the REAL harness treat absolute / odd paths in read_file / write_file / edit_file?  python atif_abs_paths.py"""
import collections, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows = collections.defaultdict(collections.Counter)
samples = {}
for p in sorted(ROOT.glob("**/trace_rich_*.json")):
    if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
        continue
    t = json.loads(p.read_text(encoding="utf-8"))
    for s in t.get("steps", []):
        if s.get("source") != "agent":
            continue
        calls = s.get("tool_calls") or []
        c = (s.get("observation") or {}).get("content")
        if len(calls) != 1 or not isinstance(c, str):
            continue
        fn = calls[0].get("function_name")
        if fn not in ("read_file", "write_file", "edit_file"):
            continue
        a = calls[0].get("arguments") or {}
        fp = a.get("filepath") or a.get("path") or ""
        if not isinstance(fp, str) or not fp.startswith("/"):
            continue
        try:
            d = json.loads(c)
        except Exception:
            d = {}
        kind = fp.split("/")[1] if len(fp.split("/")) > 1 else ""
        bucket = "workspace" if kind == "workspace" else ("tmp" if kind == "tmp" else "other:" + kind)
        res = d.get("status") if isinstance(d, dict) else "?"
        et = d.get("error_type") if isinstance(d, dict) else None
        rows[(fn, bucket)][(res, et)] += 1
        samples.setdefault((fn, bucket, res, et), (fp, c[:240].replace("\n", "\\n")))
for k in sorted(rows):
    print(k, dict(rows[k]))
print()
for k, v in samples.items():
    print(k, "->", v)
