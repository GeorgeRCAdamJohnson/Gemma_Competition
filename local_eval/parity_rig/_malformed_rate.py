"""Malformed tool-call rate: the metric the de-literalisation change targets.
Log claim (our own replay): literal shell examples in prompt -> 30/96 (31%) malformed calls,
prose -> 5/96 (5%). A malformed call (`call:grep -rn ...`) is not parsed; it stays in content,
triggers the token-limit nudge, and 3 nudges end the session.

Measures it directly from ATIF traces: every `call:<name>` emitted in AGENT TEXT whose name is
not a real harness tool. No GPU needed.
Usage: python _malformed_rate.py <arm> [<arm> ...]   (arms live under m1_batch_multi/)
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
RIG = Path(__file__).resolve().parent
ANSI = re.compile(r"\x1b\[[0-9;]*m")
VALID = {"read_file", "search_code", "edit_file", "run_command", "submit_patch", "write_file",
         "get_status", "get_code_neighbors", "search_similar_code", "get_code_subgraph"}
CALL = re.compile(r"call\s*:\s*([A-Za-z_][\w\-]*)")
TOOLTAG = re.compile(r"<\|tool_call\|>|</?tool_call\|>")


def scan_arm(arm):
    root = RIG / "m1_batch_multi" / arm
    good = bad = 0
    bad_names = Counter()
    reps = 0
    for d in sorted(root.glob("r*")):
        for tr in (d / "traces").glob("*.json") if (d / "traces").exists() else []:
            try:
                j = json.loads(ANSI.sub("", tr.read_text(encoding="utf-8")))
            except Exception:
                continue
            reps += 1
            for s in j.get("steps", []):
                if s.get("source") != "agent":
                    continue
                msg = s.get("message") or ""
                for m in CALL.finditer(msg):
                    nm = m.group(1)
                    if nm in VALID:
                        good += 1
                    else:
                        bad += 1
                        bad_names[nm] += 1
    tot = good + bad
    return dict(arm=arm, reps=reps, good=good, bad=bad, tot=tot,
                rate=(bad / tot if tot else 0.0), names=bad_names)


def main():
    arms = sys.argv[1:] or ["off12", "ca5"]
    print(f"{'arm':<16} {'reps':>5} {'calls':>7} {'malformed':>10} {'rate':>7}")
    print("-" * 50)
    for a in arms:
        r = scan_arm(a)
        if not r["tot"] and not r["reps"]:
            print(f"{a:<16} (no traces)")
            continue
        print(f"{r['arm']:<16} {r['reps']:>5} {r['tot']:>7} {r['bad']:>10} {r['rate']*100:>6.1f}%")
        if r["names"]:
            top = ", ".join(f"{k}={v}" for k, v in r["names"].most_common(6))
            print(f"    malformed names: {top}")


if __name__ == "__main__":
    main()
