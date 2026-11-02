"""Gold-first validity gate over ALL 129 public tasks (item 1 closure).

Runs the FIXED per-task-pinned engine (kb/kblib/replay.py rp-4) gold_first control
for every task in comp_files/tasks.jsonl and caches one verdict per task under
kb/replays/goldgate_all.json. Resumable: existing verdicts are skipped.

Usage:
  python gold_gate_all.py                 # all tasks not yet cached
  python gold_gate_all.py --all           # ignore cache, recompute everything
  python gold_gate_all.py --repo Textualize/rich
  python gold_gate_all.py --timeout 900
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEMMA = HERE.parent
KB = GEMMA / "kb"
TASKS_JSONL = GEMMA / "comp_files" / "tasks.jsonl"
OUT = KB / "replays" / "goldgate_all.json"

sys.path.insert(0, str(KB))
from kblib import replay as rp, gold  # noqa: E402

VALID = ("VALID-HARNESS-LIKE", "VALID-GOLD-RELATIVE")


def load_tasks():
    rows = []
    for line in TASKS_JSONL.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    tasks = load_tasks()
    if args.repo:
        tasks = [t for t in tasks if t["repo"] == args.repo]
    cache = {}
    if OUT.is_file() and not args.all:
        try:
            cache = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    rp.load_raw_tasks(TASKS_JSONL)
    tasks_gold = gold.build_tasks_gold(TASKS_JSONL)
    todo = [t for t in tasks if args.all or t["instance_id"] not in cache]
    print(f"tasks={len(tasks)} already_cached={len(cache)} todo={len(todo)}", flush=True)

    if todo:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with rp.ReplayEngine(tasks_gold) as eng:
            for i, rec in enumerate(todo, 1):
                tid = rec["instance_id"]
                t0 = time.time()
                try:
                    gr = eng.gold_first(rec["repo"], tid, rec["base_commit"],
                                        timeout_s=args.timeout)
                except Exception as e:  # noqa: BLE001
                    gr = {"gold_first": "INFRA",
                          "reason": f"{type(e).__name__}: {e}"}
                v = gr.get("gold_first")
                cache[tid] = {
                    "gold_first": v,
                    "reason": gr.get("reason", ""),
                    "result_criterion": gr.get("result_criterion"),
                    "pins": gr.get("pins", []),
                    "pin_provenance": gr.get("pin_provenance", "none"),
                    "pin_warnings": gr.get("pin_warnings", []),
                    "gold_pass_n": len(gr.get("gold_pass_tests", [])),
                    "repo": rec["repo"],
                    "included": v in VALID,
                    "secs": round(time.time() - t0, 1),
                }
                OUT.write_text(json.dumps(cache, indent=1, ensure_ascii=False),
                               encoding="utf-8")
                print(f"[{i}/{len(todo)}] {tid}: {v} "
                      f"({cache[tid]['reason'] or cache[tid]['result_criterion']}) "
                      f"{cache[tid]['secs']}s", flush=True)

    print("\n=== SUMMARY ===", flush=True)
    import collections
    by_repo = collections.Counter()
    tot_repo = collections.Counter()
    for rec in tasks:
        c = cache.get(rec["instance_id"], {})
        tot_repo[rec["repo"]] += 1
        if c.get("included"):
            by_repo[rec["repo"]] += 1
    for r in sorted(tot_repo):
        print(f"{r}: {by_repo[r]}/{tot_repo[r]} valid")
    bad = {k: v for k, v in cache.items() if not v.get("included")}
    print(f"TOTAL: {len(cache) - len(bad)}/{len(cache)} valid")
    if bad:
        print("\nNOT VALID:")
        for k in sorted(bad, key=lambda x: (bad[x]["repo"], x)):
            print(f"  {k} [{bad[k]['repo']}] {bad[k]['gold_first']}: "
                  f"{(bad[k]['reason'] or '')[:90]}")


if __name__ == "__main__":
    main()