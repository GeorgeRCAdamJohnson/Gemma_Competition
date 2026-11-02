"""Analyse the 129-task 31B A3 run: join results with repo + fix-shape buckets.

Input: the per-task result lines from the Kaggle kernel, either
  (a) pasted into a file as-is (the "-> resolved=..." lines), or
  (b) a JSONL/CSV with columns task,resolved,duration,tool_calls,patch_chars.

Usage:
    python analyse_129.py results.txt
    python analyse_129.py results.txt --shapes   # also slice by fix-shape bucket
"""
import argparse
import collections
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
GEMMA = os.path.dirname(HERE)
TASKS_JSONL = os.path.join(GEMMA, "comp_files", "tasks.jsonl")
SHAPES = os.path.join(HERE, "prompts", "_task_shapes.json")
ANNOTATED = os.path.join(HERE, "all129_annotated.tsv")

# "[12/129] requests_7502 (psf/requests)..."  and  "-> resolved=False duration=328.0s ..."
RE_TASK = re.compile(r"\[\d+/129\]\s+(\S+)\s+\(([^)]+)\)")
RE_RES = re.compile(r"->\s+resolved=(True|False)\s+duration=([\d.]+)s\s+tool_calls=(\d+)\s+patch_chars=(\d+)")


def parse(text):
    """Return list of dicts: task, repo, resolved, duration, calls, patch.

    Handles two formats: plain text, and Kaggle's JSONL stream log where each
    stdout line is a JSON object with the text in "data" (with \\u003e etc.).
    """
    # Decode JSONL stream records first if present
    decoded = []
    for ln in text.splitlines():
        s = ln.strip().lstrip(",")
        if s.startswith('{"stream_name"'):
            try:
                decoded.append(json.loads(s).get("data", ""))
                continue
            except Exception:
                pass
        decoded.append(ln)
    text = "\n".join(decoded)

    rows = []
    cur = None
    for ln in text.splitlines():
        m = RE_TASK.search(ln)
        if m:
            cur = {"task": m.group(1), "repo": m.group(2)}
            continue
        m = RE_RES.search(ln)
        if m and cur:
            cur.update(resolved=(m.group(1) == "True"), duration=float(m.group(2)),
                       calls=int(m.group(3)), patch=int(m.group(4)))
            rows.append(cur)
            cur = None
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results", help="file with the kernel's per-task output")
    ap.add_argument("--shapes", action="store_true", help="also slice by fix-shape bucket")
    args = ap.parse_args()

    text = open(args.results, encoding="utf-8", errors="replace").read()
    rows = parse(text)
    if not rows:
        print("no result lines found -- paste the raw kernel output")
        return 1

    shapes = json.load(open(SHAPES, encoding="utf-8")) if os.path.exists(SHAPES) else {}
    n = len(rows)
    solved = sum(1 for r in rows if r["resolved"])
    print("=" * 74)
    print("31B A3 on %d tasks: %d solved = %.3f  (0.18 leaderboard ~= 23/129)" % (n, solved, solved / n))
    print("=" * 74)

    # by repo
    print("\n--- by repo ---")
    by_repo = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        by_repo[r["repo"]][1] += 1
        by_repo[r["repo"]][0] += int(r["resolved"])
    for repo, (k, m) in sorted(by_repo.items(), key=lambda kv: -kv[1][1]):
        print("  %-24s %2d/%3d = %5.1f%%" % (repo, k, m, 100.0 * k / m))

    # failure modes
    print("\n--- how the misses ended ---")
    zero = sum(1 for r in rows if not r["resolved"] and r["patch"] == 0)
    wall = sum(1 for r in rows if not r["resolved"] and r["calls"] >= 28)
    wrong = sum(1 for r in rows if not r["resolved"] and r["patch"] > 0 and r["calls"] < 28)
    print("  landed a patch but tests failed : %d" % wrong)
    print("  burned all 28 calls             : %d" % wall)
    print("  submitted nothing (0 chars)     : %d" % zero)

    # durations
    durs = sorted(r["duration"] for r in rows)
    print("\n  duration: median %.0fs  mean %.0fs  p90 %.0fs  max %.0fs" % (
        durs[len(durs) // 2], sum(durs) / len(durs), durs[int(0.9 * len(durs))], durs[-1]))
    print("  total wall: %.1f h" % (sum(durs) / 3600))

    if args.shapes and shapes:
        print("\n--- by fix-shape bucket ---")
        by_shape = collections.defaultdict(lambda: [0, 0])
        for r in rows:
            s = shapes.get(r["task"], "?")
            by_shape[s][1] += 1
            by_shape[s][0] += int(r["resolved"])
        for s, (k, m) in sorted(by_shape.items(), key=lambda kv: (-kv[1][1], kv[0])):
            print("  %-28s %2d/%3d = %5.1f%%" % (s, k, m, 100.0 * k / m))

    # the misses worth knowing: solved tasks list
    print("\n--- solved tasks ---")
    print("  " + ", ".join(r["task"] for r in rows if r["resolved"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
