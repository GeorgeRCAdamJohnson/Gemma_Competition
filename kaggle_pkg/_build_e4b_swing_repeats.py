"""Freeze the swing-task repeats from the Seed39 repair-decisions inputs (the policy of competition submission 58547656).

One policy: the frozen G_startup_lora repair-decisions bundle (adapter on the fixer, base verifier, 32K, task caps
unchanged). The 17 swing tasks of Outputs/SWING_DOSSIER.md each run --rounds times, 12 slots on each of four L4 lanes.
Descriptive measurement (pre-registered in GEMMA_EXPERIMENT_LOG.md, 2026-11-22 "swing-task repeats"). No leaderboard
submission; the results are a held-out evaluation set and must not be used as training data.

usage: python -m kaggle_pkg._build_e4b_swing_repeats --rounds 100
"""
import argparse
import ast
import base64
import gzip
import io
import json
import tarfile

from kaggle_pkg._build_e4b_slots_check import PARENT_ARM, RUN_PATH, SOURCE, replace_once
from kaggle_pkg._build_tool_lora_kaggle import ROOT, cell, digest
from kaggle_pkg.run_experiment import preflight
from kaggle_pkg.tool_lora_runner import (
    SWING_EVAL_SECONDS, SWING_MAX_ROUNDS, SWING_NOTEBOOK_SECONDS, SWING_SLOTS, SWING_TASKS,
)


def build(*, rounds, output_root=ROOT / "Outputs"):
    title = f"E4B Swing Task Repeats R{rounds}"
    notebook_name = title.lower().replace(" ", "-")
    slug = f"comfyops/{notebook_name}"
    destination = output_root / f"{notebook_name}-package"
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite {destination}")
    metadata, parent = preflight(SOURCE)
    task_ids = list(parent["task_ids"])
    if len(task_ids) != 39 or len(set(task_ids)) != 39 or not set(SWING_TASKS) <= set(task_ids):
        raise ValueError("Frozen Seed39 cohort changed or lacks a swing task")
    swing = [task for task in task_ids if task in SWING_TASKS]

    notebook = json.loads((SOURCE / metadata["code_file"]).read_bytes())
    stage = "".join(notebook["cells"][3]["source"])
    encoded = next(
        ast.literal_eval(node.value.args[0])
        for node in ast.parse(stage).body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "bundle" for target in node.targets)
    )
    files = {}
    with tarfile.open(fileobj=io.BytesIO(base64.b64decode(encoded, validate=True))) as original:
        for member in original.getmembers():
            files[member.name] = original.extractfile(member).read()
    if RUN_PATH not in files:
        raise ValueError("Frozen bundle has no runner to replace")
    files[RUN_PATH] = (ROOT / "kaggle_pkg" / "tool_lora_runner.py").read_bytes()
    prefix = f"arms/{PARENT_ARM}/"
    policy = {name.removeprefix(prefix): raw for name, raw in files.items() if name.startswith(prefix)}
    policy_hashes = {name: digest(raw) for name, raw in sorted(policy.items())}
    if policy_hashes != parent["treatment_file_hashes"]:
        raise ValueError("Policy differs from the frozen repair-decisions policy")
    arm_hash = digest(json.dumps(policy_hashes, sort_keys=True).encode())
    if arm_hash != parent["arm_hashes"][PARENT_ARM]:
        raise ValueError("Arm hash differs from the frozen registration")

    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as archive:
        for name, contents in sorted(files.items()):
            member = tarfile.TarInfo(name)
            member.size = len(contents)
            archive.addfile(member, io.BytesIO(contents))
    bundle = gzip.compress(stream.getvalue(), mtime=0)
    bundle_hash = digest(bundle)
    if stage.count(parent["bundle_sha256"]) != 2:
        raise ValueError("Unexpected frozen bundle hash layout")
    stage = replace_once(stage, encoded, base64.b64encode(bundle).decode()).replace(
        parent["bundle_sha256"], bundle_hash)
    stage = replace_once(stage, "G_startup; fixer adapter only; verifier unchanged",
                         f"G_startup; one policy; 17 swing tasks x {rounds}; {SWING_SLOTS} slots per lane")
    runtime = "".join(notebook["cells"][2]["source"])
    notebook["cells"][2] = cell(
        runtime + '\nif (adk_submission.__version__, swegemma.__version__) != ("0.2.13", "0.2.11"):\n'
        '    raise RuntimeError("Registered ADK submission/evaluator versions were not mounted")\n', 2)
    notebook["cells"][3] = cell(stage, 3)
    notebook["cells"][4] = cell(
        "from kaggle_pkg.tool_lora_runner import run\n"
        "run(WORK, AGENT, TASKS, TASK_IDS, SNAPS, MODEL_PATH, SMOKE_PROMPT, ADAPTERS,\n"
        f"    rounds={rounds}, swing_repeat=True)\n", 4)
    notebook["cells"][0]["source"] = [
        "# E4B swing-task repeats\n",
        f"17 swing tasks from the Seed39 cohort, {rounds} independent attempts each, one frozen repair-decisions "
        f"policy, {SWING_SLOTS} slots on each of four L4 lanes. No leaderboard submission.\n",
        "Frozen notebook: rebuild with --rounds instead of editing cells.\n",
    ]
    raw_notebook = json.dumps(notebook, indent=1).encode()
    metadata.update(id=slug, title=title, code_file=f"{notebook_name}.ipynb")
    executions = len(swing) * rounds
    registration = dict(
        parent, slug=slug, notebook_sha256=digest(raw_notebook), bundle_sha256=bundle_hash,
        task_ids=task_ids, swing_task_ids=swing, parent_slug=parent["slug"], parent_version=2,
        parent_notebook_sha256=parent["notebook_sha256"], rounds=rounds,
        round_labels=list(range(1, rounds + 1)), slots_per_lane=SWING_SLOTS,
        concurrency_per_gpu={f"gpu{g}": SWING_SLOTS for g in range(4)},
        notebook_seconds=SWING_NOTEBOOK_SECONDS, eval_seconds=SWING_EVAL_SECONDS,
        baseline_file_hashes=policy_hashes, treatment_file_hashes=policy_hashes,
        arm_hashes={PARENT_ARM: arm_hash},
        comparison="Descriptive single-policy measurement: each of the 17 swing tasks (Outputs/SWING_DOSSIER.md) runs "
                   f"{rounds} independent attempts under the repair-decisions v1 policy of submission 58547656 "
                   "(fixer adapter, base verifier, 32K, task caps unchanged). Measures per-task solve rate under one "
                   "configuration and records full traces, patches and test outputs for failure classification.",
        criteria={
            **parent["criteria"],
            "expected_tasks": len(swing), "expected_executions": executions,
            "round_labels": list(range(1, rounds + 1)),
            "complete_rule": f"Usable if >= 90% of {executions} executions start and >= 95% of started attempts are "
                             "real-graded; otherwise report as partial and use complete rounds only.",
            "analysis": "Per task: verified solve rate with Wilson 95% interval; a task stays a swing task if its "
                        "interval overlaps 10-90%. Compare each rate to the pooled DB rate (multi-config) and report "
                        "tasks whose interval excludes it. Re-run the failure taxonomy on these attempts and report "
                        "how many right-file failures gain a classification from the new test outputs.",
            "report": "Per-task attempts, solves, interval, overflows, grading coverage; lane-hours and throughput. "
                      "Abort on serving gates; no automatic retry or leaderboard claim.",
        },
        resources=f"Private internet-off, four L4s, 32K context, {SWING_SLOTS} slots per lane; "
                  f"{SWING_NOTEBOOK_SECONDS}s notebook cap ({4 * SWING_NOTEBOOK_SECONDS / 3600:g} device-hours "
                  f"maximum), {SWING_EVAL_SECONDS}s evaluation, 2,000s task wall; no Drive, training or submission.",
    )
    destination.mkdir()
    (destination / metadata["code_file"]).write_bytes(raw_notebook)
    for name, value in (("kernel-metadata.json", metadata), ("registration.json", registration)):
        (destination / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    preflight(destination, for_launch=True)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, choices=range(1, SWING_MAX_ROUNDS + 1), required=True)
    print(build(rounds=parser.parse_args().rounds))
