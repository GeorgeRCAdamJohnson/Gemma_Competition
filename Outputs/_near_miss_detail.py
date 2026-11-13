# For the strongest near-miss tasks: in the BEST unsolved run, which tests failed (new = fail-to-pass vs old = regression),
# and which prompt/config produced the runs (source dir).
import json
import re
from collections import Counter
from pathlib import Path

T = {json.loads(l)["instance_id"]: json.loads(l) for l in Path("Outputs/e4b_variance3/tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
NEW = {k: set(re.findall(r"^\+\s*(?:async\s+)?def (test_\w+)", t["test_patch"], re.M)) for k, t in T.items()}
for tid in ("rich_3130", "rich_3675", "rich_3782", "fastapi_14794", "fastapi_15763", "rich_3506", "rich_4075", "rich_3052"):
    best, srcs = None, Counter()
    for tr in Path("Outputs").rglob("task_results.jsonl"):
        for l in tr.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                r = json.loads(l)
            except Exception:
                continue
            if r.get("instance_id") != tid:
                continue
            srcs[tr.relative_to("Outputs").parts[0]] += 1
            to = tr.parent / "test_outputs" / f"{tid}.log"
            if r.get("resolved") or not to.exists():
                continue
            txt = to.read_text(errors="replace")
            fails = re.findall(r"^(?:FAILED|ERROR) \S+::(\w+)(\[[^\]]*\])?", txt, re.M)
            if best is None or len(fails) < len(best[0]):
                best = (fails, tr.parent)
    print(f"\n{tid}: runs by source {dict(srcs)} | new tests {len(NEW[tid])}")
    if best:
        new = [f + p for f, p in best[0] if f in NEW[tid]]
        old = [f + p for f, p in best[0] if f not in NEW[tid]]
        print(f"  best unsolved run ({best[1].relative_to('Outputs')}): new-test failures {new[:4]} | regressions {old[:4]}")
