"""Does the OFFICIAL Kaggle eval image also fail to import inline_snapshot / dirty_equals?

If yes, the 46 blocked tasks are unresolvable for everyone and the local rig is faithful.
If no, the local rig is genuinely missing test deps and has been under-measuring.
"""
import re
from collections import Counter
from pathlib import Path

RIG = Path(__file__).resolve().parent
KAGGLE_LOGS = RIG.parents[1] / 'kaggle_pkg' / 'out_e4b' / 'results' / 'test_outputs'
LOCAL_LOGS = RIG / 'm1_capped' / 'agent_ctrl_e4b_r0' / 'test_outputs'

for label, d in [('KAGGLE (official eval image)', KAGGLE_LOGS), ('LOCAL (parity rig)', LOCAL_LOGS)]:
    logs = sorted(d.glob('*.log'))
    coll, mods = [], Counter()
    for p in logs:
        t = p.read_text(encoding='utf-8', errors='replace')
        if 'ERROR collecting' in t:
            coll.append(p.stem)
        for m in re.findall(r"No module named '([^']+)'", t):
            mods[m] += 1
    print(f'{label}: {len(logs)} logs, {len(coll)} with collection errors')
    print('   missing modules:', dict(mods.most_common(6)) or 'none')
    if coll:
        print('   blocked:', ' '.join(coll[:10]))
    print()
