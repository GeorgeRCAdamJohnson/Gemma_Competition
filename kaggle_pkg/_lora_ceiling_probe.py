"""DATA-CEILING PROBE for the content-correctness LoRA (free, laptop, no GPU).

Question (pre-registered): of the rich tasks the 31B FAILS on CONTENT (reached the right file, submitted a
non-empty patch, tests still failed), how many have a gold fix whose content is plausibly LEARNABLE from a
sibling/pattern an adapter could generalize, vs idiosyncratic one-offs?

Kill bar: if the learnable-content ceiling is <= ~3 rich tasks, no small adapter is worth a Colab train;
the LoRA path closes. If >= ~10, there is a real target and the recipe-fix work is justified.

Signal = the GOLD patch shape (model-free, from tasks.jsonl):
- LEARNABLE_PATTERN: small fix (<= 6 added non-trivial lines, 1 file, 1-2 hunks) that is a recognizable
  shape: add a method/guard/return, delegate to self.<attr>, change a constant/operator, mirror an existing
  branch. These are what a pattern-LoRA could in principle generalize.
- IDIOSYNCRATIC: multi-hunk / multi-file / large, or a one-off semantic change with no repeating shape.
Judged on the gold diff; the point is the CEILING (does the signal exist), not that the model will learn it.

Inputs: Outputs/ca5_31b_ab/ab31.json (31B control arm = plain ca5), kaggle_pkg/taskdefs/tasks.jsonl (gold).
"""
import json
import re
from pathlib import Path
from collections import Counter

K = Path(__file__).resolve().parent
ab = json.loads((K.parent / "Outputs" / "ca5_31b_ab" / "ab31.json").read_text(encoding="utf-8"))
rows = ab["rows"]
gold = {}
for l in (K / "taskdefs" / "tasks.jsonl").read_text(encoding="utf-8").splitlines():
    if l.strip():
        t = json.loads(l)
        gold[t["instance_id"]] = t.get("patch") or ""

# control arm (A), rich only. A task "content-fails" if in NO control run was it resolved, but it DID
# submit a non-empty patch in at least one control run (reached a fix, got it wrong).
A = [r for r in rows if r["arm"] == "A_control" and r["id"].startswith("rich_")]
byid = {}
for r in A:
    d = byid.setdefault(r["id"], {"resolved": False, "max_patch": 0, "runs": 0})
    d["resolved"] |= bool(r["resolved"])
    d["max_patch"] = max(d["max_patch"], r.get("patch") or 0)
    d["runs"] += 1

content_fail = [t for t, d in byid.items() if not d["resolved"] and d["max_patch"] > 0]
no_patch = [t for t, d in byid.items() if not d["resolved"] and d["max_patch"] == 0]
solved = [t for t, d in byid.items() if d["resolved"]]
print(f"rich control: {len(byid)} tasks | solved {len(solved)} | content-fail (patch but wrong) {len(content_fail)} | no-patch {len(no_patch)}")


def gold_shape(patch):
    """Classify the gold diff. Returns (label, added_nontrivial, files, hunks)."""
    if not patch:
        return ("NO_GOLD", 0, 0, 0)
    files = len(re.findall(r"^\+\+\+ ", patch, re.M))
    hunks = len(re.findall(r"^@@ ", patch, re.M))
    added = [l[1:] for l in patch.splitlines() if l.startswith("+") and not l.startswith("+++")]
    def trivial(s):
        s = s.strip()
        return (not s or s.startswith("#") or s in ("", "pass") or s.startswith(("import ", "from ", '"""', "'''"))
                or re.fullmatch(r"[)\]}:,]+", s) is not None)
    nontriv = [l for l in added if not trivial(l)]
    n = len(nontriv)
    small = n <= 6 and files <= 1 and hunks <= 2
    text = "\n".join(nontriv)
    patternish = bool(re.search(
        r"return self\.|def \w+\(self|self\.\w+ =|if .+:|raise \w+|return |isinstance\(|\.append\(|"
        r"== |!= | and | or |getattr\(|\.get\(", text))
    if files > 1 or hunks > 2 or n > 10:
        return ("IDIOSYNCRATIC_LARGE", n, files, hunks)
    if small and patternish:
        return ("LEARNABLE_PATTERN", n, files, hunks)
    if n <= 10 and patternish:
        return ("MAYBE_PATTERN", n, files, hunks)
    return ("IDIOSYNCRATIC_OTHER", n, files, hunks)


labels = Counter()
learnable, maybe = [], []
print("\n--- rich content-failures (31B submitted a patch, tests failed), judged on gold shape ---")
for t in sorted(content_fail):
    lab, n, f, h = gold_shape(gold.get(t, ""))
    labels[lab] += 1
    mark = {"LEARNABLE_PATTERN": "LEARN", "MAYBE_PATTERN": "maybe", "IDIOSYNCRATIC_LARGE": "big  ", "IDIOSYNCRATIC_OTHER": "idio "}.get(lab, lab)
    print(f"  [{mark}] {t:14} added={n} files={f} hunks={h}")
    if lab == "LEARNABLE_PATTERN": learnable.append(t)
    if lab == "MAYBE_PATTERN": maybe.append(t)

print("\n=== CEILING ===")
print("label counts:", dict(labels))
print(f"LEARNABLE_PATTERN rich content-fails: {len(learnable)}  -> {learnable}")
print(f"+ MAYBE_PATTERN (optimistic):         {len(learnable)+len(maybe)}  (maybe: {maybe})")
print("\nKILL BAR: <=3 learnable => LoRA path CLOSES. >=10 => a real target exists.")
ceil = len(learnable)
opt = len(learnable) + len(maybe)
print(f"VERDICT: strict ceiling {ceil}, optimistic {opt} ->",
      "CLOSE LoRA" if opt <= 3 else ("REAL TARGET" if ceil >= 10 else "MARGINAL (strict<=%d, opt=%d): small, risky" % (ceil, opt)))
