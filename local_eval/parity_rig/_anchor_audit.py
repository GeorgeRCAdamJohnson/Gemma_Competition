"""Anchor taxonomy: for every edit_file call in every 4077 rep, test the old_string
against the REAL snapshot bytes and classify EXACTLY why the matcher rejected it."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
SNAP = RIG.parent / "_snap4077"
ARM = "off12"
TASK = "rich_4077"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def read_snap(relpath):
    p = SNAP / relpath
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8", errors="replace")


def dunder_denorm(s):
    """model 'corrects' __file -> __file__ ; try mapping dunders back to private names"""
    return re.sub(r"__([a-z][a-z0-9_]*)__", r"__\1", s)


def ws_norm(s):
    return re.sub(r"[ \t]+", " ", s.replace("\r\n", "\n").strip())


def classify(old, real):
    if real is None:
        return "FILE_NOT_IN_SNAPSHOT"
    if old in real:
        return "MATCHES_VERBATIM(tool should have worked!)"
    if dunder_denorm(old) in real:
        return "DUNDER_HALLUCINATION(__x__ -> __x)"
    if ws_norm(old) in ws_norm(real):
        return "WHITESPACE_ONLY_DIFF"
    # try line-subset: do all non-empty lines of old appear (order) in real?
    ol = [l.strip() for l in old.strip().splitlines() if l.strip()]
    rl = [l.strip() for l in real.splitlines()]
    if ol and all(any(a == b for b in rl) for a in ol):
        return "LINES_EXIST_BUT_CONTIGUITY_BROKEN(post-edit or wrong span)"
    if ol and all(any(a == b for b in rl) for a in [dunder_denorm(x) for x in ol]):
        return "LINES_EXIST_AFTER_DENORM"
    return "HALLUCINATED_CONTENT"


def main():
    reps = sorted((RIG / "m1_batch_multi" / ARM).glob("r*"), key=lambda p: int(p.name[1:]))
    tax = Counter()
    per_rep = {}
    details = []
    for d in reps:
        tr = d / "traces" / f"trace_{TASK}.json"
        if not tr.exists():
            continue
        j = json.loads(ANSI.sub("", tr.read_text(encoding="utf-8")))
        rep_tax = Counter()
        for s in j["steps"]:
            for tc in (s.get("tool_calls") or []):
                if tc.get("function_name") != "edit_file":
                    continue
                args = tc.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        continue
                obs = s.get("observation") or {}
                c = obs.get("content") if isinstance(obs, dict) else obs
                try:
                    oj = json.loads(c) if isinstance(c, str) else (c or {})
                except Exception:
                    oj = {}
                st = (oj or {}).get("status")
                fp = args.get("filepath") or args.get("path") or "?"
                old = args.get("old_string") or ""
                real = read_snap(fp)
                verdict = classify(old, real)
                key = f"{'OK ' if st == 'ok' else 'ERR'} {verdict}"
                rep_tax[key] += 1
                tax[key] += 1
                if st != "ok":
                    details.append((d.name, fp, verdict, old[:120]))
        per_rep[d.name] = rep_tax

    print("=" * 100)
    print("ANCHOR TAXONOMY (all edit_file calls across 13 reps, tested vs snapshot bytes)")
    for k, v in tax.most_common():
        print(f"  {v:3d}  {k}")
    print("\nPER-REP:")
    for r, c in per_rep.items():
        print(f"  {r}: " + ", ".join(f"{k}={v}" for k, v in c.items()))
    print("\nFAILED ANCHOR SAMPLES:")
    for name, fp, verdict, old in details[:14]:
        print(f"  [{name}] {fp} :: {verdict}")
        print(f"        {old!r}")


if __name__ == "__main__":
    main()
