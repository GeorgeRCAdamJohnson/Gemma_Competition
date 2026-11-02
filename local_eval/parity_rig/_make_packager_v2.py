"""Rebuild the ca5 packager: restore the guards the fork dropped and add the intel
(real compiler parity, manifest fingerprint, leak audit, caps readout).

Output: local_eval/push_packager_ca5v2/gemma-submission-packager-ca5v2.ipynb
Cell 0/1 are reused verbatim from the ca5 fork so the shipped bytes cannot drift.
"""
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "local_eval" / "push_packager_ca5" / "gemma-submission-packager-ca5.ipynb"
OUT = ROOT / "local_eval" / "push_packager_ca5v2"
OUT.mkdir(parents=True, exist_ok=True)

INTEL = r'''# ===== INTEL: validate + fingerprint exactly what we are about to ship =====
# Restores what the ca5 fork dropped (3 GiB guard, full extension set) and adds the
# capability neither version had: a real compiler parity check and a manifest.
import hashlib, json, os, subprocess, sys
from pathlib import Path

AGENT_DIR = Path('/kaggle/working/submission')

try:
    from swegemma.config import (ALLOWED_SUBMISSION_EXTENSIONS as OK_EXT,
                                 ALLOWED_ADAPTER_EXTENSIONS as OK_ADP)
    MAXB = 3 * 1024 ** 3
    print('extension sets : from swegemma.config (harness ground truth)')
except Exception as e:
    OK_EXT = {'.yaml', '.yml', '.md', '.txt', '.py', '.json'}
    OK_ADP = {'.safetensors', '.bin', '.pt', '.pth', '.gguf', '.ggml'}
    MAXB = 3 * 1024 ** 3
    print('extension sets : fallback literal (%s)' % type(e).__name__)
OK_EXT = {str(e).lower() for e in OK_EXT}
OK_ADP = {str(e).lower() for e in OK_ADP}

files = sorted(p for p in AGENT_DIR.rglob('*') if p.is_file())
total = sum(p.stat().st_size for p in files)
bad = [p for p in files if p.suffix.lower() not in (OK_EXT | OK_ADP)]
assert not bad, 'illegal extensions: %s' % [str(p) for p in bad]
assert total <= MAXB, 'too big: %d > %d' % (total, MAXB)
print('size            : %d files, %.2f MiB (cap %.0f GiB)'
      % (len(files), total / 1024 ** 2, MAXB / 1024 ** 3))

import yaml


class _Tolerant(yaml.SafeLoader):
    """agent.yaml uses !include; treat any unknown tag as its literal contents."""


def _any_tag(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


_Tolerant.add_multi_constructor('', _any_tag)
_load = lambda p: yaml.load(Path(p).read_text(encoding='utf-8'), Loader=_Tolerant) or {}

ag = _load(AGENT_DIR / 'agent.yaml')
_ec = _load(AGENT_DIR / 'eval_config.yaml')
ec = _ec.get('evaluation', _ec) or {}
sm = _load(AGENT_DIR / 'configs' / 'sampling.yaml')
prompt = (AGENT_DIR / 'prompts' / 'system.md').read_bytes()

BANNED = ('TextIOBase', 'isatty', '__file', 'FileProxy', 'RawIOBase', 'fileno')
leaks = [b for b in BANNED if b in prompt.decode('utf-8', 'ignore')]

info = {
    'model': ag.get('model'),
    'agent_name': ag.get('name'),
    'caps': {k: ec.get(k) for k in ('max_tool_calls', 'max_time_minutes', 'max_turns', 'timeout_seconds')},
    'sampling': sm,
    'prompt_bytes': len(prompt),
    'prompt_sha1_12': hashlib.sha1(prompt).hexdigest()[:12],
    'prompt_sha256_12': hashlib.sha256(prompt).hexdigest()[:12],
    'leak_audit': leaks,
    'adapters': [p.name for p in files if p.suffix.lower() in OK_ADP],
    'total_bytes': total,
    'files': [{'path': str(p.relative_to(AGENT_DIR)), 'bytes': p.stat().st_size,
               'sha256': hashlib.sha256(p.read_bytes()).hexdigest()[:16]} for p in files],
}
print('declared model  :', info['model'])
print('prompt          : %d B  sha1 %s / sha256 %s'
      % (len(prompt), info['prompt_sha1_12'], info['prompt_sha256_12']))
print('caps            :', info['caps'])
print('sampling        :', info['sampling'])
print('adapters        :', info['adapters'] or 'none')
print('leak audit      :', leaks or 'clean')
print('files           :')
for f in info['files']:
    print('   %-36s %9d B' % (f['path'], f['bytes']))

# unreferenced files still get shipped: dead weight and a source of confusion
_ag_txt = (AGENT_DIR / 'agent.yaml').read_text(encoding='utf-8')
_core = {'agent.yaml', 'eval_config.yaml'}
unused = [f['path'] for f in info['files']
          if f['path'].replace('\\', '/') not in _core
          and Path(f['path']).name not in _ag_txt
          and f['path'].replace('\\', '/') not in _ag_txt]
info['unreferenced'] = unused
print('unreferenced    :', unused or 'none (every file is referenced by agent.yaml)')

Path('/kaggle/working/submission_manifest.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
print('wrote /kaggle/working/submission_manifest.json (outside the zip)')

# --- real compiler parity: catches config crashes before a submission slot is spent ---
import importlib.util
cc = Path('compile_check.py')
if not cc.exists():
    cc = Path('/kaggle/working/compile_check.py')
have_adk = importlib.util.find_spec('adk_submission') is not None
if not cc.exists():
    print('COMPILE CHECK: skipped (compile_check.py not in env; copy it next to the notebook)')
elif not have_adk:
    print('COMPILE CHECK: skipped (adk_submission not importable here; the Kaggle wheelhouse has it)')
else:
    r = subprocess.run([sys.executable, str(cc), str(AGENT_DIR)],
                       capture_output=True, text=True, timeout=900)
    print(r.stdout[-4000:] or '', r.stderr[-1500:] or '')
    assert r.returncode == 0, 'COMPILE CHECK FAILED -> do not ship this pack'
    print('COMPILE CHECK: PASS')
'''

ZIP = r'''# ===== Package submission.zip (guards restored from the original packager) =====
import shutil, zipfile
from pathlib import Path

AGENT_DIR = Path('/kaggle/working/submission')
zip_path = Path(shutil.make_archive(str(AGENT_DIR), 'zip', root_dir=AGENT_DIR))
with zipfile.ZipFile(zip_path, 'r') as zf:
    infos = [i for i in zf.infolist() if not i.is_dir()]
    names = zf.namelist()
    total = sum(i.file_size for i in infos)
    assert total <= 3 * 1024 ** 3, 'too big: %d' % total
    assert 'agent.yaml' in names, 'missing agent.yaml'
    assert 'prompts/system.md' in names, 'missing prompt'
    assert 'configs/sampling.yaml' in names, 'missing sampling'
    assert 'eval_config.yaml' in names, 'missing eval_config'
    assert not any(n.startswith('sub_agents') for n in names), 'sub_agents must NOT be present'
    allowed = {'.yaml', '.yml', '.md', '.txt', '.py', '.json',
               '.safetensors', '.bin', '.pt', '.pth', '.gguf', '.ggml'}
    for i in infos:
        assert Path(i.filename).suffix.lower() in allowed, 'illegal file: %s' % i.filename
    print('zip: %d files, %.2f MiB uncompressed' % (len(infos), total / 1024 ** 2))
print('Created %s (%.1f KiB)' % (zip_path, zip_path.stat().st_size / 1024))
for i in sorted(infos, key=lambda x: x.filename):
    print('   %-36s %9d B' % (i.filename, i.file_size))
'''

nb = json.loads(SRC.read_text(encoding="utf-8"))
cells = nb["cells"][:2]          # header + agent-dir writer, verbatim from the ca5 fork


def code(src: str):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": src.splitlines(keepends=True)}


cells += [code(INTEL), code(ZIP)]
nb["cells"] = cells

for i, c in enumerate(nb["cells"]):
    ast.parse("".join(c["source"]))

path = OUT / "gemma-submission-packager-ca5v2.ipynb"
path.write_text(json.dumps(nb, indent=1), encoding="utf-8")

blob = "\n".join("".join(c["source"]) for c in nb["cells"])
print(f"wrote {path} ({path.stat().st_size} B, {len(nb['cells'])} cells, all parse)")
for probe in ("3 * 1024 ** 3", "ALLOWED_ADAPTER_EXTENSIONS", "compile_check.py",
              "submission_manifest.json", "leak_audit", ".safetensors"):
    print("   %-30s %s" % (probe, probe in blob))
