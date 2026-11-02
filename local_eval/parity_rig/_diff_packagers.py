"""Compare the original packager with the ca5 fork: what capability was lost?"""
import json
import re
from pathlib import Path

PAIRS = [
    ('ORIGINAL', Path('local_eval/push_packager/gemma-submission-packager.ipynb')),
    ('CA5 FORK', Path('local_eval/push_packager_ca5/gemma-submission-packager-ca5.ipynb')),
]

info = {}
for label, p in PAIRS:
    if not p.exists():
        print('%s: MISSING %s' % (label, p))
        continue
    d = json.loads(p.read_text(encoding='utf-8', errors='replace'))
    cells = d.get('cells', [])
    srcs = [''.join(c.get('source', [])) for c in cells]
    code = [s for c, s in zip(cells, srcs) if c.get('cell_type') == 'code']
    joined = '\n'.join(srcs)
    info[label] = dict(path=p, n=len(cells), ncode=len(code), chars=len(joined), srcs=srcs)
    print('\n' + '=' * 78)
    print('%s  (%d cells, %d code, %d chars)  %s' % (label, len(cells), len(code), len(joined), p))
    for i, (c, s) in enumerate(zip(cells, srcs)):
        first = next((l.strip() for l in s.splitlines() if l.strip()), '')
        print('  [%02d] %-9s %s' % (i, c.get('cell_type'), first[:110]))

# capability probes: things a good packager must do
PROBES = {
    'compile check (real compiler)': r'compile_check|compile_submission|COMPILE OK',
    'adapter discovery / manifest': r'discover_adapters|adapter_manifest|ALLOWED_ADAPTER_EXTENSIONS',
    'prompt sha assertion': r'prompt sha|sha1\(|sha256\(',
    'banned-token / leak audit': r'BANNED|leak',
    'eval_config written': r'eval_config\.yaml',
    'sampling.yaml written': r'sampling\.yaml',
    'agent.yaml written': r'agent\.yaml',
    'size / 3GiB guard': r'3 ?\* ?1024|3221225472|GiB|MAX_SUBMISSION_SIZE',
    'submission.zip creation': r'submission\.zip',
    'upload / submit call': r'competitions?\.submit|submit_submission|kaggle.*submit',
    'fingerprint / manifest json': r'fingerprint|manifest\.json|RUN_FINGERPRINT',
    'sub-agent / skills copy': r'skills|sub_agent|subagents',
}
if len(info) == 2:
    print('\n' + '=' * 78)
    print('%-34s %-10s %-10s' % ('capability', 'ORIGINAL', 'CA5 FORK'))
    for name, rx in PROBES.items():
        a = len(re.findall(rx, '\n'.join(info['ORIGINAL']['srcs']), re.I))
        b = len(re.findall(rx, '\n'.join(info['CA5 FORK']['srcs']), re.I))
        flag = ''
        if a and not b:
            flag = '   <-- LOST'
        elif a > b * 2 and a >= 2:
            flag = '   (thinner)'
        print('%-34s %-10d %-10d%s' % (name, a, b, flag))
