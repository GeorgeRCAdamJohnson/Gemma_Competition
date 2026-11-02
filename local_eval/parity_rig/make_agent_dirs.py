"""Materialize the two agent dirs the A25 test compares, LOCALLY, byte-identically to
what cell1_a25.py writes on Kaggle:
  agent_ctrl   <- copy of the shipped v10 submission dir (pull_31ba3hard_out/submission)
  agent_router <- same dir + agent_tool entries + sub_agents/*.yaml + step-1 prompt span
Configs are extracted from kern_src/_a25_router_tail.py (single source of truth shared
with the arm-test kernel and the packager).
"""
import re
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
LE = Path(__file__).resolve().parent.parent
RIG = LE / "parity_rig"
TAIL = (LE / "kern_src" / "_a25_router_tail.py").read_text(encoding="utf-8")


def extract(marker, text):
    m = re.search(re.escape(marker) + r"'''(.*?)'''", text, re.S)
    assert m, "extract failed: " + marker
    return m.group(1)


def main():
    src = LE / "pull_31ba3hard_out" / "submission"
    assert (src / "agent.yaml").is_file(), src

    ctrl = RIG / "agent_ctrl"
    router = RIG / "agent_router"
    for d in (ctrl, router):
        if d.exists():
            shutil.rmtree(d)
        shutil.copytree(src, d)

    # router: sub_agents + modified agent.yaml + prompt span
    (router / "sub_agents").mkdir(exist_ok=True)
    (router / "sub_agents" / "locator.yaml").write_text(
        extract("(AGENT_DIR_R / 'sub_agents' / 'locator.yaml').write_text(", TAIL), encoding="utf-8")
    (router / "sub_agents" / "logic.yaml").write_text(
        extract("(AGENT_DIR_R / 'sub_agents' / 'logic.yaml').write_text(", TAIL), encoding="utf-8")
    (router / "agent.yaml").write_text(
        extract("(AGENT_DIR_R / 'agent.yaml').write_text(", TAIL), encoding="utf-8")

    step1_old = re.search(r'_step1_old = """(.*?)"""', TAIL, re.S).group(1)
    step1_new = re.search(r'_step1_new = """(.*?)"""', TAIL, re.S).group(1)
    shipped = (src / "prompts" / "system.md").read_text(encoding="utf-8")
    assert shipped.count(step1_old) == 1, "anchor count %d" % shipped.count(step1_old)
    rt = shipped.replace(step1_old, step1_new, 1)
    assert rt.replace(step1_new, step1_old, 1) == shipped, "not reversible"
    (router / "prompts" / "system.md").write_text(rt, encoding="utf-8")
    # keep the arm files too, mirroring the kernel layout
    (router / "prompts" / "system_router.md").write_text(rt, encoding="utf-8")
    (ctrl / "prompts" / "system_a3.md").write_text(shipped, encoding="utf-8")

    for name, d in (("ctrl", ctrl), ("router", router)):
        files = sorted(str(p.relative_to(d)) for p in d.rglob("*") if p.is_file())
        print("%s: %d files %s" % (name, len(files), files))


if __name__ == "__main__":
    main()
