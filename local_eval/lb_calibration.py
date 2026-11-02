"""Calibrate the LB against the 129-task practice set using the #1 competitor's own number.

Yurnero (1st, 0.29) states: "I ran all 129 tasks this weekend on the Kaggle side ... landing
about 30%ish across the whole board." That gives an independent (129-rate -> LB) data point.
"""
from math import floor

N = 58
disp = lambda k: floor(k / N * 100) / 100

LEADER_RATE = 0.30
LEADER_K = 17          # 0.29 = 17/58

print('=== the three candidate models for how the 58 relate to the 129 ===\n')

# Model 1: random subset of all 129 (dead tasks included)
p_random = LEADER_K and (LEADER_RATE * 129) * N / 129
print('1. RANDOM SUBSET of the 129 (dead tasks included)')
print('   leader solves 0.30 x 129 = %.1f tasks' % (LEADER_RATE * 129))
print('   predicted on 58      = %.1f/58  -> %.2f' % (LEADER_RATE * 129 * N / 129,
                                                      disp(round(LEADER_RATE * 129 * N / 129))))
print('   observed             = %d/58  -> %.2f' % (LEADER_K, disp(LEADER_K)))
print('   ERROR                = %.1f tasks' % abs(LEADER_RATE * 129 * N / 129 - LEADER_K))

# Model 2: filtered to the 59 truly-solvable (our earlier inventory)
print('\n2. FILTERED to the 59 truly-solvable (my earlier inventory)')
print('   leader solves %.1f of the 129; if the LB keeps only solvable tasks, the rate becomes'
      % (LEADER_RATE * 129))
print('   %.1f/59 = %.0f%% -> predicted %.1f/58 -> %.2f' % (
    LEADER_RATE * 129, 100 * LEADER_RATE * 129 / 59, LEADER_RATE * 129 / 59 * N,
    disp(round(LEADER_RATE * 129 / 59 * N))))
print('   ERROR                = %.1f tasks' % abs(LEADER_RATE * 129 / 59 * N - LEADER_K))

# Model 3: filtered to live tasks only (129 minus 34 dead = 95)
print('\n3. FILTERED to the 95 live tasks (129 minus 34 dead)')
print('   %.1f/95 = %.0f%% -> predicted %.1f/58 -> %.2f' % (
    LEADER_RATE * 129, 100 * LEADER_RATE * 129 / 95, LEADER_RATE * 129 / 95 * N,
    disp(round(LEADER_RATE * 129 / 95 * N))))
print('   ERROR                = %.1f tasks' % abs(LEADER_RATE * 129 / 95 * N - LEADER_K))

print('\n=== verdict ===')
print('  Only the RANDOM-SUBSET model reproduces the #1 score (%.1f vs %d tasks).' % (
    LEADER_RATE * 129 * N / 129, LEADER_K))
print('  The filtered models over-predict by %.1f and %.1f tasks respectively.' % (
    abs(LEADER_RATE * 129 / 59 * N - LEADER_K), abs(LEADER_RATE * 129 / 95 * N - LEADER_K)))
print('  => the public 58 behave like a random subset of the 129, NOT a filtered one.')

print('\n=== what that means for us ===')
for label, kaggle129 in [('us, Kaggle side (n=1 run)', 10), ('us, local ca5 r1/fa', 11),
                         ('leader', 39)]:
    rate = kaggle129 / 129
    pred = rate * N
    print('  %-26s %3d/129 = %5.1f%%  -> predicted %.1f/58 = %.2f' % (
        label, kaggle129, 100 * rate, pred, disp(round(pred))))

print('\n  our observed: 2/58 = 0.03')
print('  predicted from the Kaggle-side 10/129: %.1f/58' % (10 / 129 * N))
print('  the gap is %.1f tasks - within sigma~2 noise, but it is a LOW draw.' % (10 / 129 * N - 2))

print('\n=== the real gap ===')
print('  leader: 39/129 = 30%')
print('  us    : 10/129 = 7.8% (Kaggle side), 12/129 local')
print('  ratio : %.1fx' % (39 / 10))
print('  To match 0.29 we need ~39/129. To reach the 0.24 cluster (14/58) we need %.0f/129.' % (14 * 129 / N))
