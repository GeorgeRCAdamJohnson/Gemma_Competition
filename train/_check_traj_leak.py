"""Leak check on the localization trajectories: is the grep QUERY symbol actually PRESENT in the
symptom the model sees? If the target greps for a symbol only visible in the gold PATCH (not the
problem statement), the LoRA learns an un-derivable action = useless/leaky target."""
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
traj = [json.loads(l) for l in open(os.path.join(HERE,"data","localization_traj_train.jsonl"),encoding="utf-8")]
curr = {json.loads(l)["instance_id"]: json.loads(l) for l in open(os.path.join(HERE,"data","localization_curriculum.jsonl"),encoding="utf-8")}

inq = 0; notinq = []
for r in traj:
    iid = r["instance_id"]
    symptom = curr[iid]["symptom"].lower()
    m = re.search(r"grep -rn '([^']+)'", r["messages"][1]["content"])
    q = m.group(1).lower() if m else ""
    if q and q in symptom:
        inq += 1
    else:
        notinq.append((iid, q))
n = len(traj)
print(f"grep-query symbol PRESENT in symptom: {inq}/{n} = {100*inq/n:.0f}%")
print(f"NOT present (target greps a symbol the model can't derive from the symptom): {len(notinq)}")
for iid, q in notinq[:15]:
    print(f"  {iid:16} query={q!r}")
