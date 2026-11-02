"""For every ENV-classified failure: did the agent edit the gold file, and how close?

An ENV failure means the test never really ran.  If the agent's patch touched the
same file as the gold patch, that failure is a *candidate false negative* -- we
cannot say it solved, but we also cannot say it failed for a content reason.
"""
import io
import json
import os
import re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RUN = os.path.join(ROOT, "kaggle_pkg", "out_e4b")


def parse_patch(text):
    """-> {path: [(start, added_lines)]}"""
    files = {}
    cur = None
    start = None
    added = []
    for line in text.splitlines():
        m = re.match(r"^\+\+\+ b/(.+)$", line)
        if m:
            cur = m.group(1).strip()
            files.setdefault(cur, [])
            added = []
            continue
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)", line)
        if m:
            start = int(m.group(1))
            continue
        if cur and line.startswith("+") and not line.startswith("+++"):
            added.append(line[1:])
        elif cur and line.startswith("@@"):
            if start is not None and added:
                files[cur].append((start, added))
            added = []
    if cur and start is not None and added:
        files[cur].append((start, added))
    return files


def main():
    tasks = {}
    for line in io.open(os.path.join(RUN, "tasks.jsonl"), encoding="utf-8"):
        line = line.strip()
        if line:
            r = json.loads(line)
            tasks[r["instance_id"]] = r

    cls = {r["task"]: r for r in json.load(
        io.open(os.path.join(HERE, "test_failure_classification.json"), encoding="utf-8"))}
    pdir = os.path.join(RUN, "results", "patches")

    buckets = Counter()
    detail = []
    for tid, c in sorted(cls.items()):
        gold = parse_patch(tasks.get(tid, {}).get("patch", ""))
        agent_path = os.path.join(pdir, tid + ".patch")
        agent = {}
        if os.path.exists(agent_path):
            agent = parse_patch(io.open(agent_path, encoding="utf-8", errors="replace").read())
        gold_files = set(gold)
        agent_files = set(agent)
        if not agent_files:
            bucket = "no_patch"
        elif agent_files & gold_files:
            # min distance between any agent hunk start and any gold hunk start
            dist = min(
                abs(a[0] - g[0])
                for f in agent_files & gold_files
                for a in agent[f]
                for g in gold[f]
            ) if any(agent[f] and gold[f] for f in agent_files & gold_files) else 10**6
            bucket = "gold_file_near" if dist <= 100 else "gold_file_far"
        else:
            bucket = "wrong_file"
        buckets[(c["class"], bucket)] += 1
        detail.append({"task": tid, "class": c["class"], "signals": c["signals"],
                       "position": bucket})

    print(f"{'class':<9} {'no_patch':>9} {'wrong_file':>11} {'gold_far':>9} {'gold_near':>10} {'total':>7}")
    for k in ("ENV", "REAL", "MIXED", "UNKNOWN"):
        row = [buckets[(k, b)] for b in ("no_patch", "wrong_file", "gold_file_far", "gold_file_near")]
        print(f"{k:<9} {row[0]:>9} {row[1]:>11} {row[2]:>9} {row[3]:>10} {sum(row):>7}")

    cand = [d for d in detail if d["class"] == "ENV" and d["position"] in
            ("gold_file_near", "gold_file_far")]
    print()
    print(f"=== {len(cand)} ENV failures where the agent DID edit the gold file ===")
    for d in sorted(cand, key=lambda x: (x["position"], x["task"])):
        print(f"  {d['task']:<18} {d['position']:<14} {d['signals']}")
    io.open(os.path.join(HERE, "env_false_negative_candidates.json"), "w",
            encoding="utf-8").write(json.dumps(detail, indent=1))


if __name__ == "__main__":
    main()
