"""Static lint for the gemma-audit workflow recipe (design §19.1)."""
import json
import pathlib
import re

ROOT = pathlib.Path(r"c:\Users\Biges\OneDrive\Documents\Desktop\kAGGLE")
RECIPE = ROOT / ".kiro" / "workflows" / "gemma-audit.workflow.json"
AGENT = ROOT / ".kiro" / "agents" / "gemma-auditor.md"

_REF = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_MODELS = {"claude-opus-5", "gpt-5.6-sol", "claude-fable-5"}
_FAMILY = {"claude-opus-5": "claude", "claude-fable-5": "claude", "gpt-5.6-sol": "gpt"}


def _load():
    return json.loads(RECIPE.read_text(encoding="utf-8"))


def test_parses_and_top_level_keys():
    r = _load()
    assert set(r.keys()) == {"name", "description", "inputs", "steps"}
    assert r["inputs"] == {"proposal_path": "file", "slug": "string"}


def test_steps_shape_and_ids():
    r = _load()
    ids = [s["id"] for s in r["steps"]]
    assert ids == ["rebuild-kb", "audit", "refute", "final"]
    assert len(set(ids)) == 4
    for s in r["steps"]:
        assert {"type", "id", "agent", "prompt"} <= set(s)
        assert s["type"] == "step"
        assert "input" not in s


def test_agents_and_models():
    r = _load()
    by = {s["id"]: s for s in r["steps"]}
    assert by["rebuild-kb"]["agent"] == "wf-coder"
    assert by["audit"]["agent"] == "gemma-auditor"
    assert by["refute"]["agent"] == "gemma-auditor"
    assert by["final"]["agent"] == "wf-coder"
    assert by["audit"]["modelId"] in _MODELS
    assert by["refute"]["modelId"] in _MODELS
    assert _FAMILY[by["audit"]["modelId"]] != _FAMILY[by["refute"]["modelId"]]
    assert AGENT.is_file()
    fm = AGENT.read_text(encoding="utf-8").split("---")[1]
    assert "write" in fm or "shell" in fm


def test_template_references():
    r = _load()
    steps = r["steps"]
    seen_ids = set()
    declared_artifacts = set()
    inputs = set(r["inputs"])
    for s in steps:
        # prompt references
        texts = [s["prompt"]] + list((s.get("artifacts") or {}).values())
        for t in texts:
            for ref in _REF.findall(t):
                if ref.endswith(".output"):
                    rid = ref[: -len(".output")]
                    assert rid in seen_ids, f"{ref} not an earlier step"
                elif ref.startswith("artifacts."):
                    name = ref[len("artifacts."):]
                    assert name in declared_artifacts, f"{ref} not declared earlier"
                else:
                    assert ref in inputs, f"bare {ref} not an input"
        # a step cannot reference its own artifact in its prompt
        own = set((s.get("artifacts") or {}).keys())
        for ref in _REF.findall(s["prompt"]):
            if ref.startswith("artifacts."):
                assert ref[len("artifacts."):] not in own
        seen_ids.add(s["id"])
        declared_artifacts |= own


def test_p1_flags_and_p2_unwrap():
    r = _load()
    by = {s["id"]: s for s in r["steps"]}
    p1 = by["rebuild-kb"]["prompt"]
    assert "--deadline-s 1500" in p1 and "--lock-wait-s 120" in p1
    p2 = by["audit"]["prompt"]
    assert "{{rebuild-kb.output}}" in p2
    assert "wrapped" in p2 and "ignore the tags" in p2


def test_artifact_keys():
    r = _load()
    by = {s["id"]: s for s in r["steps"]}
    assert "audit_report" in by["audit"]["artifacts"]
    assert "refute_report" in by["refute"]["artifacts"]
    assert "final_report" in by["final"]["artifacts"]
