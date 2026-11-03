"""Build kaggle_pkg/push_e4b_verify_batch: a SMALL-BATCH E4B gate for the verify-fix skill bundle.

Forks push_129_e4b (the known-good ca5 E4B full-129 kernel) and makes exactly these changes:
  1. Re-embed the agent dir from local_eval/parity_rig/agent_ctrl_e4b_verify, INCLUDING the skills/ tree
     (SKILL.md + scripts/verify.py). The stock kernel embeds only 4 flat files; we extend EMBED + the
     materialize loop to write prompts/, configs/, eval_config, agent.yaml, AND skills/verify-fix/**.
  2. Drop the ca5 prompt-sha assert (the prompt now carries the VERIFY section; sha is expected to differ).
  3. Limit the run to a small BATCH_IDS list (both near-miss and known-win tasks) instead of all 129.
Everything else identical: same model source, wheelhouse, snapshots, serve cell, caps-from-eval_config
(28 calls / 8 min), subprocess sandbox, no compaction.

NO GPU here; this only writes the kernel. `kaggle kernels push` runs it on Kaggle's L4.
"""
import base64
import gzip
import json
import re
import shutil
from pathlib import Path

K = Path(__file__).resolve().parent
SRC = K / "push_129_e4b"
DST = K / "push_e4b_verify_batch"
BUNDLE = K.parent / "local_eval" / "parity_rig" / "agent_ctrl_e4b_verify"

# Small batch: 2 near-miss "does verify convert" + stable wins "does verify regress a known green".
BATCH_IDS = [
    "rich_4077",    # reliably localizes+edits; has tests/test_file_proxy.py -> verify should fire
    "rich_3894",    # flaky near-miss (wrong-content family) -> verify's best conversion shot
    "rich_3006",    # stable E4B win -> regression check (must stay resolved)
    "rich_3905",    # stable E4B win -> regression check
    "fastapi_14301",# stable fastapi win -> regression check + fastapi test-mapping check
    "fastapi_14463",# stable fastapi win -> regression check
]

assert BUNDLE.is_dir(), f"bundle missing: {BUNDLE}"
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir()

# ---- gather the bundle files into an EMBED dict (relative POSIX paths -> b64) ----
emb = {}
for p in sorted(BUNDLE.rglob("*")):
    if p.is_file() and "__pycache__" not in p.parts:
        rel = p.relative_to(BUNDLE).as_posix()
        emb[rel] = base64.b64encode(p.read_bytes()).decode()
print("embedded bundle files:", list(emb))
assert "agent.yaml" in emb and "prompts/system.md" in emb and "skills/verify-fix/scripts/verify.py" in emb

# carry over the task defs + we'll filter to BATCH_IDS at runtime
nb = json.loads((SRC / "ca5-e4b-full129.ipynb").read_text(encoding="utf-8"))

# ---- CELL 2: replace the EMBED block + the file-materialize + the sha assert ----
cell2 = "".join(nb["cells"][2]["source"])

# reuse the existing tasks.jsonl_gz from the stock EMBED (keep all 129; we filter by id in cell 4)
m_embed = re.search(r'EMBED = json\.loads\("""(.*?)"""\)', cell2, re.S)
stock_embed = json.loads(m_embed.group(1))
emb["tasks.jsonl_gz"] = stock_embed["tasks.jsonl_gz"]

new_embed_literal = 'EMBED = json.loads("""%s""")' % json.dumps(emb)
cell2 = cell2.replace(m_embed.group(0), new_embed_literal, 1)

# replace the materialize-WANT block (writes 4 flat files) with a generic tree writer that also
# writes the skills/ subtree, and drop the sha assert.
old_write = re.search(
    r'AGENT = Path\("/kaggle/working/agent_ca5"\).*?assert sha == "b08b32a2438d".*?\n',
    cell2, re.S)
assert old_write, "could not find the agent-materialize block in cell 2"

new_write = '''AGENT = Path("/kaggle/working/agent_ca5")
if AGENT.exists():
    shutil.rmtree(AGENT)
AGENT.mkdir(parents=True, exist_ok=True)
import hashlib as _hashlib
for _rel, _b64 in EMBED.items():
    if _rel == "tasks.jsonl_gz":
        continue
    _dst = AGENT / _rel
    _dst.parent.mkdir(parents=True, exist_ok=True)
    _dst.write_bytes(base64.b64decode(_b64))
    print(f"  {_rel}: {_dst.stat().st_size} B <- embedded")
# skill scripts must be executable text; nothing to chmod (python3 <file>), but assert they parse
import ast as _ast
for _py in AGENT.rglob("scripts/*.py"):
    _ast.parse(_py.read_text(encoding="utf-8"))
    print(f"  script OK: {_py.relative_to(AGENT)}")
sha = _hashlib.sha1((AGENT / "prompts" / "system.md").read_bytes()).hexdigest()[:12]
print("agent prompt sha (verify bundle, EXPECTED to differ from ca5 b08b32a2438d):", sha)
# SKILL.md BOM guard (the known compile-killer)
for _sm in AGENT.rglob("SKILL.md"):
    assert _sm.read_bytes()[:3] != b"\\xef\\xbb\\xbf", f"SKILL.md has BOM: {_sm}"
    assert _sm.read_bytes()[:3] == b"---", f"SKILL.md must start with ---: {_sm}"
    print(f"  SKILL.md ok: {_sm.relative_to(AGENT)}")
'''
cell2 = cell2.replace(old_write.group(0), new_write, 1)
nb["cells"][2]["source"] = cell2.splitlines(keepends=True)

# ---- CELL 4: limit to BATCH_IDS ----
cell4 = "".join(nb["cells"][4]["source"])
batch_literal = "BATCH_IDS = %s\n" % json.dumps(BATCH_IDS)
anchor = 'all_ids = [json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()]'
assert anchor in cell4, "cell 4 task-list anchor not found"
cell4 = cell4.replace(
    anchor,
    batch_literal + 'all_ids = [i for i in (json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()) if i in set(BATCH_IDS)]',
    1)
# small batch -> one chunk, lower concurrency to be gentle
cell4 = cell4.replace('CONC = "10"', 'CONC = "3"').replace("CHUNK = 20", "CHUNK = 10")
nb["cells"][4]["source"] = cell4.splitlines(keepends=True)

# ---- CELL 0: retitle ----
nb["cells"][0]["source"] = [
    "# E4B VERIFY-FIX skill gate (SMALL BATCH)\n",
    "Fork of ca5-e4b-full129 with the verify-fix skill bundle + edit->verify->repair prompt.\n",
    "Batch = 2 near-miss (convert?) + 4 stable wins (regress?). Caps 28/8 from eval_config.\n",
    "Read per-task `resolved` + look for VERIFY: lines in results/logs/*.log.\n",
]

(DST / "e4b-verify-batch.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")

# ---- metadata ----
meta = json.loads((SRC / "kernel-metadata.json").read_text(encoding="utf-8"))
meta.update(id="comfyops/e4b-verify-batch",
            title="e4b verify batch",
            code_file="e4b-verify-batch.ipynb")
(DST / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

print("wrote", DST)
print("batch:", BATCH_IDS)
