"""ca5-31b-timeout-ab final read: per arm solved/timeouts/duration, per task, Fisher exact vs control,
and what killed B's commands (60 s timeouts) - were they hung scripts or legitimate work?"""
import json
import re
import tarfile
from collections import Counter, defaultdict
from math import comb
from pathlib import Path

D = Path("Outputs/ca5_31b_timeout_ab")
ab = json.load(open(D / "presubmit_ab.json"))
rows = [r for r in ab["rows"] if r["chunk_complete"]]
arms = ["A_ca5", "B_cmd60", "C_time10"]


def fisher(a, n1, b, n2):  # two-sided, hypergeometric
    k = a + b; N = n1 + n2
    p0 = comb(n1, a) * comb(n2, b) / comb(N, k)
    return sum(comb(n1, x) * comb(n2, k - x) / comb(N, k) for x in range(max(0, k - n2), min(k, n1) + 1)
               if comb(n1, x) * comb(n2, k - x) / comb(N, k) <= p0 + 1e-12)


st = {}
for a in arms:
    ra = [r for r in rows if r["arm"] == a]
    s = sum(r["resolved"] for r in ra); n = len(ra)
    to = sum("timeout" in (r["err"] or "") for r in ra)
    ovf = sum("ContextWindow" in (r["err"] or "") for r in ra)
    d = sorted((r["dur"] or 0) for r in ra)
    st[a] = (s, n)
    print(f"{a:9s} solved {s:2d}/{n} ({s/n:.0%}) | session timeouts {to:2d} | overflow {ovf} | dur median {d[n//2]:.0f}s max {d[-1]:.0f}s")
for a in arms[1:]:
    print(f"   {a} vs A: Fisher two-sided p = {fisher(st[a][0], st[a][1], st['A_ca5'][0], st['A_ca5'][1]):.3f}")
print("\nper task (solved/runs):")
for t in ["rich_3480", "fastapi_14616", "fastapi_14851", "rich_3506", "fastapi_14419", "rich_3521"]:
    print(f"   {t:15s} " + "  ".join(f"{a[:8]} {sum(r['resolved'] for r in rows if r['arm']==a and r['id']==t)}/"
                                         f"{sum(1 for r in rows if r['arm']==a and r['id']==t)}" for a in arms))
# C: how many of C's solves needed > 8 min (would have been lost at the 8-min cap)?
c_late = [r for r in rows if r["arm"] == "C_time10" and r["resolved"] and (r["dur"] or 0) > 480]
print(f"\nC solves finishing after 8 min: {len(c_late)} of {st['C_time10'][0]} -> {sorted(round(r['dur']) for r in c_late)}")
# B: command timeouts in logs
A = re.compile(r"\x1b\[[0-9;]*m")
kills = Counter(); kill_tasks = defaultdict(int)
with tarfile.open(D / "results.tar.gz") as tf:
    for m in tf.getmembers():
        if "/B_cmd60/logs/" in m.name and m.name.endswith(".log"):
            t = A.sub("", tf.extractfile(m).read().decode("utf-8", "replace"))
            for hit in re.finditer(r"(run_command[^\n]{0,80})\n[^\n]*(TimeoutExceeded|timed out|Timeout)", t):
                kills[re.sub(r"\s+", " ", hit.group(1))[:60]] += 1
                kill_tasks[m.name.split("/")[-1][:-4]] += 1
print(f"B command timeouts seen in logs: {sum(kills.values())} | by task {dict(kill_tasks)}")
for k, v in kills.most_common(6):
    print(f"   {v}x {k}")
