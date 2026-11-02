"""Reconstruct what each packager actually writes, by executing its writer cells.

The packagers build the agent dir from embedded strings, so running them reproduces
the shipped bytes exactly. Nothing is written outside the temp dirs.
"""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTEBOOKS = [
    ("original", ROOT / "local_eval/push_packager/gemma-submission-packager.ipynb"),
    ("a25", ROOT / "local_eval/push_packager_a25/gemma-submission-packager-a25.ipynb"),
    ("ca5", ROOT / "local_eval/push_packager_ca5/gemma-submission-packager-ca5.ipynb"),
]

import yaml


class T(yaml.SafeLoader):
    pass


def _any(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    return loader.construct_mapping(node)


T.add_multi_constructor('', _any)

for label, nb_path in NOTEBOOKS:
    print("=" * 78)
    print("PACKAGER:", label, "|", nb_path.name)
    if not nb_path.exists():
        print("  MISSING")
        continue
    nb = json.loads(nb_path.read_text(encoding="utf-8", errors="replace"))
    work = Path(tempfile.mkdtemp(prefix="pk_%s_" % label))
    sub = work / "submission"
    sub.mkdir(parents=True, exist_ok=True)

    # execute only cells that write files, with paths redirected
    ran = 0
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        src = "".join(cell.get("source", []))
        if "AGENT_DIR" not in src or "write_text" not in src and "write_bytes" not in src:
            continue
        rendered = (src.replace("/kaggle/working/submission", str(sub).replace("\\", "/"))
                    .replace("/kaggle/working", str(work).replace("\\", "/")))
        try:
            exec(compile(rendered, "cell", "exec"), {"__name__": "__main__"})
            ran += 1
        except Exception as e:
            print("   [cell skipped] %s: %s" % (type(e).__name__, str(e)[:90]))
    if ran == 0:
        print("   (no writer cells executed)")
        continue

    files = sorted(p for p in sub.rglob("*") if p.is_file())
    total = sum(p.stat().st_size for p in files)
    print("   files: %d | total %d B" % (len(files), total))
    for p in files:
        rel = str(p.relative_to(sub)).replace("\\", "/")
        print("     %-32s %8d B  sha256 %s"
              % (rel, p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()[:12]))

    for name in ("agent.yaml", "eval_config.yaml", "configs/sampling.yaml"):
        p = sub / name
        if p.exists():
            try:
                d = yaml.load(p.read_text(encoding="utf-8"), Loader=T) or {}
                if name == "agent.yaml":
                    print("   declared model: %s | name: %s" % (d.get("model"), d.get("name")))
                    print("   agent keys    : %s" % sorted(d.keys()))
                    ag_txt = p.read_text(encoding="utf-8")
                    print("   has agent_tool: %s | has sub_agents: %s"
                          % ("agent_tool" in ag_txt, "sub_agents" in ag_txt))
                elif name == "eval_config.yaml":
                    ev = d.get("evaluation", d)
                    print("   caps          : %s" % {k: ev.get(k) for k in
                                                     ("max_tool_calls", "max_time_minutes",
                                                      "max_turns", "timeout_seconds")})
                else:
                    print("   sampling      : %s" % d)
            except Exception as e:
                print("   [%s parse] %s" % (name, str(e)[:80]))

    pm = sub / "prompts" / "system.md"
    if pm.exists():
        b = pm.read_bytes()
        print("   prompt        : %d B  sha1 %s  sha256 %s"
              % (len(b), hashlib.sha1(b).hexdigest()[:12], hashlib.sha256(b).hexdigest()[:12]))
    for extra in sorted(sub.rglob("system*.md")):
        if extra.name != "system.md":
            print("   EXTRA PROMPT  : %s (%d B)" % (extra.name, extra.stat().st_size))
    shutil.rmtree(work, ignore_errors=True)
