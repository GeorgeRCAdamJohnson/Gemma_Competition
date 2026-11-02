import json, glob, os, re

TDIR = os.path.join(os.path.dirname(__file__), 'out_v21', 'results', 'traces')

def dump(tid):
    f = os.path.join(TDIR, f'trace_{tid}.json')
    t = json.load(open(f, encoding='utf-8'))
    print('='*90)
    print(f'TASK {tid}  (steps={len(t.get("steps", []))})')
    print('='*90)
    step_i = 0
    for s in t.get('steps', []):
        if s.get('source') != 'agent':
            continue
        tcs = s.get('tool_calls') or []
        obs = s.get('observation')
        for c in tcs:
            step_i += 1
            fn = c.get('function_name', '?')
            args = c.get('arguments', {}) or {}
            cmd = ''
            if isinstance(args, dict):
                cmd = args.get('command', '') or ''
                if not cmd:
                    # show arg keys + short values
                    cmd = ' '.join(f'{k}={str(v)[:60]!r}' for k, v in args.items())
            o = str(obs)[:300].replace('\n', ' ')
            print(f'\n[{step_i}] FN={fn}')
            print(f'    CMD: {cmd[:400]}')
            print(f'    OBS: {o}')

for tid in ['rich_4077', 'rich_4079', 'rich_4076', 'rich_3469', 'rich_4070']:
    dump(tid)
