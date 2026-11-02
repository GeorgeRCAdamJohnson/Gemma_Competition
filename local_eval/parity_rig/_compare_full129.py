"""Compare a full-129 result file against our references.
Usage: python _compare_full129.py <task_results.jsonl> [label]

References we hold per-task: m1_full129/ca5 (E4B ca5, 15/129) and ca5_v2 (10/129).
31B-v10 exists only as a COUNT (34/129, per-repo fastapi 18 / rich 15 / requests 1), no ids.
So: per-task delta is computable vs E4B; vs 31B-v10 only per-repo.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
BASE = RIG.parent.parent
TASKS = BASE / "comp_files" / "tasks.jsonl"
V10 = {"fastapi": 18, "rich": 15, "requests": 1, "httpx": 0}


def load(p):
    rows = []
    for l in open(p, encoding="utf-8"):
        if l.strip():
            rows.append(json.loads(l))
    return rows


def solved_set(rows):
    return {r["instance_id"] for r in rows if r.get("resolved")}


def repo_of(i):
    return i.split("_")[0]


def patch_shape(patch):
    files = set(re.findall(r"^\+\+\+ b/(.+)$", patch or "", re.M))
    adds = len([x for x in (patch or "").splitlines() if x.startswith("+") and not x.startswith("+++")])
    return len(files), adds


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    target = Path(sys.argv[1])
    label = sys.argv[2] if len(sys.argv) > 2 else target.parent.name
    trows = load(target)
    ts = solved_set(trows)

    refs = {}
    for name in ("ca5", "ca5_v2"):
        p = RIG / "m1_full129" / name / "task_results.jsonl"
        if p.exists():
            refs[name] = solved_set(load(p))
    union = set().union(*refs.values()) if refs else set()

    tasks = {}
    for l in open(TASKS, encoding="utf-8"):
        if l.strip():
            d = json.loads(l)
            tasks[d["instance_id"]] = d

    print("=" * 78)
    print(f"{label}: {len(ts)}/{len(trows)} = {len(ts)/max(len(trows),1):.3f}")
    print("references: " + ", ".join(f"{k} {len(v)}/129" for k, v in refs.items()))
    print(f"E4B-ca5 union of any config: {len(union)}/129   |   31B-v10 reference: 34/129")

    print("\nper-repo:")
    tr = Counter(repo_of(i) for i in ts)
    allr = Counter(repo_of(r["instance_id"]) for r in trows)
    print(f"  {'repo':<10} {'this':>10} {'E4B-union':>11} {'v10':>5}")
    for repo in sorted(allr):
        eu = len({i for i in union if repo_of(i) == repo})
        print(f"  {repo:<10} {tr.get(repo,0):>4}/{allr[repo]:<5} {eu:>6}/{allr[repo]:<4} {V10.get(repo,0):>5}")

    new = sorted(ts - union)
    lost = sorted(union - ts)
    print(f"\nNEWLY solved vs any E4B config ({len(new)}):")
    for i in new[:40]:
        f, a = patch_shape(tasks.get(i, {}).get("patch"))
        print(f"  {i:<18} gold files={f} +{a}")
    if lost:
        print(f"\nLOST vs E4B ({len(lost)}): {', '.join(lost[:20])}")

    # what separates the new wins?
    shp = [patch_shape(tasks.get(i, {}).get("patch")) for i in new]
    if shp:
        one = sum(1 for f, a in shp if f <= 1 and a <= 8)
        print(f"\nnew wins that are single-file <=8 added lines: {one}/{len(shp)}")
    print("\nverdict heuristics:")
    print(f"  vs E4B-union {len(union)}: {'+' if len(ts)>len(union) else ''}{len(ts)-len(union)}")
    print(f"  vs 31B-v10 34: {'+' if len(ts)>34 else ''}{len(ts)-34}")


if __name__ == "__main__":
    main()
