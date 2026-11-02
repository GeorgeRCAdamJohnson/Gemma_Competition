"""Machine-readable mirror of GEMMA_EXPERIMENT_LOG.md.

The markdown log is the human-readable record; this module builds a SQLite + FTS5
database that indexes EVERY `## ` unit in the log (not only the units that happen to
yield a curated claim), plus the extracted claims and the task gold metadata.

Rationale: an audit of this project's own chat transcript found 13 of 44 corrected
errors were facts already present in the log. The cause was search discipline against
a 15k-line markdown file, so retrieval needs an index that covers the whole log.

Usage (build):
    python kb/build_kb.py build            # wired into the normal build
    python kb/kblib/logdb.py --build       # standalone rebuild

Usage (query):
    python kb/kblib/logdb.py "inline_snapshot"
    python kb/kblib/logdb.py "winnable" --limit 5
    python kb/kblib/logdb.py --task rich_3518
    python kb/kblib/logdb.py --sql "select line, heading from units where body like '%18 fastapi%'"
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

SCHEMA_VERSION = "logdb/1"
UNIT_RE = re.compile(r'^##\s+(.*)$')


def _split_units(log_text: str) -> list[dict]:
    """Split the markdown log into units at every `## ` heading.

    Lines before the first `## ` become a leading unit so coverage is 100%.
    """
    lines = log_text.split('\n')
    starts: list[tuple[int, str]] = []
    for i, ln in enumerate(lines):
        m = UNIT_RE.match(ln)
        if m:
            starts.append((i, m.group(1).strip()))
    units: list[dict] = []
    if not starts or starts[0][0] > 0:
        head_end = starts[0][0] if starts else len(lines)
        units.append({
            'line': 1,
            'end_line': head_end,
            'heading': '(preamble)',
            'body': '\n'.join(lines[0:head_end]),
        })
    for idx, (i, title) in enumerate(starts):
        end = starts[idx + 1][0] if idx + 1 < len(starts) else len(lines)
        units.append({
            'line': i + 1,
            'end_line': end,
            'heading': title,
            'body': '\n'.join(lines[i:end]),
        })
    return units


def build_logdb(kb_dir: Path, log_text: str, claims: list[dict] | None = None,
                tasks_gold: dict | None = None) -> dict:
    """Build kb/logdb.sqlite. Returns a small stats dict."""
    kb_dir = Path(kb_dir)
    db_path = kb_dir / 'logdb.sqlite'
    tmp = kb_dir / 'logdb.sqlite.tmp'
    if tmp.exists():
        tmp.unlink()

    units = _split_units(log_text)
    con = sqlite3.connect(tmp)
    cur = con.cursor()
    cur.executescript('''
        PRAGMA journal_mode=OFF;
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE units (
            unit_id  INTEGER PRIMARY KEY,
            line     INTEGER NOT NULL,
            end_line INTEGER NOT NULL,
            heading  TEXT NOT NULL,
            body     TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE units_fts USING fts5(
            heading, body, content='units', content_rowid='unit_id',
            tokenize='porter unicode61'
        );
        CREATE TABLE claims (
            claim_id TEXT PRIMARY KEY, line INTEGER, heading TEXT, kind TEXT,
            status TEXT, auto_status TEXT, text TEXT, tasks TEXT,
            versions TEXT, levers TEXT, models TEXT
        );
        CREATE VIRTUAL TABLE claims_fts USING fts5(
            text, heading, content='claims', content_rowid='rowid',
            tokenize='porter unicode61'
        );
        CREATE TABLE tasks (
            instance_id TEXT PRIMARY KEY, repo TEXT, n_files INTEGER,
            added INTEGER, removed INTEGER, mech_class TEXT,
            files TEXT, problem_title TEXT
        );
        CREATE INDEX idx_units_line ON units(line);
        CREATE INDEX idx_claims_line ON claims(line);
    ''')

    cur.executemany(
        'INSERT INTO units(unit_id, line, end_line, heading, body) VALUES (?,?,?,?,?)',
        [(i + 1, u['line'], u['end_line'], u['heading'], u['body'])
         for i, u in enumerate(units)])
    cur.execute("INSERT INTO units_fts(units_fts) VALUES('rebuild')")

    n_claims = 0
    for c in claims or []:
        try:
            cur.execute(
                'INSERT OR REPLACE INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (c.get('claim_id') or c.get('id'), c.get('line'), c.get('heading'),
                 c.get('kind'), c.get('status'), c.get('auto_status'),
                 (c.get('text') or '')[:20000],
                 json.dumps(c.get('tasks') or []), json.dumps(c.get('versions') or []),
                 json.dumps(c.get('levers') or []), json.dumps(c.get('models') or [])))
            n_claims += 1
        except sqlite3.Error:
            pass
    cur.execute("INSERT INTO claims_fts(claims_fts) VALUES('rebuild')")

    n_tasks = 0
    for tid, t in ((tasks_gold or {}).get('tasks') or {}).items():
        try:
            cur.execute('INSERT OR REPLACE INTO tasks VALUES (?,?,?,?,?,?,?,?)',
                        (tid, t.get('repo'), t.get('n_files'), t.get('added'),
                         t.get('removed'),
                         (t.get('difficulty') or {}).get('kb_mech_class'),
                         json.dumps(t.get('files') or []), t.get('problem_title')))
            n_tasks += 1
        except sqlite3.Error:
            pass

    stats = {
        'units': len(units),
        'claims': n_claims,
        'tasks': n_tasks,
        'log_lines': log_text.count('\n') + 1,
        'schema': SCHEMA_VERSION,
    }
    cur.executemany('INSERT OR REPLACE INTO meta VALUES (?,?)',
                    [(k, str(v)) for k, v in stats.items()])
    con.commit()
    con.close()
    tmp.replace(db_path)
    return stats


def _open(kb_dir: Path) -> sqlite3.Connection:
    p = Path(kb_dir) / 'logdb.sqlite'
    if not p.exists():
        sys.exit(f'no logdb at {p} - run: python kb/build_kb.py build')
    con = sqlite3.connect(f'file:{p}?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    return con


def search(kb_dir: Path, term: str, limit: int = 8) -> list[sqlite3.Row]:
    """FTS search that degrades gracefully for identifiers, paths and FTS syntax.

    File paths such as `dependencies/utils.py` are a syntax error for FTS5 MATCH, and
    a raw substring is what a caller usually wants for an id or a path. So: try MATCH,
    then a quoted phrase, then a LIKE scan.
    """
    con = _open(kb_dir)
    sql = '''SELECT u.line, u.end_line, u.heading,
                    snippet(units_fts, 1, '[', ']', ' ... ', 14) AS snip
             FROM units_fts f JOIN units u ON u.unit_id = f.rowid
             WHERE units_fts MATCH ? ORDER BY rank LIMIT ?'''
    like_sql = '''SELECT line, end_line, heading,
                         substr(body, 1, 200) AS snip
                  FROM units WHERE body LIKE ? ORDER BY line LIMIT ?'''
    try:
        for q in (term, '"%s"' % term.replace('"', '""')):
            try:
                rows = con.execute(sql, (q, limit)).fetchall()
                if rows:
                    return rows
            except sqlite3.OperationalError:
                continue
        return con.execute(like_sql, (f'%{term}%', limit)).fetchall()
    finally:
        con.close()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='machine-readable log index')
    ap.add_argument('term', nargs='?', help='FTS query (supports AND, OR, NOT, "phrases")')
    ap.add_argument('--kb', default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument('--limit', type=int, default=8)
    ap.add_argument('--task', help='list units mentioning a task id')
    ap.add_argument('--sql', help='run a raw read-only query')
    ap.add_argument('--build', action='store_true', help='rebuild from the markdown log')
    a = ap.parse_args(argv)
    kb = Path(a.kb)

    if a.build:
        g = kb.parent
        log_text = (g / 'GEMMA_EXPERIMENT_LOG.md').read_text(encoding='utf-8', errors='replace')
        claims = [json.loads(l) for l in (kb / 'log_claims.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()] \
            if (kb / 'log_claims.jsonl').exists() else []
        tg = json.loads((kb / 'tasks_gold.json').read_text(encoding='utf-8')) \
            if (kb / 'tasks_gold.json').exists() else {}
        print(build_logdb(kb, log_text, claims, tg))
        return 0

    con = _open(kb)
    try:
        if a.sql:
            for r in con.execute(a.sql):
                print(dict(r))
            return 0
        if a.task:
            rows = con.execute(
                'SELECT line, end_line, heading FROM units WHERE body LIKE ? ORDER BY line',
                (f'%{a.task}%',)).fetchall()
            for r in rows:
                print('L%-6d %s' % (r['line'], r['heading'][:96]))
            print(f'\n{len(rows)} units mention {a.task}')
            return 0
        if not a.term:
            ap.print_help()
            return 2
    finally:
        con.close()

    rows = search(kb, a.term, a.limit)
    for r in rows:
        print('L%-6d %s' % (r['line'], r['heading'][:96]))
        print('       %s' % re.sub(r'\s+', ' ', r['snip'] or '')[:300])
    print(f'\n{len(rows)} hits (limit {a.limit})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
