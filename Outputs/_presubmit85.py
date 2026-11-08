"""ca5-31b-presubmit-85: (1) telemetry - per-sequence decode speed vs batch, KV headroom; (2) did the check fire, and
on which tasks; (3) timeouts per arm."""
import json
import re
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

D = Path("Outputs/ca5_31b_presubmit_85")
T = [json.loads(l) for l in open(D / "telemetry.jsonl") if l.strip()]
print(f"telemetry samples {len(T)} over {T[-1]['t']/3600:.2f} h")
by = defaultdict(list)
for a, b in zip(T, T[1:]):
    dt = b["t"] - a["t"]
    if dt <= 0:
        continue
    tok = b.get("vllm:generation_tokens_total", 0) - a.get("vllm:generation_tokens_total", 0)
    run = round((a.get("vllm:num_requests_running", 0) + b.get("vllm:num_requests_running", 0)) / 2)
    by[run].append(tok / dt)
print("decode throughput by requests in flight (aggregate tok/s, per-sequence tok/s):")
for r in sorted(by):
    v = by[r]
    agg = sum(v) / len(v)
    print(f"   running~{r}: n={len(v):3d}  aggregate {agg:6.1f} tok/s  per-seq {agg/max(r,1):5.1f} tok/s")
kv = [t.get("vllm:gpu_cache_usage_perc", t.get("vllm:kv_cache_usage_perc", 0)) for t in T]
print(f"KV cache use: mean {100*sum(kv)/len(kv):.0f}%  max {100*max(kv):.0f}% | waiting>0 samples: "
      f"{sum(1 for t in T if t.get('vllm:num_requests_waiting', 0) > 0)} | preemptions "
      f"{T[-1].get('vllm:num_preemptions_total', 0) - T[0].get('vllm:num_preemptions_total', 0):.0f}")
g = [t["gpu"] for t in T if t.get("gpu")]
for i in range(4):
    print(f"   gpu{i}: util mean {sum(s[i][0] for s in g)/len(g):.0f}%  mem {max(s[i][1] for s in g)/1024:.1f} GB  "
          f"temp max {max(s[i][2] for s in g):.0f}C  SM clock min/mean {min(s[i][3] for s in g):.0f}/{sum(s[i][3] for s in g)/len(g):.0f} MHz  "
          f"power mean {sum(s[i][4] for s in g)/len(g):.0f} W")
print(f"host load1 mean {sum(t.get('load1',0) for t in T)/len(T):.1f} | pytest procs max {max(t.get('procs_pytest',0) for t in T)}")

ab = json.load(open(D / "presubmit_ab.json"))
rows = ab["rows"]
for arm in ("A_ca5", "B_presubmit"):
    rs = [r for r in rows if r["arm"] == arm]
    print(f"{arm}: solved {sum(r['resolved'] for r in rs)}/{len(rs)} | errors {Counter((r['err'] or 'none')[:40] for r in rs).most_common(3)}"
          f" | empty patch {sum(1 for r in rs if not (r['patch'] or 0))}")

# did the check fire? read B logs from the tarball
A = re.compile(r"\x1b\[[0-9;]*m")
fired = Counter(); fired_tasks = defaultdict(list)
with tarfile.open(D / "results.tar.gz") as tf:
    for m in tf.getmembers():
        if "/B_presubmit/logs/" in m.name and m.name.endswith(".log"):
            t = A.sub("", tf.extractfile(m).read().decode("utf-8", "replace"))
            task = m.name.rsplit("/", 1)[1][:-4]
            outs = re.findall(r'"stdout": "(OK|PROBLEM: [^"]{0,40})', t)
            if not outs:
                fired["check never called"] += 1
            for o in outs:
                k = "OK" if o == "OK" else o[:34]
                fired[k] += 1
                if o != "OK":
                    fired_tasks[task].append(o[:34])
res_b = {r["id"]: r["resolved"] for r in rows if r["arm"] == "B_presubmit"}
res_a = {r["id"]: r["resolved"] for r in rows if r["arm"] == "A_ca5"}
print("check outcomes over B runs:", dict(fired))
for task, fs in fired_tasks.items():
    print(f"   PROBLEM on {task}: {fs} -> B resolved {res_b.get(task)} | A resolved {res_a.get(task)}")
