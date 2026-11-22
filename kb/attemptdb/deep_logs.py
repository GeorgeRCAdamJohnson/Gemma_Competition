"""Stage `logs`: swegemma display logs (logs/<task>.log) for attempts WITHOUT a trace -> log_events, plus
attempt_features (basis='log', keyed by trace_id = -attempt_id). Observations in display logs are truncated, so
features that need full observations (diffs, exit codes) are NULL/approximate here."""
import json
import re

from deep_traces import PYFILE, cmd_kind, features, norm

SCHEMA = """
CREATE TABLE log_events (attempt_id INTEGER, idx INTEGER, t_s REAL, author TEXT, kind TEXT, tool TEXT, arg TEXT,
  chars INTEGER, status TEXT, verdict TEXT, text TEXT, PRIMARY KEY (attempt_id, idx));
CREATE INDEX ix_le_tool ON log_events(tool);
"""
ANSI = re.compile(r"\x1b\[[0-9;]*m")
LINE = re.compile(r"^\s*\[\s*([\d.]+)s\]\s?(.*)$")
TOOLS = "read_file|run_command|edit_file|write_file|run_skill_script|get_status|submit_patch|list_files|search_code|" \
        "get_code_subgraph|find_definition|grep_code"
CALL = re.compile(rf"(?<![\w:])({TOOLS})(?:\s*\((.*)\)|\s+(\{{.*\}})|)\s*$")
OBS_TOOL = re.compile(rf"({TOOLS}):\s*(\{{.*)$")
THOUGHT = re.compile(r"\((\d+) chars\)\s*\"(.*)")
STATUS = re.compile(r"""['"]status['"]:\s*['"](\w+)['"]""")


def parse(text):
    ev = []
    for raw in ANSI.sub("", text).splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        t, rest = float(m.group(1)), m.group(2)
        author = "verifier" if "(verifier)" in rest else "tester" if "(tester)" in rest else "fixer"
        if "Task Prompt:" in rest:
            ev.append(dict(t=t, author="harness", kind="task_prompt", text=rest[:300]))
        elif "Agent finished:" in rest:
            ev.append(dict(t=t, author=author, kind="final", text=rest.split("Agent finished:", 1)[1].strip()[:2000]))
        elif (mm := THOUGHT.search(rest)):
            ev.append(dict(t=t, author=author, kind="thought", chars=int(mm.group(1)), text=mm.group(2)[:500]))
        elif (mm := OBS_TOOL.search(rest)) or "{'status'" in rest or '{"status"' in rest:
            body = mm.group(2) if mm else rest
            st = STATUS.search(body)
            verdict = "ACCEPTED" if "ACCEPTED" in body else "REJECTED" if "REJECTED" in body else None
            ev.append(dict(t=t, author=author, kind="obs", tool=mm.group(1) if mm else None,
                           status=st.group(1) if st else None, verdict=verdict, text=body[:1500]))
        elif (mm := CALL.search(rest)):
            ev.append(dict(t=t, author=author, kind="call", tool=mm.group(1), arg=(mm.group(2) or mm.group(3) or "")[:2000]))
        elif "RETRY" in rest:
            ev.append(dict(t=t, author="harness", kind="retry", text=rest[:500]))
    return ev


def run(db, vfs):
    db.executescript(SCHEMA)
    gold_of = {t: {g for g in json.loads(gf) if "test" not in g} for t, gf in db.execute("SELECT task, gold_files FROM tasks")}
    have = {a for (a,) in db.execute("SELECT attempt_id FROM traces WHERE attempt_id IS NOT NULL")}
    todo = db.execute("""SELECT COALESCE(dup_of, id) AS aid, MIN(log_path), MIN(task) FROM attempts
                         WHERE log_path IS NOT NULL GROUP BY COALESCE(dup_of, id)""").fetchall()
    n = 0
    for aid, lp, task in todo:
        if aid in have or not vfs.exists(lp):
            continue
        evs = parse(vfs.text(lp))
        if not evs:
            continue
        rows, crow, srows = [], [], []
        gold = gold_of.get(task, set())
        seen, ci = {}, 0
        for i, e in enumerate(evs):
            rows.append((aid, i, e["t"], e.get("author"), e["kind"], e.get("tool"), e.get("arg"), e.get("chars"),
                         e.get("status"), e.get("verdict"), e.get("text")))
            if e["kind"] == "thought":
                srows.append((None, i, "agent", e["author"], "thinking", None, e["t"], e["t"], e.get("text"),
                              e.get("chars") or 0, None, None, None, 1, 0))
            elif e["kind"] in ("retry", "task_prompt"):
                srows.append((None, i, "user", e["author"], e["kind"], None, e["t"], e["t"], e.get("text"), 0,
                              None, None, None, 0, 0))
            elif e["kind"] == "final":
                srows.append((None, i, "agent", e["author"], "final", None, e["t"], e["t"], e.get("text"), 0,
                              None, None, None, 1, 0))
            elif e["kind"] == "call":
                arg = e.get("arg") or ""
                tool = e["tool"]
                fp = cmd = None
                if tool in ("read_file", "edit_file", "write_file"):
                    fp = norm(arg.strip().split(",")[0].strip(" '\""))
                elif tool == "run_command":
                    cmd = arg
                ck = cmd_kind(cmd) if cmd else None
                cfiles = sorted({norm(x) for x in PYFILE.findall(cmd)}) if cmd else []
                # observation = next obs event of the same author
                ob = next((x for x in evs[i + 1:i + 4] if x["kind"] == "obs" and x.get("author") == e["author"]), {})
                st = ob.get("status") or ("ok" if ob.get("verdict") else None)
                st = "ok" if st in ("ok", "success") else "error" if st == "error" else "unknown"
                key = (tool, arg)
                rep = seen.get(key)
                seen.setdefault(key, ci)
                is_edit = int(tool in ("edit_file", "write_file") or ck == "script_write")
                files = [fp] if fp else cfiles
                crow.append((None, i, ci, e["author"], tool, json.dumps({"arg": arg}), fp, cmd, ck,
                             json.dumps(cfiles) if cfiles else None, None, None, e["t"], ob.get("t"),
                             (ob["t"] - e["t"]) if ob.get("t") is not None else None, st, None, None, None,
                             len(ob.get("text") or ""), None, None, None, None, None, None, ob.get("verdict"), is_edit,
                             int(is_edit and st == "ok"), int(bool(gold) and any(f in gold for f in files if f)), rep, None))
                ci += 1
        db.executemany("INSERT INTO log_events VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
        wall = (evs[-1]["t"] - evs[0]["t"]) if len(evs) > 1 else None
        features(db, -aid, aid, srows, crow, gold, wall=wall, max_prompt=None, fm={}, basis="log")
        n += 1
        if n % 1000 == 0:
            db.commit()
            print(f"    logs {n}", flush=True)
    print(f"    {n} display logs parsed into log_events + attempt_features(basis='log')", flush=True)
