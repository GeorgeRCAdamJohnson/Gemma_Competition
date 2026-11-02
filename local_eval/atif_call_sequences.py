"""CPU-only: print the compact call sequence of each real 28-call-regime run, to see what the long pre-edit stretches are made of.
python atif_call_sequences.py [--tasks rich_4079,rich_3471] [--versions ...]
Token key: g=grep/find/ls via run_command, s=sed/head/cat/awk window via run_command, X=python/pytest via run_command,
W=write via run_command, R=read_file (with :start-end or :whole), E=edit_file (e=failed), Q=other tool (search/graph).
"""
import argparse, json, re
from pathlib import Path
import atif_behavior_outcomes as B

ROOT = B.ROOT


def tok(tn, args, content):
    if tn == "read_file":
        a, b = args.get("start_line"), args.get("end_line")
        return f"R:{args.get('filepath') or args.get('path')}:{a}-{b}" if (a or b) else f"R:{args.get('filepath') or args.get('path')}:whole"
    if tn in ("edit_file", "write_file"):
        return "E" if B.status_of(content) == "ok" else "e"
    if tn == "run_command":
        c = str(args.get("command", ""))
        if B.WRITE_CMD.search(c):
            return "W"
        if B.EXEC_CMD.search(c):
            return "X"
        if re.match(r"\s*(sed|head|tail|cat|awk|nl)\b", c):
            return "s"
        return "g"
    return "Q:" + tn


def seq(p):
    t = json.loads(p.read_text(encoding="utf-8"))
    out = []
    for s in t.get("steps", []):
        obs = s.get("observation")
        tcs = s.get("tool_calls") or []
        if s.get("source") != "agent" or not obs or not tcs:
            continue
        tn = (obs.get("extra") or {}).get("tool_name") or tcs[0].get("function_name")
        c = obs.get("content") or ""
        if tn in ("get_status", "submit_patch") or B.MALFORMED in c:
            continue
        out.append(tok(tn, tcs[0].get("arguments") or {}, c))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="rich_4079,rich_3471")
    ap.add_argument("--versions", default="v6b,v6c,v6s,v6t,v6v,v6w,v6x,v6y")
    a = ap.parse_args()
    tasks, want = set(a.tasks.split(",")), set(a.versions.split(","))
    for p in sorted(ROOT.glob("**/trace_rich_*.json")):
        if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
            continue
        v = B.version_of(p)
        task = re.search(r"trace_(rich_\d+)\.json", p.name).group(1)
        if v.split("/")[0] not in want or task not in tasks:
            continue
        r = B.analyse(p)
        o = B.OUTCOME.get((v, task))
        if r is None or o is None:
            continue
        s = seq(p)
        print(f"{task} {v:10} {'PASS' if o['resolved'] else 'fail'} first_edit={r['first_edit']}")
        print("   " + " ".join(s))


if __name__ == "__main__":
    main()
