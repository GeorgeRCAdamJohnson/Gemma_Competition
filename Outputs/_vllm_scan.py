"""Scan of all vLLM server logs in the intel DB: configuration, load, prefix caching, errors, warnings, and whether lane
load relates to attempt outcomes. Read-only on kb/attempts.sqlite."""
import json
import re
import sqlite3
import statistics as st
from collections import Counter, defaultdict

db = sqlite3.connect("kb/attempts.sqlite")
q = lambda s, *a: db.execute(s, a).fetchall()

print("1. SERVER CONFIGURATIONS")
for r in q("""SELECT exp, COUNT(*), vllm_version, max_model_len, tensor_parallel, gpu_memory_utilization, enable_lora,
                     max_lora_rank, tool_call_parser, reasoning_parser, MIN(kv_cache_tokens), MAX(max_concurrency),
                     ROUND(AVG(init_engine_s)), lora_modules FROM vllm_servers GROUP BY exp ORDER BY MIN(first_ts)"""):
    print(f"  {r[0][:44]:44s} lanes {r[1]} v{r[2]} ctx {r[3]} tp {r[4]} gmu {r[5]} lora {r[6]} rank {r[7]} "
          f"tool {r[8]} reason {r[9]} kv {r[10]} conc {r[11]}x init {r[12]}s {r[13]}")
args = Counter()
for (a,) in q("SELECT args_text FROM vllm_servers"):
    for k in re.findall(r"'(\w+)':", a or ""):
        args[k] += 1
print("  non-default args seen (servers):", dict(args.most_common(25)))
eng = q("SELECT engine_config FROM vllm_servers LIMIT 1")[0][0] or ""
for key in ("enable_prefix_caching", "enable_chunked_prefill", "enforce_eager", "max_num_seqs", "max_num_batched_tokens",
            "kv_cache_dtype", "quantization", "seed"):
    m = re.search(rf"{key}=([^,]+)", eng)
    print(f"  engine {key}: {m.group(1) if m else '(not in engine line)'}")

print("\n2. LOAD (10 s samples while running: running > 0)")
m = q("""SELECT COUNT(*), AVG(kv_usage), MAX(kv_usage), AVG(running), MAX(running), AVG(waiting), MAX(waiting),
                AVG(gen_tps), AVG(prompt_tps), AVG(prefix_hit) FROM vllm_metrics WHERE running > 0""")[0]
print(f"  samples {m[0]} | KV use avg {m[1]:.1f}% max {m[2]:.1f}% | running avg {m[3]:.1f} max {m[4]} | waiting avg {m[5]:.2f}"
      f" max {m[6]} | gen {m[7]:.0f} tok/s | prompt {m[8]:.0f} tok/s | prefix-cache hit avg {m[9]:.1f}%")
dist = q("""SELECT CASE WHEN kv_usage < 50 THEN '<50%' WHEN kv_usage < 80 THEN '50-80%' WHEN kv_usage < 95 THEN '80-95%'
            ELSE '>=95%' END, COUNT(*), SUM(waiting > 0) FROM vllm_metrics WHERE running > 0 GROUP BY 1""")
print("  KV-use distribution (samples, of which requests were waiting):", dist)
print("  prefix-cache hit by experiment:", q("""SELECT s.exp, ROUND(AVG(m.prefix_hit),1) FROM vllm_metrics m
      JOIN vllm_servers s USING (server_id) WHERE m.running > 0 GROUP BY s.exp ORDER BY 2"""))

print("\n3. LOAD vs ATTEMPT OUTCOME (attempt's own lane during its window)")
for r in q("""SELECT CASE WHEN l.kv_max < 50 THEN 'kv max <50%' WHEN l.kv_max < 80 THEN 'kv max 50-80%'
                  WHEN l.kv_max < 95 THEN 'kv max 80-95%' ELSE 'kv max >=95%' END AS b, COUNT(*),
                  ROUND(AVG(a.resolved),3), ROUND(AVG(COALESCE(a.error_class,'')='overflow'),3), ROUND(AVG(a.duration_s)),
                  ROUND(AVG(l.waiting_max),2), ROUND(AVG(l.gen_tps_avg))
           FROM attempt_server_load l JOIN attempts_unique a ON a.id = l.attempt_id GROUP BY b ORDER BY b"""):
    print(f"  {r[0]:15s} n {r[1]:5d} solve {r[2]:.3f} overflow {r[3]:.3f} mean {r[4]:.0f}s waiting_max {r[5]} gen {r[6]} tok/s")
# within-task: does lane congestion (waiting_max > 0) change solve rate?
per = defaultdict(lambda: defaultdict(list))
for task, res, w in q("""SELECT a.task, a.resolved, l.waiting_max FROM attempt_server_load l JOIN attempts_unique a
                         ON a.id = l.attempt_id WHERE a.resolved IS NOT NULL"""):
    per[task]["queued" if (w or 0) > 0 else "clear"].append(res)
d = [st.mean(v["queued"]) - st.mean(v["clear"]) for v in per.values() if len(v["queued"]) >= 5 and len(v["clear"]) >= 5]
print(f"  within-task solve(queued) - solve(clear): tasks {len(d)}, mean {st.mean(d) if d else float('nan'):+.3f}, "
      f"worse {sum(x < 0 for x in d)}, better {sum(x > 0 for x in d)}")

print("\n4. ERRORS")
print("  by kind:", q("SELECT kind, COUNT(*) FROM vllm_errors GROUP BY 1 ORDER BY 2 DESC"))
ov = q("""SELECT MIN(input_tokens_at_least), MAX(input_tokens_at_least), AVG(input_tokens_at_least), COUNT(*)
          FROM vllm_errors WHERE kind = 'context_overflow'""")[0]
print(f"  overflow 'at least N input tokens': min {ov[0]} max {ov[1]} avg {ov[2]:.0f} (n {ov[3]})")
# per overflow attempt: how many overflow errors on its lane in its window, and time spent after the first one
rows = q("""SELECT a.id, t.first_ts, t.last_ts, s.server_id FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id
            JOIN attempt_server_load l ON l.attempt_id = a.id JOIN vllm_servers s ON s.server_id = l.server_id
            WHERE a.error_class = 'overflow'""")
per_att, after = [], []
for aid, f, l, sid in rows:
    e = [x for (x,) in q("""SELECT ts FROM vllm_errors WHERE server_id = ? AND kind = 'context_overflow'
                            AND ts BETWEEN ? AND ?""", sid, f - 5, l + 15)]
    if e:
        per_att.append(len(e))
        after.append(max(0.0, l - min(e)))
print(f"  overflow attempts on a logged lane: {len(per_att)}; overflow errors in their window: median {st.median(per_att)}"
      f" max {max(per_att)}; seconds from first overflow to trace end: median {st.median(after):.0f} max {max(after):.0f}")
http = q("SELECT status, SUM(n) FROM vllm_http GROUP BY 1")
print("  HTTP status totals:", http)

print("\n5. WARNINGS (distinct message classes, summed over servers)")
w = Counter()
for (j,) in q("SELECT warnings FROM vllm_servers"):
    for msg, n in json.loads(j or "[]"):
        w[re.sub(r"\d+(\.\d+)?", "#", msg)[:150]] += n
for msg, n in w.most_common(15):
    print(f"  {n:6d}  {msg}")
