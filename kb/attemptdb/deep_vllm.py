"""Stage `vllm`: vLLM server logs -> vllm_servers (config), vllm_metrics (10 s engine stats), vllm_errors (timestamped;
context overflows with token counts), vllm_http (per-minute status counts), and attempt_server_load (each attempt's
lane load during its trace window). vLLM log lines carry 'MM-DD HH:MM:SS' without a year or zone; the year is taken
from the experiment's trace timestamps (UTC epoch) and the zone is assumed UTC (Kaggle containers). Untimestamped lines
(tracebacks, uvicorn access lines) inherit the last timestamp seen (<= ~10 s error)."""
import calendar
import hashlib
import json
import re
import time
from collections import Counter

from vfs import ROOT, SKIP

SCHEMA = """
CREATE TABLE vllm_servers (server_id INTEGER PRIMARY KEY, exp TEXT, path TEXT, lane INTEGER, sha12 TEXT,
  vllm_version TEXT, model TEXT, served_names TEXT, max_model_len INTEGER, tensor_parallel INTEGER, dtype TEXT,
  quantization TEXT, gpu_memory_utilization REAL, enable_lora INTEGER, max_lora_rank INTEGER, lora_modules TEXT,
  tool_call_parser TEXT, reasoning_parser TEXT, kv_cache_tokens INTEGER, kv_cache_gib REAL, max_concurrency REAL,
  init_engine_s REAL, first_ts REAL, last_ts REAL, n_requests_ok INTEGER, n_requests_bad INTEGER,
  n_overflow INTEGER, n_errors INTEGER, args_text TEXT, engine_config TEXT, warnings TEXT);
CREATE TABLE vllm_metrics (server_id INTEGER, ts REAL, prompt_tps REAL, gen_tps REAL, running INTEGER,
  waiting INTEGER, kv_usage REAL, prefix_hit REAL);
CREATE INDEX ix_vm ON vllm_metrics(server_id, ts);
CREATE TABLE vllm_errors (server_id INTEGER, ts REAL, kind TEXT, max_context INTEGER, requested_output INTEGER,
  input_tokens_at_least INTEGER, message TEXT);
CREATE INDEX ix_ve ON vllm_errors(server_id, ts);
CREATE TABLE vllm_http (server_id INTEGER, minute_ts REAL, status INTEGER, n INTEGER);
CREATE TABLE attempt_server_load (attempt_id INTEGER, server_id INTEGER, n_samples INTEGER, kv_avg REAL, kv_max REAL,
  running_avg REAL, running_max INTEGER, waiting_max INTEGER, gen_tps_avg REAL, prompt_tps_avg REAL,
  lane_overflows_in_window INTEGER, PRIMARY KEY (attempt_id, server_id));
"""
TS = re.compile(r"\b(INFO|WARNING|ERROR|DEBUG|CRITICAL) (\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)(?:\.\d+)? \[")
MET = re.compile(r"Avg prompt throughput: ([\d.]+) tokens/s, Avg generation throughput: ([\d.]+) tokens/s, "
                 r"Running: (\d+) reqs, (?:Swapped: \d+ reqs, )?(?:Pending|Waiting): (\d+) reqs, "
                 r"GPU KV cache usage: ([\d.]+)%(?:, Prefix cache hit rate: ([\d.]+)%)?")
OVF = re.compile(r"maximum context length is (\d+) tokens\. However, you requested (\d+) output tokens and your "
                 r"prompt contains at least (\d+) input tokens")
HTTP = re.compile(r'"(?:POST|GET) (\S+) HTTP/[\d.]+" (\d{3})')
EXC = re.compile(r"\b((?:vllm\.exceptions\.|torch\.)?\w*(?:Error|Exception))\b: (.{0,300})")


def g(rx, s, cast=str):
    m = re.search(rx, s)
    return cast(m.group(1).replace(",", "")) if m else None


def run(db, vfs):
    db.executescript(SCHEMA)
    years = {exp: time.gmtime(ts).tm_year for exp, ts in db.execute(
        "SELECT a.exp, MIN(t.first_ts) FROM traces t JOIN attempts a ON a.id = t.attempt_id "
        "WHERE t.first_ts > 1.6e9 GROUP BY a.exp")}
    cands = [vp for vp in vfs.files if re.search(r"vllm[^/]*\.(log|txt)$", vp.rsplit("/", 1)[-1], re.I)]
    cands += [p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*vllm*") if p.is_file() and p.suffix in (".log", ".txt")
              and not SKIP.search(str(p)) and p.relative_to(ROOT).parts[0] != "Outputs"]
    seen_sha = set()
    sid = 0
    for vp in sorted(set(cands)):
        raw = vfs.read(vp) if vfs.exists(vp) else (ROOT / vp).read_bytes()
        sha = hashlib.sha1(raw).hexdigest()[:12]
        if sha in seen_sha or b"vllm" not in raw.lower()[:200000]:
            continue
        seen_sha.add(sha)
        text = raw.decode("utf-8", "replace")
        from build import exp_of
        exp = exp_of(vp)
        year = years.get(exp) or time.gmtime((ROOT / vp.split("!/")[0]).stat().st_mtime).tm_year
        lane = g(r"gpu(\d+)", vp.rsplit("/", 1)[-1], int)
        sid += 1
        cur_ts, first_ts, mets, errs, http, warns = None, None, [], [], Counter(), Counter()
        cfg = dict(args="", engine="", lora=[])
        for line in text.splitlines():
            m = TS.search(line)
            if m:
                _, mo, dd, hh, mi, ss = m.groups()
                cur_ts = calendar.timegm((year, int(mo), int(dd), int(hh), int(mi), int(ss)))
                first_ts = first_ts or cur_ts
            if "Avg prompt throughput" in line and (mm := MET.search(line)):
                mets.append((sid, cur_ts, float(mm.group(1)), float(mm.group(2)), int(mm.group(3)), int(mm.group(4)),
                             float(mm.group(5)), float(mm.group(6)) if mm.group(6) else None))
            elif (mm := OVF.search(line)):
                errs.append((sid, cur_ts, "context_overflow", int(mm.group(1)), int(mm.group(2)), int(mm.group(3)), line[-400:]))
            elif (mm := HTTP.search(line)):
                if cur_ts:
                    http[(cur_ts // 60 * 60, int(mm.group(2)))] += 1
            elif "non-default args:" in line:
                cfg["args"] = line.split("non-default args:", 1)[1].strip()[:8000]
            elif "Initializing a V1 LLM engine" in line or "Initializing an LLM engine" in line:
                cfg["engine"] = line[:8000]
            elif "Loaded new LoRA adapter" in line:
                cfg["lora"].append(g(r"name '([^']+)'", line))
            elif "GPU KV cache size:" in line:
                cfg["kv"] = g(r"GPU KV cache size: ([\d,]+) tokens", line, int)
            elif "Maximum concurrency for" in line:
                cfg["conc"] = g(r"per request: ([\d.]+)x", line, float)
            elif "Available KV cache memory:" in line:
                cfg["kvgib"] = g(r"Available KV cache memory: ([\d.]+) GiB", line, float)
            elif "init engine" in line and "took" in line:
                cfg["init"] = g(r"took ([\d.]+) seconds", line, float)
            elif (" ERROR " in line or "Traceback" in line or "Error:" in line) and (mm := EXC.search(line)):
                if "maximum context length" not in line:
                    errs.append((sid, cur_ts, mm.group(1).split(".")[-1], None, None, None, line[-400:]))
            if " WARNING " in line:
                warns[re.sub(r"^.*?\] ", "", line)[:160]] += 1
        a, e = cfg["args"], cfg["engine"]
        db.execute("INSERT INTO vllm_servers VALUES (" + ",".join("?" * 31) + ")", (
            sid, exp, vp, lane, sha, g(r"engine \(v([\w.+-]+)\)", e) or g(r"vLLM API server version ([\w.+-]+)", text),
            g(r"model='([^']+)'", e) or g(r"'model': '([^']+)'", a), g(r"served_model_name=([^,]+)", e),
            g(r"max_seq_len=(\d+)", e, int) or g(r"'max_model_len': (\d+)", a, int),
            g(r"tensor_parallel_size=(\d+)", e, int), g(r"dtype=([\w.]+)", e), g(r"quantization=([\w-]+)", e),
            g(r"'gpu_memory_utilization': ([\d.]+)", a, float), int("enable_lora" in a or "lora_modules" in a),
            g(r"'max_lora_rank': (\d+)", a, int), json.dumps(cfg["lora"]), g(r"'tool_call_parser': '(\w+)'", a),
            g(r"'reasoning_parser': '(\w+)'", a), cfg.get("kv"), cfg.get("kvgib"), cfg.get("conc"), cfg.get("init"),
            first_ts, cur_ts, sum(n for (_, st), n in http.items() if st == 200),
            sum(n for (_, st), n in http.items() if st == 400),
            sum(1 for x in errs if x[2] == "context_overflow"), sum(1 for x in errs if x[2] != "context_overflow"),
            a, e, json.dumps(warns.most_common(30))))
        db.executemany("INSERT INTO vllm_metrics VALUES (?,?,?,?,?,?,?,?)", mets)
        db.executemany("INSERT INTO vllm_errors VALUES (?,?,?,?,?,?,?)", errs)
        db.executemany("INSERT INTO vllm_http VALUES (?,?,?,?)", [(sid, k[0], k[1], n) for k, n in http.items()])
    # each attempt's lane load during its own trace window (lane = attempts.node, from lora_progress 'gpu')
    db.executescript("""
    INSERT OR REPLACE INTO attempt_server_load
    SELECT a.id, s.server_id, COUNT(m.ts), AVG(m.kv_usage), MAX(m.kv_usage), AVG(m.running), MAX(m.running),
      MAX(m.waiting), AVG(m.gen_tps), AVG(m.prompt_tps),
      (SELECT COUNT(*) FROM vllm_errors e WHERE e.server_id = s.server_id AND e.kind = 'context_overflow'
         AND e.ts BETWEEN t.first_ts - 5 AND t.last_ts + 15)
    FROM attempts a JOIN traces t ON t.attempt_id = a.id
    JOIN vllm_servers s ON s.exp = a.exp AND s.lane = a.node
      AND t.first_ts BETWEEN s.first_ts - 60 AND s.last_ts + 60
    LEFT JOIN vllm_metrics m ON m.server_id = s.server_id AND m.ts BETWEEN t.first_ts AND t.last_ts
    WHERE a.dup_of IS NULL GROUP BY a.id, s.server_id;
    """)
    n = db.execute("SELECT COUNT(*), SUM(n_samples > 0) FROM attempt_server_load").fetchone()
    print(f"    {sid} vLLM server logs; {n[0]} attempts joined to their lane ({n[1]} with metric samples)", flush=True)
