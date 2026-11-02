"""Print the tool-call sequence of one local gate run.  python seq_local.py <tag> <task> [--reason N]"""
import json, sys
from pathlib import Path

tag, task = sys.argv[1], sys.argv[2]
nr = int(sys.argv[sys.argv.index("--reason") + 1]) if "--reason" in sys.argv else 100
rows = [json.loads(l) for l in (Path(__file__).parent / "runs" / f"{tag}.trace.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
turn = {}
for r in rows:
    if r.get("task") != task:
        continue
    if r["kind"] == "turn":
        turn[r["turn"]] = r
        print(f"T{r['turn']:>2} {r['t']:>6.0f}s {r['secs']:>5.1f}s fin={r['finish']:<10} ptok={r['ptok']:>6} ctok={r['ctok']:>5} rc={r['reasoning_chars']:>5} cc={r['content_chars']:>5} tools={','.join(r['tools'])}")
        if r["reasoning_chars"] and nr:
            print(f"      R: {r['reasoning_head'][:nr]!r}")
        if r["content_chars"] and nr:
            print(f"      C: {r['content_head'][:nr]!r}")
    elif r["kind"] == "tool":
        a = r.get("args_head") or ""
        print(f"      call#{r.get('call')} {r['tool']} {r.get('path') or ''} {r.get('start')}-{r.get('end')} q={r.get('query')} -> {r['status']} {r.get('strategy') or ''} {(r.get('error') or '')[:80]} | {a[:90]}")
    else:
        print(f"   [{r['kind']}] " + json.dumps({k: v for k, v in r.items() if k not in ('task', 'kind')})[:200])
