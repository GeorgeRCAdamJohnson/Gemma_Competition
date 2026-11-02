"""Query EXPERIMENT_KB.sqlite - search the log without reading 13k lines.

Usage:
  python kb_query.py search "temperature 0 localization"     # FTS, best sections first
  python kb_query.py search -n 5 "sub-agent overflow"
  python kb_query.py experiments [--verdict REGRESSION] [--arm v4]
  python kb_query.py section 820                            # dump a section by line
  python kb_query.py paper                                   # white-paper digest:
                                                            # experiment registry (csv) + timeline
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DB = Path(__file__).resolve().parent / "EXPERIMENT_KB.sqlite"


def get():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def cmd_search(args):
    con = get()
    q = " ".join(args.terms)
    rows = con.execute(
        "SELECT s.first_line, s.heading, snippet(sections_fts, 1, '[', ']', '...', 90) snip "
        "FROM sections_fts f JOIN sections s ON s.id = f.rowid "
        "WHERE sections_fts MATCH ? ORDER BY rank LIMIT ?", (q, args.n)).fetchall()
    if not rows:
        print("no hits for:", q)
        return
    for r in rows:
        print("L%-6d %s\n         %s\n" % (r["first_line"], r["heading"][:100], r["snip"]))


def cmd_experiments(args):
    con = get()
    sql = "SELECT date, name, k, n, rate, verdict, line FROM experiments WHERE 1=1"
    args_l = []
    if args.verdict:
        sql += " AND verdict LIKE ?"; args_l.append("%" + args.verdict + "%")
    if args.arm:
        sql += " AND name LIKE ?"; args_l.append(args.arm + "%")
    sql += " ORDER BY COALESCE(date, '0'), line"
    rows = con.execute(sql, args_l).fetchall()
    print("%-11s %-10s %8s %7s %-11s %s" % ("date", "arm", "score", "rate", "verdict", "line"))
    for r in rows:
        print("%-11s %-10s %4d/%-4d %7.3f %-11s L%d" % (
            r["date"] or "?", r["name"][:10], r["k"], r["n"],
            r["rate"] if r["rate"] is not None else 0, r["verdict"] or "", r["line"]))


def cmd_section(args):
    con = get()
    row = con.execute(
        "SELECT heading, first_line, text FROM sections "
        "WHERE first_line <= ? ORDER BY first_line DESC LIMIT 1", (args.line,)).fetchone()
    print("== %s (L%d) ==" % (row["heading"], row["first_line"]))
    print(row["text"][: args.chars])


def cmd_paper(args):
    con = get()
    print("# WHITE-PAPER DIGEST")
    print("\n## Experiment registry (chronological)")
    rows = con.execute(
        "SELECT date, name, k, n, rate, verdict, line FROM experiments "
        "WHERE n >= 10 ORDER BY COALESCE(date, '0'), line").fetchall()
    print("| date | arm/config | score | rate | verdict | log |")
    print("|---|---|---|---|---|---|")
    for r in rows:
        print("| %s | %s | %d/%d | %.2f | %s | L%d |" % (
            r["date"] or "-", r["name"], r["k"], r["n"], r["rate"] or 0,
            r["verdict"] or "-", r["line"]))
    print("\n## Section index (for narrative chapters)")
    for r in con.execute("SELECT first_line, level, heading FROM sections WHERE level <= 2 ORDER BY first_line"):
        print("%sL%-6d %s" % ("  " * (r["level"] - 1), r["first_line"], r["heading"][:110]))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search"); s.add_argument("terms", nargs="+"); s.add_argument("-n", type=int, default=8)
    s.set_defaults(fn=cmd_search)
    e = sub.add_parser("experiments"); e.add_argument("--verdict"); e.add_argument("--arm")
    e.set_defaults(fn=cmd_experiments)
    c = sub.add_parser("section"); c.add_argument("line", type=int); c.add_argument("--chars", type=int, default=3000)
    c.set_defaults(fn=cmd_section)
    p = sub.add_parser("paper"); p.set_defaults(fn=cmd_paper)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
