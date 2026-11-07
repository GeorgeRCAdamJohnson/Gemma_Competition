"""Build kaggle_pkg/push_e4b_cap_ab: E4B PER-NODE cap A/B on the 85 live tasks.

  node0,node1 = ARM A: ca5 E4B, eval_config 40 calls / 12 min / 120 turns
  node2,node3 = ARM B: ca5 E4B, eval_config 50 calls / 20 min / 120 turns

Forks push_e4b_ab_pernode (1 tp=1 E4B server per L4, each node runs its own full passes, no barrier).
Fixes the old CRLF/LF confound: BOTH arms use the LF 31B ca5 bytes (system.md sha1 b08b32a2438d,
LF sampling/agent) with ONLY the agent.yaml model line swapped to gemma-4-e4b-it-qat-w4a16-ct. So the
two arms differ in eval_config only. Task list = the 85 live ids (live_ids_31b_ab.json).
Output: variance_ab.json (same schema as the per-node A/B) + per-pass forensics for pass 1.
"""
import base64
import gzip
import hashlib
import json
import re
import shutil
from pathlib import Path

K = Path(__file__).resolve().parent
SRC = K / "push_e4b_ab_pernode"
DST = K / "push_e4b_cap_ab"
SLUG = "e4b-cap-ab"
BUDGET_SECONDS = int(3.5 * 3600)
ARMS_CFG = {"ARM_A_cap40_12": (40, 12, 120), "ARM_B_cap50_20": (50, 20, 120)}

live = json.loads((K / "live_ids_31b_ab.json").read_text(encoding="utf-8"))["order"]
assert len(live) == 85

pn = json.loads((SRC / "e4b-ab-pernode.ipynb").read_text(encoding="utf-8"))
c2 = "".join(pn["cells"][2]["source"])
m = re.search(r'ARMS = json\.loads\("""(.*?)"""\)', c2, re.S)
old_arms = json.loads(m.group(1))
o31 = json.loads((K / "push_129_off31" / "ca5-31b-full129.ipynb").read_text(encoding="utf-8"))
e31 = json.loads(re.search(r'EMBED = json\.loads\("""(.*?)"""\)', "".join(o31["cells"][2]["source"]), re.S).group(1))

dec = lambda k: base64.b64decode(e31[k])
sys_md = dec("system.md")
assert hashlib.sha1(sys_md).hexdigest()[:12] == "b08b32a2438d" and b"\r" not in sys_md
agent = dec("agent.yaml").decode()
assert agent.count("model: gemma-4-31b-it-qat-w4a16-ct") == 1
agent_e4b = agent.replace("model: gemma-4-31b-it-qat-w4a16-ct", "model: gemma-4-e4b-it-qat-w4a16-ct")
# parity: E4B per-node control agent.yaml must equal ours after CRLF->LF
old_ag = base64.b64decode(old_arms["ARM_A_control"]["agent.yaml"]).replace(b"\r\n", b"\n").decode()
assert old_ag == agent_e4b, "E4B agent.yaml differs from 31B beyond the model line"
samp = dec("sampling.yaml")
assert base64.b64decode(old_arms["ARM_A_control"]["sampling.yaml"]).replace(b"\r\n", b"\n") == samp
tasks_gz = old_arms["ARM_A_control"]["tasks.jsonl_gz"]
assert sum(1 for l in gzip.decompress(base64.b64decode(tasks_gz)).splitlines() if l.strip()) == 129

b64 = lambda b: base64.b64encode(b).decode()
new_arms = {}
for arm, (c, mi, t) in ARMS_CFG.items():
    ev = f"evaluation:\n  max_time_minutes: {mi}\n  max_tool_calls: {c}\n  max_turns: {t}\n  timeout_seconds: 300\n"
    new_arms[arm] = {"system.md": b64(sys_md), "agent.yaml": b64(agent_e4b.encode()),
                     "sampling.yaml": b64(samp), "eval_config.yaml": b64(ev.encode())}
first = list(ARMS_CFG)[0]
new_arms[first]["tasks.jsonl_gz"] = tasks_gz
c2 = c2.replace(m.group(0), 'ARMS = json.loads("""%s""")' % json.dumps(new_arms), 1)
c2 = c2.replace('ARMS["ARM_A_control"]["tasks.jsonl_gz"]', f'ARMS["{first}"]["tasks.jsonl_gz"]')
c2 = c2.replace('AGENT = AGENT_DIRS["ARM_A_control"]', f'AGENT = AGENT_DIRS["{first}"]')
assert "ARM_A_control" not in c2 and "ARM_B_sibling" not in c2, "stale arm name left in cell 2"
compile(c2, "cell2", "exec")
pn["cells"][2]["source"] = c2.splitlines(keepends=True)

c4 = "".join(pn["cells"][4]["source"])
c4 = c4.replace("BUDGET_SECONDS = 10800", f"BUDGET_SECONDS = {BUDGET_SECONDS}")
c4 = c4.replace('NODE_ARM = {0: "ARM_A_control", 1: "ARM_A_control", 2: "ARM_B_sibling", 3: "ARM_B_sibling"}',
                'NODE_ARM = {0: "ARM_A_cap40_12", 1: "ARM_A_cap40_12", 2: "ARM_B_cap50_20", 3: "ARM_B_cap50_20"}')
old_ids = 'ALL_IDS = [json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()]'
assert old_ids in c4
c4 = c4.replace(old_ids, old_ids + "\nLIVE = %s\nassert set(LIVE) <= set(ALL_IDS) and len(LIVE) == 85\nALL_IDS = LIVE" % json.dumps(live))
c4 = c4.replace("# ---------- PER-NODE A/B: node0/1 = ARM_A control, node2/3 = ARM_B sibling. No cross-node barrier. ----------",
                "# ---------- E4B PER-NODE CAP A/B: node0/1 = 40/12, node2/3 = 50/20, 85 live tasks. No cross-node barrier. ----------")
assert "ARM_A_control" not in c4 and "BUDGET_SECONDS = %d" % BUDGET_SECONDS in c4 and "ALL_IDS = LIVE" in c4
compile(c4, "cell4", "exec")
pn["cells"][4]["source"] = c4.splitlines(keepends=True)
pn["cells"][0]["source"] = [
    "# E4B PER-NODE CAP A/B: ca5 (LF) 40/12 (node0,1) vs 50/20 (node2,3), 85 live tasks, ~3.5h\n",
    "Companion to comfyops/ca5-31b-cap-ab. Arms differ ONLY in eval_config.yaml.\n",
]
for c in pn["cells"]:
    if c.get("cell_type") == "code":
        c["outputs"] = []; c["execution_count"] = None
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir()
(DST / f"{SLUG}.ipynb").write_text(json.dumps(pn, indent=1, ensure_ascii=False), encoding="utf-8")
meta = json.loads((SRC / "kernel-metadata.json").read_text(encoding="utf-8"))
meta.pop("id_no", None)
meta.update(id=f"comfyops/{SLUG}", title=SLUG.replace("-", " "), code_file=f"{SLUG}.ipynb")
(DST / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("wrote", DST, "| arms", ARMS_CFG, "| live", len(live), "| budget h", BUDGET_SECONDS / 3600)
