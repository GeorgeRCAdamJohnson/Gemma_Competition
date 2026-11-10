# Runs ON the GPU VM: per-task smoke results so far vs the Kaggle pack-1 reference.
import json
from pathlib import Path

REF = {"fastapi_14786": (20, 51), "fastapi_14301": (20, 91), "rich_3905": (20, 115),
       "rich_3006": (19, 86), "rich_3067": (14, 127), "fastapi_9555": (13, 184)}
r = Path("/content/work/results/task_results.jsonl")
rows = [json.loads(l) for l in r.read_text().splitlines() if l.strip()] if r.exists() else []
print(f"{len(rows)}/6 done | solved {sum(bool(x['resolved']) for x in rows)}")
for x in rows:
    k, d = REF.get(x["instance_id"], (None, None))
    print(f"  {x['instance_id']:15s} resolved={str(x['resolved']):5s} dur={x['duration_seconds']:7.1f}s "
          f"(kaggle {k}/20, mean {d}s) calls={x.get('tool_calls')} patch={x.get('agent_patch_size')} "
          f"exit={x.get('test_exit_code')} err={str(x.get('error'))[:70]}")
s = Path("/content/smoke.log").read_text(errors="replace").splitlines()
done = [l for l in s if "SMOKE DONE" in l]
print("run finished:", done[-1] if done else "no")
