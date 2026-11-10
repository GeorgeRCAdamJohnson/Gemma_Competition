"""Did any agent in our traces call a tool it did not declare, and what happened next (crash vs error response)?
Verifier declares: get_status, submit_patch + skill tools (load_skill, run_skill_script, ...).
Fixer declares: run_command, read_file, edit_file, write_file, get_status, get_code_neighbors, search_similar_code,
get_code_subgraph. Searches every E4B pack-1 log and the 31B ca5 archives."""
import json
import re
import tarfile
from collections import Counter
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;]*m")
VER_OK = {"get_status", "submit_patch", "load_skill", "run_skill_script", "load_skill_resource", "list_skills"}
FIX_OK = {"run_command", "read_file", "edit_file", "write_file", "get_status", "get_code_neighbors",
          "search_similar_code", "get_code_subgraph"}
ev = re.compile(r"\]\s+\S+\s+([a-z_]+)\b")
hits = Counter()
examples = []
for lp in Path("Outputs/e4b_pack1_val/results").glob("node*/run_*/logs/*.log"):
    t = ANSI.sub("", lp.read_text(encoding="utf-8", errors="replace")).splitlines()
    rows = {json.loads(l)["instance_id"]: json.loads(l) for l in (lp.parent.parent / "task_results.jsonl").read_text().splitlines() if l.strip()}
    r = rows.get(lp.stem, {})
    for i, ln in enumerate(t):
        is_ver = "(verifier)" in ln
        m = ev.search(ln.replace("\u2502 (verifier) ", ""))
        if not m:
            continue
        tool = m.group(1)
        if tool in ("agent", "task", "system") or not re.search(r"\]\s+\S+\s+" + tool + r"(\s|$|\s*\{|\s*\()", ln.replace("\u2502 (verifier) ", "")):
            continue
        allowed = VER_OK if is_ver else FIX_OK | {"exit_loop"}
        known = VER_OK | FIX_OK | {"exit_loop", "transfer_to_agent"}
        if tool not in allowed and (tool in known or tool.endswith("_file") or tool.startswith(("get_", "run_", "search_"))):
            hits[(("verifier" if is_ver else "fixer"), tool)] += 1
            if len(examples) < 6:
                examples.append((lp.parent.parent.parent.name + "/" + lp.parent.parent.name, lp.stem, ln.strip()[:110],
                                 (t[i + 1].strip()[:150] if i + 1 < len(t) else ""), r.get("resolved"), str(r.get("error"))[:80]))
print("undeclared calls in E4B pack-1 logs:", dict(hits))
for e in examples:
    print("  ", e)
