"""Breakthrough analysis 3b: what fills the E4B FIXER's context? Per attempt, characters entering the history by source
(observations per tool / command kind, model message text) for overflow vs non-overflow attempts, plus overflow rate
by experiment (fixed: NULL error_class counted as not-overflow)."""
import sqlite3
from collections import defaultdict

db = sqlite3.connect("kb/attempts.sqlite")
q = lambda s, *a: db.execute(s, a).fetchall()
agg = defaultdict(lambda: defaultdict(float))
cnt = defaultdict(int)
for tid, ov in q("""SELECT t.trace_id, COALESCE(a.error_class, '') = 'overflow' FROM attempts_unique a
                    JOIN traces t ON t.attempt_id = a.id WHERE a.model NOT LIKE '%31b%' AND a.resolved IS NOT NULL"""):
    key = "overflow" if ov else "no_overflow"
    cnt[key] += 1
    for tool, ck, ch, n in q("""SELECT tool, COALESCE(cmd_kind, ''), SUM(obs_chars), COUNT(*) FROM tool_calls
                                WHERE trace_id = ? AND author IN ('fixer', 'sibling_conform_agent', 'swe_agent')
                                GROUP BY 1, 2""", tid):
        agg[key][f"obs {tool}{(':' + ck) if ck else ''}"] += ch or 0
        agg[key][f"n {tool}{(':' + ck) if ck else ''}"] += n
    m = q("""SELECT SUM(message_chars) FROM steps WHERE trace_id = ? AND source = 'agent'
             AND author IN ('fixer', 'sibling_conform_agent', 'swe_agent')""", tid)[0][0]
    agg[key]["model text (thinking + replies)"] += m or 0
keys = sorted({k for d in agg.values() for k in d if k.startswith("obs ") or k.startswith("model")},
              key=lambda k: -agg["overflow"].get(k, 0))
print(f"fixer context sources, mean characters per attempt (overflow n {cnt['overflow']}, no_overflow n {cnt['no_overflow']})")
print(f"  {'source':34s} {'overflow':>9s} {'normal':>9s}  calls/attempt ovf vs normal")
for k in keys[:14]:
    o, n_ = agg["overflow"][k] / cnt["overflow"], agg["no_overflow"][k] / cnt["no_overflow"]
    nk = "n " + k[4:] if k.startswith("obs ") else None
    co = agg["overflow"].get(nk, 0) / cnt["overflow"] if nk else 0
    cn = agg["no_overflow"].get(nk, 0) / cnt["no_overflow"] if nk else 0
    print(f"  {k:34s} {o:9.0f} {n_:9.0f}  {co:5.1f} vs {cn:5.1f}")
print("\nlargest single observations in overflow attempts (what blows the window):")
for tool, ck, ch, fp, cmd in q("""SELECT c.tool, c.cmd_kind, c.obs_chars, c.filepath, substr(c.command, 1, 70)
    FROM tool_calls c JOIN traces t ON t.trace_id = c.trace_id JOIN attempts_unique a ON a.id = t.attempt_id
    WHERE a.error_class = 'overflow' AND a.model NOT LIKE '%31b%' ORDER BY c.obs_chars DESC LIMIT 8"""):
    print(f"  {ch:7d} chars  {tool}:{ck or ''} {fp or cmd}")
print("\noverflow rate by experiment (traced E4B, >= 100 attempts):")
for r in q("""SELECT a.exp, COUNT(*), ROUND(AVG(COALESCE(a.error_class, '') = 'overflow'), 3) FROM attempts_unique a
              JOIN traces t ON t.attempt_id = a.id WHERE a.model NOT LIKE '%31b%' GROUP BY a.exp HAVING COUNT(*) >= 100
              ORDER BY 3 DESC"""):
    print(f"   {r[0]:45s} n {r[1]:5d} overflow {r[2]:.1%}")
