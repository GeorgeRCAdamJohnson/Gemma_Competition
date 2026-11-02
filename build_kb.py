"""Build EXPERIMENT_KB.sqlite from GEMMA_EXPERIMENT_LOG.md (idempotent full rebuild).

Tables:
  sections(id, heading, level, first_line, last_line, text)  -- markdown sections
  experiments(id, date, name, model, n, k, rate, verdict, line, note)  -- curated extraction
  artifacts(path, line)                                        -- file paths cited
  sections_fts (FTS5)                                          -- full-text search
Designed for the white paper: query the experiment registry + full-text search + section dump.
"""
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
G = Path(r"C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma")
LOG = G / "GEMMA_EXPERIMENT_LOG.md"
DB = G / "EXPERIMENT_KB.sqlite"

text = LOG.read_text(encoding="utf-8", errors="replace")
lines = text.splitlines()

# ---- sections by headings ----
sec_re = re.compile(r"^(#{1,4})\s+(.*)$")
sections = []  # (heading, level, first_line, text)
starts = []
for i, ln in enumerate(lines, 1):
    m = sec_re.match(ln)
    if m:
        starts.append((i, len(m.group(1)), m.group(2)))
for idx, (line_no, lvl, head) in enumerate(starts):
    end = starts[idx + 1][0] - 1 if idx + 1 < len(starts) else len(lines)
    body = "\n".join(lines[line_no - 1:end])
    sections.append((head, lvl, line_no, body))

# ---- experiments: score-table rows + verdict lines ----
exps = []
score_re = re.compile(
    r"\|\s*(?:\*\*)?([Av](?:\d{1,2}|[0-9a-f]{4,12}|[\w.-]*?)|ca5|ctrl|D\d|P\d|E\d)\**\s*"
    r"\|\s*([^|]*?)\|\s*(\d+)\s*/\s*(\d+)\s*\|")
date_re = re.compile(r"(2026-\d\d-\d\d)")
for i, ln in enumerate(lines, 1):
    # rows like | A24 | ... | 36/120 |   or  9/21 patterns with an arm name nearby
    m = re.search(r"\b([Aa]\d{1,2}|v\d|D\d|ca5|ctrl|v\d[\w-]*|A\d\d)\b[^\n]*?(\d{1,3})\s*/\s*(\d{1,3})\b", ln)
    if m and not ln.strip().startswith("```"):
        name, k, n = m.group(1), int(m.group(2)), int(m.group(3))
        if n >= 5 and k <= n:
            verdict = None
            low = ln.lower()
            if "regression" in low: verdict = "REGRESSION"
            elif "null" in low or "tie" in low: verdict = "NULL/TIE"
            elif "advance" in low: verdict = "ADVANCE"
            # date: nearest date in this line or 60 lines up
            d = date_re.search(ln)
            if not d:
                for j in range(i - 1, max(0, i - 61), -1):
                    d = date_re.search(lines[j - 1])
                    if d: break
            exps.append((d.group(1) if d else None, name, n, k,
                         round(k / n, 4) if n else None, verdict, i, ln.strip()[:220]))
# dedupe exact
exps = list(dict.fromkeys(exps))

# ---- artifacts ----
art_re = re.compile(r"((?:[A-Za-z]:\\|Gemma/|local_eval/|parity_rig/)[\w./\\-]+\.(?:py|md|json|jsonl|zip|ipynb|yaml|yml|txt|png))")
arts = set()
for i, ln in enumerate(lines, 1):
    for m in art_re.finditer(ln):
        arts.add((m.group(1), i))

# ---- write DB ----
if DB.exists():
    DB.unlink()
con = sqlite3.connect(DB)
con.execute("CREATE TABLE sections (id INTEGER PRIMARY KEY, heading TEXT, level INT, first_line INT, text TEXT)")
con.executemany("INSERT INTO sections (heading, level, first_line, text) VALUES (?,?,?,?)", sections)
con.execute("CREATE TABLE experiments (id INTEGER PRIMARY KEY, date TEXT, name TEXT, n INT, k INT, rate REAL, verdict TEXT, line INT, note TEXT)")
con.executemany("INSERT INTO experiments (date, name, n, k, rate, verdict, line, note) VALUES (?,?,?,?,?,?,?,?)", exps)
con.execute("CREATE TABLE artifacts (path TEXT, line INT)")
con.executemany("INSERT INTO artifacts VALUES (?,?)", sorted(arts))
con.execute("CREATE VIRTUAL TABLE sections_fts USING fts5(heading, text, content='sections', content_rowid='id')")
con.execute("INSERT INTO sections_fts(rowid, heading, text) SELECT id, heading, text FROM sections")
con.commit()
n_sec, n_exp, n_art = (con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                       for t in ("sections", "experiments", "artifacts"))
con.close()
print("KB written: %s" % DB)
print("  sections=%d  experiments=%d  artifacts=%d  log_lines=%d" % (n_sec, n_exp, n_art, len(lines)))
