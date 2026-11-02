"""CPU-only: print the call sequence (+ a bit of reasoning) of one ATIF trace.  python atif_seq.py <trace.json> [--reason N]"""
import json, sys, re
from pathlib import Path

p = Path(sys.argv[1])
nr = int(sys.argv[sys.argv.index("--reason") + 1]) if "--reason" in sys.argv else 160
t = json.loads(p.read_text(encoding="utf-8"))
n = 0
for i, s in enumerate(t["steps"]):
    if s.get("source") != "agent":
        continue
    tcs = s.get("tool_calls") or []
    obs = s.get("observation") or {}
    rc = (s.get("reasoning_content") or "").replace("\n", " ")
    msg = (s.get("message") or "").replace("\n", " ")
    if not tcs:
        print(f"#{i} TEXT msg={len(msg)}c rc={len(rc)}c :: {msg[:nr]!r}")
        continue
    for tc in tcs:
        fn = tc.get("function_name")
        a = tc.get("arguments") or {}
        if fn == "run_command":
            d = str(a.get("command"))[:110].replace("\n", " ")
        elif fn in ("read_file",):
            d = f"{a.get('filepath')}:{a.get('start_line')}-{a.get('end_line')}"
        elif fn in ("edit_file",):
            d = f"{a.get('filepath')} old={len(str(a.get('old_string','')))}c new={len(str(a.get('new_string','')))}c keys={sorted(a)}"
        else:
            d = json.dumps(a)[:100]
        c = (obs.get("content") or "")
        status = "ERR" if ('"error"' in c or "error_message" in c) else "ok"
        if fn != "get_status":
            n += 1
        print(f"#{i} call{n:>3} {fn:18} {d} -> {status} {len(c)}c | rc={len(rc)}c :: {rc[:nr]!r}")
