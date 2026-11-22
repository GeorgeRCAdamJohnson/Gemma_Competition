"""Stage `gemmalog`: GEMMA_EXPERIMENT_LOG.md -> log_sections (+ FTS5) and log_mentions, so every log entry links to
the experiments, Kaggle slugs, tasks, submission refs, bundle hashes and Drive tags it talks about (and back)."""
import re

from vfs import ROOT

SCHEMA = """
CREATE TABLE log_sections (sec_id INTEGER PRIMARY KEY, line_start INTEGER, line_end INTEGER, level INTEGER,
  heading TEXT, date TEXT, text TEXT);
CREATE VIRTUAL TABLE log_sections_fts USING fts5(heading, text, content='log_sections', content_rowid='sec_id');
CREATE TABLE log_mentions (sec_id INTEGER, kind TEXT, value TEXT, PRIMARY KEY (sec_id, kind, value));
CREATE INDEX ix_lm ON log_mentions(kind, value);
"""
HEAD = re.compile(r"^(#{1,4})\s+(.*)$")
DATE = re.compile(r"(20\d\d-\d\d-\d\d)")
PATTERNS = {
    "slug": re.compile(r"\bcomfyops/[\w.-]+"),
    "task": re.compile(r"\b(?:fastapi|rich|requests|httpx)_\d{3,6}\b"),
    "submission": re.compile(r"\b5[6-9]\d{6}\b"),
    "drive_tag": re.compile(r"\be4b_ab\w+|\be4b_\w+_2026\d{4}\w*"),
}


def run(db, vfs):
    db.executescript(SCHEMA)
    lines = (ROOT / "GEMMA_EXPERIMENT_LOG.md").read_text(encoding="utf-8", errors="replace").splitlines()
    heads = [(i, len(m.group(1)), m.group(2).strip()) for i, l in enumerate(lines) if (m := HEAD.match(l))]
    if not heads or heads[0][0] != 0:
        heads.insert(0, (0, 0, "(preamble)"))
    exps = [e for (e,) in db.execute("SELECT exp FROM experiments") if len(e) >= 8]
    shas = {s for (s,) in db.execute("SELECT DISTINCT sha12 FROM bundles")}
    last_date = None
    for k, (i, lvl, h) in enumerate(heads):
        j = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        text = "\n".join(lines[i:j])
        d = DATE.search(h)
        last_date = d.group(1) if d else last_date
        sid = k + 1
        db.execute("INSERT INTO log_sections VALUES (?,?,?,?,?,?,?)", (sid, i + 1, j, lvl, h, last_date, text))
        db.execute("INSERT INTO log_sections_fts (rowid, heading, text) VALUES (?,?,?)", (sid, h, text))
        ments = set()
        for kind, rx in PATTERNS.items():
            ments |= {(kind, m) for m in rx.findall(text)}
        ments |= {("exp", e) for e in exps if e in text}
        ments |= {("bundle_sha12", s) for s in re.findall(r"\b[0-9a-f]{12}\b", text) if s in shas}
        db.executemany("INSERT OR IGNORE INTO log_mentions VALUES (?,?,?)", [(sid, a, b) for a, b in ments])
    n = db.execute("SELECT COUNT(*), (SELECT COUNT(*) FROM log_mentions) FROM log_sections").fetchone()
    print(f"    {n[0]} log sections, {n[1]} entity mentions", flush=True)
