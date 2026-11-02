"""CPU-only: how often do run_command commands mention /workspace (real traces vs local runs)?  python atif_cmd_workspace.py"""
import collections, json, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

real = collections.Counter()
ex = []
for p in sorted(ROOT.glob("**/trace_rich_*.json")):
    if any(x in p.parts for x in ("local_eval", ".train_env", "repos", "node_modules")):
        continue
    t = json.loads(p.read_text(encoding="utf-8"))
    for s in t.get("steps", []):
        if s.get("source") != "agent":
            continue
        for c in s.get("tool_calls") or []:
            if c.get("function_name") != "run_command":
                continue
            cmd = (c.get("arguments") or {}).get("command") or ""
            real["run_command"] += 1
            if "/workspace" in cmd:
                real["mentions_/workspace"] += 1
                if re.search(r"(^|[;&|]\s*)cd\s+/workspace", cmd):
                    real["cd_/workspace"] += 1
                if len(ex) < 6:
                    ex.append(cmd[:140])
            if re.search(r"(^|\s)/tmp/", cmd):
                real["mentions_/tmp"] += 1
print("REAL traces:", dict(real))
for e in ex:
    print("   e.g.", repr(e))

loc = collections.Counter()
lex = []
for p in sorted((ROOT / "local_eval" / "runs").glob("*.trace.jsonl")):
    if p.name.startswith("k_"):
        continue
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("kind") == "tool" and r.get("tool") == "run_command":
            loc["run_command"] += 1
            h = r.get("args_head") or ""
            if "/workspace" in h:
                loc["mentions_/workspace"] += 1
                loc["  status=" + str(r.get("status"))] += 1
                if len(lex) < 6:
                    lex.append((p.name, h[:140], r.get("status")))
            if "/tmp/" in h:
                loc["mentions_/tmp"] += 1
print("LOCAL traces:", dict(loc))
for e in lex:
    print("   e.g.", e)
