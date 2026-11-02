"""CPU-only: how often is real Kaggle thinking cut at the budget? (thinking-step length histogram per version)
python atif_budget_hits.py
"""
import collections, json, re, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUD = {"v6b": 4096, "v6c": 4096, "v6s": 4096, "v6t": 4096, "v6x": 4096, "v6v": 2048, "v6w": 1024, "v6y": 1024}
OUT = json.loads((ROOT / "local_eval" / "runs" / "kaggle_outcomes.json").read_text())
OUTCOME = {(r["version"], r["task"]): r["tag"] for r in OUT}
for v, b in BUD.items():
    L, per_task = [], collections.defaultdict(list)
    for p in sorted(ROOT.glob(f"submit_{v}/**/trace_rich_*.json")):
        if "local_eval" in p.parts:
            continue
        t = json.loads(p.read_text(encoding="utf-8"))
        task = re.search(r"(rich_\d+)", p.name).group(1)
        for s in t.get("steps", []):
            if s.get("source") != "agent":
                continue
            if (s.get("extra") or {}).get("event_type") != "thinking":
                continue
            n = len(s.get("message") or "")
            L.append(n)
            per_task[task].append(n)
    if not L:
        continue
    cap_chars = b * 3.2
    hit = sum(1 for n in L if n >= cap_chars)
    print(f"{v}: budget {b} tok (~{int(cap_chars)}+ chars): thinking steps n={len(L)} median={statistics.median(L):.0f} "
          f"p90={sorted(L)[int(len(L)*.9)]} max={max(L)} steps>=cap={hit} ({100*hit/len(L):.1f}%)  >=half-cap={sum(1 for n in L if n >= cap_chars/2)}")
