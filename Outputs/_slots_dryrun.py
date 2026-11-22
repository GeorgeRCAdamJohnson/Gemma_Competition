"""Offline dry run of the slots-comparison logic in kaggle_pkg/tool_lora_runner.py (no GPU, no Kaggle):
job coverage per arm/lane and summarize_slots on synthetic records for a passing and a failing case."""
import itertools
import random
import sys
from collections import Counter

sys.path.insert(0, ".")
from kaggle_pkg import tool_lora_runner as r  # noqa: E402

tasks = [f"fastapi_{i}" for i in range(20)] + [f"rich_{i}" for i in range(19)]
R = 4
jobs = {g: r.slot_jobs(tasks, R, g) for g in range(4)}
cover = Counter((t, a, k) for g in jobs for t, a, k in jobs[g])
assert len(cover) == 39 * 2 * R and set(cover.values()) == {1}, "each task/arm/round exactly once"
for g, js in jobs.items():
    assert {a for _, a, _ in js} == {r.slot_arm(g)}, "lane runs only its arm"
print("coverage OK:", {g: len(js) for g, js in jobs.items()}, "| lane arms:", {g: r.slot_arm(g) for g in range(4)})
# task alternates lanes across rounds
lanes_of = {t: {g for g in jobs for tt, a, k in jobs[g] if tt == t and a == "slots8"} for t in tasks}
assert all(v == {0, 1} for v in lanes_of.values()) if R >= 2 else True
print("alternation OK: every task visits both lanes of its arm")


def fake(task, arm, rnd, gpu, solved, secs, t0):
    return {"id": task, "arm": arm, "round": rnd, "gpu": gpu, "status": "completed", "seconds": secs,
            "real_grade": True, "graded": True, "result": {"resolved": solved, "test_exit_code": 0 if solved else 1,
                                                           "error": None},
            "routing": {"fixer_adapter_observed": True, "violations": []}, "wall_start": t0, "wall_end": t0 + secs}


def scenario(slow12, solve12):
    random.seed(1)
    recs = []
    clock = {g: 0.0 for g in range(4)}
    for g in range(4):
        slots = r.SLOT_ARMS[r.slot_arm(g)]
        for i, (t, a, k) in enumerate(jobs[g]):
            secs = 300 * (slow12 if a == "slots12" else 1.0)
            start = clock[g] + (i // slots) * secs  # waves of `slots` concurrent attempts
            solved = random.random() < (solve12 if a == "slots12" else 0.30)
            recs.append(fake(t, a, k, g, solved, secs, start))
    return r.summarize_slots(tasks, recs, R)


for name, slow, s12 in (("expected pass (x1.13 slower, same solve rate)", 1.13, 0.30),
                        ("expected fail (x1.4 slower, -8 points)", 1.4, 0.22)):
    s = scenario(slow, s12)
    print(f"\n{name}: complete {s['complete']} pass_a_b_c {s['pass_a_b_c']}")
    print("  rules:", s["rules"])
    print("  per-lane-hour:", {a: v["attempts_per_lane_hour"] for a, v in s["arms"].items()},
          "| paired:", s["paired"])
