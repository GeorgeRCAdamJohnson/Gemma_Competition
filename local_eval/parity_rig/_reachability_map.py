"""REACHABILITY MAP for the never-solved tasks.
Cross-references every local result bank (what ANY config ever solved) with the gold
patch shape, so we can separate 'one insight away' from 'structurally out of reach'.
Pure analysis: no GPU, reads tasks.jsonl + result banks only."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
BASE = RIG.parent.parent
TASKS = BASE / "comp_files" / "tasks.jsonl"

BANK_DIRS = [RIG.parent]  # scan ALL of local_eval for task_results.jsonl


def load_tasks():
    out = {}
    for line in open(TASKS, encoding="utf-8"):
        if line.strip():
            d = json.loads(line)
            out[d["instance_id"]] = d
    return out


def ever_solved():
    """instance_id -> (max solved reps, total runs) across every bank"""
    agg = {}
    for root in BANK_DIRS:
        if not root.exists():
            continue
        for f in root.rglob("task_results.jsonl"):
            try:
                for line in open(f, encoding="utf-8"):
                    if not line.strip():
                        continue
                    r = json.loads(line)
                    iid = r.get("instance_id")
                    if not iid:
                        continue
                    a = agg.setdefault(iid, [0, 0])
                    a[1] += 1
                    a[0] += int(bool(r.get("resolved")))
            except Exception:
                continue
    return agg


def patch_shape(patch):
    if not patch:
        return dict(files=0, adds=0, dels=0, chars=0)
    files = set(re.findall(r"^\+\+\+ b/(.+)$", patch, re.M))
    adds = len([l for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")])
    dels = len([l for l in patch.splitlines() if l.startswith("-") and not l.startswith("---")])
    return dict(files=len(files), adds=adds, dels=dels, chars=len(patch))


def kind(patch):
    """crude fix taxonomy from the diff itself"""
    if not patch:
        return "none"
    adds = [l[1:] for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")]
    dels = [l[1:] for l in patch.splitlines() if l.startswith("-") and not l.startswith("---")]
    text = "\n".join(adds)
    new_defs = len(re.findall(r"^\s*(?:async )?def \w+", text, re.M))
    new_class = len(re.findall(r"^\s*class \w+", text, re.M))
    new_files = len(re.findall(r"^\+\+\+ b/", patch, re.M))
    if new_class:
        return "new-class"
    if new_defs and not dels:
        return "add-method/feature"
    if new_defs and dels:
        return "add+modify"
    if new_files > 1:
        return "multi-file"
    return "modify-existing"


def main():
    tasks = load_tasks()
    agg = ever_solved()
    never = [t for t in tasks if agg.get(t, [0, 0])[0] == 0]
    ever = [t for t in tasks if agg.get(t, [0, 0])[0] > 0]

    print(f"tasks in pool: {len(tasks)}   ever solved by ANY config: {len(ever)}   never: {len(never)}")
    print(f"total runs seen across banks: {sum(a[1] for a in agg.values())}")

    rows = []
    for t in never:
        d = tasks[t]
        sh = patch_shape(d.get("patch") or "")
        rows.append((t, kind(d.get("patch") or ""), sh))

    print("\n=== NEVER-SOLVED: fix taxonomy ===")
    for k, n in Counter(k for _, k, _ in rows).most_common():
        print(f"  {k:<20} {n:>3}")

    print("\n=== NEVER-SOLVED: gold size distribution (added lines) ===")
    buckets = Counter()
    for _, _, sh in rows:
        a = sh["adds"]
        b = "1-3" if a <= 3 else "4-8" if a <= 8 else "9-20" if a <= 20 else "21-50" if a <= 50 else "50+"
        buckets[b] += 1
    for b in ("1-3", "4-8", "9-20", "21-50", "50+"):
        print(f"  {b:>6} added lines: {buckets[b]:>3}")

    # REACHABLE = small, single-file, modifies existing code
    reach = [(t, k, sh) for t, k, sh in rows
             if sh["files"] <= 1 and sh["adds"] <= 8 and k in ("modify-existing", "add+modify")]
    print(f"\n=== REACHABLE CLASS (single file, <=8 added lines, modifies existing): {len(reach)} ===")
    for t, k, sh in sorted(reach, key=lambda x: x[2]["adds"]):
        print(f"  {t:<18} {k:<16} files={sh['files']} +{sh['adds']}/-{sh['dels']}")

    # what did the ever-solved set look like, for contrast?
    ev = Counter()
    for t in ever:
        ev[kind(tasks[t].get("patch") or "")] += 1
    print("\n=== EVER-SOLVED taxonomy (contrast) ===")
    for k, n in ev.most_common():
        print(f"  {k:<20} {n:>3}")


if __name__ == "__main__":
    main()
