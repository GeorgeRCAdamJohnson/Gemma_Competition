"""CPU-only: is get_status.patch_size nonzero before submit_patch (i.e. does it track the working tree)?  python atif_status_patchsize.py"""
import collections, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
cnt = collections.Counter()
ex = {}
for p in sorted(ROOT.glob("**/trace_rich_*.json")):
    if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
        continue
    t = json.loads(p.read_text(encoding="utf-8"))
    edited = False
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
            d = {}
        if fn in ("edit_file", "write_file") and isinstance(d, dict) and d.get("status") == "ok":
            edited = True
        if fn == "get_status" and isinstance(d, dict) and "patch_size" in d:
            key = ("edited_before" if edited else "no_edit_before", "patch_submitted=%s" % d.get("patch_submitted"), "patch_size>0" if d.get("patch_size") else "patch_size==0")
            cnt[key] += 1
            ex.setdefault(key, (p.name, c[:200]))
for k, n in sorted(cnt.items()):
    print(n, k, ex[k])
