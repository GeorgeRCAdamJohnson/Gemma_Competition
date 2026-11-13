"""Does the problem statement contain the CONTRACT the hidden test checks? From each task's test_patch, take the string
literals on ADDED lines (len >= 4, not paths/imports): expected messages, outputs, names. Share that appear verbatim in the
statement = how much of the exact expected behaviour the model is actually told. Joined with E4B solve rate."""
import json
import re
import statistics as st
from pathlib import Path

rows = {r["id"]: r for r in json.loads(Path("Outputs/_statement_accuracy.json").read_text())}
LIT = re.compile(r"""(?:'([^'\n]{4,120})'|"([^"\n]{4,120})")""")
out = []
for l in Path("Outputs/e4b_variance3/tasks.jsonl").read_text(encoding="utf-8").splitlines():
    if not l.strip():
        continue
    t = json.loads(l)
    if t["instance_id"] not in rows:
        continue
    lits = set()
    for line in t["test_patch"].splitlines():
        if line.startswith("+") and not line.startswith("+++") and not re.match(r"\+\s*(from|import)\s", line):
            for a, b in LIT.findall(line):
                s = (a or b).strip()
                if s and not re.fullmatch(r"[\w./-]+\.(py|txt|json)|test_\w+|\W+", s):
                    lits.add(s)
    ps = t["problem_statement"]
    hit = {s for s in lits if s in ps}
    r = rows[t["instance_id"]]
    out.append(dict(id=t["instance_id"], n=len(lits), hit=len(hit), frac=len(hit) / len(lits) if lits else None,
                    rate=r["rate"], pr=r["pr"]))
q = [o for o in out if o["n"]]
print(f"{len(q)} tasks whose hidden test adds string literals (median {st.median(o['n'] for o in q):.0f} literals)")
print(f"  statement contains >= 1 of them: {st.mean(o['hit'] > 0 for o in q):.0%} | mean share contained "
      f"{st.mean(o['frac'] for o in q):.0%} | contains none: {st.mean(o['hit'] == 0 for o in q):.0%}")
for label, f in (("contains >= 25% of test literals", lambda o: o["frac"] >= 0.25), ("contains some (<25%)", lambda o: 0 < o["frac"] < 0.25),
                 ("contains none", lambda o: o["frac"] == 0)):
    z = [o["rate"] for o in q if f(o) and o["rate"] is not None]
    print(f"  {label:34s} n {len(z):3d}  E4B solve {st.mean(z) if z else 0:5.1%}  ever solved {sum(x > 0 for x in z)}")
for pr in (True, False):
    z = [o["frac"] for o in q if o["pr"] == pr]
    print(f"  {'PR-style' if pr else 'issue-style':12s} mean share of test literals in statement {st.mean(z):.0%} (n {len(z)})")
