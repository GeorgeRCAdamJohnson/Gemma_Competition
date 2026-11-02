"""Real-trace prompt-token accounting: does the real harness keep the context bounded (compaction) or let it grow?

For every real ATIF trace: N agent steps (= LLM calls), final_metrics.total_prompt_tokens, mean tokens/call.
If the context only grew (no compaction), mean tokens/call ~ P0 + g*(N+1)/2 and a long run must have a larger mean
than a short one. A mean that stays flat while N grows indicates compaction (or a bounded window).
Usage: python atif_prompt_tokens.py [glob-root]
"""
import json, sys, glob, re, os, statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
rows = []
for p in glob.glob(str(ROOT / "submit_*" / "**" / "trace_rich_*.json"), recursive=True):
    try:
        j = json.load(open(p, encoding="utf-8"))
    except Exception:
        continue
    fm = j.get("final_metrics") or {}
    steps = j.get("steps") or []
    n_llm = sum(1 for s in steps if s.get("source") == "agent")
    tot = fm.get("total_prompt_tokens")
    if not tot or not n_llm:
        continue
    task = re.search(r"trace_(rich_\d+)", p).group(1)
    ver = re.search(r"submit_([^\\/]+)", p).group(1)
    rows.append((ver, task, n_llm, tot, tot / n_llm))

print("traces:", len(rows))
by_n = {}
for ver, task, n, tot, avg in rows:
    by_n.setdefault(min(n // 5 * 5, 40), []).append(avg)
print("mean prompt tokens per LLM call, by N agent steps bucket:")
for k in sorted(by_n):
    v = by_n[k]
    print(f"  N {k:2d}-{k+4:2d}: runs={len(v):3d} mean={st.mean(v):7.0f} median={st.median(v):7.0f} max={max(v):7.0f}")

# shortest runs approximate P0 (first call prompt incl. system + task + tool schemas)
short = sorted(rows, key=lambda r: r[2])[:8]
print("shortest runs (N, total, avg):", [(r[1], r[2], r[3]) for r in short])
