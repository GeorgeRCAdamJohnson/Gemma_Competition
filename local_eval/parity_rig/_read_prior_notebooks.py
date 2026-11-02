"""Extract the eval invocation from our own previously-working Kaggle kernels."""
import json
import re
from pathlib import Path

ROOT = Path('local_eval')
seen = set()
for nb in sorted(ROOT.rglob('*.ipynb')):
    try:
        d = json.loads(nb.read_text(encoding='utf-8', errors='replace'))
    except Exception:
        continue
    for c in d.get('cells', []):
        src = ''.join(c.get('source', []))
        if 'swegemma' in src and ('eval' in src or 'max-tool' in src):
            key = re.sub(r'\s+', ' ', src)[:200]
            if key in seen:
                continue
            seen.add(key)
            if 'max-tool-calls' in src or 'max_tool_calls' in src or 'max-time' in src:
                print('#' * 80)
                print('FILE:', nb)
                for line in src.splitlines():
                    if re.search(r'max-tool|max-time|max_turn|max-turns|swegemma|concurrency|sandbox|results-dir|task-id|--limit', line):
                        print('   ', line.strip()[:180])
                print()
