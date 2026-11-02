"""CPU-only: distinct real tool-result error shapes across ALL ATIF traces.  python atif_error_shapes.py"""
import collections, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cnt = collections.Counter()
ex = {}
cmd_err_samples = []
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
        try:
            d = json.loads(c)
        except Exception:
            continue
        if not isinstance(d, dict) or d.get("status") != "error":
            continue
        d2 = {k: v for k, v in d.items() if k != "budget_warning"}
        key = (fn, d.get("error_type"), tuple(sorted(d2.keys())))
        cnt[key] += 1
        ex.setdefault(key, c[:420])
        if fn == "run_command" and isinstance(d.get("details"), dict) and d["details"].get("stdout") and len(cmd_err_samples) < 4:
            cmd_err_samples.append((json.dumps(calls[0].get("arguments"))[:120], d.get("error_message", "")[:160], d["details"]["stdout"][:120], d["details"].get("stderr", "")[:120]))
for k, n in sorted(cnt.items(), key=lambda kv: -kv[1]):
    print(n, k)
    print("    e.g.", ex[k].replace("\n", "\\n"))
print()
print("run_command errors with non-empty stdout (error_message vs details.stdout/stderr):")
for s in cmd_err_samples:
    print("  cmd:", s[0]); print("    error_message:", repr(s[1])); print("    stdout:", repr(s[2])); print("    stderr:", repr(s[3]))
