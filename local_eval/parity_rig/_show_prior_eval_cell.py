import json
import re
from pathlib import Path

nb = Path('local_eval/pull_31ba3hard_kern/gemma-sibling-conform-31b-a3-hard.ipynb')
d = json.loads(nb.read_text(encoding='utf-8', errors='replace'))
for i, c in enumerate(d.get('cells', [])):
    src = ''.join(c.get('source', []))
    if 'EvalConfig' in src and 'max_tool_calls' in src:
        print('===== CELL %d =====' % i)
        print(src)
        print()
