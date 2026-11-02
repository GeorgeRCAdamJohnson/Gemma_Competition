"""Slow acceptance-fact checks against the built KB (design §19.2, 'slow').

These read the generated runs.jsonl / tasks_gold.json. Run `build_kb.py build`
first. Facts are asserted content-anchored and with '>=' where the design does.
"""
import json
import pathlib

import pytest

KB = pathlib.Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.slow


def _rows():
    return {json.loads(l)["row_id"]: json.loads(l)
            for l in (KB / "runs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}


def _gold():
    return json.loads((KB / "tasks_gold.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rows():
    if not (KB / "runs.jsonl").exists():
        pytest.skip("runs.jsonl not built")
    return _rows()


def test_fact1_v6b_rich_4079(rows):
    r = rows["submit_v6b/out_v6b::rich_4079"]
    assert r["outcome"]["resolved"] is False
    assert r["outcome"]["tool_calls"] == 28
    assert r["outcome"]["patch_chars"] == 0
    t = r["trace"]
    assert t["calls_total"] == 30
    assert t["refused"][0]["step_id"] == 31
    assert t["refused"][0]["kind"] == "REFUSED_CALLS"
    assert t["count_model"]["residual"] == 0


def test_fact7_tasks_gold_count():
    g = _gold()
    assert len(g["tasks"]) == 129
    rich = [k for k, v in g["tasks"].items() if v["repo"] == "Textualize/rich"]
    ast = sum(1 for k in rich if g["tasks"][k]["functions_source"] == "ast@base_commit")
    # >= 46 of 48 (the 2 misses are pure new-file additions)
    assert ast >= 46


def test_fact8_v19lora_rich_4070(rows):
    r = rows.get("Outputs/v19_lora::rich_4070")
    if r is None or r["trace"] is None:
        pytest.skip("row not present at this snapshot")
    t = r["trace"]
    assert t["calls_total"] == 24
    assert t["tool_call_malformation"]["arg_rejected"] == 18
    assert t["count_model"]["residual"] == 0


def test_count_model_bar(rows):
    traced = [r for r in rows.values() if r["trace"]]
    withh = [r for r in traced if r["trace"]["count_model"]["harness"] is not None]
    r0 = sum(1 for r in withh if r["trace"]["count_model"]["residual"] == 0)
    assert r0 / max(1, len(withh)) >= 0.95


def test_fact14_v6z_failed(rows):
    # submit_v6z/out_v6z is a run-dir-failed (0 rows) -> no runs rows for it
    assert not any(k.startswith("submit_v6z/out_v6z::") for k in rows)


# --- iteration 2: static reconstruction, near-miss nm-3, replay ---

def test_edit_attempts_reconstructed(rows):
    # v6b rich_4079 step 31 is a python-replace edit attempt (REFUSED at the wall)
    r = rows["submit_v6b/out_v6b::rich_4079"]
    atts = r["trace"]["edit_attempts"]
    step31 = [a for a in atts if a["step_id"] == 31]
    assert step31, "step 31 edit attempt missing"
    a = step31[0]
    assert a["fn"] == "run_command"
    assert a["shape"] in ("python-replace", "python-heredoc")
    assert a["observed"] == "REFUSED_CALLS"
    assert "rich/markdown.py" in (a["files"] or [])


def test_nearmiss_v6b_4079_stages(rows):
    nm = _nm_rows()["submit_v6b/out_v6b::rich_4079"]
    assert nm["has_trace"] is True
    assert str(nm["confidence"]).startswith("measured")
    st = nm["stages"]
    # read gold file (step 26), saw hunk (step 27), tried apply (step 31)
    assert st["READ_GOLD_FILE"]["reached"] and st["READ_GOLD_FILE"]["step_id"] == 26
    assert st["SAW_GOLD_HUNK"]["reached"]
    assert st["TRIED_APPLY"]["reached"] and st["TRIED_APPLY"]["step_id"] == 31
    assert nm["stopped_by"] == "REFUSED_CALLS"


def test_crosstask_fp_bar_met():
    bm = json.loads((KB / "build_meta.json").read_text(encoding="utf-8"))
    fp = bm.get("near_miss_fp")
    assert fp is not None
    # pre-registered bar: <= 1% of (trace, other-task) pairs
    assert fp["wrote_gold_change_fp_rate"] <= 0.01, fp


def test_replay_gold_first_valid_when_present():
    # if a replay has run, the min-set rich gold controls must be VALID or recorded
    gold_dir = KB / "replays" / "gold"
    if not gold_dir.exists() or not any(gold_dir.glob("*.json")):
        pytest.skip("no replay has run yet")
    for task in ("rich_4079", "rich_4076", "rich_4070"):
        p = gold_dir / f"{task}.json"
        if not p.exists():
            continue
        g = json.loads(p.read_text(encoding="utf-8"))
        # gold must be a recorded gold-first verdict; VALID means gold passed locally
        assert g["gold_first"] in ("VALID-HARNESS-LIKE", "VALID-GOLD-RELATIVE",
                                   "INVALID", "INFRA")
        if g["gold_first"].startswith("VALID"):
            assert g["module_file_check"]["under_worktree"] is True


# --- REV5 FEAT-001: new stacks, stack/track, dev-harness AST pass ---

def test_rev5_kaggle_pkg_v7_rows(rows):
    v7 = [r for r in rows.values() if r["run_id"] == "kaggle_pkg/out_v7"]
    assert len(v7) == 129
    srcs = {r["outcome_source"] for r in v7}
    # the 9 surviving harness labels come from task_results.jsonl; the chunk-
    # overwritten rest from the user's recovered proxy (labelled, lower priority)
    assert sum(1 for r in v7 if r["outcome_source"] == "task_results") >= 9
    assert srcs <= {"task_results", "recovered-proxy"}
    assert all(r["outcome"] is not None for r in v7)
    assert all(r["run_kind"] == "kaggle-kernel" and r["stack"]["platform"] == "kaggle" for r in v7)


def test_rev5_every_row_has_stack_and_track(rows):
    for r in rows.values():
        assert r["stack"]["platform"] in ("kaggle", "local-rig", "local-sweep", "colab", "unknown")
        assert r["track"] in ("main", "small-model", "dev-proxy")


def test_rev5_parity_rig_row(rows):
    rig = [r for r in rows.values() if r["run_id"].startswith("local_eval/parity_rig/")]
    assert rig
    assert all(r["stack"]["platform"] == "local-rig" and r["run_kind"] == "local-rig"
               and r["stack"]["model_served_verified"] is False for r in rig)


def test_rev5_sweep_rows_patch_trusted(rows):
    sw = [r for r in rows.values() if r["run_kind"] == "local-sweep"]
    assert sw
    assert all(isinstance(r["patch_trusted"], bool) and r["trace"] is None for r in sw)
    assert any(r["patch_trusted"] for r in sw) and any(not r["patch_trusted"] for r in sw)


def test_rev5_v6w_dev_harness_mismatch(rows):
    v6w = [r for r in rows.values() if r["run_id"] == "submit_v6w/out_v6w"]
    assert v6w
    for r in v6w:
        assert r["dev_harness"]["compaction_interval"] == 15
        assert r["dev_harness"]["matches_scorer"] is False


def test_rev5_fp_sampling_recorded():
    bm = json.loads((KB / "build_meta.json").read_text(encoding="utf-8"))
    assert bm["near_miss_fp"]["sampling"] == "hash-cap-40"
    assert bm["near_miss_fp"]["wrote_gold_change_fp_rate"] <= 0.01


def _nm_rows():
    return {json.loads(l)["row_id"]: json.loads(l)
            for l in (KB / "near_miss.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()}


def test_rev5_legacy_pull_mismatch(rows):
    """D5-10: the manual v6w_temp1_probe pull (temperature 0.2) must NOT explain
    ref 57201051 (temperature 1.0 / top_k 64)."""
    legacy = [r for r in rows.values() if r["run_id"] == "kb/pulled/v6w_temp1_probe"]
    assert legacy
    for r in legacy:
        assert r["run_kind"] == "kaggle-pulled-legacy"
        a = r["attribution"]
        per = {p["ref"]: p for p in a["per_ref"]}
        assert per["57201051"]["flag"] == "ATTRIBUTION-MISMATCH"
        assert "temperature: pulled 0.2 vs submission 1" in per["57201051"]["detail"]
        assert "57201051" not in a["explains_refs"]
    summ = (KB / "KB_SUMMARY.md").read_text(encoding="utf-8")
    assert "ATTRIBUTION-MISMATCH: pulled output does not explain ref 57201051" in summ
