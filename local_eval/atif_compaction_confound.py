"""Compaction: confound check + what happens right after it.  CPU only.
1. Within-task comparison (Mantel-Haenszel style): same task, compacted vs not compacted.
2. Post-compaction prompt size vs the run's OWN first-call prompt (is the task statement kept?).
3. Post-compaction behaviour: does the next 6 tool calls repeat (file/range or command) calls from BEFORE the compaction?
"""
import json, glob, re, collections, statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = json.load(open(ROOT / "local_eval" / "runs" / "kaggle_outcomes.json", encoding="utf-8"))
by_key = {}
for r in OUT:
    by_key.setdefault((r["version"], r["task"]), r)


def version_of(p):
    rel = p.relative_to(ROOT).parts
    if len(rel) > 3 and rel[2] == "out":
        return f"{rel[0][7:]}/{rel[1]}"
    return rel[0][7:]


def sig(tc):
    a = tc.get("arguments") or {}
    if isinstance(a, str):
        try:
            a = json.loads(a)
        except Exception:
            a = {"raw": a}
    n = tc.get("function_name")
    if n == "read_file":
        return (n, str(a.get("filepath") or a.get("path")), a.get("start_line") or a.get("offset"), a.get("end_line") or a.get("limit"))
    if n == "run_command":
        return (n, re.sub(r"\s+", " ", str(a.get("command") or ""))[:160])
    return (n, json.dumps(a, sort_keys=True)[:160])


def fileof(tc):
    a = tc.get("arguments") or {}
    if isinstance(a, str):
        try:
            a = json.loads(a)
        except Exception:
            return None
    n = tc.get("function_name")
    if n == "read_file":
        return str(a.get("filepath") or a.get("path"))
    if n == "run_command":
        m = re.search(r"(rich/[\w/\.]+\.py|[\w/\.]+\.py)", str(a.get("command") or ""))
        return m.group(1) if m else None
    return None


recs = []
for p in glob.glob(str(ROOT / "submit_*" / "**" / "trace_rich_*.json"), recursive=True):
    pp = Path(p)
    try:
        j = json.load(open(pp, encoding="utf-8"))
    except Exception:
        continue
    task = re.search(r"trace_(rich_\d+)", p).group(1)
    ver = version_of(pp)
    steps = [s for s in (j.get("steps") or []) if s.get("source") == "agent" and (s.get("metrics") or {}).get("prompt_tokens")]
    if len(steps) < 3:
        continue
    P = [s["metrics"]["prompt_tokens"] for s in steps]
    comp = [k for k in range(1, len(P)) if P[k] < P[k - 1] and P[k - 1] >= 13500]
    out = by_key.get((ver, task)) or {}
    recs.append(dict(task=task, ver=ver, steps=steps, P=P, comp=comp, res=bool(out.get("resolved")), tag=out.get("tag")))

# 1. within-task
bytask = collections.defaultdict(list)
for r in recs:
    bytask[r["task"]].append(r)
num = den = 0.0
var = 0.0
rows = []
for t, rs in sorted(bytask.items()):
    a = [r for r in rs if r["comp"]]
    b = [r for r in rs if not r["comp"]]
    if a and b:
        ra, rb = sum(r["res"] for r in a), sum(r["res"] for r in b)
        rows.append((t, len(a), ra, len(b), rb))
        n1, n0, m1 = len(a), len(b), ra + rb
        N = n1 + n0
        num += ra - n1 * m1 / N
        var += (n1 * n0 * m1 * (N - m1)) / (N * N * (N - 1)) if N > 1 else 0
print("tasks with BOTH compacted and non-compacted runs:", len(rows))
print(" task      comp(n,res)  nocomp(n,res)")
for t, n1, ra, n0, rb in rows:
    print(f" {t:10s}  {n1:2d} {ra:2d}       {n0:2d} {rb:2d}")
tot_a = sum(r[1] for r in rows)
tot_ra = sum(r[2] for r in rows)
tot_b = sum(r[3] for r in rows)
tot_rb = sum(r[4] for r in rows)
print(f" pooled within these tasks: compacted {tot_ra}/{tot_a} = {100*tot_ra/max(tot_a,1):.0f}%   not compacted {tot_rb}/{tot_b} = {100*tot_rb/max(tot_b,1):.0f}%")
print(f" Mantel-Haenszel: observed-expected resolved among compacted = {num:+.2f}, var = {var:.2f}, z = {num/ (var**0.5 if var>0 else 1):+.2f}")

# 2. post compaction prompt vs own first prompt
d = []
for r in recs:
    for k in r["comp"]:
        d.append((r["P"][k] - r["P"][0], r["P"][k], r["P"][0]))
print(f"\n2. compaction events: {len(d)}; post-compaction prompt minus this run's first-call prompt: median {st.median(x[0] for x in d):+.0f}, p10 {sorted(x[0] for x in d)[len(d)//10]:+.0f}, p90 {sorted(x[0] for x in d)[9*len(d)//10]:+.0f}; negative in {sum(1 for x in d if x[0] < 0)}/{len(d)}")

# 3a. control: exact-repeat rate in a 6-call window vs ALL earlier calls, window right after compaction vs right before it
#     vs the same call-index window in runs that never compacted
def flat_calls(r):
    seq, comp_pos = [], None
    for k, s in enumerate(r["steps"]):
        if r["comp"] and k == r["comp"][0] and comp_pos is None:
            comp_pos = len(seq)
        for tc in (s.get("tool_calls") or []):
            if tc.get("function_name") in ("get_status", "submit_patch", "edit_file"):
                continue
            seq.append(sig(tc))
    return seq, comp_pos


def window_rate(seq, s, w=6):
    win = seq[s:s + w]
    if len(win) < 3:
        return None
    prior = set(seq[:s])
    return sum(1 for x in win if x in prior), len(win)


agg = {"after compaction": [0, 0], "6 calls BEFORE compaction": [0, 0], "no-compaction runs, calls 13-18": [0, 0]}
for r in recs:
    seq, cp = flat_calls(r)
    if r["comp"] and cp is not None:
        a = window_rate(seq, cp)
        if a:
            agg["after compaction"][0] += a[0]
            agg["after compaction"][1] += a[1]
        if cp >= 8:
            b = window_rate(seq, cp - 6)
            if b:
                agg["6 calls BEFORE compaction"][0] += b[0]
                agg["6 calls BEFORE compaction"][1] += b[1]
    elif not r["comp"]:
        c = window_rate(seq, 12)
        if c:
            agg["no-compaction runs, calls 13-18"][0] += c[0]
            agg["no-compaction runs, calls 13-18"][1] += c[1]
print("\n3a. exact-repeat rate of read-type calls in a 6-call window (vs all earlier calls):")
for k, (a, b) in agg.items():
    print(f"   {k:36s} {a:3d}/{b:3d} = {100*a/max(b,1):4.0f}%")

# 3. repeats after compaction
rep_tot = new_tot = 0
file_rep = file_tot = 0
per_run = []
for r in recs:
    if not r["comp"]:
        continue
    k = r["comp"][0]
    before = set()
    files_before = set()
    for s in r["steps"][:k]:
        for tc in (s.get("tool_calls") or []):
            before.add(sig(tc))
            f = fileof(tc)
            if f:
                files_before.add(f)
    rep = new = fr = ft = 0
    cnt = 0
    for s in r["steps"][k:]:
        for tc in (s.get("tool_calls") or []):
            if tc.get("function_name") in ("get_status", "submit_patch", "edit_file"):
                continue
            if cnt >= 6:
                break
            cnt += 1
            if sig(tc) in before:
                rep += 1
            else:
                new += 1
            f = fileof(tc)
            if f:
                ft += 1
                if f in files_before:
                    fr += 1
    rep_tot += rep
    new_tot += new
    file_rep += fr
    file_tot += ft
    per_run.append((rep, rep + new))
print(f"\n3. first 6 non-edit calls after the first compaction (runs={len(per_run)}): exact repeats of a pre-compaction call {rep_tot}/{rep_tot+new_tot} = {100*rep_tot/max(rep_tot+new_tot,1):.0f}%;  same-FILE as before {file_rep}/{file_tot} = {100*file_rep/max(file_tot,1):.0f}%")
print("   runs with >=1 exact repeat:", sum(1 for a, b in per_run if a), "of", len(per_run))
