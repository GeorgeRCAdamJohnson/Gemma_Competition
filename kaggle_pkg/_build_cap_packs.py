"""Fork the known-good mobile packager (comfyops/gemma-submit-mobile-ca5, the 0.20 pack bytes) into
two CPU-only packager kernels that differ ONLY in eval_config.yaml.

  ca5 cap40/12  -> v7 cap-sim predicts 31/129 (~0.24)
  ca5 cap50/20  -> v7 cap-sim predicts 35/129 (~0.27)

Before writing anything, verifies the packager's agent/sampling/system bytes equal the v7 run's
agent_ca5 files (so the simulation applies to exactly these bytes).
"""
import copy, hashlib, json, re, sys
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "_src_mobile_ca5"
V7 = HERE.parent / "Outputs" / "v7_31b_full129" / "agentcfg" / "agent_ca5"

nb = json.loads((SRC / "gemma-submit-mobile-ca5.ipynb").read_text(encoding="utf-8"))
meta = json.loads((SRC / "kernel-metadata.json").read_text(encoding="utf-8"))
cell1 = "".join(nb["cells"][1]["source"])


def written(rel):
    """Execute the write_text literal for one file without touching disk."""
    pat = re.compile(r"\(AGENT_DIR(?: / '[^']+')+\)\.write_text\((.+?), encoding='utf-8', newline=''\)")
    for m in pat.finditer(cell1):
        parts = re.findall(r"'([^']+)'", m.group(0).split(".write_text")[0])
        if "/".join(parts) == rel:
            return eval(m.group(1))  # literal from our own packager source
    raise KeyError(rel)


def sha(b):
    return hashlib.sha256(b).hexdigest()[:12]


# 1. parity with v7
ok = True
for rel in ("agent.yaml", "configs/sampling.yaml", "prompts/system.md"):
    pk = written(rel).encode("utf-8")
    v7 = (V7 / rel).read_bytes()
    same = pk == v7
    ok &= same
    print(f"{rel:24s} packager {sha(pk)}  v7 {sha(v7)}  {'SAME' if same else 'DIFFERENT'}")
    if not same:
        print("   packager:", pk[:300]); print("   v7      :", v7[:300])
old_eval = written("eval_config.yaml")
print("eval_config (board pack):", repr(old_eval))
if not ok:
    sys.exit("ABORT: packager bytes differ from the v7 agent - simulation would not apply")

# 2. two forks
import os as _os
# PACKS env: comma list of tags to build (default: the original two cap packs). bc = the validated 31B B+C pack.
ALL_ARMS = {
    "cap40-12": (40, 12, 120, 300),
    "cap50-20": (50, 20, 120, 300),
    "bc-time10-cmd60": (28, 10, 120, 60),   # ca5-31b-timeout-ab C+B, regression-checked in ca5-31b-bc-check
}
ARMS = {t: ALL_ARMS[t] for t in _os.environ.get("PACKS", "cap40-12,cap50-20").split(",")}
for tag, (calls, mins, turns, cmd_to) in ARMS.items():
    new_eval = (f"evaluation:\n  max_time_minutes: {mins}\n  max_tool_calls: {calls}\n"
                f"  max_turns: {turns}\n  timeout_seconds: {cmd_to}\n")
    assert old_eval in cell1 or repr(old_eval)[1:-1] in cell1
    lit_old = repr(old_eval)
    assert lit_old in cell1, "eval literal not found verbatim"
    new_cell1 = cell1.replace(lit_old, repr(new_eval), 1)
    # only diff vs source must be the eval literal
    assert new_cell1.replace(repr(new_eval), lit_old, 1) == cell1
    n2 = copy.deepcopy(nb)
    n2["cells"][1]["source"] = new_cell1.splitlines(keepends=True)
    n2["cells"][0]["source"] = (
        f"# ca5 {tag}: board 0.20 pack bytes, ONLY eval_config changed to {calls} calls / {mins} min / "
        f"{turns} turns.\n" + "".join(nb["cells"][0]["source"]).split("\n", 1)[1]
    ).splitlines(keepends=True)
    for c in n2["cells"]:
        c["outputs"] = []; c["execution_count"] = None
    slug = f"gemma-submit-ca5-{tag}"
    out = HERE / f"push_{slug.replace('-', '_')}"
    out.mkdir(exist_ok=True)
    (out / f"{slug}.ipynb").write_text(json.dumps(n2, indent=1), encoding="utf-8")
    m2 = {k: v for k, v in meta.items() if k not in ("id_no",)}
    m2.update(id=f"comfyops/{slug}", title=f"Gemma submit ca5 {tag}", code_file=f"{slug}.ipynb")
    assert m2["competition_sources"] == ["gemma-4-developer-agent"] and not m2["enable_gpu"]
    (out / "kernel-metadata.json").write_text(json.dumps(m2, indent=2), encoding="utf-8")
    print(f"built {out.name}: eval sha {sha(new_eval.encode())} | {new_eval!r}")
