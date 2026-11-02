"""Classify why each task failed: environment/skew vs real assertion failure.

Free experiment (no model runs, no GPU, no submission quota): read the test_outputs
that our own 129-run already produced and separate failures the *sandbox* caused
from failures the *agent* caused.
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

ENV_PATTERNS = [
    ("collection_error", re.compile(r"ERROR collecting|Interrupted: \d+ error")),
    ("name_error", re.compile(r"NameError: name .* is not defined")),
    ("module_missing", re.compile(r"ModuleNotFoundError|No module named")),
    ("import_error", re.compile(r"ImportError")),
    ("pytest_usage", re.compile(r"error: unrecognized arguments|no tests ran|file or directory not found")),
    ("fixture_missing", re.compile(r"fixture '.*' not found")),
    ("wheel_install", re.compile(r"Could not find a version|No matching distribution|is not a valid editable")),
    ("syntax_pyver", re.compile(r"SyntaxError|TypeError: .*unexpected keyword argument")),
]
REAL_PATTERNS = [
    ("assertion", re.compile(r"AssertionError|^E\s+assert |FAILED .* - assert")),
    ("test_failure", re.compile(r"FAILED ")),
]


def classify(text):
    hits = [n for n, rx in ENV_PATTERNS if rx.search(text)]
    real = [n for n, rx in REAL_PATTERNS if rx.search(text)]
    if hits and not real:
        return "ENV", hits
    if real and not hits:
        return "REAL", real
    if real and hits:
        return "MIXED", hits + real
    return "UNKNOWN", []


def main(run_dir):
    res = os.path.join(run_dir, "results")
    tdir = os.path.join(res, "test_outputs")
    trdir = os.path.join(res, "traces")
    verdicts = {}
    vpath = os.path.join(res, "task_results.all.jsonl")
    if os.path.exists(vpath):
        for line in io.open(vpath, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            tid = row.get("instance_id") or row.get("task_id")
            verdicts[tid] = row

    rows = []
    for fn in sorted(os.listdir(tdir)):
        if not fn.endswith(".log"):
            continue
        tid = fn[:-4]
        text = io.open(os.path.join(tdir, fn), encoding="utf-8", errors="replace").read()
        kind, why = classify(text)
        v = verdicts.get(tid, {})
        rows.append({
            "task": tid,
            "repo": tid.rsplit("_", 1)[0],
            "class": kind,
            "signals": ",".join(why),
            "resolved": bool(v.get("resolved", v.get("passed", False))),
            "trace": os.path.exists(os.path.join(trdir, tid + ".json"))
            or os.path.exists(os.path.join(trdir, tid + ".jsonl")),
        })

    from collections import Counter, defaultdict
    print("run:", run_dir)
    print("task_results rows:", len(verdicts))
    print("test_outputs:", len(rows))
    print()
    print("=== failure classification (test_outputs) ===")
    for k, n in Counter(r["class"] for r in rows).most_common():
        print(f"  {k:<9} {n:>4}")
    print()
    print("=== ENV-classified failures by repo ===")
    byrepo = defaultdict(Counter)
    for r in rows:
        byrepo[r["repo"]][r["class"]] += 1
    for repo in sorted(byrepo):
        c = byrepo[repo]
        tot = sum(c.values())
        print(f"  {repo:<10} total={tot:<4} ENV={c['ENV']:<4} REAL={c['REAL']:<4} "
              f"MIXED={c['MIXED']:<4} UNKNOWN={c['UNKNOWN']}")
    print()
    print("=== signal frequency ===")
    sig = Counter()
    for r in rows:
        for s in r["signals"].split(","):
            if s:
                sig[s] += 1
    for k, n in sig.most_common():
        print(f"  {k:<18} {n:>4}")
    print()
    env = [r["task"] for r in rows if r["class"] == "ENV"]
    print(f"=== {len(env)} ENV-only failures (candidate false negatives) ===")
    for t in env:
        print("  ", t)
    out = os.path.join(HERE, "test_failure_classification.json")
    io.open(out, "w", encoding="utf-8").write(json.dumps(rows, indent=1))
    print()
    print("wrote", out)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "kaggle_pkg", "out_e4b"))
