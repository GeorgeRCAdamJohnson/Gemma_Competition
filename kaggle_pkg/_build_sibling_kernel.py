"""Build kaggle_pkg/push_e4b_sibling: single-GPU 6-task gate for the PROMPT-ONLY sibling arm (no skill).

Fork of push_129_e4b. Re-embeds the stock 4 flat files from agent_ctrl_e4b_sibling (NO skills tree),
drops the ca5 sha assert (prompt changed), limits to the same 6-task batch. Clean A/B vs the guardrail
5/6: does the sibling-mirror rule ALONE (no verify skill) also convert rich_4077?
"""
import base64
import json
import re
import shutil
from pathlib import Path

K = Path(__file__).resolve().parent
SRC = K / "push_129_e4b"
DST = K / "push_e4b_sibling"
BUNDLE = K.parent / "local_eval" / "parity_rig" / "agent_ctrl_e4b_sibling"
BATCH_IDS = ["rich_4077", "rich_3894", "rich_3006", "rich_3905", "fastapi_14301", "fastapi_14463"]

assert BUNDLE.is_dir()
assert not (BUNDLE / "skills").exists(), "this arm must have NO skill"
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir()

emb = {
    "system.md": base64.b64encode((BUNDLE / "prompts" / "system.md").read_bytes()).decode(),
    "agent.yaml": base64.b64encode((BUNDLE / "agent.yaml").read_bytes()).decode(),
    "sampling.yaml": base64.b64encode((BUNDLE / "configs" / "sampling.yaml").read_bytes()).decode(),
    "eval_config.yaml": base64.b64encode((BUNDLE / "eval_config.yaml").read_bytes()).decode(),
}

nb = json.loads((SRC / "ca5-e4b-full129.ipynb").read_text(encoding="utf-8"))
cell2 = "".join(nb["cells"][2]["source"])
m = re.search(r'EMBED = json\.loads\("""(.*?)"""\)', cell2, re.S)
stock = json.loads(m.group(1))
emb["tasks.jsonl_gz"] = stock["tasks.jsonl_gz"]
cell2 = cell2.replace(m.group(0), 'EMBED = json.loads("""%s""")' % json.dumps(emb), 1)
# drop the sha assert only (keep the stock flat-file WANT writer; this bundle is flat, no skills)
cell2 = re.sub(r'assert sha == "b08b32a2438d".*?\n',
               'print("prompt sha (sibling arm, expected != ca5):", sha)\n', cell2, count=1, flags=re.S)
nb["cells"][2]["source"] = cell2.splitlines(keepends=True)

cell4 = "".join(nb["cells"][4]["source"])
anchor = 'all_ids = [json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()]'
cell4 = cell4.replace(
    anchor,
    "BATCH_IDS = %s\n" % json.dumps(BATCH_IDS) +
    'all_ids = [i for i in (json.loads(l)["instance_id"] for l in open(TASKS) if l.strip()) if i in set(BATCH_IDS)]',
    1).replace('CONC = "10"', 'CONC = "3"').replace("CHUNK = 20", "CHUNK = 10")
nb["cells"][4]["source"] = cell4.splitlines(keepends=True)

nb["cells"][0]["source"] = [
    "# E4B SIBLING-MIRROR prompt-only gate (NO skill) — attribution A/B vs guardrail 5/6\n",
    "Does the sibling-mirror/smallest-diff rule ALONE convert rich_4077?\n",
]
(DST / "e4b-sibling.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
meta = json.loads((SRC / "kernel-metadata.json").read_text(encoding="utf-8"))
meta.update(id="comfyops/e4b-sibling", title="e4b sibling", code_file="e4b-sibling.ipynb")
(DST / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("wrote", DST, "| batch", BATCH_IDS)
