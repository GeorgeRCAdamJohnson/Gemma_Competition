"""Build kaggle_pkg/push_e4b_verify_guard: SINGLE-GPU small-batch gate for the verify guardrail bundle.

Per the 2026-11-02 timing finding, <=8-task batches run best on ONE GPU (one ~300s boot beats four).
So this uses the STOCK single-tp=1 serve path (fork of push_e4b_verify_batch) with the guardrail bundle
embedded and the same 6-task batch -> a clean A/B vs the plain-verify run (also 1-GPU-equivalent / same
tasks): does MIRROR-SIBLING + SMALLEST-DIFF repair convert rich_4077 and/or rich_3894?

Only diff vs _build_verify_kernel.py: the embedded bundle is agent_ctrl_e4b_verify_guard, and the kernel
id/title. Everything else identical (model, wheelhouse, snapshots, caps 28/8, subprocess).
"""
import base64
import json
import re
import shutil
from pathlib import Path

K = Path(__file__).resolve().parent
SRC = K / "push_129_e4b"
DST = K / "push_e4b_verify_guard"
BUNDLE = K.parent / "local_eval" / "parity_rig" / "agent_ctrl_e4b_verify_guard"

BATCH_IDS = ["rich_4077", "rich_3894", "rich_3006", "rich_3905", "fastapi_14301", "fastapi_14463"]

assert BUNDLE.is_dir(), f"bundle missing: {BUNDLE} (run _build_verify_guard.py)"
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir()

emb = {}
for p in sorted(BUNDLE.rglob("*")):
    if p.is_file() and "__pycache__" not in p.parts:
        emb[p.relative_to(BUNDLE).as_posix()] = base64.b64encode(p.read_bytes()).decode()
assert "skills/verify-fix/scripts/verify.py" in emb and "prompts/system.md" in emb

nb = json.loads((SRC / "ca5-e4b-full129.ipynb").read_text(encoding="utf-8"))
cell2 = "".join(nb["cells"][2]["source"])
m_embed = re.search(r'EMBED = json\.loads\("""(.*?)"""\)', cell2, re.S)
emb["tasks.jsonl_gz"] = json.loads(m_embed.group(1))["tasks.jsonl_gz"]
cell2 = cell2.replace(m_embed.group(0), 'EMBED = json.loads("""%s""")' % json.dumps(emb), 1)

old_write = re.search(
    r'AGENT = Path\("/kaggle/working/agent_ca5"\).*?assert sha == "b08b32a2438d".*?\n', cell2, re.S)
assert old_write
new_write = '''AGENT = Path("/kaggle/working/agent_ca5")
if AGENT.exists():
    shutil.rmtree(AGENT)
AGENT.mkdir(parents=True, exist_ok=True)
import hashlib as _hashlib, ast as _ast
for _rel, _b64 in EMBED.items():
    if _rel == "tasks.jsonl_gz":
        continue
    _dst = AGENT / _rel
    _dst.parent.mkdir(parents=True, exist_ok=True)
    _dst.write_bytes(base64.b64decode(_b64))
    print(f"  {_rel}: {_dst.stat().st_size} B <- embedded")
for _py in AGENT.rglob("scripts/*.py"):
    _ast.parse(_py.read_text(encoding="utf-8")); print(f"  script OK: {_py.relative_to(AGENT)}")
sha = _hashlib.sha1((AGENT / "prompts" / "system.md").read_bytes()).hexdigest()[:12]
print("agent prompt sha (verify_guard):", sha)
for _sm in AGENT.rglob("SKILL.md"):
    assert _sm.read_bytes()[:3] == b"---", f"SKILL.md must start with ---: {_sm}"
'''
cell2 = cell2.replace(old_write.group(0), new_write, 1)
nb["cells"][2]["source"] = cell2.splitlines(keepends=True)

cell4 = "".join(nb["cells"][4]["source"])
anchor = 'all_ids = [json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()]'
cell4 = cell4.replace(
    anchor,
    "BATCH_IDS = %s\n" % json.dumps(BATCH_IDS) +
    'all_ids = [i for i in (json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()) if i in set(BATCH_IDS)]',
    1)
cell4 = cell4.replace('CONC = "10"', 'CONC = "3"').replace("CHUNK = 20", "CHUNK = 10")
nb["cells"][4]["source"] = cell4.splitlines(keepends=True)

nb["cells"][0]["source"] = [
    "# E4B VERIFY GUARDRAIL gate (single GPU, 6-task A/B vs plain verify)\n",
    "Repair rule = MIRROR THE SIBLING + SMALLEST DIFF. Does it convert rich_4077 / rich_3894?\n",
]
(DST / "e4b-verify-guard.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
meta = json.loads((SRC / "kernel-metadata.json").read_text(encoding="utf-8"))
meta.update(id="comfyops/e4b-verify-guard", title="e4b verify guard", code_file="e4b-verify-guard.ipynb")
(DST / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("wrote", DST, "| batch", BATCH_IDS)
