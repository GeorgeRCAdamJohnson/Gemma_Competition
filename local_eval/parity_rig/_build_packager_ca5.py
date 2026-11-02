"""Build push_packager_ca5: CPU-only packager for the TOURNAMENT-WINNER submission
(ctrl + pre-edit anchor-grep rule, NO sub-agents). Sources read from the LOCALY VERIFIED
agent_ctrl_v5 dir (compile-checked, LF prompt, sha b9aeaa9a53ce)."""
import ast
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
LE = Path(__file__).resolve().parent.parent
RIG = LE / "parity_rig"
SRC = RIG / "agent_ctrl_v5"

agent_yaml = (SRC / "agent.yaml").read_text(encoding="utf-8")
prompt = (SRC / "prompts" / "system.md").read_text(encoding="utf-8")
sampling = (SRC / "configs" / "sampling.yaml").read_text(encoding="utf-8")
evalcfg = (SRC / "eval_config.yaml").read_text(encoding="utf-8")
assert "agent_tool" not in agent_yaml
assert "BEFORE the edit: grep your anchor" in prompt
assert prompt.count("BEFORE the edit: grep your anchor") == 1
sha = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
assert sha == "b9aeaa9a53ce", sha
assert "\r" not in prompt, "prompt must stay LF for Kaggle byte-identity"
print("sources verified; prompt sha", sha, "chars", len(prompt))

cell0 = """# ca5 submission packager: ctrl + anchor-grep rule, NO sub-agents. CPU, stdlib only.
import os, shutil, hashlib
from pathlib import Path
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
WORKING_DIR = Path('/kaggle/working')
AGENT_DIR = WORKING_DIR / 'submission'
if AGENT_DIR.exists():
    shutil.rmtree(AGENT_DIR)
AGENT_DIR.mkdir(parents=True)
print('Agent dir:', AGENT_DIR)
"""

cell1 = (
    "import hashlib\n"
    "AGENT_DIR = Path('/kaggle/working/submission')\n"
    "(AGENT_DIR / 'configs').mkdir(parents=True, exist_ok=True)\n"
    "(AGENT_DIR / 'prompts').mkdir(parents=True, exist_ok=True)\n"
    "(AGENT_DIR / 'agent.yaml').write_text(" + repr(agent_yaml) + ", encoding='utf-8', newline='')\n"
    "(AGENT_DIR / 'configs' / 'sampling.yaml').write_text(" + repr(sampling) + ", encoding='utf-8', newline='')\n"
    "(AGENT_DIR / 'eval_config.yaml').write_text(" + repr(evalcfg) + ", encoding='utf-8', newline='')\n"
    "(AGENT_DIR / 'prompts' / 'system.md').write_text(" + repr(prompt) + ", encoding='utf-8', newline='')\n"
    "_ag = (AGENT_DIR / 'agent.yaml').read_text(encoding='utf-8')\n"
    "assert 'agent_tool' not in _ag and 'sub_agents' not in _ag\n"
    "_sm = (AGENT_DIR / 'prompts' / 'system.md').read_bytes()\n"
    "assert b'\\r' not in _sm, 'CRLF leaked'\n"
    "_sha = hashlib.sha256(_sm).hexdigest()[:12]\n"
    "assert _sha == 'b9aeaa9a53ce', _sha\n"
    "print('system.md: %d chars sha %s (ctrl + anchor span, LF, no sub-agents)' % (len(_sm), _sha))\n"
    "print('agent.yaml sha', hashlib.sha256(_ag.encode()).hexdigest()[:12], '(9 tools, no agent_tool)')\n"
    "print('eval sha', hashlib.sha256((AGENT_DIR / 'eval_config.yaml').read_bytes()).hexdigest()[:12],\n"
    "      '| sampling sha', hashlib.sha256((AGENT_DIR / 'configs' / 'sampling.yaml').read_bytes()).hexdigest()[:12])\n"
)

cell2 = """# ===== Package submission.zip =====
import zipfile, shutil
from pathlib import Path
AGENT_DIR = Path('/kaggle/working/submission')
zip_path = Path(shutil.make_archive(str(Path('/kaggle/working/submission')), 'zip', root_dir=AGENT_DIR))
with zipfile.ZipFile(zip_path, 'r') as zf:
    names = zf.namelist()
    assert 'agent.yaml' in names, 'missing agent.yaml'
    assert 'prompts/system.md' in names, 'missing prompt'
    assert 'configs/sampling.yaml' in names, 'missing sampling'
    assert 'eval_config.yaml' in names, 'missing eval_config'
    assert not any(n.startswith('sub_agents') for n in names), 'sub_agents must NOT be present'
    for info in zf.infolist():
        if not info.is_dir():
            assert Path(info.filename).suffix.lower() in {'.yaml', '.yml', '.md'}, info.filename
print(f'Created {zip_path} ({zip_path.stat().st_size/1024:.1f} KiB)')
print('Files:', names)
"""

nb = {"cells": [{"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [],
                 "source": s.splitlines(keepends=True)} for s in (cell0, cell1, cell2)],
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python"}},
      "nbformat": 4, "nbformat_minor": 5}

out = RIG.parent / "push_packager_ca5"
out.mkdir(exist_ok=True)
(out / "gemma-submission-packager-ca5.ipynb").write_text(json.dumps(nb, indent=1), encoding="utf-8")
km = json.loads((LE / "push_packager" / "kernel-metadata.json").read_text(encoding="utf-8"))
km["id"] = "comfyops/gemma-submission-packager-ca5"
km["title"] = "Gemma Submission Packager ca5 anchor"
km["code_file"] = "gemma-submission-packager-ca5.ipynb"
(out / "kernel-metadata.json").write_text(json.dumps(km, indent=2), encoding="utf-8")

for i, s in enumerate((cell0, cell1, cell2)):
    ast.parse(s)
print("cells parse OK; READY push_packager_ca5 (slug resolves from title: gemma-submission-packager-ca5-anchor)")
