"""Breakthrough analysis 1b: were the edits E4B FAILED to apply (old_string not found) the right fix?
Proxy: overlap between the lines the edit meant to ADD (new_string lines not in old_string) and the gold patch's '+'
lines (stripped, non-trivial). Compared with the same overlap for edits that DID apply, split by attempt outcome.
If failed edits carry gold-like content about as often as applied edits in solved attempts, the model had the fix and
the editing mechanism lost it. Writes nothing; prints."""
import json
import re
import sqlite3
from collections import defaultdict

db = sqlite3.connect("kb/attempts.sqlite")
gold_add = {}
for task, patch in db.execute("SELECT task, gold_patch FROM tasks"):
    lines, cur = set(), None
    for l in patch.splitlines():
        if l.startswith("+++ b/"):
            cur = l[6:]
        elif l.startswith("+") and not l.startswith("+++") and cur and "test" not in cur:
            s = l[1:].strip()
            if len(s) >= 6 and not re.fullmatch(r"[\W_]+|(pass|return|else:|try:|\)|\]|\}|\"\"\")", s):
                lines.add(s)
    gold_add[task] = lines


def added(a):
    old = a.get("old_string") if isinstance(a.get("old_string"), str) else ""
    new = a.get("new_string") if isinstance(a.get("new_string"), str) else ""
    o = {l.strip() for l in old.splitlines()}
    return {l.strip() for l in new.splitlines() if l.strip() and l.strip() not in o and len(l.strip()) >= 6}


stats = defaultdict(lambda: [0, 0, 0])  # group -> [edits with added lines, edits hitting >=1 gold line, gold lines hit]
att_gold_failed = defaultdict(bool)
att_gold_applied = defaultdict(bool)
for aid, task, res, args, eok, err in db.execute("""
    SELECT a.id, a.task, a.resolved, c.args_json, c.edit_ok, c.error_message
    FROM tool_calls c JOIN traces t ON t.trace_id = c.trace_id JOIN attempts_unique a ON a.id = t.attempt_id
    WHERE c.tool = 'edit_file' AND a.model NOT LIKE '%31b%' AND a.resolved IS NOT NULL"""):
    g = gold_add.get(task)
    if not g:
        continue
    try:
        add = added(json.loads(args))
    except Exception:
        continue
    if not add:
        continue
    hit = len(add & g)
    kind = "applied" if eok else ("anchor_not_found" if err and "old_string not found" in err else "other_fail")
    key = f"{kind:17s} | attempt {'SOLVED' if res else 'failed'}"
    s = stats[key]
    s[0] += 1
    s[1] += hit > 0
    s[2] += hit
    if hit and kind == "anchor_not_found":
        att_gold_failed[aid] = True
    if hit and kind == "applied":
        att_gold_applied[aid] = True
print("edit kind         | outcome          edits  share adding >=1 exact gold line")
for k in sorted(stats):
    n, h, _ = stats[k]
    print(f"  {k}   {n:6d}   {h / n:6.1%}")
lost = [a for a in att_gold_failed if not att_gold_applied[a]]
res = dict(db.execute(f"SELECT id, resolved FROM attempts WHERE id IN ({','.join(map(str, lost)) or 0})"))
print(f"\nattempts where a FAILED anchor edit carried >= 1 exact gold line and NO applied edit ever did: {len(lost)} "
      f"(solved anyway: {sum(res.values())})")
tasks = defaultdict(int)
for a in lost:
    tasks[db.execute("SELECT task FROM attempts WHERE id = ?", (a,)).fetchone()[0]] += 1
print("  by task:", sorted(tasks.items(), key=lambda kv: -kv[1])[:15])
n_failed_att = db.execute("""SELECT COUNT(*) FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id
    WHERE a.model NOT LIKE '%31b%' AND a.resolved = 0""").fetchone()[0]
print(f"  = {len(lost) - sum(res.values())} of {n_failed_att} failed traced E4B attempts ({(len(lost) - sum(res.values())) / n_failed_att:.1%})")
