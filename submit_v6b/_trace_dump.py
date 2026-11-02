import json

for f in ['rich_4070', 'rich_4079', 'rich_4076']:
    d = json.load(open(rf'out_v6b\results\traces\trace_{f}.json'))
    print(f'\n==================== {f} ====================')
    for s in d['steps']:
        msg = (s.get('message') or '').strip().replace('\n', ' ')
        tcs = s.get('tool_calls') or []
        if tcs:
            for tc in tcs:
                fn = tc.get('function_name')
                ar = tc.get('arguments') or {}
                ars = {k: (str(v)[:60]) for k, v in ar.items()}
                print(f"  [{s.get('step_id')}] CALL {fn} {json.dumps(ars)[:150]}  | think: {msg[:70]}")
        elif s.get('source') == 'agent' and msg:
            print(f"  [{s.get('step_id')}] (no call) think: {msg[:120]}")
    fm = d.get('final_metrics', {})
    print(f"  FINAL: steps={fm.get('total_steps')} completion_tok={fm.get('total_completion_tokens')}")
