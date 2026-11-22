"""Freeze the slots-per-lane validation (GPU rule 3, .kiro/steering/gpu-usage.md) from the Seed39 repair-decisions inputs.

Identical policy in both arms (the frozen G_startup_lora repair-decisions bundle: adapter on the fixer, base
verifier, 32K, task caps unchanged). Lanes 0-1 run 8 concurrent attempts, lanes 2-3 run 12. Every task/round runs
once per arm, so outcomes are paired by task and round. Pass rules pre-registered in GEMMA_EXPERIMENT_LOG.md
(2026-11-21 "GPU-usage guidance"). No leaderboard submission.

usage: python -m kaggle_pkg._build_e4b_slots_check --rounds 4
"""
import argparse
import ast
import base64
import gzip
import io
import json
import tarfile

from kaggle_pkg._build_tool_lora_kaggle import ROOT, cell, digest
from kaggle_pkg.run_experiment import preflight
from kaggle_pkg.tool_lora_runner import (
    SLOT_ARMS, SLOT_EVAL_SECONDS, SLOT_LANES, SLOT_MAX_ROUNDS, SLOT_NOTEBOOK_SECONDS,
)

SOURCE = ROOT / "kaggle_pkg" / "push_e4b_repair_decisions_seed39_r1_r5_v2"
PARENT_ARM = "G_startup_lora"
RUN_PATH = "support/kaggle_pkg/tool_lora_runner.py"


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f"Expected one occurrence of {old[:120]!r} in frozen input")
    return text.replace(old, new, 1)


def build(*, rounds, output_root=ROOT / "Outputs"):
    title = f"E4B Slots Per Lane 8v12 R{rounds}"
    notebook_name = title.lower().replace(" ", "-")
    slug = f"comfyops/{notebook_name}"
    destination = output_root / f"{notebook_name}-package"
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite {destination}")
    metadata, parent = preflight(SOURCE)
    task_ids = list(parent["task_ids"])
    if len(task_ids) != 39 or len(set(task_ids)) != 39:
        raise ValueError("Frozen Seed39 cohort changed")

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
                         "G_startup; identical policy; slots per lane 8 (gpu0-1) vs 12 (gpu2-3)")
    runtime = "".join(notebook["cells"][2]["source"])
    notebook["cells"][2] = cell(
        runtime + '\nif (adk_submission.__version__, swegemma.__version__) != ("0.2.13", "0.2.11"):\n'
        '    raise RuntimeError("Registered ADK submission/evaluator versions were not mounted")\n', 2)
    notebook["cells"][3] = cell(stage, 3)
    notebook["cells"][4] = cell(
        "from kaggle_pkg.tool_lora_runner import run\n"
        "run(WORK, AGENT, TASKS, TASK_IDS, SNAPS, MODEL_PATH, SMOKE_PROMPT, ADAPTERS,\n"
        f"    rounds={rounds}, slot_compare=True)\n", 4)
    notebook["cells"][0]["source"] = [
        "# E4B slots per lane: 8 vs 12\n",
        f"Seed39 (39 tasks), {rounds} rounds per arm, identical repair-decisions policy in both arms.\n",
        "GPU 0-1 run 8 concurrent attempts, GPU 2-3 run 12; only the slot count differs. No leaderboard submission.\n",
        "Frozen notebook: rebuild with --rounds instead of editing cells.\n",
    ]
    raw_notebook = json.dumps(notebook, indent=1).encode()
    metadata.update(id=slug, title=title, code_file=f"{notebook_name}.ipynb")
    pairs = 39 * rounds
    registration = dict(
        parent, slug=slug, notebook_sha256=digest(raw_notebook), bundle_sha256=bundle_hash,
        task_ids=task_ids, parent_slug=parent["slug"], parent_version=2,
        parent_notebook_sha256=parent["notebook_sha256"], rounds=rounds,
        round_labels=list(range(1, rounds + 1)), slots_per_lane=SLOT_ARMS,
        lanes={arm: list(lanes) for arm, lanes in SLOT_LANES.items()},
        concurrency_per_gpu={f"gpu{g}": SLOT_ARMS[arm] for arm, lanes in SLOT_LANES.items() for g in lanes},
        notebook_seconds=SLOT_NOTEBOOK_SECONDS, eval_seconds=SLOT_EVAL_SECONDS,
        baseline_file_hashes=policy_hashes, treatment_file_hashes=policy_hashes,
        arm_hashes={PARENT_ARM: arm_hash},
        comparison="Contemporaneous paired test of slots per lane (8 on gpu0-1 vs 12 on gpu2-3) with an identical "
                   "policy: repair-decisions v1 adapter on the fixer, base verifier, 32K, task caps unchanged. Each "
                   "task/round runs once per arm. Tests GPU-usage rule 3 (projected x1.33 throughput at 12 slots).",
        criteria={
            **parent["criteria"],
            "expected_tasks": 39, "expected_pairs": pairs, "expected_executions": 2 * pairs,
            "round_labels": list(range(1, rounds + 1)),
            "pass_rule": "Adopt 12 slots only if ALL hold on complete data: (a) attempts per lane-hour slots12/slots8 "
                         ">= 1.2; (b) mean attempt duration ratio <= 1.25 and no slots12 attempt over 30 min; "
                         "(c) paired verified-solve rate (slots12 - slots8) >= -2.0 points; (d) no vLLM error type "
                         "other than context overflow. Any failure or incomplete data -> keep 8 slots.",
            "report": "Per-arm attempts, lane-hours, throughput, mean/max seconds, verified solves, overflows; paired "
                      "pairs and discordances. Abort on serving gates; no automatic retry or leaderboard claim.",
        },
        resources=f"Private internet-off, four L4s, 32K context, 8 slots (gpu0-1) and 12 slots (gpu2-3); "
                  f"{SLOT_NOTEBOOK_SECONDS}s notebook cap ({4 * SLOT_NOTEBOOK_SECONDS / 3600:g} device-hours "
                  f"maximum), {SLOT_EVAL_SECONDS}s evaluation, 2,000s task wall; no Drive, training or submission.",
    )
    destination.mkdir()
    (destination / metadata["code_file"]).write_bytes(raw_notebook)
    for name, value in (("kernel-metadata.json", metadata), ("registration.json", registration)):
        (destination / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    preflight(destination, for_launch=True)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, choices=range(1, SLOT_MAX_ROUNDS + 1), required=True)
    print(build(rounds=parser.parse_args().rounds))
