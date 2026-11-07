"""Build a CPU-only packager kernel for the E4B fresh-retry pack (exact bytes measured in e4b-repro-ab ARM_F).

Source = local_eval/parity_rig/agent_e4b_retry_fresh (9 files). Embedded base64; the kernel writes them, zips,
and checks: root agent.yaml, the 4 sub-agent/prompt files, check.py, allowed extensions (harness list), no BOM/CRLF,
and that the bundle hash equals the measured one. Competition attached so it can be submitted from the notebook page.
"""
import base64
import hashlib
import json
import shutil
from pathlib import Path

K = Path(__file__).resolve().parent
SRC = K.parent / "local_eval" / "parity_rig" / "agent_e4b_retry_fresh"
SLUG = "gemma-submit-e4b-retry-fresh"
DST = K / f"push_{SLUG.replace('-', '_')}"
TEMPLATE_META = K / "_src_mobile_ca5" / "kernel-metadata.json"

files = {p.relative_to(SRC).as_posix(): p.read_bytes() for p in sorted(SRC.rglob("*")) if p.is_file()}
assert len(files) == 9 and "agent.yaml" in files and "skills/submit-gate/scripts/check.py" in files
assert b"model: gemma-4-e4b-it-qat-w4a16-ct" in files["sub_agents/fixer.yaml"]
assert b"max_tool_calls: 80" in files["eval_config.yaml"] and b"max_time_minutes: 30" in files["eval_config.yaml"]
for n, b in files.items():
    assert b"\r" not in b and not b.startswith(b"\xef\xbb\xbf"), n
bundle_sha = hashlib.sha1(b"".join(files[n] for n in sorted(files))).hexdigest()[:12]
emb = {n: base64.b64encode(b).decode() for n, b in files.items()}

cell = f'''# E4B fresh-retry pack: LoopAgent(3)[fixer, verifier], gate = existing tests (stale-bytecode fix), 80/30/200.
# Measured: e4b-repro-ab ARM_F 11.50/39 vs plain ca5 9.82 (16 vs 17 passes, Welch t=3.18). CPU only.
import base64, hashlib, json, shutil, zipfile
from pathlib import Path
FILES = json.loads("""{json.dumps(emb)}""")
A = Path("/kaggle/working/submission")
if A.exists():
    shutil.rmtree(A)
for rel, b64 in FILES.items():
    p = A / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(base64.b64decode(b64))
raw = {{rel: (A / rel).read_bytes() for rel in FILES}}
sha = hashlib.sha1(b"".join(raw[n] for n in sorted(raw))).hexdigest()[:12]
assert sha == "{bundle_sha}", sha
zp = Path(shutil.make_archive("/kaggle/working/submission", "zip", root_dir=A))
ALLOWED = {{".yaml", ".yml", ".md", ".txt", ".py", ".json", ".safetensors"}}
with zipfile.ZipFile(zp) as zf:
    names = [n for n in zf.namelist() if not n.endswith("/")]
    for need in ("agent.yaml", "eval_config.yaml", "sub_agents/fixer.yaml", "sub_agents/verifier.yaml",
                 "skills/submit-gate/SKILL.md", "skills/submit-gate/scripts/check.py"):
        assert need in names, need
    for n in names:
        assert Path(n).suffix.lower() in ALLOWED, n
        assert b"\\r" not in zf.read(n), n
print(f"Created {{zp}} ({{zp.stat().st_size/1024:.1f}} KiB) bundle sha {{sha}}")
print("Files:", names)
print(zf.read("eval_config.yaml").decode() if False else (A / "eval_config.yaml").read_text())
'''
nb = {"cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                 "source": cell.splitlines(keepends=True)}],
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 4}
compile(cell, "cell", "exec")
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir()
(DST / f"{SLUG}.ipynb").write_text(json.dumps(nb, indent=1), encoding="utf-8")
meta = json.loads(TEMPLATE_META.read_text(encoding="utf-8"))
meta.pop("id_no", None)
meta.update(id=f"comfyops/{SLUG}", title=SLUG.replace("-", " "), code_file=f"{SLUG}.ipynb")
assert meta["competition_sources"] == ["gemma-4-developer-agent"] and not meta["enable_gpu"]
(DST / "kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("built", DST.name, "| bundle sha", bundle_sha, "|", len(files), "files")
