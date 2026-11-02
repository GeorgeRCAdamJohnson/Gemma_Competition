"""Re-score saved gate diffs with the per-task-pinned replay engine (kb/kblib/replay.py).

gate_run.py's built-in verify() runs pytest in the shared interpreter without per-task pins, and
some rich tasks fail even with the gold patch there. This uses the same engine as gold_gate_all.py,
so a task counts only if the gold patch is locally valid for it.

python rescore_pinned.py --tag e4b_parity6
Writes runs\\<tag>.pinned.jsonl and prints a summary over locally-valid tasks.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GEMMA = HERE.parent
KB = GEMMA / "kb"
TASKS_JSONL = GEMMA / "comp_files" / "tasks.jsonl"
GOLDGATE = KB / "replays" / "goldgate_all.json"
DIFF_CAP = 8000  # gate_run stores row["diff"] = diff[:8000]

sys.path.insert(0, str(KB))
from kblib import replay as rp, gold  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    # NOTE: split on "\n" only. str.splitlines() also breaks on U+2028/U+2029, which can appear
    # inside JSON string values (model-emitted patches do), corrupting records mid-string.
    res_path = HERE / "runs" / f"{args.tag}.results.jsonl"
    rows = [json.loads(l) for l in res_path.read_text(encoding="utf-8").split("\n") if l.strip()]
    goldgate = json.loads(GOLDGATE.read_text(encoding="utf-8"))
    raw = {rec["instance_id"]: rec
           for l in TASKS_JSONL.read_text(encoding="utf-8", errors="replace").split("\n") if l.strip()
           for rec in (json.loads(l),)}

    rp.load_raw_tasks(TASKS_JSONL)
    tasks_gold = gold.build_tasks_gold(TASKS_JSONL)
    out_rows = []
    with rp.ReplayEngine(tasks_gold) as eng:
        for row in rows:
            tid = row["task"]
            gg = goldgate.get(tid, {})
            validity = gg.get("gold_first", "UNKNOWN")
            rec = raw[tid]
            out = {"task": tid, "gold_validity": validity, "patch_chars": row.get("patch_chars", 0),
                   "gate_resolved": row.get("resolved"), "end": row.get("end"),
                   "calls": row.get("calls")}
            diff = row.get("diff") or ""
            # Prefer the full sidecar patch; results.jsonl truncates at 8000 chars, which makes a
            # larger patch unscorable. Fall back to the stored diff for runs predating sidecars.
            sidecar = HERE / "runs" / f"{args.tag}.patches" / f"{tid}.patch"
            truncated_no_sidecar = False
            if sidecar.exists():
                diff = sidecar.read_text(encoding="utf-8")
            elif row.get("patch_chars", 0) > DIFF_CAP:
                truncated_no_sidecar = True
            if truncated_no_sidecar:
                out.update(pinned_resolved=None, pinned_result="DIFF_TRUNCATED_NO_SIDECAR")
            elif not diff.strip():
                out.update(pinned_resolved=False, pinned_result="EMPTY_PATCH")
            else:
                gold_pass = None
                if validity == "VALID-GOLD-RELATIVE":
                    gold_pass = eng.gold_first(rec["repo"], tid, rec["base_commit"],
                                               timeout_s=args.timeout).get("gold_pass_tests", [])
                r = eng.run_candidate(rec["repo"], tid, rec["base_commit"], kind="patch",
                                      patch_text=diff, timeout_s=args.timeout,
                                      gold_pass_tests=gold_pass)
                if "result" in r and r["result"] in ("INFRA", "APPLY_FAIL"):
                    out.update(pinned_resolved=None if r["result"] == "INFRA" else False,
                               pinned_result=r["result"], reason=r.get("reason"))
                else:
                    ok = r.get("gold_relative") if validity == "VALID-GOLD-RELATIVE" else r.get("harness_like")
                    out.update(pinned_resolved=bool(ok), pinned_result="PASS" if ok else "FAIL",
                               passed=r.get("passed"), failed=r.get("failed"), errors=r.get("errors"),
                               required_pass=r.get("required_pass"))
            out_rows.append(out)
            print(f"{tid:<10} valid={validity:<20} gate={str(out['gate_resolved']):<5} "
                  f"pinned={out['pinned_result']}", flush=True)

    (HERE / "runs" / f"{args.tag}.pinned.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in out_rows), encoding="utf-8")
    valid = [r for r in out_rows if r["gold_validity"] in ("VALID-HARNESS-LIKE", "VALID-GOLD-RELATIVE")]
    solved = sum(1 for r in valid if r["pinned_resolved"])
    unknown = sum(1 for r in valid if r["pinned_resolved"] is None)
    print(f"\n[{args.tag}] pinned resolved {solved}/{len(valid)} locally-valid tasks"
          f" (unknown/infra {unknown}; excluded invalid-gold {len(out_rows) - len(valid)})")


if __name__ == "__main__":
    main()
