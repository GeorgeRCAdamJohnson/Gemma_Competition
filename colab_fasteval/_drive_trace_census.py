# Runs ON a VM with Drive mounted: count trace files and solved-with-trace per A/B tag on Drive (LoRA pool census).
import collections
import json
from pathlib import Path

root = Path("/content/drive/MyDrive/gemma_fasteval/ab_runs")
for tag in sorted(p for p in root.iterdir() if p.is_dir()):
    n_tr = n_res = n_ok = n_ok_tr = 0
    solved = collections.Counter()
    for tr in tag.rglob("task_results.jsonl"):
        d = tr.parent
        for line in tr.read_text(errors="replace").splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            n_res += 1
            if r.get("resolved"):
                n_ok += 1
                solved[r["instance_id"]] += 1
                if (d / "traces" / f"trace_{r['instance_id']}.json").exists():
                    n_ok_tr += 1
    n_tr = sum(1 for _ in tag.rglob("trace_*.json"))
    print(f"{tag.name:40s} results {n_res:5d} solved {n_ok:4d} solved_w_trace {n_ok_tr:4d} traces {n_tr:5d} "
          f"distinct_solved {len(solved)}", flush=True)
