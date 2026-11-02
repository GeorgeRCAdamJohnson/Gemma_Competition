"""Summarize a _skilltest run dir: per task, tool sequence (from steps[].tool_calls), submit attempts, nudges, outcome."""
import json
import sys
from pathlib import Path

d = Path(__file__).resolve().parent / "m1_skilltest" / sys.argv[1]
rows = {json.loads(l)["instance_id"]: json.loads(l)
        for l in (d / "task_results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
for t, r in rows.items():
    tr = d / "traces" / f"trace_{t}.json"
    seq, sub_attempts, sub_errs, nudges, skill = [], 0, 0, 0, []
    if tr.exists():
        j = json.loads(tr.read_text(encoding="utf-8"))
        for s in j.get("steps", []):
            src = s.get("source")
            msg = str(s.get("message") or "")
            if src in ("harness", "user") and "Please continue your work" in msg:
                nudges += 1
            for c in s.get("tool_calls") or []:
                n = c.get("function_name")
                seq.append(n)
                if n == "submit_patch":
                    sub_attempts += 1
                if n == "run_skill_script":
                    skill.append((c.get("arguments") or {}))
            obs = json.dumps(s.get("observation") or {})
            if "submit_patch" in obs and ("not found" in obs.lower() or "error" in obs.lower()):
                sub_errs += 1
    print(f"{t}: resolved={r['resolved']} patch={r.get('agent_patch_size')} tool_calls={r.get('tool_calls')} "
          f"llm={r.get('total_llm_calls')} dur={r.get('duration_seconds')}s err={str(r.get('error') or '')[:80]}")
    print(f"   submit_patch attempts={sub_attempts} (error obs mentioning it={sub_errs}) nudges~={nudges} skill_calls={len(skill)}")
    print(f"   seq={seq}")
    for a in skill[:6]:
        print(f"   skill args={json.dumps(a)[:160]}")
