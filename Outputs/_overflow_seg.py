"""For each overflow, measure the FINAL segment (events since the last message from a different agent) - that is
exactly what an include_contents:none agent sees. Count model turns, model-text chars, read_file calls and
run_command calls in it; also the whole-log totals (what an include_contents:default agent sees)."""
import glob
import json
import re
from collections import defaultdict

A = re.compile(r"\x1b\[[0-9;]*m")
TAG = re.compile(r"\((tester|fixer|verifier)\) (\S+) ?(.*)")
NODE_ARM = {"node0": "F", "node1": "F", "node2": "R", "node3": "R"}
out = defaultdict(list)
for f in sorted(glob.glob("Outputs/e4b_repro_ab/results/node*/run_*/task_results.jsonl")):
    arm = NODE_ARM[re.search(r"node\d", f).group(0)]
    for l in open(f):
        if not l.strip():
            continue
        r = json.loads(l)
        overflow = "ContextWindow" in str(r.get("error") or "")
        log = A.sub("", open(f.replace("task_results.jsonl", "logs/%s.log" % r["instance_id"]),
                             encoding="utf-8", errors="replace").read())
        ev = []
        for line in log.splitlines():
            m = TAG.search(line)
            if m:
                ev.append((m.group(1), line))
        if not ev:
            continue
        last = ev[-1][0]
        seg = []
        for a, line in reversed(ev):
            if a != last:
                break
            seg.append(line)

        def stats(lines):
            chars = sum(int(x) for x in re.findall(r"💭 \((\d+) chars\)", "\n".join(lines)))
            return dict(turns=sum("💭" in x for x in lines), chars=chars,
                        reads=sum("read_file (" in x for x in lines), cmds=sum("run_command" in x for x in lines),
                        edit_err=sum("❌" in x for x in lines))
        out[(arm, last, overflow)].append((r["instance_id"], stats(seg), stats([x for _, x in ev])))


def med(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else "-"


print("%-3s %-9s %-8s %4s | %-44s | %-30s" % ("arm", "agent", "overflow", "n", "FINAL SEGMENT med: turns chars reads cmds errs",
                                              "WHOLE LOG med: turns chars reads"))
for (arm, agent, ov), v in sorted(out.items()):
    s = [x[1] for x in v]
    w = [x[2] for x in v]
    print("%-3s %-9s %-8s %4d | %5s %7s %5s %5s %5s %17s | %5s %7s %5s" % (
        arm, agent, ov, len(v), med([x["turns"] for x in s]), med([x["chars"] for x in s]), med([x["reads"] for x in s]),
        med([x["cmds"] for x in s]), med([x["edit_err"] for x in s]), "", med([x["turns"] for x in w]),
        med([x["chars"] for x in w]), med([x["reads"] for x in w])))
