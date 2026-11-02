"""CPU-only Kaggle probe: dump the E4B HF chat template so it can be diffed against the GGUF one.

llama-server runs with --jinja, so the local rig renders the GGUF's embedded template.
vLLM renders tokenizer_config.json's chat_template. If those differ, the same system.md
becomes a different prompt on the two stacks.
"""
import json
import os
from pathlib import Path

OUT = Path('/kaggle/working')
model_dir = None
for root, dirs, files in os.walk('/kaggle/input'):
    if 'tokenizer_config.json' in files and 'config.json' in files:
        model_dir = Path(root)
        break
print('model_dir:', model_dir)
assert model_dir, 'no model dir with tokenizer_config.json found'

info = {'model_dir': str(model_dir)}
tc = json.loads((model_dir / 'tokenizer_config.json').read_text(encoding='utf-8'))
info['tokenizer_class'] = tc.get('tokenizer_class')
info['bos_token'] = str(tc.get('bos_token'))
info['eos_token'] = str(tc.get('eos_token'))
info['has_chat_template'] = bool(tc.get('chat_template'))
tmpl = tc.get('chat_template') or ''
if isinstance(tmpl, list):
    tmpl = json.dumps(tmpl)
info['chat_template_len'] = len(tmpl)
import hashlib
info['chat_template_sha256'] = hashlib.sha256(tmpl.encode()).hexdigest()[:16]
(OUT / 'hf_chat_template.jinja').write_text(tmpl, encoding='utf-8')
print('template len:', info['chat_template_len'], 'sha:', info['chat_template_sha256'])
print('--- head ---')
print('\n'.join(tmpl.splitlines()[:16]))

cfg = json.loads((model_dir / 'config.json').read_text(encoding='utf-8'))
info['max_position_embeddings'] = cfg.get('max_position_embeddings')
info['model_type'] = cfg.get('model_type')
info['architectures'] = cfg.get('architectures')

MSGS = [{'role': 'system', 'content': 'SYSTEM_PROBE'},
        {'role': 'user', 'content': 'USER_PROBE'}]
try:
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(str(model_dir))
    info['tokenizer_loaded'] = type(tok).__name__
    rendered = tok.apply_chat_template(MSGS, tokenize=False, add_generation_prompt=True)
    info['rendered'] = rendered
    ids = tok.apply_chat_template(MSGS, tokenize=True, add_generation_prompt=True)
    info['rendered_token_ids_head'] = ids[:40]
    info['rendered_token_count'] = len(ids)
    (OUT / 'hf_rendered.txt').write_text(rendered, encoding='utf-8')
    print('--- rendered (repr) ---')
    print(repr(rendered))
    print('tokens:', len(ids))
except Exception as e:
    info['tokenizer_error'] = f'{type(e).__name__}: {e}'
    print('tokenizer error:', info['tokenizer_error'])

(OUT / 'tmpl_probe.json').write_text(json.dumps(info, indent=1), encoding='utf-8')
print('wrote', OUT / 'tmpl_probe.json')
