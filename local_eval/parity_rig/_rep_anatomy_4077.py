"""Per-rep outcome anatomy for rich_4077: target file, edit verdict, whether an isatty
method was added to FileProxy (the gold shape), submit?, resolved?, patch size."""
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
import os
ARM = os.environ.get("M1_ARM", "off12")
TASK = "rich_4077"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
GOLD_FILE = "rich/file_proxy.py"


def main():
    reps = sorted((RIG / "m1_batch_multi" / ARM).glob("r*"), key=lambda p: int(p.name[1:]))
    print(f"{'rep':>4} {'editfile':>22} {'edits':>5} {'err':>3} {'sub':>3} {'patch':>6} {'resolved':>8}  goldshape")
    print("-" * 100)
    for d in reps:
        tr = d / "traces" / f"trace_{TASK}.json"
        if not tr.exists():
            continue
        j = json.loads(ANSI.sub("", tr.read_text(encoding="utf-8")))
        files, edits, errs, subs, goldshape = [], 0, 0, 0, False
        for s in j["steps"]:
            for tc in (s.get("tool_calls") or []):
                fn = tc.get("function_name")
                args = tc.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {}
                obs = s.get("observation") or {}
                c = obs.get("content") if isinstance(obs, dict) else obs
                try:
                    oj = json.loads(c) if isinstance(c, str) else (c or {})
                except Exception:
                    oj = {}
                st = (oj or {}).get("status")
                if fn == "edit_file":
                    edits += 1
                    fp = args.get("filepath") or args.get("path") or "?"
                    if fp not in files:
                        files.append(fp)
                    if st != "ok":
                        errs += 1
                    n = args.get("new_string") or ""
                    if fp == GOLD_FILE and re.search(r"def isatty", n) and "__file" in n:
                        goldshape = True
                elif fn == "submit_patch":
                    subs += 1
        res, patch = None, 0
        rf = d / "task_results.jsonl"
        if rf.exists():
            for line in open(rf, encoding="utf-8"):
                if line.strip():
                    r = json.loads(line)
                    if r.get("instance_id") == TASK:
                        res = bool(r.get("resolved"))
                        patch = int(r.get("agent_patch_size") or 0)
        print(f"{d.name:>4} {','.join(f.replace('rich/', '') for f in files)[:22]:>22} "
              f"{edits:>5} {errs:>3} {subs:>3} {patch:>6} {str(res):>8}  {goldshape}")

    # the winning edit, verbatim
    d0 = RIG / "m1_batch_multi" / ARM / "r0"
    tr = d0 / "traces" / f"trace_{TASK}.json"
    if tr.exists():
        j = json.loads(ANSI.sub("", tr.read_text(encoding="utf-8")))
        print("\n=== r0 (ONLY SUCCESS): the edit that worked ===")
        for s in j["steps"]:
            for tc in (s.get("tool_calls") or []):
                if tc.get("function_name") == "edit_file":
                    a = tc.get("arguments") or {}
                    if isinstance(a, str):
                        a = json.loads(a)
                    print("filepath:", a.get("filepath"))
                    print("OLD:", repr(a.get("old_string")))
                    print("NEW:", repr(a.get("new_string")))


if __name__ == "__main__":
    main()

