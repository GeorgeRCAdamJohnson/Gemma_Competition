"""The LB ladder is discrete, and the leaderboard structure tells us sigma.

Corrects three things I said earlier:
  1. "E[max of 3] = 12.3/58 -> 0.21" - 0.21 is NOT achievable. floor(k/58*100)/100 jumps
     0.20 (k=12) -> 0.22 (k=13).
  2. sigma = 1 was inferred from ONE pair (12 vs 11). The leaderboard implies sigma ~ 2.
  3. "gap to #1 = 3 tasks" was stale. #1 is 17/58; we are 12/58. Gap = 5.
"""
from math import comb, erf, floor, sqrt

N = 58
disp = lambda k: floor(k / N * 100) / 100


def p_ge_normal(mean, k, sigma):
    """P(draw >= k) with a continuity correction."""
    z = (k - 0.5 - mean) / sigma
    return 0.5 * (1 - erf(z / sqrt(2)))


print('=== the ladder (achievable scores only) ===')
for k in (11, 12, 13, 14, 15, 16, 17):
    tag = {11: 'us (2nd draw)', 12: 'us (best)', 14: '#2-#5 cluster', 17: '#1 Yurnero'}.get(k, '')
    print('  k=%2d -> %.2f   %s' % (k, disp(k), tag))

print('\n=== observed leaderboard (kaggle CLI, 2026-11-02) ===')
print('  #1 Yurnero      0.29 = 17/58   (18 entries, submitted 2026-10-29)')
print('  #2-#5           0.24 = 14/58   (four teams: Yike Xu, MUHAMMED IDRIS, SAVE, chizhu)')
print('  us              0.20 = 12/58   (best of 2 draws; 0.18 = 11/58 on the other)')

print('\n=== what sigma does the #1 result imply? ===')
print('  A cluster of FOUR teams sits at 14/58, so 14 is plausibly the "good artifact" centre.')
print('  #1 reached 17 = centre + 3, with 18 entries.')
print('  %-8s %-14s %-16s %s' % ('sigma', 'P(>=17) 1 draw', 'P(>=17) 18 draws', 'verdict'))
for s in (1, 1.5, 2, 2.5, 3):
    p1 = p_ge_normal(14, 17, s)
    p18 = 1 - (1 - p1) ** 18
    print('  %-8.1f %-14.3f %-16.3f %s' % (s, p1, p18,
          'implausible' if p18 < 0.10 else ('plausible' if p18 < 0.95 else 'near-certain')))
print('\n  => sigma = 1 makes 17/58 in 18 draws a 10% event; sigma ~ 2 makes it ~87%.')
print('  The leaderboard therefore favours sigma ~ 2, NOT the sigma = 1 I inferred from one pair.')
print('  This matches the outside review M3: 5-8 discordant tasks of 129 -> 2-4 of 58.')

print('\n=== the user is right: the step is symmetric, and best-of-2 absorbs the downside ===')
print('  0.20 -> 0.18 proved one task of churn. The same churn upward is 0.20 -> 0.22.')
print('  Each extra draw, from our centre of 11.5:')
print('  %-6s %-12s %-12s %s' % ('sigma', 'P(>=13)=0.22', 'P(>=14)=0.24', 'P(>=15)=0.25'))
for s in (1, 2, 3):
    print('  %-6d %-12.3f %-12.3f %.3f' % (s, p_ge_normal(11.5, 13, s),
                                           p_ge_normal(11.5, 14, s), p_ge_normal(11.5, 15, s)))

print('\n=== so what does a week of travel (7 draws) buy? ===')
for s in (1, 2):
    p13 = p_ge_normal(11.5, 13, s)
    p14 = p_ge_normal(11.5, 14, s)
    print('  sigma=%d: P(reach >=0.22 in 7 draws) = %.2f   P(reach >=0.24) = %.2f'
          % (s, 1 - (1 - p13) ** 7, 1 - (1 - p14) ** 7))
