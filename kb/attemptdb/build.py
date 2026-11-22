"""Build kb/attempts.sqlite -- the project intel database. See kb/attemptdb/README.md.

Stages (each in its own module, all read-only on the repo):
  core     (this file)   attempts from task_results / lora_progress / summaries, incl. tar archives; experiments,
                         registrations, agent bundles, tasks, submissions; dedupe
  traces   deep_traces   traces -> steps, tool_calls (full observations), attempt_features; trace-only attempts
  logs     deep_logs     agent display logs -> log_events (+ attempt_features where no trace exists)
  vllm     deep_vllm     vLLM server logs -> servers, 10 s metrics, errors, http counts; attempt <-> lane load
  crawl    crawl         notebooks, kernel-metadata, registrations, receipts, adapters, training artifacts, run logs,
                         docs -> documents (+ FTS5), kernels, adapters
  gemmalog gemmalog      GEMMA_EXPERIMENT_LOG.md -> sections (+ FTS5) and entity mentions
  catalog  catalog       bundle diffs vs pack 1, experiment signatures (repeat detection)

usage: python kb/attemptdb/build.py [--out kb/attempts.sqlite] [--stages core,traces,...]
"""
import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vfs import ROOT, VFS, parent, parts_after_outputs  # noqa: E402

OUT = ROOT / "Outputs"
STRUCT = re.compile(r"^(results|lora_results|shard\d+|node\d+|round_\d+|run_\d+|pass_\d+|logs|traces|patches|"
                    r"test_outputs|priority|kaggle_output\w*)$")
ROUND = re.compile(r"^(?:round|run|pass)_?(\d+)$")
TASKDIR = re.compile(r"^(fastapi|rich|requests|httpx)_\d+$")
MODEL_RE = re.compile(rb'"model_name":\s*"([^"]+)"')

SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE experiments (exp TEXT PRIMARY KEY, path TEXT, slug TEXT, version INTEGER, platform_status TEXT,
  registration_path TEXT, notebook_sha256 TEXT, bundle_sha256 TEXT, tasks_sha256 TEXT, adapter_sha256 TEXT,
  adapter_dataset TEXT, n_registered_tasks INTEGER, report_path TEXT, report_complete INTEGER, report_json TEXT,
  registration_json TEXT);
CREATE TABLE arms (exp TEXT, arm TEXT, arm_hash TEXT, PRIMARY KEY (exp, arm));
CREATE TABLE tasks (task TEXT PRIMARY KEY, repo TEXT, gold_files TEXT, n_gold_src INTEGER, statement_chars INTEGER,
  created_at TEXT, problem_statement TEXT, gold_patch TEXT, test_patch TEXT);
CREATE TABLE submissions (ref INTEGER PRIMARY KEY, date TEXT, description TEXT, status TEXT, score REAL, error TEXT,
  url TEXT, kernel_slug TEXT, track TEXT);
CREATE TABLE attempts (id INTEGER PRIMARY KEY, exp TEXT, source TEXT, source_path TEXT, arm TEXT, round INTEGER,
  node INTEGER, shard INTEGER, task TEXT, repo TEXT, model TEXT, model_basis TEXT,
  resolved INTEGER, verified INTEGER, verified_basis TEXT, error TEXT, error_class TEXT, test_exit_code INTEGER,
  patch_chars INTEGER, duration_s REAL, tool_calls INTEGER, llm_calls INTEGER,
  graded INTEGER, real_grade INTEGER, routing_violations INTEGER, adapter_observed INTEGER,
  trace_path TEXT, patch_path TEXT, test_output_path TEXT, log_path TEXT, test_output_chars INTEGER,
  fingerprint TEXT, fp_noround TEXT, dup_of INTEGER);
CREATE INDEX ix_att_task ON attempts(task); CREATE INDEX ix_att_exp ON attempts(exp, arm, round);
CREATE INDEX ix_att_fp ON attempts(fingerprint); CREATE INDEX ix_att_fpn ON attempts(fp_noround, exp);
CREATE INDEX ix_att_trace ON attempts(trace_path);
CREATE VIEW attempts_unique AS SELECT * FROM attempts WHERE dup_of IS NULL;
CREATE VIEW pass_summary AS SELECT exp, arm, round, node, COUNT(*) AS n, SUM(resolved) AS resolved,
  SUM(verified) AS verified, SUM(error_class = 'overflow') AS overflows, ROUND(AVG(duration_s), 1) AS mean_s
  FROM attempts_unique GROUP BY exp, arm, round, node;
CREATE VIEW task_rates AS SELECT task, model, COUNT(*) AS n, SUM(resolved) AS resolved,
  ROUND(1.0 * SUM(resolved) / COUNT(*), 3) AS rate FROM attempts_unique GROUP BY task, model;
CREATE TABLE bundles (bundle_id INTEGER PRIMARY KEY, path TEXT UNIQUE, sha12 TEXT, name TEXT, agent_class TEXT,
  max_iterations INTEGER, n_sub_agents INTEGER, skills TEXT, models TEXT, max_tool_calls INTEGER,
  max_time_minutes REAL, max_turns INTEGER, temperature REAL, prompt_chars INTEGER, n_files INTEGER);
CREATE TABLE bundle_files (bundle_id INTEGER, relpath TEXT, sha256 TEXT, bytes INTEGER, content TEXT,
  PRIMARY KEY (bundle_id, relpath));
CREATE INDEX ix_bf_sha ON bundle_files(sha256);
CREATE TABLE registered_files (exp TEXT, role TEXT, relpath TEXT, sha256 TEXT);
CREATE VIEW exp_bundles AS
  SELECT r.exp, r.role, b.bundle_id, b.path, b.sha12, COUNT(*) AS matched,
    (SELECT COUNT(*) FROM registered_files r2 WHERE r2.exp = r.exp AND r2.role = r.role) AS registered
  FROM registered_files r JOIN bundle_files f ON f.relpath = r.relpath AND f.sha256 = r.sha256
  JOIN bundles b ON b.bundle_id = f.bundle_id GROUP BY r.exp, r.role, b.bundle_id
  HAVING matched = registered;
"""


def load_json(vfs, vp):
    try:
        return json.loads(vfs.text(vp).lstrip("\ufeff"))
    except Exception:
        return None


def error_class(err):
    e = (err or "").lower()
    if not e:
        return None
    if "contextwindow" in e or "maximum context" in e:
        return "overflow"
    if "timeout" in e or "timed out" in e:
        return "timeout"
    if "failed to load skill" in e or "invalid yaml" in e:
        return "bundle_load"
    if "sandbox" in e:
        return "sandbox"
    return "other"


# Colab A/B layouts <dir>/<tag>/<arm>/round_N/...: drive_ab_runs = copy of Drive gemma_fasteval/ab_runs (traces);
# ab_logs = the earlier log-only pull. Same tag in both -> attempts dedupe across them (arm + round in the key).
TAGGED = {"drive_ab_runs": "drive", "ab_logs": "ablogs"}


def exp_of(vp):
    p = parts_after_outputs(vp)
    if vp.startswith("Outputs/"):
        if p[0] in TAGGED and len(p) > 2:
            return f"{TAGGED[p[0]]}_{p[1]}"  # one experiment per Colab A/B tag
        return p[0]
    return vp.split("/")[0]  # e.g. submit_v7_d, local_eval


def path_context(vp):
    """exp, arm, round, node, shard from a result-file vpath (dirs only)."""
    exp = exp_of(vp)
    parts = parts_after_outputs(vp)[:-1] if vp.startswith("Outputs/") else vp.split("!/")[0].split("/")[:-1]
    parts = parts[2:] if parts and parts[0] in TAGGED else parts[1:]  # drop exp (and the tag level)
    rnd = node = shard = arm = None
    for p in parts:
        if m := ROUND.match(p):
            rnd = int(m.group(1))
        elif m := re.match(r"^node(\d+)$", p):
            node = int(m.group(1))
        elif m := re.match(r"^shard(\d+)$", p):
            shard = int(m.group(1))
        elif not STRUCT.match(p) and not TASKDIR.match(p):
            arm = p
    return exp, arm, rnd, node, shard


def fingerprint(task, resolved, patch, dur, calls, llm, rnd, arm=None):
    # round + arm + 0.01 s duration are in the key: short deterministic runs collide otherwise
    key = (f"{task}|{rnd}|{arm}|{int(bool(resolved))}|{patch}|{'' if dur is None else round(float(dur), 2)}|"
           f"{calls}|{llm}")
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def trace_model(vfs, vp):
    try:
        m = MODEL_RE.search(vfs.read(vp, 20000))
        return m.group(1).decode() if m else None
    except Exception:
        return None


def index_bundles(db):
    """Every directory holding an agent.yaml = one agent bundle (file contents stored for diffing)."""
    import yaml

    class L(yaml.SafeLoader):
        pass
    L.add_constructor("!include", lambda loader, node: f"!include {loader.construct_scalar(node)}")

    def y(p):
        try:
            return yaml.load(p.read_text(encoding="utf-8", errors="replace"), Loader=L) or {}
        except Exception:
            return {}

    skip = re.compile(r"[\\/](\.git|node_modules|venv|\.venv|site-packages)[\\/]")
    roots = sorted(p.parent for p in ROOT.rglob("agent.yaml") if not skip.search(str(p)))
    roots = [r for r in roots if not any(o != r and o in r.parents for o in roots)]
    for d in roots:
        files = sorted(p for p in d.rglob("*") if p.is_file() and "__pycache__" not in p.parts)
        if len(files) > 400:
            continue
        blobs = {p.relative_to(d).as_posix(): p.read_bytes() for p in files}
        sha12 = hashlib.sha1(b"".join(blobs[n] for n in sorted(blobs))).hexdigest()[:12]
        top = y(d / "agent.yaml")
        ev = y(d / "eval_config.yaml")
        ev = ev.get("evaluation", ev) if isinstance(ev, dict) else {}
        subs = [y(d / s["config_path"]) for s in top.get("sub_agents") or [] if isinstance(s, dict) and s.get("config_path")]
        agents = [top] + subs
        models = sorted({a.get("model") for a in agents if isinstance(a, dict) and a.get("model")})
        skills = sorted({s for a in agents if isinstance(a, dict) for s in (a.get("skills") or []) if isinstance(s, str)})
        temps = [float(m.group(1)) for p in d.rglob("*.yaml")
                 for m in [re.search(r"^\s*temperature:\s*([\d.]+)", p.read_text(encoding="utf-8", errors="replace"), re.M)] if m]
        prompt_chars = sum(len(b) for n, b in blobs.items() if n.endswith(".md") and "prompts" in n)
        cur = db.execute("INSERT INTO bundles (path, sha12, name, agent_class, max_iterations, n_sub_agents, skills, models,"
                         " max_tool_calls, max_time_minutes, max_turns, temperature, prompt_chars, n_files)"
                         " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                         (d.relative_to(ROOT).as_posix(), sha12, top.get("name"), top.get("agent_class"),
                          top.get("max_iterations"), len(subs), json.dumps(skills), json.dumps(models),
                          ev.get("max_tool_calls"), ev.get("max_time_minutes"), ev.get("max_turns"),
                          temps[0] if len(set(temps)) == 1 else None, prompt_chars, len(blobs)))
        bid = cur.lastrowid
        db.executemany("INSERT INTO bundle_files VALUES (?,?,?,?,?)",
                       [(bid, n, hashlib.sha256(b).hexdigest(), len(b),
                         b.decode("utf-8", "replace") if len(b) < 200_000 and not n.endswith((".safetensors", ".bin")) else None)
                        for n, b in blobs.items()])


def core(db, vfs):
    db.executescript(SCHEMA)
    # tasks (full statement + gold patch + test patch, for in-DB analysis)
    for line in (ROOT / "Outputs/e4b_variance3/tasks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line)
            gold = re.findall(r"^\+\+\+ b/(\S+)", t["patch"], re.M)
            db.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)", (t["instance_id"], t["repo"], json.dumps(gold),
                       sum("test" not in g for g in gold), len(t["problem_statement"]), t.get("created_at"),
                       t["problem_statement"], t["patch"], t["test_patch"]))
    repo_of = dict(db.execute("SELECT task, repo FROM tasks"))

    for s in load_json(vfs, "Outputs/_submissions.json") or []:
        url = s.get("url") or ""
        slug = (re.search(r"/code/([^?]+)", url) or [None, None])[1]
        desc = (s.get("desc") or "").lower()
        track = "E4B" if ("e4b" in url.lower() or desc.startswith("e4b")) else "31B/main"
        db.execute("INSERT OR REPLACE INTO submissions VALUES (?,?,?,?,?,?,?,?,?)",
                   (s["ref"], s.get("date"), s.get("desc"), s.get("status"),
                    float(s["score"]) if s.get("score") not in (None, "") else None, s.get("err"), url, slug, track))

    # experiments
    meta_names = ("task_results.jsonl", "progress.json", "variance_ab.json", "lora_progress.json", "registration.json",
                  "result_report.json")
    exps = sorted({exp_of(vp) for vp in vfs.files if vp.rsplit("/", 1)[-1] in meta_names and vp.startswith("Outputs/")
                   and vp.count("/") >= 2})
    for exp in exps:
        regs = sorted(vp for vp in vfs.glob_name("registration.json") if vp.startswith(f"Outputs/{exp}/"))
        reps = sorted(vp for vp in vfs.glob_name("result_report.json") if vp.startswith(f"Outputs/{exp}/"))
        reg = load_json(vfs, regs[0]) if regs else None
        rep = load_json(vfs, reps[0]) if reps else None
        reg = reg if isinstance(reg, dict) else {}
        rep = rep if isinstance(rep, dict) else {}
        summ = rep.get("experiment_summary") or {}
        db.execute("INSERT INTO experiments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            exp, f"Outputs/{exp}", reg.get("slug") or rep.get("slug"), rep.get("version"), rep.get("platform_status"),
            regs[0] if regs else None, reg.get("notebook_sha256"), reg.get("bundle_sha256"), reg.get("tasks_sha256"),
            reg.get("adapter_sha256"), reg.get("adapter_dataset"), len(reg.get("task_ids") or []) or None,
            reps[0] if reps else None, None if not summ else int(bool(summ.get("complete"))),
            json.dumps(summ)[:50000] if summ else None, json.dumps(reg)[:50000] if reg else None))
        for arm, h in (reg.get("arm_hashes") or {}).items():
            db.execute("INSERT OR REPLACE INTO arms VALUES (?,?,?)", (exp, arm, h))
        for role in ("baseline", "treatment"):
            for rp, h in (reg.get(f"{role}_file_hashes") or {}).items():
                db.execute("INSERT INTO registered_files VALUES (?,?,?,?)", (exp, role, rp, h))
    index_bundles(db)

    lora = {}
    for lp in vfs.glob_name("lora_progress.json"):
        for rec in (load_json(vfs, lp) or {}).get("tasks", []):
            rd = (rec.get("result_dir") or "").replace("\\", "/")
            lora[(exp_of(lp), "/".join(rd.split("/")[-4:]))] = rec
    node_arm = {}
    for va in vfs.glob_name("variance_ab.json"):
        for p in (load_json(vfs, va) or {}).get("passes", []):
            node_arm[(exp_of(va), p.get("node"), p.get("run"))] = p.get("arm")

    def row(**k):
        return k

    rows = []
    for tr in vfs.glob_name("task_results.jsonl"):
        exp, arm, rnd, node, shard = path_context(tr)
        if arm is None and node is not None:
            arm = node_arm.get((exp, node, rnd))
        d = parent(tr)
        for line in vfs.text(tr).splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            task = r.get("instance_id")
            if not task:
                continue

            def art(sub, names, d=d):
                for n in names:
                    if vfs.exists(f"{d}/{sub}/{n}"):
                        return f"{d}/{sub}/{n}"
                return None
            trace = art("traces", [f"trace_{task}.json", f"{task}.json"])
            patch, tout, log = art("patches", [f"{task}.patch"]), art("test_outputs", [f"{task}.log"]), art("logs", [f"{task}.log"])
            lrec = lora.get((exp, "/".join(d.replace("!/", "/").split("/")[-4:])))
            if lrec:
                arm, rnd = lrec.get("arm") or arm, lrec.get("round") or rnd
                node = node if node is not None else lrec.get("gpu")  # GPU lane -> joins to vllm_gpuN.log
            model, basis = (trace_model(vfs, trace), "trace") if trace else (None, None)
            if not model:
                model, basis = ("gemma-4-31b" if "31b" in tr.lower() else "gemma-4-e4b(assumed)"), "path"
            err = r.get("error")
            tchars = vfs.size(tout) if tout else None
            routing = (lrec or {}).get("routing") or {}
            viol = len(routing.get("violations") or []) if routing else None
            real = (lrec or {}).get("real_grade")
            if tout is None:
                ver, vb = None, "no test output on disk"
            else:
                ver = int(bool(r.get("resolved")) and not err and r.get("test_exit_code") == 0 and (tchars or 0) > 0
                          and viol in (None, 0) and real in (None, True))
                vb = "task_results+test_output" + ("+routing" if routing else "")
            rows.append(row(exp=exp, source="task_results", source_path=tr, arm=arm, round=rnd, node=node,
                            shard=shard, task=task, repo=r.get("repo") or repo_of.get(task), model=model, model_basis=basis,
                            resolved=int(bool(r.get("resolved"))), verified=ver, verified_basis=vb,
                            error=(str(err)[:500] if err else None), error_class=error_class(err),
                            test_exit_code=r.get("test_exit_code"), patch_chars=r.get("agent_patch_size"),
                            duration_s=r.get("duration_seconds"), tool_calls=r.get("tool_calls"),
                            llm_calls=r.get("total_llm_calls"), graded=(lrec or {}).get("graded"), real_grade=real,
                            routing_violations=viol,
                            adapter_observed=routing.get("fixer_adapter_observed") if routing else None,
                            trace_path=trace, patch_path=patch, test_output_path=tout, log_path=log,
                            test_output_chars=tchars))

    for lp in vfs.glob_name("lora_progress.json"):
        exp = exp_of(lp)
        base = parent(lp)
        for rec in (load_json(vfs, lp) or {}).get("tasks", []):
            res = rec.get("result") or {}
            task = rec.get("id") or res.get("instance_id")
            rnd = rec.get("round")
            tail = "/".join((rec.get("result_dir") or "").replace("\\", "/").split("/")[-4:])
            local = next((c for c in (f"{base}/{tail}", f"{parent(base)}/results/{tail}")
                          if vfs.exists(f"{c}/task_results.jsonl") or vfs.exists(f"{c}/traces/trace_{task}.json")), None)
            find = lambda sub, n, local=local: f"{local}/{sub}/{n}" if local and vfs.exists(f"{local}/{sub}/{n}") else None
            trace, patch = find("traces", f"trace_{task}.json"), find("patches", f"{task}.patch")
            tout, log = find("test_outputs", f"{task}.log"), find("logs", f"{task}.log")
            routing = rec.get("routing") or {}
            viol = len(routing.get("violations") or []) if routing else None
            err = res.get("error") or rec.get("result_error")
            ok_run = rec.get("status") == "completed" and rec.get("rc") == 0
            ver = int(bool(res.get("resolved")) and not err and ok_run and res.get("test_exit_code") == 0
                      and bool(rec.get("graded")) and rec.get("real_grade") is not False and viol in (None, 0))
            model = trace_model(vfs, trace) if trace else None
            rows.append(row(exp=exp, source="lora_progress", source_path=lp, arm=rec.get("arm"), round=rnd,
                            node=rec.get("gpu"), shard=None, task=task, repo=res.get("repo") or repo_of.get(task),
                            model=model or "gemma-4-e4b(assumed)", model_basis="trace" if model else "path",
                            resolved=int(bool(res.get("resolved"))), verified=ver,
                            verified_basis="lora_progress (status, rc, graded, real_grade, routing)",
                            error=(str(err)[:500] if err else None),
                            error_class=error_class(err) or (None if ok_run else f"run_{rec.get('status')}"),
                            test_exit_code=res.get("test_exit_code"), patch_chars=res.get("agent_patch_size"),
                            duration_s=res.get("duration_seconds"), tool_calls=res.get("tool_calls"),
                            llm_calls=res.get("total_llm_calls"), graded=rec.get("graded"), real_grade=rec.get("real_grade"),
                            routing_violations=viol,
                            adapter_observed=routing.get("fixer_adapter_observed") if routing else None,
                            trace_path=trace, patch_path=patch, test_output_path=tout, log_path=log,
                            test_output_chars=vfs.size(tout) if tout else None))

    for sp in vfs.glob_name("progress.json") + vfs.glob_name("variance_ab.json"):
        d = load_json(vfs, sp)
        if not isinstance(d, dict):
            continue
        exp = exp_of(sp)
        for p in d.get("passes", []):
            for x in p.get("rows") or []:
                rows.append(row(exp=exp, source="summary", source_path=sp, arm=p.get("arm"),
                                round=p.get("round", p.get("run")), node=p.get("node"), shard=None, task=x.get("id"),
                                repo=repo_of.get(x.get("id")),
                                model="gemma-4-31b" if "31b" in exp.lower() else "gemma-4-e4b(assumed)", model_basis="path",
                                resolved=int(bool(x.get("resolved"))), verified=None,
                                verified_basis="summary row (no artifacts)", error=x.get("err") or None,
                                error_class=error_class(x.get("err")), test_exit_code=None, patch_chars=x.get("patch"),
                                duration_s=x.get("dur"), tool_calls=x.get("calls"), llm_calls=x.get("llm"), graded=None,
                                real_grade=None, routing_violations=None, adapter_observed=None, trace_path=None,
                                patch_path=None, test_output_path=None, log_path=None, test_output_chars=None))

    for r in rows:
        r["fingerprint"] = fingerprint(r["task"], r["resolved"], r["patch_chars"], r["duration_s"], r["tool_calls"],
                                       r["llm_calls"], r["round"], r["arm"])
        r["fp_noround"] = fingerprint(r["task"], r["resolved"], r["patch_chars"], r["duration_s"], r["tool_calls"],
                                      r["llm_calls"], None, None)
    cols = list(rows[0])
    db.executemany(f"INSERT INTO attempts ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                   [tuple(r[c] for c in cols) for r in rows])
    dedupe(db)


def dedupe(db):
    db.executescript("""
    DROP TABLE IF EXISTS temp.keep; DROP TABLE IF EXISTS temp.r2;
    UPDATE attempts SET dup_of = NULL;
    CREATE TEMP TABLE keep AS SELECT fingerprint, (SELECT k.id FROM attempts k WHERE k.fingerprint = f.fingerprint
        ORDER BY CASE k.source WHEN 'task_results' THEN 0 WHEN 'lora_progress' THEN 1 WHEN 'summary' THEN 2 ELSE 3 END,
        (k.source_path LIKE '%!/%'), k.source_path, k.id LIMIT 1) AS id FROM (SELECT DISTINCT fingerprint FROM attempts) f;
    CREATE INDEX temp.ix_keep ON keep(fingerprint);
    UPDATE attempts SET dup_of = (SELECT id FROM keep WHERE keep.fingerprint = attempts.fingerprint)
      WHERE id <> (SELECT id FROM keep WHERE keep.fingerprint = attempts.fingerprint);
    CREATE TEMP TABLE r2 AS SELECT a.id AS id, MIN(k.id) AS keep_id, COUNT(*) AS c FROM attempts a JOIN attempts k
        ON k.fp_noround = a.fp_noround AND k.exp = a.exp AND k.round IS NOT NULL AND k.dup_of IS NULL
      WHERE a.round IS NULL AND a.dup_of IS NULL GROUP BY a.id;
    UPDATE attempts SET dup_of = (SELECT keep_id FROM r2 WHERE r2.id = attempts.id)
      WHERE id IN (SELECT id FROM r2 WHERE c = 1);
    """)


STAGES = ["core", "traces", "logs", "vllm", "crawl", "gemmalog", "catalog"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "kb" / "attempts.sqlite"))
    ap.add_argument("--stages", default=",".join(STAGES))
    a = ap.parse_args()
    out, stages = Path(a.out), a.stages.split(",")
    if "core" in stages and out.exists():
        out.unlink()
    db = sqlite3.connect(out)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=OFF")
    vfs = VFS(roots=("Outputs",))
    print(f"vfs: {len(vfs.files)} files ({len(vfs.tars)} result archives)", flush=True)
    timings = {}
    for st in STAGES:
        if st not in stages:
            continue
        t0 = time.time()
        if st == "core":
            core(db, vfs)
        else:
            mod = __import__({"traces": "deep_traces", "logs": "deep_logs", "vllm": "deep_vllm"}.get(st, st))
            mod.run(db, vfs)
        db.commit()
        timings[st] = round(time.time() - t0, 1)
        print(f"  stage {st:9s} {timings[st]:7.1f}s", flush=True)
    db.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    db.execute("INSERT OR REPLACE INTO meta VALUES ('built_at', ?)", (time.strftime("%Y-%m-%d %H:%M:%S"),))
    db.execute("INSERT OR REPLACE INTO meta VALUES ('stage_seconds', ?)", (json.dumps(timings),))
    db.commit()
    n, u = db.execute("SELECT COUNT(*), SUM(dup_of IS NULL) FROM attempts").fetchone()
    print(f"built {out.relative_to(ROOT).as_posix()}: {n} attempt rows, {u} unique")
    db.close()


if __name__ == "__main__":
    main()
