"""Re-score every run of the e4b_arms_1024 sweep with the pinned replay engine.

WHY: gate_run's built-in verify() runs pytest in the shared interpreter without per-task
pins, and it has SILENT FALSE POSITIVES -- on rich_3777 it failed to apply the test patch,
passed 91 unrelated tests, and reported resolved=True. It also threw RuntimeError on ~83%
of this sweep's runs, so its resolve flags are unusable. rescore_pinned.py uses the same
engine as gold_gate_all.py, so a task counts only if the gold patch is locally valid for it.

rescore_pinned.py takes ONE --tag, so this drives it once per run and aggregates.

Usage:
    python rescore_sweep.py                 # all runs
    python rescore_sweep.py --limit 6       # smoke test
    python rescore_sweep.py --task rich_2725
"""
import argparse
import collections
import glob
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUNS = os.path.join(HERE, "runs")
SWEEP = "e4b_arms_1024"
ARMS = ["A3", "D2", "A19"]
TASKS = ["rich_2725", "rich_2943"]


def run_rescore(tag, timeout=600):
    """Run rescore_pinned.py for one tag. Returns (returncode, stdout, stderr)."""
    cmd = [sys.executable, "rescore_pinned.py", "--tag", tag, "--timeout", str(timeout)]
    p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, p.stdout, p.stderr


def parse_summary(out):
    """Pull the 'pinned resolved X/Y locally-valid tasks' line out of the output."""
    for ln in out.splitlines():
        if "pinned resolved" in ln:
            return ln.strip()
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--task", default=None)
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    tags = []
    for arm in ARMS:
        for task in TASKS:
            pat = os.path.join(RUNS, "%s_%s_r*_%s.results.jsonl" % (SWEEP, arm, task))
            for p in sorted(glob.glob(pat)):
                base = os.path.basename(p)[: -len(".results.jsonl")]
                if args.task and not base.endswith(args.task):
                    continue
                tags.append(base)
    if args.limit:
        tags = tags[: args.limit]

    print("re-scoring %d runs with the pinned engine" % len(tags))
    print("(each run replays the tests; this is the slow part)\n")

    results = collections.defaultdict(list)
    failures = []
    for i, tag in enumerate(tags, 1):
        rc, out, err = run_rescore(tag, args.timeout)
        # tag = <sweep>_<ARM>_r<N>_<task>; the task itself contains underscores
        # (rich_2725), so split from the RIGHT: task is the last two segments.
        parts = tag[len(SWEEP) + 1:].split("_")
        arm = parts[0]
        task = "_".join(parts[-2:])
        summary = parse_summary(out)
        if rc != 0 or summary is None:
            failures.append((tag, rc, (err or out).strip()[-200:]))
            print("  [%3d/%d] %-46s FAILED rc=%d" % (i, len(tags), tag, rc))
            continue
        # "pinned resolved 1/2 locally-valid tasks"
        try:
            frac = summary.split("pinned resolved")[1].split("locally-valid")[0].strip()
            num, den = frac.split("/")
            num, den = int(num), int(den)
        except Exception:
            failures.append((tag, rc, "could not parse: %r" % summary))
            continue
        results[(arm, task)].append((num, den))
        print("  [%3d/%d] %-46s %s" % (i, len(tags), tag, summary))

    print("\n" + "=" * 74)
    print("PINNED RESOLVE RATE (gold-valid tasks only)")
    print("=" * 74)
    for task in TASKS:
        print("\n%s" % task)
        for arm in ARMS:
            v = results.get((arm, task), [])
            if not v:
                print("  %-4s no scored runs" % arm)
                continue
            num = sum(x[0] for x in v)
            den = sum(x[1] for x in v)
            print("  %-4s %d/%d gold-valid task-instances resolved  (%.1f%%)  [n=%d runs]"
                  % (arm, num, den, 100.0 * num / den if den else 0, len(v)))

    print("\n--- pooled over both tasks ---")
    for arm in ARMS:
        v = results.get((arm, "rich_2725"), []) + results.get((arm, "rich_2943"), [])
        if not v:
            print("  %-4s no scored runs" % arm)
            continue
        num = sum(x[0] for x in v)
        den = sum(x[1] for x in v)
        print("  %-4s %d/%d  (%.1f%%)  [n=%d runs]"
              % (arm, num, den, 100.0 * num / den if den else 0, len(v)))

    if failures:
        print("\n--- %d runs could not be scored ---" % len(failures))
        for tag, rc, msg in failures[:10]:
            print("  %-46s rc=%d %s" % (tag, rc, msg.replace("\n", " ")[:120]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
