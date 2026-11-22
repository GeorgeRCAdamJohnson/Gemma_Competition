"""Validate that an experiment is in the intel DB: compare DB per-arm counts with the run's own lora_summary.json /
lora_progress.json, and list vLLM servers and error types. usage: python kb/attemptdb/_check_exp.py <exp dir name> [...]"""
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
db = sqlite3.connect(ROOT / "kb" / "attempts.sqlite")
q = lambda s, *a: db.execute(s, a).fetchall()
for exp in sys.argv[1:]:
    print(f"\n===== {exp}")
    base = ROOT / "Outputs" / exp
    prog = next(iter(sorted(base.rglob("lora_progress.json"))), None)
    if prog:
        recs = json.loads(prog.read_text(encoding="utf-8"))["tasks"]
        by = {}
        for r in recs:
            res = r.get("result") or {}
            k = by.setdefault(r.get("arm"), [0, 0, 0])
            k[0] += 1
            k[1] += bool(res.get("resolved"))
            k[2] += "ContextWindow" in str(res.get("error") or "")
        print(f"  run file {prog.relative_to(ROOT)}: per arm [attempts, resolved, overflow] = {by}")
    db_rows = q("""SELECT arm, COUNT(*), SUM(resolved), SUM(verified), SUM(error_class = 'overflow'),
                   SUM(trace_path IS NOT NULL), COUNT(DISTINCT round) FROM attempts_unique WHERE exp = ? GROUP BY arm""", exp)
    print("  DB attempts_unique per arm [n, resolved, verified, overflow, with trace, rounds]:")
    for r in db_rows:
        print(f"    {r[0]}: {list(r[1:])}")
    tr = q("""SELECT COUNT(*), SUM(t.n_tool_calls), SUM(t.n_steps) FROM traces t JOIN attempts a ON a.id = t.attempt_id
              WHERE a.exp = ?""", exp)[0]
    print(f"  traces {tr[0]}, tool calls {tr[1]}, steps {tr[2]}")
    for s in q("""SELECT lane, n_requests_ok, n_requests_bad, n_overflow, n_errors, kv_cache_tokens FROM vllm_servers
                  WHERE exp = ? ORDER BY lane""", exp):
        print(f"  vLLM lane {s[0]}: ok {s[1]} bad {s[2]} overflow {s[3]} other errors {s[4]} kv {s[5]}")
    kinds = q("""SELECT e.kind, COUNT(*) FROM vllm_errors e JOIN vllm_servers s USING (server_id) WHERE s.exp = ?
                 GROUP BY 1""", exp)
    print("  vLLM error kinds:", kinds)
    print("  catalogued:", q("SELECT n_attempts, n_unique_tasks, arms, first_utc, last_utc FROM experiment_catalog WHERE exp = ?", exp))
