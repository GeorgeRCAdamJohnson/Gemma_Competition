"""Stage `traces`: ATIF traces -> traces, steps, tool_calls (full observations) and attempt_features.
Traces referenced by attempts are linked to the kept (unique) attempt; unreferenced traces (incl. old submission
folders outside Outputs/) become source='trace_only' attempts with unknown outcome."""
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from vfs import ROOT, SKIP

SCHEMA = """
CREATE TABLE traces (trace_id INTEGER PRIMARY KEY, trace_path TEXT UNIQUE, attempt_id INTEGER, schema_version TEXT,
  agent_name TEXT, n_steps INTEGER, n_tool_calls INTEGER, n_llm_calls INTEGER, total_prompt_tokens INTEGER,
  total_completion_tokens INTEGER, total_cached_tokens INTEGER, max_prompt_tokens INTEGER, first_ts REAL,
  last_ts REAL, wall_s REAL, authors TEXT, models TEXT, system_prompt_chars INTEGER, task_prompt_chars INTEGER,
  final_message TEXT, bytes INTEGER);
CREATE INDEX ix_tr_att ON traces(attempt_id);
CREATE TABLE steps (trace_id INTEGER, step_id INTEGER, source TEXT, author TEXT, event_type TEXT, model_name TEXT,
  ts REAL, elapsed_s REAL, message TEXT, message_chars INTEGER, prompt_tokens INTEGER, completion_tokens INTEGER,
  cached_tokens INTEGER, llm_call_count INTEGER, n_tool_calls INTEGER, PRIMARY KEY (trace_id, step_id));
CREATE TABLE tool_calls (trace_id INTEGER, step_id INTEGER, idx INTEGER, author TEXT, tool TEXT, args_json TEXT,
  filepath TEXT, command TEXT, cmd_kind TEXT, cmd_files TEXT, skill_name TEXT, skill_script TEXT, ts REAL,
  obs_ts REAL, latency_s REAL, obs_status TEXT, error_type TEXT, error_message TEXT, exit_code INTEGER,
  obs_chars INTEGER, truncated INTEGER, edit_strategy TEXT, edit_occurrences INTEGER, edit_diff TEXT,
  patch_size INTEGER, files_changed INTEGER, gate_verdict TEXT, is_edit INTEGER, edit_ok INTEGER,
  touches_gold INTEGER, repeat_of_idx INTEGER, obs_content TEXT, PRIMARY KEY (trace_id, idx));
CREATE INDEX ix_tc_tool ON tool_calls(tool, cmd_kind); CREATE INDEX ix_tc_file ON tool_calls(filepath);
CREATE TABLE attempt_features (trace_id INTEGER PRIMARY KEY, attempt_id INTEGER, basis TEXT,
  n_steps INTEGER, n_calls INTEGER, n_read_file INTEGER, n_run_command INTEGER, n_edit_file INTEGER,
  n_write_file INTEGER, n_skill INTEGER, n_get_status INTEGER, n_submit INTEGER, n_other_tool INTEGER,
  n_grep INTEGER, n_sed INTEGER, n_cat INTEGER, n_find_ls INTEGER, n_pytest INTEGER, n_script_write INTEGER,
  n_failed_calls INTEGER, n_repeat_calls INTEGER, n_edit_ok INTEGER, n_edit_fail INTEGER,
  first_edit_idx INTEGER, first_edit_file TEXT, first_edit_gold INTEGER, edited_files TEXT, n_edited_files INTEGER,
  edited_any_gold INTEGER, n_gold_touches INTEGER, saw_gold_before_first_edit INTEGER, distinct_files_read INTEGER,
  calls_before_first_edit INTEGER, s_before_first_edit REAL,
  n_fixer_calls INTEGER, n_verifier_calls INTEGER, n_tester_calls INTEGER, n_iterations INTEGER, n_retry_msgs INTEGER,
  gate_accepted INTEGER, gate_rejected INTEGER, gate_last TEXT, max_prompt_tokens INTEGER, total_prompt_tokens INTEGER,
  total_completion_tokens INTEGER, thinking_chars INTEGER, wall_s REAL, last_author TEXT, last_event_type TEXT,
  tool_sequence TEXT);
CREATE INDEX ix_af_att ON attempt_features(attempt_id);
"""

CMD_KINDS = [
    ("script_write", re.compile(r"<<\s*['\"]?\w+|cat\s+>|tee\s|python3?\s+-\s|>\s*\S+\.py\b")),
    ("pytest", re.compile(r"\bpytest\b|-m\s+pytest|unittest")),
    ("grep", re.compile(r"\b(grep|rg|ag|egrep|git\s+grep)\b")),
    ("sed", re.compile(r"\bsed\s+-n\b|\bawk\b")),
    ("cat", re.compile(r"\b(cat|head|tail|nl|less|more)\b")),
    ("find_ls", re.compile(r"\b(find|ls|tree|du)\b")),
    ("git", re.compile(r"\bgit\b")),
    ("python", re.compile(r"\bpython3?\b")),
    ("pip", re.compile(r"\bpip3?\b")),
]
PYFILE = re.compile(r"([\w./-]+\.py)\b")
EDIT_TOOLS = {"edit_file", "write_file"}


def norm(f):
    if not f:
        return f
    f = str(f).replace("\\", "/")
    for pre in ("/workspace/", "workspace/", "./"):
        if f.startswith(pre):
            f = f[len(pre):]
    return f.lstrip("/")


def cmd_kind(c):
    for k, rx in CMD_KINDS:
        if rx.search(c):
            return k
    return "other"


def parse_obs(content):
    if isinstance(content, dict):
        return content
    if isinstance(content, str) and content[:1] == "{":
        try:
            return json.loads(content)
        except Exception:
            return {}
    return {}


def ingest_trace(db, tid, path, raw, attempt_id, gold):
    d = json.loads(raw)
    steps = d.get("steps") or []
    fm = d.get("final_metrics") or {}
    srows, crow = [], []
    seen_calls, authors, models = {}, Counter(), Counter()
    idx = 0
    max_prompt = 0
    first_ts = last_ts = None
    sys_chars = task_chars = 0
    final_msg = None
    for s in steps:
        ex = s.get("extra") or {}
        author, ev, ts = ex.get("author"), ex.get("event_type"), ex.get("timestamp")
        m = s.get("metrics") or {}
        msg = s.get("message")
        msg = msg if isinstance(msg, str) else (json.dumps(msg) if msg is not None else None)
        tcs = s.get("tool_calls") or []
        srows.append((tid, s.get("step_id"), s.get("source"), author, ev, s.get("model_name"), ts, ex.get("elapsed_s"),
                      msg, len(msg) if msg else 0, m.get("prompt_tokens"), m.get("completion_tokens"),
                      m.get("cached_tokens"), s.get("llm_call_count"), len(tcs)))
        if author:
            authors[author] += 1
        if s.get("model_name"):
            models[s["model_name"]] += 1
        max_prompt = max(max_prompt, m.get("prompt_tokens") or 0)
        if ts:
            first_ts = ts if first_ts is None else min(first_ts, ts)
            last_ts = ts if last_ts is None else max(last_ts, ts)
        if ev == "system_instruction" and msg:
            sys_chars = len(msg)
        if ev == "task_prompt" and msg:
            task_chars = len(msg)
        if ev == "final" and msg:
            final_msg = msg[:4000]
        obs = s.get("observation") or {}
        content = obs.get("content")
        o = parse_obs(content)
        obs_ts = (obs.get("extra") or {}).get("timestamp")
        for t in tcs:
            a = t.get("arguments") or {}
            a = a if isinstance(a, dict) else {"_raw": a}
            tool = t.get("function_name")
            te = t.get("extra") or {}
            fp = norm(a.get("filepath") or a.get("file_path") or a.get("path"))
            cmd = a.get("command") if isinstance(a.get("command"), str) else None
            ck = cmd_kind(cmd) if cmd else None
            cfiles = sorted({norm(x) for x in PYFILE.findall(cmd)}) if cmd else []
            sk = a.get("skill_name")
            out = (o.get("stdout") or "") if isinstance(o.get("stdout"), str) else ""
            verdict = ("ACCEPTED" if "ACCEPTED" in out else "REJECTED" if "REJECTED" in out else None) \
                if tool == "run_skill_script" else None
            key = (tool, json.dumps(a, sort_keys=True, default=str))
            rep = seen_calls.get(key)
            seen_calls.setdefault(key, idx)
            raw_status = o.get("status") if isinstance(o.get("status"), str) else None
            # normalise: tools report ok / success / error; plain-text bodies are harness errors
            # ("Invoking `edit_file()` failed as the following mandatory input ...") or unparsed output
            if raw_status in ("ok", "success"):
                status = "ok"
            elif raw_status == "error":
                status = "error"
            elif isinstance(content, str) and re.search(r"^Invoking `\w+\(\)` failed|^Error|Traceback|not found", content[:300]):
                status = "error"
            else:
                status = "unknown"
            is_edit = int(tool in EDIT_TOOLS or ck == "script_write")
            files = [fp] if fp else cfiles
            touches = int(bool(gold) and any(f in gold for f in files if f))
            cstr = content if isinstance(content, str) else json.dumps(content) if content is not None else None
            crow.append((tid, s.get("step_id"), idx, te.get("author") or author, tool,
                         json.dumps(a, default=str)[:20000], fp, cmd[:4000] if cmd else None, ck,
                         json.dumps(cfiles) if cfiles else None, sk, norm(a.get("file_path")) if sk else None,
                         te.get("timestamp") or ts, obs_ts,
                         (obs_ts - (te.get("timestamp") or ts)) if obs_ts and (te.get("timestamp") or ts) else None,
                         status, o.get("error_type"),
                         (o.get("error_message") or o.get("error") or
                          (cstr[:300] if status == "error" and raw_status is None and cstr else None)),
                         o.get("exit_code") if isinstance(o.get("exit_code"), int) else None,
                         len(cstr) if cstr else 0, int(bool(o.get("is_truncated"))), o.get("strategy"),
                         o.get("occurrences") if isinstance(o.get("occurrences"), int) else None,
                         (o.get("diff") or None) if isinstance(o.get("diff"), str) else None,
                         o.get("patch_size") if isinstance(o.get("patch_size"), int) else None,
                         o.get("files_changed") if isinstance(o.get("files_changed"), int) else None,
                         verdict, is_edit, int(is_edit and status == "ok"), touches, rep,
                         cstr if len(tcs) == 1 else None))  # an observation belongs to a step; split only if 1 call
            idx += 1
    db.execute("INSERT INTO traces VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
        tid, path, attempt_id, d.get("schema_version"), (d.get("agent") or {}).get("name"), len(steps), idx,
        sum(s.get("llm_call_count") or 0 for s in steps), fm.get("total_prompt_tokens"),
        fm.get("total_completion_tokens"), fm.get("total_cached_tokens"), max_prompt, first_ts, last_ts,
        (last_ts - first_ts) if first_ts and last_ts else None, json.dumps(dict(authors)), json.dumps(dict(models)),
        sys_chars, task_chars, final_msg, len(raw)))
    db.executemany("INSERT OR IGNORE INTO steps VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", srows)
    db.executemany("INSERT INTO tool_calls VALUES (" + ",".join("?" * 32) + ")", crow)
    features(db, tid, attempt_id, srows, crow, gold, wall=(last_ts - first_ts) if first_ts and last_ts else None,
             max_prompt=max_prompt, fm=fm)


def features(db, tid, attempt_id, srows, crow, gold, wall, max_prompt, fm, basis="trace"):
    # crow column positions
    AUTH, TOOL, FP, CK, CF, TS, ST, VER, ISE, EOK, TG, REP = 3, 4, 6, 8, 9, 12, 15, 26, 27, 28, 29, 30
    tools = Counter(c[TOOL] for c in crow)
    kinds = Counter(c[CK] for c in crow if c[CK])
    edits = [c for c in crow if c[EOK]]
    first = edits[0] if edits else None
    fe_file = None
    if first:
        fe_file = first[FP] or (json.loads(first[CF])[0] if first[CF] else None)
    before = crow[: first[2]] if first else crow
    files_read = {c[FP] for c in crow if c[TOOL] == "read_file" and c[FP]}
    edited = []
    for c in edits:
        f = c[FP] or (json.loads(c[CF])[0] if c[CF] else None)
        if f and f not in edited:
            edited.append(f)
    authors = [c[AUTH] for c in crow]
    iters = sum(1 for i, a in enumerate(authors) if a == "verifier" and (i == 0 or authors[i - 1] != "verifier"))
    retry = sum(1 for s in srows if s[8] and s[2] in ("user", "system") and "RETRY" in s[8])
    verdicts = [c[VER] for c in crow if c[VER]]
    ts0 = srows[0][6] if srows and srows[0][6] else None
    seq = " ".join((c[CK] or c[TOOL] or "?")[:6] for c in crow)[:2000]
    db.execute("INSERT OR REPLACE INTO attempt_features VALUES (" + ",".join("?" * 50) + ")", (
        tid, attempt_id, basis, len(srows), len(crow), tools["read_file"], tools["run_command"], tools["edit_file"],
        tools["write_file"], tools["run_skill_script"], tools["get_status"], tools["submit_patch"],
        sum(v for k, v in tools.items() if k not in ("read_file", "run_command", "edit_file", "write_file",
                                                    "run_skill_script", "get_status", "submit_patch")),
        kinds["grep"], kinds["sed"], kinds["cat"], kinds["find_ls"], kinds["pytest"], kinds["script_write"],
        sum(1 for c in crow if c[ST] == "error"), sum(1 for c in crow if c[REP] is not None),
        len(edits), sum(1 for c in crow if c[ISE] and not c[EOK]),
        first[2] if first else None, fe_file, (int(fe_file in gold) if fe_file and gold else None),
        json.dumps(edited), len(edited), int(any(f in gold for f in edited)) if gold else None,
        sum(c[TG] for c in crow), int(any(c[TG] for c in before)) if gold else None, len(files_read),
        len(before) if first else None, (first[TS] - ts0) if first and first[TS] and ts0 else None,
        authors.count("fixer"), authors.count("verifier"), authors.count("tester"), iters, retry,
        verdicts.count("ACCEPTED"), verdicts.count("REJECTED"), verdicts[-1] if verdicts else None,
        max_prompt, fm.get("total_prompt_tokens"), fm.get("total_completion_tokens"),
        sum(s[9] for s in srows if s[2] == "agent"), wall, authors[-1] if authors else None,
        srows[-1][4] if srows else None, seq))


def run(db, vfs):
    db.executescript(SCHEMA)
    gold_of = {t: {g for g in json.loads(gf) if "test" not in g} for t, gf in db.execute("SELECT task, gold_files FROM tasks")}
    # trace path -> kept attempt id
    link = {}
    for path, aid, dup in db.execute("SELECT trace_path, id, dup_of FROM attempts WHERE trace_path IS NOT NULL ORDER BY id"):
        keep = dup or aid
        if path not in link or dup is None:
            link[path] = keep
    all_traces = [vp for vp in vfs.files if re.search(r"/traces/trace_[\w-]+\.json$|!/.*trace_[\w-]+\.json$", vp)]
    outside = [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("trace_*.json")
               if not SKIP.search(str(p)) and p.relative_to(ROOT).parts[0] != "Outputs"]
    tid = 0
    trace_only = 0
    for vp in sorted(set(all_traces) | set(outside)):
        raw = vfs.read(vp) if vfs.exists(vp) else (ROOT / vp).read_bytes()
        task = re.search(r"trace_([\w-]+)\.json$", vp).group(1)
        aid = link.get(vp)
        if aid is None:
            from build import exp_of
            exp = exp_of(vp)
            cur = db.execute("INSERT INTO attempts (exp, source, source_path, task, model, model_basis, verified_basis,"
                             " trace_path, fingerprint, fp_noround) VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (exp, "trace_only", vp, task, None, None, "outcome unknown (trace only)", vp,
                              "trace:" + hashlib.sha1(vp.encode()).hexdigest()[:12], None))
            aid = cur.lastrowid
            trace_only += 1
        tid += 1
        try:
            ingest_trace(db, tid, vp, raw, aid, gold_of.get(task, set()))
        except Exception as e:  # keep going; record the failure
            db.execute("INSERT INTO traces (trace_id, trace_path, attempt_id, final_message, bytes) VALUES (?,?,?,?,?)",
                       (tid, vp, aid, f"PARSE ERROR: {type(e).__name__}: {e}"[:500], len(raw)))
        if tid % 500 == 0:
            db.commit()
            print(f"    traces {tid}", flush=True)
    # model for trace-only attempts from the trace's dominant model
    db.execute("""UPDATE attempts SET model = (SELECT json_extract(t.models, '$') FROM traces t WHERE t.attempt_id = attempts.id)
                  WHERE source = 'trace_only'""")
    print(f"    {tid} traces ingested ({trace_only} trace-only attempts)", flush=True)
