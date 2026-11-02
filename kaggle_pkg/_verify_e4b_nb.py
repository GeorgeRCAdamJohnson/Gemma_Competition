import ast
import json
from pathlib import Path

nb_path = Path('push_129_e4b/ca5-e4b-full129.ipynb')
nb = json.loads(nb_path.read_text(encoding='utf-8'))
code = ''.join(''.join(c['source']) for c in nb['cells'] if c['cell_type'] == 'code')

PROBES = [
    'gemma-4-e4b-it-qat-w4a16-ct/2',
    'tensor_parallel_size=1',
    'CONC = "10"',
    '--max-tool-calls',
    'board caps:',
    'SMOKE OK',
    '--served-model-name',
    'task_results.all.jsonl',
]
for p in PROBES:
    print('  %-34s %s' % (p, p in code))

print('\n31b mentions left:', code.count('31b-it-qat'))
print('e4b mentions:', code.count('e4b-it-qat'))

bad = 0
for c in nb['cells']:
    if c['cell_type'] == 'code':
        try:
            ast.parse(''.join(c['source']))
        except SyntaxError as e:
            bad += 1
            print('SYNTAX ERROR:', e)
print('all code cells parse:', bad == 0)

meta = json.loads(Path('push_129_e4b/kernel-metadata.json').read_text())
print('model_sources:', meta['model_sources'])
print('id:', meta['id'], '| machine:', meta['machine_shape'])

# show the exact model path + tp lines
for line in ''.join(nb['cells'][2]['source']).splitlines():
    if 'MODEL_PATH' in line or 'TARGET_MODEL_NAME' in line or 'tensor_parallel' in line:
        print('   >', line.strip()[:120])
