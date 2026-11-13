# Runs ON the batch-6 VM: live intel from /content/ab6 (finished passes AND the pass in progress -- a trace is written as
# each task finishes). Per arm: paired solves; per trace: skill load errors, did the fixer call `locate`, was the gold
# file in locate's list / #1, which file was edited FIRST and was it the gold file. Gold files = `+++ b/` of the gold patch.
import json
import re
import statistics as st
from collections import defaultdict
from pathlib import Path

OUT = Path("/content/ab6")
gold = {}
for line in Path("/content/work/tasks.jsonl").read_text().splitlines():
    if line.strip():
        r = json.loads(line)
        gold[r["instance_id"]] = set(re.findall(r"^\+\+\+ b/(\S+)", r.get("patch", ""), re.M))

lg = Path("/content/ab6.log")
print("== driver:", *(lg.read_text(errors="replace").splitlines()[-3:] if lg.exists() else ["no log"]), sep="\n  ")
pg = OUT / "progress.json"
P = json.loads(pg.read_text())["passes"] if pg.exists() else []
by = {(p["round"], p["arm"]): p for p in P}
print("== finished passes:", [(p["round"], p["arm"], f"{p['solved']}/{p['n']}", f"{p['seconds'] / 60:.0f}m") for p in P])
rounds = sorted({r for r, _ in by if (r, "C_pack1") in by and (r, "L_loc") in by})
if rounds:
    d = [by[(r, "L_loc")]["solved"] - by[(r, "C_pack1")]["solved"] for r in rounds]
    print(f"== paired rounds {len(rounds)}: L-C per pass {d} mean {st.mean(d):+.2f}")

stats = defaultdict(lambda: defaultdict(int))
rows = []
for tr in sorted(OUT.glob("*/round_*/**/trace_*.json")):
    arm, rnd = tr.parts[3], tr.parts[4]
    tid = tr.stem[len("trace_"):]
    try:
        steps = json.loads(tr.read_text())["steps"]
    except Exception:
        continue
    s = stats[arm]
    s["traces"] += 1
    txt = json.dumps(steps)
    if "Failed to load skill" in txt:
        s["skill_load_error"] += 1
    called, loc_out, first_edit = False, "", None
    for st_ in steps:
        for t in st_.get("tool_calls") or []:
            a = t.get("arguments") or {}
            if t["function_name"] == "run_skill_script" and a.get("skill_name") == "locate":
                called = True
                loc_out = (st_.get("observation") or {}).get("content", "")
            if first_edit is None and t["function_name"] in ("edit_file", "write_file") and a.get("filepath"):
                first_edit = a["filepath"].replace("/workspace/", "").lstrip("./")
    g = gold.get(tid, set())
    s["called_locate"] += called
    in_list = called and any(f in loc_out for f in g)
    top1 = False
    if called:
        m = re.search(r"([\w./-]+\.py)", loc_out)
        top1 = bool(m and m.group(1).lstrip("./") in g)
    s["gold_in_locate_list"] += in_list
    s["gold_is_locate_top1"] += top1
    s["edited"] += first_edit is not None
    s["first_edit_gold"] += first_edit in g
    rows.append((arm, rnd, tid, called, in_list, top1, first_edit, first_edit in g))

print("== per-arm trace stats")
for arm, s in sorted(stats.items()):
    print(f"  {arm:8s}", dict(s))
print("== L_loc traces (task | locate called | gold in list | gold #1 | first edit | first edit = gold)")
for r in rows:
    if r[0] == "L_loc":
        print(f"  {r[1]:8s} {r[2]:14s} {str(r[3]):5s} {str(r[4]):5s} {str(r[5]):5s} {str(r[6])[:40]:40s} {r[7]}")
if any(r[0] == "L_loc" and r[3] for r in rows):
    ex = next(r for r in rows if r[0] == "L_loc" and r[3])
    print("== sample locate output for", ex[2])
for tr in sorted(OUT.glob("L_loc/round_*/**/trace_*.json"))[:1]:
    for st_ in json.loads(tr.read_text())["steps"]:
        for t in st_.get("tool_calls") or []:
            if t["function_name"] == "run_skill_script":
                print("  args:", json.dumps(t.get("arguments"))[:300])
                print("  out :", (st_.get("observation") or {}).get("content", "")[:700])
