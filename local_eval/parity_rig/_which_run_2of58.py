"""Which of our runs is most likely to score 2/58?

Two models for the public 58:
  A) subset  - the 58 are a subset of our 129 (58+71=129), so k is hypergeometric
  B) separate- k ~ Binomial(58, rate)
Then: which run's solve set, restricted to LB-valid tasks, predicts 2?
"""
import json
from math import comb
from pathlib import Path

RIG = Path(__file__).resolve().parent
PHANTOM = {'requests_7309', 'requests_7315', 'requests_7427'}
RUNS = {
    'r0 (top_k64)': RIG / 'm1_capped' / 'agent_ctrl_e4b_r0',
    'r1 (top_k64)': RIG / 'm1_capped' / 'agent_ctrl_e4b_r1',
    'fa (top_k0)': RIG / 'm1_faithful' / 'agent_ctrl_e4b_r0',
}


def rs(p):
    if not Path(p).exists():
        return None
    return {r['task'] for r in json.loads(Path(p).read_text(encoding='utf-8')) if r.get('resolved_here')}


gold = rs(RIG / 'replay_gold129_files.json')
empty = rs(RIG / 'replay_empty129_files.json')
valid = (gold - empty) if (gold is not None and empty is not None) else gold

recs = {k: {r['instance_id']: r for r in
            (json.loads(l) for l in (Path(d) / 'task_results.jsonl').read_text(encoding='utf-8').splitlines() if l.strip())}
        for k, d in RUNS.items()}
ids = sorted(set.intersection(*[set(v) for v in recs.values()]))
N = len(ids)
solved = {k: {t for t in ids if recs[k][t].get('resolved')} for k in RUNS}

print('gold-valid: %d   empty-pass: %s   LB-valid set: %d' % (
    len(gold), len(empty) if empty is not None else 'pending', len(valid)))
print('LB-valid repos:', {r: sum(1 for t in valid if t.startswith(r)) for r in ['rich', 'fastapi', 'requests', 'httpx']})
print()


def hyper(S, k=2, n=58, N=N):
    if S < k or N - S < n - k:
        return 0.0
    return comb(S, k) * comb(N - S, n - k) / comb(N, n)


def bino(p, k=2, n=58):
    return comb(n, k) * p ** k * (1 - p) ** (n - k)


print('%-14s %-6s %-8s %-9s %-9s %-10s %-10s %s' % (
    'run', 'solved', 'genuine', 'valid-solv', 'rate/valid', 'E[58]', 'P(k=2)', 'P(k<=2)'))
for k, S in solved.items():
    g = S - PHANTOM
    v = S & valid
    rate = len(v) / len(valid) if valid else 0
    e58 = 58 * rate
    pk = hyper(len(S), 2)
    pk2 = sum(hyper(len(S), i) for i in range(3))
    print('%-14s %-6d %-8d %-9d %-9.3f %-10.1f %-10.3f %.3f' % (
        k, len(S), len(g), len(v), rate, e58, pk, pk2))

print('\n--- if the 58 were a RANDOM subset of our 129 (hypergeometric) ---')
for S in (9, 10, 12, 14, 15):
    print('  solved=%2d -> E[k]=%.1f  P(k=2)=%.3f  P(k<=2)=%.3f' % (
        S, S * 58 / N, hyper(S, 2), sum(hyper(S, i) for i in range(3))))

print('\n--- if the 58 were a separate clean set (binomial) ---')
for S in (9, 10, 12, 14, 15):
    p = S / N
    print('  rate=%.3f -> E[k]=%.1f  P(k=2)=%.3f  P(k<=2)=%.3f' % (
        p, 58 * p, bino(p, 2), sum(bino(p, i) for i in range(3))))

print('\n--- overlap of each run with the LB-valid set ---')
for k, S in solved.items():
    print('  %-14s valid solves: %s' % (k, sorted(S & valid)))
