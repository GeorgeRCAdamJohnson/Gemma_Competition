"""Build every chart from the data on disk -> Outputs/viz/*.png (+ index.md). Re-runnable; each chart is
independent and skips itself (with a note) if its source file is missing."""
import json
import re
import statistics as st
import tarfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

O = Path(__file__).resolve().parent
V = O / "viz"; V.mkdir(exist_ok=True)
plt.rcParams.update({"figure.dpi": 130, "axes.grid": True, "grid.alpha": 0.25, "axes.spines.top": False,
                     "axes.spines.right": False, "font.size": 9})
C31, CE4, CGR, CRED = "#1f6feb", "#d97706", "#6b7280", "#dc2626"
made = []


def save(fig, name, title, note):
    fig.tight_layout(); fig.savefig(V / name); plt.close(fig); made.append((name, title, note))
    print("wrote", name)


def jload(p):
    p = O / p
    return json.load(open(p, encoding="utf-8")) if p.exists() else None


ever39 = set((jload("_solvable85.json") or {}).get("ever", []))

# 1 ---------------------------------------------------------------- board timeline
subs = jload("_submissions.json")
if subs:
    fig, ax = plt.subplots(figsize=(10, 4))
    for s in subs:
        d = datetime.fromisoformat(s["date"][:19])
        txt = f"{s['desc'] or ''} {s['url'] or ''}".lower()
        model = "E4B" if "e4b" in txt else "31B"
        col = CE4 if model == "E4B" else C31
        if s["score"] not in (None, ""):
            ax.scatter(d, float(s["score"]), color=col, s=36, zorder=3)
        else:
            ax.scatter(d, -0.015, marker="x", color=CRED, s=40, zorder=3)
    ax.axhline(0.29, color=CGR, ls=":", lw=1); ax.axhline(0.24, color=CGR, ls="--", lw=0.8)
    xr = max(datetime.fromisoformat(s["date"][:19]) for s in subs)
    ax.text(xr, 0.293, "#1 (0.29) ", color=CGR, fontsize=8, ha="right")
    ax.text(xr, 0.243, "0.24 cluster ", color=CGR, fontsize=8, ha="right")
    ax.scatter([], [], color=C31, label="31B"); ax.scatter([], [], color=CE4, label="E4B")
    ax.scatter([], [], marker="x", color=CRED, label="no score (exception / runtime exceeded)")
    ax.set_ylim(-0.03, 0.32); ax.set_ylabel("public score (k/58, truncated)"); ax.legend(loc="upper left", fontsize=8)
    ax.set_title(f"Every board submission ({len(subs)})")
    fig.autofmt_xdate()
    save(fig, "01_board_timeline.png", "Board submissions over time",
         "31B ca5 family sits 0.13-0.20; E4B 0.03 / 0.01; x = runs that never scored.")

# 2 ---------------------------------------------------------------- E4B arms on the 39
def k39(passes, arm=None, kind=None):
    out = []
    for p in passes:
        if not p.get("complete") or (arm and p.get("arm") != arm) or (kind and p.get("kind") != kind):
            continue
        out.append(sum(1 for r in p["rows"] if r["resolved"] and r["id"] in ever39))
    return out


groups = []
cap = jload("e4b_cap_ab/variance_ab.json"); rep = jload("e4b_repro_ab/variance_ab.json")
p1 = jload("e4b_pack1_val/variance_ab.json"); p2 = jload("e4b_pack2_val/variance_ab.json")
if cap:
    groups.append(("plain ca5\n(control)", k39(cap["passes"]), CGR))
if rep:
    groups.append(("fresh retry\n(repro run)", k39(rep["passes"], "ARM_F_retry_fresh"), CE4))
    groups.append(("repro gate", k39(rep["passes"], "ARM_R_retry_repro"), CRED))
if p1:
    groups.append(("pack 1\nvalidation", k39(p1["passes"], kind="score39"), CE4))
if p2:
    groups.append(("pack 2\n(verifier none)", k39(p2["passes"], kind="score39"), "#a16207"))
if groups:
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    rng = np.random.default_rng(0)
    for i, (lab, ks, col) in enumerate(groups):
        x = i + rng.uniform(-0.18, 0.18, len(ks))
        ax.scatter(x, ks, color=col, alpha=0.6, s=22)
        m = st.mean(ks); ax.hlines(m, i - 0.3, i + 0.3, color="k", lw=2)
        ax.text(i, max(ks) + 0.6, f"{m:.2f}\n(n={len(ks)})", ha="center", fontsize=8)
    ax.set_xticks(range(len(groups))); ax.set_xticklabels([g[0] for g in groups])
    ax.set_ylabel("tasks solved per pass (of 39 ever-solved)"); ax.set_ylim(4, 17)
    ax.set_title("E4B on the 39 ever-solved practice tasks: every pass, every arm")
    save(fig, "02_e4b_arms_39.png", "E4B arms on the 39",
         "Fresh retry ~11.5-12 vs plain 9.8 locally - but pack 1 scored 0.01 on the board (transfer).")

# 3 ---------------------------------------------------------------- 31B passes on the 85 live
ab31 = jload("ca5_31b_ab/ab31.json"); pre = jload("ca5_31b_presubmit_85/presubmit_ab.json")
bars = []
if ab31:
    for a, lab in (("A_control", "ab31 ca5"), ("B_sibling", "ab31 +sibling")):
        bars.append((lab, sum(r["resolved"] for r in ab31["rows"] if r["arm"] == a and r["round"] == 1), C31))
if pre:
    for a, lab in (("A_ca5", "pre85 ca5"), ("B_presubmit", "pre85 +presubmit")):
        bars.append((lab, sum(r["resolved"] for r in pre["rows"] if r["arm"] == a), C31))
v7 = jload("v7_31b_full129/_cap_sim_rows.json")
live = set((jload("../kaggle_pkg/live_ids_31b_ab.json") or {}).get("order", []))
if v7 and live:
    bars.insert(0, ("v7 uncapped", sum(1 for r in v7 if r["resolved"] and r["task"] in live), CGR))
if bars:
    fig, ax = plt.subplots(figsize=(8, 3.6))
    ax.bar([b[0] for b in bars], [b[1] for b in bars], color=[b[2] for b in bars])
    for i, b in enumerate(bars):
        ax.text(i, b[1] + 0.4, str(b[1]), ha="center")
    ax.set_ylim(25, 38); ax.set_ylabel("solved of 85 live tasks"); ax.set_title("31B: one round on the 85 live tasks, every run")
    save(fig, "03_31b_85_rounds.png", "31B rounds on 85 live",
         "Rock-steady 32-34 regardless of prompt add-ons; uncapped v7 also 34.")

# 4 ---------------------------------------------------------------- timeout A/B per task + totals
tab = jload("ca5_31b_timeout_ab/presubmit_ab.json"); bc = jload("ca5_31b_bc_check/presubmit_ab.json")
if tab:
    rows = [r for r in tab["rows"] if r["chunk_complete"]]
    arms = ["A_ca5", "B_cmd60", "C_time10"]; cols = [CGR, "#0891b2", C31]
    tasks = ["rich_3480", "fastapi_14616", "fastapi_14851", "rich_3506", "fastapi_14419", "rich_3521"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 3.8), gridspec_kw={"width_ratios": [3, 1]})
    w = 0.26
    for j, (a, c) in enumerate(zip(arms, cols)):
        vals = [sum(r["resolved"] for r in rows if r["arm"] == a and r["id"] == t) for t in tasks]
        ax1.bar(np.arange(len(tasks)) + (j - 1) * w, vals, w, color=c, label=a)
    if bc:
        brow = {r["id"]: r for r in bc["rows"] if r["chunk_complete"]}
        ax1.scatter(np.arange(len(tasks)) + 1.6 * w, [6 * int(brow[t]["resolved"]) if t in brow else np.nan for t in tasks],
                    marker="*", s=90, color="#7c3aed", zorder=4, label="B+C check (1 run, x6 scale)")
    ax1.set_xticks(range(len(tasks))); ax1.set_xticklabels(tasks, rotation=20); ax1.set_ylabel("solved of 6 rounds")
    ax1.legend(fontsize=7); ax1.set_title("Recoverable timeout tasks, per task")
    tot = [sum(r["resolved"] for r in rows if r["arm"] == a) for a in arms]
    tos = [sum("timeout" in (r["err"] or "") for r in rows if r["arm"] == a) for a in arms]
    ax2.bar(["A", "B", "C"], tot, color=cols)
    for i, (t, o) in enumerate(zip(tot, tos)):
        ax2.text(i, t + 0.5, f"{t}/36\n{o} t/o", ha="center", fontsize=8)
    ax2.set_ylim(0, 26); ax2.set_title("Totals (p: B .14, C .03)")
    save(fig, "04_timeout_ab.png", "Timeout recovery A/B",
         "10-min cap converts the time-bound tasks (12 of 19 C solves landed after 8 min).")

# 5 ---------------------------------------------------------------- telemetry
tel = O / "ca5_31b_presubmit_85" / "telemetry.jsonl"
if tel.exists():
    T = [json.loads(l) for l in open(tel) if l.strip()]
    by = defaultdict(list)
    for a, b in zip(T, T[1:]):
        dt = b["t"] - a["t"]
        if dt > 0:
            run = round((a.get("vllm:num_requests_running", 0) + b.get("vllm:num_requests_running", 0)) / 2)
            by[run].append((b.get("vllm:generation_tokens_total", 0) - a.get("vllm:generation_tokens_total", 0)) / dt)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 3.6))
    ks = sorted(k for k in by if k > 0)
    agg = [st.mean(by[k]) for k in ks]
    ax1.plot(ks, agg, "o-", color=C31, label="aggregate tok/s")
    ax1.plot(ks, [a / k for a, k in zip(agg, ks)], "s--", color=CE4, label="per-sequence tok/s")
    ax1.set_xlabel("requests in flight"); ax1.set_ylabel("decode tokens / s"); ax1.legend(); ax1.set_title("31B on 4xL4: throughput vs load")
    t_h = [r["t"] / 3600 for r in T if r.get("gpu")]
    pw = [st.mean(g[4] for g in r["gpu"]) for r in T if r.get("gpu")]
    ut = [st.mean(g[0] for g in r["gpu"]) for r in T if r.get("gpu")]
    ax2.plot(t_h, pw, color=CRED, lw=0.8, label="mean power W (TDP 72)")
    ax2.plot(t_h, ut, color=CGR, lw=0.8, label="mean util %")
    ax2.plot([r["t"] / 3600 for r in T], [25 * r.get("vllm:num_requests_running", 0) for r in T], color=C31, lw=0.6,
             alpha=0.6, label="in flight x25")
    ax2.set_xlabel("hours into run"); ax2.legend(fontsize=7); ax2.set_title("GPU power / util / load over the run")
    save(fig, "05_telemetry.png", "31B server telemetry",
         "Power-limited at ~69 W; per-sequence speed drops 30 -> 23 tok/s at 4 in flight; chunk tails idle.")

# 6 ---------------------------------------------------------------- E4B fresh-retry mechanism
mech = jload("_mechanism_rows.json")
if mech:
    cat = Counter()
    for x in mech:
        if x["ovf"] and not x["sub"]:
            k = "overflow"
        elif not x["v"]:
            k = "no gate"
        elif x["v"][-1].startswith("ACC"):
            k = f"accepted @{len(x['v'])}"
        else:
            k = "3 rejects->restore"
        cat[(k, x["res"])] += 1
    keys = ["accepted @1", "accepted @2", "accepted @3", "3 rejects->restore", "overflow", "no gate"]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 3.8))
    sol = [cat[(k, True)] for k in keys]; uns = [cat[(k, False)] for k in keys]
    ax1.bar(keys, sol, color=CE4, label="solved"); ax1.bar(keys, uns, bottom=sol, color=CGR, alpha=0.5, label="unsolved")
    ax1.set_xticklabels(keys, rotation=25, ha="right"); ax1.legend(); ax1.set_title("E4B pack runs: where the submitted patch came from")
    vc = Counter(c for x in mech for c in x["v"])
    ks2 = [k for k, _ in vc.most_common()]
    ax2.barh(ks2, [vc[k] for k in ks2], color=[C31 if k.startswith("ACC") else CRED for k in ks2])
    ax2.invert_yaxis(); ax2.set_title("Gate verdicts on every attempt")
    save(fig, "06_e4b_retry_mechanism.png", "E4B fresh-retry mechanism",
         "80% of solves are attempt 1; the retry adds 31 conversions, half via the syntax check.")

# 7 ---------------------------------------------------------------- practice vs board (transfer)
pts = [("31B ca5", 0.26, 10.6 / 58, C31), ("E4B ca5", 0.078, 2 / 58, CE4), ("E4B pack 1", 13 / 129, 1 / 58, "#a16207")]
fig, ax = plt.subplots(figsize=(5.2, 4.4))
for lab, x, y, c in pts:
    ax.scatter(x, y, s=70, color=c); ax.annotate(f"{lab}\nratio {y/x:.2f}", (x, y), textcoords="offset points", xytext=(6, 4), fontsize=8)
ax.plot([0, 0.3], [0, 0.3], color=CGR, ls="--", lw=1, label="perfect transfer")
ax.set_xlim(0, 0.3); ax.set_ylim(0, 0.3); ax.set_xlabel("practice-set solve rate (our Kaggle runs)")
ax.set_ylabel("board rate (mean draw)"); ax.legend(fontsize=8); ax.set_title("Practice -> hidden-set transfer")
save(fig, "07_transfer.png", "Practice vs board transfer",
     "Hidden repos != practice repos (host-confirmed). Weaker model + task-specific gains transfer worst.")

# 8 ---------------------------------------------------------------- 31B per-task solve-rate heatmap
src = {}
if ab31:
    src["ab31"] = [(r["id"], r["resolved"]) for r in ab31["rows"]]
if pre:
    src["pre85"] = [(r["id"], r["resolved"]) for r in pre["rows"]]
capab = jload("ca5_31b_cap_ab/cap_ab.json")
if capab:
    src["cap"] = [(r["id"], r["resolved"]) for r in capab["rows"]]
if tab:
    src["timeout"] = [(r["id"], r["resolved"]) for r in tab["rows"] if r["arm"] == "A_ca5"]
if v7:
    src["v7"] = [(r["task"], r["resolved"]) for r in v7]
if src and live:
    tl = sorted(live)
    rate = {}
    for s, rows in src.items():
        agg = defaultdict(lambda: [0, 0])
        for t, ok in rows:
            agg[t][0] += bool(ok); agg[t][1] += 1
        rate[s] = {t: (agg[t][0] / agg[t][1]) if agg[t][1] else np.nan for t in tl}
    allr = {t: np.nanmean([rate[s][t] for s in rate]) for t in tl}
    tl.sort(key=lambda t: -np.nan_to_num(allr[t], nan=-1))
    M = np.array([[rate[s][t] for t in tl] for s in rate])
    fig, ax = plt.subplots(figsize=(14, 2.8))
    im = ax.imshow(M, aspect="auto", cmap="viridis", vmin=0, vmax=1)
    ax.set_yticks(range(len(rate))); ax.set_yticklabels(list(rate))
    ax.set_xticks(range(len(tl))); ax.set_xticklabels(tl, rotation=90, fontsize=5)
    fig.colorbar(im, ax=ax, fraction=0.02, label="solve rate")
    ax.set_title("31B per-task solve rate across every run (85 live tasks, sorted)"); ax.grid(False)
    save(fig, "08_31b_task_heatmap.png", "31B per-task heatmap",
         "~28 always / ~8 flippy / ~49 never - the flippy middle is where every lever lives.")

# 9 ---------------------------------------------------------------- where timeout runs spend time
if (O / "ca5_31b_presubmit_85" / "results.tar.gz").exists() and pre:
    A_ = re.compile(r"\x1b\[[0-9;]*m"); TS = re.compile(r"^\s*\[\s*([\d.]+)s\]\s+(.*)$")
    rs = {(r["arm"], r["id"]): r for r in pre["rows"]}
    turns = {"timeout": [], "solved": []}
    with tarfile.open(O / "ca5_31b_presubmit_85" / "results.tar.gz") as tf:
        for m in tf.getmembers():
            if not (m.name.endswith(".log") and "/logs/" in m.name):
                continue
            arm = "A_ca5" if "/A_ca5/" in m.name else "B_presubmit"
            r = rs.get((arm, m.name.rsplit("/", 1)[1][:-4]))
            if not r:
                continue
            kind = "timeout" if "timeout" in (r["err"] or "") else ("solved" if r["resolved"] else None)
            if not kind:
                continue
            last = 0.0
            for l in A_.sub("", tf.extractfile(m).read().decode("utf-8", "replace")).splitlines():
                mm = TS.match(l)
                if not mm:
                    continue
                t, s = float(mm.group(1)), mm.group(2)
                if "💭" in s:
                    turns[kind].append(t - last)
                if s.lstrip().startswith(("→", "✓", "❌")):
                    last = t
    # share of turns per bin (NOT density: density on log-width bins hides the slow tail) + share of wall time
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(11, 3.6))
    bins = np.logspace(0, np.log10(320), 25)
    for k, c in (("solved", C31), ("timeout", CRED)):
        v = np.array(turns[k]); v = v[v > 0]
        ax.hist(v, bins=bins, alpha=0.55, color=c, weights=np.ones(len(v)) / len(v),
                label=f"{k} runs: {100*np.mean(v > 60):.0f}% of turns > 60 s (n={len(v)})")
        tb = np.histogram(v, bins=bins, weights=v)[0]
        ax2.step(bins[1:], np.cumsum(tb) / tb.sum(), where="post", color=c, label=f"{k} runs")
    ax.axvline(60, color=CGR, ls="--", lw=1)
    ax.set_xscale("log"); ax.set_xlabel("seconds per model turn (log)"); ax.set_ylabel("share of turns"); ax.legend(fontsize=7)
    ax.set_title("31B: turn-time distribution")
    ax2.axvline(60, color=CGR, ls="--", lw=1); ax2.set_xscale("log"); ax2.set_ylim(0, 1)
    ax2.set_xlabel("seconds per model turn (log)"); ax2.set_ylabel("cumulative share of MODEL TIME"); ax2.legend(fontsize=8)
    ax2.set_title("Where the clock goes: slow turns eat timeout runs")
    save(fig, "09_31b_turn_times.png", "31B model-turn time distribution",
         "Turns > 60 s are a small share of turns but a large share of the clock in timeout runs; they carry "
         "~10k chars of text before a run_command.")

# 10 ---------------------------------------------------------------- phase-annotated timeline (paper Fig. 1)
if subs:
    D = lambda s: datetime.fromisoformat(s)
    phases = [("P1 design +\nearly wins", "2026-10-01", "2026-10-03", "#dbeafe"),
              ("P2 31B-only plateau\n(LoRA, prompt levers)", "2026-10-03", "2026-10-12", "#fee2e2"),
              ("P3 small models legal\nbudget recipe", "2026-10-12", "2026-10-28", "#dcfce7"),
              ("P4 measurement +\nsmall-model prize", "2026-10-28", "2026-11-04", "#fef9c3"),
              ("P5 architecture +\ntimeouts", "2026-11-04", "2026-11-10", "#ede9fe")]
    fig, ax = plt.subplots(figsize=(12, 4.6))
    for i, (lab, a, b, c) in enumerate(phases):
        ax.axvspan(D(a), D(b), color=c, alpha=0.8, lw=0)
        ax.text(D(a), 0.305 if i % 2 == 0 else 0.272, " " + lab, fontsize=7, va="top")   # stagger: no overlap
    for s in subs:
        d = D(s["date"][:19]); txt = f"{s['desc'] or ''} {s['url'] or ''}".lower()
        col = CE4 if "e4b" in txt else C31
        if s["score"] not in (None, ""):
            ax.scatter(d, float(s["score"]), color=col, s=34, zorder=3)
        else:
            ax.scatter(d, -0.015, marker="x", color=CRED, s=36, zorder=3)
    events = [("2026-10-03", 0.12, "v6 0.12\n(held 10 days)"), ("2026-10-10", 0.05, "edit-discipline\nLoRA 0.05"),
              ("2026-10-13", 0.15, "v6w budget\nrecipe 0.15"), ("2026-10-20", 0.18, "A3 delimiter\nfix 0.18"),
              ("2026-10-30", 0.20, "ca5 0.20\n(best)"), ("2026-11-08", 0.01, "E4B fresh-retry\n0.01")]
    scored = [(D(s["date"][:19]), float(s["score"])) for s in subs if s["score"] not in (None, "")]
    for d, y, t in events:
        # snap the label onto the actual submission with that score nearest the logged date
        cand = [p for p in scored if abs(p[1] - y) < 1e-9]
        xy = min(cand, key=lambda p: abs((p[0] - D(d)).total_seconds())) if cand else (D(d), y)
        ax.annotate(t, xy, xytext=(0, 14), textcoords="offset points", ha="center", fontsize=7,
                    arrowprops=dict(arrowstyle="-", color=CGR, lw=0.6))
    ax.axhline(0.24, color=CGR, ls="--", lw=0.8); ax.axhline(0.29, color=CGR, ls=":", lw=0.8)
    ax.set_ylim(-0.03, 0.31); ax.set_ylabel("public score (k/58)"); fig.autofmt_xdate()
    ax.set_title("Board history by project phase (blue 31B, orange E4B, x = no score)")
    save(fig, "10_phase_timeline.png", "Board history by phase (paper Fig. 1)",
         "Fast start, a 10-day plateau during the 31B-only/LoRA phase, then steady gains after the small-model "
         "release changed what we could iterate on.")

# 11 ---------------------------------------------------------------- model-size ladder (log L11433-11452)
fig, ax = plt.subplots(figsize=(5.6, 3.6))
sizes = ["E2B", "E4B*", "12B", "31B"]; solved = [0, 3, 3, 4]
ax.bar(sizes, solved, color=[CE4, CE4, "#059669", C31])
for i, v in enumerate(solved):
    ax.text(i, v + 0.1, f"{v}/6", ha="center")
ax.set_ylim(0, 6); ax.set_ylabel("solved (same 6 rich tasks, same prompt)")
ax.set_title("Size ladder: one variable (the model)")
ax.text(0.02, 0.92, "* E4B needed the architecture remap", transform=ax.transAxes, fontsize=7, color=CGR)
save(fig, "11_size_ladder.png", "Model-size ladder",
     "Identical v6w prompt + 6 rich tasks: 31B 4, 12B 3, E4B 3, E2B 0 (log L11433-11452). Tiny n - "
     "it showed small models were viable proxies, not that they match the 31B.")

# index
with open(V / "index.md", "w", encoding="utf-8") as f:
    f.write(f"# Visualizations - built {datetime.now():%Y-%m-%d %H:%M}\n\nRegenerate: `python Outputs/_viz_all.py`\n\n"
            "Four-tab HTML record: `Write-up/gemma-agent-score-record.html` "
            "(hand-maintained; this script does not rebuild it).\n\n")
    for name, title, note in made:
        f.write(f"## {title}\n![{title}]({name})\n\n{note}\n\n")
print(f"{len(made)} charts -> {V}")
# mirror into the repo-root Write-up/ folder (charts + README index; links are relative so they work unchanged)
import shutil
W = O.parent / "Write-up"; W.mkdir(exist_ok=True)
for name, _, _ in made:
    shutil.copy2(V / name, W / name)
shutil.copy2(V / "index.md", W / "README.md")
print(f"mirrored {len(made)} charts + README.md -> {W}")
