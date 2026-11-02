"""Ground truth: read the actual submitted zips and report what they contain."""
import hashlib
import io
import zipfile
from pathlib import Path

BASE = Path('local_eval')
ZIPS = [
    ('E4B 0.03 candidate', BASE / 'push_ca5_e4b' / 'submission.zip'),
    ('ca5 31B 0.20 candidate (pulled from Kaggle)', BASE / 'pull_packager_ca5_out' / 'submission.zip'),
    ('A25 router 0.13', BASE / 'pull_packager_a25_out' / 'submission.zip'),
    ('original packager', BASE / 'pull_packager_out' / 'submission.zip'),
]

import yaml


class T(yaml.SafeLoader):
    pass


def _any(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


T.add_multi_constructor('', _any)

for label, p in ZIPS:
    print('=' * 88)
    print('%s\n  %s  (%.0f B, %s)' % (label, p, p.stat().st_size if p.exists() else 0,
                                       p.stat().st_mtime if p.exists() else ''))
    if not p.exists():
        print('  MISSING')
        continue
    with zipfile.ZipFile(p) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        print('  files: %d | uncompressed %d B' % (len(infos), sum(i.file_size for i in infos)))
        for i in infos:
            data = zf.read(i.filename)
            print('    %-34s %7d B  sha256 %s'
                  % (i.filename, i.file_size, hashlib.sha256(data).hexdigest()[:12]))

        def read(name):
            try:
                return zf.read(name)
            except KeyError:
                return None

        ag = read('agent.yaml')
        if ag:
            try:
                d = yaml.load(ag.decode('utf-8'), Loader=T) or {}
                print('  declared model : %s' % d.get('model'))
                print('  agent name     : %s' % d.get('name'))
                print('  agent keys     : %s' % sorted(d.keys()))
            except Exception as e:
                print('  agent.yaml parse failed:', e)
            txt = ag.decode('utf-8', 'replace')
            print('  agent_tool ref : %s | sub_agents ref: %s'
                  % ('agent_tool' in txt, 'sub_agents' in txt))

        ec = read('eval_config.yaml')
        if ec:
            d = yaml.load(ec.decode('utf-8'), Loader=T) or {}
            ev = d.get('evaluation', d)
            print('  caps           : %s' % {k: ev.get(k) for k in
                                             ('max_tool_calls', 'max_time_minutes',
                                              'max_turns', 'timeout_seconds')})

        sm = read('configs/sampling.yaml')
        if sm:
            print('  sampling       : %s' % (yaml.load(sm.decode('utf-8'), Loader=T) or {}))

        pr = read('prompts/system.md')
        if pr:
            print('  prompt         : %d B  sha1 %s  sha256 %s'
                  % (len(pr), hashlib.sha1(pr).hexdigest()[:12], hashlib.sha256(pr).hexdigest()[:12]))
            first = pr.decode('utf-8', 'replace').splitlines()[0]
            print('  prompt line 1  : %s' % first[:96])
        for n in zf.namelist():
            if 'system' in n.lower() and n != 'prompts/system.md':
                print('  EXTRA PROMPT   : %s (%d B)' % (n, len(zf.read(n))))
