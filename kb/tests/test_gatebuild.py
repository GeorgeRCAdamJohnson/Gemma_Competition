"""REV5 D5-26 gate-build / gate-check (synthetic GKB_GEMMA_ROOT trees only)."""
import ast
import json
import pathlib

import pytest

import build_kb
from kblib import gatebuild

_ASSEMBLE = (
    "import json, os\n"
    "HERE = os.path.dirname(os.path.abspath(__file__))\n"
    "src = open(os.path.join(HERE, 'notebook_src.py'), encoding='utf-8').read()\n"
    "compile(src, 'notebook_src.py', 'exec')\n"
    "json.dump({'cells': [{'source': src}]}, open(os.path.join(HERE, 'gate.ipynb'), 'w'))\n"
    "print('assembled')\n")
_GOLD_LINE = "return self._render_the_unique_gold_line(value)"


def _tree(tmp_path, monkeypatch, verdict="PROCEED", bar=True):
    g = tmp_path / "Gemma"
    (g / "comp_files").mkdir(parents=True)
    rec = {"instance_id": "rich_9001", "repo": "Textualize/rich",
           "problem_statement": "Synthetic problem title for tests\nbody",
           "patch": f"--- a/x.py\n+++ b/x.py\n+    {_GOLD_LINE}\n"}
    (g / "comp_files" / "tasks.jsonl").write_text(json.dumps(rec) + "\n", encoding="utf-8")
    base = g / "submit_base"
    (base / "out_run").mkdir(parents=True)
    (base / "out_run" / "trace.json").write_text("{}", encoding="utf-8")
    (base / "prompts").mkdir()
    (base / "prompts" / "system.md").write_text("Be careful. Edit the file.\n", encoding="utf-8")
    (base / "kernel-metadata.json").write_text(json.dumps(
        {"id": "comfyops/gemma-sibling-conform-base", "title": "Base", "code_file": "gate.ipynb"},
        indent=2), encoding="utf-8")
    (base / "notebook_src.py").write_text(
        "SAMPLE_IDS = ['rich_9001']\nTEMPERATURE = 0.2\nprint(TEMPERATURE)\n", encoding="utf-8")
    (base / "_assemble.py").write_text(_ASSEMBLE, encoding="utf-8")
    (base / "gate.ipynb").write_text("{}", encoding="utf-8")
    (base / "old.zip").write_bytes(b"PK")
    audits = g / "kb" / "audits"
    audits.mkdir(parents=True)
    aj = {"schema": "gemma-audit/1", "mode": "AUDIT", "verdict": verdict}
    if bar:
        aj["bar"] = {"change": "temperature 0.2 -> 0.0", "task_set": [
            {"task": "rich_9001", "class": "EASY"}], "pass": ">= 1/1", "fail": "0/1",
            "mechanism_check": "first edit lands"}
    audit = audits / "2026-10-31-temp-zero.md"
    audit.write_text(f"VERDICT: {verdict}\n# audit\n<!-- AUDIT-JSON\n{json.dumps(aj)}\n-->\n",
                     encoding="utf-8")
    final = audits / "2026-10-31-temp-zero-final.md"
    final.write_text(f"VERDICT: {verdict}\n# Final\n- Pass 1 (AUDIT): {verdict} — {audit}\n",
                     encoding="utf-8")
    spec = tmp_path / "spec.json"
    spec.write_text(json.dumps({"variable": "sampling.temperature", "changes": [
        {"file": "notebook_src.py", "old": "TEMPERATURE = 0.2", "new": "TEMPERATURE = 0.0"}]}),
        encoding="utf-8")
    monkeypatch.setenv("GKB_GEMMA_ROOT", str(g))
    return g, base, final, spec


def _mtimes(d):
    return {p.relative_to(d).as_posix(): p.stat().st_mtime_ns for p in sorted(d.rglob("*"))}


def test_gate_build_and_check_happy_path(tmp_path, monkeypatch):
    g, base, final, spec = _tree(tmp_path, monkeypatch)
    before = _mtimes(base)
    calls = []
    real_run = gatebuild.subprocess.run

    def spy(argv, *a, **k):
        calls.append([str(x) for x in argv])
        return real_run(argv, *a, **k)
    monkeypatch.setattr(gatebuild.subprocess, "run", spy)
    rc = build_kb.main(["gate-build", "--audit", str(final), "--base", "submit_base",
                        "--name", "temp_zero", "--change-spec", str(spec)])
    assert rc == 0
    d = g / "submit_temp_zero"
    man = json.loads((d / "GATE_MANIFEST.json").read_text(encoding="utf-8"))
    assert man["kernel_id"] == "comfyops/gemma-gate-temp-zero"
    assert man["base"] == "submit_base" and "notebook_src.py" in man["base_file_sha256"]
    km = json.loads((d / "kernel-metadata.json").read_text(encoding="utf-8"))
    assert km["id"] == "comfyops/gemma-gate-temp-zero"
    assert "TEMPERATURE = 0.0" in (d / "notebook_src.py").read_text(encoding="utf-8")
    assert not (d / "out_run").exists() and not (d / "old.zip").exists()
    pre = (d / "GATE_PREREG.md").read_text(encoding="utf-8")
    assert "sampling.temperature" in pre and ">= 1/1" in pre and "FREE Kaggle" in pre
    assert "kernels push" in pre
    assert gatebuild.check_gate(d)[0] is True
    assert build_kb.main(["gate-check", "--dir", str(d)]) == 0
    assert (d / "gate.ipynb").read_text(encoding="utf-8") != "{}"  # assembled
    assert _mtimes(base) == before
    # (the workspace path itself contains "kAGGLE", so check the program + tokens)
    assert calls and all(pathlib.Path(c[0]).name.lower().startswith("python")
                         and c[1:] == ["_assemble.py"] for c in calls)


def test_refuses_non_proceed_and_missing_bar(tmp_path, monkeypatch):
    g, base, final, spec = _tree(tmp_path, monkeypatch, verdict="REVISE")
    with pytest.raises(gatebuild.GateError, match="not 'VERDICT: PROCEED'"):
        gatebuild.build_gate(final, "submit_base", "temp_zero", spec)
    assert not (g / "submit_temp_zero").exists()
    assert build_kb.main(["gate-build", "--audit", str(final), "--base", "submit_base",
                          "--name", "temp_zero", "--change-spec", str(spec)]) == 1
    # a single PROCEED pass report is not the final report
    with pytest.raises(gatebuild.GateError, match="FINAL"):
        gatebuild.build_gate(final.with_name("2026-10-31-temp-zero.md"), "submit_base",
                             "temp_zero", spec)


def test_refuses_proceed_without_bar(tmp_path, monkeypatch):
    g, base, final, spec = _tree(tmp_path, monkeypatch, bar=False)
    with pytest.raises(gatebuild.GateError, match="bar"):
        gatebuild.build_gate(final, "submit_base", "temp_zero", spec)
    assert not (g / "submit_temp_zero").exists()


def test_refuses_existing_target_and_bad_name(tmp_path, monkeypatch):
    g, base, final, spec = _tree(tmp_path, monkeypatch)
    (g / "submit_temp_zero").mkdir()
    (g / "submit_temp_zero" / "keep.txt").write_text("user", encoding="utf-8")
    with pytest.raises(gatebuild.GateError, match="target exists"):
        gatebuild.build_gate(final, "submit_base", "temp_zero", spec)
    assert (g / "submit_temp_zero" / "keep.txt").read_text(encoding="utf-8") == "user"
    for bad in ("Temp", "x", "a-b", "../x", "a" * 50):
        with pytest.raises(gatebuild.GateError, match="bad --name"):
            gatebuild.build_gate(final, "submit_base", bad, spec)


def test_refuses_kernel_id_collision(tmp_path, monkeypatch):
    g, base, final, spec = _tree(tmp_path, monkeypatch)
    other = g / "push_other"
    other.mkdir()
    (other / "kernel-metadata.json").write_text(
        json.dumps({"id": "comfyops/gemma-gate-temp-zero"}), encoding="utf-8")
    with pytest.raises(gatebuild.GateError, match="already exists locally"):
        gatebuild.build_gate(final, "submit_base", "temp_zero", spec)
    assert not (g / "submit_temp_zero").exists()


def test_refuses_bad_specs_and_cleans_up(tmp_path, monkeypatch):
    g, base, final, spec = _tree(tmp_path, monkeypatch)
    bad = tmp_path / "bad.json"
    for body, msg in [
        ({"changes": [{"file": "notebook_src.py", "old": "a", "new": "b"}]}, "variable"),
        ({"variable": "v", "changes": [{"file": "notebook_src.py", "old": "a", "new": "b",
                                        "variable": "other"}]}, "single-variable"),
        ({"variable": "v", "changes": [{"file": "../x.py", "old": "a", "new": "b"}]}, "relative"),
        ({"variable": "v", "changes": [{"file": "notebook_src.py", "old": "E", "new": "e"}]},
         "need exactly 1"),
    ]:
        bad.write_text(json.dumps(body), encoding="utf-8")
        with pytest.raises(gatebuild.GateError, match=msg):
            gatebuild.build_gate(final, "submit_base", "temp_zero", bad)
        assert not (g / "submit_temp_zero").exists()  # partial dir removed by the guard


def test_gate_check_fails_on_undeclared_change_and_leak(tmp_path, monkeypatch):
    g, base, final, spec = _tree(tmp_path, monkeypatch)
    r = gatebuild.build_gate(final, "submit_base", "temp_zero", spec)
    d = pathlib.Path(r["dir"])
    (d / "prompts" / "system.md").write_text("Be careful.\n", encoding="utf-8")
    ok, lines = gatebuild.check_gate(d)
    assert not ok and any(l.startswith("FAIL changed files") and "prompts/system.md" in l
                          for l in lines)
    assert build_kb.main(["gate-check", "--dir", str(d)]) == 1
    # a gold line / task id introduced by the change text fails the leakcheck
    g2 = tmp_path / "two"
    g2.mkdir()
    g, base, final, spec = _tree(g2, monkeypatch)
    spec.write_text(json.dumps({"variable": "sampling.temperature", "changes": [
        {"file": "notebook_src.py", "old": "TEMPERATURE = 0.2",
         "new": f"TEMPERATURE = 0.0  # rich_9001 {_GOLD_LINE}"}]}), encoding="utf-8")
    d = pathlib.Path(gatebuild.build_gate(final, "submit_base", "temp_zero", spec)["dir"])
    ok, lines = gatebuild.check_gate(d)
    leak_line = [l for l in lines if "leakcheck" in l][0]
    assert not ok and leak_line.startswith("FAIL") and "gold_line" in leak_line \
        and "task_id" in leak_line


def test_gate_check_detects_base_change(tmp_path, monkeypatch):
    g, base, final, spec = _tree(tmp_path, monkeypatch)
    d = pathlib.Path(gatebuild.build_gate(final, "submit_base", "temp_zero", spec)["dir"])
    (base / "notebook_src.py").write_text("changed\n", encoding="utf-8")
    ok, lines = gatebuild.check_gate(d)
    assert not ok and any(l.startswith("FAIL base") for l in lines)


def test_write_guard_refuses_outside_paths(tmp_path, monkeypatch):
    g, base, final, spec = _tree(tmp_path, monkeypatch)
    guard = gatebuild._Guard(g)
    with pytest.raises(gatebuild.GateError):
        guard.write(base / "notebook_src.py", "x")
    with pytest.raises(gatebuild.GateError):
        guard.adopt_created(g / "kb")


def test_gatebuild_source_never_runs_kaggle():
    src = pathlib.Path(gatebuild.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    n_sub = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert "kaggle" not in [a.name for a in node.names]
            assert node.module not in ("kblib.kaggle", "kaggle")
        if isinstance(node, ast.Import):
            assert all("kaggle" not in a.name for a in node.names)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
            n_sub += 1
            consts = [c.value for c in ast.walk(node) if isinstance(c, ast.Constant)
                      and isinstance(c.value, str)]
            assert all("kaggle" not in c.lower() for c in consts), consts
            assert all(not (isinstance(a, ast.Name) and a.id in ("exe", "push"))
                       for a in ast.walk(node))
        if isinstance(node, (ast.List, ast.Tuple)):
            consts = {e.value for e in node.elts
                      if isinstance(e, ast.Constant) and isinstance(e.value, str)}
            assert not ({"kernels", "push"} <= consts)
    assert n_sub == 1  # only `python _assemble.py`
    assert "os.system" not in src and "Popen" not in src
