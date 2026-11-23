"""Interim/final summary of the 31B six-arm Colab A/B from progress.json (Drive), each arm vs A_ca5 paired by task.
Pre-registered reads (GEMMA_EXPERIMENT_LOG 2026-11-22): solves are reported, not decided on in one round; mechanisms:
8-minute timeouts, context overflow, no-edit (empty patch), calls and seconds per attempt. First-edit-on-gold and
right-file conversion need traces (DB rebuild after the run). usage: python Outputs/_lb022_interim.py"""
import json
from pathlib import Path

RUN = Path(r"G:\My Drive\gemma_fasteval\ab_runs\31b_lb022_20261122")
prog = json.loads((RUN / "progress.json").read_text(encoding="utf-8"))


def kind(r):
    e = (r.get("err") or "").lower()
    if "contextwindow" in e:
        return "overflow"
    if "timeout" in e or "session timeout" in e or (r.get("dur") or 0) >= 475:
        return "timeout"
    return "error" if e else "ok"


arms = {}
for p in prog["passes"]:
    arms[p["arm"]] = {t["id"]: t for t in p.get("rows", [])}
print("passes:", [(p["arm"], p.get("round"), len(p.get("rows", []))) for p in prog["passes"]])
base = arms.get("A_ca5", {})
print(f"\n{'arm':14s} {'n':>3s} {'solved':>6s} {'timeout':>7s} {'overflow':>8s} {'no-edit':>7s} {'calls':>5s} {'sec':>4s}"
      f" | vs A_ca5 paired: {'both':>4s} {'arm-only':>8s} {'A-only':>6s} {'d timeout+ovf':>13s}")
for arm, rows in arms.items():
    ts = list(rows.values())
    n = len(ts)
    k = [kind(t) for t in ts]
    solved = sum(bool(t.get("resolved")) for t in ts)
    to, ov = k.count("timeout"), k.count("overflow")
    noedit = sum((t.get("patch") or 0) == 0 for t in ts)
    calls = sum(t.get("calls") or 0 for t in ts) / max(n, 1)
    sec = sum(t.get("dur") or 0 for t in ts) / max(n, 1)
    shared = sorted(set(rows) & set(base))
    both = sum(bool(rows[t].get("resolved")) and bool(base[t].get("resolved")) for t in shared)
    arm_only = sum(bool(rows[t].get("resolved")) and not base[t].get("resolved") for t in shared)
    a_only = sum(bool(base[t].get("resolved")) and not rows[t].get("resolved") for t in shared)
    mech = lambda rs: sum(kind(rs[t]) in ("timeout", "overflow") for t in shared)
    d_mech = (mech(rows) - mech(base)) / max(len(shared), 1) * 100
    print(f"{arm:14s} {n:3d} {solved:6d} {to:7d} {ov:8d} {noedit:7d} {calls:5.1f} {sec:4.0f} | "
          f"{'':18s}{both:4d} {arm_only:8d} {a_only:6d} {d_mech:+12.1f}pt")
print("\nRule: a config is worth borrowing from only if timeouts + overflow fall >= 5 points vs A_ca5 without lowering"
      " first-edit-gold or conversion (trace check after the run). One round: solve differences of +-3 are noise.")
