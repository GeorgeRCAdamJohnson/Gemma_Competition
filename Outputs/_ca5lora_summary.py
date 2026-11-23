"""Summary of the 31B ca5 vs ca5 + ayush adapter A/B (progress.json on Drive), paired by task within each round.
Pre-registered (GEMMA_EXPERIMENT_LOG 2026-11-23): the adapter earns a leaderboard draw on ca5 only if G - A >= +4
solves summed over the 2 rounds AND G's mean seconds per attempt is <= 1.10 x A's. usage: python Outputs/_ca5lora_summary.py"""
import json
from pathlib import Path

RUN = Path(r"G:\My Drive\gemma_fasteval\ab_runs\31b_ca5lora_20261123")
passes = json.loads((RUN / "progress.json").read_text(encoding="utf-8"))["passes"]


def kind(r):
    e = (r.get("err") or "").lower()
    if "contextwindow" in e:
        return "overflow"
    if "timeout" in e or (r.get("dur") or 0) >= 475:
        return "timeout"
    return "error" if e else "ok"


by = {(p["round"], p["arm"]): {r["id"]: r for r in p["rows"]} for p in passes}
print("passes:", sorted(by))
tot = {"A_ca5": [0, 0, 0, 0, 0.0, 0], "G_ca5_ayush": [0, 0, 0, 0, 0.0, 0]}  # solved, timeout, overflow, no-edit, sec, n
g_only = a_only = 0
for rnd in sorted({r for r, _ in by}):
    A, G = by.get((rnd, "A_ca5")), by.get((rnd, "G_ca5_ayush"))
    for arm, rows in (("A_ca5", A), ("G_ca5_ayush", G)):
        if not rows:
            continue
        t = tot[arm]
        for r in rows.values():
            t[0] += bool(r.get("resolved"))
            t[1] += kind(r) == "timeout"
            t[2] += kind(r) == "overflow"
            t[3] += (r.get("patch") or 0) == 0
            t[4] += r.get("dur") or 0
            t[5] += 1
        print(f"round {rnd} {arm:12s} solved {sum(bool(r.get('resolved')) for r in rows.values()):2d}/{len(rows)}")
    if A and G:
        shared = set(A) & set(G)
        g_only += sum(bool(G[t].get("resolved")) and not A[t].get("resolved") for t in shared)
        a_only += sum(bool(A[t].get("resolved")) and not G[t].get("resolved") for t in shared)
print(f"\n{'arm':12s} {'solved':>6s} {'timeout':>7s} {'overflow':>8s} {'no-edit':>7s} {'mean s':>6s} {'n':>4s}")
for arm, (s, to, ov, ne, sec, n) in tot.items():
    print(f"{arm:12s} {s:6d} {to:7d} {ov:8d} {ne:7d} {sec / max(n, 1):6.0f} {n:4d}")
(sa, *_, seca, na), (sg, *_, secg, ng) = tot["A_ca5"], tot["G_ca5_ayush"]
ratio = (secg / max(ng, 1)) / max(seca / max(na, 1), 1e-9)
print(f"\npaired over rounds: G-only {g_only}, A-only {a_only}, G - A = {sg - sa:+d}; time ratio G/A {ratio:.2f}")
complete = na == 170 and ng == 170
passed = complete and sg - sa >= 4 and ratio <= 1.10
print("RULE:", "PASS -> worth a leaderboard draw of ca5 + adapter" if passed else
      ("FAIL -> ca5 stays as is" if complete else "INCOMPLETE -> wait for all four passes"))
