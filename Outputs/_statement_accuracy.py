"""How accurate/useful are the 129 problem statements, measured against the gold patch?
Per task:
  kind        PR description (template / "this PR" / checklist) vs issue-style
  noise       share of the statement that is PR-template boilerplate (checklists, type-of-change boxes)
  gold_named  does it name a gold source file (path, basename or dotted module)?
  gold_syms   share of gold-changed functions/classes (from @@ hunk headers + def/class on changed lines) it names
  distract    other repo source files it names that the gold patch does NOT touch
  top_word    is the statement's most repeated code-ish identifier a gold file's stem? (rich_2725: "box" -> box.py, gold table.py)
  fix_leak    does it describe the change itself (a +line of the gold patch appears, or "changed/fixed/reversed X")?
Joined with E4B solve rate (variance3: 5 full runs of 129 tasks, ca5 prompt).
"""
import json
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

T = [json.loads(l) for l in Path("Outputs/e4b_variance3/tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
solve = defaultdict(list)
for f in Path("Outputs/e4b_variance3/results").glob("run_*/shard*/task_results.jsonl"):
    for l in f.read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            solve[r["instance_id"]].append(bool(r["resolved"]))
BOILER = re.compile(r"(?im)^\s*(?:[-*]\s*\[[ xX]\].*|#+\s*(?:type of changes?|checklist|description|summary|related issues?)\s*$|"
                    r"<!--.*?-->|.*(?:pedantic in the code review|I've run the latest|CHANGELOG\.md and CONTRIBUTORS).*)$")
PR = re.compile(r"(?i)(## type of changes|checklist|this pr\b|pull request|i've added tests|\bfixes #\d+|closes #\d+)")
IDENT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b")
STOP = set("""the and for that this with not are but from have has was were when what which will would should could into
your you our their there then than also only some such more most other each very just like make made use used using does
did done can cannot about after before because been being both same here how its it's new old one two all any get set
true false none self return class def import python code file files line lines error errors issue bug fix fixed test tests
example output expected actual version versions value values type types function method methods call called work works
""".split())

rows = []
for t in T:
    tid, ps, patch = t["instance_id"], t["problem_statement"], t["patch"]
    files = [f for f in re.findall(r"^\+\+\+ b/(\S+)", patch, re.M)]
    src = [f for f in files if "test" not in f and f.endswith(".py")]
    if not src:
        continue
    stems = {Path(f).stem for f in src}
    mods = {f[:-3].replace("/", ".") for f in src}
    low = ps.lower()
    gold_named = any(f in ps or Path(f).name in ps or m in ps or re.search(rf"\b{re.escape(Path(f).stem)}\.py\b", ps)
                     for f, m in zip(src, sorted(mods)))
    # gold symbols: hunk-header function names + def/class names on changed lines, source files only
    syms = set()
    cur = None
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
        if cur in src:
            m = re.match(r"@@.*@@\s*(?:async\s+)?(?:def|class)\s+(\w+)", line)
            if m:
                syms.add(m.group(1))
            m = re.match(r"[+-]\s*(?:async\s+)?(?:def|class)\s+(\w+)", line)
            if m:
                syms.add(m.group(1))
    syms -= {"__init__", "__call__"}
    named_syms = {s for s in syms if re.search(rf"\b{re.escape(s)}\b", ps)}
    # other repo source files named in the statement
    mentioned = set(re.findall(r"\b([\w/]+\.py)\b", ps))
    distract = {m for m in mentioned if "test" not in m and not any(m.endswith(Path(f).name) for f in src)}
    words = Counter(w.lower() for w in IDENT.findall(re.sub(r"https?://\S+", " ", ps)) if w.lower() not in STOP)
    top = words.most_common(1)[0][0] if words else ""
    top_is_gold = top in stems
    # does the top word name some OTHER module of the package (a pull toward the wrong file)?
    plus = [l[1:].strip() for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++") and len(l.strip()) > 12]
    leak = any(p in ps for p in plus) or bool(re.search(r"(?i)\b(changed|reversed|replaced|renamed|moved|now (?:uses|returns|raises))\b", ps))
    boiler = sum(len(m.group(0)) for m in BOILER.finditer(ps))
    s = solve.get(tid, [])
    rows.append(dict(id=tid, repo=tid.split("_")[0], pr=bool(PR.search(ps)), noise=boiler / max(len(ps), 1), n=len(ps),
                     gold_named=gold_named, syms=len(syms), syms_named=len(named_syms),
                     sym_frac=len(named_syms) / len(syms) if syms else None, distract=len(distract), top=top,
                     top_is_gold=top_is_gold, leak=leak, rate=st.mean(s) if s else None, nsrc=len(src)))

print(f"{len(rows)} tasks with a gold source-file change")
pct = lambda xs: f"{st.mean(xs):.0%}"
print(f"  PR-description style            {pct([r['pr'] for r in rows])}")
print(f"  boilerplate share (mean)        {st.mean(r['noise'] for r in rows):.0%}   median length {st.median(r['n'] for r in rows):.0f} chars")
print(f"  names a gold source file        {pct([r['gold_named'] for r in rows])}")
fr = [r["sym_frac"] for r in rows if r["sym_frac"] is not None]
print(f"  names >= 1 gold symbol          {pct([r['syms_named'] > 0 for r in rows if r['syms']])} "
      f"(mean share of gold symbols named {st.mean(fr):.0%}, n {len(fr)})")
print(f"  names NEITHER file nor symbol   {pct([not r['gold_named'] and not r['syms_named'] for r in rows])}")
print(f"  names other (non-gold) src file {pct([r['distract'] > 0 for r in rows])}")
print(f"  top word = gold file stem       {pct([r['top_is_gold'] for r in rows])}")
print(f"  describes the fix (leak)        {pct([r['leak'] for r in rows])}")
print(f"  multi-file gold fix             {pct([r['nsrc'] > 1 for r in rows])}")

print("\nby repo: n | names gold file | names gold symbol | neither | E4B solve rate")
for repo in sorted({r["repo"] for r in rows}):
    q = [r for r in rows if r["repo"] == repo]
    rr = [r["rate"] for r in q if r["rate"] is not None]
    print(f"  {repo:9s} {len(q):3d} | {pct([r['gold_named'] for r in q]):>4s} | {pct([r['syms_named'] > 0 for r in q]):>4s} | "
          f"{pct([not r['gold_named'] and not r['syms_named'] for r in q]):>4s} | {st.mean(rr):.1%}")

print("\nE4B solve rate by what the statement gives (variance3, 5 runs each)")
for label, f in (("names gold file", lambda r: r["gold_named"]), ("names gold symbol only", lambda r: not r["gold_named"] and r["syms_named"] > 0),
                 ("names neither", lambda r: not r["gold_named"] and not r["syms_named"]),
                 ("names a distractor file", lambda r: r["distract"] > 0), ("multi-file fix", lambda r: r["nsrc"] > 1),
                 ("PR-style", lambda r: r["pr"]), ("issue-style", lambda r: not r["pr"])):
    q = [r["rate"] for r in rows if f(r) and r["rate"] is not None]
    print(f"  {label:26s} n {len(q):3d}  solve {st.mean(q) if q else 0:5.1%}  tasks ever solved {sum(x > 0 for x in q)}")

print("\nthe 6 wrong-file tasks:")
for r in rows:
    if r["id"] in ("rich_4077", "rich_3063", "fastapi_11194", "fastapi_9555", "rich_2725", "fastapi_9425"):
        print(f"  {r['id']:14s} pr {r['pr']!s:5s} gold file named {r['gold_named']!s:5s} gold syms {r['syms_named']}/{r['syms']} "
              f"distractors {r['distract']} top word '{r['top']}' (gold stem? {r['top_is_gold']}) noise {r['noise']:.0%}")
Path("Outputs/_statement_accuracy.json").write_text(json.dumps(rows, indent=1))
