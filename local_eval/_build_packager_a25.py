"""Build push_packager_router: CPU-only packager that zips the A25 ROUTER agent package.

Configs are extracted VERBATIM from kern_src/_a25_router_tail.py so the board submission is
byte-identical to what the A25 arm test runs (only the harness context differs). The prompt is
the shipped v10/A3-hard text with the SAME single step-1 substitution, applied here with a
count==1 anchor assert. Sampling/eval held at the v10 family (temp .2 / thinking 4096 /
out 5000 / 8 min / 28 calls / 120 turns / 300 s) so the ONLY changed variable vs the scored
A3-hard draws (0.12-0.18 band) is the architecture.

Pre-flight (local, no Kaggle): yaml-parse every generated file with an !include-tolerant
loader, ast-parse the cells, verify anchors and the schema-shaped keys used by
adk_submission (agent_tool: {config_path, skip_summarization}).
"""
import json, re, sys, ast, hashlib
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
LE = Path(r'C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\local_eval')
TAIL = (LE / 'kern_src' / '_a25_router_tail.py').read_text(encoding='utf-8')

def extract(marker, text):
    m = re.search(re.escape(marker) + r"'''(.*?)'''", text, re.S)
    assert m, 'extract failed: ' + marker
    return m.group(1)

AGENT_YAML   = extract("(AGENT_DIR_R / 'agent.yaml').write_text(", TAIL)
LOCATOR_YAML = extract("(AGENT_DIR_R / 'sub_agents' / 'locator.yaml').write_text(", TAIL)
LOGIC_YAML   = extract("(AGENT_DIR_R / 'sub_agents' / 'logic.yaml').write_text(", TAIL)
_step1_old = re.search(r'_step1_old = """(.*?)"""', TAIL, re.S).group(1)
_step1_new = re.search(r'_step1_new = """(.*?)"""', TAIL, re.S).group(1)

# shipped v10 prompt = the A3-hard base (runtime-identical to the kernel's system_a3.md)
shipped = (LE / 'pull_31ba3hard_out' / 'submission' / 'prompts' / 'system.md').read_text(encoding='utf-8')
assert shipped.count(_step1_old) == 1, 'anchor count %d in shipped prompt' % shipped.count(_step1_old)
ROUTER_PROMPT = shipped.replace(_step1_old, _step1_new, 1)
assert ROUTER_PROMPT.replace(_step1_new, _step1_old, 1) == shipped, 'not reversible'
print('router prompt: %d chars, sha %s' % (len(ROUTER_PROMPT), hashlib.sha256(ROUTER_PROMPT.encode()).hexdigest()[:12]))

SAMPLING = """temperature: 0.2
top_p: 0.95
max_output_tokens: 5000
thinking_config:
  thinking_budget: 4096
  include_thoughts: true
"""
EVALCFG = """evaluation:
  max_time_minutes: 8
  max_tool_calls: 28
  max_turns: 120
  timeout_seconds: 300
"""

cell0 = """# A25 ROUTER submission packager: writes the ROUTER agent dir (2 agent_tool specialists) and
# packages submission.zip. CPU-only, stdlib only (no swegemma import - v1/v2 lesson).
# Configs are byte-identical to the A25 arm test (kern_src/_a25_router_tail.py).
import os, shutil, hashlib, json
from pathlib import Path
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['TRANSFORMERS_NO_TF'] = '1'
WORKING_DIR = Path('/kaggle/working')
AGENT_DIR = WORKING_DIR / 'submission'
if AGENT_DIR.exists():
    shutil.rmtree(AGENT_DIR)
AGENT_DIR.mkdir(parents=True)
print('Agent dir:', AGENT_DIR)
"""

cell1 = (
"# ===== Write ROUTER agent directory (A25) =====\n"
"import hashlib\n"
"AGENT_DIR = Path('/kaggle/working/submission')\n"
"(AGENT_DIR / 'configs').mkdir(parents=True, exist_ok=True)\n"
"(AGENT_DIR / 'prompts').mkdir(parents=True, exist_ok=True)\n"
"(AGENT_DIR / 'sub_agents').mkdir(parents=True, exist_ok=True)\n"
"(AGENT_DIR / 'agent.yaml').write_text(" + repr(AGENT_YAML) + ", encoding='utf-8')\n"
"(AGENT_DIR / 'sub_agents' / 'locator.yaml').write_text(" + repr(LOCATOR_YAML) + ", encoding='utf-8')\n"
"(AGENT_DIR / 'sub_agents' / 'logic.yaml').write_text(" + repr(LOGIC_YAML) + ", encoding='utf-8')\n"
"(AGENT_DIR / 'configs' / 'sampling.yaml').write_text(" + repr(SAMPLING) + ", encoding='utf-8')\n"
"(AGENT_DIR / 'eval_config.yaml').write_text(" + repr(EVALCFG) + ", encoding='utf-8')\n"
"# ROUTER prompt = shipped v10/A3-hard text + ONE step-1 span (same anchor as the arm test).\n"
"_step1_old = " + repr(_step1_old) + "\n"
"_step1_new = " + repr(_step1_new) + "\n"
"_shipped = " + repr(shipped) + "\n"
"assert _shipped.count(_step1_old) == 1, 'anchor matched %d times' % _shipped.count(_step1_old)\n"
"_rt = _shipped.replace(_step1_old, _step1_new, 1)\n"
"assert _rt.replace(_step1_new, _step1_old, 1) == _shipped, 'not reversible'\n"
"(AGENT_DIR / 'prompts' / 'system.md').write_text(_rt, encoding='utf-8')\n"
"print('system.md: %d chars sha %s' % (len(_rt), hashlib.sha256(_rt.encode()).hexdigest()[:12]))\n"
"_ag = (AGENT_DIR / 'agent.yaml').read_text(encoding='utf-8')\n"
"assert 'agent_tool' in _ag and 'sub_agents/locator.yaml' in _ag and 'sub_agents/logic.yaml' in _ag\n"
"assert 'skip_summarization: false' in _ag\n"
"print('agent.yaml sha', hashlib.sha256(_ag.encode()).hexdigest()[:12], '(2 agent_tool specialists)')\n"
"for _f in ('sub_agents/locator.yaml', 'sub_agents/logic.yaml', 'configs/sampling.yaml', 'eval_config.yaml'):\n"
"    _p = AGENT_DIR / _f\n"
"    print(' %s: %d chars sha %s' % (_f, len(_p.read_text(encoding='utf-8')),\n"
"          hashlib.sha256(_p.read_bytes()).hexdigest()[:12]))\n"
)

cell2 = """# ===== Package submission.zip =====
import zipfile, shutil, os
from pathlib import Path
AGENT_DIR = Path('/kaggle/working/submission')
zip_path = Path(shutil.make_archive(str(Path('/kaggle/working/submission')), 'zip', root_dir=AGENT_DIR))
with zipfile.ZipFile(zip_path, 'r') as zf:
    total = sum(i.file_size for i in zf.infolist())
    names = zf.namelist()
    assert total <= 3 * 1024**3, f'too big: {total}'
    assert 'agent.yaml' in names, 'missing agent.yaml'
    assert 'sub_agents/locator.yaml' in names, 'missing locator sub-agent'
    assert 'sub_agents/logic.yaml' in names, 'missing logic sub-agent'
    assert 'prompts/system.md' in names, 'missing prompt'
    for info in zf.infolist():
        if not info.is_dir():
            assert Path(info.filename).suffix.lower() in {'.yaml', '.yml', '.md', '.txt', '.py', '.json', '.safetensors'}, info.filename
print(f'Created {zip_path} ({zip_path.stat().st_size/1024:.1f} KiB)')
print('Files:', names)
"""

def to_src(code):
    return code.splitlines(keepends=True)

nb = {
    "cells": [
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": to_src(cell0)},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": to_src(cell1)},
        {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": to_src(cell2)},
    ],
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    },
    "nbformat": 4, "nbformat_minor": 5,
}

out = LE / 'push_packager_a25'
out.mkdir(exist_ok=True)
(out / 'gemma-submission-packager-a25.ipynb').write_text(json.dumps(nb, indent=1), encoding='utf-8')
km = json.loads((LE / 'push_packager' / 'kernel-metadata.json').read_text(encoding='utf-8'))
km['id'] = 'comfyops/gemma-submission-packager-a25'
km['title'] = 'Gemma Submission Packager A25 router'
km['code_file'] = 'gemma-submission-packager-a25.ipynb'
(out / 'kernel-metadata.json').write_text(json.dumps(km, indent=2), encoding='utf-8')

# ---------- PRE-FLIGHT VALIDATION (local) ----------
import yaml as _y

class _IncLoader(_y.SafeLoader):
    pass
_IncLoader.add_constructor('!include', lambda l, n: str(n.value))

for name, txt in (('agent.yaml', AGENT_YAML), ('locator.yaml', LOCATOR_YAML),
                  ('logic.yaml', LOGIC_YAML), ('sampling.yaml', SAMPLING), ('eval_config.yaml', EVALCFG)):
    d = _y.load(txt, Loader=_IncLoader)
    assert isinstance(d, dict), name
    print('yaml OK:', name, '| keys:', sorted(d.keys()))

ag = _y.load(AGENT_YAML, Loader=_IncLoader)
tools = ag['tools']
agent_tools = [t for t in tools if isinstance(t, dict) and 'agent_tool' in t]
assert len(agent_tools) == 2, agent_tools
for t in agent_tools:
    ref = t['agent_tool']
    assert set(ref) == {'config_path', 'skip_summarization'}, ref
    assert ref['skip_summarization'] is False
print('agent_tool refs OK: 2 x {config_path, skip_summarization:false}')
sub_names = set()
for fn, txt in (('locator', LOCATOR_YAML), ('logic', LOGIC_YAML)):
    d = _y.load(txt, Loader=_IncLoader)
    assert d['name'] and d['model'] and d['instruction'] and isinstance(d['tools'], list)
    assert d['generate_content_config']['thinking_config']['thinking_budget'] == 1024
    sub_names.add(d['name'])
print('sub-agent yamls OK:', sorted(sub_names))

# ast-parse the generated cells (as they will run on Kaggle)
for i, code in enumerate((cell0, cell1, cell2)):
    ast.parse(code)
print('cells ast-parse OK (3)')

# schema cross-check vs harness_src (field names only - mirrors adk_submission/schema.py)
sch = Path(r'C:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE\Gemma\harness_src\x\adk_submission\schema.py').read_text(encoding='utf-8')
assert 'skip_summarization: bool = False' in sch and 'agent_tool: AgentToolRef' in sch
print('schema cross-check OK (AgentToolRef: config_path + skip_summarization)')
print()
print('READY: push_packager_a25/gemma-submission-packager-a25.ipynb (slug comfyops/gemma-submission-packager-a25)')
