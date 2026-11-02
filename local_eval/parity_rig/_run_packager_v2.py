"""Execute the new packager cells for real against the ca5 agent dir."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NB = ROOT / "local_eval" / "push_packager_ca5v2" / "gemma-submission-packager-ca5v2.ipynb"
AGENT_SRC = ROOT / "local_eval" / "parity_rig" / "agent_ctrl_v5"

nb = json.loads(NB.read_text(encoding="utf-8"))
intel = "".join(nb["cells"][2]["source"])
zipc = "".join(nb["cells"][3]["source"])

work = Path(tempfile.mkdtemp(prefix="pk_"))
sub = work / "submission"
shutil.copytree(AGENT_SRC, sub)

# make the compile check available the way the notebook expects
cc_src = ROOT / "local_eval" / "parity_rig" / "compile_check.py"
shutil.copy2(cc_src, work / "compile_check.py")


def render(src: str) -> str:
    fwd_sub = str(sub).replace("\\", "/")
    fwd_work = (str(work) + "/").replace("\\", "/")
    return src.replace("/kaggle/working/submission", fwd_sub).replace("/kaggle/working/", fwd_work)


print("=" * 78)
print("EXEC INTEL CELL")
print("=" * 78)
g = {"__name__": "__main__"}
exec(compile(render(intel), "intel_cell", "exec"), g)

manifest = work / "submission_manifest.json"
print()
print("=" * 78)
print("EXEC ZIP CELL")
print("=" * 78)
exec(compile(render(zipc), "zip_cell", "exec"), g)

print()
print("=" * 78)
print("MANIFEST SANITY")
print("=" * 78)
m = json.loads(manifest.read_text(encoding="utf-8"))
print("model        :", m["model"])
print("caps         :", m["caps"])
print("prompt sha1  :", m["prompt_sha1_12"], "(expect b08b32a2438d for ca5)")
print("prompt sha256:", m["prompt_sha256_12"], "(expect b9aeaa9a53ce)")
print("leak audit   :", m["leak_audit"])
print("adapters     :", m["adapters"])
print("files        :", len(m["files"]), "| total", m["total_bytes"], "B")
print("zip exists   :", (work / "submission.zip").exists())
