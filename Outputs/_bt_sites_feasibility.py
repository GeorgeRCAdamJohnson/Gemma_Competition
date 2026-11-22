"""Breakthrough analysis 5b: could a mechanical "other sites" check find the gold hunks an incomplete E4B fix missed?
For failed attempts that covered SOME but not all gold source hunks: take identifiers from the agent's applied edits
(old_string + new_string, length >= 4, not Python keywords/common words) and test whether each MISSED gold hunk's
base-side text (context + removed lines of that hunk in the gold patch) contains any of them. If most missed hunks
share an identifier with the edit, a grep from the edit (same file, then repo) would surface them."""
import json
import keyword
import re
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, "kb/attemptdb")
from vfs import VFS  # noqa: E402

HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")
IDENT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{3,}\b")
COMMON = set(keyword.kwlist) | {"self", "None", "True", "False", "return", "Optional", "List", "Dict", "Any", "str",
                                "int", "bool", "dict", "list", "tuple", "type", "value", "name", "args", "kwargs"}


def gold_hunks(patch):
    out, cur, h = [], None, None
    for l in patch.splitlines():
        if l.startswith("+++ b/"):
            cur = l[6:].strip()
        elif (m := HUNK.match(l)):
            h = dict(file=cur, start=int(m.group(1)), end=int(m.group(1)) + int(m.group(2) or 1), text="")
            if cur and "test" not in cur and cur.endswith(".py"):
                out.append(h)
            else:
                h = None
        elif h is not None and (l.startswith(" ") or l.startswith("-")):
            h["text"] += l[1:] + "\n"
    return out


def agent_hunks(patch):
    out, cur = [], None
    for l in patch.splitlines():
        if l.startswith("+++ b/"):
            cur = l[6:].strip()
        elif (m := HUNK.match(l)) and cur:
            s = int(m.group(1))
            out.append((cur, s, s + int(m.group(2) or 1)))
    return out


db = sqlite3.connect("kb/attempts.sqlite")
vfs = VFS(roots=("Outputs",))
gold = {t: gold_hunks(p) for t, p in db.execute("SELECT task, gold_patch FROM tasks")}
stats = Counter()
same_file = Counter()
for aid, task, pp, tid in db.execute("""SELECT a.id, a.task, a.patch_path, t.trace_id FROM attempts_unique a
        JOIN traces t ON t.attempt_id = a.id WHERE a.model NOT LIKE '%31b%' AND a.resolved = 0 AND a.patch_path IS NOT NULL"""):
    g = gold.get(task) or []
    if len(g) < 2 or not vfs.exists(pp):
        continue
    ah = agent_hunks(vfs.text(pp))
    cov = [any(f == h["file"] and s <= h["end"] + 15 and e >= h["start"] - 15 for f, s, e in ah) for h in g]
    if not any(cov) or all(cov):
        continue
    idents = set()
    for (args,) in db.execute("SELECT args_json FROM tool_calls WHERE trace_id = ? AND tool = 'edit_file' AND edit_ok = 1", (tid,)):
        a = json.loads(args)
        for k in ("old_string", "new_string"):
            if isinstance(a.get(k), str):
                idents |= {w for w in IDENT.findall(a[k]) if w not in COMMON}
    for h, c in zip(g, cov):
        if c:
            continue
        stats["missed hunks"] += 1
        hit = bool(idents & set(IDENT.findall(h["text"])))
        stats["missed hunk shares an identifier with the agent's edit"] += hit
        edited_files = {f for f, _, _ in ah}
        same_file["in a file the agent already edited" if h["file"] in edited_files else "in a file the agent did NOT edit"] += 1
        same_file[("same file" if h["file"] in edited_files else "other file") + (" + shares identifier" if hit else "")] += 1
m = stats["missed hunks"]
print(f"missed gold hunks in failed incomplete-fix E4B attempts: {m}")
print(f"  share an identifier with the agent's own applied edits: {stats['missed hunk shares an identifier with the agent' + chr(39) + 's edit']} "
      f"({stats['missed hunk shares an identifier with the agent' + chr(39) + 's edit'] / m:.0%})")
for k, v in same_file.most_common():
    print(f"  {k:45s} {v:5d} ({v / m:.0%})")
