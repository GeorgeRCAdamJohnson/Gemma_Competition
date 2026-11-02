"""Compile-only parity check: run the REAL adk_submission compiler over an agent dir.

No model, no tasks, no GPU. Catches config crashes (missing keys, bad config_path,
!include resolution, adapter requirements, sub-agent nesting) BEFORE a submission slot
or a quota-hour is spent. Usage inside the container:
    python compile_check.py <submission_dir> [<submission_dir> ...]
"""
import sys
import traceback
from pathlib import Path

from adk_submission import ToolRegistry, ModelRegistry, compile_submission


def _stub(name):
    def f(**kwargs):
        return {"status": "ok", "stub": name, "args": sorted(kwargs)}

    f.__name__ = name
    f.__qualname__ = name
    return f


HARNESS_TOOLS = [
    "run_command",
    "read_file",
    "edit_file",
    "write_file",
    "get_status",
    "submit_patch",
    "get_code_neighbors",
    "search_similar_code",
    "get_code_subgraph",
]

MODEL_NAME = "gemma-4-31b-it-qat-w4a16-ct"
OFFICIAL_MODELS = ["gemma-4-31b-it-qat-w4a16-ct", "gemma-4-12b-it-qat-w4a16-ct",
                   "gemma-4-e4b-it-qat-w4a16-ct", "gemma-4-e2b-it-qat-w4a16-ct"]


def walk(agent, depth=0, out=None):
    if out is None:
        out = []
    cls = type(agent).__name__
    name = getattr(agent, "name", "?")
    tools = []
    for t in getattr(agent, "tools", None) or []:
        tname = type(t).__name__
        inner = getattr(t, "agent", None)
        if inner is not None:
            tname += ":" + type(inner).__name__
        tools.append(tname)
    out.append("  " * depth + "%s(%s) tools=%s" % (cls, name, tools))
    for attr in ("sub_agents", "_sub_agents", "contents"):
        subs = getattr(agent, attr, None)
        if isinstance(subs, (list, tuple)):
            for s in subs:
                if hasattr(s, "tools") or hasattr(s, "_sub_agents"):
                    walk(s, depth + 1, out)
    return out


def check(subdir: Path) -> bool:
    print("=" * 70)
    print("COMPILING:", subdir)
    if not (subdir / "agent.yaml").is_file():
        print("  FAIL: no agent.yaml")
        return False
    tools = ToolRegistry()
    for n in HARNESS_TOOLS:
        tools.register(n, _stub(n))
    models = ModelRegistry()
    for m in OFFICIAL_MODELS:
        models.register(m, "openai/" + m)
    models.register("adapter:main_lora", "openai/" + MODEL_NAME)
    models.register("adapter:tool_lora", "openai/" + MODEL_NAME)
    adapter_manifest = None
    try:
        from adk_submission import discover_adapters
        adapter_manifest = discover_adapters(str(subdir))
        found = getattr(adapter_manifest, "adapters", {}) or {}
        print(f"  ADAPTERS DISCOVERED: {len(found)} -> {sorted(found)}")
        for nm, info in found.items():
            print(f"    {nm}: format={getattr(info, 'format', '?')} path={getattr(info, 'path', '?')}")
    except Exception:
        print("  ADAPTER DISCOVERY FAILED:")
        traceback.print_exc(limit=4)
        return False
    try:
        agent = compile_submission(
            submission_dir=str(subdir),
            tool_registry=tools,
            model_registry=models,
            adapter_manifest=adapter_manifest,
        )
    except Exception:
        print("  COMPILE FAILED:")
        traceback.print_exc(limit=6)
        return False
    print("  COMPILE OK ->", type(agent).__name__, "name=", getattr(agent, "name", "?"))
    for line in walk(agent):
        print("   ", line)
    return True


def main():
    ok = True
    for a in sys.argv[1:]:
        ok = check(Path(a)) and ok
    print("=" * 70)
    print("RESULT:", "ALL OK" if ok else "FAILURES PRESENT")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
