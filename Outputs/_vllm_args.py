# Distinct values of reasoning_config / scheduler_reserve_full_isl across vLLM servers (from non-default args).
import re
import sqlite3

db = sqlite3.connect("kb/attempts.sqlite")
seen = {}
for exp, a in db.execute("SELECT exp, args_text FROM vllm_servers"):
    rc = re.search(r"'reasoning_config': (\w+\([^)]*\)|\{[^}]*\})", a or "")
    sr = re.search(r"'scheduler_reserve_full_isl': (\w+)", a or "")
    k = (rc.group(1) if rc else None, sr.group(1) if sr else None)
    seen.setdefault(k, []).append(exp)
for k, exps in seen.items():
    print(k, "->", sorted(set(exps))[:4], f"({len(exps)} servers)")
