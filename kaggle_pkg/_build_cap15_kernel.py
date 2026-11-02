"""Build kaggle_pkg/push_129_e4b_cap15: the ca5 E4B full-129 eval kernel with ONE change, the embedded
eval_config.yaml -> max_tool_calls 15 (bytes of local_eval/parity_rig/agent_ctrl_e4b_cap15/eval_config.yaml).
Everything else is identical to push_129_e4b (prompt sha asserted b08b32a2438d, same model, same tasks, no compaction,
board caps read from eval_config). New kernel id so the replication kernel's output is not overwritten."""
import base64
import json
import re
import shutil
from pathlib import Path

K = Path(__file__).resolve().parent
SRC, DST = K / "push_129_e4b", K / "push_129_e4b_cap15"
NEW_EC = (K.parent / "local_eval" / "parity_rig" / "agent_ctrl_e4b_cap15" / "eval_config.yaml").read_bytes()
assert b"max_tool_calls: 15" in NEW_EC
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir()
nb = json.loads((SRC / "ca5-e4b-full129.ipynb").read_text(encoding="utf-8"))
cell = nb["cells"][2]
s = "".join(cell["source"])
m = re.search(r'"eval_config\.yaml": "([A-Za-z0-9+/=]+)"', s)
old = base64.b64decode(m.group(1))
assert b"max_tool_calls: 28" in old, old
s = s.replace(m.group(0), '"eval_config.yaml": "%s"' % base64.b64encode(NEW_EC).decode())
cell["source"] = s.splitlines(keepends=True)
md = nb["cells"][0]
md["source"] = ["# ca5 E4B full-129 eval - CAP-15 free gate (only change vs ca5-e4b-full129-eval: eval_config max_tool_calls 28 -> 15)\n\n"] + md["source"]
(DST / "ca5-e4b-cap15-full129.ipynb").write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
meta = json.loads((SRC / "kernel-metadata.json").read_text(encoding="utf-8"))
meta.update(id="comfyops/ca5-e4b-cap15-full129-eval", title="ca5 e4b cap15 full129 eval", code_file="ca5-e4b-cap15-full129.ipynb")
(DST / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
# verify: decode back and diff against the original embedded set
s2 = "".join(json.loads((DST / "ca5-e4b-cap15-full129.ipynb").read_text(encoding="utf-8"))["cells"][2]["source"])
emb1 = json.loads(re.search(r'EMBED = json.loads\("""(.*?)"""\)', s, re.S).group(1))
emb0 = json.loads(re.search(r'EMBED = json.loads\("""(.*?)"""\)', "".join(json.loads((SRC / "ca5-e4b-full129.ipynb").read_text(encoding="utf-8"))["cells"][2]["source"]), re.S).group(1))
diff = [k for k in emb0 if emb0[k] != emb1.get(k)]
print("embedded files changed:", diff)
print("new eval_config:\n" + base64.b64decode(emb1["eval_config.yaml"]).decode())
print("wrote", DST)
