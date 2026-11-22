"""Stage `crawl`: everything else in the project -> documents (+ FTS5 full-text index), kernels (kernel-metadata),
adapters (LoRA configs + weight hashes). Read-only; text capped at 2 MB per document."""
import hashlib
import json
import re
import time

from vfs import ROOT, SKIP

SCHEMA = """
CREATE TABLE documents (doc_id INTEGER PRIMARY KEY, path TEXT UNIQUE, kind TEXT, exp TEXT, bytes INTEGER,
  mtime TEXT, sha256 TEXT, title TEXT, text TEXT);
CREATE INDEX ix_doc_kind ON documents(kind, exp);
CREATE VIRTUAL TABLE documents_fts USING fts5(path, kind, text, content='documents', content_rowid='doc_id');
CREATE TABLE kernels (path TEXT PRIMARY KEY, slug TEXT, title TEXT, code_file TEXT, kernel_type TEXT,
  is_private INTEGER, enable_gpu INTEGER, enable_internet INTEGER, machine_shape TEXT, dataset_sources TEXT,
  competition_sources TEXT, kernel_sources TEXT, model_sources TEXT);
CREATE TABLE adapters (path TEXT PRIMARY KEY, exp TEXT, r INTEGER, lora_alpha REAL, lora_dropout REAL,
  target_modules TEXT, base_model TEXT, task_type TEXT, weights_path TEXT, weights_bytes INTEGER,
  weights_sha256 TEXT, config_json TEXT);
"""
MAXTXT = 2_000_000
PER_TASK = re.compile(r"/(logs|test_outputs|patches|traces)/|/lora_results/|/round_\d+/|/run_\d+/|/shard\d+/")


def kind_of(rel):
    n = rel.rsplit("/", 1)[-1].lower()
    if n.endswith(".ipynb"):
        return "notebook"
    if n == "kernel-metadata.json":
        return "kernel_metadata"
    if n in ("registration.json", "submission_receipt.json", "result_report.json", "launch.json") or n.startswith("launch_"):
        return n.replace(".json", "")
    if n == "adapter_config.json":
        return "adapter_config"
    if n == "chat_history" or "chat_history" in n:
        return "chat_history"
    if rel.startswith("train/") and n.endswith((".json", ".jsonl", ".log", ".md", ".txt", ".csv", ".yaml")):
        return "training"
    if n.endswith(".md"):
        return "doc"
    if n.endswith(".py"):
        return "code"
    if n.endswith((".yaml", ".yml")) and not rel.startswith(("Outputs/", "local_eval/")):
        return "config"
    if n.endswith((".log", ".txt")) and "vllm" not in n:
        return "run_log"
    if n.endswith(".json") and rel.startswith("Outputs/") and n not in ("summary.json", "task_results.jsonl"):
        return "result_json"
    return None


def notebook_text(raw):
    try:
        nb = json.loads(raw)
    except Exception:
        return raw.decode("utf-8", "replace")
    out = []
    for c in nb.get("cells", []):
        src = c.get("source", "")
        out.append(f"## [{c.get('cell_type')}]\n" + ("".join(src) if isinstance(src, list) else str(src)))
        for o in c.get("outputs", []) or []:
            t = o.get("text") or (o.get("data") or {}).get("text/plain")
            if t:
                out.append("## [output]\n" + ("".join(t) if isinstance(t, list) else str(t))[:50000])
    return "\n".join(out)


def run(db, vfs):
    db.executescript(SCHEMA)
    n = 0
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or SKIP.search(str(p)):
            continue
        rel = p.relative_to(ROOT).as_posix()
        if rel.startswith(("kb/attempts.sqlite", ".git/")) or rel == "GEMMA_EXPERIMENT_LOG.md":
            continue
        k = kind_of(rel)
        if not k or (k in ("run_log", "result_json", "code", "doc") and PER_TASK.search("/" + rel)):
            continue
        size = p.stat().st_size
        if size > 50_000_000:
            continue
        raw = p.read_bytes()
        text = notebook_text(raw) if k == "notebook" else raw.decode("utf-8", "replace")
        exp = rel.split("/")[1] if rel.startswith("Outputs/") and rel.count("/") >= 2 else None
        title = None
        if k == "kernel_metadata":
            try:
                m = json.loads(raw)
                title = m.get("title")
                db.execute("INSERT OR REPLACE INTO kernels VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                    rel, m.get("id"), m.get("title"), m.get("code_file"), m.get("kernel_type"),
                    int(bool(m.get("is_private"))), int(bool(m.get("enable_gpu"))), int(bool(m.get("enable_internet"))),
                    m.get("machine_shape") or m.get("accelerator"), json.dumps(m.get("dataset_sources") or []),
                    json.dumps(m.get("competition_sources") or []), json.dumps(m.get("kernel_sources") or []),
                    json.dumps(m.get("model_sources") or [])))
            except Exception:
                pass
        if k == "adapter_config":
            try:
                c = json.loads(raw)
                w = next((x for x in (p.parent / "adapter_model.safetensors", p.parent / "adapter_model.bin") if x.exists()), None)
                db.execute("INSERT OR REPLACE INTO adapters VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
                    rel, exp, c.get("r"), c.get("lora_alpha"), c.get("lora_dropout"),
                    json.dumps(c.get("target_modules")), c.get("base_model_name_or_path"), c.get("task_type"),
                    w.relative_to(ROOT).as_posix() if w else None, w.stat().st_size if w else None,
                    hashlib.sha256(w.read_bytes()).hexdigest() if w else None, raw.decode("utf-8", "replace")[:20000]))
            except Exception:
                pass
        cur = db.execute("INSERT INTO documents (path, kind, exp, bytes, mtime, sha256, title, text) VALUES (?,?,?,?,?,?,?,?)",
                         (rel, k, exp, size, time.strftime("%Y-%m-%d %H:%M", time.gmtime(p.stat().st_mtime)),
                          hashlib.sha256(raw).hexdigest(), title, text[:MAXTXT]))
        db.execute("INSERT INTO documents_fts (rowid, path, kind, text) VALUES (?,?,?,?)",
                   (cur.lastrowid, rel, k, text[:MAXTXT]))
        n += 1
    kinds = db.execute("SELECT kind, COUNT(*) FROM documents GROUP BY kind ORDER BY 2 DESC").fetchall()
    print(f"    {n} documents: {dict(kinds)}", flush=True)
