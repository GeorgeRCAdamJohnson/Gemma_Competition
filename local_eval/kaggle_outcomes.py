"""Per-task outcomes from every Kaggle gate notebook log + null-mechanism tags.  CPU only.
python kaggle_outcomes.py            # table of all rows
python kaggle_outcomes.py --summary  # counts only
"""
import argparse, collections, json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROW = re.compile(r"(?:rich|fastapi)_\d+\s+(?:rich|fastapi)\s+(True|False)\s+([\d.]+)\s+(\d+)\s+(\d+)")
ROWID = re.compile(r"\b((?:rich|fastapi)_\d+)\s+(?:rich|fastapi)\s+(True|False)\s+([\d.]+)\s+(\d+)\s+(\d+)")
WARN = re.compile(r"Task ((?:rich|fastapi)_\d+):\s*([^\\\"]{0,160})")


def version_of(p):
    rel = p.relative_to(ROOT).parts
    if rel[0].startswith("submit_"):
        if len(rel) > 3 and rel[2] == "out":
            return f"{rel[0][7:]}/{rel[1]}"
        return rel[0][7:]
    return "/".join(rel[:-1]) or rel[0]


def parse_log(p):
    txt = p.read_text(encoding="utf-8", errors="replace")
    txt = txt.replace("\\n", "\n").replace('\\"', '"')
    rows = {}
    for m in ROWID.finditer(txt):
        rows[m.group(1)] = dict(task=m.group(1), resolved=m.group(2) == "True", dur=float(m.group(3)),
                               calls=int(m.group(4)), chars=int(m.group(5)))
    warns = collections.defaultdict(set)
    for m in WARN.finditer(txt):
        warns[m.group(1)].add(m.group(2).strip()[:90])
    for t, r in rows.items():
        r["warn"] = sorted(warns.get(t, []))
    return rows


def tag(r):
    w = " | ".join(r["warn"]).lower()
    if r["resolved"]:
        return "RESOLVED"
    if r["chars"] > 0:
        return "wrong-patch"
    if "tool call budget" in w:
        return "NULL:call-budget"
    if "timeout" in w or "timed out" in w or "wall" in w or "deadline" in w:
        return "NULL:time"
    return "NULL:other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    allrows = []
    for p in sorted(ROOT.glob("**/*.log")):
        if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
            continue
        if not p.name.startswith("gemma-sibling-conform") and "kernel" not in p.name:
            continue
        if a.only and a.only not in str(p):
            continue
        try:
            rows = parse_log(p)
        except Exception as e:
            print("skip", p, e)
            continue
        for t, r in rows.items():
            r["version"] = version_of(p)
            r["tag"] = tag(r)
            allrows.append(r)
    if not a.summary:
        print(f"{'version':26}{'task':13}{'res':>4}{'dur':>7}{'calls':>6}{'chars':>6}  tag / warnings")
        for r in allrows:
            print(f"{r['version'][:25]:26}{r['task']:13}{str(r['resolved'])[0]:>4}{r['dur']:>7.0f}{r['calls']:>6}{r['chars']:>6}  {r['tag']}  {'; '.join(r['warn'])[:80]}")
    by = collections.defaultdict(list)
    for r in allrows:
        by[r["version"]].append(r)
    print(f"\n{'version':26}{'n':>3}{'RES':>4}{'wrongP':>7}{'NULLbud':>8}{'NULLtime':>9}{'NULLoth':>8}{'meanCalls':>10}{'meanDur':>8}")
    for v, rs in by.items():
        c = collections.Counter(r["tag"] for r in rs)
        print(f"{v[:25]:26}{len(rs):>3}{c['RESOLVED']:>4}{c['wrong-patch']:>7}{c['NULL:call-budget']:>8}{c['NULL:time']:>9}{c['NULL:other']:>8}"
              f"{sum(r['calls'] for r in rs) / len(rs):>10.1f}{sum(r['dur'] for r in rs) / len(rs):>8.0f}")
    c = collections.Counter(r["tag"] for r in allrows)
    n = len(allrows)
    print(f"\nrows={n}  " + "  ".join(f"{k}={v}" for k, v in c.most_common()))
    json.dump(allrows, open(ROOT / "local_eval" / "runs" / "kaggle_outcomes.json", "w"), indent=1)


if __name__ == "__main__":
    main()
