"""CPU-only: when does the REAL read_file set is_truncated?  python atif_read_trunc.py"""
import collections, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cnt = collections.Counter()
ex = {}
for p in sorted(ROOT.glob("**/trace_rich_*.json")):
    if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
        continue
    t = json.loads(p.read_text(encoding="utf-8"))
    for s in t.get("steps", []):
        if s.get("source") != "agent":
            continue
        calls = s.get("tool_calls") or []
        c = (s.get("observation") or {}).get("content")
        if len(calls) != 1 or not isinstance(c, str) or calls[0].get("function_name") != "read_file":
            continue
        try:
            d = json.loads(c)
        except Exception:
            continue
        if not isinstance(d, dict) or d.get("status") != "ok":
            continue
        a = calls[0].get("arguments") or {}
        rs, re_ = a.get("start_line"), a.get("end_line")
        try:
            rs = int(rs) if rs is not None else None
            re_ = int(re_) if re_ is not None else None
        except Exception:
            continue
        total, el, trunc = d.get("total_lines"), d.get("end_line"), d.get("is_truncated")
        sl = d.get("start_line")
        asked = "explicit_end" if re_ is not None else "no_end"
        reached_total = (el == total)
        span_ok = (re_ is None) or (el == min(re_, total))
        key = (asked, "end==total" if reached_total else "end<total", "returned_all_requested" if span_ok else "cut_short", "trunc=%s" % trunc)
        cnt[key] += 1
        ex.setdefault(key, (json.dumps(a)[:100], sl, el, total, len(d.get("content", ""))))
for k, n in sorted(cnt.items()):
    print(n, k, "e.g. args/start/end/total/chars:", ex[k])
