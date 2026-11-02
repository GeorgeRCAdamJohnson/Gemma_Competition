"""Item 2: does statement informativeness predict resolve rate? CPU only, all traced rows.

Joins every traced outcome row in kb/runs.jsonl (per task per run, resolved flag)
against gold-derived task features (problem_chars, target_named_in_issue,
symptom_class, n_files, n_edits) and tests each feature as a predictor of the
per-task resolve rate.

Reports per-task determinism first: if a task is 0/1 or 1/1 across every traced
run, the outcome is task-determined and a bucketed rate is meaningful. Coin-flip
tasks are reported separately and excluded from rate math.
"""
from __future__ import annotations

import collections
import json
import math
import pathlib
import statistics

GEMMA = pathlib.Path(__file__).resolve().parent.parent
RUNS = GEMMA / "kb" / "runs.jsonl"
LABELS = GEMMA / "train" / "data" / "router_labels.json"
TASKS = GEMMA / "comp_files" / "tasks.jsonl"


def load():
    rows = [json.loads(l) for l in RUNS.read_text(encoding="utf-8").splitlines() if l.strip()]
    labels = {r["instance_id"]: r for r in json.load(open(LABELS, encoding="utf-8"))}
    feats = {}
    for l in TASKS.read_text(encoding="utf-8", errors="replace").splitlines():
        if l.strip():
            r = json.loads(l)
            feats[r["instance_id"]] = r
    return rows, labels, feats


def spearman(xs, ys):
    def rank(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        rk = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk
    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


def main():
    rows, labels, feats = load()

    per_task = collections.defaultdict(list)
    for r in rows:
        out = r.get("outcome") or {}
        if isinstance(out, dict) and "resolved" in out:
            per_task[r["task"]].append((bool(out["resolved"]), r["repo"]))

    print("=" * 78)
    print("A. PER-TASK DETERMINISM (is the outcome task-determined?)")
    print("=" * 78)
    det, coin = [], []
    for t in sorted(per_task):
        vals = [v for v, _ in per_task[t]]
        rate = sum(vals) / len(vals)
        if rate in (0.0, 1.0):
            det.append((t, per_task[t][0][1], int(rate), len(vals)))
        else:
            coin.append((t, per_task[t][0][1], rate, len(vals)))
    print(f"deterministic tasks: {len(det)}   coin-flip tasks: {len(coin)}")
    for t, repo, r_, n in coin:
        print(f"  COIN-FLIP {t:14} [{repo:18}] rate={r_:.2f} n={n}")

    print()
    print("=" * 78)
    print("B. PER-TASK FEATURES vs RESOLVE (deterministic tasks only)")
    print("=" * 78)
    print(f"{'task':15}{'repo':6}{'res':>4}{'n':>3}{'chars':>7}"
          f"{'named':>7}{'files':>7}{'edits':>7}{'symptom':>12}")
    data = []
    for t, repo, r_, n in det:
        lab = labels.get(t, {})
        f = feats.get(t, {})
        chars = lab.get("problem_chars", len(f.get("problem_statement", "") or ""))
        named = lab.get("target_named_in_issue")
        data.append({
            "task": t, "repo": repo, "resolved": r_, "n": n, "chars": chars,
            "named": bool(named), "files": lab.get("n_files", 0),
            "edits": lab.get("n_edits", 0), "symptom": lab.get("symptom_class", "?"),
        })
        print(f"{t:15}{repo.split('/')[0][:5]:6}{r_:>4}{n:>3}{chars:>7}"
              f"{str(bool(named)):>7}{lab.get('n_files', 0):>7}"
              f"{lab.get('n_edits', 0):>7}{lab.get('symptom_class', '?'):>12}")

    print()
    print("=" * 78)
    print("C. PREDICTOR TESTS (deterministic tasks, n=%d)" % len(data))
    print("=" * 78)
    y = [d["resolved"] for d in data]

    def bucket(name, key, edges=None):
        print(f"\n-- {name} --")
        g = collections.defaultdict(lambda: [0, 0])
        for d in data:
            v = d[key]
            if edges is None:
                b = str(v)
            elif v is None:
                b = "?"
            else:
                b = next((f"[{edges[i]},{edges[i+1]})" for i in range(len(edges) - 1)
                          if edges[i] <= v < edges[i + 1]), f">={edges[-1]}")
            g[b][0] += d["resolved"]
            g[b][1] += 1
        for b in sorted(g, key=lambda x: (x == "?", x)):
            ok, n = g[b]
            print(f"   {b:>16}: resolved {ok}/{n}")

    bucket("problem_chars", "chars", [0, 100, 200, 400, 800, 10 ** 9])
    bucket("target_named_in_issue", "named")
    bucket("n_files", "files", [1, 2, 3, 10 ** 9])
    bucket("n_edits", "edits", [1, 2, 3, 6, 10 ** 9])
    bucket("symptom_class", "symptom")

    print()
    print("-- Spearman rho (numeric predictors vs resolved) --")
    for key in ("chars", "files", "edits"):
        xs = [d[key] for d in data]
        pairs = [(a, b) for a, b in zip(xs, y) if a is not None]
        if len(pairs) > 2:
            rho = spearman([a for a, _ in pairs], [float(b) for _, b in pairs])
            print(f"   {key:8}: rho={rho:+.3f}  (n={len(pairs)})")
    named = [float(d["named"]) for d in data]
    if len(set(named)) > 1:
        print(f"   {'named':8}: rho={spearman(named, [float(v) for v in y]):+.3f}")

    print()
    print("=" * 78)
    print("D. RICH ONLY (the repo where statement terseness was flagged)")
    print("=" * 78)
    rd = [d for d in data if d["repo"] == "Textualize/rich"]
    print(f"n={len(rd)}  resolved={sum(d['resolved'] for d in rd)}")
    for name, key, edges in (("chars", "chars", [0, 100, 200, 10 ** 9]),
                             ("named", "named", None),
                             ("files", "files", [1, 2, 3, 10 ** 9])):
        print(f"\n-- rich {name} --")
        g = collections.defaultdict(lambda: [0, 0])
        for d in rd:
            v = d[key]
            b = (str(v) if edges is None else
                 next((f"[{edges[i]},{edges[i+1]})" for i in range(len(edges) - 1)
                       if edges[i] <= v < edges[i + 1]), f">={edges[-1]}"))
            g[b][0] += d["resolved"]
            g[b][1] += 1
        for b in sorted(g):
            ok, n = g[b]
            print(f"   {b:>16}: resolved {ok}/{n}")

    out = GEMMA / "kb" / "audits" / "_stmt_info_all.json"
    out.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()