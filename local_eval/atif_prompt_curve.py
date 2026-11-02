"""Per-step prompt-token curves of the REAL 31B runs (ATIF steps carry metrics.prompt_tokens).

Questions answered:
  1. Does the real context ever SHRINK mid-task (a drop in prompt_tokens = compaction fired)? At what prompt size?
  2. How large does the real prompt get (max over steps) vs the 14,336 compaction threshold and the 32,768 window?
  3. Per-step growth in tokens, and its relation to the previous step's text (message), tool-call and observation chars
     (does the real harness re-send the assistant text/thoughts?).
Usage: python atif_prompt_curve.py
"""
import json, glob, re, statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
runs = []
for p in glob.glob(str(ROOT / "submit_*" / "**" / "trace_rich_*.json"), recursive=True):
    try:
        j = json.load(open(p, encoding="utf-8"))
    except Exception:
        continue
    steps = [s for s in (j.get("steps") or []) if s.get("source") == "agent" and (s.get("metrics") or {}).get("prompt_tokens")]
    if len(steps) < 3:
        continue
    ver = re.search(r"submit_([^\\/]+)", p).group(1)
    task = re.search(r"trace_(rich_\d+)", p).group(1)
    runs.append((ver, task, steps))
print("runs with per-step prompt_tokens:", len(runs))

drops, maxp, n_over_thr = [], [], 0
first_p = []
xs, ys = [], []          # regression rows: dP vs chars of previous step
for ver, task, steps in runs:
    P = [s["metrics"]["prompt_tokens"] for s in steps]
    first_p.append(P[0])
    maxp.append(max(P))
    if max(P) >= 14336:
        n_over_thr += 1
    for k in range(1, len(P)):
        d = P[k] - P[k - 1]
        if d < 0:
            drops.append((ver, task, k, P[k - 1], P[k]))
        prev = steps[k - 1]
        msg = len(prev.get("message") or "")
        call = sum(len(json.dumps(tc.get("arguments") or {}, ensure_ascii=False)) + len(tc.get("function_name") or "")
                   for tc in (prev.get("tool_calls") or []))
        obs = len(((prev.get("observation") or {}).get("content")) or "")
        if d >= 0:
            xs.append((msg, call, obs))
            ys.append(d)

print(f"first-call prompt tokens: median={st.median(first_p):.0f} min={min(first_p)} max={max(first_p)}")
print(f"max prompt tokens per run: median={st.median(maxp):.0f} p90={sorted(maxp)[int(.9*len(maxp))]} max={max(maxp)}")
print(f"runs whose prompt reached >= 14336: {n_over_thr}/{len(runs)}")
print(f"steps where prompt tokens DROPPED vs previous step: {len(drops)}")
for d in drops[:20]:
    print("   ", d)

# least squares dP ~ a*msg + b*call + c*obs  (tokens per char), no intercept
try:
    import numpy as np
    X = np.array(xs, dtype=float)
    y = np.array(ys, dtype=float)
    coef, res, rk, sv = np.linalg.lstsq(X, y, rcond=None)
    pred = X @ coef
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    print(f"dP ~ a*msg_chars + b*call_chars + c*obs_chars: a={coef[0]:.3f} b={coef[1]:.3f} c={coef[2]:.3f} tok/char, R2={r2:.3f}, n={len(y)}")
    X2 = X[:, 1:]
    coef2, *_ = np.linalg.lstsq(X2, y, rcond=None)
    pred2 = X2 @ coef2
    r22 = 1 - ((y - pred2) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    print(f"without msg term: b={coef2[0]:.3f} c={coef2[1]:.3f}, R2={r22:.3f}")
except Exception as e:
    print("numpy unavailable:", e)

mean_g = st.mean(ys)
print(f"mean per-step growth: {mean_g:.0f} tokens; median {st.median(ys):.0f}")
