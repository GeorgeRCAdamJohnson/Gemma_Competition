"""Unit tests for kblib modules (design §19.1, 'not slow')."""
import pathlib

import pytest

from kblib import (io, lock, traces, configs, unidiff, verdict, leak, kernellog,
                   bashpy, reconstruct, harness_edit, gitio, nearmiss, replay)


# --- io / safe_write boundary ---

def test_safe_write_rejects_protected(tmp_path, monkeypatch):
    import os
    monkeypatch.setenv("GKB_GEMMA_ROOT", str(tmp_path / "Gemma"))
    (tmp_path / "Gemma" / "kb" / "curated").mkdir(parents=True)
    with pytest.raises(io.SafeWriteError):
        io.safe_write(tmp_path / "Gemma" / "kb" / "curated" / "x.json", b"{}")


def test_safe_write_allows_generated_and_skips_identical(tmp_path, monkeypatch):
    monkeypatch.setenv("GKB_GEMMA_ROOT", str(tmp_path / "Gemma"))
    (tmp_path / "Gemma" / "kb").mkdir(parents=True)
    target = tmp_path / "Gemma" / "kb" / "runs.jsonl"
    assert io.safe_write(target, b'{"a":1}\n') is True
    assert io.safe_write(target, b'{"a":1}\n') is False  # identical, skipped


def test_dumps_json_deterministic():
    a = io.dumps_json({"b": 1, "a": 2})
    b = io.dumps_json({"a": 2, "b": 1})
    assert a == b


# --- lock ---

def test_lock_exclusive(tmp_path):
    kb = tmp_path
    l1 = lock.BuildLock(kb)
    l1.acquire()
    l2 = lock.BuildLock(kb)
    with pytest.raises(TimeoutError):
        l2.acquire(wait_s=0.0)
    l1.release()
    l2.acquire(wait_s=0.0)
    l2.release()


def test_lock_no_os_kill_in_source():
    # No actual os.kill CALL anywhere in the module (docstring prose aside).
    import ast
    src = (pathlib.Path(lock.__file__)).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "kill":
            if isinstance(node.value, ast.Name) and node.value.id == "os":
                raise AssertionError("os.kill call present")


# --- traces obs classes ---

def _fake_trace(tmp_path, steps):
    import json
    p = tmp_path / "trace_x.json"
    p.write_text(json.dumps({"schema_version": "ATIF-v1.7", "steps": steps,
                             "final_metrics": {}}), encoding="utf-8")
    return p


def test_trace_refused_and_arg_rejected(tmp_path):
    steps = [
        {"step_id": 1, "source": "agent", "tool_calls": [{"function_name": "run_command",
         "arguments": {"command": "ls"}}],
         "observation": {"content": '{"status":"error","error_type":"BudgetExceeded",'
                                    '"error_message":"Tool call budget exhausted (28 calls)"}'}},
        {"step_id": 2, "source": "agent", "tool_calls": [{"function_name": "edit_file",
         "arguments": {"filepath": "a.py", "new_string": "x"}}],
         "observation": {"content": '{"error":"Invoking `edit_file()` failed as the following '
                                    'mandatory input parameters are not present:\\nold_string\\n'
                                    'You could retry ..."}'}},
    ]
    t = traces.parse_trace(_fake_trace(tmp_path, steps), harness_tool_calls=0)
    assert t["refused"][0]["kind"] == "REFUSED_CALLS"
    assert t["arg_rejected"][0]["missing_params"] == ["old_string"]
    assert t["count_model"]["residual"] == 0  # both excluded -> predicted 0


def test_trace_scored_state_basis(tmp_path):
    steps = [
        {"step_id": 1, "source": "agent", "tool_calls": [{"function_name": "submit_patch",
         "arguments": {}}], "observation": {"content": '{"status":"ok","patch_size":10}'}},
    ]
    t = traces.parse_trace(_fake_trace(tmp_path, steps), harness_tool_calls=0)
    assert t["scored_state_basis"] == "last-ok-submit"
    assert t["last_ok_submit_call"] == 1


# --- configs YAML subset ---

def test_yaml_subset_nested_and_scalars():
    text = ("model: gemma-4-31b-it-qat-w4a16-ct\n"
            "generate_content_config:\n"
            "  temperature: 0.2\n"
            "  thinking_config:\n"
            "    thinking_budget: 1024\n")
    obj = configs._load_yaml_subset(text, pathlib.Path("."))
    assert obj["model"] == "gemma-4-31b-it-qat-w4a16-ct"
    assert obj["generate_content_config"]["temperature"] == 0.2
    assert obj["generate_content_config"]["thinking_config"]["thinking_budget"] == 1024


# --- unidiff ---

def test_unidiff_rejects_unsafe_path():
    with pytest.raises(unidiff.UniDiffError):
        unidiff.parse("--- a/../etc/passwd\n+++ b/../etc/passwd\n@@ -1 +1 @@\n-x\n+y\n")


def test_unidiff_new_file():
    files = unidiff.parse("--- /dev/null\n+++ b/new.py\n@@ -0,0 +1,1 @@\n+hello\n")
    assert files[0]["new_path"] == "new.py"
    assert files[0]["hunks"][0]["added"] == ["hello"]


# --- verdict stricter ---

@pytest.mark.parametrize("a,b,expected", [
    ("PROCEED", "REVISE", "REVISE"),
    ("REVISE", "REJECT", "REJECT"),
    ("PROCEED", "NEEDS-DATA", "NEEDS-DATA"),
    ("REJECT", "PROCEED", "REJECT"),
    ("PROCEED", "INVALID", "NEEDS-DATA"),
])
def test_stricter(a, b, expected):
    assert verdict.stricter(a, b) == expected


def test_derive_date_slug():
    d, s = verdict.derive_date_slug(pathlib.Path("2026-10-14-max-tool-calls.md"))
    assert d == "2026-10-14" and s == "max-tool-calls"


# --- leak ---

def test_leak_clean_text(tmp_path):
    tj = tmp_path / "tasks.jsonl"
    tj.write_text('{"instance_id":"rich_1","repo":"Textualize/rich","patch":"","test_patch":"",'
                  '"problem_statement":"Some title here that is long"}\n', encoding="utf-8")
    assert leak.check("nothing to see", tj, scope="config") == []


def test_leak_task_id_scope(tmp_path):
    tj = tmp_path / "tasks.jsonl"
    tj.write_text('{"instance_id":"rich_1","repo":"Textualize/rich","patch":"","test_patch":"",'
                  '"problem_statement":"t"}\n', encoding="utf-8")
    assert any(h["type"] == "task_id" for h in leak.check("see rich_1", tj, scope="config"))
    assert leak.check("see rich_1", tj, scope="tooling") == []  # tooling allows ids


# --- kernellog result parsing ---

def test_p1r_order_free_fields():
    row = kernellog._parse_result_line(
        "  -> resolved=False, exit_code=-1, patch_chars=0, tool_calls=5, duration=67.3s", 1)
    assert row["resolved"] is False
    assert row["tool_calls"] == 5 and row["patch_chars"] == 0


# --- static edit reconstruction (§8) ---

def test_bashpy_heredoc_junk_terminator_stays_in_body():
    # a `PY'` junk terminator leaves the heredoc unterminated; the junk ends up
    # inside the python body (bash behaviour), so the body is a SyntaxError.
    cmd = "python3 - <<'PY'\nimport os\nprint('x')\nPY'\n"
    p = bashpy.parse_command(cmd)
    assert p["heredoc_unterminated"] is True
    assert any(e.kind == "python-exec" for e in p["effects"])


def test_reconstruct_str_replace_applied():
    vfs = reconstruct.VFS(loader=lambda path: "def f():\n    return 1\n")
    # a python heredoc exactly like the agents emit (real newlines inside the body)
    cmd = ("python3 - <<'PY'\n"
           "import pathlib\n"
           "p = pathlib.Path('rich/x.py')\n"
           "s = p.read_text()\n"
           "s = s.replace('return 1', 'return 2')\n"
           "p.write_text(s)\n"
           "PY\n")
    res = reconstruct.reconstruct_run_command(cmd, vfs)
    assert res.prediction == "APPLIED", (res.prediction, res.detail, res.unparsed)
    assert "rich/x.py" in res.changed
    assert "return 2" in res.changed["rich/x.py"]
    assert "return 1" in res.old_literals
    assert "return 2" in res.new_literals


def test_reconstruct_syntax_error_is_not_executed():
    vfs = reconstruct.VFS(loader=lambda path: "x")
    # unterminated string -> SyntaxError, never executed
    res = reconstruct.reconstruct_run_command("python3 -c 'print(\"', vfs" if False
                                              else 'python3 -c "print(\'"', vfs)
    assert res.prediction in ("SYNTAX_ERROR", "BASH_ERROR", "UNPARSED")


def test_r1_escaped_quote_span_decode():
    # the v6b rich_4079 shape: NAME = \"...\"  with an inner \"\" that must stay
    src = 'OLD = \\"a=Text(\\"\\", justify)\\";\nprint(OLD)'
    repaired = reconstruct.extract_escaped_quote_spans(src)
    assert repaired is not None
    assert 'Text("", justify' in repaired


def test_reconstruct_no_exec_apis_in_source():
    import ast
    for mod in (bashpy, reconstruct):
        src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("exec", "eval"), f"{mod.__name__}: {node.func.id}"
            if isinstance(node, ast.Attribute):
                assert not (isinstance(node.value, ast.Name)
                            and node.value.id in ("subprocess", "os")
                            and node.attr in ("system", "popen", "exec", "spawn")), \
                    f"{mod.__name__} uses a process API"


# --- harness edit emulation (§8.3) ---

def test_harness_edit_applies_and_errors():
    r = harness_edit.emulate_edit_file("a = 1\nb = 2\n", "a = 1", "a = 10")
    assert r["status"] == "ok" and "a = 10" in r["new_content"]
    r2 = harness_edit.emulate_edit_file("a = 1\n", "nonexistent", "x")
    assert r2["status"] == "error"
    r3 = harness_edit.emulate_edit_file(None, "x", "y")
    assert r3["status"] == "error" and r3["error_type"] == "FileReadError"


# --- near-miss nm-3 line matcher (§9.2) ---

def _mini_gold(added, removed=()):
    return {"schema": "tasks_gold/2", "tasks": {"rich_1": {
        "repo": "Textualize/rich", "base_commit": "x", "files": ["rich/a.py"],
        "task_fingerprint": "fp", "hunks": [{
            "file": "rich/a.py", "old_start": 1, "old_len": 1,
            "added": list(added), "removed": list(removed)}]}}}


def test_nearmiss_wrote_gold_change_fires_on_new_side():
    gold = _mini_gold(["    result = compute_total(items)"])
    idx = nearmiss.GoldIndex(gold)
    gt = dict(gold["tasks"]["rich_1"], _task_id="rich_1")
    trace = {"_calls": [{"call_index": 1, "step_id": 5, "fn": "edit_file",
                         "obs_class": "OK", "is_edit": True,
                         "edit_files": ["rich/a.py"], "edit_shape": "edit_file",
                         "new_payload": "    result = compute_total(items)",
                         "old_payload": "x", "raw_cmd": None, "msg": None,
                         "read_path": None, "obs_text": None}],
             "refused": [], "edit_attempts": []}
    nm = nearmiss.compute(trace, {"resolved": False}, gt, index=idx)
    assert nm["stages"]["WROTE_GOLD_CHANGE"]["reached"] is True
    assert nm["stages"]["TRIED_APPLY"]["reached"] is True
    assert str(nm["confidence"]).startswith("measured")


def test_nearmiss_cross_task_fp_bar():
    # two tasks with DISTINCT gold; a trace carrying task A's change must not
    # fire WROTE_GOLD_CHANGE for task B.
    gold = {"schema": "x", "tasks": {
        "rich_1": {"repo": "Textualize/rich", "base_commit": "x",
                   "files": ["rich/a.py"], "task_fingerprint": "1",
                   "hunks": [{"file": "rich/a.py", "old_start": 1, "old_len": 1,
                              "added": ["    alpha = unique_symbol_one(z)"], "removed": []}]},
        "rich_2": {"repo": "Textualize/rich", "base_commit": "x",
                   "files": ["rich/b.py"], "task_fingerprint": "2",
                   "hunks": [{"file": "rich/b.py", "old_start": 1, "old_len": 1,
                              "added": ["    beta = different_symbol_two(q)"], "removed": []}]}}}
    idx = nearmiss.GoldIndex(gold)
    trace = {"_calls": [{"call_index": 1, "step_id": 1, "fn": "edit_file",
                         "obs_class": "OK", "is_edit": True, "edit_files": ["rich/a.py"],
                         "edit_shape": "edit_file",
                         "new_payload": "    alpha = unique_symbol_one(z)",
                         "old_payload": "x", "raw_cmd": None, "msg": None,
                         "read_path": None, "obs_text": None}]}
    fp = nearmiss.cross_task_fp([{"task": "rich_1", "_trace": trace}], gold, idx)
    assert fp["wrote_gold_change_fp"] == 0
    assert fp["passes_bar"] is True


# --- gitio allowlist (§13.2) ---

def test_gitio_allowlist_blocks_commit_push_config():
    repo = pathlib.Path(".")
    for verb in (["commit", "-m", "x"], ["push"], ["config", "a", "b"], ["stash"]):
        with pytest.raises(gitio.GitError):
            gitio.git(repo, *verb, scope="worktree")
    # a main-clone reset/checkout is NOT allowed in main scope
    with pytest.raises(gitio.GitError):
        gitio.git(repo, "reset", "--hard", scope="main-ro")


def test_gitio_allowlist_exact_set():
    toks = gitio.allowlist_tokens()
    assert ("reset",) in toks["worktree"]
    assert ("worktree", "add") in toks["main-worktree"]
    assert ("rev-parse",) in toks["main-ro"]
    assert ("commit",) not in toks["worktree"]


# --- replay cache keys + junit parse (§13.4/§13.6) ---

def test_replay_candidate_sha_stable():
    a = replay.candidate_sha_vfs({"rich/a.py": "x\n", "rich/b.py": "y\n"})
    b = replay.candidate_sha_vfs({"rich/b.py": "y\n", "rich/a.py": "x\n"})
    assert a == b  # order-independent
    assert a != replay.candidate_sha_vfs({"rich/a.py": "z\n"})


def test_replay_is_protected():
    assert replay._is_protected("tests/test_markdown.py")
    assert replay._is_protected("conftest.py")
    assert replay._is_protected("x.pth")
    assert not replay._is_protected("rich/markdown.py")


def test_replay_no_mutating_git_verbs_in_source():
    # the engine routes git through gitio (verb-allowlisted). It must never
    # issue a mutating verb as a git argument literal (commit/push/fetch/stash/gc
    # or a `config` SET). `.git/config` file reads are fine (no `git config`).
    import ast
    src = pathlib.Path(replay.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    banned = {"commit", "push", "fetch", "stash", "gc"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert node.value not in banned, f"replay.py has git verb literal {node.value!r}"


# =========================================================== REV5 FEAT-001

import json as _json  # noqa: E402

from kblib import discover, sources, devharness  # noqa: E402


def _w(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _json_log(lines):
    return _json.dumps([{"stream_name": "stdout", "time": 1.0, "data": ln + "\n"}
                        for ln in lines])


_ATIF = _json.dumps({"schema_version": "ATIF-v1.7", "steps": [], "final_metrics": {}})


def _rev5_tree(tmp_path, monkeypatch):
    g = tmp_path / "Gemma"
    monkeypatch.setenv("GKB_GEMMA_ROOT", str(g))
    (g / "kb").mkdir(parents=True)
    # local rig rN dir: traces/ + task_results.jsonl directly in the run dir
    rig = g / "local_eval" / "parity_rig" / "m1_batch" / "ctrl" / "r0"
    _w(rig / "traces" / "trace_rich_1.json", _ATIF)
    _w(rig / "task_results.jsonl", _json.dumps(
        {"instance_id": "rich_1", "resolved": True, "agent_patch_size": 10,
         "tool_calls": 5, "duration_seconds": 3.0}) + "\n")
    _w(rig / "summary.json", _json.dumps({"total_tasks": 2, "resolved": 1}))
    _w(g / "local_eval" / "parity_rig" / "agent_ctrl" / "agent.yaml",
       "model: gemma-4-e4b-it-qat-w4a16-ct\n")
    # kaggle-eval run: JSON log WITHOUT resolved= + results/task_results.jsonl
    ev = g / "kaggle_pkg" / "out_v7"
    _w(ev / "ca5-31b-full129-eval.log",
       _json_log(["declared: gemma-4-31b-it-qat-w4a16-ct",
                  "served model ids: ['gemma-4-31b-it-qat-w4a16-ct', '2']"]))
    _w(ev / "results" / "traces" / "trace_rich_1.json", _ATIF)
    _w(ev / "results" / "traces" / "trace_rich_2.json", _ATIF)
    _w(ev / "results" / "task_results.jsonl", _json.dumps(
        {"instance_id": "rich_1", "resolved": False, "agent_patch_size": 0}) + "\n")
    _w(ev / "agent_ca5" / "agent.yaml", "model: gemma-4-31b-it-qat-w4a16-ct\n")
    # sweep tags: one isolated (guard has --isolate) + pinned, one not isolated
    runs = g / "local_eval" / "runs"
    _w(runs / "s1_A3_r0_rich_1.results.jsonl", _json.dumps(
        {"task": "rich_1", "resolved": False, "patch_chars": 9, "calls": 4, "temp": 0.2}) + "\n")
    _w(runs / "s1_A3_r0_rich_1.pinned.jsonl", _json.dumps(
        {"task": "rich_1", "pinned_resolved": True, "pinned_result": "PASS",
         "gate_resolved": False, "patch_chars": 9, "calls": 4}) + "\n")
    _w(runs / "s1_A3_r0_rich_1.guard.jsonl", _json.dumps(
        {"ev": "start", "arm": "A3", "rep": 0, "task": "rich_1",
         "cmd": "python gate_run.py --tag s1 --isolate --model /m/gemma-4-E4B-it-qat-w4a16-ct "
                "--temp 0.2 --max-tool-calls 28 --prompt-file prompts/a3.md"}) + "\n")
    _w(runs / "s1_A3_r0_rich_1.trace.jsonl", "{}\n")
    _w(runs / "s2_A3_r1_rich_1.results.jsonl", _json.dumps(
        {"task": "rich_1", "resolved": True, "patch_chars": 5, "calls": 3}) + "\n")
    _w(runs / "s2_A3_r1_rich_1.guard.jsonl", _json.dumps(
        {"ev": "start", "arm": "A3", "rep": 1, "task": "rich_1",
         "cmd": "python gate_run.py --tag s2 --model /m/gemma-4-E4B-it --temp 0.2"}) + "\n")
    (runs / "s2_A3_r1_rich_1.patches").mkdir()
    # an incomplete pull and a packager kernel dir + a foreign kernel
    _w(g / "kb" / "pulled" / "x" / "2026-10-31T000000Z.partial" / "a.log", "x")
    _w(g / "local_eval" / "push_packager_ca5" / "kernel-metadata.json",
       _json.dumps({"id": "comfyops/gemma-submission-packager-ca5"}))
    _w(g / "comp_other" / "k" / "kernel-metadata.json", _json.dumps({"id": "someone/kern"}))
    # legacy pulled run (no _pull_meta.json)
    lp = g / "kb" / "pulled" / "v6w_temp1_probe"
    _w(lp / "gemma-sibling-conform-v6w.log",
       _json_log(["[1/1] Evaluating rich_1 (Textualize/rich)...",
                  "  -> resolved=False, exit_code=1, patch_chars=0, tool_calls=3, duration=1.0s"]))
    _w(lp / "results" / "traces" / "trace_rich_1.json", _ATIF)
    return g


def test_discover_rev5_kinds(tmp_path, monkeypatch):
    g = _rev5_tree(tmp_path, monkeypatch)
    d = discover.discover(g)
    assert d["rig_runs"] == ["local_eval/parity_rig/m1_batch/ctrl/r0"]
    assert d["eval_runs"] == ["kaggle_pkg/out_v7"]
    assert "kaggle_pkg/out_v7" not in d["failed_run_dirs"]
    assert "kaggle_pkg/out_v7/results" not in d["rig_runs"]
    assert d["pulled_runs"] == ["kb/pulled/v6w_temp1_probe"]
    assert d["partials"] == ["kb/pulled/x/2026-10-31T000000Z.partial"]
    assert d["kernel_dirs"]["local_eval/push_packager_ca5"]["family"] == "packager"
    assert d["reference_kernels"] == ["comp_other/k"]
    # sweep files grouped per tag, never listed per file
    assert d["sweep_tags"] == ["s1_A3_r0_rich_1", "s2_A3_r1_rich_1"]
    assert set(d["sweep_tag_files"]["s1_A3_r0_rich_1"]) == {"results", "pinned", "guard", "trace"}
    kinds = {(i.kind, i.g_rel) for i in d["items"]}
    assert ("pulled-legacy", "kb/pulled/v6w_temp1_probe") in kinds
    assert not any(i.g_rel.endswith(".results.jsonl") for i in d["items"])


def test_kernel_family_rules():
    assert discover.kernel_family("comfyops/gemma-sibling-conform-31b-a3-hard") == "sibling-conform"
    assert discover.kernel_family("comfyops/gemma-submission-packager-ca5") == "packager"
    assert discover.kernel_family("comfyops/ca5-31b-full129-eval") == "full129-eval"
    assert discover.kernel_family("comfyops/ci-tools-probe") == "probe"
    assert discover.kernel_family("comfyops/gemma-localizer-lora-train") == "train"


def test_sweep_rows_isolate_vs_not(tmp_path, monkeypatch):
    g = _rev5_tree(tmp_path, monkeypatch)
    d = discover.discover(g)
    a = sources.sweep_rows("s1_A3_r0_rich_1", d["sweep_tag_files"]["s1_A3_r0_rich_1"], g)
    b = sources.sweep_rows("s2_A3_r1_rich_1", d["sweep_tag_files"]["s2_A3_r1_rich_1"], g)
    assert a[0]["patch_trusted"] is True and b[0]["patch_trusted"] is False
    # pinned rescore beats the raw results row
    assert a[0]["scorer"] == "sweep-pinned" and a[0]["outcome"]["resolved"] is True
    assert b[0]["scorer"] == "sweep-raw" and b[0]["outcome"]["resolved"] is True
    assert a[0]["config"]["model"] == "gemma-4-E4B-it-qat-w4a16-ct"
    assert a[0]["config"]["max_tool_calls"] == 28 and a[0]["config"]["temperature"] == 0.2
    assert a[0]["arm"] == "A3" and a[0]["rep"] == 0


def test_task_results_outcomes_and_summary(tmp_path, monkeypatch):
    g = _rev5_tree(tmp_path, monkeypatch)
    rig = g / "local_eval" / "parity_rig" / "m1_batch" / "ctrl" / "r0"
    o = sources.outcomes_from_task_results(rig / "task_results.jsonl")
    assert o["rich_1"]["resolved"] is True and o["rich_1"]["patch_chars"] == 10
    assert o["rich_1"]["tool_calls"] == 5
    assert sources.summary_disagrees(rig / "summary.json", o, 1) is True
    assert sources.rig_arm_and_rep("local_eval/parity_rig/m1_batch/ctrl/r0") == ("ctrl", 0)
    assert sources.rig_arm_and_rep("local_eval/parity_rig/m1_locate/agent_ctrl_e4b_def_r0") == \
        ("agent_ctrl_e4b_def", 0)
    assert sources.rig_arm_config(g, "ctrl").name == "agent_ctrl"


def test_stack_and_track():
    s, t, _ = sources.stack_and_track("local-rig", "gemma-4-e4b-it-qat-w4a16-ct", True)
    assert t == "small-model" and s["model_served_verified"] is False
    s, t, _ = sources.stack_and_track("kaggle", "gemma-4-31b-it-qat-w4a16-ct", True)
    assert t == "main" and s["model_served_verified"] is True and s["scorer"] == "harness"
    assert sources.stack_and_track("kaggle", "gemma-4-12b-it-qat-w4a16-ct", False)[1] == "dev-proxy"


def test_build_rows_rev5_synthetic(tmp_path, monkeypatch):
    # end-to-end adapters on the synthetic tree (no real data)
    import build_kb
    g = _rev5_tree(tmp_path, monkeypatch)
    _w(g / "comp_files" / "tasks.jsonl", "")
    d = discover.discover(g)
    from kblib import nearmiss
    tg = {"schema": "x", "tasks": {}}
    ctx = build_kb._RowCtx(g, d, tg, nearmiss.GoldIndex(tg))
    for rd in d["eval_runs"]:
        build_kb._rows_kernel_run(ctx, rd, "kaggle-kernel")
    for rd in d["rig_runs"]:
        build_kb._rows_rig_run(ctx, rd)
    for t in d["sweep_tags"]:
        build_kb._rows_sweep_tag(ctx, t)
    by = {r["row_id"]: r for r in ctx.rows}
    ev = by["kaggle_pkg/out_v7::rich_1"]
    assert ev["outcome_source"] == "task_results" and ev["outcome"]["resolved"] is False
    assert ev["stack"]["model_served_verified"] is True and ev["track"] == "main"
    assert ev["config_confidence"].startswith("agent dir")
    assert by["kaggle_pkg/out_v7::rich_2"]["outcome"] is None  # trace only
    rg = by["local_eval/parity_rig/m1_batch/ctrl/r0::rich_1"]
    assert rg["run_kind"] == "local-rig" and rg["stack"]["platform"] == "local-rig"
    assert rg["track"] == "small-model" and rg["stack"]["model_served_verified"] is False
    assert rg["summary_disagrees"] is True and rg["arm"] == "ctrl"
    sw = by["local_eval/runs/s2_A3_r1_rich_1::rich_1"]
    assert sw["run_kind"] == "local-sweep" and sw["patch_trusted"] is False and sw["trace"] is None


def test_zip_drift_detects_drift(tmp_path):
    import zipfile
    pkg = tmp_path / "submit_x"
    _w(pkg / "agent.yaml", "model: m\n")
    _w(pkg / "eval_config.yaml", "evaluation:\n  max_tool_calls: 28\n")
    _w(pkg / "configs" / "sampling.yaml", "temperature: 0.2\n")
    _w(pkg / "prompts" / "system.md", "be good\n")
    assert configs.zip_drift(pkg) == "NO_ZIP"
    with zipfile.ZipFile(pkg / "submission.zip", "w") as zf:
        zf.writestr("agent.yaml", "model: m\r\n")  # CRLF-only difference is not drift
        zf.writestr("eval_config.yaml", "evaluation:\n  max_tool_calls: 28\n")
        zf.writestr("configs/sampling.yaml", "temperature: 0.2\n")
        zf.writestr("prompts/system.md", "be different\n")
    assert configs.zip_drift(pkg) == "DRIFT(['prompts/system.md'])"
    (pkg / "prompts" / "system.md").write_text("be different\n", encoding="utf-8")
    assert configs.zip_drift(pkg) == "MATCH"
    assert not (pkg / "configs" / "agent.yaml").exists()  # nothing extracted


def test_devharness_notebook_ignores_decoy_comment(tmp_path, monkeypatch):
    monkeypatch.setenv("GKB_GEMMA_ROOT", str(tmp_path))
    nb = {"cells": [
        {"cell_type": "markdown", "source": ["EventsCompactionConfig(compaction_interval=1)"]},
        {"cell_type": "code", "source": [
            "!pip install x\n",
            "%time y = 1\n",
            "# EventsCompactionConfig(compaction_interval=5) decoy comment\n",
            "s = 'EventsCompactionConfig(compaction_interval=7)'\n",
            "cfg = EventsCompactionConfig(compaction_interval=15, overlap_size=2,\n",
            "    token_threshold=14336, event_retention_size=5)\n",
            "cc = ContextCacheConfig(min_tokens=2048, ttl_seconds=1800, cache_intervals=10)\n"]},
    ]}
    d = tmp_path / "submit_k"
    _w(d / "k.ipynb", _json.dumps(nb))
    rec = devharness.scan_dir(d)
    assert rec["compaction_interval"] == 15 and rec["overlap_size"] == 2
    assert rec["token_threshold"] == 14336 and rec["cache_min_tokens"] == 2048
    assert rec["cache_intervals"] == 10 and rec["found"] is True
    readme = _w(tmp_path / "HARNESS_README.md",
                "- **Events Compaction (`EventsCompactionConfig`)**:\n"
                "  - `compaction_interval = 5`\n  - `overlap_size = 2`\n"
                "  - `token_threshold = 14,336`\n- **Context Caching**:\n")
    ref = devharness.scorer_reference(readme)
    assert (ref["compaction_interval"], ref["overlap_size"], ref["token_threshold"]) == (5, 2, 14336)
    assert devharness.matches_scorer(rec, ref) == (False, ["compaction_interval"])
    assert devharness.scan_dir(tmp_path / "nothing_here") is None


def test_rev5_modules_have_no_exec_eval_or_process_apis():
    import ast
    for mod in (devharness, sources, discover):
        tree = ast.parse(pathlib.Path(mod.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("exec", "eval", "compile", "__import__"), \
                    f"{mod.__name__}: {node.func.id}"
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
                assert "subprocess" not in names, f"{mod.__name__} imports subprocess"
            if isinstance(node, ast.Attribute):
                assert not (isinstance(node.value, ast.Name) and node.value.id == "os"
                            and node.attr in ("system", "popen", "spawnl", "execv")), mod.__name__


def test_fp_sampler_hash_cap_deterministic():
    import hashlib
    tasks = {f"rich_{i}": {"repo": "Textualize/rich", "base_commit": "x", "files": ["a.py"],
                           "task_fingerprint": str(i),
                           "hunks": [{"file": "a.py", "old_start": 1, "old_len": 1,
                                      "added": [f"    value_{i} = compute_{i}(arg)"],
                                      "removed": []}]}
             for i in range(60)}
    gold = {"schema": "x", "tasks": tasks}
    idx = nearmiss.GoldIndex(gold)
    trace = {"_calls": [{"is_edit": True, "new_payload": "    value_0 = compute_0(arg)",
                         "edit_files": ["a.py"], "edit_shape": "edit_file"}]}
    rows = [{"task": "rich_0", "_trace": trace}]
    a = nearmiss.cross_task_fp(rows, gold, idx)
    b = nearmiss.cross_task_fp(rows, gold, idx)
    assert a == b
    assert a["pairs"] == nearmiss.FP_CAP == 40
    assert a["sampling"] == "hash-cap-40" and a["wrote_gold_change_fp"] == 0
    # fewer same-repo tasks than the cap -> all of them
    small = {"schema": "x", "tasks": {k: tasks[k] for k in ("rich_0", "rich_1", "rich_2")}}
    assert nearmiss.cross_task_fp(rows, small, nearmiss.GoldIndex(small))["pairs"] == 2
    # the chosen 40 are the smallest sha256(task + other)
    others = sorted((o for o in tasks if o != "rich_0"),
                    key=lambda o: hashlib.sha256(("rich_0" + o).encode()).hexdigest())
    assert len(others[:40]) == 40


def test_card_grouping(tmp_path, monkeypatch, capsys):
    import build_kb
    g = tmp_path / "Gemma"
    monkeypatch.setenv("GKB_GEMMA_ROOT", str(g))
    kb = g / "kb"
    rows = [
        {"row_id": "a::rich_1", "run_id": "a", "task": "rich_1", "version_label": "v6w",
         "outcome": {"resolved": True}, "failure_class": "RESOLVED", "failure_subclass": None,
         "stack": {"platform": "kaggle"}, "track": "main"},
        {"row_id": "b::rich_1", "run_id": "b", "task": "rich_1", "version_label": "v6w",
         "outcome": {"resolved": False}, "failure_class": "LOCATE", "failure_subclass": None,
         "stack": {"platform": "kaggle"}, "track": "main"},
        {"row_id": "c::rich_1", "run_id": "c", "task": "rich_1", "version_label": "ca5",
         "outcome": {"resolved": False}, "failure_class": None, "failure_subclass": None,
         "stack": {"platform": "local-rig"}, "track": "small-model"},
    ]
    _w(kb / "runs.jsonl", "".join(_json.dumps(r) + "\n" for r in rows))
    assert build_kb.main(["card", "--task", "rich_1", "--limit", "1"]) == 0
    out = capsys.readouterr().out.splitlines()
    groups = [l for l in out if l.startswith("GROUP ")]
    assert groups == [
        "GROUP stack=kaggle track=main label=v6w n=2 resolved=1 classes=LOCATE:1,RESOLVED:1",
        "GROUP stack=local-rig track=small-model label=ca5 n=1 resolved=0 classes=None:1"]
    assert sum(1 for l in out if l.startswith("{")) == 1
    assert build_kb.main(["card", "--task", "rich_1", "--stack", "local-rig"]) == 0
    out = capsys.readouterr().out.splitlines()
    assert [l for l in out if l.startswith("GROUP ")] == [groups[1]]
    # card RUN TASK unchanged
    assert build_kb.main(["card", "a", "rich_1"]) == 0
    assert '"row_id": "a::rich_1"' in capsys.readouterr().out


# --- FEAT-002: read-only pull, attribution, baselines/banner, proposals ---

def test_kaggle_argv_validator(tmp_path, monkeypatch):
    from kblib import kaggle
    g = tmp_path / "Gemma"
    monkeypatch.setenv("GKB_GEMMA_ROOT", str(g))
    pulled = g / "kb" / "pulled" / "x" / "t.partial"
    ok = ["kernels", "output", "comfyops/gemma-sibling-conform-v6w", "-p", str(pulled)]
    assert kaggle.validate_argv(ok) == ok
    assert kaggle.validate_argv(ok + ["--file-pattern", kaggle.NO_BINARIES_PATTERN])
    assert kaggle.validate_argv(["competitions", "submissions", "gemma-4-developer-agent",
                                 "--csv"])
    bad = [
        ["kernels", "push", "-p", str(pulled)],
        ["kernels", "output", "comfyops/x/3", "-p", str(pulled)],
        ["kernels", "output", "other/x", "-p", str(pulled)],
        ["kernels", "output", "comfyops/x", "-p", str(tmp_path / "elsewhere")],
        ["kernels", "pull", "comfyops/x", "-p", str(pulled)],             # no -m
        ["competitions", "submit", "gemma-4-developer-agent", "--csv"],
        ["competitions", "submissions", "other-comp", "--csv"],
    ]
    for a in bad:
        with pytest.raises(kaggle.ArgvError):
            kaggle.validate_argv(a)
    for s in ("comfyops/x/3", "other/x", "comfyops/X"):
        with pytest.raises(kaggle.ArgvError):
            kaggle.normalize_slug(s)
    assert kaggle.normalize_slug("ca5-31b-full129-eval") == "comfyops/ca5-31b-full129-eval"


def test_pull_dry_run_makes_no_subprocess_call(tmp_path, monkeypatch, capsys):
    import subprocess
    import build_kb
    g = tmp_path / "Gemma"
    (g / "kb").mkdir(parents=True)
    monkeypatch.setenv("GKB_GEMMA_ROOT", str(g))

    def boom(*a, **k):
        raise AssertionError("subprocess.run called during --dry-run")
    monkeypatch.setattr(subprocess, "run", boom)
    assert build_kb.main(["pull", "--submissions", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert '"competitions", "submissions", "gemma-4-developer-agent", "--csv"' in out
    assert '"kernels", "list", "--mine", "--csv", "--page-size", "200"' in out
    assert build_kb.main(["pull", "--slug", "comfyops/x", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert '"kernels", "output", "comfyops/x", "-p"' in out and '"-m"]' in out
    assert not (g / "kb" / "pulled").exists() or not any((g / "kb" / "pulled").rglob("*"))
    # bad args -> exit 1, still no subprocess
    assert build_kb.main(["pull", "--slug", "comfyops/x/3", "--dry-run"]) == 1
    assert build_kb.main(["pull", "--slug", "other/x", "--dry-run"]) == 1
    assert build_kb.main(["pull"]) == 1


def test_no_push_in_any_kblib_argv_template():
    import ast
    from kblib import kaggle
    for tpl in kaggle.ALLOWED_TEMPLATES:
        assert "push" not in tpl and "submit" not in tpl
    kb = pathlib.Path(kaggle.__file__).resolve().parent
    for f in sorted(kb.glob("*.py")):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.List, ast.Tuple)):
                consts = {e.value for e in node.elts
                          if isinstance(e, ast.Constant) and isinstance(e.value, str)}
                assert not ({"kernels", "push"} <= consts), f"push argv template in {f.name}"
                assert not ({"competitions", "submit"} <= consts), f"submit argv in {f.name}"
    # build never imports the network runner at module level
    src = (kb.parent / "build_kb.py").read_text(encoding="utf-8")
    top = [n for n in ast.parse(src).body if isinstance(n, (ast.Import, ast.ImportFrom))]
    for n in top:
        names = [a.name for a in n.names]
        assert "kaggle" not in names and getattr(n, "module", "") != "kblib.kaggle"


def test_attribution_mismatch_on_temperature():
    from kblib import attribution as at
    f = at.description_facts("v6w + temperature 1.0 / top_k 64 (only change vs the 0.15 "
                             "v6w baseline)")
    assert f["temperature"] == 1.0 and f["top_k"] == 64
    f2 = at.description_facts("v6w: 0.18 budget (28/8/80/240) + thinking_budget 1024. Gate 4/6")
    assert (f2["max_tool_calls"], f2["max_time_minutes"], f2["max_turns"],
            f2["timeout_seconds"], f2["thinking_budget"]) == (28, 8, 80, 240, 1024)
    assert at.description_facts("max_tool_calls 28->100")["max_tool_calls"] == 100
    assert at.description_model("ladder: gemma-4-31b-it-qat -> gemma-4-12b-it-qat") == "12b"
    assert at.description_track("E4B ca5 anchor-grep") == "small-model"
    assert at.description_track("Lucy") == "main"
    row = {"ref": "57201051", "description": "v6w + temperature 1.0 / top_k 64",
           "status": "SubmissionStatus.COMPLETE", "publicScore": "0.13"}
    cfg = {"temperature": 0.2, "top_k": None, "thinking_budget": 1024}
    mapped = at.map_refs("v6w", "gemma-sibling-conform-v6w", [row], None, {})
    assert mapped and "description mentions v6w" in mapped[0][1]
    rec = at.attribute(cfg, None, mapped, {}, {})[0]
    assert rec["flag"] == at.MISMATCH
    assert "temperature: pulled 0.2 vs submission 1" in rec["detail"]
    # equal package hashes and no differing fact -> CONFIRMED
    h = {"agent.yaml": "a"}
    rec = at.attribute({"temperature": 1.0}, h, [(row, ["x"])], {"57201051": h},
                       {"57201051": "z.zip"})[0]
    assert rec["flag"] == at.CONFIRMED
    # nothing to compare -> UNVERIFIED
    rec = at.attribute({}, None, [({"ref": "1", "description": "Lucy"}, ["x"])], {}, {})[0]
    assert rec["flag"] == at.UNVERIFIED
    # "V1" in prose is a kernel version, not the v1 run label
    assert not at._mentions("uploaded from V1 committed output", "v1")
    assert at._mentions("A25 router blind", "a25")


def test_banner_conflict_from_steering_text(tmp_path):
    from kblib import baseline as bl
    st = tmp_path / "gemma-submission-protocol.md"
    st.write_text("x\n- **v6w @ 0.15 is SACRED (live-best)** \u2014 Kaggle submission "
                  "57098497, 2026-10-12\n", encoding="utf-8")
    s = bl.steering_baseline(st)
    assert (s["label"], s["score"], s["ref"], s["line"]) == ("v6w", 0.15, "57098497", 2)
    curated = {"label": "v6w", "lb": 0.15, "submission_ref": 57098497}
    rows = [
        {"ref": "57760641", "date": "2026-10-29", "description": "ca5: anchor-grep",
         "status": "SubmissionStatus.COMPLETE", "publicScore": "0.20"},
        {"ref": "57807043", "date": "2026-10-30", "description": "E4B ca5",
         "status": "SubmissionStatus.COMPLETE", "publicScore": "0.03"},
        {"ref": "57847285", "date": "2026-10-31", "description": "ca5 resubmit",
         "status": "SubmissionStatus.PENDING", "publicScore": ""},
        {"ref": "57146757", "date": "2026-10-13", "description": "PER-TASK BRANCHING",
         "status": "SubmissionStatus.COMPLETE", "publicScore": "0.12"},
    ]
    best = bl.track_best(rows)
    assert best["main"]["ref"] == "57760641" and best["small-model"]["ref"] == "57807043"
    b = bl.banner(s, curated, best, "pulled/submissions/x.csv")
    assert b.splitlines()[0].startswith("BASELINE: steering says v6w @ 0.15 (ref 57098497")
    assert "BASELINE CONFLICT: steering=v6w@0.15 57098497" in b
    assert "lb_best_main=ca5: anchor-grep@0.20 57760641" in b
    assert "no curated small-model baseline" in b
    assert "STALE" not in b.upper()
    # all three agree -> no conflict line on the main track
    b2 = bl.banner(s, curated, bl.track_best(rows[3:]) | {"main": {
        "ref": "57098497", "score": 0.15, "desc": "v6w", "date": "", "n_ties": 1}}, "c.csv")
    assert "BASELINE CONFLICT: steering" not in b2
    # stale pending + proposal text
    rl = {"baseline": curated, "pending": [{"label": "branch_final",
                                            "submission_ref": 57146757, "status": "PENDING"}]}
    sp = bl.stale_pending(rl, rows)
    assert sp == [{"index": 0, "label": "branch_final", "ref": "57146757",
                   "curated_status": "PENDING", "status": "COMPLETE", "score": 0.12}]
    md = bl.proposed_updates(rl, {"path": "curated/submissions.csv", "reason": "r",
                                  "rows": rows}, best, s)
    assert '"path": "/pending/0/status"' in md and "Baseline conflict" in md
    assert "small-model" in md and "lever_lexicon.json is missing" in md


def test_lb_source_prefers_newer_snapshot(tmp_path, monkeypatch):
    import os
    from kblib import baseline as bl
    kb = tmp_path / "kb"
    hdr = "ref,fileName,date,description,status,publicScore,privateScore\n"
    _w(kb / "curated" / "submissions.csv", hdr + "1,s.zip,2026-10-01,a,"
       "SubmissionStatus.COMPLETE,0.10,\n")
    os.utime(kb / "curated" / "submissions.csv", (1792000000, 1792000000))  # 2026-10-15
    assert bl.lb_source(kb)["path"] == "curated/submissions.csv"
    _w(kb / "pulled" / "submissions" / "20261101T055511Z.csv",
       hdr + "2,s.zip,2026-10-30,b,SubmissionStatus.COMPLETE,0.20,\n")
    src = bl.lb_source(kb)
    assert src["path"] == "pulled/submissions/20261101T055511Z.csv"
    assert [r["ref"] for r in src["rows"]] == ["2"]
    _w(kb / "pulled" / "submissions" / "20261001T000000Z.csv", hdr)   # older than curated
    assert bl.lb_source(kb)["path"] == "pulled/submissions/20261101T055511Z.csv"


def test_safe_write_allows_only_the_proposals_file_under_curated(tmp_path, monkeypatch):
    g = tmp_path / "Gemma"
    monkeypatch.setenv("GKB_GEMMA_ROOT", str(g))
    cur = g / "kb" / "curated"
    cur.mkdir(parents=True)
    assert io.safe_write(cur / "_proposed_updates.md", "# p\n") is True
    for name in ("claims.jsonl", "run_labels.json", "submissions.csv", "replay_set.json",
                 "lever_lexicon.json", "_proposed_updates.md.bak", "sub/_proposed_updates.md"):
        with pytest.raises(io.SafeWriteError):
            io.safe_write(cur / name, "x")


# =========================================================== REV5 FEAT-003

def _syn_claims():
    def c(cid, line, status, versions, tasks=(), levers=(), text="t", facts=(), sup=None):
        return {"claim_id": cid, "id": cid, "line": line, "unit_start_line": line, "status": status,
                "kind": "fact-line", "versions": list(versions), "tasks": list(tasks),
                "levers": list(levers), "text": text, "heading": "h", "facts": list(facts),
                "superseded_by": sup or [], "date": "2026-10-01", "reason": "r"}
    return [
        c("C-1", 10, "SUPPORTED", ["ca5"], text="ca5 scored 0.20",
          facts=[{"field": "F5", "value": "0.20", "line": 10, "version": "ca5"}]),
        c("C-2", 30, "SUPERSEDED", ["v6w"], tasks=["rich_4077"], levers=["temperature"],
          text="v6w temp 1.0", sup=[{"unit_id": "U-new", "link_basis": "heading-tag"}]),
        c("C-3", 20, "UNVERIFIED", ["ca5-v2"], text="ca5_v2 anchor grep run"),
        c("C-4", 40, "CONTRADICTED", ["v7"], tasks=["rich_4079"], text="v7 resolved 1/6",
          facts=[{"field": "F2", "value": True, "line": 40, "version": "v7", "task": "rich_4077"}]),
    ]


def test_cmd_claims_filters_synthetic(tmp_path, monkeypatch, capsys):
    import argparse
    import build_kb
    rows = _syn_claims()
    ids = {"temperature", "prompt-anchor-grep"}
    f = lambda **kw: [c["claim_id"] for c in build_kb.filter_claims(rows, lever_ids=ids, **kw)]
    assert f() == ["C-4", "C-2", "C-3", "C-1"]                    # newest unit first
    assert f(version="ca5") == ["C-1"]                             # ca5_v2 is a different label
    assert f(version="CA5_v2") == ["C-3"]
    assert f(task="rich_4077") == ["C-4", "C-2"]                   # claim tasks or fact tasks
    assert f(lever="temperature") == ["C-2"]                       # lexicon id
    assert f(lever="anchor grep") == ["C-3"]                       # free text
    assert f(text=r"scored 0\.20") == ["C-1"]
    assert f(text="0.20") == ["C-1"]                               # facts are searched too
    assert f(status="superseded") == ["C-2"]
    g = tmp_path / "Gemma"
    monkeypatch.setenv("GKB_GEMMA_ROOT", str(g))
    (g / "kb").mkdir(parents=True)
    (g / "kb" / "log_claims.jsonl").write_text(
        "".join(_json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    ns = argparse.Namespace(task=None, version=None, lever=None, text=None, status=None, limit=2)
    assert build_kb.cmd_claims(ns) == 0
    out = capsys.readouterr().out
    assert "4 matched of 4; showing 2" in out
    assert "C-4" in out and "C-2 SUPERSEDED [SUPERSEDED by U-new]" in out and "C-1" not in out
    ns = build_kb.build_parser().parse_args(["claims", "--version", "ca5", "--limit", "5"])
    assert ns.limit == 5 and ns.version == "ca5"
    assert build_kb.cmd_claims(ns) == 0
    out = capsys.readouterr().out
    assert "C-1" in out and "C-3" not in out and "C-2" not in out


def _lever_rows(run, label, temp, tasks, kind="kaggle-kernel"):
    cfg = {"max_tool_calls": 28, "max_time_minutes": 8, "max_turns": 80, "timeout_seconds": 240,
           "thinking_budget": 1024, "temperature": temp, "top_k": None, "top_p": 0.95,
           "max_output_tokens": 8192, "adapter": None, "model": "gemma-4-31b",
           "tools": ["edit_file", "read_file"], "prompt_sha256": "abc"}
    return [{"run_id": run, "task": t, "version_label": label, "track": "main",
             "run_kind": kind, "stack": {"platform": "kaggle"}, "config": dict(cfg),
             "outcome": {"resolved": r}, "dev_harness": None} for t, r in tasks.items()]


def test_lever_single_temperature_instance(tmp_path):
    from kblib import levers
    kb = pathlib.Path(__file__).resolve().parent.parent
    lex = levers.load_lexicon(tmp_path, kb / "kblib")          # tmp kb -> default lexicon
    assert lex["source"].startswith("kblib/lever_lexicon_default.json")
    assert len(lex["levers"]) >= 10
    rows = _lever_rows("submit_v6w/out", "v6w", 0.2, {"rich_1": True, "rich_2": False})
    rows += _lever_rows("submit_v6x/out", "v6x", 1.0, {"rich_1": True, "rich_2": True,
                                                      "rich_3": False})
    res = levers.compute(tmp_path, rows, {"claims": []}, lex, "v6w", [], {})
    main = {x["id"]: x for x in res["tracks"]["main"]["levers"]}
    assert main["temperature"]["runs"] == 1
    assert (main["temperature"]["rows"], main["temperature"]["distinct_tasks"]) == (3, 3)
    assert main["temperature"]["labels"] == ["v6x"]
    assert main["temperature"]["transitions"] == ["0.2->1.0 (baseline) x1"]
    assert main["temperature"]["per_task"].startswith("rich_1:1R/1")
    others = [k for k, x in main.items() if x["runs"] and k != "temperature"]
    assert others == []
    assert res["tracks"]["main"]["reference"].startswith("curated baseline v6w")
    lines = levers.render_lines(res)
    assert any(l.startswith("| temperature | config | 1 | 3/3 |") for l in lines)
    assert any(l.startswith("### Track: small-model") for l in lines)


def test_standing_truths_render_bounded_and_deterministic(tmp_path):
    from kblib import standing
    g = tmp_path / "Gemma"
    (g / "kb" / "curated").mkdir(parents=True)
    (g / "kb" / "curated" / "run_labels.json").write_text('{\n "baseline": {"label": "v6w"}\n}\n',
                                                         encoding="utf-8")
    csvp = g / "kb" / "curated" / "submissions.csv"
    csvp.write_text("ref,date,description,status,publicScore\n111,2026-10-29,ca5 x,COMPLETE,0.20\n",
                    encoding="utf-8")
    cl = {"curated": [{"id": "J-x", "status": "SUPPORTED", "evidence_ok": True,
                       "text": "Sub-agents underperform; do not use them.", "curated_line": 1,
                       "evidence": [{"path": "Gemma/GEMMA_EXPERIMENT_LOG.md", "line": 5,
                                     "exists": True}]}],
          "claims": [{"claim_id": f"C-{i}", "line": i, "status": "SUPPORTED", "kind": "verdict",
                      "unit_kind": "verdict", "text": f"Lever {i} is DEAD after the gate result."}
                     for i in range(200)],
          "chains": [{"chain": ["U-a", "U-b"], "lines": [3, 9], "newest": "U-b",
                      "newest_heading": "CORRECTION: x", "newest_line": 9,
                      "newest_superseded": False}], "units": []}
    lb_src = {"path": "curated/submissions.csv", "abs": csvp}
    best = {"main": {"ref": "111", "score": 0.2, "desc": "ca5 x", "date": "2026-10-29"}}
    args = (g, "abc123", cl, {"label": "v6w", "lb": 0.15, "submission_ref": 9}, lb_src, best,
            {"found": True, "label": "v6w", "score": 0.15, "ref": "9", "line": 23},
            ["LB best != curated"], [{"run_id": "r", "track": "main", "stack": {"platform": "kaggle"}}],
            {"compaction_interval": 5, "source": "comp_files/HARNESS_README.md:L555"}, [])
    a = standing.render(*args)
    b = standing.render(*args)
    assert a == b
    lines = a.rstrip("\n").split("\n")
    assert len(lines) <= 80
    bullets = [l for l in lines if l.startswith("- ")]
    assert bullets and all(" — evidence: " in l and l.split(" — evidence: ")[1].strip() for l in bullets)
    assert any("[J-x]" in l and "GEMMA_EXPERIMENT_LOG.md:L5" in l for l in bullets)
    assert any("[B-lb-main]" in l and "kb/curated/submissions.csv:L2" in l for l in bullets)
    assert any(l.startswith("- [trimmed]") for l in bullets)
    for sec in ("## Baselines & LB", "## Stacks", "## Closed axes", "## Open axes", "## Corrections"):
        assert any(l.startswith(sec) for l in lines)


# =========================================================== REV5 FEAT-004 (rp-5)

def test_gitio_extra_env_and_binary(monkeypatch):
    seen = {}

    class _R:
        returncode = 0
        stdout = b"x"
        stderr = b""

    def fake_run(cmd, **kw):
        seen["cmd"], seen["kw"] = cmd, kw
        return _R()
    monkeypatch.setattr(gitio.subprocess, "run", fake_run)
    gitio.git(pathlib.Path("wt"), "diff", "--binary", scope="worktree", eol=True,
              odb="odb", alt="alt", extra_env={"GIT_CONFIG_COUNT": "1"}, binary=True)
    assert seen["kw"]["env"]["GIT_CONFIG_COUNT"] == "1"
    assert seen["kw"]["env"]["GIT_OBJECT_DIRECTORY"] == "odb"
    assert "text" not in seen["kw"]           # bytes mode
    assert seen["cmd"][-2:] == ["diff", "--binary"]
    gitio.git(pathlib.Path("wt"), "status", scope="main-ro")
    assert seen["kw"].get("text") is True and "GIT_CONFIG_COUNT" not in seen["kw"]["env"]
    # extra_env never bypasses the verb allowlist
    with pytest.raises(gitio.GitError):
        gitio.git(pathlib.Path("wt"), "commit", scope="worktree", extra_env={"A": "1"})


def test_replay_source_no_if_false_and_no_git_subprocess():
    import ast
    src = pathlib.Path(replay.__file__).read_text(encoding="utf-8")
    assert "if False" not in src
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "run" and getattr(node.func.value, "id", "") == "subprocess":
            for sub in ast.walk(node):
                assert not (isinstance(sub, ast.Constant) and sub.value == "git"), \
                    "replay.py runs git via subprocess outside gitio"


def _junit(tmp_path, cases):
    body = "".join(cases)
    p = tmp_path / "junit.xml"
    p.write_text(f'<?xml version="1.0"?><testsuites><testsuite>{body}</testsuite></testsuites>',
                 encoding="utf-8")
    return p


def test_junit_skipped_required_node_is_infra_with_message(tmp_path):
    jx = _junit(tmp_path, [
        '<testcase classname="tests.test_x" name="test_ok"/>',
        '<testcase classname="tests.test_x" name="test_win">'
        '<skipped type="pytest.skip" message="requires a POSIX terminal"/></testcase>'])
    parsed = replay._parse_junit(jx)
    assert parsed["skipped_names"] == ["test_win"]
    assert parsed["skip_reasons"]["test_win"] == "requires a POSIX terminal"
    gold = {"task": "rich_1"}
    eng = replay.ReplayEngine({"tasks": {"rich_1": {"task_fingerprint": "fp"}}}, freeze=False)
    required = ["test_win"]

    def fake_run(repo, task, base_commit, *, kind, patch_text=None, timeout_s=300,
                 required_mode="added", **kw):
        if patch_text is None:   # base control: fails the required node
            return {"result": "RAN", "exit_code": 1, "passed": 0, "failed": 1, "errors": 0,
                    "required_pass": False, "required_tests": required}
        res = dict(parsed, result="RAN", exit_code=0)
        res["required_tests"] = required
        res["required_pass"] = eng._required_pass(res, required)
        res["missing_required"] = replay._missing_required(res, required)
        return res
    eng.run_candidate = fake_run
    rec = eng.gold_first("Textualize/rich", "rich_1", "abc")
    assert rec["gold_first"] == "INFRA"
    assert "required nodes skipped on this platform" in rec["reason"]
    assert "requires a POSIX terminal" in rec["reason"]
    assert rec["required_mode"] == "added" and rec["task_fingerprint"] == "fp"
    assert gold  # noqa


def test_gold_collection_error_on_missing_module_is_infra():
    eng = replay.ReplayEngine({"tasks": {"rich_1": {"task_fingerprint": "fp"}}}, freeze=False)

    def fake_run(repo, task, base_commit, *, kind, patch_text=None, **kw):
        return {"result": "RAN", "exit_code": 2, "passed": 0, "failed": 0, "errors": 1,
                "required_pass": False, "required_tests": ["test_x"],
                "missing_required": ["test_x"], "skipped_names": [],
                "missing_modules": ["attr"]}
    eng.run_candidate = fake_run
    rec = eng.gold_first("Textualize/rich", "rich_1", "abc")
    assert rec["gold_first"] == "INFRA" and "attr" in rec["reason"]


_TP_HUNK = (
    "--- a/tests/test_x.py\n+++ b/tests/test_x.py\n"
    "@@ -4,3 +4,3 @@ def test_a():\n"
    " def test_b():\n"
    "-    assert f() == 1\n"
    "+    assert f() == 2\n"
    "     return None\n"
    "@@ -10,0 +11,2 @@\n"
    "+def test_new():\n"
    "+    assert True\n")
_POST = ("def test_a():\n    assert True\n\n"
         "def test_b():\n    assert f() == 2\n    return None\n\n"
         "class TestK:\n    def test_m(self):\n"
         "        assert 1\n"
         "def test_new():\n    assert True\n")


def test_required_nodes_added_is_rp4_and_hunk_adds_modified_body(tmp_path):
    wt = tmp_path / "wt"
    (wt / "tests").mkdir(parents=True)
    (wt / "tests" / "test_x.py").write_text(_POST, encoding="utf-8")
    gt = {"tests": {"added_tests": ["test_new", "test_new"], "files": ["tests/test_x.py"]}}
    added, nodes = replay._required_tests(gt, wt, "added", _TP_HUNK)
    assert added == ["test_new"] and nodes == []          # exactly the rp-4 list
    hunk, nodes = replay._required_tests(gt, wt, "hunk", _TP_HUNK)
    assert "test_b" in hunk and "test_new" in hunk       # modified body added
    assert set(added) <= set(hunk)                        # never drops an added node
    assert "test_a" not in hunk and "test_m" not in hunk  # context-only defs not added
    assert "tests/test_x.py::test_b" in nodes


def test_unidiff_new_side_line_numbers():
    f = unidiff.parse(_TP_HUNK)[0]
    assert f["hunks"][0]["added_new_lines"] == [5]
    assert f["hunks"][0]["removed_at_new"] == [5]
    assert f["hunks"][1]["added_new_lines"] == [11, 12]


def test_parser_accepts_replay_and_gold_gate_options():
    import build_kb
    p = build_kb.build_parser()
    a = p.parse_args(["replay", "--task", "rich_4079", "--gold", "--force",
                      "--required-nodes", "hunk", "--deadline-s", "100", "--lock-wait-s", "5"])
    assert a.fn is build_kb.cmd_replay and a.gold and a.required_nodes == "hunk"
    a = p.parse_args(["replay", "--task", "t", "--run", "r/x", "--kind", "counterfactual"])
    assert a.run == "r/x" and a.kind == "counterfactual" and a.required_nodes == "added"
    a = p.parse_args(["replay", "--task", "t", "--candidate", "c.patch"])
    assert a.candidate == "c.patch"
    with pytest.raises(SystemExit):
        p.parse_args(["replay", "--task", "t", "--gold", "--run", "r"])   # exclusive
    a = p.parse_args(["gold-gate", "--repo", "rich", "--tasks", "rich_1", "rich_2",
                      "--deadline-s", "1750", "--required-nodes", "hunk"])
    assert a.fn is build_kb.cmd_gold_gate and a.tasks == ["rich_1", "rich_2"]
    a = p.parse_args(["build", "--replay", "--replay-scope", "min"])
    assert a.replay_scope == "min" and a.required_nodes == "added"
    assert p.parse_args(["build"]).replay_scope == "rich"


def _trow(run_id, task, kind, track, edits=1, trace=True):
    return {"run_id": run_id, "task": task, "run_kind": kind, "track": track,
            "trace": ({"edit_attempts": [{}] * edits} if trace else None),
            "outcome": {"patch_chars": 0}}


def test_replay_targets_tier_order_and_scopes():
    import build_kb
    rows = [_trow("z_rig", "rich_2", "local-rig", "dev-proxy"),
            _trow("b_kag", "rich_2", "kaggle-kernel", "small-model"),
            _trow("c_kag", "rich_1", "kaggle-kernel", "main"),
            _trow("a_kag", "rich_3", "kaggle-pulled", "main"),
            _trow("a_kag", "rich_4", "kaggle-kernel", "main", edits=0),   # no candidate
            _trow("s", "rich_1", "local-sweep", "dev-proxy", trace=False),  # never
            _trow("f_kag", "fastapi_1", "kaggle-kernel", "main"),
            _trow("m", "rich_9", "kaggle-kernel", "main")]
    rs = {"min_set": [{"run_id": "m", "task": "rich_9"}], "all_runs_rules": []}
    t = build_kb.replay_targets(rows, rs, "rich")
    assert t == [(0, "m", "rich_9"), (1, "a_kag", "rich_3"), (1, "c_kag", "rich_1"),
                 (2, "b_kag", "rich_2"), (3, "z_rig", "rich_2")]
    assert build_kb.replay_targets(rows, rs, "min") == [(0, "m", "rich_9")]
    assert (1, "f_kag", "fastapi_1") in build_kb.replay_targets(rows, rs, "all")


def test_goldcov_rows_and_gap(tmp_path, monkeypatch):
    from kblib import goldcov
    kb = tmp_path / "kb"
    (kb / "replays" / "gold").mkdir(parents=True)
    (kb / "replays" / "gold" / "rich_1.json").write_text(_json.dumps(
        {"gold_first": "INFRA", "reason": "required nodes skipped on this platform: x",
         "engine_version": replay.RP_VERSION, "required_mode": "added",
         "gold_pass_tests": ["a"], "pins": []}), encoding="utf-8")
    (kb / "replays" / "goldgate_all.json").write_text(_json.dumps(
        {"rich_1": {"gold_first": "INVALID"}}), encoding="utf-8")
    tg = {"tasks": {"rich_1": {"repo": "Textualize/rich", "tests": {"added_tests": [],
                                                                    "files": ["tests/test_x.py"]}},
                    "rich_2": {"repo": "Textualize/rich", "tests": {"added_tests": ["t"],
                                                                    "files": []}},
                    "fastapi_1": {"repo": "fastapi/fastapi", "tests": {"added_tests": ["t"],
                                                                        "files": []}}}}
    cov = goldcov.build(kb, tg, {"rich_1": {"test_patch": _TP_HUNK}}, replay.RP_VERSION)
    assert [r["task"] for r in cov["rows"]] == ["rich_1", "rich_2"]   # fastapi not attempted
    r1 = cov["rows"][0]
    assert r1["verdict"] == "INFRA" and r1["concordance"]["goldgate_all"] == "disagree"
    assert cov["rows"][1]["verdict"].startswith("not run")
    assert cov["whole_file_fallback"][0]["task"] == "rich_1"
    assert cov["whole_file_fallback"][0]["n_hunk_test_funcs_static"] >= 1
    lines = goldcov.render_lines(cov)
    assert any(l.startswith("### 13a.") for l in lines) and any(l.startswith("### 13b.") for l in lines)
