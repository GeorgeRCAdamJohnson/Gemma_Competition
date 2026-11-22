"""Breakthrough analysis 3c: how much of the fixer's read_file volume is waste, and has a STRUCTURAL limit ever been tried?
waste kinds per read_file observation (E4B, fixer-side authors):
  repeat      identical read_file call earlier in the same attempt (same args)
  reread      same file read again with different args (window) -- overlapping context
  test/doc    file under tests/ or docs/ or a .md/.rst (not a gold source file)
  source      everything else (first read of a source file)
Then: every bundle's fixer tool list -> which bundles removed read_file / added other read tools, and their results."""
import json
import re
import sqlite3
from collections import defaultdict

db = sqlite3.connect("kb/attempts.sqlite")
q = lambda s, *a: db.execute(s, a).fetchall()
tot = defaultdict(lambda: defaultdict(float))
n_att = defaultdict(int)
for tid, ov, res in q("""SELECT t.trace_id, COALESCE(a.error_class, '') = 'overflow', a.resolved FROM attempts_unique a
                         JOIN traces t ON t.attempt_id = a.id WHERE a.model NOT LIKE '%31b%' AND a.resolved IS NOT NULL"""):
    g = "overflow" if ov else ("solved" if res else "failed")
    n_att[g] += 1
    seen_files = set()
    for fp, ch, rep in q("""SELECT filepath, obs_chars, repeat_of_idx FROM tool_calls WHERE trace_id = ? AND tool = 'read_file'
                            AND author IN ('fixer', 'sibling_conform_agent', 'swe_agent') ORDER BY idx""", tid):
        f = fp or ""
        if rep is not None:
            k = "repeat"
        elif f in seen_files:
            k = "reread"
        elif re.search(r"(^|/)(tests?|docs?|docs_src)/|\.(md|rst|txt)$", f):
            k = "test/doc"
        else:
            k = "source"
        seen_files.add(f)
        tot[g][k] += ch or 0
print("read_file characters per attempt by kind")
print(f"  {'group':9s} {'n':>5s} " + " ".join(f"{k:>9s}" for k in ("source", "reread", "repeat", "test/doc", "TOTAL")) + "  waste share")
for g in ("solved", "failed", "overflow"):
    d = {k: tot[g][k] / n_att[g] for k in ("source", "reread", "repeat", "test/doc")}
    T = sum(d.values())
    print(f"  {g:9s} {n_att[g]:5d} " + " ".join(f"{d[k]:9.0f}" for k in d) + f" {T:9.0f}  {(T - d['source']) / T:6.1%}")

print("\nfixer tool lists across all bundles (does any arm restrict read_file structurally?)")
rows = q("""SELECT b.path, b.sha12, f.relpath, f.content FROM bundle_files f JOIN bundles b ON b.bundle_id = f.bundle_id
            WHERE (f.relpath LIKE 'sub_agents/%.yaml' OR f.relpath = 'agent.yaml') AND f.content LIKE '%tools:%'""")
tools_by = defaultdict(set)
for path, sha, rel, content in rows:
    m = re.search(r"^tools:\s*\n((?:\s+-\s*\S+\s*\n?)+)", content, re.M)
    if m and ("fixer" in rel or rel == "agent.yaml"):
        tools_by[(path, sha)].add(tuple(sorted(re.findall(r"-\s*(\S+)", m.group(1)))))
sets = defaultdict(list)
for (path, sha), ts in tools_by.items():
    for t in ts:
        sets[t].append(path)
for t, paths in sorted(sets.items(), key=lambda kv: -len(kv[1])):
    print(f"  {len(paths):3d} bundles  read_file={'read_file' in t!s:5s} tools={list(t)}")
no_read = [p for t, ps in sets.items() if "read_file" not in t for p in ps]
print(f"\nbundles whose main/fixer agent has NO read_file: {len(no_read)}", no_read[:8])
for r in q(f"""SELECT ac.exp, ac.arm, ac.n, ac.resolve_rate FROM arm_catalog ac JOIN bundles b ON b.sha12 = ac.bundle_sha12
              WHERE b.path IN ({','.join('?' * len(no_read)) or "''"})""", *no_read):
    print("   results:", r)
