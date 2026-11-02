"""CPU-only: which behaviours of the real 31B (Kaggle ATIF traces, 28-call regime) go with success WITHIN a task?
python atif_behavior_outcomes.py [--versions v6b,v6c,...] [--list]

Per trace: classify every counted tool call (read / exec / edit), derive binary behaviours, and compare resolved-rates
exposed vs unexposed with the task as the stratum (Mantel-Haenszel), because task difficulty dominates outcomes.
Strata where every run has the same outcome carry no information and are reported but contribute nothing.
"""
import argparse, collections, json, math, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = json.loads((ROOT / "local_eval" / "runs" / "kaggle_outcomes.json").read_text())
OUTCOME = {(r["version"], r["task"]): r for r in OUT}
# commands that WRITE source (python -c / heredoc only count when they open a file for writing)
WRITE_CMD = re.compile(r"(sed\s+-i|>\s*[\w./-]+\.py|cat\s*>|tee\s|git\s+apply|patch\s+-p|perl\s+-pi|write_text\(|\.write\(|open\([^)]*['\"][wa]\+?['\"])")
EXEC_CMD = re.compile(r"(pytest|python3?\s|python3?$|\bnode\b)")
MALFORMED = "mandatory input parameters"


def version_of(p):
    rel = p.relative_to(ROOT).parts
    if rel[0].startswith("submit_"):
        if len(rel) > 3 and rel[2] == "out":
            return f"{rel[0][7:]}/{rel[1]}"
        return rel[0][7:]
    return "/".join(rel[:-1]) or rel[0]


def status_of(content):
    m = re.search(r'"status":\s*"(\w+)"', content[:200])
    return m.group(1) if m else None


def analyse(p):
    t = json.loads(p.read_text(encoding="utf-8"))
    steps = t.get("steps", [])
    first_user = next((s.get("message") for s in steps if s.get("source") == "user"), "") or ""
    if "Tool calls allowance: 28 calls" not in first_user:
        return None
    n = 0
    kinds = []              # (n, kind, tool, status)
    submitted = False
    malformed = 0
    for s in steps:
        obs = s.get("observation")
        tcs = s.get("tool_calls") or []
        if s.get("source") != "agent" or not obs or not tcs:
            continue
        tn = (obs.get("extra") or {}).get("tool_name") or tcs[0].get("function_name")
        c = obs.get("content") or ""
        if tn == "submit_patch":
            submitted = True
            continue
        if tn == "get_status":
            continue
        if MALFORMED in c:
            malformed += 1
            continue
        n += 1
        args = tcs[0].get("arguments") or {}
        cmd = str(args.get("command", "")) if tn == "run_command" else ""
        if tn in ("edit_file", "write_file"):
            kind = "edit"
        elif tn == "run_command" and WRITE_CMD.search(cmd):
            kind = "edit"
        elif tn == "run_command" and EXEC_CMD.search(cmd):
            kind = "exec"
        else:
            kind = "read"
        kinds.append((n, kind, tn, status_of(c)))
    edits = [k for k in kinds if k[1] == "edit"]
    first_edit = edits[0][0] if edits else None
    pre = [k for k in kinds if first_edit is None or k[0] < first_edit]
    post = [k for k in kinds if first_edit is not None and k[0] > first_edit]
    ef = [k for k in kinds if k[2] == "edit_file"]
    return dict(
        calls=n, malformed=malformed, submitted=submitted, first_edit=first_edit, n_edits=len(edits),
        edit_file_err=sum(1 for k in ef if k[3] != "ok"), edit_file_n=len(ef),
        used_run_cmd_edit=any(k[2] == "run_command" for k in edits),
        used_edit_file=bool(ef),
        exec_before_edit=any(k[1] == "exec" for k in pre),
        exec_after_edit=any(k[1] == "exec" for k in post),
        n_exec=sum(1 for k in kinds if k[1] == "exec"),
        reads_before_edit=sum(1 for k in pre if k[1] == "read"),
    )


def mh(rows, pred):
    """Mantel-Haenszel across tasks. Returns dict with crude and stratified comparison of predicate-true vs false."""
    strata = collections.defaultdict(lambda: [0, 0, 0, 0])      # a b c d : exposed ok/fail, unexposed ok/fail
    for r in rows:
        k = strata[r["task"]]
        e = bool(pred(r))
        ok = bool(r["resolved"])
        k[(0 if e else 2) + (0 if ok else 1)] += 1
    A = B = C = D = 0
    num = den = 0.0
    sumd = sumv = 0.0
    rd_num = rd_w = 0.0
    inform = 0
    for t, (a, b, c, d) in strata.items():
        n = a + b + c + d
        A += a; B += b; C += c; D += d
        if (a + b) == 0 or (c + d) == 0 or n < 2:
            continue
        if (a + c) == 0 or (b + d) == 0:
            continue
        inform += 1
        num += a * d / n
        den += b * c / n
        sumd += a - (a + b) * (a + c) / n
        sumv += (a + b) * (c + d) * (a + c) * (b + d) / (n * n * (n - 1))
        w = (a + b) * (c + d) / n
        rd_num += w * (a / (a + b) - c / (c + d))
        rd_w += w
    z = None
    if sumv > 0:
        z = math.copysign(math.sqrt(max(0.0, (abs(sumd) - 0.5) ** 2 / sumv)), sumd)
    return dict(n_e=A + B, r_e=(A / (A + B)) if A + B else float("nan"), n_u=C + D,
                r_u=(C / (C + D)) if C + D else float("nan"),
                or_mh=(num / den) if den > 0 else float("nan"), z=z,
                rd=(rd_num / rd_w) if rd_w > 0 else float("nan"), inform=inform)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--versions", default="v6b,v6c,v6s,v6t,v6v,v6w,v6x,v6y")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    want = set(a.versions.split(","))
    rows = []
    for p in sorted(ROOT.glob("**/trace_rich_*.json")):
        if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
            continue
        v = version_of(p)
        if v.split("/")[0] not in want:
            continue
        try:
            r = analyse(p)
        except Exception as e:
            print("skip", p, e)
            continue
        if r is None:
            continue
        task = re.search(r"trace_(rich_\d+)\.json", p.name).group(1)
        o = OUTCOME.get((v, task))
        if o is None:
            continue
        r.update(version=v, task=task, resolved=bool(o["resolved"]), tag=o.get("tag", "?"))
        rows.append(r)
    print(f"runs analysed: {len(rows)}   resolved: {sum(r['resolved'] for r in rows)}")
    by_task = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        by_task[r["task"]][0 if r["resolved"] else 1] += 1
    print("per task [resolved, failed]:", {k: v for k, v in sorted(by_task.items())})
    print()
    feats = {
        "exec_before_edit (ran python/pytest before 1st edit)": lambda r: r["exec_before_edit"],
        "exec_after_edit (ran python/pytest after 1st edit)": lambda r: r["exec_after_edit"],
        "never ran python/pytest at all": lambda r: r["n_exec"] == 0,
        "first_edit <= 8": lambda r: r["first_edit"] is not None and r["first_edit"] <= 8,
        "first_edit <= 12": lambda r: r["first_edit"] is not None and r["first_edit"] <= 12,
        "first_edit > 18 or none": lambda r: r["first_edit"] is None or r["first_edit"] > 18,
        "reads_before_edit >= 8": lambda r: r["reads_before_edit"] >= 8,
        "used edit_file at all": lambda r: r["used_edit_file"],
        "edit via run_command (sed/python/heredoc)": lambda r: r["used_run_cmd_edit"],
        "any edit_file error": lambda r: r["edit_file_err"] > 0,
        "any malformed call (missing params)": lambda r: r["malformed"] > 0,
        "multiple edits (n_edits >= 3)": lambda r: r["n_edits"] >= 3,
        "submitted (called submit_patch)": lambda r: r["submitted"],
    }
    hdr = f"{'behaviour':54}{'n_exp':>6}{'rate':>7}{'n_unexp':>8}{'rate':>7}{'MH OR':>8}{'z':>7}{'RDstrat':>9}{'strata':>7}"
    print(hdr)
    for name, pred in feats.items():
        m = mh(rows, pred)
        zs = "  n/a" if m["z"] is None else f"{m['z']:+.2f}"
        print(f"{name:54}{m['n_e']:>6}{m['r_e']:>7.2f}{m['n_u']:>8}{m['r_u']:>7.2f}{m['or_mh']:>8.2f}{zs:>7}{m['rd']:>+9.2f}{m['inform']:>7}")
    if a.list:
        for r in sorted(rows, key=lambda r: (r["task"], r["version"])):
            print(r["task"], r["version"], r["resolved"], r["tag"], "calls", r["calls"], "first_edit", r["first_edit"],
                  "exec", r["n_exec"], "efErr", r["edit_file_err"], "sub", r["submitted"])


if __name__ == "__main__":
    main()
