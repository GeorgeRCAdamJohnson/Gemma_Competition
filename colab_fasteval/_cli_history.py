# Run in WSL: event-by-event Colab CLI history for the given sessions (default: survivors vs reclaimed).
import json
import os
import sys

for name in sys.argv[1:] or ["e4bab", "e4bvote", "e4bvm2", "e4bloc5"]:
    f = os.path.expanduser(f"~/.config/colab-cli/history/{name}.jsonl")
    print(f"== {name}")
    for line in open(f, errors="replace"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        code = r.get("code") or ""
        first = next((x for x in code.splitlines() if x.strip() and not x.startswith("#")), code[:80]) if code else ""
        head = code.splitlines()[0][:70] if code else ""
        print(f"  {str(r.get('timestamp'))[:19]} {r.get('type') or '':10s} {r.get('event_type') or r.get('op') or '':18s} "
              f"{r.get('reason') or ''} {head} | {first[:60]}")
