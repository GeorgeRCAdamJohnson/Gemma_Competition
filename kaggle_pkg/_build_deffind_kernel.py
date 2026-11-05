"""Build kaggle_pkg/push_e4b_deffind: E4B definition-finder gate on the 7 target tasks + regression guards.

Single GPU (<=8-task-ish batch), ca5 + find-def skill. Fork of push_129_e4b with the deffind bundle
embedded (incl. skills tree), ca5 sha assert dropped, task list = the 7 ref-vs-def targets + 3 stable
E4B wins as regression guards.
"""
import base64
import json
import re
import shutil
from pathlib import Path

K = Path(__file__).resolve().parent
SRC = K / "push_129_e4b"
DST = K / "push_e4b_deffind"
BUNDLE = K.parent / "local_eval" / "parity_rig" / "agent_ctrl_e4b_deffind"
# 7 ref-vs-def targets (4 LOC-only + 3 content-hard, kept to see if finder helps the hard ones too)
TARGETS = ["rich_4077", "rich_3067", "rich_3480", "fastapi_14492", "fastapi_14372", "fastapi_14458", "fastapi_9555"]
# regression guards: stable E4B wins (must stay solved)
GUARDS = ["rich_3006", "rich_3905", "fastapi_14301"]
BATCH = TARGETS + GUARDS

assert BUNDLE.is_dir()
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir()

emb = {}
for p in sorted(BUNDLE.rglob("*")):
    if p.is_file() and "__pycache__" not in p.parts:
        emb[p.relative_to(BUNDLE).as_posix()] = base64.b64encode(p.read_bytes()).decode()
assert "skills/find-def/scripts/find_def.py" in emb and "prompts/system.md" in emb

nb = json.loads((SRC / "ca5-e4b-full129.ipynb").read_text(encoding="utf-8"))
cell2 = "".join(nb["cells"][2]["source"])
m = re.search(r'EMBED = json\.loads\("""(.*?)"""\)', cell2, re.S)
emb["tasks.jsonl_gz"] = json.loads(m.group(1))["tasks.jsonl_gz"]
cell2 = cell2.replace(m.group(0), 'EMBED = json.loads("""%s""")' % json.dumps(emb), 1)

old = re.search(r'AGENT = Path\("/kaggle/working/agent_ca5"\).*?assert sha == "b08b32a2438d".*?\n', cell2, re.S)
assert old
neww = '''AGENT = Path("/kaggle/working/agent_ca5")
if AGENT.exists(): shutil.rmtree(AGENT)
AGENT.mkdir(parents=True, exist_ok=True)
import hashlib as _h, ast as _ast
for _rel, _b64 in EMBED.items():
    if _rel == "tasks.jsonl_gz": continue
    _d = AGENT / _rel; _d.parent.mkdir(parents=True, exist_ok=True); _d.write_bytes(base64.b64decode(_b64))
    print(f"  {_rel}: {_d.stat().st_size} B")
for _py in AGENT.rglob("scripts/*.py"): _ast.parse(_py.read_text(encoding="utf-8")); print("  script OK:", _py.name)
for _s in AGENT.rglob("SKILL.md"): assert _s.read_bytes()[:3] == b"---", _s
sha = _h.sha1((AGENT/"prompts"/"system.md").read_bytes()).hexdigest()[:12]
print("deffind prompt sha:", sha)
'''
cell2 = cell2.replace(old.group(0), neww, 1)
nb["cells"][2]["source"] = cell2.splitlines(keepends=True)

cell4 = "".join(nb["cells"][4]["source"])
anchor = 'all_ids = [json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()]'
cell4 = cell4.replace(anchor,
    "BATCH = %s\n" % json.dumps(BATCH) +
    'all_ids = [i for i in (json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()) if i in set(BATCH)]',
    1).replace('CONC = "10"', 'CONC = "3"').replace("CHUNK = 20", "CHUNK = 10")
nb["cells"][4]["source"] = cell4.splitlines(keepends=True)

nb["cells"][0]["source"] = [
    "# E4B DEFINITION-FINDER gate - 7 ref-vs-def targets + 3 regression guards\n",
    "Does a deterministic find-def skill convert the LOC-only targets (rich_4077/3067/3480, fastapi_14492)?\n",
]
(DST / "e4b-deffind.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
meta = json.loads((SRC / "kernel-metadata.json").read_text(encoding="utf-8"))
meta.update(id="comfyops/e4b-deffind", title="e4b deffind", code_file="e4b-deffind.ipynb")
(DST / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("wrote", DST, "| batch", BATCH)
