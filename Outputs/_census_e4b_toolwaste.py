"""E4B pack-1: which tool calls add no value, and what they cost (calls, wall time, turns), split by outcome.

Each tool call is charged the time from its log timestamp to the NEXT event's timestamp: that covers the tool's own
execution plus the model turn it triggers (the model reading the result and deciding what to do next).
Categories (fixer only; the verifier is reported separately as fixed overhead):
  get_status              free in the call budget, but each costs a turn; the budget never binds (median 10 of 80)
  edit_fail               edit_file/write_file that returned an error (old_string not found, no-op, arg error)
  edit_nonsrc             edit/write to a non-.py file (toml/md/yaml/cff/LICENSE): the gate rejects / undo misses
  read_repeat             read_file of a path already read in the same attempt (no new information)
  read_first              first read_file of a path (useful, but returns the WHOLE file into context)
  cmd_error               run_command whose result line is an error
  cmd_repeat              run_command identical to an earlier one in the same attempt
  cmd_ok                  other run_command
  edit_ok                 successful edit
  graph                   get_code_* / search_similar_code
"""
import json
import re
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

R = Path("Outputs/e4b_pack1_val/results")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
TS = re.compile(r"^\s*(?:\u2502 \(verifier\) )?\s*\[\s*([\d.]+)s\]")
EV = re.compile(r"^\s*\[\s*([\d.]+)s\]\s+(\S+)\s+(\w+)(.*)$")


def parse(log, ver_marker="(verifier)"):
    """yield (t, tool, arg, result_line, is_verifier, attempt_idx) for every tool call line."""
    lines = log.splitlines()
    out, attempt = [], 0
    for i, ln in enumerate(lines):
        if "Agent finished: RETRY" in ln:
            attempt += 1
        ver = ver_marker in ln
        s = ln.replace("\u2502 (verifier) ", "").replace("\u2502", "")
        m = EV.match(s)
        if not m:
            continue
        t, icon, tool, rest = float(m.group(1)), m.group(2), m.group(3), m.group(4)
        if tool not in ("get_status", "read_file", "edit_file", "write_file", "run_command", "run_skill_script",
                        "submit_patch", "get_code_neighbors", "get_code_subgraph", "search_similar_code", "load_skill"):
            continue
        res = lines[i + 1] if i + 1 < len(lines) else ""
        # next event time (any timestamped line after the result)
        nt = None
        for j in range(i + 1, min(i + 8, len(lines))):
            mm = TS.match(lines[j].replace("\u2502 (verifier) ", "").replace("\u2502", ""))
            if mm and float(mm.group(1)) >= t and j > i + 1:
                nt = float(mm.group(1))
                break
        out.append(dict(t=t, nt=nt, tool=tool, arg=rest.strip(), res=res, ver=ver, attempt=attempt))
    return out


def classify(calls):
    seen_read, seen_cmd = defaultdict(set), defaultdict(set)
    for c in calls:
        tool, arg, res, a = c["tool"], c["arg"], c["res"], c["attempt"]
        if c["ver"]:
            c["cat"] = "verifier"
        elif tool == "get_status":
            c["cat"] = "get_status"
        elif tool in ("edit_file", "write_file"):
            path = arg.strip("() ").split(",")[0].strip()
            ok = "\u2713" in res and "'status': 'ok'" in res
            if not path.endswith(".py"):
                c["cat"] = "edit_nonsrc"
            else:
                c["cat"] = "edit_ok" if ok else "edit_fail"
        elif tool == "read_file":
            path = arg.strip("() ")
            # identity = path + the start of the returned content (a read of a DIFFERENT region is new information)
            m = re.search(r"'content': '(.{0,80})", res)
            key = (path, m.group(1) if m else res[:120])
            if key in seen_read[a]:
                c["cat"] = "read_repeat"
            elif any(k[0] == path for k in seen_read[a]):
                c["cat"] = "read_region"
            else:
                c["cat"] = "read_first"
            seen_read[a].add(key)
        elif tool == "run_command":
            if "error" in res[:40] or "\u274c" in res:
                c["cat"] = "cmd_error"
            elif arg in seen_cmd[a]:
                c["cat"] = "cmd_repeat"
            else:
                c["cat"] = "cmd_ok"
            seen_cmd[a].add(arg)
        elif tool.startswith("get_code") or tool == "search_similar_code":
            c["cat"] = "graph"
        else:
            c["cat"] = "other:" + tool
        c["cost"] = max(0.0, (c["nt"] - c["t"])) if c["nt"] is not None else 0.0
    return calls


runs = []
for tr in sorted(R.glob("node*/run_*/task_results.jsonl")):
    d = tr.parent
    kind = "runtime90" if (d.parent.name == "node0" and d.name == "run_1") else "score39"
    for l in tr.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        lp = d / "logs" / f"{r['instance_id']}.log"
        if not lp.exists():
            continue
        log = ANSI.sub("", lp.read_text(encoding="utf-8", errors="replace"))
        e = str(r.get("error") or "")
        b = "solved" if r["resolved"] else "overflow" if "ContextWindow" in e else "failed"
        runs.append(dict(r=r, b=b, kind=kind, calls=classify(parse(log)), dur=r.get("duration_seconds") or 0))

WASTE = ("get_status", "edit_fail", "edit_nonsrc", "read_repeat", "cmd_error", "cmd_repeat", "graph")
for kind in ("score39", "runtime90"):
    K = [x for x in runs if x["kind"] == kind]
    allc = [c for x in K for c in x["calls"]]
    tot_n = len(allc)
    tot_t = sum(c["cost"] for c in allc)
    tot_dur = sum(x["dur"] for x in K)
    print(f"\n=== {kind}: {len(K)} runs, {tot_n} tool calls, {tot_t/3600:.2f} h charged to calls "
          f"(sum of run durations {tot_dur/3600:.2f} h)")
    cnt = Counter(c["cat"] for c in allc)
    tim = defaultdict(float)
    for c in allc:
        tim[c["cat"]] += c["cost"]
    print(f"  {'category':12s} {'calls':>6s} {'%calls':>6s} {'hours':>6s} {'%time':>6s} {'s/call':>6s}")
    for cat, n in cnt.most_common():
        mark = "  <- no value" if cat in WASTE else ""
        print(f"  {cat:12s} {n:6d} {100*n/tot_n:5.1f}% {tim[cat]/3600:6.2f} {100*tim[cat]/max(1,tot_t):5.1f}% "
              f"{tim[cat]/n:6.1f}{mark}")
    wn = sum(cnt[c] for c in WASTE)
    wt = sum(tim[c] for c in WASTE)
    print(f"  NO-VALUE TOTAL: {wn} calls ({100*wn/tot_n:.0f}%), {wt/3600:.2f} h ({100*wt/max(1,tot_t):.0f}% of charged time, "
          f"{100*wt/max(1,tot_dur):.0f}% of run time)")
    # by outcome: does waste concentrate in losing runs?
    for b in ("solved", "failed", "overflow"):
        xs = [x for x in K if x["b"] == b]
        if not xs:
            continue
        w = [sum(1 for c in x["calls"] if c["cat"] in WASTE) for x in xs]
        wtime = [sum(c["cost"] for c in x["calls"] if c["cat"] in WASTE) for x in xs]
        rr = [sum(1 for c in x["calls"] if c["cat"] == "read_repeat") for x in xs]
        rf = [sum(1 for c in x["calls"] if c["cat"] in ("read_first", "read_repeat")) for x in xs]
        print(f"  {b:8s} n={len(xs):3d}: no-value calls/run median {st.median(w):4.1f} mean {st.mean(w):4.1f} | "
              f"no-value time/run median {st.median(wtime):5.0f}s | read_file/run mean {st.mean(rf):4.1f} "
              f"(repeats {st.mean(rr):4.1f}) | dur median {st.median(x['dur'] for x in xs):5.0f}s")

# runtime budget view: the scorer runs all 129 sequentially; pack 1 estimate was 10.7 h of task time (12 h limit)
S = [x for x in runs if x["kind"] == "score39"]
R90 = [x for x in runs if x["kind"] == "runtime90"]
def nv(xs, cats):
    return sum(c["cost"] for x in xs for c in x["calls"] if c["cat"] in cats)
per_pass39 = nv(S, WASTE) / 7
print(f"\nScorer-time view: no-value time per 39-task pass {per_pass39/60:.0f} min; on the 90 never-solved tasks "
      f"{nv(R90, WASTE)/60:.0f} min. Full-129 estimate saved if ALL no-value calls vanished: "
      f"{(per_pass39 + nv(R90, WASTE))/3600:.2f} h of the ~10.7 h.")
for cat in WASTE:
    print(f"  {cat:12s}: {(nv(S, (cat,))/7 + nv(R90, (cat,)))/60:5.0f} min per full 129")
