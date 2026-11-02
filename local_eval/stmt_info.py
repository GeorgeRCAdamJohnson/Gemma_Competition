"""Does the problem statement carry enough information to localize the gold fix?  CPU only, no model.

For each rich task: parse the gold patch (files, hunk-header scopes, identifiers on changed lines) and
check which of them literally appear in the problem statement. A task whose statement names none of them
cannot be localized by reading the statement; it needs search to get lucky.
"""
import json, re, sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent
TASKS = HERE.parent / "comp_files" / "tasks.jsonl"
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
STOP = set("""self none true false return import from class def with else elif pass this that have been will
    which when then than into each only also more some text line lines file files test tests data type types
    value values name names args kwargs list dict tuple string bool optional union any""".split())


def idents(s):
    # code-like only: snake_case, CamelCase, dunder or CONSTANT; plain English words are not evidence of localization
    return {w for w in IDENT.findall(s)
            if w.lower() not in STOP and ("_" in w or re.search(r"[a-z][A-Z]", w) or (w.isupper() and len(w) >= 4))}


def analyse(t):
    stmt = t["problem_statement"]
    gold = t["patch"]
    files = re.findall(r"^\+\+\+ b/(\S+)", gold, re.M)
    scopes, changed = set(), set()
    for line in gold.splitlines():
        m = re.match(r"^@@ .*?@@\s*(.*)$", line)
        if m:
            scopes |= idents(m.group(1))
        elif line[:1] in "+-" and not line.startswith(("+++", "---")):
            changed |= idents(line[1:])
    low = stmt.lower()
    file_hit = [f for f in files if f.lower() in low or pathlib.PurePosixPath(f).name.lower() in low]
    scope_hit = sorted(s for s in scopes if s in stmt)
    chg_hit = sorted(c for c in changed if c in stmt)
    return {
        "id": t["instance_id"], "stmt_chars": len(stmt), "files": files,
        "names_file": bool(file_hit), "names_scope": bool(scope_hit), "names_changed_ident": bool(chg_hit),
        "scope_hit": scope_hit[:4], "chg_hit": chg_hit[:4],
    }


def main():
    only = set(sys.argv[1:])
    rows = []
    for line in open(TASKS, encoding="utf-8"):
        t = json.loads(line)
        if t["repo"] != "Textualize/rich":
            continue
        r = analyse(t)
        if only and r["id"] not in only and r["id"].split("_")[1] not in only:
            continue
        rows.append(r)
    rows.sort(key=lambda r: r["id"])
    print("file = statement names the gold file path/name; scope = names a function/class in a gold hunk header; "
          "ident = names a code-like identifier on a changed line")
    print(f"{'task':11}{'chars':>6}  file scope ident  gold file(s) / hits")
    for r in rows:
        print(f"{r['id']:11}{r['stmt_chars']:>6}   {'Y' if r['names_file'] else '-'}     {'Y' if r['names_scope'] else '-'}     "
              f"{'Y' if r['names_changed_ident'] else '-'}    {','.join(r['files'])[:44]:44} {r['scope_hit'] or ''} {r['chg_hit'] or ''}")
    n = len(rows)
    print(f"\n{n} tasks | names gold file: {sum(r['names_file'] for r in rows)} | names a hunk scope: "
          f"{sum(r['names_scope'] for r in rows)} | names a changed identifier: {sum(r['names_changed_ident'] for r in rows)} | "
          f"names none of the three: {sum(not (r['names_file'] or r['names_scope'] or r['names_changed_ident']) for r in rows)}")
    json.dump(rows, open(HERE / "runs" / "stmt_info.json", "w"), indent=1)


if __name__ == "__main__":
    main()
