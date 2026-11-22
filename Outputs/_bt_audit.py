"""Audit of the 2026-11-21 breakthrough claims (data-analyst pass). Each block re-tests one claim against a confounder.
A1 lead 1 within-task: some-vs-all coverage difference inside each task (no pooling across tasks)
A2 lead 1 sensitivity: tolerance 0 / 5 / 15 / 30 lines; runtime-only gold hunks (drop docs_src/, scripts/, docs/)
A3 lead 1 identifier null: share-rate for MISSED gold hunks vs gold hunks of OTHER tasks in the same repo
B1 lead 2: were overflow attempts' patches graded, and did graded ones fail? (is overflow the cause of the loss?)
B2 lead 2: re-reads split into overlapping (true waste) vs new windows of the same file; thinking-text share
C1 anchor downgrade with a looser similarity (token Jaccard >= 0.5 to any gold '+' line)
"""
import json
import keyword
import random
import re
import sqlite3
import statistics as st
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "kb/attemptdb")
from vfs import VFS  # noqa: E402

db = sqlite3.connect("kb/attempts.sqlite")
vfs = VFS(roots=("Outputs",))
q = lambda s, *a: db.execute(s, a).fetchall()
HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+\d+(?:,\d+)? @@")
IDENT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{3,}\b")
COMMON = set(keyword.kwlist) | {"self", "None", "True", "False", "Optional", "List", "Dict", "Any", "str", "int",
                                "bool", "dict", "list", "tuple", "type", "value", "name", "args", "kwargs", "return"}
NONRUNTIME = re.compile(r"^(docs_src|docs|scripts)/")


def gold_hunks(patch, runtime_only=False):
    out, cur, h = [], None, None
    for l in patch.splitlines():
        if l.startswith("+++ b/"):
            cur = l[6:].strip()
        elif (m := HUNK.match(l)):
            ok = cur and "test" not in cur and cur.endswith(".py") and not (runtime_only and NONRUNTIME.match(cur))
            h = dict(file=cur, start=int(m.group(1)), end=int(m.group(1)) + int(m.group(2) or 1), text="") if ok else None
            if h:
                out.append(h)
        elif h is not None and l[:1] in (" ", "-"):
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


tasks = {t: p for t, p in q("SELECT task, gold_patch FROM tasks")}
att = [(a, t, r, pp, tid) for a, t, r, pp, tid in q("""SELECT a.id, a.task, a.resolved, a.patch_path, t.trace_id FROM attempts_unique a
        LEFT JOIN traces t ON t.attempt_id = a.id
        WHERE a.model NOT LIKE '%31b%' AND a.resolved IS NOT NULL AND a.patch_path IS NOT NULL""") if vfs.exists(pp)]
patches = {a: agent_hunks(vfs.text(pp)) for a, _, _, pp, _ in att}


def coverage(aid, task, tol, runtime_only):
    g = gold_hunks(tasks[task], runtime_only)
    ah = patches[aid]
    if not g or not ah:
        return None, g
    cov = [any(f == h["file"] and s <= h["end"] + tol and e >= h["start"] - tol for f, s, e in ah) for h in g]
    return ("none" if not any(cov) else "all" if all(cov) else "some"), g


print("A1/A2. lead 1 -- multi-hunk tasks only")
print("  tol  gold-hunk set   pooled some / all solve   | within-task: tasks  mean(all - some)  tasks all>some  some>all")
for runtime_only in (False, True):
    for tol in (0, 5, 15, 30):
        pooled = defaultdict(list)
        per = defaultdict(lambda: defaultdict(list))
        for aid, task, res, _, _ in att:
            k, g = coverage(aid, task, tol, runtime_only)
            if k is None or len(g) < 2:
                continue
            pooled[k].append(res)
            per[task][k].append(res)
        diffs = [st.mean(v["all"]) - st.mean(v["some"]) for v in per.values() if len(v["all"]) >= 5 and len(v["some"]) >= 5]
        ps = lambda k: f"{st.mean(pooled[k]):.1%} (n {len(pooled[k])})" if pooled[k] else "-"
        print(f"  {tol:3d}  {'runtime-only' if runtime_only else 'all .py':12s}   {ps('some'):>15s} / {ps('all'):>15s} | "
              f"{len(diffs):5d}   {st.mean(diffs) if diffs else float('nan'):+.3f}   {sum(d > 0 for d in diffs):5d}  {sum(d < 0 for d in diffs):5d}")

print("\nA3. lead 1 -- identifier-sharing null (tol 15, runtime-only hunks)")
by_repo = defaultdict(list)
for t, p in tasks.items():
    for h in gold_hunks(p, True):
        by_repo[t.split("_")[0]].append((t, h))
random.seed(7)
real = null = n = 0
for aid, task, res, _, tid in att:
    if res or tid is None:
        continue
    k, g = coverage(aid, task, 15, True)
    if k != "some":
        continue
    idents = set()
    for (args,) in q("SELECT args_json FROM tool_calls WHERE trace_id = ? AND tool = 'edit_file' AND edit_ok = 1", tid):
        a = json.loads(args)
        for f in ("old_string", "new_string"):
            if isinstance(a.get(f), str):
                idents |= {w for w in IDENT.findall(a[f]) if w not in COMMON}
    ah = patches[aid]
    pool = [h for t, h in by_repo[task.split("_")[0]] if t != task]
    if not pool:  # httpx has a single task: no null available
        continue
    for h in g:
        if any(f == h["file"] and s <= h["end"] + 15 and e >= h["start"] - 15 for f, s, e in ah):
            continue
        n += 1
        real += bool(idents & set(IDENT.findall(h["text"])))
        r = random.choice(pool)
        null += bool(idents & set(IDENT.findall(r["text"])))
print(f"  missed gold hunks sharing an identifier with the agent's edit: {real}/{n} = {real / n:.0%}")
print(f"  random other-task gold hunk (same repo) sharing one:           {null}/{n} = {null / n:.0%}  <- null")

print("\nB1. lead 2 -- were overflow attempts graded?")
rows = q("""SELECT a.test_output_path, a.test_exit_code, a.patch_chars, f.edited_any_gold FROM attempts_unique a
            JOIN traces t ON t.attempt_id = a.id JOIN attempt_features f ON f.trace_id = t.trace_id
            WHERE a.model NOT LIKE '%31b%' AND a.error_class = 'overflow'""")
kinds = Counter()
for tp, ec, pc, gold in rows:
    if not tp:
        kinds["no test output (ungraded)"] += 1
        continue
    txt = vfs.text(tp)[-3000:] if vfs.exists(tp) else ""
    m = re.findall(r"(\d+) (passed|failed)", txt)
    failed = sum(int(x) for x, k in m if k == "failed")
    passed = sum(int(x) for x, k in m if k == "passed")
    tag = "tests ran: some FAILED" if failed else "tests ran: all passed" if passed else "test output w/o pytest summary"
    kinds[tag + (" | gold edit" if gold else " | no gold edit")] += 1
for k, v in kinds.most_common():
    print(f"  {k:45s} {v:4d}")

print("\nB2. lead 2 -- re-read windows: overlapping vs new (read_file with line ranges)")
w = Counter()
for tid, ov in q("""SELECT t.trace_id, COALESCE(a.error_class,'') = 'overflow' FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id
                    WHERE a.model NOT LIKE '%31b%' AND a.resolved IS NOT NULL"""):
    g = "overflow" if ov else "normal"
    shown = defaultdict(list)
    for fp, args, ch in q("""SELECT filepath, args_json, obs_chars FROM tool_calls WHERE trace_id = ? AND tool = 'read_file'
                             AND author IN ('fixer','sibling_conform_agent','swe_agent') ORDER BY idx""", tid):
        a = json.loads(args)
        s = a.get("start_line") or 1
        e = a.get("end_line") or (s + 149)
        try:
            s, e = int(s), int(e)
        except Exception:
            s, e = 1, 150
        prev = shown[fp]
        if not prev:
            k = "first read"
        else:
            ov_lines = max((min(e, pe) - max(s, ps) + 1 for ps, pe in prev), default=0)
            k = "overlapping re-read" if ov_lines >= 0.5 * (e - s + 1) else "new window, same file"
        shown[fp].append((s, e))
        w[(g, k)] += ch or 0
        w[(g, "_n")] += 0
n_ov = q("SELECT COUNT(*) FROM attempts_unique a JOIN traces t ON t.attempt_id=a.id WHERE a.model NOT LIKE '%31b%' AND a.error_class='overflow'")[0][0]
n_no = q("SELECT COUNT(*) FROM attempts_unique a JOIN traces t ON t.attempt_id=a.id WHERE a.model NOT LIKE '%31b%' AND a.resolved IS NOT NULL AND COALESCE(a.error_class,'')<>'overflow'")[0][0]
for g, n_ in (("overflow", n_ov), ("normal", n_no)):
    tot = sum(v for (gg, k), v in w.items() if gg == g)
    print(f"  {g:8s} " + " | ".join(f"{k} {w[(g, k)] / n_:7.0f}" for k in ("first read", "new window, same file", "overlapping re-read"))
          + f" | overlapping share {w[(g, 'overlapping re-read')] / tot:.0%}")
think = q("""SELECT COALESCE(a.error_class,'')='overflow', AVG(f.thinking_chars) FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id
             JOIN attempt_features f ON f.trace_id = t.trace_id WHERE a.model NOT LIKE '%31b%' AND a.resolved IS NOT NULL GROUP BY 1""")
print("  model text chars per attempt (normal, overflow):", [round(x[1]) for x in sorted(think)])

print("\nC1. anchor downgrade with token-Jaccard >= 0.5 instead of exact gold-line match")
gold_add = defaultdict(list)
for t, p in tasks.items():
    cur = None
    for l in p.splitlines():
        if l.startswith("+++ b/"):
            cur = l[6:]
        elif l.startswith("+") and not l.startswith("+++") and cur and "test" not in cur and len(l.strip()) > 6:
            gold_add[t].append(set(IDENT.findall(l)))
res_c = defaultdict(lambda: [0, 0])
for task, res, args, eok, err in q("""SELECT a.task, a.resolved, c.args_json, c.edit_ok, c.error_message FROM tool_calls c
        JOIN traces t ON t.trace_id = c.trace_id JOIN attempts_unique a ON a.id = t.attempt_id
        WHERE c.tool = 'edit_file' AND a.model NOT LIKE '%31b%' AND a.resolved IS NOT NULL"""):
    a = json.loads(args)
    old, new = a.get("old_string") or "", a.get("new_string") or ""
    if not isinstance(new, str) or not isinstance(old, str):
        continue
    o = {l.strip() for l in old.splitlines()}
    add = [set(IDENT.findall(l)) for l in new.splitlines() if l.strip() and l.strip() not in o and len(l.strip()) > 6]
    add = [x for x in add if x]
    if not add or not gold_add[task]:
        continue
    hit = any(len(x & g) / len(x | g) >= 0.5 for x in add for g in gold_add[task] if g)
    kind = "applied" if eok else ("anchor_not_found" if err and "old_string not found" in err else "other")
    key = f"{kind} | {'SOLVED' if res else 'failed'}"
    res_c[key][0] += 1
    res_c[key][1] += hit
for k in sorted(res_c):
    n_, h = res_c[k]
    print(f"  {k:32s} n {n_:6d}  gold-like {h / n_:6.1%}")
