"""CPU-only probe: do missing-mandatory-parameter edit_file calls consume the 28-call budget on Kaggle?
For traces that contain such errors, compare total tool calls vs calls that were not rejected at validation."""
import json, glob, re

rows = []
for p in glob.glob(r"..\**\trace_rich_*.json", recursive=True):
    try:
        t = json.loads(open(p, encoding="utf-8").read())
    except Exception:
        continue
    total = miss = budget = status_calls = 0
    last_status = None
    first_budget_idx = None
    counted_before_budget = None
    for s in t.get("steps", []):
        obs = s.get("observation")
        if not obs:
            continue
        tn = (obs.get("extra") or {}).get("tool_name")
        c = obs.get("content") or ""
        if tn is None:
            continue
        if tn == "get_status":
            status_calls += 1
            m = re.search(r'tool_calls_used\\?"?: ?(\d+)', c)
            if m:
                last_status = (total, int(m.group(1)))
            continue
        total += 1
        if "mandatory input parameters" in c:
            miss += 1
        if "BudgetExceeded" in c or "budget" in c.lower() and "exhausted" in c.lower():
            budget += 1
            if first_budget_idx is None:
                first_budget_idx = total
                counted_before_budget = total - miss
    if miss:
        rows.append((p, total, miss, budget, first_budget_idx, counted_before_budget, last_status))
rows.sort(key=lambda r: -r[2])
for r in rows[:25]:
    print(r)
print("traces with missing-param errors:", len(rows))
