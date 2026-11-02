import json, re, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
for rep in ("r4", "r11", "r2"):
    p = RIG / "m1_batch_multi" / "off12" / rep / "traces" / "trace_rich_4077.json"
    if not p.exists():
        continue
    j = json.loads(re.sub(r"\x1b\[[0-9;]*m", "", p.read_text(encoding="utf-8")))
    print("=" * 100)
    print(f"{rep}  RAW edit_file failures")
    shown = 0
    for s in j["steps"]:
        for tc in (s.get("tool_calls") or []):
            if tc.get("function_name") != "edit_file":
                continue
            obs = s.get("observation") or {}
            c = obs.get("content") if isinstance(obs, dict) else obs
            try:
                oj = json.loads(c) if isinstance(c, str) else c
            except Exception:
                oj = {"raw": str(c)[:400]}
            st = (oj or {}).get("status")
            args = tc.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            if st == "ok":
                continue
            shown += 1
            print(f"\n--- fail #{shown} step {s.get('step_id')} ---")
            print("ARG KEYS:", list(args.keys()))
            print("PATH FIELD:", {k: v for k, v in args.items() if "file" in k.lower() or "path" in k.lower()})
            o = args.get("old_string") or ""
            n = args.get("new_string") or ""
            print(f"OLD ({len(o)}b) repr: {o!r}")
            print(f"NEW ({len(n)}b) repr: {n!r}")
            print("OBS FULL:", json.dumps(oj)[:900])
            if shown >= 4:
                break
        if shown >= 4:
            break
