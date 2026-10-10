"""
RICH gold-verify probe (CPU-only, no model).

Purpose: for each of the 4 rich sample tasks, apply the GOLD patch to a clean checkout and run the
task's gold test_patch. This CONFIRMS (a) our harness apply+test path is sound, (b) exactly which test
each rich task checks, and (c) the gold fix file (the localization target). This is the ground-truth
measurement the rich attack is built on — it needs no LLM.

For each task prints: gold patch applies? gold test PASSES? (it MUST, by definition) + the fix file(s)
and the test file(s). If a gold patch does NOT pass here, our harness/verify is broken and no agent
result from it can be trusted — that is itself the most important thing to learn.

Usage: python _gold_verify_rich.py
"""
import json, re, sys
from pathlib import Path
import run_local as R

RICH = ["rich_4077", "rich_4079", "rich_4076", "rich_3469"]
TASKS = Path(__file__).parent.parent / "comp_files" / "tasks.jsonl"


def load(tid):
    for l in open(TASKS, encoding="utf-8"):
        t = json.loads(l)
        if t["instance_id"] == tid:
            return t
    raise SystemExit(f"task {tid} not found")


def files_in_patch(patch):
    return re.findall(r'\+\+\+ b/(\S+)', patch or "")


def main():
    R.set_repo("rich")
    results = []
    for tid in RICH:
        t = load(tid)
        gold = t.get("patch") or ""
        fix_files = files_in_patch(gold)
        test_files = [f for f in files_in_patch(t.get("test_patch") or "") if f.endswith(".py")]
        print("\n" + "=" * 72)
        print(f"=== {tid}  base={t['base_commit'][:12]} ===")
        print(f"problem: {(t.get('problem_statement') or '')[:120].strip()!r}")
        print(f"GOLD fix file(s):  {fix_files}")
        print(f"GOLD test file(s): {test_files}")
        try:
            passed, log = R.verify(t, gold)
        except Exception as e:
            passed, log = False, f"verify EXCEPTION: {type(e).__name__}: {e}"
        verdict = "PASS (gold confirmed)" if passed else "FAIL (harness/verify problem!)"
        print(f"GOLD VERIFY: {verdict}")
        if not passed:
            print("---- verify log tail ----")
            print((log or "")[-1500:])
        results.append((tid, fix_files, test_files, passed))

    print("\n" + "=" * 72)
    print("SUMMARY (gold patches must all PASS; any FAIL = harness bug, not model):")
    for tid, fix, test, ok in results:
        print(f"  {tid:12s} gold={'PASS' if ok else 'FAIL':4s}  fix={fix}  test={test}")


if __name__ == "__main__":
    main()
