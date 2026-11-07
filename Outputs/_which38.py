"""Which task set has 38 members? Candidates built from every per-task source we have."""
import glob
import json
from collections import defaultdict

live = json.load(open("kaggle_pkg/live_ids_31b_ab.json"))["order"]
L = set(live)
ever39 = set(json.load(open("Outputs/_solvable85.json"))["ever"])
v7 = {r["task"] for r in json.load(open("Outputs/v7_31b_full129/_cap_sim_rows.json")) if r["resolved"]}
ab = json.load(open("Outputs/ca5_31b_ab/ab31.json"))["rows"]
ab_any = {r["id"] for r in ab if r["resolved"]}
cap = {r["id"] for r in json.load(open("Outputs/ca5_31b_cap_ab/cap_ab.json"))["rows"] if r["resolved"]}
e4b = set()
for f in ("Outputs/e4b_cap_ab/variance_ab.json", "Outputs/e4b_repro_ab/variance_ab.json",
          "Outputs/e4b_pack1_val/variance_ab.json", "Outputs/e4b_pack2_val/variance_ab.json"):
    for p in json.load(open(f))["passes"]:
        e4b |= {r["id"] for r in p["rows"] if r["resolved"]}
b31 = (v7 | ab_any | cap)
cands = {
    "ever-solved (old, 39)": ever39,
    "ever-solved incl. today's E4B passes (live)": (b31 | e4b) & L,
    "31B ever-solved (live)": b31 & L,
    "31B ever-solved (all 129)": b31,
    "E4B ever-solved (live)": e4b & L,
    "31B v7 solved (all 129)": v7,
    "31B A/B any-arm solved": ab_any,
}
for k, s in cands.items():
    print(f"{len(s):3d}  {k}")
new = ((b31 | e4b) & L) - ever39
print("\nlive tasks newly solved since the 39 were defined:", sorted(new))
print("in old 39 but not solved by 31B ever:", sorted(ever39 - b31))
