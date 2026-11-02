"""CPU-only: identical-call repetition in real Kaggle traces.  python atif_repeat_calls.py [--all]
For each run: longest streak of consecutive identical (tool,args) calls, and share of calls that repeat an earlier identical call."""
import collections, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALL = "--all" in sys.argv
WANT = {"v6w", "v6x", "v6y", "v6c", "v6t", "v6b", "v6v", "v6s"}


def version_of(p):
    rel = p.relative_to(ROOT).parts
    if rel[0].startswith("submit_"):
        if len(rel) > 3 and rel[2] == "out":
            return f"{rel[0][7:]}/{rel[1]}"
        return rel[0][7:]
    return "/".join(rel[:-1]) or rel[0]


rows = []
for p in sorted(ROOT.glob("**/trace_rich_*.json")):
    if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
        continue
    v = version_of(p)
    if not ALL and v.split("/")[0] not in WANT:
        continue
    t = json.loads(p.read_text(encoding="utf-8"))
    seq = []
    for s in t.get("steps", []):
        for tc in s.get("tool_calls") or []:
            fn = tc.get("function_name")
            if fn in ("get_status",):
                continue
            seq.append((fn, json.dumps(tc.get("arguments"), sort_keys=True)))
    if not seq:
        continue
    best = cur = 1
    for a, b in zip(seq, seq[1:]):
        cur = cur + 1 if a == b else 1
        best = max(best, cur)
    seen, rep = set(), 0
    for c in seq:
        if c in seen:
            rep += 1
        seen.add(c)
    rows.append((v, re.search(r"(rich_\d+)", p.name).group(1), len(seq), best, rep))

print(f"runs={len(rows)}")
print("longest identical consecutive streak distribution:", dict(sorted(collections.Counter(r[3] for r in rows).items())))
print("runs with repeated identical call anywhere (>=1 repeat):", sum(1 for r in rows if r[4] > 0), "of", len(rows))
tot = sum(r[2] for r in rows)
print(f"share of all calls that repeat an earlier identical call: {sum(r[4] for r in rows)}/{tot} = {100*sum(r[4] for r in rows)/tot:.1f}%")
print("runs with streak>=3:")
for r in sorted(rows, key=lambda r: -r[3]):
    if r[3] >= 3:
        print("  ", r)
