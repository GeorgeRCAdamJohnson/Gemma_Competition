# Search GEMMA_EXPERIMENT_LOG sections (FTS5) for prior work on a theme. usage: python Outputs/_bt_log_search.py
import sqlite3

db = sqlite3.connect("kb/attempts.sqlite")
themes = {
    "all-sites / incomplete fix": '"all call sites" OR "every site" OR "other occurrences" OR "parallel path" OR '
                                  '"parallel paths" OR "all occurrences" OR "every caller" OR "incomplete fix" OR '
                                  '"partial fix" OR "every field" OR "composed behaviour" OR "composed behavior"',
    "read limits / dedupe": '"re-read" OR "reread" OR "read_file" NEAR "remove" OR "dedupe" OR "redundant read" OR '
                            '"read cache" OR "sed -n" NEAR "instead"',
}
for name, expr in themes.items():
    rows = db.execute("""SELECT s.line_start, s.date, substr(s.heading, 1, 100) FROM log_sections_fts f
                         JOIN log_sections s ON s.sec_id = f.rowid WHERE log_sections_fts MATCH ?
                         ORDER BY s.line_start""", (expr,)).fetchall()
    print(f"\n== {name}: {len(rows)} sections")
    for r in rows[:25]:
        print(f"  L{r[0]:<6d} {r[1] or '':10s} {r[2]}")
