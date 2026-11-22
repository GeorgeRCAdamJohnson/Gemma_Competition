"""Diagnose every ContextWindowExceeded in e4b-repro-ab passes 1-2: which agent was active, prompt size at failure,
what filled the context (thought chars, read_file count, tool-output chars), and which attempt/iteration it was."""
import glob
import json
import re
from collections import Counter, defaultdict

A = re.compile(r"\x1b\[[0-9;]*m")
NODE_ARM = {"node0": "F", "node1": "F", "node2": "R", "node3": "R"}
tot = defaultdict(Counter)
detail = defaultdict(list)
for f in sorted(glob.glob("Outputs/e4b_repro_ab/results/node*/run_*/task_results.jsonl")):
    node = f.split("/")[-3] if "/" in f else f.split("\\")[-3]
    node = re.search(r"node\d", f).group(0)
    arm = NODE_ARM[node]
    for l in open(f):
        if not l.strip():
            continue
        r = json.loads(l)
        tot[arm]["runs"] += 1
        err = str(r.get("error") or "")
        if "ContextWindow" not in err:
            continue
        tot[arm]["overflow"] += 1
        m = re.search(r"prompt contains at least (\d+) input tokens", err)
        ptok = int(m.group(1)) if m else None
        log = A.sub("", open(f.replace("task_results.jsonl", "logs/%s.log" % r["instance_id"]),
                             encoding="utf-8", errors="replace").read())
        agents = re.findall(r"\((tester|fixer|verifier)\)", log)
        last = agents[-1] if agents else "?"
        thought = sum(int(x) for x in re.findall(r"\((tester|fixer|verifier)\) \S+ \((\d+) chars\)", log) and
                      [c for _, c in re.findall(r"\((tester|fixer|verifier)\) \S+ \((\d+) chars\)", log)])
        reads = len(re.findall(r"read_file \(", log))
        retries = log.count("RETRY")
        n_ver = len(re.findall(r"\(verifier\) .*run_skill_script|\(verifier\) .*submit-gate", log))
        tot[arm]["active_" + last] += 1
        detail[arm].append((r["instance_id"], last, ptok, thought, reads, retries, r.get("tool_calls")))
for arm in ("F", "R"):
    t = tot[arm]
    print(f"== ARM {arm}: {t['overflow']}/{t['runs']} overflow | active agent at failure: "
          f"fixer {t['active_fixer']}, tester {t['active_tester']}, verifier {t['active_verifier']}")
    d = detail[arm]
    if d:
        pt = [x[2] for x in d if x[2]]
        print(f"   prompt tokens at failure: min {min(pt)} median {sorted(pt)[len(pt)//2]} max {max(pt)}")
        print(f"   model text (thought/answer) chars in log: median {sorted(x[3] for x in d)[len(d)//2]}")
        print(f"   read_file calls: median {sorted(x[4] for x in d)[len(d)//2]} | RETRY mentions median "
              f"{sorted(x[5] for x in d)[len(d)//2]} | tool_calls median {sorted((x[6] or 0) for x in d)[len(d)//2]}")
        print("   by task:", Counter(x[0] for x in d).most_common(8))
