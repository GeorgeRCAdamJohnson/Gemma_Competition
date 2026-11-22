"""Offline validation of the GPU-usage guidance from existing vLLM metrics (32K servers only).
1. Throughput scaling: aggregate generation tok/s and per-request tok/s by number of running requests. If aggregate
   throughput still rises at 7-8 running, the lane is not saturated and more slots add throughput.
2. KV headroom: KV-cache use by running count, extrapolated to 12 and 13 running.
3. Time-cap risk: per-request generation speed falls as concurrency rises; project mean attempt duration at 12 running
   against the 30-min cap, and the share of attempts that would exceed it.
4. Overflow tail: lane time spent after the first overflow, as a share of all attempt time."""
import sqlite3
import statistics as st

db = sqlite3.connect("kb/attempts.sqlite")
q = lambda s, *a: db.execute(s, a).fetchall()
rows = q("""SELECT m.running, AVG(m.gen_tps), AVG(m.prompt_tps), AVG(m.kv_usage), COUNT(*) FROM vllm_metrics m
            JOIN vllm_servers s USING (server_id) WHERE s.max_model_len = 32768 AND m.running > 0 GROUP BY m.running""")
print("1-2. running | samples | aggregate gen tok/s | per-request gen tok/s | KV use %")
pts = []
for r, g, p, kv, n in rows:
    print(f"   {r:2d}     | {n:6d}  | {g:8.1f}            | {g / r:7.1f}               | {kv:5.1f}")
    pts.append((r, g, kv))
# least-squares on running 4..8 for aggregate throughput and KV
sub = [(r, g, kv) for r, g, kv in pts if r >= 4]
mx = st.mean(r for r, _, _ in sub)
slope_g = sum((r - mx) * (g - st.mean(x for _, x, _ in sub)) for r, g, _ in sub) / sum((r - mx) ** 2 for r, _, _ in sub)
slope_kv = sum((r - mx) * (kv - st.mean(x for _, _, x in sub)) for r, _, kv in sub) / sum((r - mx) ** 2 for r, _, _ in sub)
g8 = next(g for r, g, _ in pts if r == 8)
kv8 = next(kv for r, _, kv in pts if r == 8)
for c in (10, 12, 13):
    g = g8 + slope_g * (c - 8)
    kv = kv8 + slope_kv * (c - 8)
    print(f"   projected {c:2d} running: aggregate {g:6.1f} tok/s (x{g / g8:.2f} vs 8), per-request {g / c:5.1f}, KV ~{kv:4.1f}%")
print(f"   (linear fit on running 4-8: +{slope_g:.1f} tok/s and +{slope_kv:.2f} KV-points per extra request; "
      f"extrapolation, not measured above 8)")

print("\n3. time-cap risk (32K, E4B attempts joined to their lane)")
d = [x for (x,) in q("""SELECT a.duration_s FROM attempt_server_load l JOIN attempts_unique a ON a.id = l.attempt_id
                       WHERE a.duration_s IS NOT NULL""")]
rate8 = g8 / 8
for c in (12,):
    rc = (g8 + slope_g * (c - 8)) / c
    stretch = rate8 / rc
    proj = [x * stretch for x in d]
    print(f"   per-request slowdown at {c}: x{stretch:.2f}; mean duration {st.mean(d):.0f}s -> {st.mean(proj):.0f}s; "
          f"over 30 min now {sum(x > 1800 for x in d) / len(d):.1%} -> {sum(x > 1800 for x in proj) / len(proj):.1%} "
          f"(upper bound: assumes all time is generation)")

print("\n4. overflow tail as share of attempt time")
tot = q("SELECT SUM(a.duration_s) FROM attempt_server_load l JOIN attempts_unique a ON a.id = l.attempt_id")[0][0]
tail = 0.0
for aid, f, l, sid in q("""SELECT a.id, t.first_ts, t.last_ts, l.server_id FROM attempts_unique a JOIN traces t ON t.attempt_id = a.id
        JOIN attempt_server_load l ON l.attempt_id = a.id WHERE a.error_class = 'overflow'"""):
    e = q("""SELECT MIN(ts) FROM vllm_errors WHERE server_id = ? AND kind = 'context_overflow' AND ts BETWEEN ? AND ?""",
          sid, f - 5, l + 15)[0][0]
    if e:
        tail += max(0.0, l - e)
print(f"   seconds after first overflow: {tail:.0f} of {tot:.0f} attempt-seconds = {tail / tot:.1%} of slot time")
