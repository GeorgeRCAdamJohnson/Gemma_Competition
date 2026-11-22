"""Breakthrough analysis 1: WHY does edit_file say "old_string not found" for E4B, and what happens next?
For each failed anchor, compare old_string with the file text the agent had SEEN in that attempt (read_file contents +
run_command stdout mentioning the file) and classify:
  stale        old_string is in the seen text, but an earlier successful edit changed that file
  in_seen      old_string is in the seen text and the file was not edited before (harness-side mismatch?)
  gutter       old_string carries line-number prefixes copied from a numbered listing
  escaping     matches the seen text after unescaping literal \\n / \\t / \\"
  whitespace   matches after normalising indentation/trailing spaces per line
  near_miss    >= 60% of its non-blank lines appear verbatim (stripped) in the seen text
  partial      some (< 60%) lines appear
  invented     no line appears; file content was seen
  never_seen   the file was never read/printed in the attempt before this edit
Then: recovery (next edit on the same file succeeds? within how many calls? did the agent re-read first?) and outcome.
Reads kb/attempts.sqlite. Writes Outputs/_bt_anchor_mechanism.json."""
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

db = sqlite3.connect("kb/attempts.sqlite")
GUTTER = re.compile(r"^\s*\d+\s*[:|\t]|^\s*\d+\s{2,}\S", re.M)


def norm_ws(s):
    return "\n".join(l.rstrip() for l in s.replace("\t", "    ").splitlines()).strip("\n")


def strip_lines(s):
    return [l.strip() for l in s.splitlines() if l.strip()]


rows = db.execute("""
SELECT a.id, a.task, a.resolved, a.exp, a.arm, c.trace_id, c.idx, c.tool, c.filepath, c.args_json, c.cmd_files,
       c.obs_status, c.error_message, c.edit_ok, c.obs_content, c.cmd_kind
FROM tool_calls c JOIN traces t ON t.trace_id = c.trace_id JOIN attempts_unique a ON a.id = t.attempt_id
WHERE a.model NOT LIKE '%31b%' AND a.resolved IS NOT NULL
ORDER BY c.trace_id, c.idx""").fetchall()
by_trace = defaultdict(list)
for r in rows:
    by_trace[r[5]].append(r)

cls = Counter()
cls_solve = defaultdict(list)
recov = Counter()
per_attempt = []
examples = defaultdict(list)
for tid, calls in by_trace.items():
    seen = defaultdict(str)     # file -> concatenated seen text
    edited = set()
    nf_here = []
    for i, c in enumerate(calls):
        aid, task, res, exp, arm, _, idx, tool, fp, args, cfiles, st, err, eok, obs, ck = c
        try:
            o = json.loads(obs) if obs and obs[:1] == "{" else {}
        except Exception:
            o = {}
        if tool == "read_file" and fp and isinstance(o.get("content"), str):
            seen[fp] += "\n" + o["content"]
        elif tool == "run_command" and cfiles and isinstance(o.get("stdout"), str):
            for f in json.loads(cfiles):
                seen[f] += "\n" + o["stdout"]
        if tool == "edit_file" and eok:
            edited.add(fp)
        if tool == "edit_file" and err and "old_string not found" in err:
            try:
                a = json.loads(args)
            except Exception:
                a = {}
            old = a.get("old_string") if isinstance(a.get("old_string"), str) else ""
            text = seen.get(fp, "")
            if not text.strip():
                k = "never_seen"
            elif old and old in text:
                k = "stale" if fp in edited else "in_seen"
            elif GUTTER.search(old or "") and len(GUTTER.findall(old)) >= max(1, len(old.splitlines()) // 2):
                k = "gutter"
            elif old and old.encode().decode("unicode_escape", "ignore") in text if "\\" in old else False:
                k = "escaping"
            elif old and norm_ws(old) in norm_ws(text):
                k = "whitespace"
            else:
                L = strip_lines(old)
                tl = set(strip_lines(text))
                frac = sum(l in tl for l in L) / len(L) if L else 0
                k = "near_miss" if frac >= 0.6 else "partial" if frac > 0 else "invented"
            cls[k] += 1
            cls_solve[k].append(res)
            # recovery: next edit_file on the same file
            nxt = next((x for x in calls[i + 1:] if x[7] == "edit_file" and x[8] == fp), None)
            reread = any(x[7] == "read_file" and x[8] == fp or (x[7] == "run_command" and x[10] and fp in json.loads(x[10]))
                         for x in calls[i + 1:calls.index(nxt)] if nxt) if nxt else None
            if nxt is None:
                recov["no further edit of that file"] += 1
            elif nxt[13]:
                recov["next edit ok" + (" (re-read first)" if reread else " (no re-read)")] += 1
            else:
                recov["next edit failed" + (" (re-read first)" if reread else " (no re-read)")] += 1
            nf_here.append(k)
            if len(examples[k]) < 3:
                examples[k].append(dict(task=task, file=fp, old=old[:300], seen_chars=len(text)))
    if nf_here:
        per_attempt.append((calls[0][0], calls[0][1], calls[0][2], nf_here))

tot = sum(cls.values())
print(f"{tot} 'old_string not found' failures in {len(per_attempt)} E4B attempts\n")
print("class        n      share  solve rate of the attempts")
for k, n in cls.most_common():
    print(f"  {k:11s} {n:5d}  {n / tot:6.1%}  {sum(cls_solve[k]) / len(cls_solve[k]):6.1%}")
print("\nwhat happened next (per failure):")
for k, n in recov.most_common():
    print(f"  {k:40s} {n:5d}  {n / tot:6.1%}")
fixable = sum(cls[k] for k in ("stale", "in_seen", "gutter", "escaping", "whitespace"))
print(f"\nmechanically recoverable classes (stale/in_seen/gutter/escaping/whitespace): {fixable} ({fixable / tot:.1%})")
print(f"near_miss (mostly right, some lines wrong): {cls['near_miss']} ({cls['near_miss'] / tot:.1%})")
for k in ("in_seen", "near_miss", "invented", "never_seen"):
    for e in examples[k][:2]:
        print(f"\n  [{k}] {e['task']} {e['file']} (seen {e['seen_chars']} chars)\n    old_string: {e['old']!r}")
Path("Outputs/_bt_anchor_mechanism.json").write_text(json.dumps(
    dict(classes=cls, recovery=recov, examples=examples), indent=1, default=list))
