"""Verify the 0.20 submission zip byte-for-byte before resubmitting it."""
import hashlib
import json
import zipfile
from pathlib import Path

CAND = Path('local_eval/pull_packager_ca5_out/submission.zip')

# recorded fingerprints of the pack that scored 0.20
EXPECT = {
    'prompts/system.md': ('b9aeaa9a53ce', 7833),
    'eval_config.yaml': ('3b20d99d328d', 95),
    'configs/sampling.yaml': ('a49dbd3aab94', 119),
    'agent.yaml': ('6562a591393b', 326),
}

print('zip:', CAND, '| exists:', CAND.exists())
if not CAND.exists():
    raise SystemExit('missing zip')
print('size:', CAND.stat().st_size, 'B')

with zipfile.ZipFile(CAND) as zf:
    names = sorted(n for n in zf.namelist() if not n.endswith('/'))
    print('files:', names)
    ok = True
    for name, (want, wantlen) in EXPECT.items():
        if name not in names:
            print('  MISSING', name)
            ok = False
            continue
        data = zf.read(name)
        got = hashlib.sha256(data).hexdigest()[:12]
        match = got == want
        ok &= match and len(data) == wantlen
        print('  %-24s %6d B  sha %s  %s' % (name, len(data), got, 'MATCH' if match else 'DIFF (want %s)' % want))
    ag = zf.read('agent.yaml').decode('utf-8', 'replace')
    line = [l for l in ag.splitlines() if l.strip().startswith('model:')]
    print('  declared model:', line[0].strip() if line else '?')
    ec = zf.read('eval_config.yaml').decode('utf-8', 'replace')
    print('  eval_config   :', ' '.join(ec.split()))
    print('  agent_tool    :', 'agent_tool' in ag, '| sub_agents:', 'sub_agents' in ag)
    print('\nVERIFIED AS THE 0.20 PACK:', ok)
