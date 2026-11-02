"""CPU-only probe: print the exact tool-result text Kaggle returns for a missing-mandatory-parameter call."""
import json, re, sys
from pathlib import Path

p = Path(sys.argv[1])
t = json.loads(p.read_text(encoding="utf-8"))
steps = t.get("steps") or t.get("trajectory", {}).get("steps") or []
n = 0
for s in steps:
    blob = json.dumps(s, ensure_ascii=False)
    if "mandatory input parameters" in blob:
        n += 1
        if n <= 2:
            obs = s.get("observation")
            print(json.dumps(obs, ensure_ascii=False)[:900])
            print("tool_calls:", json.dumps(s.get("tool_calls"), ensure_ascii=False)[:600])
            print("---")
print("matches:", n, "steps:", len(steps), "keys:", list(t.keys())[:10])
