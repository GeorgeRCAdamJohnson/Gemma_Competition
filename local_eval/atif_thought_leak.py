"""CPU-only: do real Kaggle traces show 'thought'-prefixed / very long thinking messages (content-channel runaway)?
python atif_thought_leak.py [--versions v6w,...] [--all]
"""
import argparse, collections, json, re, statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ap = argparse.ArgumentParser()
ap.add_argument("--versions", default="v6w")
ap.add_argument("--all", action="store_true")
ap.add_argument("--long", type=int, default=8000)
a = ap.parse_args()
want = set(a.versions.split(","))


def version_of(p):
    rel = p.relative_to(ROOT).parts
    if rel[0].startswith("submit_"):
        if len(rel) > 3 and rel[2] == "out":
            return f"{rel[0][7:]}/{rel[1]}"
        return rel[0][7:]
    return "/".join(rel[:-1]) or rel[0]


by_ver = collections.defaultdict(lambda: collections.Counter())
lens = collections.defaultdict(list)
flag = []
for p in sorted(ROOT.glob("**/trace_rich_*.json")):
    if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
        continue
    v = version_of(p)
    if not a.all and v.split("/")[0] not in want:
        continue
    try:
        t = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    task = re.search(r"trace_(rich_\d+)\.json", p.name).group(1)
    for i, s in enumerate(t.get("steps", [])):
        if s.get("source") != "agent":
            continue
        m = s.get("message") or ""
        et = (s.get("extra") or {}).get("event_type")
        has_tc = bool(s.get("tool_calls"))
        c = by_ver[v]
        c["agent_steps"] += 1
        c[f"ev:{et}"] += 1
        if m.lstrip().lower().startswith("thought"):
            c["starts_thought"] += 1
        lens[(v, et, has_tc)].append(len(m))
        if len(m) >= a.long:
            c["long"] += 1
            flag.append((v, task, i, et, has_tc, len(m), m[:90].replace("\n", " ")))

for v, c in sorted(by_ver.items()):
    print(v, dict(c))
print()
for k, L in sorted(lens.items(), key=lambda kv: str(kv[0])):
    L2 = sorted(L)
    print(f"{k[0]:16} ev={str(k[1]):10} tc={str(k[2])[0]} n={len(L):4} median={statistics.median(L):7.0f} p90={L2[int(len(L2)*.9)]:7d} max={L2[-1]:7d}")
print(f"\nmessages >= {a.long} chars: {len(flag)}")
for f in flag[:40]:
    print("  ", f)
