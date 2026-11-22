"""Single-pass LoRA validation using the existing isolated Kaggle evaluator."""
import concurrent.futures
import json
import math
import os
from pathlib import Path
import random
import shutil
import sys
import threading
import time
import traceback
import urllib.request

from kaggle_pkg.memory_isolated_runner import run_task


MODEL = "gemma-4-e4b-it-qat-w4a16-ct"
ADAPTER = "tool_state_p5"
EVIDENCE_ADAPTER = "evidence_to_edit_seed"
EVIDENCE_EVAL_SECONDS = 3600
EVIDENCE_NOTEBOOK_SECONDS = 4800
EVIDENCE_REPEAT_ROUNDS = 9
EVIDENCE_REPEAT_SECONDS = 9600
EVIDENCE_REPEAT_NOTEBOOK_SECONDS = 10800
REPAIR_DECISIONS_ADAPTER = "repair_decisions_v1"
REPAIR_DECISIONS_ROUNDS = 5
REPAIR_DECISIONS_SECONDS = 9600
REPAIR_DECISIONS_NOTEBOOK_SECONDS = 10800
THINKING_CONTROL_BUDGET = 4096
THINKING_MAX_ROUNDS = 5
THINKING_TASKS = 20
THINKING_NOTEBOOK_SECONDS = 5400
THINKING_EVAL_SECONDS = 4200
TASK_SECONDS = 2000
EVALUATION_SECONDS = 12000
CONCURRENCY = 8
REPEAT_ROUNDS = 16
REPEAT_SEED = 32768
REPEAT_SECONDS = 16800
REPEAT_NOTEBOOK_SECONDS = 18000
# Slots-per-lane validation (GPU rule 3, .kiro/steering/gpu-usage.md): identical policy, two lanes at 8 slots vs two
# lanes at 12 slots; every task/round runs once in each arm.
SLOT_ARMS = {"slots8": 8, "slots12": 12}
SLOT_LANES = {"slots8": (0, 1), "slots12": (2, 3)}
SLOT_MAX_ROUNDS = 6
SLOT_EVAL_SECONDS = 4800
SLOT_NOTEBOOK_SECONDS = 6000


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def request(base_url, endpoint, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base_url + endpoint, data=data,
        headers={"Content-Type": "application/json", "Authorization": "Bearer EMPTY"},
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        return json.load(response)


def logprob_effect(responses, *, adapter_name=ADAPTER):
    if [response["model"] for response in responses] != [MODEL, MODEL, adapter_name, adapter_name]:
        raise ValueError("Require two base and two adapter responses in request order")
    distributions = []
    for response in responses:
        values = response["choices"][0]["logprobs"]["top_logprobs"][0]
        if not values or not all(math.isfinite(value) for value in values.values()):
            raise ValueError("Missing or nonfinite first-token logprobs")
        distributions.append(values)
    base, base_repeat, adapter, adapter_repeat = distributions
    if base != base_repeat or adapter != adapter_repeat:
        raise ValueError("Repeated deterministic logprob requests were not reproducible")
    common = set(base) & set(adapter)
    delta = max((abs(base[token] - adapter[token]) for token in common), default=0.0)
    if set(base) == set(adapter) and delta <= 1e-6:
        raise ValueError("No measurable adapter-on/off logprob effect")
    return {"repeatable": True, "max_shared_token_logprob_delta": delta,
            "top_token_sets_differ": set(base) != set(adapter)}


def probe_context_window(base_url, token_id, context_length, receipt):
    advertised = request(base_url, "/models")["data"]
    base = next(item for item in advertised if item["id"] == MODEL)
    if base.get("max_model_len") != context_length:
        raise RuntimeError(f"Server does not advertise registered {context_length}-token context")
    input_tokens = context_length - 8
    response = request(base_url, "/completions", {
        "model": ADAPTER, "prompt": [token_id] * input_tokens,
        "temperature": 0, "seed": 0, "max_tokens": 8,
    })
    save(receipt, response)
    usage = response.get("usage") or {}
    if (response["model"] != ADAPTER or usage.get("prompt_tokens") != input_tokens
            or usage.get("completion_tokens", 0) < 1):
        raise RuntimeError("Full-window adapter request gate failed")
    return response


def audit_routing(trace, fixer_model=ADAPTER, *, adapter_name=ADAPTER):
    counts = {"fixer": 0, "verifier": 0}
    unknown = {"fixer": 0, "verifier": 0}
    violations = []
    events = []
    for step in trace.get("steps", []):
        if step.get("source") != "agent":
            continue
        extra = step.get("extra") or {}
        events.append((extra.get("author"), step.get("model_name")))
        for call in step.get("tool_calls", []):
            detail = call.get("extra") or {}
            events.append((detail.get("author"), detail.get("model_version")))
    for entry in trace.get("entries", []):
        if entry.get("type") in ("thinking", "text", "final", "tool_call", "usage"):
            events.append((entry.get("author"), entry.get("model")))
    for author, model in events:
        if author not in counts:
            continue
        if not model:
            unknown[author] += 1
            continue
        model = model.removeprefix("openai/")
        if model == (fixer_model if author == "fixer" else MODEL):
            counts[author] += 1
        else:
            violations.append({"author": author, "model": model})
    expected_observed = counts["fixer"] > 0 and not violations
    return {"observed": counts, "unknown": unknown, "violations": violations,
            "fixer_expected_model_observed": expected_observed,
            "fixer_adapter_observed": expected_observed and fixer_model == adapter_name}


def summarize(task_ids, records):
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)) or not set(ids).issubset(task_ids):
        raise ValueError("Duplicate or unexpected task result")
    graded = [record for record in records if record["real_grade"]]
    return {
        "experiment": "p5 LoRA; G_startup fixer only; verifier unchanged",
        "complete": set(ids) == set(task_ids) and len(graded) == len(task_ids),
        "expected": len(task_ids), "recorded": len(records), "graded": len(graded),
        "resolved_among_graded": sum(record["result"]["resolved"] for record in graded),
        "missing_task_ids": sorted(set(task_ids) - set(ids)),
        "ungraded_task_ids": [record["id"] for record in records if not record["real_grade"]],
        "fixer_adapter_observed_tasks": sum(
            record["routing"]["fixer_adapter_observed"] for record in records),
        "routing_violations": [record["id"] for record in records
                               if record["routing"]["violations"]],
        "errors": {record["id"]: {"status": record["status"],
                                  "error": (record.get("result") or {}).get("error"),
                                  "result_error": record.get("result_error"),
                                  "trace_error": record.get("trace_error")}
                   for record in records if record["status"] != "completed"
                   or (record.get("result") or {}).get("error") or not record["real_grade"]
                   or record.get("trace_error")},
        "warning": "One diagnostic pass, not an adapter-off comparison or leaderboard prediction. "
                   "Missing, errored and ungraded tasks are reported separately.",
    }


def summarize_controls(task_ids, records, rounds):
    expected = {(arm, rnd, task) for arm in ("base", "adapter")
                for rnd in range(1, rounds + 1) for task in task_ids}
    keys = [(record["arm"], record["round"], record["id"]) for record in records]
    if len(keys) != len(set(keys)) or not set(keys).issubset(expected):
        raise ValueError("Duplicate or unexpected control execution")
    runs = {f"{arm}_round_{rnd}": summarize(task_ids, [
        record for record in records if record["arm"] == arm and record["round"] == rnd
    ]) for arm in ("base", "adapter") for rnd in range(1, rounds + 1)}
    by_key = dict(zip(keys, records))
    pairs = []
    for rnd in range(1, rounds + 1):
        for task in task_ids:
            base = by_key.get(("base", rnd, task))
            adapter = by_key.get(("adapter", rnd, task))
            base_resolved = adapter_resolved = None
            if base is not None and adapter is not None and base["real_grade"] and adapter["real_grade"]:
                base_resolved = base["result"]["resolved"]
                adapter_resolved = adapter["result"]["resolved"]
            pairs.append({"id": task, "round": rnd,
                          "paired_graded": base_resolved is not None and adapter_resolved is not None,
                          "base_resolved": base_resolved, "adapter_resolved": adapter_resolved})
    complete = set(keys) == expected and all(value["complete"] for value in runs.values())
    return {
        "experiment": "historically solved E4B positive controls; paired G_startup base/p5",
        "complete": complete, "expected_executions": len(expected), "runs": runs, "pairs": pairs,
        "base_resolved": sum(pair["base_resolved"] is True for pair in pairs),
        "adapter_resolved": sum(pair["adapter_resolved"] is True for pair in pairs),
        "paired_graded": sum(pair["paired_graded"] for pair in pairs),
        "routing_verified": complete and all(
            record["routing"].get("fixer_expected_model_observed")
            and record["routing"]["fixer_adapter_observed"] == (record["arm"] == "adapter")
            for record in records),
        "warning": "Selected positive controls, not a held-out capability or leaderboard estimate. "
                   "Historical solves do not guarantee this different policy will solve every repeat.",
    }


def verified_solve(record, *, arm="adapter"):
    row = record.get("result") or {}
    routing = record.get("routing") or {}
    return bool(
        record["status"] == "completed" and record.get("real_grade")
        and row.get("resolved") is True and row.get("test_exit_code") == 0
        and not row.get("error") and not record.get("result_error")
        and not record.get("trace_error")
        and (routing.get("fixer_adapter_observed") if arm == "adapter"
             else routing.get("fixer_expected_model_observed") and not routing.get("fixer_adapter_observed"))
        and not routing.get("violations"))


def summarize_evidence_seed(task_ids, records):
    summary = summarize(task_ids, records)
    verified = [record["id"] for record in records if verified_solve(record)]
    summary.update(
        experiment="Evidence-to-edit seed; single score39 pass; fixer only; verifier unchanged",
        verified_solves=len(verified), verified_solve_ids=verified,
        overflows=sum("ContextWindowExceededError" in str((record.get("result") or {}).get("error"))
                      for record in records),
        complete=summary["complete"] and summary["fixer_adapter_observed_tasks"] == len(task_ids)
        and not summary["errors"] and not summary["routing_violations"],
    )
    return summary


def summarize_seed_repeats(task_ids, records):
    rounds = {}
    seen = set()
    for record in records:
        key = (record["round"], record["id"])
        if (key in seen or key[0] not in range(2, 2 + EVIDENCE_REPEAT_ROUNDS)
                or key[1] not in task_ids or record["arm"] != "adapter"):
            raise ValueError(f"Duplicate or unexpected Seed39 result: {key}")
        seen.add(key)
    for rnd in range(2, 2 + EVIDENCE_REPEAT_ROUNDS):
        attempts = [r for r in records if r["round"] == rnd
                    and not r["status"].startswith("not_started_")]
        rounds[rnd] = summarize_evidence_seed(task_ids, attempts)
    violations = [{"round": r["round"], "id": r["id"]} for r in records
                  if r["routing"]["violations"]]
    deadline_hits = sum(r["status"] == "evaluation_deadline" for r in records)
    expected = len(task_ids) * EVIDENCE_REPEAT_ROUNDS
    attempted = sum(r["recorded"] for r in rounds.values())
    return {
        "experiment": "Seed39 32K; nine additional adapter-only rounds",
        "complete": attempted == expected and not violations and not deadline_hits,
        "expected_executions": expected, "attempted": attempted, "recorded": len(records),
        "global_deadline_hits": deadline_hits, "routing_violations": violations,
        "verified_solves": sum(r["verified_solves"] for r in rounds.values()),
        "overflows": sum(r["overflows"] for r in rounds.values()),
        "rounds": rounds,
        "warning": "Round 1 is the separate original Seed39 run. Comparisons to p5/base are "
                   "descriptive, not concurrent matched attempts or a leaderboard prediction.",
    }


def repair_decision_jobs(task_ids, gpu, first_round=1):
    for rnd in range(first_round, first_round + REPAIR_DECISIONS_ROUNDS):
        for task in task_ids[gpu::4]:
            yield task, "adapter", rnd


def summarize_repair_decisions(task_ids, records, first_round=1):
    expected = {(rnd, task) for rnd in range(first_round, first_round + REPAIR_DECISIONS_ROUNDS)
                for task in task_ids}
    keys = [(record["round"], record["id"]) for record in records]
    if (len(keys) != len(set(keys)) or not set(keys).issubset(expected)
            or any(record.get("arm") != "adapter" for record in records)):
        raise ValueError("Duplicate or unexpected repair-decisions task/round result")
    rounds = {}
    for rnd in range(first_round, first_round + REPAIR_DECISIONS_ROUNDS):
        round_records = [record for record in records if record["round"] == rnd]
        rounds[rnd] = summarize_evidence_seed(task_ids, round_records)
    violations = [{"round": record["round"], "id": record["id"]}
                  for record in records if record["routing"]["violations"]]
    deadline_hits = sum(record["status"] == "evaluation_deadline" for record in records)
    attempted = sum(not record["status"].startswith("not_started_") for record in records)
    complete = (set(keys) == expected and all(summary["complete"] for summary in rounds.values())
                and not violations and not deadline_hits)
    return {
        "experiment": "Repair-decisions v1 adapter; Seed39 32K; five adapter-only rounds",
        "complete": complete,
        "expected_executions": len(expected),
        "attempted": attempted,
        "recorded": len(records),
        "global_deadline_hits": deadline_hits,
        "routing_violations": violations,
        "verified_solves": sum(summary["verified_solves"] for summary in rounds.values()),
        "overflows": sum(summary["overflows"] for summary in rounds.values()),
        "rounds": rounds,
        "warning": "Adapter-only diagnostic; historical comparisons are descriptive, "
                   "not concurrent matched attempts or a leaderboard prediction.",
    }


def seed_repeat_jobs(task_ids, gpu):
    for rnd in range(2, 2 + EVIDENCE_REPEAT_ROUNDS):
        for task in task_ids[gpu::4]:
            yield task, "adapter", rnd


def paired_jobs(task_ids, rounds, arms=("base", "adapter")):
    rng = random.Random(REPEAT_SEED)
    for rnd in range(1, rounds + 1):
        order = list(task_ids)
        rng.shuffle(order)
        for index, task in enumerate(order):
            yield rnd, task, arms if (index + rnd) % 2 else arms[::-1]


def slot_arm(gpu):
    return next(arm for arm, lanes in SLOT_LANES.items() if gpu in lanes)


def slot_jobs(task_ids, rounds, gpu):
    """Jobs for one lane in the slots comparison. Each arm runs every task once per round across its two lanes; a
    task alternates lanes between rounds so lane identity does not align with task identity. Rounds are interleaved
    in order so a deadline cut leaves complete early rounds."""
    arm = slot_arm(gpu)
    position = SLOT_LANES[arm].index(gpu)
    return [(task, arm, rnd) for rnd in range(1, rounds + 1)
            for index, task in enumerate(task_ids) if (index + rnd) % 2 == position]


def summarize_slots(task_ids, records, rounds):
    """Throughput, timing and outcome per slot arm, and paired (task, round) outcome deltas. Pass rule (a)-(c) from the
    pre-registration; rule (d), no new vLLM error types, is checked from the saved vllm_gpu*.log files after collection."""
    expected = {(task, arm, rnd) for task in task_ids for arm in SLOT_ARMS for rnd in range(1, rounds + 1)}
    keys = [(record["id"], record["arm"], record["round"]) for record in records]
    if len(keys) != len(set(keys)) or not set(keys) <= expected:
        raise ValueError("Duplicate or unexpected slots-comparison result")
    started = [record for record in records if not record["status"].startswith("not_started_")]
    arms = {}
    for arm in SLOT_ARMS:
        rows = [record for record in started if record["arm"] == arm]
        lane_hours = 0.0
        for gpu in SLOT_LANES[arm]:
            lane = [record for record in rows if record["gpu"] == gpu and record.get("wall_start")]
            if lane:
                lane_hours += (max(r["wall_end"] for r in lane) - min(r["wall_start"] for r in lane)) / 3600
        seconds = [record["seconds"] for record in rows if record.get("seconds") is not None]
        arms[arm] = {
            "slots_per_lane": SLOT_ARMS[arm], "lanes": list(SLOT_LANES[arm]), "attempts": len(rows),
            "verified_solves": sum(verified_solve(record, arm="adapter") for record in rows),
            "real_graded": sum(bool(record["real_grade"]) for record in rows),
            "overflows": sum("ContextWindow" in str((record.get("result") or {}).get("error") or "")
                             for record in rows),
            "lane_hours": round(lane_hours, 4),
            "attempts_per_lane_hour": round(len(rows) / lane_hours, 3) if lane_hours else None,
            "mean_seconds": round(sum(seconds) / len(seconds), 1) if seconds else None,
            "max_seconds": max(seconds) if seconds else None,
            "over_30_min": sum(s > 1800 for s in seconds),
        }
    by_key = {(record["id"], record["arm"], record["round"]): record for record in started}
    pairs = [(by_key[(task, "slots8", rnd)], by_key[(task, "slots12", rnd)])
             for task in task_ids for rnd in range(1, rounds + 1)
             if (task, "slots8", rnd) in by_key and (task, "slots12", rnd) in by_key]
    solve = lambda record: int(verified_solve(record, arm="adapter"))
    paired = {
        "pairs": len(pairs),
        "verified_slots8": sum(solve(a) for a, _ in pairs),
        "verified_slots12": sum(solve(b) for _, b in pairs),
        "only_slots8": sum(solve(a) and not solve(b) for a, b in pairs),
        "only_slots12": sum(solve(b) and not solve(a) for a, b in pairs),
    }
    paired["rate_delta_points"] = (round(100 * (paired["verified_slots12"] - paired["verified_slots8"]) / len(pairs), 2)
                                   if pairs else None)
    a8, a12 = arms["slots8"], arms["slots12"]
    throughput = (a12["attempts_per_lane_hour"] / a8["attempts_per_lane_hour"]
                  if a8["attempts_per_lane_hour"] and a12["attempts_per_lane_hour"] else None)
    duration = (a12["mean_seconds"] / a8["mean_seconds"] if a8["mean_seconds"] and a12["mean_seconds"] else None)
    rules = {
        "a_throughput_ratio": round(throughput, 3) if throughput else None,
        "a_pass": bool(throughput and throughput >= 1.2),
        "b_duration_ratio": round(duration, 3) if duration else None,
        "b_pass": bool(duration and duration <= 1.25 and a12["over_30_min"] == 0),
        "c_pass": paired["rate_delta_points"] is not None and paired["rate_delta_points"] >= -2.0,
        "d": "check vllm_gpu*.log offline: no error types other than context overflow",
    }
    complete = len(started) == len(expected)
    return {
        "experiment": "slots per lane: 8 vs 12, identical policy (repair-decisions fixer adapter, base verifier)",
        "complete": complete, "expected_executions": len(expected), "recorded": len(records),
        "started": len(started), "rounds": rounds, "arms": arms, "paired": paired, "rules": rules,
        "pass_a_b_c": complete and rules["a_pass"] and rules["b_pass"] and rules["c_pass"],
        "warning": "Throughput/timing apply to TP1 experiment lanes, not scorer wall time; outcome check is paired "
                   "by task and round. Partial results are descriptive.",
    }


def run_paired_repeats(task_ids, rounds, evaluate, deadline, *, gpus=4, slots=CONCURRENCY,
                      arms=("base", "adapter")):
    if slots < 2 or slots % 2 or gpus < 1:
        raise ValueError("Require a positive number of GPUs and an even slot count per GPU")
    jobs = iter(paired_jobs(task_ids, rounds, arms))
    dispatch = threading.Lock()
    abort = threading.Event()

    def worker(gpu, pool):
        while True:
            with dispatch:
                job = next(jobs, None) if not abort.is_set() and time.monotonic() < deadline else None
            if job is None:
                return
            rnd, task, arms = job
            pair = [pool.submit(evaluate, gpu, task, arm, rnd) for arm in arms]
            for attempt in pair:
                attempt.result()

    with concurrent.futures.ThreadPoolExecutor(max_workers=gpus * slots // 2) as coordinators:
        with concurrent.futures.ThreadPoolExecutor(max_workers=gpus * slots) as evaluators:
            workers = [coordinators.submit(worker, gpu, evaluators)
                       for gpu in range(gpus) for _ in range(slots // 2)]
            try:
                for future in concurrent.futures.as_completed(workers):
                    future.result()
            finally:
                abort.set()


def thinking_plan(rounds, treatment_budget):
    if type(rounds) is not int or not 1 <= rounds <= THINKING_MAX_ROUNDS:
        raise ValueError(f"The 90-minute thinking profile supports 1-{THINKING_MAX_ROUNDS} rounds")
    if type(treatment_budget) is not int or not 0 <= treatment_budget < THINKING_CONTROL_BUDGET:
        raise ValueError(f"Fixer treatment budget must be 0-{THINKING_CONTROL_BUDGET - 1}")
    return {f"think{budget}": budget for budget in (THINKING_CONTROL_BUDGET, treatment_budget)}


def summarize_repeats(task_ids, records, rounds, *, thinking_budget=None):
    thinking_compare = thinking_budget is not None
    control, treatment = (thinking_plan(rounds, thinking_budget) if thinking_compare
                          else ("base", "adapter"))
    arms = (control, treatment)

    def solved(record):
        return verified_solve(record, arm="adapter" if thinking_compare else record["arm"])

    def clean(record):
        return (record["status"] == "completed" and record["real_grade"]
                and not (record.get("result") or {}).get("error") and not record.get("result_error")
                and not record.get("trace_error") and record["routing"].get("fixer_expected_model_observed")
                and not record["routing"].get("violations")
                and (not thinking_compare or record["routing"].get("fixer_adapter_observed")))

    by_key = {(r["round"], r["id"], r["arm"]): r for r in records}
    expected = {(rnd, task, arm) for rnd in range(1, rounds + 1) for task in task_ids
                for arm in arms}
    if len(by_key) != len(records) or not by_key.keys() <= expected:
        raise ValueError("Duplicate or unexpected repeat result")

    def counts():
        values = {"attempted": 0, "valid_grades": 0, "verified_solves": 0,
                  "overflows": 0, "other_abnormal_outcomes": 0}
        if thinking_compare:
            values.update(task_timeouts=0, collection_errors=0, ungraded=0)
        return values

    by_round = {rnd: {arm: counts() for arm in arms} for rnd in range(1, rounds + 1)}
    by_task = {task: {arm: counts() for arm in arms} for task in task_ids}
    for (rnd, task, arm), record in by_key.items():
        status = record["status"]
        row = record.get("result") or {}
        overflow = "ContextWindowExceededError" in str(row.get("error"))
        started = not status.startswith("not_started_")
        real_grade = record["real_grade"]
        abnormal = (status != "completed" or not real_grade or row.get("error")
                    or record.get("result_error") or record.get("trace_error"))
        for bucket in (by_round[rnd][arm], by_task[task][arm]):
            bucket["attempted"] += started
            bucket["valid_grades"] += bool(clean(record) if thinking_compare else real_grade)
            bucket["verified_solves"] += solved(record)
            bucket["overflows"] += overflow
            bucket["other_abnormal_outcomes"] += bool(abnormal and not overflow)
            if thinking_compare:
                bucket["task_timeouts"] += status == "task_timeout"
                bucket["collection_errors"] += bool(record.get("collection_error"))
                bucket["ungraded"] += started and not real_grade
    totals = {arm: {key: sum(row[arm][key] for row in by_round.values()) for key in counts()}
              for arm in arms}
    clean_pairs = {"both_solved": 0, f"{control}_only": 0, f"{treatment}_only": 0, "neither_solved": 0}
    paired_attempts = 0
    for rnd in by_round:
        for task in task_ids:
            base, adapter = (by_key.get((rnd, task, arm)) for arm in arms)
            if base is None or adapter is None:
                continue
            paired_attempts += all(not row["status"].startswith("not_started_") for row in (base, adapter))
            if all(clean(row) for row in (base, adapter)):
                a, b = solved(base), solved(adapter)
                clean_pairs[{(True, True): "both_solved", (True, False): f"{control}_only",
                             (False, True): f"{treatment}_only", (False, False): "neither_solved"}[a, b]] += 1
    routing_violations = [{"task": r["id"], "round": r["round"], "arm": r["arm"]}
                          for r in records if r["routing"]["violations"]]
    deadline_hits = sum(r["status"] == "evaluation_deadline" for r in records)
    complete = paired_attempts == len(task_ids) * rounds and not deadline_hits and not routing_violations
    differences = [row[treatment]["verified_solves"] - row[control]["verified_solves"]
                   for row in by_task.values()]
    delta = sum(differences)
    p = None
    if complete:
        # Flip whole task histories together so repeats are not treated as independent tasks.
        rng = random.Random(REPEAT_SEED)
        exceed = sum(sum(d if rng.getrandbits(1) else -d for d in differences) >= delta
                     for _ in range(10000))
        p = (exceed + 1) / 10001
    result = {
        "experiment": (f"32K paired fixer thinking {THINKING_CONTROL_BUDGET} vs {thinking_budget} "
                       "on maintenance tasks"
                       if thinking_compare else
                       "32K paired G_startup base vs p5 on the historical score39 cohort"),
        "complete": complete, "expected_executions": len(expected), "recorded": len(records),
        "expected_pairs": len(task_ids) * rounds, "attempted_pairs": paired_attempts,
        "global_deadline_hits": deadline_hits, "routing_violations": routing_violations,
        "totals": totals, "rounds": by_round, "tasks": by_task, "clean_grade_pairs": clean_pairs,
        "verified_solve_delta": delta, "gain_per_round": delta / rounds if complete else None,
        "one_sided_task_cluster_p": p, "positive_signal": p is not None and p <= .05 and delta >= rounds,
        "warning": "Selected historical cohort, not a held-out or leaderboard estimate. "
                   "Unstarted attempts are not scored. Abnormal attempts are not valid grades.",
    }
    if thinking_compare:
        clean_delta = clean_pairs[f"{treatment}_only"] - clean_pairs[f"{control}_only"]
        result.update(
            clean_pair_delta=clean_delta,
            positive_signal=result["positive_signal"] and clean_delta > 0,
            repositories={
                repo: {arm: {key: sum(row[arm][key] for task, row in by_task.items()
                                     if task.startswith(repo + "_")) for key in counts()}
                       for arm in arms}
                for repo in sorted({task.split("_", 1)[0] for task in task_ids})
            },
        )
    return result


def audit_thinking_policy(compiled, fixer_budget):
    expected = {"fixer": fixer_budget, "verifier": THINKING_CONTROL_BUDGET}
    observed = {}
    for child in compiled.sub_agents:
        body = child.model._additional_args.get("extra_body") or {}
        enabled = (body.get("chat_template_kwargs") or {}).get("enable_thinking")
        budget = body.get("thinking_token_budget")
        if (enabled is not (expected[child.name] > 0)
                or budget != (expected[child.name] or None)
                or child.generate_content_config.max_output_tokens != 5000):
            raise RuntimeError(f"Incorrect compiled thinking settings for {child.name}: {enabled}, {budget}")
        observed[child.name] = {"enable_thinking": enabled, "thinking_token_budget": budget,
                                "max_output_tokens": child.generate_content_config.max_output_tokens}
    return observed


def run_with_failure_stop(task_ids, evaluate, persist, *, limit=10, workers=4, deadline=None):
    cancellation = threading.Event()
    lock = threading.Lock()
    records = []
    stop = {"limit": limit, "consecutive_failures": 0, "triggered": False,
            "trigger_task": None, "completion_order": []}

    def lane(gpu):
        for task in task_ids[gpu::workers]:
            if cancellation.is_set() or (deadline is not None and time.monotonic() >= deadline):
                break
            record = evaluate(gpu, task, cancellation)
            with lock:
                record["after_stop"] = stop["triggered"]
                if not stop["triggered"] and not record["status"].startswith("not_started_"):
                    stop["completion_order"].append(task)
                    stop["consecutive_failures"] = (
                        0 if verified_solve(record) else stop["consecutive_failures"] + 1)
                    if stop["consecutive_failures"] >= limit:
                        stop.update(triggered=True, trigger_task=task)
                        cancellation.set()
                        print("FAILURE_STREAK_STOP", json.dumps(stop), flush=True)
                records.append(record)
                persist(records, stop)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(lane, gpu) for gpu in range(workers)]
        try:
            for future in concurrent.futures.as_completed(futures):
                future.result()
        finally:
            cancellation.set()
    return records, stop


def run(work, agent, tasks, task_ids, snapshots, model_path, prompt, adapters,
        *, control_agent=None, rounds=1, overflow_recovery=False, context_probe_token_id=None,
        recovery_context=65536, repeat_benchmark=False, evidence_seed=False,
        repair_decisions=False, repair_first_round=1, thinking_budget=None, slot_compare=False):
    thinking_policies = thinking_plan(rounds, thinking_budget) if thinking_budget is not None else {}
    thinking_compare = bool(thinking_policies)
    if slot_compare and (
            thinking_compare or repeat_benchmark or evidence_seed or overflow_recovery or repair_decisions
            or control_agent is not None or not 1 <= rounds <= SLOT_MAX_ROUNDS
            or len(task_ids) != 39 or len(set(task_ids)) != 39):
        raise ValueError(f"Slots comparison requires one policy, 39 unique tasks and 1-{SLOT_MAX_ROUNDS} rounds")
    if overflow_recovery and (control_agent is not None or type(context_probe_token_id) is not int):
        raise ValueError("Overflow recovery requires one adapter arm and a native probe token ID")
    if recovery_context not in (65536, 131072):
        raise ValueError("Recovery context must be65536 or131072 tokens")
    if repeat_benchmark and (
            overflow_recovery or control_agent is None or rounds != REPEAT_ROUNDS
            or len(task_ids) != 39 or len(set(task_ids)) != 39):
        raise ValueError("Repeat benchmark requires both arms, 39 tasks, and 16 rounds at 32K")
    if evidence_seed and (repeat_benchmark or overflow_recovery or control_agent is not None
                          or rounds not in (1, EVIDENCE_REPEAT_ROUNDS)
                          or len(task_ids) != 39 or len(set(task_ids)) != 39):
        raise ValueError("Evidence seed requires 39 unique tasks and one or nine adapter-only passes")
    if repair_decisions and (
            repeat_benchmark or evidence_seed or overflow_recovery or control_agent is not None
            or rounds != REPAIR_DECISIONS_ROUNDS or repair_first_round not in (1, 6)
            or len(task_ids) != 39 or len(set(task_ids)) != 39):
        raise ValueError("Repair-decisions mode requires 39 unique tasks and five adapter-only rounds")
    if not repair_decisions and repair_first_round != 1:
        raise ValueError("A repair round offset requires repair-decisions mode")
    if thinking_compare and (
            repeat_benchmark or evidence_seed or overflow_recovery or repair_decisions
            or control_agent is None
            or len(task_ids) != THINKING_TASKS or len(set(task_ids)) != THINKING_TASKS):
        raise ValueError("Paired thinking mode requires two policies on 20 unique tasks")
    seed_repeats = evidence_seed and rounds == EVIDENCE_REPEAT_ROUNDS
    repair_decision_repeats = repair_decisions
    adapter_name = (REPAIR_DECISIONS_ADAPTER if repair_decisions or thinking_compare or slot_compare else
                    EVIDENCE_ADAPTER if evidence_seed else ADAPTER)
    context_length = recovery_context if overflow_recovery else 32768
    from adk_submission import VllmConfig, VllmServer, compile_submission
    from swegemma.cli import _build_cli_model_registry

    servers = []
    records = []
    lock = threading.Lock()
    phase = "startup"
    try:
        for gpu in range(4):
            config = VllmConfig(
                model=str(model_path), port=8000 + gpu, host="127.0.0.1",
                tool_call_parser="gemma4", reasoning_parser="gemma4",
                enable_auto_tool_choice=True, enable_lora=True,
                max_loras=1, max_lora_rank=8, tensor_parallel_size=1,
                max_model_len=context_length, gpu_memory_utilization=0.85,
                dtype="bfloat16", startup_timeout=900,
                extra_args=["--served-model-name", MODEL, "2"],
            )
            server = VllmServer(config, adapter_manifest=adapters)
            original_env = server.build_env
            server.build_env = lambda original=original_env, gpu=gpu: dict(
                original(), CUDA_VISIBLE_DEVICES=str(gpu))
            servers.append(server)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda server: server.start(), servers))

        phase = "serving_gates"

        def smoke(gpu):
            server = servers[gpu]
            models = {item["id"]: item for item in request(server.base_url, "/models")["data"]}
            ids = list(models)
            if MODEL not in ids or adapter_name not in ids:
                raise RuntimeError(f"gpu{gpu}: missing served model or adapter: {ids}")
            if (repeat_benchmark or evidence_seed or repair_decisions or thinking_compare or slot_compare) \
                    and models[MODEL].get("max_model_len") != context_length:
                raise RuntimeError(f"gpu{gpu}: incorrect advertised context for the 32K benchmark")
            responses = []
            for name in (MODEL, MODEL, adapter_name, adapter_name):
                responses.append(request(server.base_url, "/completions", {
                    "model": name, "prompt": prompt, "temperature": 0,
                    "seed": 0, "max_tokens": 8, "logprobs": 5,
                }))
            save(work / f"logprob_gpu{gpu}.json", responses)
            effect = logprob_effect(responses, adapter_name=adapter_name)
            parsed = request(server.base_url, "/chat/completions", {
                "model": adapter_name, "temperature": 0, "max_tokens": 512,
                "chat_template_kwargs": {"enable_thinking": False},
                "messages": [{"role": "user", "content":
                              "Call read_file exactly once with path example.py. "
                              "Use the tool now; do not explain or solve anything."}],
                "tools": [{"type": "function", "function": {
                    "name": "read_file", "description": "Read a source file.",
                    "parameters": {"type": "object", "properties": {
                        "path": {"type": "string"}}, "required": ["path"]},
                }}], "tool_choice": "auto",
            })
            save(work / f"parser_gpu{gpu}.json", parsed)
            calls = parsed["choices"][0]["message"].get("tool_calls") or []
            if (parsed["model"] != adapter_name or len(calls) != 1
                    or calls[0]["function"]["name"] != "read_file"
                    or json.loads(calls[0]["function"]["arguments"]) != {"path": "example.py"}):
                raise RuntimeError(f"gpu{gpu}: native tool parser gate failed")
            context_probe = None
            if overflow_recovery:
                context_probe = probe_context_window(
                    server.base_url, context_probe_token_id, context_length,
                    work / f"context_gpu{gpu}.json")
            return {"gpu": gpu, "served_ids": ids, "effect": effect, "native_parser": True,
                    "context_tokens_verified": context_length if context_probe is not None else None}

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            gates = list(pool.map(smoke, range(4)))
        save(work / "serving_gates.json", {"passed": True, "lanes": gates})
        # Use the same CLI model registry/resolver as the existing isolated eval workflow.
        def stub(name):
            def function():
                raise RuntimeError("Structural compiler placeholder must not execute")
            function.__name__ = name
            return function
        tool_names = ("run_command", "read_file", "edit_file", "write_file", "get_status",
                      "submit_patch", "get_code_neighbors", "search_similar_code", "get_code_subgraph")
        routes = {}
        thinking_settings = {}
        policies = {"adapter": agent}
        if control_agent is not None:
            policies["base"] = control_agent
        if thinking_compare:
            policies = dict(zip(thinking_policies, (control_agent, agent)))
        if slot_compare:
            policies = {arm: agent for arm in SLOT_ARMS}  # identical policy; only slots per lane differ
        for arm, path in policies.items():
            registry = _build_cli_model_registry(path)
            compiled = compile_submission(path, {name: stub(name) for name in tool_names},
                                          registry, adapter_manifest=adapters)
            actual = {child.name: child.model.model for child in compiled.sub_agents}
            expected_fixer = adapter_name if thinking_compare or slot_compare or arm == "adapter" else MODEL
            if actual != {"fixer": f"openai/{expected_fixer}", "verifier": f"openai/{MODEL}"}:
                raise RuntimeError(f"Incorrect compiled {arm} roles: {actual}")
            routes[arm] = actual
            if thinking_compare:
                thinking_settings[arm] = audit_thinking_policy(compiled, thinking_policies[arm])
        save(work / "compiled_routes.json", routes)
        if thinking_compare:
            save(work / "compiled_thinking.json", thinking_settings)
            print("COMPILED_THINKING_OK", thinking_settings, flush=True)
        print("ALL_FOUR_SERVING_GATES_PASSED", routes, flush=True)

        phase = ("slots_per_lane_8_vs_12_32k" if slot_compare else
                 "paired_fixer_thinking_32k" if thinking_compare else
                 "repair_decisions_seed39_32k" if repair_decisions else
                 "evidence_seed39_repeats_32k" if seed_repeats else
                 "evidence_seed39_32k" if evidence_seed else "repeat39_32k" if repeat_benchmark else
                 f"overflow_recovery_{context_length}" if overflow_recovery else
                 "positive_controls" if control_agent is not None else "full129")
        seconds = (SLOT_EVAL_SECONDS if slot_compare else
                   THINKING_EVAL_SECONDS if thinking_compare else
                   REPAIR_DECISIONS_SECONDS if repair_decisions else
                   EVIDENCE_REPEAT_SECONDS if seed_repeats else
                   EVIDENCE_EVAL_SECONDS if evidence_seed else REPEAT_SECONDS if repeat_benchmark else
                   3600 if overflow_recovery else
                   2400 if control_agent is not None else EVALUATION_SECONDS)
        deadline = time.monotonic() + seconds

        def one(gpu, task, arm="adapter", rnd=1, cancellation=None):
            output = work / "lora_results" / task
            if control_agent is not None or seed_repeats or repair_decision_repeats or slot_compare:
                output = work / "lora_results" / arm / f"round_{rnd}" / task
            command = [
                sys.executable, "-m", "swegemma", "eval", "--tasks", str(tasks),
                "--snapshots-dir", str(snapshots), "--results-dir", str(output),
                "--submission-dir", str(policies[arm]), "--sandbox", "subprocess",
                "--concurrency", "1", "--display", "quiet", "--task-id", task,
                "--max-tool-calls", "80", "--max-time-minutes", "30",
                "--max-turns", "200", "--timeout-seconds", "300",
            ]
            if thinking_compare or slot_compare:
                print("TASK_START", gpu, arm, rnd, task, flush=True)
            wall_start = time.time()
            record = run_task(command, output, dict(
                os.environ, OPENAI_BASE_URL=servers[gpu].base_url, OPENAI_API_KEY="EMPTY"),
                task, TASK_SECONDS, deadline, cancel_event=cancellation)
            if slot_compare:  # lane-hours for the throughput rule; other modes keep their record schema
                record.update(wall_start=wall_start, wall_end=time.time())
            record.pop("recall_audit", None)
            record.pop("wiring_audit", None)
            record["gpu"] = gpu
            record.update(arm=arm, round=rnd)
            test_output = output / "test_outputs" / f"{task}.log"
            row = record.get("result") or {}
            has_output = test_output.is_file() and test_output.stat().st_size > 0
            if thinking_compare:
                record["collection_error"] = has_output and "ERROR collecting" in test_output.read_text(
                    encoding="utf-8", errors="replace")
            record["real_grade"] = bool(
                record["graded"] and row.get("test_exit_code") in (0, 1)
                and has_output and not record.get("collection_error"))
            trace = output / "traces" / f"trace_{task}.json"
            record["routing"] = audit_routing(
                json.loads(trace.read_text()),
                fixer_model=adapter_name if thinking_compare or slot_compare or arm == "adapter" else MODEL,
                adapter_name=adapter_name,
            ) if trace.is_file() and not record.get("trace_error") else (
                {"fixer_adapter_observed": False, "violations": [],
                 "error": record.get("trace_error") or "Missing trace"})
            if not overflow_recovery:
                with lock:
                    records.append(record)
                    save(work / "lora_progress.json", {"tasks": records})
            print("TASK_END", arm, rnd, task, record["status"], "graded", record["real_grade"],
                  "resolved", row.get("resolved"), "error", row.get("error"), flush=True)
            return record

        def lane(gpu):
            slots = SLOT_ARMS[slot_arm(gpu)] if slot_compare else CONCURRENCY
            with concurrent.futures.ThreadPoolExecutor(max_workers=slots) as pool:
                if slot_compare:
                    print("LANE_SLOTS", gpu, slot_arm(gpu), slots, flush=True)
                    list(pool.map(lambda job: one(gpu, *job), slot_jobs(task_ids, rounds, gpu)))
                elif repair_decision_repeats:
                    list(pool.map(lambda job: one(gpu, *job),
                                  repair_decision_jobs(task_ids, gpu, repair_first_round)))
                elif seed_repeats:
                    list(pool.map(lambda job: one(gpu, *job), seed_repeat_jobs(task_ids, gpu)))
                elif control_agent is None:
                    list(pool.map(lambda task: one(gpu, task), task_ids[gpu::4]))
                else:
                    jobs = [(task, arm, rnd) for index, task in enumerate(task_ids)
                            for rnd in range(1, rounds + 1) for arm in ("base", "adapter")
                            if (index + rnd - 1 + (2 if arm == "base" else 0)) % 4 == gpu]
                    list(pool.map(lambda job: one(gpu, *job), jobs))

        stop = None
        if overflow_recovery:
            def persist(current, state):
                save(work / "lora_progress.json", {"tasks": current, "failure_stop": state})
            records, stop = run_with_failure_stop(
                task_ids, lambda gpu, task, event: one(gpu, task, cancellation=event), persist,
                deadline=deadline)
        elif repeat_benchmark:
            run_paired_repeats(task_ids, rounds, one, deadline)
        elif thinking_compare:
            run_paired_repeats(task_ids, rounds, one, deadline, arms=tuple(thinking_policies))
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lane, range(4)))
        summary = (summarize_slots(task_ids, records, rounds) if slot_compare else
                   summarize_repair_decisions(task_ids, records, repair_first_round) if repair_decisions else
                   summarize_seed_repeats(task_ids, records) if seed_repeats else
                   summarize_evidence_seed(task_ids, records) if evidence_seed else
                   summarize_repeats(task_ids, records, rounds, thinking_budget=thinking_budget)
                   if thinking_compare else
                   summarize_repeats(task_ids, records, rounds) if repeat_benchmark else
                   summarize_controls(task_ids, records, rounds) if control_agent is not None
                   else summarize(task_ids, records))
        if overflow_recovery:
            if stop is None:
                raise RuntimeError("Overflow recovery finished without its failure-stop receipt")
            summary.update(
                experiment=f"p5 overflow-only {context_length}-token recovery; "
                           "single arm, not a paired context effect",
                max_model_len=context_length, failure_stop=stop,
                verified_solves=sum(verified_solve(record) for record in records),
                not_started_task_ids=sorted(
                    (set(task_ids) - {record["id"] for record in records})
                    | {record["id"] for record in records
                       if record["status"].startswith("not_started_")}),
                cancelled_task_ids=[record["id"] for record in records
                                    if record["status"] == "cancelled_failure_streak"],
            )
            summary["complete"] = summary["complete"] and not stop["triggered"]
        save(work / "lora_summary.json", summary)
        # Compatibility name for the existing version-pinned private experiment collector.
        save(work / "memory_summary.json", summary)
        console = (summary if slot_compare else
                   {k: v for k, v in summary.items() if k not in ("tasks", "rounds")}
                   if seed_repeats or repair_decisions else
                   {k: v for k, v in summary.items() if k != "tasks"}
                   if repeat_benchmark or thinking_compare else summary)
        print("EVALUATION_END", phase, json.dumps(console), flush=True)
    finally:
        if sys.exc_info()[0] is not None:
            save(work / "failure.json", {"phase": phase, "traceback": traceback.format_exc()})
        for gpu, server in enumerate(servers):
            if Path(server.log_path).is_file():
                shutil.copyfile(server.log_path, work / f"vllm_gpu{gpu}.log")
            server.stop()
